"""
app/api/routes/health.py
========================
Health check endpoint.
"""

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()


class HealthResponse(BaseModel):
    status: str
    service: str
    version: str


@router.get("/health", response_model=HealthResponse, tags=["Health"])
def health_check():
    """
    Returns service health status.
    Always returns 200 if the service is running.
    """
    return HealthResponse(
        status="ok",
        service="Morning Pulse AI — M1 Data Pipeline",
        version="1.0.0",
    )
