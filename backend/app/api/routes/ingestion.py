"""
app/api/routes/ingestion.py
============================
Ingestion trigger endpoints for Morning Pulse AI M1.

These endpoints allow triggering the pipeline (full or per-source)
via HTTP POST — useful for testing and scheduled runs.

Security note: These endpoints trigger data collection only.
They do not expose arbitrary code execution or DB mutation beyond
what the pipeline already does.
"""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database.database import get_db
from app.database import repositories as repo
from app.schemas.document import IngestionRequest, IngestionStats
from app.services.pipeline import M1Pipeline

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/ingestion", tags=["Ingestion"])


def _run_pipeline(sources: Optional[list[str]], req: IngestionRequest) -> IngestionStats:
    """Helper that instantiates and runs the pipeline."""
    pipeline = M1Pipeline(
        use_mock=req.use_mock,
        sources=sources,
        lookback_days=req.lookback_days,
    )
    return pipeline.run()


@router.post("/run", response_model=IngestionStats)
def run_full_pipeline(
    req: IngestionRequest = IngestionRequest(),
):
    """
    Trigger a full M1 pipeline run (all sources).

    - **use_mock**: override the USE_MOCK_DATA env setting for this run
    - **lookback_days**: how many days back to collect (default from settings)
    - **limit**: max documents per source
    """
    logger.info("Full M1 pipeline triggered via API")
    try:
        stats = _run_pipeline(sources=None, req=req)
        return stats
    except Exception as exc:
        logger.exception("Pipeline failed: %s", exc)
        raise HTTPException(status_code=500, detail=f"Pipeline error: {exc}")


@router.post("/gdelt", response_model=IngestionStats)
def run_gdelt(req: IngestionRequest = IngestionRequest()):
    """Trigger GDELT ingestion only."""
    logger.info("GDELT ingestion triggered via API")
    try:
        stats = _run_pipeline(sources=["gdelt"], req=req)
        return stats
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/sec", response_model=IngestionStats)
def run_sec(req: IngestionRequest = IngestionRequest()):
    """Trigger SEC EDGAR ingestion only."""
    logger.info("SEC EDGAR ingestion triggered via API")
    try:
        stats = _run_pipeline(sources=["sec"], req=req)
        return stats
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/official", response_model=IngestionStats)
def run_official(req: IngestionRequest = IngestionRequest()):
    """Trigger official company source ingestion only."""
    logger.info("Official company ingestion triggered via API")
    try:
        stats = _run_pipeline(sources=["official"], req=req)
        return stats
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/research", response_model=IngestionStats)
def run_research(req: IngestionRequest = IngestionRequest()):
    """Trigger research/industry source ingestion only."""
    logger.info("Research ingestion triggered via API")
    try:
        stats = _run_pipeline(sources=["research"], req=req)
        return stats
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/stats", response_model=dict)
def get_db_stats(db: Session = Depends(get_db)):
    """
    Return current database counts — useful for quick status checks.
    """
    return {
        "total_documents": repo.count_documents(db),
        "total_clusters": repo.count_clusters(db),
        "total_sources": len(repo.list_sources(db)),
        "total_companies": len(repo.list_companies(db)),
    }
