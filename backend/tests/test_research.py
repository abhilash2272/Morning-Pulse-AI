"""
tests/test_research.py
========================
Unit tests for app/ingestion/research.py — HTTP is mocked.
"""

from __future__ import annotations

import pytest

from app.ingestion.research import ResearchCollector


# ------------------------------------------------------------------ #
# ResearchCollector.parse()
# ------------------------------------------------------------------ #
class TestResearchCollectorParse:
    def setup_method(self):
        self.collector = ResearchCollector(sources=[], use_mock=False)

    def test_parses_valid_item(self, sample_raw_research):
        docs = self.collector.parse([sample_raw_research])
        assert len(docs) == 1
        doc = docs[0]
        assert doc.title == "The Race to Build the Most Powerful AI Chip"
        assert doc.source_type == "research_industry"
        assert doc.metadata["publisher"] == "MIT Technology Review"
        assert doc.metadata["category"] == "technology"
        assert "Rebecca Ackermann" in doc.metadata["authors"]

    def test_skips_item_without_title(self):
        item = {
            "_source_config": {"source_name": "Test", "category": "tech", "base_url": "https://test.com"},
            "title": "",
            "url": "https://test.com/article",
            "content": "Some content",
            "published_at": None,
            "authors": [],
            "tags": [],
        }
        docs = self.collector.parse([item])
        assert len(docs) == 0

    def test_content_fallback_to_summary(self):
        item = {
            "_source_config": {"source_name": "VentureBeat", "category": "ai", "base_url": "https://vb.com"},
            "title": "AI Investment Doubles in 2024",
            "url": "https://vb.com/ai-investment",
            "content": None,
            "summary": "AI investment has doubled year over year according to analysts.",
            "published_at": None,
            "authors": [],
            "tags": [],
        }
        docs = self.collector.parse([item])
        assert len(docs) == 1
        assert "doubled" in (docs[0].content or "")

    def test_handles_string_authors(self):
        item = {
            "_source_config": {"source_name": "Test", "category": "tech", "base_url": "https://test.com"},
            "title": "Some Research Article",
            "url": "https://test.com/research",
            "content": "Research content here." * 5,
            "summary": "",
            "published_at": None,
            "authors": "Single Author",
            "tags": [],
        }
        docs = self.collector.parse([item])
        assert len(docs) == 1
        assert isinstance(docs[0].metadata["authors"], list)

    def test_url_can_be_none(self):
        item = {
            "_source_config": {"source_name": "Test", "category": "tech", "base_url": "https://test.com"},
            "title": "Article Without URL",
            "url": "",
            "content": "Some research content here." * 3,
            "summary": "",
            "published_at": None,
            "authors": [],
            "tags": [],
        }
        docs = self.collector.parse([item])
        assert len(docs) == 1
        assert docs[0].url is None


# ------------------------------------------------------------------ #
# ResearchCollector.fetch() — mock mode
# ------------------------------------------------------------------ #
class TestResearchCollectorFetch:
    def test_mock_mode_returns_records(self):
        collector = ResearchCollector(sources=[], use_mock=True)
        records = collector.fetch()
        assert isinstance(records, list)
        assert len(records) >= 4

    def test_mock_records_have_source_config(self):
        collector = ResearchCollector(sources=[], use_mock=True)
        records = collector.fetch()
        for r in records:
            assert "_source_config" in r
            assert r["_source_config"].get("source_name")

    def test_mock_includes_multiple_publishers(self):
        collector = ResearchCollector(sources=[], use_mock=True)
        records = collector.fetch()
        publishers = {r["_source_config"]["source_name"] for r in records}
        assert len(publishers) >= 2


# ------------------------------------------------------------------ #
# ResearchCollector.run() — mock mode end-to-end
# ------------------------------------------------------------------ #
class TestResearchCollectorRun:
    def test_run_with_mock(self):
        collector = ResearchCollector(sources=[], use_mock=True)
        docs, stats = collector.run()
        assert stats.source == "Research/Industry"
        assert stats.fetched >= 4
        assert len(docs) >= 4
        for doc in docs:
            assert doc.source_type == "research_industry"
            assert doc.metadata.get("publisher") is not None

    def test_no_sources_no_live_results(self):
        collector = ResearchCollector(sources=[], use_mock=False)
        records = collector.fetch()
        assert records == []
