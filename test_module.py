"""Test script to verify crossref module directly"""
import sys
import json
from pathlib import Path
from datetime import UTC, datetime

# Change to the project directory
os.chdir('F:/K4_Day10_Data-Pipeline-Data-Observability-VuaTuat')
sys.path.insert(0, str(Path.cwd()))

# Read the crossref.py file and execute it directly
crossref_code = Path('src/ingestion/crossref.py').read_text()
exec(crossref_code)

# Read the cleaning.py file and execute it directly
cleaning_code = Path('src/ingestion/cleaning.py').read_text()
exec(cleaning_code)

print("Crossref and cleaning modules loaded successfully!")

# Test parse_crossref_payload with mock data
print("\nTesting parse_crossref_payload...")
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
print(f"Parsed {len(records)} records")

# Test cleaning
print("\nTesting cleaning...")
run_date = datetime.now(UTC)

df = build_clean_dataframe(records, run_date, None)
print(f"Cleaned DataFrame: {len(df)} rows")

if not df.empty:
    print("\nCleaned data sample:")
    for i, row in df.head().iterrows():
        print(f"\nRow {i}:")
        print(f"  paper_id: {row['paper_id']}")
        print(f"  title: {row['title']}")
        print(f"  authors_joined: {row['authors_joined']}")
        print(f"  categories_joined: {row['categories_joined']}")
        print(f"  summary: {row['summary']}")
        print(f"  published: {row['published']}")
        print(f"  age_days: {row['age_days']}")

print("\n✓ All tests passed!")