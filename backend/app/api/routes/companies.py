"""
app/api/routes/companies.py
============================
Company registry endpoints.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database.database import get_db
from app.database import repositories as repo
from app.schemas.document import CompanyResponse

router = APIRouter(prefix="/api/v1/companies", tags=["Companies"])


@router.get("", response_model=list[CompanyResponse])
def list_companies(
    active_only: bool = True,
    db: Session = Depends(get_db),
):
    """
    List all companies in the registry.

    - **active_only**: when True (default), returns only active companies
    """
    return repo.list_companies(db, active_only=active_only)
