"""
app/database/repositories.py
=============================
Data-access layer for Morning Pulse AI M1.

All database reads/writes go through these repository functions.
Business logic (normalization, deduplication, clustering) lives in
app/processing/ and app/services/ — not here.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional
from uuid import UUID

from sqlalchemy import select, func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database.models import Company, Document, DocumentCluster, Source, StoryCluster

logger = logging.getLogger(__name__)


# ================================================================== #
# Source repository
# ================================================================== #

def get_or_create_source(
    db: Session,
    source_name: str,
    source_type: str,
    domain: Optional[str] = None,
    base_url: Optional[str] = None,
    reliability_level: str = "medium",
) -> Source:
    """
    Return an existing Source row or create a new one.
    Uses (source_name, source_type) as the natural key.
    """
    stmt = select(Source).where(
        Source.source_name == source_name,
        Source.source_type == source_type,
    )
    source = db.execute(stmt).scalar_one_or_none()

    if source is None:
        source = Source(
            source_name=source_name,
            source_type=source_type,
            domain=domain,
            base_url=base_url,
            reliability_level=reliability_level,
        )
        db.add(source)
        db.commit()
        db.refresh(source)
        logger.debug("Created new source: %s (%s)", source_name, source_type)

    return source


def list_sources(db: Session) -> list[Source]:
    """Return all sources ordered by id."""
    return list(db.execute(select(Source).order_by(Source.id)).scalars().all())


# ================================================================== #
# Company repository
# ================================================================== #

def get_or_create_company(db: Session, company_data: dict) -> Company:
    """
    Return an existing Company row or create one from a company dict
    (as loaded from companies.json).
    """
    stmt = select(Company).where(Company.ticker == company_data["ticker"])
    company = db.execute(stmt).scalar_one_or_none()

    if company is None:
        company = Company(
            ticker=company_data["ticker"],
            company_name=company_data["company_name"],
            cik=company_data.get("cik"),
            website=company_data.get("website"),
            investor_relations_url=company_data.get("investor_relations_url"),
            news_url=company_data.get("news_url"),
            rss_feed_url=company_data.get("rss_feed_url"),
            active=company_data.get("active", True),
        )
        db.add(company)
        db.commit()
        db.refresh(company)
        logger.debug("Created new company: %s", company_data["ticker"])

    return company


def list_companies(db: Session, active_only: bool = True) -> list[Company]:
    """Return companies, optionally filtering to active ones."""
    stmt = select(Company).order_by(Company.ticker)
    if active_only:
        stmt = stmt.where(Company.active == True)  # noqa: E712
    return list(db.execute(stmt).scalars().all())


def get_company_by_ticker(db: Session, ticker: str) -> Optional[Company]:
    """Fetch a single company by ticker symbol."""
    stmt = select(Company).where(Company.ticker == ticker)
    return db.execute(stmt).scalar_one_or_none()


# ================================================================== #
# Document repository
# ================================================================== #

def document_exists_by_url(db: Session, url: str) -> bool:
    """Level-1 deduplication check: has this URL already been ingested?"""
    stmt = select(func.count()).where(Document.url == url)
    count = db.execute(stmt).scalar_one()
    return count > 0


def document_exists_by_hash(db: Session, content_hash: str) -> bool:
    """Level-2 deduplication check: has this content hash been seen?"""
    stmt = select(func.count()).where(Document.content_hash == content_hash)
    count = db.execute(stmt).scalar_one()
    return count > 0


def create_document(db: Session, doc_data: dict) -> Optional[Document]:
    """
    Insert a new document.
    Returns the created Document or None if a uniqueness conflict occurs
    (e.g. URL race condition between two pipeline runs).
    """
    doc = Document(**doc_data)
    db.add(doc)
    try:
        db.commit()
        db.refresh(doc)
        return doc
    except IntegrityError:
        db.rollback()
        logger.warning("Duplicate document skipped (integrity error): %s", doc_data.get("url"))
        return None


def get_document_by_id(db: Session, document_id: UUID) -> Optional[Document]:
    """Fetch a document by its public UUID."""
    stmt = select(Document).where(Document.document_id == document_id)
    return db.execute(stmt).scalar_one_or_none()


def get_document_by_db_id(db: Session, db_id: int) -> Optional[Document]:
    """Fetch a document by its internal integer PK."""
    return db.get(Document, db_id)


def list_documents(
    db: Session,
    source_type: Optional[str] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    limit: int = 50,
    offset: int = 0,
) -> list[Document]:
    """
    Return paginated documents with optional filters.
    Used by the GET /api/v1/documents endpoint.
    """
    stmt = select(Document).where(Document.is_duplicate == False)  # noqa: E712

    if source_type:
        stmt = stmt.where(Document.source_type == source_type)
    if start_date:
        stmt = stmt.where(Document.published_at >= start_date)
    if end_date:
        stmt = stmt.where(Document.published_at <= end_date)

    stmt = stmt.order_by(Document.published_at.desc().nullslast()).limit(limit).offset(offset)
    return list(db.execute(stmt).scalars().all())


def get_recent_titles(db: Session, limit: int = 500) -> list[tuple[int, str]]:
    """
    Return (id, title) pairs for recently stored documents.
    Used by Level-3 (title similarity) deduplication.
    """
    stmt = (
        select(Document.id, Document.title)
        .where(Document.is_duplicate == False)  # noqa: E712
        .order_by(Document.created_at.desc())
        .limit(limit)
    )
    rows = db.execute(stmt).all()
    return [(row[0], row[1]) for row in rows]


def count_documents(db: Session) -> int:
    """Return total number of non-duplicate documents stored."""
    stmt = select(func.count()).where(Document.is_duplicate == False)  # noqa: E712
    return db.execute(stmt).scalar_one()


# ================================================================== #
# StoryCluster repository
# ================================================================== #

def create_story_cluster(db: Session, representative_title: str) -> StoryCluster:
    """Create and persist a new story cluster."""
    cluster = StoryCluster(representative_title=representative_title)
    db.add(cluster)
    db.commit()
    db.refresh(cluster)
    return cluster


def add_document_to_cluster(
    db: Session,
    document_db_id: int,
    cluster_id: int,
    similarity_score: float,
) -> DocumentCluster:
    """Link a document to a story cluster with a similarity score."""
    link = DocumentCluster(
        document_id=document_db_id,
        cluster_id=cluster_id,
        similarity_score=similarity_score,
    )
    db.add(link)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
    db.refresh(link)
    return link


def list_clusters(db: Session, limit: int = 50) -> list[StoryCluster]:
    """Return story clusters ordered by creation time (newest first)."""
    stmt = select(StoryCluster).order_by(StoryCluster.created_at.desc()).limit(limit)
    return list(db.execute(stmt).scalars().all())


def count_clusters(db: Session) -> int:
    """Return total number of story clusters."""
    stmt = select(func.count()).select_from(StoryCluster)
    return db.execute(stmt).scalar_one()
