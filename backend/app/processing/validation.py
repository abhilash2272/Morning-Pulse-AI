"""
app/processing/validation.py
=============================
Pydantic-based document validation for Morning Pulse AI M1.

Invalid documents are logged and skipped — they never crash the pipeline.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from typing import Optional
from urllib.parse import urlparse

from app.schemas.document import NormalizedDocument, VALID_SOURCE_TYPES

logger = logging.getLogger(__name__)

# Minimum character lengths
MIN_TITLE_LENGTH = 5
MIN_CONTENT_LENGTH = 20

# Earliest plausible publication date (nothing before the public web)
_EARLIEST_DATE = datetime(1990, 1, 1, tzinfo=timezone.utc)
# Latest plausible: 7 days in the future (clock skew tolerance)
_FUTURE_TOLERANCE_DAYS = 7


class ValidationResult:
    """Holds the outcome of a single document validation pass."""

    __slots__ = ("is_valid", "reasons")

    def __init__(self, is_valid: bool, reasons: Optional[list[str]] = None):
        self.is_valid = is_valid
        self.reasons = reasons or []

    def __bool__(self) -> bool:
        return self.is_valid

    def __repr__(self) -> str:
        return f"<ValidationResult valid={self.is_valid} reasons={self.reasons}>"


def _is_valid_url(url: str) -> bool:
    """Return True if *url* has a valid HTTP(S) scheme and netloc."""
    try:
        p = urlparse(url)
        return p.scheme in ("http", "https") and bool(p.netloc)
    except Exception:
        return False


def validate_document(doc: NormalizedDocument) -> ValidationResult:
    """
    Validate a normalized document before database insertion.

    Checks
    ------
    - title present and long enough
    - content present and long enough (when source_type is not sec_edgar
      which may legitimately have minimal content in metadata)
    - URL valid if present
    - source_type recognized
    - published_at plausible if present

    Returns a ValidationResult; never raises.
    """
    reasons: list[str] = []

    # --- Title ---
    if not doc.title or len(doc.title.strip()) < MIN_TITLE_LENGTH:
        reasons.append(
            f"title too short or missing (min {MIN_TITLE_LENGTH} chars): {doc.title!r}"
        )

    # --- Content ---
    # Sources that legitimately have no full article text:
    #   sec_edgar : filing metadata records may omit body text
    #   gdelt     : GDELT DOC 2.0 API returns headlines/URLs only;
    #               full text requires a separate fetch to the publisher site
    _NO_CONTENT_REQUIRED = {"sec_edgar", "gdelt"}
    if doc.source_type not in _NO_CONTENT_REQUIRED:
        if not doc.content or len(doc.content.strip()) < MIN_CONTENT_LENGTH:
            reasons.append(
                f"content too short or missing (min {MIN_CONTENT_LENGTH} chars)"
            )

    # --- URL ---
    if doc.url is not None and not _is_valid_url(doc.url):
        reasons.append(f"URL is not valid: {doc.url!r}")

    # --- Source type ---
    if doc.source_type not in VALID_SOURCE_TYPES:
        reasons.append(f"unrecognized source_type: {doc.source_type!r}")

    # --- Source name ---
    if not doc.source_name or not doc.source_name.strip():
        reasons.append("source_name is missing")

    # --- Published date plausibility ---
    if doc.published_at is not None:
        now_utc = datetime.now(timezone.utc)
        future_limit = now_utc.replace(day=now_utc.day + _FUTURE_TOLERANCE_DAYS) \
            if now_utc.day + _FUTURE_TOLERANCE_DAYS <= 28 else now_utc
        if doc.published_at < _EARLIEST_DATE:
            reasons.append(f"published_at {doc.published_at} is before 1990")
        if doc.published_at > now_utc.replace(year=now_utc.year + 1):
            reasons.append(f"published_at {doc.published_at} is far in the future")

    is_valid = len(reasons) == 0

    if not is_valid:
        logger.warning(
            "Document INVALID [source=%s]: %s",
            doc.source_name,
            "; ".join(reasons),
        )

    return ValidationResult(is_valid=is_valid, reasons=reasons)
