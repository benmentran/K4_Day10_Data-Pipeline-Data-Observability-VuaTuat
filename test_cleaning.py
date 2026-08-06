"""Test script to verify cleaning module works correctly."""
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from datetime import UTC, datetime
from src.ingestion.crossref import load_raw_records
from src.ingestion.cleaning import build_clean_dataframe
from src.core.config import load_settings


def main():
    print("=" * 60)
    print("TESTING DATA CLEANING MODULE")
    print("=" * 60)

    # Load settings
    settings = load_settings()
    print(f"\nSettings loaded:")
    print(f"  - source_query: {settings.source_query}")
    print(f"  - max_results: {settings.max_results}")

    # Load raw records
    print(f"\nLoading raw records from: {settings.paths.raw_records_json}")
    records = load_raw_records(settings.paths.raw_records_json)
    print(f"  Loaded {len(records)} raw records")

    # Run cleaning
    print("\nRunning cleaning...")
    run_date = datetime.now(UTC)
    clean_df = build_clean_dataframe(records, run_date, settings)

    print(f"\nCleaning complete:")
    print(f"  - Total records after cleaning: {len(clean_df)}")
    print(f"  - Records removed (no title or summary < 100 chars): {len(records) - len(clean_df)}")

    if not clean_df.empty:
        print(f"\nSample cleaned record:")
        print(f"  - paper_id: {clean_df.iloc[0]['paper_id']}")
        print(f"  - title: {clean_df.iloc[0]['title'][:60]}...")
        print(f"  - authors_joined: {clean_df.iloc[0]['authors_joined']}")
        print(f"  - categories_joined: {clean_df.iloc[0]['categories_joined']}")
        print(f"  - published: {clean_df.iloc[0]['published']}")
        print(f"  - age_days: {clean_df.iloc[0]['age_days']}")
        print(f"  - text_for_embedding: {clean_df.iloc[0]['text_for_embedding'][:80]}...")

        # Verify cleaning rules
        print("\n" + "=" * 60)
        print("VERIFYING CLEANING RULES")
        print("=" * 60)

        issues = []

        # Rule 1: Check no records without title
        no_title = clean_df[clean_df['title'].isna() | (clean_df['title'] == '')]
        if len(no_title) > 0:
            issues.append(f"FAIL: {len(no_title)} records without title")
        else:
            print("[PASS] No records without title")

        # Rule 2: Check summary >= 100 chars
        short_summary = clean_df[clean_df['summary'].str.len() < 100]
        if len(short_summary) > 0:
            issues.append(f"FAIL: {len(short_summary)} records with summary < 100 chars")
        else:
            print("[PASS] All summaries >= 100 characters")

        # Rule 3: Check no HTML/XML tags in title
        html_tags = clean_df[clean_df['title'].str.contains(r'<[^>]+>', regex=True, na=False)]
        if len(html_tags) > 0:
            issues.append(f"FAIL: {len(html_tags)} titles contain HTML tags")
        else:
            print("[PASS] No HTML/XML tags in titles")

        # Rule 4: Check no HTML/XML tags in summary
        html_summary = clean_df[clean_df['summary'].str.contains(r'<[^>]+>', regex=True, na=False)]
        if len(html_summary) > 0:
            issues.append(f"FAIL: {len(html_summary)} summaries contain HTML tags")
        else:
            print("[PASS] No HTML/XML tags in summaries")

        # Rule 5: Check authors_joined is string
        if not clean_df['authors_joined'].dtype == 'object':
            issues.append("FAIL: authors_joined is not string type")
        else:
            print("[PASS] authors_joined is properly joined string")

        # Rule 6: Check categories_joined is string
        if not clean_df['categories_joined'].dtype == 'object':
            issues.append("FAIL: categories_joined is not string type")
        else:
            print("[PASS] categories_joined is properly joined string")

        # Rule 7: Check age_days calculated
        age_invalid = clean_df[clean_df['age_days'] < 0]
        if len(age_invalid) > 0:
            # Only warn if published is present but age is -1
            has_published = clean_df[clean_df['published'] != '']
            if len(has_published) > 0:
                print(f"[WARN] {len(age_invalid)} records with age_days = -1 (may have no published date)")
        else:
            print("[PASS] age_days calculated correctly")

        # Rule 8: Check text_for_embedding format
        expected_format = clean_df['text_for_embedding'].str.startswith('Title: ')
        if not expected_format.all():
            issues.append("FAIL: Some text_for_embedding don't start with 'Title: '")
        else:
            print("[PASS] text_for_embedding format correct")

        # Rule 9: Check text_for_embedding contains Authors and Summary
        has_authors = clean_df['text_for_embedding'].str.contains('Authors: ', regex=False)
        has_summary = clean_df['text_for_embedding'].str.contains('Summary: ', regex=False)
        if not has_authors.all():
            issues.append("FAIL: Some text_for_embedding missing 'Authors: '")
        else:
            print("[PASS] text_for_embedding contains Authors section")
        if not has_summary.all():
            issues.append("FAIL: Some text_for_embedding missing 'Summary: '")
        else:
            print("[PASS] text_for_embedding contains Summary section")

        # Rule 10: Check duplicates removed
        duplicates = clean_df[clean_df.duplicated(subset=['paper_id'], keep=False)]
        if len(duplicates) > 0:
            issues.append(f"FAIL: {len(duplicates)} duplicate paper_ids found")
        else:
            print("[PASS] No duplicate paper_ids")

        # Final results
        print("\n" + "=" * 60)
        if issues:
            print("CLEANING VERIFICATION FAILED:")
            for issue in issues:
                print(f"  - {issue}")
            return 1
        else:
            print("ALL CLEANING RULES PASSED!")
            print(f"\nClean data saved to:")
            print(f"  - CSV: {settings.paths.clean_csv}")
            print(f"  - JSON: {settings.paths.clean_json}")
            return 0

    else:
        print("\nWARNING: No records after cleaning!")
        return 1


if __name__ == "__main__":
    sys.exit(main())
