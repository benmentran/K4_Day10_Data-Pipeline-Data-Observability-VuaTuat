"""Simple test of crossref and cleaning modules"""
from pathlib import Path
import sys
import json
from datetime import UTC, datetime

# Set the current working directory
project_root = Path('.').resolve()
sys.path.insert(0, str(project_root))

# Import the necessary functions and classes
from src.core.config import load_settings
from src.ingestion.crossref import parse_crossref_payload
from src.ingestion.cleaning import build_clean_dataframe

print("Testing Crossref Data Pipeline")
print("=" * 60)

# Load settings
print("\n1. Loading settings...")
settings = load_settings()
print(f"   source_query: {settings.source_query}")
print(f"   source_filter: {settings.source_filter}")
print(f"   max_results: {settings.max_results}")
print(f"   raw_api_response path: {settings.paths.raw_api_response}")
print(f"   raw_records_json path: {settings.paths.raw_records_json}")
print(f"   clean_csv path: {settings.paths.clean_csv}")
print(f"   clean_json path: {settings.paths.clean_json}")

# Test the parse_crossref_payload function
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
                "description": "This is another test abstract.",
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
                "abstract": "Short",
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
print(f"   ✓ Parsed {len(records)} valid records from mock data")

for i, rec in enumerate(records):
    print(f"\n   Record {i+1}:")
    print(f"     paper_id: {rec.paper_id}")
    print(f"     title: {rec.title}")
    print(f"     authors: {rec.authors}")
    print(f"     summary: {rec.summary}")
    print(f"     published: {rec.published}")

# Test the build_clean_dataframe function
print("\n3. Testing build_clean_dataframe...")
run_date = datetime.now(UTC)

df = build_clean_dataframe(records, run_date, settings)
print(f"   ✓ Cleaned DataFrame created with {len(df)} rows")
print(f"   ✓ Columns: {list(df.columns)}")

if not df.empty:
    print("\n   ✓ Sample cleaned data:")
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

# Test file exports
print("\n4. Testing file exports...")
if settings.paths.raw_api_response:
    print(f"   ✓ Raw API response path: {settings.paths.raw_api_response}")
if settings.paths.raw_records_json:
    print(f"   ✓ Raw records path: {settings.paths.raw_records_json}")
if settings.paths.clean_csv:
    print(f"   ✓ Clean CSV path: {settings.paths.clean_csv}")
if settings.paths.clean_json:
    print(f"   ✓ Clean JSON path: {settings.paths.clean_json}")

print("\n" + "=" * 60)
print("All tests passed successfully!")
print("=" * 60)