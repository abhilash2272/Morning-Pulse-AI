"""
tests/test_validation.py
=========================
Unit tests for app/processing/validation.py
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app.processing.validation import validate_document
from app.schemas.document import NormalizedDocument


def _make_doc(**kwargs) -> NormalizedDocument:
    """Create a valid NormalizedDocument with overrideable fields."""
    defaults = dict(
        title="NVIDIA Announces H200 GPU for AI Workloads",
        content="NVIDIA today announced the H200 Tensor Core GPU. " * 3,
        source_name="TechCrunch",
        source_type="gdelt",
        url="https://techcrunch.com/nvidia-h200",
        published_at=datetime(2024, 1, 15, 10, 0, 0, tzinfo=timezone.utc),
    )
    defaults.update(kwargs)
    return NormalizedDocument(**defaults)


class TestValidateDocument:
    def test_valid_document_passes(self):
        doc = _make_doc()
        result = validate_document(doc)
        assert result.is_valid is True
        assert result.reasons == []

    def test_missing_title_fails(self):
        # Use model_construct to bypass Pydantic construction validators
        # so validate_document() can catch the bad value
        doc = NormalizedDocument.model_construct(
            **{**_make_doc().model_dump(), "title": ""}
        )
        result = validate_document(doc)
        assert not result.is_valid
        assert any("title" in r for r in result.reasons)

    def test_short_title_fails(self):
        doc = NormalizedDocument.model_construct(
            **{**_make_doc().model_dump(), "title": "Hi"}
        )
        result = validate_document(doc)
        assert not result.is_valid

    def test_missing_content_ok_for_gdelt(self):
        # GDELT DOC API returns headlines/URLs only — no full text required
        doc = _make_doc(content=None, source_type="gdelt")
        result = validate_document(doc)
        assert result.is_valid

    def test_missing_content_ok_for_sec(self):
        # SEC filings may have metadata-only records
        doc = _make_doc(content=None, source_type="sec_edgar")
        result = validate_document(doc)
        assert result.is_valid

    def test_invalid_url_fails(self):
        doc = _make_doc(url="not-a-url")
        result = validate_document(doc)
        assert not result.is_valid

    def test_none_url_passes(self):
        # URL is optional
        doc = _make_doc(url=None)
        result = validate_document(doc)
        assert result.is_valid

    def test_invalid_source_type_fails(self):
        doc = NormalizedDocument.model_construct(
            **{**_make_doc().model_dump(), "source_type": "unknown_type"}
        )
        result = validate_document(doc)
        assert not result.is_valid

    def test_all_valid_source_types(self):
        for st in ("gdelt", "official_company", "sec_edgar", "research_industry"):
            doc = _make_doc(source_type=st)
            result = validate_document(doc)
            assert result.is_valid, f"Failed for source_type={st}: {result.reasons}"

    def test_very_old_date_fails(self):
        doc = _make_doc(published_at=datetime(1985, 1, 1, tzinfo=timezone.utc))
        result = validate_document(doc)
        assert not result.is_valid

    def test_missing_source_name_fails(self):
        doc = _make_doc(source_name="")
        result = validate_document(doc)
        assert not result.is_valid

    def test_bool_result(self):
        doc = _make_doc()
        result = validate_document(doc)
        assert bool(result) is True

    def test_multiple_errors_collected(self):
        base = _make_doc().model_dump()
        doc = NormalizedDocument.model_construct(
            **{**base, "title": "Hi", "content": None, "url": "bad-url", "source_type": "gdelt"}
        )
        result = validate_document(doc)
        assert not result.is_valid
        assert len(result.reasons) >= 2
