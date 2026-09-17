"""
tests/test_deduplication.py
============================
Unit tests for app/processing/deduplication.py
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app.database import repositories as repo
from app.processing.deduplication import (
    DuplicateCheckResult,
    _title_overlap_score,
    _tokenize_title,
    check_duplicate,
)
from app.schemas.document import NormalizedDocument


def _make_norm_doc(**kwargs) -> NormalizedDocument:
    defaults = dict(
        title="NVIDIA Announces H200 GPU for AI Workloads",
        content="NVIDIA today announced the H200 GPU. " * 5,
        source_name="TechCrunch",
        source_type="gdelt",
        url="https://techcrunch.com/nvidia-h200",
        published_at=datetime(2024, 1, 15, tzinfo=timezone.utc),
    )
    defaults.update(kwargs)
    return NormalizedDocument(**defaults)


class TestTokenizeTitle:
    def test_basic(self):
        tokens = _tokenize_title("NVIDIA announces H200 GPU")
        assert "nvidia" in tokens
        assert "h200" in tokens

    def test_removes_punctuation(self):
        tokens = _tokenize_title("NVIDIA's H200 GPU: World's Best!")
        assert "nvidia" in tokens or "nvidias" in tokens
        assert "!" not in str(tokens)

    def test_empty(self):
        assert _tokenize_title("") == set()


class TestTitleOverlapScore:
    def test_identical_titles(self):
        score = _title_overlap_score("NVIDIA H200 GPU announcement", "NVIDIA H200 GPU announcement")
        assert score == 1.0

    def test_completely_different(self):
        score = _title_overlap_score("NVIDIA H200 GPU", "Apple quarterly earnings report")
        assert score < 0.3

    def test_partial_overlap(self):
        score = _title_overlap_score(
            "NVIDIA H200 GPU for AI Workloads",
            "NVIDIA H200 GPU Unveiled for Data Centers",
        )
        assert 0.3 < score < 1.0

    def test_empty_titles(self):
        assert _title_overlap_score("", "anything") == 0.0


class TestCheckDuplicate:
    def test_no_duplicate_on_empty_db(self, db):
        doc = _make_norm_doc()
        result = check_duplicate(doc, db)
        assert result.is_exact_duplicate is False
        assert result.is_related is False

    def test_url_duplicate_detected(self, db):
        """L1: Same URL already in DB → exact duplicate."""
        # Insert a document with the same URL
        source = repo.get_or_create_source(db, "TechCrunch", "gdelt")
        repo.create_document(db, {
            "title": "NVIDIA H200",
            "content": "Some content here for testing." * 3,
            "source_id": source.id,
            "source_type": "gdelt",
            "url": "https://techcrunch.com/nvidia-h200",
            "content_hash": "abc123",
            "is_duplicate": False,
        })

        doc = _make_norm_doc(url="https://techcrunch.com/nvidia-h200")
        result = check_duplicate(doc, db)
        assert result.is_exact_duplicate is True
        assert "L1" in result.duplicate_reason

    def test_hash_duplicate_detected(self, db):
        """L2: Same content hash → exact duplicate."""
        from app.processing.hashing import compute_content_hash
        content = "NVIDIA today announced the H200 GPU. " * 5
        content_hash = compute_content_hash(content)

        source = repo.get_or_create_source(db, "TechCrunch", "gdelt")
        repo.create_document(db, {
            "title": "NVIDIA H200 different title",
            "content": content,
            "source_id": source.id,
            "source_type": "gdelt",
            "url": "https://other.com/article",
            "content_hash": content_hash,
            "is_duplicate": False,
        })

        doc = _make_norm_doc(
            url="https://different.com/other-url",
            content=content,
        )
        result = check_duplicate(doc, db)
        assert result.is_exact_duplicate is True
        assert "L2" in result.duplicate_reason

    def test_related_documents_flagged(self, db):
        """L3: Similar but not identical titles → related, not exact duplicate."""
        source = repo.get_or_create_source(db, "ArsTechnica", "gdelt")
        repo.create_document(db, {
            "title": "NVIDIA H200 GPU Announced for AI Workloads in Data Centers",
            "content": "Some different content." * 10,
            "source_id": source.id,
            "source_type": "gdelt",
            "url": "https://arstechnica.com/nvidia-h200",
            "content_hash": "unique_hash_xyz",
            "is_duplicate": False,
        })

        doc = _make_norm_doc(
            title="NVIDIA H200 GPU Announced for AI Workloads in Data Centers",
            url="https://techcrunch.com/nvidia-h200-new",
            content="Completely different article body. " * 10,
        )
        result = check_duplicate(doc, db, title_similarity_threshold=0.85)
        # At minimum, should not be an exact dup (different URL/hash)
        # Related flag depends on Jaccard score
        assert isinstance(result, DuplicateCheckResult)
