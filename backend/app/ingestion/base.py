"""
app/ingestion/base.py
=====================
Abstract base class for all Morning Pulse AI M1 collectors.

Every collector (GDELT, SEC EDGAR, Official Company, Research) must
inherit from BaseCollector and implement fetch() and parse().
The normalize() step is handled by the shared normalization module.

Usage
-----
class MyCollector(BaseCollector):
    def fetch(self) -> list[dict]:
        ...
    def parse(self, raw_data: list[dict]) -> list[RawDocument]:
        ...
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Any

from app.schemas.document import RawDocument, SourceStats
from app.processing.normalization import normalize_document
from app.schemas.document import NormalizedDocument

logger = logging.getLogger(__name__)


class BaseCollector(ABC):
    """
    Abstract base collector.

    Subclasses implement:
      fetch()  — call the external source and return raw data
      parse()  — convert raw data into RawDocument objects

    The run() method orchestrates fetch → parse → normalize and
    returns (normalized_docs, stats).
    """

    # Subclasses must set this to identify themselves in logs/stats
    source_name: str = "unknown"
    source_type: str = "unknown"

    def __init__(self, use_mock: bool = False):
        self.use_mock = use_mock
        self._log = logging.getLogger(self.__class__.__name__)

    @abstractmethod
    def fetch(self) -> list[Any]:
        """
        Retrieve raw data from the external source.
        Must never raise — log errors and return an empty list on failure.
        """
        ...

    @abstractmethod
    def parse(self, raw_data: list[Any]) -> list[RawDocument]:
        """
        Convert raw API/feed/scrape data into RawDocument objects.
        Must never raise — skip malformed records and log warnings.
        """
        ...

    def normalize(self, raw_docs: list[RawDocument]) -> list[NormalizedDocument]:
        """
        Apply the shared normalization pipeline to every RawDocument.
        Individual failures are caught and logged without stopping the batch.
        """
        normalized: list[NormalizedDocument] = []
        for raw in raw_docs:
            try:
                normalized.append(normalize_document(raw))
            except Exception as exc:
                self._log.warning(
                    "Normalization failed for document %r: %s",
                    raw.title[:60] if raw.title else "<no title>",
                    exc,
                )
        return normalized

    def run(self) -> tuple[list[NormalizedDocument], SourceStats]:
        """
        Orchestrate fetch → parse → normalize.
        Returns a tuple of (normalized documents, per-source statistics).

        This method is fault-tolerant: any exception at the fetch or parse
        stage is caught, logged, and results in an empty document list
        rather than crashing the overall pipeline.
        """
        stats = SourceStats(source=self.source_name)

        # --- Fetch ---
        try:
            raw_data = self.fetch()
            stats.fetched = len(raw_data)
            self._log.info("[%s] Fetched %d raw records", self.source_name, stats.fetched)
        except Exception as exc:
            self._log.error("[%s] fetch() failed: %s", self.source_name, exc)
            stats.errors += 1
            return [], stats

        # --- Parse ---
        try:
            raw_docs = self.parse(raw_data)
        except Exception as exc:
            self._log.error("[%s] parse() failed: %s", self.source_name, exc)
            stats.errors += 1
            return [], stats

        # --- Normalize ---
        normalized = self.normalize(raw_docs)
        stats.errors += stats.fetched - len(normalized)

        self._log.info(
            "[%s] Normalized %d / %d documents",
            self.source_name,
            len(normalized),
            stats.fetched,
        )
        return normalized, stats
