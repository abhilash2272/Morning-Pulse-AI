"""
app/main.py
===========
Morning Pulse AI — FastAPI application entry point.

Mounts all routers and handles application startup/shutdown.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config.settings import settings
from app.api.routes import health, documents, sources, companies, clusters, ingestion

# ------------------------------------------------------------------ #
# Logging
# ------------------------------------------------------------------ #
logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


# ------------------------------------------------------------------ #
# Lifespan: startup + shutdown
# ------------------------------------------------------------------ #
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize DB tables on startup (Alembic handles production migrations)."""
    logger.info("Morning Pulse AI M1 starting up…")
    try:
        from app.database.database import init_db
        init_db()
        logger.info("Database tables verified/created.")
    except Exception as exc:
        logger.error("Database init failed: %s", exc)
    yield
    logger.info("Morning Pulse AI M1 shutting down.")


# ------------------------------------------------------------------ #
# FastAPI app
# ------------------------------------------------------------------ #
app = FastAPI(
    title="Morning Pulse AI — M1 Data Pipeline",
    description=(
        "Evidence-Grounded Temporal Market Intelligence Using RAG.\n\n"
        "**M1**: Data Collection & Processing pipeline.\n\n"
        "Collects market intelligence from GDELT, SEC EDGAR, official company "
        "newsrooms, and research/industry sources. Normalizes, deduplicates, "
        "clusters, and persists documents for downstream RAG (M2+)."
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# ------------------------------------------------------------------ #
# CORS
# ------------------------------------------------------------------ #
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # Tighten in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ------------------------------------------------------------------ #
# Routers
# ------------------------------------------------------------------ #
app.include_router(health.router)
app.include_router(documents.router)
app.include_router(sources.router)
app.include_router(companies.router)
app.include_router(clusters.router)
app.include_router(ingestion.router)

logger.info("All routers registered.")
