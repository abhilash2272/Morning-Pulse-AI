"""
app/processing/deduplication.py
================================
Multi-level deduplication for Morning Pulse AI M1.

IMPORTANT DESIGN DECISION
--------------------------
Two articles from different sources covering the same event are NOT
duplicates — they are related documents. This module distinguishes:

  is_exact_duplicate  → skip entirely (same URL or same content hash)
  is_related          → keep both, link via story cluster

Levels
------
L1  URL deduplication        (DB lookup)
L2  Content-hash comparison  (DB lookup)
L3  Normalised title similarity (token overlap, no DB call)
L4  Semantic similarity via Sentence Transformers (optional, gated)
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Optional

from sqlalchemy.orm import Session

from app.database import repositories as repo
from app.processing.hashing import compute_content_hash
from app.schemas.document import NormalizedDocument

logger = logging.getLogger(__name__)


@dataclass
class DuplicateCheckResult:
    """Result of running all deduplication levels on one document."""
    is_exact_duplicate: bool = False
    is_related: bool = False
    related_document_ids: list[int] = field(default_factory=list)
    duplicate_reason: Optional[str] = None


# ------------------------------------------------------------------ #
# Helpers
# ------------------------------------------------------------------ #

def _tokenize_title(title: str) -> set[str]:
    """Lowercase, strip punctuation, split into word tokens."""
    title = title.lower()
    title = re.sub(r"[^\w\s]", " ", title)
    return set(title.split())


def _title_overlap_score(title_a: str, title_b: str) -> float:
    """
    Jaccard similarity between the word-token sets of two titles.
    Returns a float in [0, 1].
    """
    tokens_a = _tokenize_title(title_a)
    tokens_b = _tokenize_title(title_b)
    if not tokens_a or not tokens_b:
        return 0.0
    intersection = tokens_a & tokens_b
    union = tokens_a | tokens_b
    return len(intersection) / len(union)


# ------------------------------------------------------------------ #
# Main entry point
# ------------------------------------------------------------------ #

def check_duplicate(
    doc: NormalizedDocument,
    db: Session,
    title_similarity_threshold: float = 0.85,
    related_threshold: float = 0.60,
    enable_semantic: bool = False,
) -> DuplicateCheckResult:
    """
    Run all applicable deduplication levels and return a result.

    Parameters
    ----------
    doc                        : the normalized document to check
    db                         : active SQLAlchemy session
    title_similarity_threshold : Jaccard score above which titles are
                                 considered exact title duplicates
    related_threshold          : Jaccard score above which documents are
                                 flagged as related (same story)
    enable_semantic            : whether to run L4 Sentence Transformers check
    """
    result = DuplicateCheckResult()

    # ---- L1: URL deduplication ----------------------------------------
    if doc.url:
        if repo.document_exists_by_url(db, doc.url):
            result.is_exact_duplicate = True
            result.duplicate_reason = f"L1: URL already exists: {doc.url}"
            logger.debug("L1 duplicate: %s", doc.url)
            return result

    # ---- L2: Content-hash deduplication ---------------------------------
    content_hash = compute_content_hash(doc.content, doc.title)
    if content_hash and repo.document_exists_by_hash(db, content_hash):
        result.is_exact_duplicate = True
        result.duplicate_reason = f"L2: content hash already exists: {content_hash[:16]}…"
        logger.debug("L2 duplicate hash: %s", content_hash[:16])
        return result

    # ---- L3: Title similarity -------------------------------------------
    recent_titles = repo.get_recent_titles(db, limit=500)
    related_ids: list[int] = []

    for db_id, stored_title in recent_titles:
        score = _title_overlap_score(doc.title, stored_title)
        if score >= title_similarity_threshold:
            # Very high similarity → treat as exact duplicate
            result.is_exact_duplicate = True
            result.duplicate_reason = (
                f"L3: title highly similar (score={score:.2f}) to doc id={db_id}"
            )
            logger.debug("L3 title duplicate: score=%.2f db_id=%d", score, db_id)
            return result
        elif score >= related_threshold:
            related_ids.append(db_id)
            logger.debug("L3 related: score=%.2f db_id=%d", score, db_id)

    if related_ids:
        result.is_related = True
        result.related_document_ids = related_ids

    # ---- L4: Semantic similarity (optional) ----------------------------
    if enable_semantic and not result.is_exact_duplicate:
        try:
            _run_semantic_check(doc, db, result)
        except Exception as exc:
            logger.warning("L4 semantic check failed (non-fatal): %s", exc)

    return result


def _run_semantic_check(
    doc: NormalizedDocument,
    db: Session,
    result: DuplicateCheckResult,
    semantic_threshold: float = 0.92,
    related_threshold: float = 0.75,
) -> None:
    """
    Level-4: Sentence Transformers cosine similarity.
    Only called when ENABLE_SEMANTIC_DEDUP=true.

    Checks the document against a small window of recent documents
    (last 200 by creation time) to keep inference time bounded.
    """
    from sentence_transformers import SentenceTransformer, util  # type: ignore

    model = SentenceTransformer("all-MiniLM-L6-v2")
    text_to_embed = (doc.title or "") + " " + (doc.content or "")[:500]
    new_embedding = model.encode(text_to_embed, convert_to_tensor=True)

    recent_titles = repo.get_recent_titles(db, limit=200)

    for db_id, stored_title in recent_titles:
        stored_embedding = model.encode(stored_title, convert_to_tensor=True)
        similarity = float(util.cos_sim(new_embedding, stored_embedding)[0][0])

        if similarity >= semantic_threshold:
            result.is_exact_duplicate = True
            result.duplicate_reason = (
                f"L4: semantic similarity {similarity:.3f} to doc id={db_id}"
            )
            return
        elif similarity >= related_threshold:
            if db_id not in result.related_document_ids:
                result.related_document_ids.append(db_id)
                result.is_related = True
