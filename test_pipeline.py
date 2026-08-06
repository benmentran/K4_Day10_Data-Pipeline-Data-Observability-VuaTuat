"""Comprehensive test to verify the entire pipeline"""
import sys
import os
import json
import tempfile
from pathlib import Path
from datetime import UTC, datetime

# Add the current directory to the Python path
sys.path.insert(0, str(Path.cwd()))

# Now import modules
from src.core.config import load_settings
from src.ingestion.crossref import fetch_source_records, parse_crossref_payload
from src.ingestion.cleaning import build_clean_dataframe

print("=" * 60)
print("Testing Crossref Data Pipeline")
print("=" * 60)

# Load settings
print("\n1. Loading settings...")
settings = load_settings()
print(f"   source_query: {settings.source_query}")
print(f"   source_filter: {settings.source_filter}")
print(f"   max_results: {settings.max_results}")

# Create a mock response for testing
print("\n2. Testing parse_crossref_payload with mock data...")
mock_payload = {
    "message": {
        "items": [
            {
                "DOI": "10.1000/test1",
                "title": ["Test Paper 1 <b>with</b> tags"],
                "abstract": "This is a <jats:p>test abstract</jats:p> with <b>HTML</b> tags.",
                "author": [
                    {"given": "John", "family": "Doe"},
                    {"given": "Jane", "family": "Smith"}
                ],
                "subject": ["Machine Learning", "AI"],
                "published-print": {"date-parts": [[2023, 5, 15]]},
                "updated": {"date-parts": [[2023, 5, 16]]},
                "URL": "https://example.com/paper1",
                "link": [
                    {"content-type": "application/pdf", "URL": "https://example.com/paper1.pdf"}
                ],
                "comment": "Test comment 1"
            },
            {
                "DOI": "10.1000/test2",
                "title": ["Test Paper 2"],
                "description": "This is another test abstract without title.",
                "author": [
                    {"given": "Alice", "family": "Johnson"}
                ],
                "subject": ["Data Science"],
                "published-online": {"date-parts": [[2023, 6, 20]]},
                "created": {"date-parts": [[2023, 6, 21]]},
                "URL": "https://example.com/paper2",
                "link": [],
                "comment": "Test comment 2"
            },
            {
                "DOI": "10.1000/test3",
                "title": [],  # This will be filtered out
                "abstract": "Short abstract",
                "author": [
                    {"given": "Bob", "family": "Brown"}
                ],
                "subject": ["ML"],
                "published-print": {"date-parts": [[2023, 7, 10]]},
                "URL": "https://example.com/paper3",
                "link": [],
                "comment": "Test comment 3"
            }
        ]
    }
}

records = parse_crossref_payload(mock_payload)
print(f"   Parsed {len(records)} records from mock data")
for i, rec in enumerate(records):
    print(f"   Record {i+1}: {rec.paper_id}")
    print(f"     Title: {rec.title}")
    print(f"     Authors: {rec.authors}")
    print(f"     Published: {rec.published}")

print("\n3. Testing cleaning pipeline...")
run_date = datetime.now(UTC)
df = build_clean_dataframe(records, run_date, settings)
print(f"   Cleaned DataFrame: {len(df)} rows")
print(f"   Columns: {list(df.columns)}")

if not df.empty:
    print("\n4. Sample cleaned data:")
    for i, row in df.head().iterrows():
        print(f"\n   Row {i}:")
        print(f"     paper_id: {row['paper_id']}")
        print(f"     title: {row['title']}")
        print(f"     authors_joined: {row['authors_joined']}")
        print(f"     categories_joined: {row['categories_joined']}")
        print(f"     summary: {row['summary']}")
        print(f"     published: {row['published']}")
        print(f"     age_days: {row['age_days']}")
        print(f"     text_for_embedding: {row['text_for_embedding']}")

print("\n5. Testing file exports...")
if Path(settings.paths.raw_api_response).exists():
    print(f"   Raw API response saved to: {settings.paths.raw_api_response}")
    
if Path(settings.paths.raw_records_json).exists():
    print(f"   Raw records saved to: {settings.paths.raw_records_json}")
    
if Path(settings.paths.clean_csv).exists():
    print(f"   Cleaned CSV saved to: {settings.paths.clean_csv}")
    
if Path(settings.paths.clean_json).exists():
    print(f"   Cleaned JSON saved to: {settings.paths.clean_json}")

print("\n" + "=" * 60)
print("Pipeline test completed!")
print("=" * 60)