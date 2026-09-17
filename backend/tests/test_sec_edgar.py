"""
tests/test_sec_edgar.py
========================
Unit tests for app/ingestion/sec_edgar.py — all HTTP calls are mocked.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app.ingestion.sec_edgar import SECEdgarCollector, _parse_sec_date, _days_ago


# ------------------------------------------------------------------ #
# _parse_sec_date
# ------------------------------------------------------------------ #
class TestParseSecDate:
    def test_valid_date(self):
        result = _parse_sec_date("2024-01-10")
        assert result == datetime(2024, 1, 10, tzinfo=timezone.utc)

    def test_empty_string(self):
        assert _parse_sec_date("") is None

    def test_invalid_format(self):
        assert _parse_sec_date("not-a-date") is None

    def test_returns_utc(self):
        result = _parse_sec_date("2024-03-15")
        assert result.tzinfo == timezone.utc


# ------------------------------------------------------------------ #
# _days_ago
# ------------------------------------------------------------------ #
class TestDaysAgo:
    def test_returns_past_datetime(self):
        now = datetime.now(timezone.utc)
        result = _days_ago(7)
        assert result < now
        diff = now - result
        assert 6 < diff.days <= 7


# ------------------------------------------------------------------ #
# SECEdgarCollector.parse()
# ------------------------------------------------------------------ #
class TestSECEdgarCollectorParse:
    def setup_method(self):
        self.collector = SECEdgarCollector(companies=[], use_mock=False)

    def test_parses_valid_filing(self, sample_raw_sec):
        docs = self.collector.parse([sample_raw_sec])
        assert len(docs) == 1
        doc = docs[0]
        assert "NVIDIA" in doc.title
        assert "10-K" in doc.title
        assert doc.source_type == "sec_edgar"
        assert doc.metadata["accession_number"] == "0001045810-24-000010"
        assert doc.metadata["filing_type"] == "10-K"
        assert doc.metadata["cik"] == "0001045810"

    def test_title_includes_company_form_date(self, sample_raw_sec):
        docs = self.collector.parse([sample_raw_sec])
        doc = docs[0]
        assert "NVIDIA Corporation" in doc.title
        assert "10-K" in doc.title
        assert "2024-01-10" in doc.title

    def test_language_is_english(self, sample_raw_sec):
        docs = self.collector.parse([sample_raw_sec])
        assert docs[0].language == "en"

    def test_handles_empty_list(self):
        docs = self.collector.parse([])
        assert docs == []

    def test_handles_malformed_filing(self):
        bad_filing = {"broken": True, "form": "8-K"}
        docs = self.collector.parse([bad_filing])
        # Should return 0 docs but not raise
        assert isinstance(docs, list)

    def test_content_preserved_in_metadata(self, sample_raw_sec):
        docs = self.collector.parse([sample_raw_sec])
        doc = docs[0]
        # Content should be in the doc body
        assert doc.content is not None
        assert "NVIDIA" in doc.content


# ------------------------------------------------------------------ #
# SECEdgarCollector.fetch() — mock mode
# ------------------------------------------------------------------ #
class TestSECEdgarCollectorFetch:
    def test_mock_mode_returns_records(self):
        collector = SECEdgarCollector(companies=[], use_mock=True)
        records = collector.fetch()
        assert isinstance(records, list)
        assert len(records) >= 3  # Our mock has 3 filings

    def test_mock_records_have_required_fields(self):
        collector = SECEdgarCollector(companies=[], use_mock=True)
        records = collector.fetch()
        for r in records:
            assert "form" in r
            assert "accession_number" in r
            assert "company_name" in r
            assert r["form"] in ("8-K", "10-K", "10-Q")


# ------------------------------------------------------------------ #
# SECEdgarCollector.run() — mock mode end-to-end
# ------------------------------------------------------------------ #
class TestSECEdgarCollectorRun:
    def test_run_with_mock(self):
        collector = SECEdgarCollector(companies=[], use_mock=True)
        docs, stats = collector.run()
        assert stats.source == "SEC EDGAR"
        assert stats.fetched >= 3
        assert len(docs) >= 3
        for doc in docs:
            assert doc.source_type == "sec_edgar"
            assert doc.metadata.get("accession_number") is not None

    def test_no_companies_empty_live_fetch(self):
        """With no companies and live mode, fetch should return empty list gracefully."""
        collector = SECEdgarCollector(companies=[], use_mock=False)
        records = collector.fetch()
        assert records == []
