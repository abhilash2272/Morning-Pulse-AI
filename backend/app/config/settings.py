"""
app/config/settings.py
======================
Central configuration for Morning Pulse AI.

All values are read from environment variables (or a .env file).
No secrets are hardcoded here.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field


class Settings(BaseSettings):
    """
    Application-wide settings loaded from environment / .env file.
    Pydantic-settings automatically reads .env if present.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ------------------------------------------------------------------ #
    # Database
    # ------------------------------------------------------------------ #
    database_url: str = Field(
        default="postgresql://postgres:password@localhost:5432/morning_pulse",
        description="SQLAlchemy-compatible PostgreSQL connection string.",
    )

    # ------------------------------------------------------------------ #
    # SEC EDGAR
    # ------------------------------------------------------------------ #
    sec_user_agent: str = Field(
        default="MorningPulseAI/1.0 student@university.edu",
        description="User-Agent header required by SEC fair-access policy.",
    )
    sec_request_delay: float = Field(
        default=0.5,
        description="Seconds to wait between SEC EDGAR requests.",
    )
    sec_filing_types: list[str] = Field(
        default=["8-K", "10-K", "10-Q"],
        description="SEC filing form types to collect.",
    )

    # ------------------------------------------------------------------ #
    # GDELT
    # ------------------------------------------------------------------ #
    gdelt_max_results: int = Field(
        default=100,
        description="Maximum number of GDELT articles to fetch per query.",
    )
    gdelt_fetch_article_content: bool = Field(
        default=False,
        description="Whether to follow article URLs and fetch full text.",
    )
    gdelt_queries: list[str] = Field(
        default=["NVIDIA", "Microsoft", "Apple", "Tesla", "artificial intelligence", "semiconductor"],
        description="Search queries sent to the GDELT DOC API.",
    )

    # ------------------------------------------------------------------ #
    # Pipeline
    # ------------------------------------------------------------------ #
    default_lookback_days: int = Field(
        default=7,
        description="How many days back to look when no explicit date is given.",
    )
    use_mock_data: bool = Field(
        default=False,
        description="When True, collectors return sample data instead of calling external APIs.",
    )
    enable_semantic_dedup: bool = Field(
        default=False,
        description="When True, Level-4 semantic deduplication using Sentence Transformers is enabled.",
    )

    # ------------------------------------------------------------------ #
    # Logging
    # ------------------------------------------------------------------ #
    log_level: str = Field(
        default="INFO",
        description="Python logging level: DEBUG, INFO, WARNING, ERROR, CRITICAL.",
    )

    # ------------------------------------------------------------------ #
    # FastAPI
    # ------------------------------------------------------------------ #
    api_host: str = Field(default="0.0.0.0")
    api_port: int = Field(default=8000)


# Module-level singleton so all modules can do `from app.config.settings import settings`
settings = Settings()
