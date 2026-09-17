"""
app/database/database.py
========================
SQLAlchemy engine and session factory for Morning Pulse AI.

Usage
-----
Inject `get_db` into FastAPI route dependencies for request-scoped sessions.
Use `engine` directly only in migration scripts and one-off admin tasks.
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker, Session
from typing import Generator

from app.config.settings import settings


# ------------------------------------------------------------------ #
# Engine
# ------------------------------------------------------------------ #
engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,           # Detect stale connections before use
    pool_size=5,
    max_overflow=10,
    echo=False,                   # Set True only for deep SQL debugging
)

# ------------------------------------------------------------------ #
# Session factory
# ------------------------------------------------------------------ #
SessionLocal = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
)


# ------------------------------------------------------------------ #
# Base class for all ORM models
# ------------------------------------------------------------------ #
class Base(DeclarativeBase):
    """All SQLAlchemy ORM models inherit from this class."""
    pass


# ------------------------------------------------------------------ #
# FastAPI dependency
# ------------------------------------------------------------------ #
def get_db() -> Generator[Session, None, None]:
    """
    Yields a SQLAlchemy session scoped to a single HTTP request.
    Ensures the session is always closed after use.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """
    Create all tables that do not yet exist.
    Called at application startup.
    In production, Alembic migrations are preferred over this.
    """
    # Import models so their table definitions are registered on Base.metadata
    import app.database.models  # noqa: F401
    Base.metadata.create_all(bind=engine)
