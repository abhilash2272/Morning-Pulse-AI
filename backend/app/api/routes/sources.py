"""
app/api/routes/sources.py
==========================
Source metadata endpoints.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database.database import get_db
from app.database import repositories as repo
from app.schemas.document import SourceResponse

router = APIRouter(prefix="/api/v1/sources", tags=["Sources"])


@router.get("", response_model=list[SourceResponse])
def list_sources(db: Session = Depends(get_db)):
    """
    List all registered data sources with their reliability metadata.
    """
    return repo.list_sources(db)
