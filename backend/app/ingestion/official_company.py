"""
app/ingestion/official_company.py
==================================
Official company source collector for Morning Pulse AI M1.

Collects press releases and news from company newsrooms/IR pages.
Works entirely from the company registry (companies.json).

Priority order for each company
--------------------------------
1. RSS feed URL (rss_feed_url)   — most reliable, structured
2. News page URL (news_url)      — HTML scraping via BeautifulSoup
3. IR page (investor_relations_url) — fallback

Rules
-----
- Never bypass logins, CAPTCHAs, paywalls, or robots restrictions.
- If a source is inaccessible, log and continue to the next company.
- All output is normalized to the common document schema.
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from typing import Any, Optional
from urllib.parse import urljoin, urlparse

import feedparser
import httpx
from bs4 import BeautifulSoup

from app.config.settings import settings
from app.ingestion.base import BaseCollector
from app.schemas.document import RawDocument

logger = logging.getLogger(__name__)

_REQUEST_TIMEOUT = 20
_REQUEST_DELAY = 1.0  # seconds between requests to the same company
_MAX_ARTICLES_PER_COMPANY = 20
_COMMON_HEADERS = {
    "User-Agent": "MorningPulseAI/1.0 (academic research; contact: student@university.edu)",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}


class OfficialCompanyCollector(BaseCollector):
    """
    Collects official company news from RSS feeds and newsroom pages.

    Parameters
    ----------
    companies : list of company dicts from companies.json
    use_mock  : return sample data without hitting company sites
    """

    source_name = "Official Company"
    source_type = "official_company"

    def __init__(
        self,
        companies: Optional[list[dict]] = None,
        use_mock: bool = False,
    ):
        super().__init__(use_mock=use_mock)
        self.companies = companies or []

    # ---------------------------------------------------------------- #
    # fetch
    # ---------------------------------------------------------------- #
    def fetch(self) -> list[dict]:
        """Collect raw news items from all configured companies."""
        if self.use_mock:
            from app.ingestion.mock_data import get_mock_official_records
            return get_mock_official_records()

        all_items: list[dict] = []
        client = httpx.Client(
            timeout=_REQUEST_TIMEOUT,
            headers=_COMMON_HEADERS,
            follow_redirects=True,
        )

        try:
            for company in self.companies:
                if not company.get("active", True):
                    continue
                try:
                    items = self._collect_company(client, company)
                    all_items.extend(items)
                    self._log.info(
                        "[Official] %s → %d items", company.get("ticker"), len(items)
                    )
                    time.sleep(_REQUEST_DELAY)
                except Exception as exc:
                    self._log.warning(
                        "[Official] %s failed: %s", company.get("ticker"), exc
                    )
        finally:
            client.close()

        return all_items

    def _collect_company(self, client: httpx.Client, company: dict) -> list[dict]:
        """Try RSS first, then HTML scrape."""
        rss_url = company.get("rss_feed_url")
        if rss_url:
            items = self._fetch_rss(rss_url, company)
            if items:
                return items[:_MAX_ARTICLES_PER_COMPANY]

        news_url = company.get("news_url")
        if news_url:
            items = self._scrape_news_page(client, news_url, company)
            if items:
                return items[:_MAX_ARTICLES_PER_COMPANY]

        ir_url = company.get("investor_relations_url")
        if ir_url:
            items = self._scrape_news_page(client, ir_url, company)
            return items[:_MAX_ARTICLES_PER_COMPANY]

        return []

    # ---------------------------------------------------------------- #
    # RSS feed collection
    # ---------------------------------------------------------------- #
    def _fetch_rss(self, rss_url: str, company: dict) -> list[dict]:
        """Parse an RSS/Atom feed using feedparser."""
        try:
            feed = feedparser.parse(rss_url)
            if feed.bozo and not feed.entries:
                self._log.debug("RSS parse error for %s: %s", rss_url, feed.bozo_exception)
                return []

            items: list[dict] = []
            for entry in feed.entries[:_MAX_ARTICLES_PER_COMPANY]:
                item = {
                    "_source": "rss",
                    "company": company,
                    "title": entry.get("title", ""),
                    "url": entry.get("link", ""),
                    "summary": entry.get("summary", "") or entry.get("description", ""),
                    "content": _get_feed_content(entry),
                    "published_at": _parse_feed_date(entry),
                    "author": entry.get("author", ""),
                    "tags": [t.get("term", "") for t in entry.get("tags", [])],
                }
                items.append(item)
            return items
        except Exception as exc:
            self._log.debug("RSS fetch failed %s: %s", rss_url, exc)
            return []

    # ---------------------------------------------------------------- #
    # HTML scraping fallback
    # ---------------------------------------------------------------- #
    def _scrape_news_page(
        self, client: httpx.Client, url: str, company: dict
    ) -> list[dict]:
        """
        Attempt to extract article links from a newsroom HTML page.
        This is a best-effort fallback; many sites will block or be dynamic.
        """
        try:
            resp = client.get(url)
            if resp.status_code != 200:
                self._log.debug(
                    "HTTP %d for %s", resp.status_code, url
                )
                return []

            soup = BeautifulSoup(resp.text, "lxml")
            items: list[dict] = []
            base_domain = f"{urlparse(url).scheme}://{urlparse(url).netloc}"

            # Generic heuristic: find <a> tags whose href looks like an article
            seen: set[str] = set()
            for a_tag in soup.find_all("a", href=True):
                href = a_tag["href"].strip()
                if not href or href.startswith("#") or href.startswith("mailto:"):
                    continue
                # Make absolute
                if href.startswith("/"):
                    href = base_domain + href
                elif not href.startswith("http"):
                    href = urljoin(url, href)

                if href in seen:
                    continue
                # Only follow links within the same domain
                if urlparse(href).netloc != urlparse(url).netloc:
                    continue

                text = a_tag.get_text(strip=True)
                if len(text) < 15:
                    continue  # Too short to be a meaningful headline

                seen.add(href)
                items.append({
                    "_source": "html_scrape",
                    "company": company,
                    "title": text,
                    "url": href,
                    "summary": "",
                    "content": None,
                    "published_at": None,
                    "author": "",
                    "tags": [],
                })

                if len(items) >= _MAX_ARTICLES_PER_COMPANY:
                    break

            return items
        except Exception as exc:
            self._log.debug("HTML scrape failed %s: %s", url, exc)
            return []

    # ---------------------------------------------------------------- #
    # parse
    # ---------------------------------------------------------------- #
    def parse(self, raw_data: list[dict]) -> list[RawDocument]:
        """Convert collected company items into RawDocument objects."""
        docs: list[RawDocument] = []
        for item in raw_data:
            try:
                doc = self._parse_item(item)
                if doc:
                    docs.append(doc)
            except Exception as exc:
                self._log.warning("Failed to parse official company item: %s", exc)
        return docs

    def _parse_item(self, item: dict) -> Optional[RawDocument]:
        title = item.get("title", "").strip()
        url = item.get("url", "").strip()

        if not title:
            return None

        company = item.get("company", {})
        company_name = company.get("company_name", "")

        content = item.get("content") or item.get("summary") or None

        metadata = {
            "company_name": company_name,
            "ticker": company.get("ticker", ""),
            "section": item.get("_source", ""),
            "author": item.get("author", ""),
            "tags": item.get("tags", []),
        }

        return RawDocument(
            title=title,
            content=content,
            source_name=f"{company_name} Newsroom",
            source_type="official_company",
            url=url or None,
            published_at=item.get("published_at"),
            language=None,  # Will be detected during normalization
            metadata=metadata,
        )


# ------------------------------------------------------------------ #
# Helpers
# ------------------------------------------------------------------ #

def _get_feed_content(entry: Any) -> Optional[str]:
    """Extract the best available content from a feedparser entry."""
    content_list = entry.get("content", [])
    if content_list:
        return content_list[0].get("value", "")
    return entry.get("summary", "") or None


def _parse_feed_date(entry: Any) -> Optional[datetime]:
    """Extract and parse the published date from a feedparser entry."""
    import email.utils
    date_str = entry.get("published", "") or entry.get("updated", "")
    if not date_str:
        return None
    try:
        # feedparser provides struct_time in published_parsed
        parsed = entry.get("published_parsed") or entry.get("updated_parsed")
        if parsed:
            import calendar
            ts = calendar.timegm(parsed)
            return datetime.fromtimestamp(ts, tz=timezone.utc)
    except Exception:
        pass
    try:
        # Fallback: email.utils for RFC 2822 dates
        dt = email.utils.parsedate_to_datetime(date_str)
        return dt.astimezone(timezone.utc)
    except Exception:
        return None
