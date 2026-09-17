"""
app/api/routes/documents.py
============================
Document retrieval endpoints.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database.database import get_db
from app.database import repositories as repo
from app.schemas.document import DocumentResponse

router = APIRouter(prefix="/api/v1/documents", tags=["Documents"])


@router.get("", response_model=list[DocumentResponse])
def list_documents(
    source_type: Optional[str] = Query(None, description="Filter by source type (gdelt, sec_edgar, official_company, research_industry)"),
    start_date: Optional[datetime] = Query(None, description="Filter documents published after this datetime (ISO 8601)"),
    end_date: Optional[datetime] = Query(None, description="Filter documents published before this datetime (ISO 8601)"),
    limit: int = Query(50, ge=1, le=500, description="Maximum number of results"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
    db: Session = Depends(get_db),
):
    """
    List stored documents with optional filters.

    - **source_type**: one of `gdelt`, `sec_edgar`, `official_company`, `research_industry`
    - **start_date** / **end_date**: filter by publication date (ISO 8601 format)
    - **limit** / **offset**: pagination
    """
    documents = repo.list_documents(
        db=db,
        source_type=source_type,
        start_date=start_date,
        end_date=end_date,
        limit=limit,
        offset=offset,
    )
    return documents


@router.get("/{document_id}", response_model=DocumentResponse)
def get_document(
    document_id: UUID,
    db: Session = Depends(get_db),
):
    """
    Retrieve a single document by its UUID.
    """
    doc = repo.get_document_by_id(db, document_id)
    if doc is None:
        raise HTTPException(status_code=404, detail=f"Document {document_id} not found")
    return doc
