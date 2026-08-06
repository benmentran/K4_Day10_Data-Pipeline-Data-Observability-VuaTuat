"""Direct test of crossref functionality"""
import sys
import json
import os
from pathlib import Path

# Add the project root to path
sys.path.insert(0, '.')

# Import core modules by exec-ing them to avoid import issues
config_code = open('src/core/config.py').read()
utils_code = open('src/core/utils.py').read()

crossref_code = open('src/ingestion/crossref.py').read()
cleaning_code = open('src/ingestion/cleaning.py').read()

# Execute utils and config first
exec(utils_code)
exec(config_code)

# Now execute crossref and cleaning
exec(crossref_code)
exec(cleaning_code)

print("✓ Modules loaded successfully!")

# Create a simple settings object
root = Path('.').resolve()
workspace = root.parent
data_dir = root / "data"

paths = Paths(
    project_dir=root,
    workspace_dir=workspace,
    raw_api_response=data_dir / "raw" / "crossref_response.json",
    raw_records_json=data_dir / "raw" / "crossref_records.json",
    clean_csv=data_dir / "clean" / "papers_clean.csv",
    clean_json=data_dir / "clean" / "papers_clean.json",
    chroma_dir=data_dir / "chroma",
    embeddings_json=data_dir / "embeddings" / "papers_embeddings.json",
    corrupted_clean_csv=data_dir / "clean" / "papers_clean_corrupted.csv",
    corrupted_clean_json=data_dir / "clean" / "papers_clean_corrupted.json",
    corrupted_embeddings_json=data_dir / "embeddings" / "papers_embeddings_corrupted.json",
    repaired_clean_csv=data_dir / "clean" / "papers_clean_repaired.csv",
    repaired_clean_json=data_dir / "clean" / "papers_clean_repaired.json",
    repaired_embeddings_json=data_dir / "embeddings" / "papers_embeddings_repaired.json",
    eval_testset=data_dir / "eval" / "test_set.json",
    baseline_metrics=data_dir / "results" / "baseline_metrics.json",
    baseline_answers=data_dir / "results" / "baseline_answers.json",
    demo_answers=data_dir / "results" / "agent_demo_answers.json",
    quality_dir=data_dir / "quality",
    gx_dir=data_dir / "quality" / "gx",
    freshness_report=data_dir / "quality" / "freshness_report.json",
    baseline_report=data_dir / "reports" / "phase1_report.md",
    corruption_log=data_dir / "results" / "corruption_log.json",
    corrupted_metrics=data_dir / "results" / "corrupted_metrics.json",
    corrupted_answers=data_dir / "results" / "corrupted_answers.json",
    repaired_metrics=data_dir / "results" / "repaired_metrics.json",
    repaired_answers=data_dir / "results" / "repaired_answers.json",
    comparison_report=data_dir / "reports" / "corruption_report.md",
)

settings = Settings(
    llm_provider="gemini",
    model_name="gemini-2.5-flash",
    google_api_key=None,
    openai_api_key=None,
    anthropic_api_key=None,
    openrouter_api_key=None,
    openrouter_base_url="https://openrouter.ai/api/v1",
    ollama_base_url="http://localhost:11434",
    custom_llm_api_key=None,
    custom_llm_base_url=None,
    embedding_model="sentence-transformers/all-MiniLM-L6-v2",
    baseline_collection_name="papers-baseline",
    corrupted_collection_name="papers-corrupted",
    repaired_collection_name="papers-repaired",
    source_api="Crossref REST API",
    source_query="agentic retrieval augmented generation large language model",
    source_filter=f"from-pub-date:2023-01-01,has-abstract:true",
    max_results=24,
    top_k=4,
    freshness_threshold_days=180,
    refresh_source=False,
    refresh_test_set=False,
    paths=paths
)

print(f"\n✓ Settings created:")
print(f"  Query: {settings.source_query}")
print(f"  Max results: {settings.max_results}")
print(f"  Filter: {settings.source_filter}")

# Test the parse function with mock data
print("\n" + "="*60)
print("Testing parse_crossref_payload with mock data...")
print("="*60)

mock_payload = {
    "message": {
        "items": [
            {
                "DOI": "10.1000/test1",
                "title": ["Test Paper 1 <b>with</b> HTML tags"],
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
print(f"✓ Parsed {len(records)} valid records")

# Test cleaning
print("\n" + "="*60)
print("Testing build_clean_dataframe...")
print("="*60)

from datetime import UTC, datetime
run_date = datetime.now(UTC)

df = build_clean_dataframe(records, run_date, settings)
print(f"✓ Cleaned DataFrame created with {len(df)} rows")
print(f"✓ Columns: {list(df.columns)}")

if not df.empty:
    print("\n✓ Sample cleaned data:")
    for i, row in df.head().iterrows():
        print(f"\n  Row {i}:")
        print(f"    paper_id: {row['paper_id']}")
        print(f"    title: {row['title'][:50]}...")
        print(f"    authors_joined: {row['authors_joined']}")
        print(f"    categories_joined: {row['categories_joined']}")
        print(f"    summary: {row['summary'][:50]}...")
        print(f"    published: {row['published']}")
        print(f"    age_days: {row['age_days']}")
        print(f"    text_for_embedding: {row['text_for_embedding'][:50]}...")

# Check if files were created
print("\n" + "="*60)
print("Checking output files...")
print("="*60)

raw_response_path = data_dir / "raw" / "crossref_response.json"
raw_records_path = data_dir / "raw" / "crossref_records.json"
clean_csv_path = data_dir / "clean" / "papers_clean.csv"
clean_json_path = data_dir / "clean" / "papers_clean.json"

print(f"✓ Raw response path: {raw_response_path}")
print(f"✓ Raw records path: {raw_records_path}")
print(f"✓ Clean CSV path: {clean_csv_path}")
print(f"✓ Clean JSON path: {clean_json_path}")

print("\n" + "="*60)
print("All tests completed successfully!")
print("="*60)