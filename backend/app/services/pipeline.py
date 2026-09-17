"""
app/services/pipeline.py
=========================
M1 Pipeline Orchestrator for Morning Pulse AI.

Runs all collectors → normalization → validation → hashing →
deduplication → clustering → persistence → statistics.

Designed to be fault-tolerant: a failure in one source never
stops other sources from running.
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from sqlalchemy.orm import Session

from app.config.settings import settings
from app.database import repositories as repo
from app.database.database import SessionLocal
from app.database.models import Document
from app.ingestion.gdelt import GDELTCollector
from app.ingestion.official_company import OfficialCompanyCollector
from app.ingestion.research import ResearchCollector
from app.ingestion.sec_edgar import SECEdgarCollector
from app.processing.clustering import assign_to_cluster
from app.processing.deduplication import check_duplicate
from app.processing.hashing import compute_content_hash
from app.processing.validation import validate_document
from app.schemas.document import (
    DocumentCreate,
    IngestionStats,
    NormalizedDocument,
    SourceStats,
)

logger = logging.getLogger(__name__)

_COMPANIES_JSON = Path(__file__).parent.parent / "config" / "companies.json"


def _load_companies() -> list[dict]:
    """Load company registry from config/companies.json."""
    try:
        with open(_COMPANIES_JSON, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as exc:
        logger.error("Failed to load companies.json: %s", exc)
        return []


class M1Pipeline:
    """
    Central M1 data collection and processing pipeline.

    Parameters
    ----------
    use_mock         : override USE_MOCK_DATA setting
    enable_semantic  : override ENABLE_SEMANTIC_DEDUP setting
    sources          : which collectors to run; None = all
    lookback_days    : days to look back for date-filtered sources
    """

    def __init__(
        self,
        use_mock: Optional[bool] = None,
        enable_semantic: Optional[bool] = None,
        sources: Optional[list[str]] = None,
        lookback_days: Optional[int] = None,
    ):
        self.use_mock = use_mock if use_mock is not None else settings.use_mock_data
        self.enable_semantic = (
            enable_semantic if enable_semantic is not None else settings.enable_semantic_dedup
        )
        self.sources = sources  # None = run all
        self.lookback_days = lookback_days or settings.default_lookback_days
        self.companies = _load_companies()

    # ------------------------------------------------------------------ #
    # Main entry point
    # ------------------------------------------------------------------ #
    def run(self) -> IngestionStats:
        """
        Execute the full M1 pipeline.
        Returns IngestionStats summarising the run.
        """
        stats = IngestionStats(
            run_id=str(uuid.uuid4()),
            started_at=datetime.now(timezone.utc),
        )

        logger.info("=" * 50)
        logger.info("MORNING PULSE AI — M1 PIPELINE STARTING")
        logger.info("Run ID: %s", stats.run_id)
        logger.info("Mock mode: %s", self.use_mock)
        logger.info("=" * 50)

        db = SessionLocal()
        try:
            # Seed company registry into the DB
            self._seed_companies(db)

            # Run each collector
            all_docs: list[tuple[NormalizedDocument, str]] = []  # (doc, source_name)

            collectors = self._build_collectors()
            for name, collector in collectors:
                if self.sources and name not in self.sources:
                    continue
                try:
                    docs, src_stats = collector.run()
                    for doc in docs:
                        all_docs.append((doc, name))
                    stats.add_source_stats(src_stats)
                    logger.info("[%s] Fetched=%d Valid=%d", name, src_stats.fetched, len(docs))
                except Exception as exc:
                    logger.error("[%s] Collector FAILED: %s", name, exc)
                    stats.add_source_stats(SourceStats(source=name, errors=1))

            # Process collected documents
            clusters_created = self._process_documents(db, all_docs, stats)
            stats.story_clusters_created = clusters_created

        except Exception as exc:
            logger.exception("Pipeline encountered a fatal error: %s", exc)
            stats.success = False
            stats.error_message = str(exc)
        finally:
            db.close()

        stats.completed_at = datetime.now(timezone.utc)
        self._print_summary(stats)
        return stats

    # ------------------------------------------------------------------ #
    # Collector factory
    # ------------------------------------------------------------------ #
    def _build_collectors(self):
        """Instantiate all four collectors."""
        active_companies = [c for c in self.companies if c.get("active", True)]
        return [
            ("gdelt", GDELTCollector(use_mock=self.use_mock)),
            ("sec", SECEdgarCollector(companies=active_companies, use_mock=self.use_mock,
                                      lookback_days=self.lookback_days)),
            ("official", OfficialCompanyCollector(companies=active_companies, use_mock=self.use_mock)),
            ("research", ResearchCollector(use_mock=self.use_mock)),
        ]

    # ------------------------------------------------------------------ #
    # Document processing
    # ------------------------------------------------------------------ #
    def _process_documents(
        self,
        db: Session,
        all_docs: list[tuple[NormalizedDocument, str]],
        stats: IngestionStats,
    ) -> int:
        """
        For each collected document:
          1. Validate
          2. Compute content hash
          3. Check duplicates
          4. Persist to DB
          5. Assign to story cluster if related

        Returns the number of new story clusters created.
        """
        clusters_created = 0

        for doc, collector_name in all_docs:
            src_stats = self._find_src_stats(stats, collector_name)

            # --- Validate ---
            validation = validate_document(doc)
            if not validation:
                logger.debug("Invalid document skipped: %s", doc.title[:60])
                if src_stats:
                    src_stats.errors += 1
                continue

            # --- Hash ---
            content_hash = compute_content_hash(doc.content, doc.title)

            # --- Deduplication ---
            dup_result = check_duplicate(
                doc=doc,
                db=db,
                enable_semantic=self.enable_semantic,
            )

            if dup_result.is_exact_duplicate:
                logger.debug(
                    "Exact duplicate skipped [%s]: %s", dup_result.duplicate_reason, doc.title[:60]
                )
                if src_stats:
                    src_stats.duplicates += 1
                stats.total_duplicates += 1
                continue

            # --- Resolve source record ---
            source_record = repo.get_or_create_source(
                db=db,
                source_name=doc.source_name,
                source_type=doc.source_type,
                reliability_level=_reliability_for_type(doc.source_type),
            )

            # --- Persist ---
            doc_data = {
                "title": doc.title,
                "content": doc.content,
                "source_id": source_record.id,
                "source_type": doc.source_type,
                "url": doc.url,
                "published_at": doc.published_at,
                "collected_at": doc.collected_at,
                "language": doc.language,
                "content_hash": content_hash,
                "is_duplicate": False,
                "metadata_": doc.metadata,
            }

            stored_doc = repo.create_document(db=db, doc_data=doc_data)

            if stored_doc is None:
                # Race-condition duplicate caught by DB uniqueness constraint
                if src_stats:
                    src_stats.duplicates += 1
                stats.total_duplicates += 1
                continue

            if src_stats:
                src_stats.stored += 1
                src_stats.valid += 1
            stats.total_stored += 1
            stats.total_valid += 1

            # --- Story clustering ---
            if dup_result.is_related and dup_result.related_document_ids:
                cluster = assign_to_cluster(
                    db=db,
                    document=stored_doc,
                    related_doc_ids=dup_result.related_document_ids,
                )
                if cluster and not _cluster_existed(db, cluster.id, stored_doc.id):
                    clusters_created += 1

        return clusters_created

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #
    def _seed_companies(self, db: Session) -> None:
        """Insert/update company rows from the company registry."""
        for company in self.companies:
            try:
                repo.get_or_create_company(db, company)
            except Exception as exc:
                logger.warning("Could not seed company %s: %s", company.get("ticker"), exc)

    @staticmethod
    def _find_src_stats(stats: IngestionStats, collector_name: str) -> Optional[SourceStats]:
        """Find the SourceStats entry for a given collector name."""
        mapping = {
            "gdelt": "GDELT",
            "sec": "SEC EDGAR",
            "official": "Official Company",
            "research": "Research/Industry",
        }
        display_name = mapping.get(collector_name, collector_name)
        for s in stats.source_stats:
            if s.source == display_name:
                return s
        return None

    @staticmethod
    def _print_summary(stats: IngestionStats) -> None:
        """Print the human-readable CLI summary table."""
        print("\n" + "=" * 50)
        print("MORNING PULSE AI - M1 PIPELINE")
        print("=" * 50)

        for src in stats.source_stats:
            print(f"\n[{src.source}]")
            print(f"  Fetched:    {src.fetched}")
            print(f"  Valid:      {src.valid}")
            print(f"  Duplicates: {src.duplicates}")
            print(f"  Stored:     {src.stored}")
            print(f"  Errors:     {src.errors}")

        print("\n" + "-" * 50)
        print("TOTAL")
        print("-" * 50)
        print(f"  Collected:        {stats.total_fetched}")
        print(f"  Valid:            {stats.total_valid}")
        print(f"  Exact duplicates: {stats.total_duplicates}")
        print(f"  Story clusters:   {stats.story_clusters_created}")
        print(f"  Stored documents: {stats.total_stored}")

        duration = ""
        if stats.completed_at and stats.started_at:
            secs = (stats.completed_at - stats.started_at).total_seconds()
            duration = f" ({secs:.1f}s)"

        status = "COMPLETED SUCCESSFULLY" if stats.success else f"FAILED: {stats.error_message}"
        print(f"\nM1 PIPELINE {status}{duration}")
        print("=" * 50 + "\n")


def _reliability_for_type(source_type: str) -> str:
    """Map source_type → reliability_level for the sources table."""
    return {
        "sec_edgar": "very_high",
        "official_company": "very_high",
        "research_industry": "high",
        "gdelt": "medium",
        "mock": "medium",
    }.get(source_type, "medium")


def _cluster_existed(db: Session, cluster_id: int, doc_id: int) -> bool:
    """Return True if this cluster had documents before this doc was added."""
    from sqlalchemy import select, func
    from app.database.models import DocumentCluster
    count = db.execute(
        select(func.count()).where(
            DocumentCluster.cluster_id == cluster_id,
            DocumentCluster.document_id != doc_id,
        )
    ).scalar_one()
    return count > 0
