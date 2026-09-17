"""
tests/test_hashing.py
======================
Unit tests for app/processing/hashing.py
"""

from __future__ import annotations

from app.processing.hashing import compute_content_hash, compute_title_hash


class TestComputeContentHash:
    def test_returns_64_char_hex(self):
        result = compute_content_hash("NVIDIA announces the H200 GPU for AI workloads.")
        assert result is not None
        assert len(result) == 64
        assert all(c in "0123456789abcdef" for c in result)

    def test_same_content_same_hash(self):
        text = "NVIDIA announces the H200 GPU for AI workloads."
        assert compute_content_hash(text) == compute_content_hash(text)

    def test_different_content_different_hash(self):
        h1 = compute_content_hash("NVIDIA H200 announcement")
        h2 = compute_content_hash("Microsoft Azure quarterly earnings")
        assert h1 != h2

    def test_whitespace_insensitive(self):
        # Extra spaces should not change the hash
        h1 = compute_content_hash("NVIDIA announces the H200 GPU")
        h2 = compute_content_hash("NVIDIA   announces   the H200   GPU")
        assert h1 == h2

    def test_case_insensitive(self):
        h1 = compute_content_hash("NVIDIA Announces H200")
        h2 = compute_content_hash("nvidia announces h200")
        assert h1 == h2

    def test_none_content_falls_back_to_title(self):
        result = compute_content_hash(None, title="Some Title")
        assert result is not None

    def test_both_none_returns_none(self):
        assert compute_content_hash(None, None) is None

    def test_empty_string_returns_none(self):
        assert compute_content_hash("", "") is None

    def test_long_content(self):
        long_text = "a" * 100_000
        result = compute_content_hash(long_text)
        assert result is not None
        assert len(result) == 64


class TestComputeTitleHash:
    def test_returns_hash(self):
        result = compute_title_hash("NVIDIA H200 GPU")
        assert result is not None
        assert len(result) == 64

    def test_case_insensitive(self):
        h1 = compute_title_hash("NVIDIA H200 GPU")
        h2 = compute_title_hash("nvidia h200 gpu")
        assert h1 == h2
