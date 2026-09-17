"""
app/ingestion/research.py
=========================
Research / industry source collector for Morning Pulse AI M1.

Reads from config/research_sources.json.
Each source may provide a feed_url (RSS/Atom) or api_url (JSON endpoint).
Adding new sources requires only a config change — no code modification.

Supported source types
-----------------------
- RSS / Atom feeds  (feedparser)
- JSON API endpoints (httpx)
"""

from __future__ import annotations

import json
import logging
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional
import calendar
import email.utils

import feedparser
import httpx

from app.ingestion.base import BaseCollector
from app.schemas.document import RawDocument

logger = logging.getLogger(__name__)

_REQUEST_TIMEOUT = 20
_REQUEST_DELAY = 0.5
_MAX_ITEMS_PER_SOURCE = 25
_COMMON_HEADERS = {
    "User-Agent": "MorningPulseAI/1.0 (academic research; contact: student@university.edu)",
}

_CONFIG_PATH = Path(__file__).parent.parent / "config" / "research_sources.json"


class ResearchCollector(BaseCollector):
    """
    Collects articles from public research/industry RSS feeds and APIs.

    Parameters
    ----------
    sources  : list of source config dicts (loaded from research_sources.json)
    use_mock : return sample data without hitting external sources
    """

    source_name = "Research/Industry"
    source_type = "research_industry"

    def __init__(
        self,
        sources: Optional[list[dict]] = None,
        use_mock: bool = False,
    ):
        super().__init__(use_mock=use_mock)
        if sources is not None:
            self.sources = sources
        else:
            self.sources = _load_research_sources()

    # ---------------------------------------------------------------- #
    # fetch
    # ---------------------------------------------------------------- #
    def fetch(self) -> list[dict]:
        """Collect items from all active configured sources."""
        if self.use_mock:
            from app.ingestion.mock_data import get_mock_research_records
            return get_mock_research_records()

        all_items: list[dict] = []
        client = httpx.Client(
            timeout=_REQUEST_TIMEOUT,
            headers=_COMMON_HEADERS,
            follow_redirects=True,
        )

        try:
            for source_cfg in self.sources:
                if not source_cfg.get("active", True):
                    continue
                source_name = source_cfg.get("source_name", "unknown")
                try:
                    items = self._collect_source(client, source_cfg)
                    all_items.extend(items)
                    self._log.info(
                        "[Research] %s → %d items", source_name, len(items)
                    )
                    time.sleep(_REQUEST_DELAY)
                except Exception as exc:
                    self._log.warning(
                        "[Research] %s failed: %s", source_name, exc
                    )
        finally:
            client.close()

        return all_items

    def _collect_source(self, client: httpx.Client, source_cfg: dict) -> list[dict]:
        """Route to the correct collection strategy for this source."""
        feed_url = source_cfg.get("feed_url")
        api_url = source_cfg.get("api_url")

        if feed_url:
            return self._fetch_rss(feed_url, source_cfg)
        if api_url:
            return self._fetch_api(client, api_url, source_cfg)
        return []

    def _fetch_rss(self, feed_url: str, source_cfg: dict) -> list[dict]:
        """Parse an RSS/Atom feed."""
        feed = feedparser.parse(feed_url)
        items: list[dict] = []

        for entry in feed.entries[:_MAX_ITEMS_PER_SOURCE]:
            # Parse published date
            published_at = _parse_entry_date(entry)

            # Extract content
            content = _get_entry_content(entry)

            # Authors
            authors = []
            for author in entry.get("authors", []):
                name = author.get("name", "")
                if name:
                    authors.append(name)

            items.append({
                "_source_config": source_cfg,
                "title": entry.get("title", ""),
                "url": entry.get("link", ""),
                "content": content,
                "summary": entry.get("summary", ""),
                "published_at": published_at,
                "authors": authors,
                "tags": [t.get("term", "") for t in entry.get("tags", [])],
            })

        return items

    def _fetch_api(
        self, client: httpx.Client, api_url: str, source_cfg: dict
    ) -> list[dict]:
        """
        Fetch from a JSON API endpoint.
        The exact parsing depends on the API response structure.
        This is a generic handler — add source-specific parsers in subclasses
        or via config if needed.
        """
        resp = client.get(api_url)
        resp.raise_for_status()
        data = resp.json()

        items: list[dict] = []
        # Generic: handle both list and {"articles": [...]} shapes
        if isinstance(data, list):
            entries = data
        elif isinstance(data, dict):
            entries = data.get("articles", data.get("items", data.get("results", [])))
        else:
            return []

        for entry in entries[:_MAX_ITEMS_PER_SOURCE]:
            items.append({
                "_source_config": source_cfg,
                "title": entry.get("title", "") or entry.get("name", ""),
                "url": entry.get("url", "") or entry.get("link", ""),
                "content": entry.get("content", "") or entry.get("body", ""),
                "summary": entry.get("description", "") or entry.get("summary", ""),
                "published_at": _parse_iso_date(
                    entry.get("publishedAt", "") or entry.get("date", "")
                ),
                "authors": entry.get("authors", []),
                "tags": entry.get("tags", []),
            })

        return items

    # ---------------------------------------------------------------- #
    # parse
    # ---------------------------------------------------------------- #
    def parse(self, raw_data: list[dict]) -> list[RawDocument]:
        """Convert collected research items into RawDocument objects."""
        docs: list[RawDocument] = []
        for item in raw_data:
            try:
                doc = self._parse_item(item)
                if doc:
                    docs.append(doc)
            except Exception as exc:
                self._log.warning("Failed to parse research item: %s", exc)
        return docs

    def _parse_item(self, item: dict) -> Optional[RawDocument]:
        title = item.get("title", "").strip()
        url = item.get("url", "").strip() or None
        source_cfg = item.get("_source_config", {})

        if not title:
            return None

        content = item.get("content") or item.get("summary") or None

        authors = item.get("authors", [])
        if isinstance(authors, str):
            authors = [authors]

        metadata = {
            "publisher": source_cfg.get("source_name", ""),
            "category": source_cfg.get("category", ""),
            "authors": authors,
            "tags": item.get("tags", []),
            "base_url": source_cfg.get("base_url", ""),
        }

        return RawDocument(
            title=title,
            content=content,
            source_name=source_cfg.get("source_name", "Research Source"),
            source_type="research_industry",
            url=url,
            published_at=item.get("published_at"),
            language=None,
            metadata=metadata,
        )


# ------------------------------------------------------------------ #
# Helpers
# ------------------------------------------------------------------ #

def _load_research_sources() -> list[dict]:
    """Load research source configs from the JSON file."""
    try:
        with open(_CONFIG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as exc:
        logger.error("Failed to load research_sources.json: %s", exc)
        return []


def _parse_entry_date(entry: Any) -> Optional[datetime]:
    """Extract published date from a feedparser entry."""
    try:
        parsed = entry.get("published_parsed") or entry.get("updated_parsed")
        if parsed:
            ts = calendar.timegm(parsed)
            return datetime.fromtimestamp(ts, tz=timezone.utc)
    except Exception:
        pass
    try:
        date_str = entry.get("published", "") or entry.get("updated", "")
        if date_str:
            dt = email.utils.parsedate_to_datetime(date_str)
            return dt.astimezone(timezone.utc)
    except Exception:
        pass
    return None


def _parse_iso_date(date_str: str) -> Optional[datetime]:
    """Parse an ISO 8601 date string."""
    if not date_str:
        return None
    try:
        from dateutil import parser as du_parser
        return du_parser.parse(date_str).astimezone(timezone.utc)
    except Exception:
        return None


def _get_entry_content(entry: Any) -> Optional[str]:
    """Extract the best available content from a feedparser entry."""
    content_list = entry.get("content", [])
    if content_list:
        return content_list[0].get("value", "")
    return entry.get("summary", "") or None
