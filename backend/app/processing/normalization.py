"""
app/processing/normalization.py
================================
Text normalization for Morning Pulse AI M1.

Every raw document passes through these functions before validation
or deduplication. The goal is consistent, clean text — not aggressive
modification of meaning.

Steps
-----
1. HTML stripping
2. Unicode NFC normalization
3. Whitespace collapsing
4. Title cleanup
5. URL normalization
6. Timestamp → UTC
7. Language detection
"""

from __future__ import annotations

import logging
import re
import unicodedata
from datetime import datetime, timezone
from typing import Optional
from urllib.parse import urlparse, urlunparse, urlencode, parse_qsl

from bs4 import BeautifulSoup

from app.schemas.document import RawDocument, NormalizedDocument

logger = logging.getLogger(__name__)

# Tracking/UTM query params to strip from URLs
_TRACKING_PARAMS = frozenset({
    "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
    "fbclid", "gclid", "ref", "source", "_ga", "mc_cid", "mc_eid",
})


# ------------------------------------------------------------------ #
# HTML stripping
# ------------------------------------------------------------------ #
def strip_html(text: str) -> str:
    """
    Remove HTML tags and decode HTML entities.
    Falls back to a simple regex if BeautifulSoup cannot parse the input.
    """
    if not text:
        return text
    try:
        soup = BeautifulSoup(text, "lxml")
        # Remove script and style blocks entirely
        for tag in soup(["script", "style", "noscript"]):
            tag.decompose()
        extracted = soup.get_text(separator=" ")
        # Collapse multiple spaces that arise from adjacent tags
        return re.sub(r" +", " ", extracted).strip()
    except Exception:
        # Fallback: strip tags with regex
        return re.sub(r"<[^>]+>", " ", text)


# ------------------------------------------------------------------ #
# Unicode normalization
# ------------------------------------------------------------------ #
def normalize_unicode(text: str) -> str:
    """Apply Unicode NFC normalization (compose canonical equivalents)."""
    return unicodedata.normalize("NFC", text)


# ------------------------------------------------------------------ #
# Whitespace collapsing
# ------------------------------------------------------------------ #
def collapse_whitespace(text: str) -> str:
    """
    Replace all runs of whitespace (spaces, tabs, newlines) with a
    single space and strip leading/trailing whitespace.
    """
    return re.sub(r"\s+", " ", text).strip()


# ------------------------------------------------------------------ #
# Title cleanup
# ------------------------------------------------------------------ #
def normalize_title(title: str) -> str:
    """
    Clean up a document title:
    - Strip HTML
    - Unicode-normalize
    - Collapse whitespace
    - Remove repeated punctuation (e.g. "NVIDIA    !!   announces")
    """
    if not title:
        return title
    title = strip_html(title)
    title = normalize_unicode(title)
    title = collapse_whitespace(title)
    # Collapse repeated punctuation
    title = re.sub(r"([!?.,;:]){2,}", r"\1", title)
    return title


# ------------------------------------------------------------------ #
# Content cleanup
# ------------------------------------------------------------------ #
def normalize_content(content: Optional[str]) -> Optional[str]:
    """
    Clean up article body content:
    - Strip HTML
    - Unicode-normalize
    - Collapse whitespace
    Returns None if the result is empty.
    """
    if not content:
        return None
    content = strip_html(content)
    content = normalize_unicode(content)
    content = collapse_whitespace(content)
    return content if content else None


# ------------------------------------------------------------------ #
# URL normalization
# ------------------------------------------------------------------ #
def normalize_url(url: Optional[str]) -> Optional[str]:
    """
    Normalize a URL:
    - Lowercase scheme and host
    - Remove tracking query parameters
    - Remove trailing slash on path (except root)
    - Return None if the URL is not parseable or clearly invalid
    """
    if not url:
        return None
    url = url.strip()
    try:
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https"):
            return None

        # Lowercase scheme and host
        scheme = parsed.scheme.lower()
        netloc = parsed.netloc.lower()

        # Strip tracking params
        query_pairs = parse_qsl(parsed.query, keep_blank_values=False)
        filtered = [(k, v) for k, v in query_pairs if k.lower() not in _TRACKING_PARAMS]
        query = urlencode(filtered)

        # Normalize path (remove trailing slash unless root)
        path = parsed.path
        if path != "/" and path.endswith("/"):
            path = path.rstrip("/")

        normalized = urlunparse((scheme, netloc, path, parsed.params, query, ""))
        return normalized
    except Exception:
        return None


# ------------------------------------------------------------------ #
# Timestamp normalization
# ------------------------------------------------------------------ #
def normalize_timestamp(dt: Optional[datetime]) -> Optional[datetime]:
    """
    Convert a datetime to UTC.
    - Timezone-aware datetimes are converted.
    - Naive datetimes are assumed to be UTC.
    - Returns None if input is None.
    """
    if dt is None:
        return None
    if dt.tzinfo is None:
        # Assume UTC for naive datetimes
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


# ------------------------------------------------------------------ #
# Language detection
# ------------------------------------------------------------------ #
def detect_language(text: Optional[str]) -> Optional[str]:
    """
    Detect language using langdetect.
    Returns ISO 639-1 code (e.g. 'en') or None if detection fails.
    Requires at least ~50 characters to be reasonably reliable.
    """
    if not text or len(text.strip()) < 50:
        return None
    try:
        from langdetect import detect, LangDetectException
        return detect(text)
    except Exception:
        return None


# ------------------------------------------------------------------ #
# Main normalization entry point
# ------------------------------------------------------------------ #
def normalize_document(raw: RawDocument) -> NormalizedDocument:
    """
    Apply the full normalization pipeline to a RawDocument.
    Returns a NormalizedDocument ready for validation and deduplication.

    This function never raises — any per-field failures are logged and
    the field is set to None/empty rather than crashing the pipeline.
    """
    # Title
    try:
        title = normalize_title(raw.title)
    except Exception as exc:
        logger.warning("Title normalization failed: %s", exc)
        title = raw.title or ""

    # Content
    try:
        content = normalize_content(raw.content)
    except Exception as exc:
        logger.warning("Content normalization failed: %s", exc)
        content = raw.content

    # URL
    try:
        url = normalize_url(raw.url)
    except Exception as exc:
        logger.warning("URL normalization failed: %s", exc)
        url = raw.url

    # Timestamp
    try:
        published_at = normalize_timestamp(raw.published_at)
    except Exception as exc:
        logger.warning("Timestamp normalization failed: %s", exc)
        published_at = raw.published_at

    # Language — use provided value or detect from content
    language = raw.language
    if not language:
        language = detect_language(content or title)

    return NormalizedDocument(
        title=title,
        content=content,
        source_name=raw.source_name,
        source_type=raw.source_type,
        url=url,
        published_at=published_at,
        language=language,
        metadata=raw.metadata,
    )
