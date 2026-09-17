"""
app/processing/hashing.py
=========================
Content hashing for exact-duplicate detection in Morning Pulse AI M1.

A SHA-256 hash is computed from the normalized content (or title as
fallback). This hash is stored in the Document row and used as the
Level-2 deduplication key.
"""

from __future__ import annotations

import hashlib
import re
from typing import Optional


def compute_content_hash(content: Optional[str], title: Optional[str] = None) -> Optional[str]:
    """
    Compute a SHA-256 hash for exact-duplicate detection.

    The hash is computed from the normalized content when available,
    or from the title as a fallback.  The text is lowercased and
    whitespace is collapsed before hashing so that trivial formatting
    differences do not produce different hashes.

    Returns
    -------
    str | None
        Hex-encoded SHA-256 digest, or None if no meaningful text is
        available.
    """
    text = content or title
    if not text:
        return None

    # Normalise: lowercase + collapse whitespace
    normalised = re.sub(r"\s+", " ", text.lower()).strip()
    if not normalised:
        return None

    return hashlib.sha256(normalised.encode("utf-8")).hexdigest()


def compute_title_hash(title: str) -> str:
    """
    Convenience helper — hash only the title.
    Used for Level-3 (title similarity) pre-filtering.
    """
    normalised = re.sub(r"\s+", " ", title.lower()).strip()
    return hashlib.sha256(normalised.encode("utf-8")).hexdigest()
