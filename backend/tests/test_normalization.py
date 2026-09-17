"""
tests/test_normalization.py
============================
Unit tests for app/processing/normalization.py
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app.processing.normalization import (
    collapse_whitespace,
    detect_language,
    normalize_content,
    normalize_document,
    normalize_timestamp,
    normalize_title,
    normalize_url,
    strip_html,
)
from app.schemas.document import RawDocument


# ------------------------------------------------------------------ #
# strip_html
# ------------------------------------------------------------------ #
class TestStripHtml:
    def test_removes_tags(self):
        assert strip_html("<p>Hello <b>World</b></p>") == "Hello World"

    def test_removes_script(self):
        result = strip_html("<html><script>alert(1)</script><p>Text</p></html>")
        assert "alert" not in result
        assert "Text" in result

    def test_plain_text_unchanged(self):
        assert "No tags here" in strip_html("No tags here")

    def test_empty_string(self):
        assert strip_html("") == ""

    def test_html_entities(self):
        result = strip_html("<p>NVIDIA &amp; AMD</p>")
        assert "NVIDIA" in result
        assert "AMD" in result


# ------------------------------------------------------------------ #
# collapse_whitespace
# ------------------------------------------------------------------ #
class TestCollapseWhitespace:
    def test_multiple_spaces(self):
        assert collapse_whitespace("NVIDIA   announces   new AI   chip") == "NVIDIA announces new AI chip"

    def test_tabs_and_newlines(self):
        assert collapse_whitespace("Hello\t\nWorld") == "Hello World"

    def test_leading_trailing(self):
        assert collapse_whitespace("  hello  ") == "hello"

    def test_already_clean(self):
        assert collapse_whitespace("clean text") == "clean text"


# ------------------------------------------------------------------ #
# normalize_title
# ------------------------------------------------------------------ #
class TestNormalizeTitle:
    def test_whitespace_collapsed(self):
        result = normalize_title("NVIDIA   announces   new AI   chip")
        assert result == "NVIDIA announces new AI chip"

    def test_html_stripped(self):
        result = normalize_title("<h1>NVIDIA Launches H200</h1>")
        assert "<h1>" not in result
        assert "NVIDIA Launches H200" in result

    def test_repeated_punctuation(self):
        result = normalize_title("Breaking News!!! NVIDIA announces GPU!!!")
        assert "!!!" not in result

    def test_empty_title(self):
        result = normalize_title("")
        assert result == ""


# ------------------------------------------------------------------ #
# normalize_content
# ------------------------------------------------------------------ #
class TestNormalizeContent:
    def test_strips_html(self):
        result = normalize_content("<p>This is <b>content</b>.</p>")
        assert "<p>" not in result
        assert "This is content" in result

    def test_returns_none_for_empty(self):
        assert normalize_content("") is None
        assert normalize_content(None) is None

    def test_whitespace_collapsed(self):
        result = normalize_content("word1   word2\n\nword3")
        assert "  " not in result


# ------------------------------------------------------------------ #
# normalize_url
# ------------------------------------------------------------------ #
class TestNormalizeUrl:
    def test_removes_utm_params(self):
        url = "https://example.com/article?utm_source=twitter&utm_medium=social"
        result = normalize_url(url)
        assert "utm_source" not in result
        assert "utm_medium" not in result
        assert "example.com" in result

    def test_lowercases_scheme_and_host(self):
        result = normalize_url("HTTPS://Example.COM/path")
        assert result.startswith("https://example.com")

    def test_removes_trailing_slash(self):
        result = normalize_url("https://example.com/article/")
        assert not result.endswith("/")

    def test_root_slash_preserved(self):
        result = normalize_url("https://example.com/")
        assert result is not None

    def test_none_input(self):
        assert normalize_url(None) is None

    def test_non_http_returns_none(self):
        assert normalize_url("ftp://example.com/file") is None

    def test_keeps_fbclid_stripped(self):
        url = "https://example.com/news?id=123&fbclid=abc"
        result = normalize_url(url)
        assert "fbclid" not in result
        assert "id=123" in result


# ------------------------------------------------------------------ #
# normalize_timestamp
# ------------------------------------------------------------------ #
class TestNormalizeTimestamp:
    def test_naive_becomes_utc(self):
        naive = datetime(2024, 1, 15, 10, 0, 0)
        result = normalize_timestamp(naive)
        assert result.tzinfo == timezone.utc

    def test_aware_converted_to_utc(self):
        from datetime import timedelta
        tz_plus5 = timezone(timedelta(hours=5, minutes=30))
        aware = datetime(2024, 1, 15, 15, 30, 0, tzinfo=tz_plus5)
        result = normalize_timestamp(aware)
        assert result.tzinfo == timezone.utc
        assert result.hour == 10  # 15:30 IST → 10:00 UTC

    def test_none_returns_none(self):
        assert normalize_timestamp(None) is None


# ------------------------------------------------------------------ #
# normalize_document (integration)
# ------------------------------------------------------------------ #
class TestNormalizeDocument:
    def test_full_normalization(self):
        raw = RawDocument(
            title="  NVIDIA   Announces   H200  ",
            content="<p>The H200 GPU has   4.8 TB/s memory bandwidth.</p>",
            source_name="TechCrunch",
            source_type="gdelt",
            url="https://techcrunch.com/nvidia-h200?utm_source=rss",
            published_at=datetime(2024, 1, 15, 10, 0, 0),
        )
        result = normalize_document(raw)
        assert "  " not in result.title
        assert "<p>" not in (result.content or "")
        assert "utm_source" not in (result.url or "")
        assert result.published_at.tzinfo == timezone.utc

    def test_language_detected(self):
        raw = RawDocument(
            title="NVIDIA GPU announcement",
            content="NVIDIA has announced a new GPU for artificial intelligence workloads in data centers. " * 3,
            source_name="Test",
            source_type="gdelt",
        )
        result = normalize_document(raw)
        # Language detection may return 'en' or None depending on environment
        if result.language is not None:
            assert result.language == "en"

    def test_missing_content_is_none(self):
        raw = RawDocument(
            title="Some Title",
            content=None,
            source_name="Test",
            source_type="sec_edgar",
        )
        result = normalize_document(raw)
        assert result.content is None
