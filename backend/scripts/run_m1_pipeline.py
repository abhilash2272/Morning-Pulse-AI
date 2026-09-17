#!/usr/bin/env python
"""
scripts/run_m1_pipeline.py
===========================
CLI entry point for the Morning Pulse AI M1 pipeline.

Usage
-----
# Full run (live APIs):
python scripts/run_m1_pipeline.py

# Mock mode (no external API calls):
python scripts/run_m1_pipeline.py --mock

# Run specific sources only:
python scripts/run_m1_pipeline.py --sources gdelt,sec

# Custom lookback:
python scripts/run_m1_pipeline.py --mock --lookback 14

# With semantic deduplication enabled:
python scripts/run_m1_pipeline.py --mock --semantic
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

# Ensure the backend/ directory is on the Python path so imports resolve.
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.pipeline import M1Pipeline


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Morning Pulse AI — M1 Data Collection & Processing Pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--mock",
        action="store_true",
        help="Use mock data instead of calling external APIs.",
    )
    parser.add_argument(
        "--sources",
        type=str,
        default=None,
        help="Comma-separated list of sources to run: gdelt, sec, official, research. Default: all.",
    )
    parser.add_argument(
        "--lookback",
        type=int,
        default=None,
        help="Number of days to look back for date-filtered sources.",
    )
    parser.add_argument(
        "--semantic",
        action="store_true",
        help="Enable Level-4 semantic deduplication (requires sentence-transformers).",
    )
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO",
        help="Logging verbosity.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    # Configure logging
    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    sources = [s.strip() for s in args.sources.split(",")] if args.sources else None

    pipeline = M1Pipeline(
        use_mock=args.mock,
        enable_semantic=args.semantic,
        sources=sources,
        lookback_days=args.lookback,
    )

    stats = pipeline.run()

    # Exit with non-zero code if pipeline failed
    sys.exit(0 if stats.success else 1)


if __name__ == "__main__":
    main()
