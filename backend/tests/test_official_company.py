"""
tests/test_official_company.py
================================
Unit tests for app/ingestion/official_company.py — HTTP is mocked.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app.ingestion.official_company import OfficialCompanyCollector, _parse_feed_date


# ------------------------------------------------------------------ #
# OfficialCompanyCollector.parse()
# ------------------------------------------------------------------ #
class TestOfficialCompanyCollectorParse:
    def setup_method(self):
        self.collector = OfficialCompanyCollector(companies=[], use_mock=False)

    def test_parses_valid_item(self, sample_raw_official):
        docs = self.collector.parse([sample_raw_official])
        assert len(docs) == 1
        doc = docs[0]
        assert doc.title == "NVIDIA Launches H200 GPU for Generative AI"
        assert doc.source_type == "official_company"
        assert doc.metadata["company_name"] == "NVIDIA Corporation"
        assert doc.metadata["ticker"] == "NVDA"

    def test_content_from_summary_fallback(self):
        item = {
            "_source": "rss",
            "company": {"ticker": "AAPL", "company_name": "Apple Inc."},
            "title": "Apple Announces New MacBook Pro",
            "url": "https://apple.com/newsroom/macbook-pro",
            "summary": "Introducing the new MacBook Pro with M3 chip.",
            "content": None,
            "published_at": None,
            "author": "",
            "tags": [],
        }
        docs = self.collector.parse([item])
        assert len(docs) == 1
        doc = docs[0]
        # Falls back to summary when content is None
        assert "MacBook Pro" in (doc.content or "")

    def test_skips_item_without_title(self):
        item = {
            "_source": "rss",
            "company": {"ticker": "NVDA", "company_name": "NVIDIA"},
            "title": "",
            "url": "https://nvidia.com/news/test",
            "content": "Some content",
            "published_at": None,
        }
        docs = self.collector.parse([item])
        assert len(docs) == 0

    def test_source_name_includes_company(self, sample_raw_official):
        docs = self.collector.parse([sample_raw_official])
        assert "NVIDIA" in docs[0].source_name

    def test_handles_empty_list(self):
        assert self.collector.parse([]) == []


# ------------------------------------------------------------------ #
# OfficialCompanyCollector.fetch() — mock mode
# ------------------------------------------------------------------ #
class TestOfficialCompanyCollectorFetch:
    def test_mock_mode_returns_records(self):
        collector = OfficialCompanyCollector(companies=[], use_mock=True)
        records = collector.fetch()
        assert isinstance(records, list)
        assert len(records) >= 3

    def test_mock_records_have_company_metadata(self):
        collector = OfficialCompanyCollector(companies=[], use_mock=True)
        records = collector.fetch()
        for r in records:
            assert "company" in r
            assert "title" in r
            assert r["title"]

    def test_mock_contains_nvidia_records(self):
        collector = OfficialCompanyCollector(companies=[], use_mock=True)
        records = collector.fetch()
        tickers = [r["company"]["ticker"] for r in records]
        assert "NVDA" in tickers


# ------------------------------------------------------------------ #
# OfficialCompanyCollector.run() — mock mode end-to-end
# ------------------------------------------------------------------ #
class TestOfficialCompanyCollectorRun:
    def test_run_with_mock(self):
        collector = OfficialCompanyCollector(companies=[], use_mock=True)
        docs, stats = collector.run()
        assert stats.source == "Official Company"
        assert stats.fetched >= 3
        assert len(docs) >= 3
        for doc in docs:
            assert doc.source_type == "official_company"
            assert doc.metadata.get("ticker") is not None

    def test_no_companies_no_live_results(self):
        """With no companies in live mode, fetch returns empty list."""
        collector = OfficialCompanyCollector(companies=[], use_mock=False)
        records = collector.fetch()
        assert records == []
