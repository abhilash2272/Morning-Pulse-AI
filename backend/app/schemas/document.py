"""
app/schemas/document.py
=======================
Pydantic schemas for Morning Pulse AI M1.

These schemas serve three purposes:
1. Validate data produced by collectors before DB insertion.
2. Define the shape of API responses.
3. Provide the intermediate RawDocument model passed between pipeline stages.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from pydantic import BaseModel, Field, HttpUrl, field_validator, model_validator


# ------------------------------------------------------------------ #
# Valid source types (shared across schemas)
# ------------------------------------------------------------------ #
VALID_SOURCE_TYPES = {
    "gdelt",
    "official_company",
    "sec_edgar",
    "research_industry",
    "mock",
}


# ================================================================== #
# RawDocument — output of every collector, before normalization
# ================================================================== #
class RawDocument(BaseModel):
    """
    Intermediate document model produced by every collector.
    Fields may be dirty (raw HTML, inconsistent whitespace, naive timestamps, etc.).
    Normalization converts this into a NormalizedDocument.
    """

    title: str = Field(..., description="Raw document title as collected.")
    content: Optional[str] = Field(None, description="Raw document body text or HTML.")
    source_name: str = Field(..., description="Human-readable name of the data source.")
    source_type: str = Field(..., description="One of: gdelt, official_company, sec_edgar, research_industry.")
    url: Optional[str] = Field(None, description="Canonical URL of the document.")
    published_at: Optional[datetime] = Field(None, description="Publication timestamp (may be timezone-naive).")
    language: Optional[str] = Field(None, description="ISO 639-1 language code if known.")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Source-specific metadata payload.")

    @field_validator("source_type")
    @classmethod
    def validate_source_type(cls, v: str) -> str:
        if v not in VALID_SOURCE_TYPES:
            raise ValueError(f"source_type must be one of {VALID_SOURCE_TYPES}, got {v!r}")
        return v

    model_config = {"populate_by_name": True}


# ================================================================== #
# NormalizedDocument — after normalization pipeline
# ================================================================== #
class NormalizedDocument(BaseModel):
    """
    Document after normalization: clean text, UTC timestamps, normalized URL.
    This is what the validation and deduplication steps receive.

    NOTE: Field validators are intentionally omitted here — invalid values
    are caught by validate_document() which logs and skips bad records
    rather than raising exceptions.
    """

    title: str
    content: Optional[str] = None
    source_name: str
    source_type: str
    url: Optional[str] = None
    published_at: Optional[datetime] = None  # Always UTC if present
    collected_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    language: Optional[str] = None
    content_hash: Optional[str] = None
    metadata: dict[str, Any] = Field(default_factory=dict)


# ================================================================== #
# DocumentCreate — ready to be written to the database
# ================================================================== #
class DocumentCreate(BaseModel):
    """
    Data passed to the repository layer for DB insertion.
    All fields are clean and validated at this point.
    """

    document_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    title: str
    content: Optional[str] = None
    source_id: Optional[int] = None
    source_type: str
    url: Optional[str] = None
    published_at: Optional[datetime] = None
    collected_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    language: Optional[str] = None
    content_hash: Optional[str] = None
    is_duplicate: bool = False
    metadata_: Optional[dict[str, Any]] = Field(None, alias="metadata")

    model_config = {"populate_by_name": True}


# ================================================================== #
# API Response Schemas
# ================================================================== #
class SourceResponse(BaseModel):
    id: int
    source_name: str
    source_type: str
    domain: Optional[str] = None
    base_url: Optional[str] = None
    reliability_level: str
    active: bool

    model_config = {"from_attributes": True}


class CompanyResponse(BaseModel):
    id: int
    ticker: str
    company_name: str
    cik: Optional[str] = None
    website: Optional[str] = None
    investor_relations_url: Optional[str] = None
    news_url: Optional[str] = None
    active: bool

    model_config = {"from_attributes": True}


class DocumentResponse(BaseModel):
    id: int
    document_id: uuid.UUID
    title: str
    content: Optional[str] = None
    source_type: str
    url: Optional[str] = None
    published_at: Optional[datetime] = None
    collected_at: datetime
    language: Optional[str] = None
    content_hash: Optional[str] = None
    is_duplicate: bool
    metadata: Optional[dict[str, Any]] = Field(None, alias="metadata_")

    model_config = {"from_attributes": True, "populate_by_name": True}


class StoryClusterResponse(BaseModel):
    id: int
    representative_title: str
    created_at: datetime
    document_count: int = 0

    model_config = {"from_attributes": True}


# ================================================================== #
# Ingestion Statistics
# ================================================================== #
class SourceStats(BaseModel):
    """Per-source ingestion statistics."""
    source: str
    fetched: int = 0
    valid: int = 0
    duplicates: int = 0
    errors: int = 0
    stored: int = 0


class IngestionStats(BaseModel):
    """Summary statistics from a full M1 pipeline run."""
    run_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    started_at: datetime = Field(default_factory=lambda: datetime.utcnow())
    completed_at: Optional[datetime] = None
    source_stats: list[SourceStats] = Field(default_factory=list)

    # Totals
    total_fetched: int = 0
    total_valid: int = 0
    total_duplicates: int = 0
    total_errors: int = 0
    total_stored: int = 0
    story_clusters_created: int = 0
    success: bool = True
    error_message: Optional[str] = None

    def add_source_stats(self, stats: SourceStats) -> None:
        """Merge per-source stats into the running totals."""
        self.source_stats.append(stats)
        self.total_fetched += stats.fetched
        self.total_valid += stats.valid
        self.total_duplicates += stats.duplicates
        self.total_errors += stats.errors
        self.total_stored += stats.stored


class IngestionRequest(BaseModel):
    """Optional parameters for POST /api/v1/ingestion/* endpoints."""
    use_mock: Optional[bool] = None
    lookback_days: Optional[int] = Field(None, ge=1, le=365)
    limit: Optional[int] = Field(None, ge=1, le=1000)
