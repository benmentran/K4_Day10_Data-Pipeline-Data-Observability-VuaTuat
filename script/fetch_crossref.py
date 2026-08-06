#!/usr/bin/env python
"""Script để fetch dữ liệu thực tế từ Crossref API."""
from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

# Setup path - add src to path
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

# Change to project root for relative paths
os.chdir(PROJECT_ROOT)

from core.config import load_settings
from ingestion.crossref import (
    fetch_source_records,
    load_raw_records,
    run_validation_and_audit,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def main():
    """Main entry point để fetch và validate Crossref data."""
    logger.info("=" * 60)
    logger.info("CROSSREF DATA INGESTION PIPELINE")
    logger.info("=" * 60)

    # Load settings
    settings = load_settings(PROJECT_ROOT)
    logger.info(f"Source query: {settings.source_query}")
    logger.info(f"Max results: {settings.max_results}")
    logger.info(f"Filter: {settings.source_filter}")

    # Check if we should refresh
    if not settings.refresh_source:
        # Check if data already exists
        if settings.paths.raw_records_json.exists():
            logger.info("Raw records already exist. Loading from cache...")
            records = load_raw_records(settings.paths.raw_records_json)
            logger.info(f"Loaded {len(records)} records from cache")
        else:
            logger.info("No cached data found. Fetching from Crossref...")
            records = fetch_source_records(settings)
    else:
        logger.info("REFRESH_SOURCE=true - Fetching fresh data from Crossref...")
        records = fetch_source_records(settings)

    logger.info(f"\nTotal records fetched: {len(records)}")

    # Run validation and audit
    logger.info("\n" + "=" * 60)
    logger.info("VALIDATION & AUDIT")
    logger.info("=" * 60)
    report = run_validation_and_audit(settings)

    # Show file locations
    logger.info("\n" + "=" * 60)
    logger.info("OUTPUT FILES")
    logger.info("=" * 60)
    logger.info(f"Raw API Response: {settings.paths.raw_api_response}")
    logger.info(f"Parsed Records:   {settings.paths.raw_records_json}")

    # Verify files exist
    if settings.paths.raw_api_response.exists():
        size = settings.paths.raw_api_response.stat().st_size
        logger.info(f"  ✓ Raw response saved ({size:,} bytes)")
    if settings.paths.raw_records_json.exists():
        size = settings.paths.raw_records_json.stat().st_size
        logger.info(f"  ✓ Records saved ({size:,} bytes)")

    logger.info("\n" + "=" * 60)
    logger.info("INGESTION COMPLETE")
    logger.info("=" * 60)

    return 0


if __name__ == "__main__":
    sys.exit(main())
