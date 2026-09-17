"""
app/ingestion/gdelt.py
======================
GDELT 2.0 DOC API collector for Morning Pulse AI M1.

The GDELT Project's DOC API allows keyword-based article search over
GDELT's monitored news universe. No API key is required; the endpoint
is publicly accessible.

API Reference
-------------
https://blog.gdeltproject.org/gdelt-doc-2-0-api-debuts/
https://api.gdeltproject.org/api/v2/doc/doc

Rate limits
-----------
GDELT recommends keeping requests reasonable. We add a small delay
between per-query calls and limit total results via config.

Article content
---------------
Fetching full article HTML is optional (gdelt_fetch_article_content=false
by default) because many publishers block automated access. When enabled,
failures are silently skipped.
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from typing import Any, Optional
from urllib.parse import urlencode

import httpx
from bs4 import BeautifulSoup

from app.config.settings import settings
from app.ingestion.base import BaseCollector
from app.schemas.document import RawDocument

logger = logging.getLogger(__name__)

_GDELT_DOC_API = "https://api.gdeltproject.org/api/v2/doc/doc"
_REQUEST_TIMEOUT = 30
_INTER_QUERY_DELAY = 1.0   # seconds between consecutive GDELT queries


class GDELTCollector(BaseCollector):
    """
    Collects market-relevant news articles via the GDELT DOC 2.0 API.

    Parameters
    ----------
    queries      : list of keyword strings to search (default from settings)
    max_results  : maximum articles to fetch per query
    use_mock     : when True, return sample data without hitting the API
    """

    source_name = "GDELT"
    source_type = "gdelt"

    def __init__(
        self,
        queries: Optional[list[str]] = None,
        max_results: Optional[int] = None,
        use_mock: bool = False,
    ):
        super().__init__(use_mock=use_mock)
        self.queries = queries or settings.gdelt_queries
        self.max_results = max_results or settings.gdelt_max_results
        self.fetch_content = settings.gdelt_fetch_article_content

    # ---------------------------------------------------------------- #
    # fetch
    # ---------------------------------------------------------------- #
    def fetch(self) -> list[dict]:
        """
        Query the GDELT DOC API for each configured search term.
        Results from all queries are combined and returned as a flat list.
        """
        if self.use_mock:
            from app.ingestion.mock_data import get_mock_gdelt_records
            return get_mock_gdelt_records()

        all_articles: list[dict] = []
        client = httpx.Client(timeout=_REQUEST_TIMEOUT)

        try:
            for query in self.queries:
                try:
                    articles = self._fetch_query(client, query)
                    all_articles.extend(articles)
                    self._log.debug(
                        "GDELT query %r → %d articles", query, len(articles)
                    )
                    time.sleep(_INTER_QUERY_DELAY)
                except Exception as exc:
                    self._log.warning("GDELT query %r failed: %s", query, exc)
        finally:
            client.close()

        # Deduplicate by URL within this batch before returning
        seen_urls: set[str] = set()
        unique: list[dict] = []
        for art in all_articles:
            url = art.get("url", "")
            if url and url not in seen_urls:
                seen_urls.add(url)
                unique.append(art)

        return unique

    def _fetch_query(self, client: httpx.Client, query: str) -> list[dict]:
        """Execute one GDELT DOC API query and return article dicts."""
        params = {
            "query": query,
            "mode": "artlist",
            "maxrecords": min(self.max_results, 250),  # API max is 250
            "format": "json",
            "sort": "DateDesc",
        }
        response = client.get(_GDELT_DOC_API, params=params)
        response.raise_for_status()
        data = response.json()
        articles = data.get("articles", [])
        # Inject the query term so parse() can reference it
        for art in articles:
            art["_query"] = query
        return articles

    # ---------------------------------------------------------------- #
    # parse
    # ---------------------------------------------------------------- #
    def parse(self, raw_data: list[dict]) -> list[RawDocument]:
        """Convert GDELT article dicts into RawDocument objects."""
        docs: list[RawDocument] = []
        for article in raw_data:
            try:
                doc = self._parse_article(article)
                if doc:
                    docs.append(doc)
            except Exception as exc:
                self._log.warning("Failed to parse GDELT article: %s", exc)
        return docs

    def _parse_article(self, article: dict) -> Optional[RawDocument]:
        """Parse a single GDELT article dict into a RawDocument."""
        title = article.get("title", "").strip()
        url = article.get("url", "").strip()

        if not title or not url:
            return None

        # Parse the GDELT date format: YYYYMMDDTHHMMSSZ
        published_at = _parse_gdelt_date(article.get("seendate", ""))

        # Optional: fetch article text
        content: Optional[str] = None
        if self.fetch_content and url:
            content = _fetch_article_text(url)

        # GDELT-specific metadata
        metadata: dict = {
            "domain": article.get("domain", ""),
            "tone": article.get("tone"),
            "gdelt_language": article.get("language", ""),
            "query": article.get("_query", ""),
            "socialimage": article.get("socialimage", ""),
        }

        return RawDocument(
            title=title,
            content=content,
            source_name="GDELT",
            source_type="gdelt",
            url=url,
            published_at=published_at,
            language=_map_gdelt_language(article.get("language", "")),
            metadata=metadata,
        )


# ------------------------------------------------------------------ #
# Helpers
# ------------------------------------------------------------------ #

def _parse_gdelt_date(date_str: str) -> Optional[datetime]:
    """
    Parse GDELT's seendate format: '20240115T123000Z'
    Returns a UTC-aware datetime or None on failure.
    """
    if not date_str:
        return None
    date_str = date_str.strip().upper()
    formats = [
        "%Y%m%dT%H%M%SZ",
        "%Y%m%dT%H%M%S",
        "%Y%m%d",
    ]
    for fmt in formats:
        try:
            dt = datetime.strptime(date_str, fmt)
            return dt.replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


def _map_gdelt_language(gdelt_lang: str) -> Optional[str]:
    """Map GDELT language names to ISO 639-1 codes."""
    mapping = {
        "english": "en",
        "german": "de",
        "french": "fr",
        "spanish": "es",
        "chinese": "zh",
        "japanese": "ja",
        "arabic": "ar",
        "portuguese": "pt",
    }
    return mapping.get(gdelt_lang.lower())


def _fetch_article_text(url: str) -> Optional[str]:
    """
    Attempt to fetch and extract the main text of an article.
    Returns None silently on any failure (network, parse, etc.).
    """
    try:
        with httpx.Client(
            timeout=15,
            follow_redirects=True,
            headers={"User-Agent": "MorningPulseAI/1.0 (academic research)"},
        ) as client:
            resp = client.get(url)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "lxml")
            # Remove navigation/footer/aside elements
            for tag in soup(["nav", "footer", "aside", "script", "style"]):
                tag.decompose()
            # Prefer <article> or <main> if present
            main = soup.find("article") or soup.find("main") or soup.body
            if main:
                return main.get_text(separator=" ", strip=True)[:10_000]
    except Exception:
        pass
    return None
