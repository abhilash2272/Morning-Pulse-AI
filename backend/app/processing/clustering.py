"""
app/processing/clustering.py
=============================
Story-cluster management for Morning Pulse AI M1.

Related documents (same event, different sources) are linked to a
StoryCluster. This is NOT deduplication — all documents are retained.
Story clusters are consumed by M4 (evidence verification) to find
independent corroboration of the same event.

Algorithm
---------
1. For each new document that has related_document_ids (from dedup check):
   a. Find if any related document already belongs to a cluster.
   b. If yes → join that cluster.
   c. If no  → create a new cluster with the current document as
               the representative, then add all related docs to it.
2. For documents with no related docs → no cluster assigned.
"""

from __future__ import annotations

import logging
from typing import Optional

from sqlalchemy.orm import Session

from app.database import repositories as repo
from app.database.models import Document, StoryCluster

logger = logging.getLogger(__name__)


def find_existing_cluster(db: Session, related_doc_ids: list[int]) -> Optional[StoryCluster]:
    """
    Check whether any of the related documents already belong to a cluster.
    Returns the first matching StoryCluster or None.
    """
    for doc_id in related_doc_ids:
        doc = repo.get_document_by_db_id(db, doc_id)
        if doc and doc.cluster_links:
            cluster_id = doc.cluster_links[0].cluster_id
            cluster = db.get(StoryCluster, cluster_id)
            if cluster:
                return cluster
    return None


def assign_to_cluster(
    db: Session,
    document: Document,
    related_doc_ids: list[int],
    similarity_score: float = 0.70,
) -> Optional[StoryCluster]:
    """
    Assign *document* to an existing or newly created story cluster.

    Parameters
    ----------
    document         : the newly stored Document ORM object
    related_doc_ids  : DB ids of already-stored related documents
    similarity_score : default score used for the link record

    Returns the StoryCluster that was used/created, or None on error.
    """
    if not related_doc_ids:
        return None

    try:
        # Try to find an existing cluster via any of the related docs
        cluster = find_existing_cluster(db, related_doc_ids)

        if cluster is None:
            # No existing cluster — create a new one
            cluster = repo.create_story_cluster(
                db=db,
                representative_title=document.title,
            )
            logger.debug(
                "Created story cluster id=%d for document id=%d",
                cluster.id,
                document.id,
            )

            # Also link the related (pre-existing) documents if not already linked
            for rel_id in related_doc_ids:
                rel_doc = repo.get_document_by_db_id(db, rel_id)
                if rel_doc:
                    _safe_add_to_cluster(db, rel_doc.id, cluster.id, similarity_score)

        # Link the new document to the cluster
        _safe_add_to_cluster(db, document.id, cluster.id, similarity_score)

        return cluster

    except Exception as exc:
        logger.error("Clustering failed for document id=%s: %s", document.id, exc)
        return None


def _safe_add_to_cluster(
    db: Session,
    document_db_id: int,
    cluster_id: int,
    similarity_score: float,
) -> None:
    """
    Add a document→cluster link, ignoring duplicate-link errors.
    """
    # Check if link already exists
    from sqlalchemy import select
    from app.database.models import DocumentCluster

    exists = db.execute(
        select(DocumentCluster).where(
            DocumentCluster.document_id == document_db_id,
            DocumentCluster.cluster_id == cluster_id,
        )
    ).scalar_one_or_none()

    if exists is None:
        repo.add_document_to_cluster(
            db=db,
            document_db_id=document_db_id,
            cluster_id=cluster_id,
            similarity_score=similarity_score,
        )
        logger.debug(
            "Linked document id=%d to cluster id=%d (score=%.2f)",
            document_db_id,
            cluster_id,
            similarity_score,
        )
