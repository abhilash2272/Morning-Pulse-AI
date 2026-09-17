"""
app/api/routes/clusters.py
===========================
Story cluster endpoints.
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database.database import get_db
from app.database import repositories as repo
from app.schemas.document import StoryClusterResponse

router = APIRouter(prefix="/api/v1/clusters", tags=["Story Clusters"])


@router.get("", response_model=list[StoryClusterResponse])
def list_clusters(
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    """
    List story clusters (groups of related documents from different sources).
    Clusters are ordered by creation time, newest first.
    """
    clusters = repo.list_clusters(db, limit=limit)
    result = []
    for c in clusters:
        result.append(
            StoryClusterResponse(
                id=c.id,
                representative_title=c.representative_title,
                created_at=c.created_at,
                document_count=len(c.document_links),
            )
        )
    return result
