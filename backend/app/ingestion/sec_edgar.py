"""
app/ingestion/sec_edgar.py
==========================
SEC EDGAR collector for Morning Pulse AI M1.

Uses the SEC's public EDGAR APIs — no authentication required.
Follows SEC fair-access guidelines:
  - Descriptive User-Agent (set in .env as SEC_USER_AGENT)
  - Configurable request throttling (SEC_REQUEST_DELAY)
  - Respects HTTP 429 / 503 responses

APIs used
---------
1. EDGAR submissions API
   https://data.sec.gov/submissions/CIK{cik}.json
   Returns company metadata and a list of recent filings.

2. EDGAR filing index
   https://www.sec.gov/Archives/edgar/data/{cik}/{accession}/

Reference: https://www.sec.gov/developer
"""

from __future__ import annotations

import logging
import re
import time
from datetime import datetime, timezone
from typing import Any, Optional

import httpx

from app.config.settings import settings
from app.ingestion.base import BaseCollector
from app.schemas.document import RawDocument

logger = logging.getLogger(__name__)

_SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik}.json"
_FILING_INDEX_URL = "https://www.sec.gov/Archives/edgar/data/{cik}/{accession_nodash}/"
_FULL_TEXT_URL = "https://efts.sec.gov/LATEST/search-index?q={accession}&dateRange=custom&startdt={start}&enddt={end}&forms={form}"
_SEC_SEARCH_URL = "https://efts.sec.gov/LATEST/search-index?q=%22{accession}%22"
_REQUEST_TIMEOUT = 30


class SECEdgarCollector(BaseCollector):
    """
    Collects SEC EDGAR filings for companies in the company registry.

    Parameters
    ----------
    companies    : list of company dicts (from companies.json)
    filing_types : SEC form types to collect (8-K, 10-K, 10-Q)
    lookback_days: only collect filings from the past N days
    max_per_company: max number of filings to collect per company
    use_mock     : return sample data without hitting SEC
    """

    source_name = "SEC EDGAR"
    source_type = "sec_edgar"

    def __init__(
        self,
        companies: Optional[list[dict]] = None,
        filing_types: Optional[list[str]] = None,
        lookback_days: Optional[int] = None,
        max_per_company: int = 10,
        use_mock: bool = False,
    ):
        super().__init__(use_mock=use_mock)
        self.companies = companies or []
        self.filing_types = filing_types or settings.sec_filing_types
        self.lookback_days = lookback_days or settings.default_lookback_days
        self.max_per_company = max_per_company
        self._headers = {
            "User-Agent": settings.sec_user_agent,
            "Accept": "application/json",
        }

    # ---------------------------------------------------------------- #
    # fetch
    # ---------------------------------------------------------------- #
    def fetch(self) -> list[dict]:
        """Fetch recent filings for every configured company."""
        if self.use_mock:
            from app.ingestion.mock_data import get_mock_sec_records
            return get_mock_sec_records()

        all_filings: list[dict] = []
        client = httpx.Client(timeout=_REQUEST_TIMEOUT, headers=self._headers)

        try:
            for company in self.companies:
                cik = company.get("cik", "")
                if not cik:
                    self._log.warning("Company %s has no CIK — skipping", company.get("ticker"))
                    continue
                try:
                    filings = self._fetch_company_filings(client, company)
                    all_filings.extend(filings)
                    self._log.info(
                        "SEC: %s → %d filings", company.get("ticker"), len(filings)
                    )
                    time.sleep(settings.sec_request_delay)
                except Exception as exc:
                    self._log.warning(
                        "SEC fetch failed for %s: %s", company.get("ticker"), exc
                    )
        finally:
            client.close()

        return all_filings

    def _fetch_company_filings(
        self, client: httpx.Client, company: dict
    ) -> list[dict]:
        """Fetch filings list for a single company via the submissions API."""
        cik_raw = company["cik"].lstrip("0")
        cik_padded = company["cik"].zfill(10)
        url = _SUBMISSIONS_URL.format(cik=cik_padded)

        resp = client.get(url)
        if resp.status_code == 429:
            self._log.warning("SEC rate limit hit — sleeping 10s")
            time.sleep(10)
            resp = client.get(url)
        resp.raise_for_status()

        data = resp.json()
        recent = data.get("filings", {}).get("recent", {})

        forms = recent.get("form", [])
        dates = recent.get("filingDate", [])
        accessions = recent.get("accessionNumber", [])
        primary_docs = recent.get("primaryDocument", [])
        descriptions = recent.get("primaryDocDescription", [])

        results: list[dict] = []
        cutoff = _days_ago(self.lookback_days)

        for i, form in enumerate(forms):
            if form not in self.filing_types:
                continue
            if len(results) >= self.max_per_company:
                break

            filing_date_str = dates[i] if i < len(dates) else ""
            filing_date = _parse_sec_date(filing_date_str)
            if filing_date and filing_date < cutoff:
                continue  # Too old

            accession = accessions[i] if i < len(accessions) else ""
            primary_doc = primary_docs[i] if i < len(primary_docs) else ""
            description = descriptions[i] if i < len(descriptions) else ""

            accession_nodash = accession.replace("-", "")
            filing_url = (
                f"https://www.sec.gov/Archives/edgar/data/"
                f"{cik_raw}/{accession_nodash}/{primary_doc}"
            ) if primary_doc else (
                f"https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany"
                f"&CIK={cik_padded}&type={form}&dateb=&owner=include&count=10"
            )

            results.append({
                "company": company,
                "cik": company["cik"],
                "ticker": company.get("ticker", ""),
                "company_name": company.get("company_name", ""),
                "form": form,
                "filing_date": filing_date_str,
                "accession_number": accession,
                "primary_document": primary_doc,
                "description": description,
                "filing_url": filing_url,
                "content": None,  # Fetched separately below
            })

        # Optionally fetch the text of each filing document
        for filing in results:
            try:
                filing["content"] = self._fetch_filing_text(
                    client, filing["filing_url"]
                )
                time.sleep(settings.sec_request_delay)
            except Exception as exc:
                self._log.debug("Could not fetch filing text: %s", exc)

        return results

    def _fetch_filing_text(self, client: httpx.Client, url: str) -> Optional[str]:
        """
        Fetch the text of a filing document.
        Returns up to 20,000 characters.
        """
        if not url:
            return None
        resp = client.get(url, headers={**self._headers, "Accept": "text/html,application/xhtml+xml"})
        if resp.status_code != 200:
            return None
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(resp.text, "lxml")
        for tag in soup(["script", "style"]):
            tag.decompose()
        text = soup.get_text(separator=" ", strip=True)
        return text[:20_000] if text else None

    # ---------------------------------------------------------------- #
    # parse
    # ---------------------------------------------------------------- #
    def parse(self, raw_data: list[dict]) -> list[RawDocument]:
        """Convert SEC filing dicts into RawDocument objects."""
        docs: list[RawDocument] = []
        for filing in raw_data:
            try:
                doc = self._parse_filing(filing)
                if doc:
                    docs.append(doc)
            except Exception as exc:
                self._log.warning("Failed to parse SEC filing: %s", exc)
        return docs

    def _parse_filing(self, filing: dict) -> Optional[RawDocument]:
        """Parse a single SEC filing dict into a RawDocument."""
        form = filing.get("form", "")
        company_name = filing.get("company_name", "")
        accession = filing.get("accession_number", "")
        filing_date = filing.get("filing_date", "")
        url = filing.get("filing_url", "")
        description = filing.get("description", "") or f"{form} filing"

        title = f"{company_name} — {form} ({filing_date})"
        if description:
            title = f"{company_name} — {form}: {description} ({filing_date})"

        published_at = _parse_sec_date_to_dt(filing_date)

        content = filing.get("content")

        metadata = {
            "cik": filing.get("cik", ""),
            "ticker": filing.get("ticker", ""),
            "accession_number": accession,
            "filing_type": form,
            "filing_date": filing_date,
            "filing_url": url,
            "primary_document": filing.get("primary_document", ""),
            "description": description,
        }

        return RawDocument(
            title=title,
            content=content,
            source_name="SEC EDGAR",
            source_type="sec_edgar",
            url=url if url else None,
            published_at=published_at,
            language="en",
            metadata=metadata,
        )


# ------------------------------------------------------------------ #
# Helpers
# ------------------------------------------------------------------ #

def _parse_sec_date(date_str: str) -> Optional[datetime]:
    """Parse SEC filing date string 'YYYY-MM-DD' → UTC datetime."""
    if not date_str:
        return None
    try:
        return datetime.strptime(date_str.strip(), "%Y-%m-%d").replace(
            tzinfo=timezone.utc
        )
    except ValueError:
        return None


def _parse_sec_date_to_dt(date_str: str) -> Optional[datetime]:
    return _parse_sec_date(date_str)


def _days_ago(n: int) -> datetime:
    """Return UTC datetime N days in the past."""
    from datetime import timedelta
    return datetime.now(timezone.utc) - timedelta(days=n)
