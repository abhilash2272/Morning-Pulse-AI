"""
tests/test_clustering.py
=========================
Unit tests for app/processing/clustering.py
"""

from __future__ import annotations

import pytest

from app.database import repositories as repo
from app.database.models import StoryCluster, DocumentCluster
from app.processing.clustering import assign_to_cluster, find_existing_cluster


def _insert_doc(db, title: str, url: str, source_type: str = "gdelt") -> any:
    """Helper to insert a minimal test document."""
    source = repo.get_or_create_source(db, f"Source-{url[-5:]}", source_type)
    return repo.create_document(db, {
        "title": title,
        "content": f"Content for {title}. " * 5,
        "source_id": source.id,
        "source_type": source_type,
        "url": url,
        "content_hash": f"hash-{url}",
        "is_duplicate": False,
    })


class TestFindExistingCluster:
    def test_returns_none_when_no_docs_have_cluster(self, db):
        doc = _insert_doc(db, "NVIDIA H200", "https://example.com/nvda-1")
        result = find_existing_cluster(db, [doc.id])
        assert result is None

    def test_finds_cluster_from_related_doc(self, db):
        doc_a = _insert_doc(db, "NVIDIA H200 GPU", "https://techcrunch.com/nvda-h200")
        # Create a cluster and link doc_a
        cluster = repo.create_story_cluster(db, "NVIDIA H200 GPU")
        repo.add_document_to_cluster(db, doc_a.id, cluster.id, 0.95)

        doc_b = _insert_doc(db, "NVIDIA H200 Spec Sheet", "https://ars.com/nvda-h200")
        found = find_existing_cluster(db, [doc_a.id])
        assert found is not None
        assert found.id == cluster.id


class TestAssignToCluster:
    def test_creates_new_cluster_for_related_docs(self, db):
        doc_a = _insert_doc(db, "NVIDIA H200 Launch", "https://techcrunch.com/launch")
        doc_b = _insert_doc(db, "NVIDIA H200 Details", "https://ars.com/details")

        cluster = assign_to_cluster(db, doc_b, [doc_a.id], similarity_score=0.80)
        assert cluster is not None
        assert isinstance(cluster, StoryCluster)

    def test_joins_existing_cluster(self, db):
        doc_a = _insert_doc(db, "NVIDIA H200 Announced", "https://site1.com/h200")
        doc_b = _insert_doc(db, "NVIDIA H200 Launch", "https://site2.com/h200")

        # Create cluster and link doc_a
        cluster = repo.create_story_cluster(db, "NVIDIA H200")
        repo.add_document_to_cluster(db, doc_a.id, cluster.id, 0.90)

        # doc_b is related to doc_a → should join the same cluster
        result_cluster = assign_to_cluster(db, doc_b, [doc_a.id], similarity_score=0.85)
        assert result_cluster is not None
        assert result_cluster.id == cluster.id

    def test_no_related_docs_returns_none(self, db):
        doc = _insert_doc(db, "Isolated Article", "https://isolated.com/article")
        result = assign_to_cluster(db, doc, [], similarity_score=0.0)
        assert result is None

    def test_document_linked_with_score(self, db):
        doc_a = _insert_doc(db, "Article A", "https://site-a.com/a")
        doc_b = _insert_doc(db, "Article B", "https://site-b.com/b")

        cluster = assign_to_cluster(db, doc_b, [doc_a.id], similarity_score=0.75)
        assert cluster is not None

        from sqlalchemy import select
        link = db.execute(
            select(DocumentCluster).where(
                DocumentCluster.document_id == doc_b.id,
                DocumentCluster.cluster_id == cluster.id,
            )
        ).scalar_one_or_none()
        assert link is not None
        assert abs(link.similarity_score - 0.75) < 0.001

    def test_duplicate_link_not_created(self, db):
        """Adding the same document to the same cluster twice should not error."""
        doc_a = _insert_doc(db, "Article About NVIDIA", "https://test1.com/nvda")
        doc_b = _insert_doc(db, "NVIDIA Article Two", "https://test2.com/nvda")

        cluster1 = assign_to_cluster(db, doc_b, [doc_a.id], 0.80)
        cluster2 = assign_to_cluster(db, doc_b, [doc_a.id], 0.80)
        assert cluster1 is not None
