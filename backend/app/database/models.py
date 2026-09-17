"""
app/database/models.py
======================
SQLAlchemy ORM models for Morning Pulse AI M1.

Tables
------
sources          — tracked data sources with reliability metadata
companies        — company registry (populated from companies.json)
documents        — normalized, deduplicated market intelligence documents
story_clusters   — groups of related (same-event) documents
document_clusters — many-to-many link between documents and story clusters
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.database import Base


def _utcnow() -> datetime:
    """Return current UTC time (timezone-aware)."""
    return datetime.now(timezone.utc)


# ------------------------------------------------------------------ #
# Source
# ------------------------------------------------------------------ #
class Source(Base):
    """
    Represents a data source (GDELT, SEC EDGAR, company newsroom, etc.).
    One source record per distinct origin — shared across many documents.
    """

    __tablename__ = "sources"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    source_name: Mapped[str] = mapped_column(String(255), nullable=False)
    source_type: Mapped[str] = mapped_column(
        String(50), nullable=False, index=True
    )  # gdelt | official_company | sec_edgar | research_industry
    domain: Mapped[str | None] = mapped_column(String(255), nullable=True)
    base_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    reliability_level: Mapped[str] = mapped_column(
        String(50), nullable=False, default="medium"
    )  # very_high | high | medium | low
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )

    # Relationships
    documents: Mapped[list["Document"]] = relationship(
        "Document", back_populates="source"
    )

    __table_args__ = (
        UniqueConstraint("source_name", "source_type", name="uq_source_name_type"),
    )

    def __repr__(self) -> str:
        return f"<Source id={self.id} name={self.source_name!r} type={self.source_type!r}>"


# ------------------------------------------------------------------ #
# Company
# ------------------------------------------------------------------ #
class Company(Base):
    """
    Company registry — populated from config/companies.json.
    CIK is the SEC EDGAR company identifier.
    """

    __tablename__ = "companies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    ticker: Mapped[str] = mapped_column(String(20), nullable=False, unique=True, index=True)
    company_name: Mapped[str] = mapped_column(String(255), nullable=False)
    cik: Mapped[str | None] = mapped_column(String(20), nullable=True, index=True)
    website: Mapped[str | None] = mapped_column(String(512), nullable=True)
    investor_relations_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    news_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    rss_feed_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )

    def __repr__(self) -> str:
        return f"<Company ticker={self.ticker!r} name={self.company_name!r}>"


# ------------------------------------------------------------------ #
# Document
# ------------------------------------------------------------------ #
class Document(Base):
    """
    Core entity — one normalized market intelligence document.

    content_hash is SHA-256 of the normalized content and is used for
    exact-duplicate detection. url uniqueness catches URL-level duplication.

    metadata (JSONB) preserves source-specific fields:
    - GDELT:   domain, tone, language code, event data
    - SEC:     CIK, accession_number, filing_type, filing_date, filing_url
    - Company: company_name, section
    - Research: publisher, category, authors
    """

    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        default=uuid.uuid4,
        unique=True,
        index=True,
    )
    title: Mapped[str] = mapped_column(Text, nullable=False)
    content: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("sources.id", ondelete="SET NULL"), nullable=True, index=True
    )
    source_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
    collected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )
    language: Mapped[str | None] = mapped_column(String(10), nullable=True)
    content_hash: Mapped[str | None] = mapped_column(
        String(64), nullable=True, index=True
    )
    is_duplicate: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    metadata_: Mapped[dict | None] = mapped_column(
        "metadata", JSON, nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )

    # Relationships
    source: Mapped["Source | None"] = relationship("Source", back_populates="documents")
    cluster_links: Mapped[list["DocumentCluster"]] = relationship(
        "DocumentCluster", back_populates="document", cascade="all, delete-orphan"
    )

    __table_args__ = (
        # URL uniqueness — prevents re-ingesting the same article URL
        UniqueConstraint("url", name="uq_document_url"),
        # Composite index for common filtering patterns
        Index("ix_documents_source_type_published", "source_type", "published_at"),
    )

    def __repr__(self) -> str:
        return f"<Document id={self.id} title={self.title[:40]!r}>"


# ------------------------------------------------------------------ #
# StoryCluster
# ------------------------------------------------------------------ #
class StoryCluster(Base):
    """
    A cluster of related documents that report the same event from
    different sources. Created by the story-clustering step.

    This is NOT a deduplication mechanism — related documents are
    retained in full; this is a semantic grouping for M4 evidence verification.
    """

    __tablename__ = "story_clusters"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    representative_title: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )

    # Relationships
    document_links: Mapped[list["DocumentCluster"]] = relationship(
        "DocumentCluster", back_populates="cluster", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<StoryCluster id={self.id} title={self.representative_title[:40]!r}>"


# ------------------------------------------------------------------ #
# DocumentCluster  (junction table)
# ------------------------------------------------------------------ #
class DocumentCluster(Base):
    """
    Many-to-many join between Document and StoryCluster.
    similarity_score records how similar this document is to the cluster centroid.
    """

    __tablename__ = "document_clusters"

    document_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("documents.id", ondelete="CASCADE"), primary_key=True
    )
    cluster_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("story_clusters.id", ondelete="CASCADE"), primary_key=True
    )
    similarity_score: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Relationships
    document: Mapped["Document"] = relationship("Document", back_populates="cluster_links")
    cluster: Mapped["StoryCluster"] = relationship("StoryCluster", back_populates="document_links")

    def __repr__(self) -> str:
        return (
            f"<DocumentCluster doc={self.document_id} "
            f"cluster={self.cluster_id} score={self.similarity_score}>"
        )
