"""
tests/conftest.py
==================
Shared pytest fixtures for Morning Pulse AI M1 tests.

Uses an in-memory SQLite database so tests never need a live PostgreSQL.
All external HTTP calls are mocked — tests are fully offline.
"""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, Session

from app.database.database import Base
from app.database import models  # noqa: F401 — registers ORM models on Base


# ------------------------------------------------------------------ #
# In-memory SQLite engine for tests
# ------------------------------------------------------------------ #
@pytest.fixture(scope="session")
def engine():
    """Create an in-memory SQLite engine for the test session."""
    _engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
    )
    # SQLite does not enforce foreign keys by default — enable them
    @event.listens_for(_engine, "connect")
    def set_sqlite_pragma(dbapi_conn, _):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(bind=_engine)
    yield _engine
    Base.metadata.drop_all(bind=_engine)


@pytest.fixture(scope="function")
def db(engine) -> Session:
    """
    Provide a transactional test session that rolls back after each test.
    This keeps tests isolated without re-creating the schema.
    """
    connection = engine.connect()
    transaction = connection.begin()
    TestSession = sessionmaker(bind=connection, autocommit=False, autoflush=False)
    session = TestSession()

    yield session

    session.close()
    transaction.rollback()
    connection.close()


# ------------------------------------------------------------------ #
# Sample data fixtures
# ------------------------------------------------------------------ #
@pytest.fixture
def sample_raw_gdelt():
    """One GDELT article dict as returned by the DOC API."""
    return {
        "title": "NVIDIA Announces H200 AI Chip",
        "url": "https://techcrunch.com/2024/01/15/nvidia-h200",
        "domain": "techcrunch.com",
        "tone": "7.5",
        "language": "English",
        "seendate": "20240115T100000Z",
        "_query": "NVIDIA",
    }


@pytest.fixture
def sample_raw_sec():
    """One SEC filing dict as returned by the submissions API."""
    return {
        "company": {"ticker": "NVDA", "company_name": "NVIDIA Corporation", "cik": "0001045810"},
        "cik": "0001045810",
        "ticker": "NVDA",
        "company_name": "NVIDIA Corporation",
        "form": "10-K",
        "filing_date": "2024-01-10",
        "accession_number": "0001045810-24-000010",
        "primary_document": "nvda-20240128.htm",
        "description": "Annual Report",
        "filing_url": "https://www.sec.gov/Archives/edgar/data/1045810/000104581024000010/nvda-20240128.htm",
        "content": "NVIDIA Corporation Annual Report. Revenue $60.9 billion. Data center segment grew 217%.",
    }


@pytest.fixture
def sample_raw_official():
    """One official company news item dict."""
    return {
        "_source": "rss",
        "company": {"ticker": "NVDA", "company_name": "NVIDIA Corporation"},
        "title": "NVIDIA Launches H200 GPU for Generative AI",
        "url": "https://nvidianews.nvidia.com/news/nvidia-h200",
        "summary": "NVIDIA H200 delivers 2x inference speed over H100.",
        "content": "NVIDIA today announced the H200 Tensor Core GPU with HBM3e memory offering 4.8 TB/s bandwidth.",
        "published_at": None,
        "author": "NVIDIA Press",
        "tags": ["GPU", "AI"],
    }


@pytest.fixture
def sample_raw_research():
    """One research source item dict."""
    return {
        "_source_config": {
            "source_name": "MIT Technology Review",
            "category": "technology",
            "base_url": "https://www.technologyreview.com",
        },
        "title": "The Race to Build the Most Powerful AI Chip",
        "url": "https://www.technologyreview.com/2024/01/14/ai-chip-race",
        "content": "Competition among chip companies for AI dominance intensifies. " * 5,
        "summary": "Analysis of the AI chip market.",
        "published_at": None,
        "authors": ["Rebecca Ackermann"],
        "tags": ["AI", "chips"],
    }
