#!/usr/bin/env python
"""Script to run the cleaning pipeline and save clean data."""
from __future__ import annotations

from datetime import UTC, datetime
import sys
from pathlib import Path

# Add the project root to the path (parent of src/)
ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

from ingestion.cleaning import build_clean_dataframe
from ingestion.crossref import load_raw_records
from core.config import load_settings

def main():
    settings = load_settings()
    records = load_raw_records(settings.paths.raw_records_json)
    print(f"Loaded {len(records)} records from raw JSON")

    run_date = datetime(2026, 8, 6, tzinfo=UTC)
    df = build_clean_dataframe(records, run_date, settings)
    print(f"Cleaned to {len(df)} records")
    print(f"Saved CSV to: {settings.paths.clean_csv}")
    print(f"Saved JSON to: {settings.paths.clean_json}")

    # Print sample data
    print("\n--- Sample Clean Data ---")
    print(df[["paper_id", "title", "authors_joined", "published", "age_days"]].head(3).to_string())

if __name__ == "__main__":
    main()
