"""Simple test of crossref and cleaning modules"""
import sys
import json
import os
from pathlib import Path

# Set up the Python path correctly
project_root = Path.cwd()
sys.path.insert(0, str(project_root))

# Import the modules
print("Importing modules...")
try:
    from src.core.config import Settings, Paths
    from src.core.utils import ensure_parent, read_json, write_json, compact_join
    from src.ingestion.crossref import PaperRecord, parse_crossref_payload
    from src.ingestion.cleaning import build_clean_dataframe, _strip_html_tags
    print("✓ All imports successful")
except Exception as e:
    print(f"✗ Import failed: {e}")
    sys.exit(1)

# Create settings
print("\nCreating settings...")
paths = Paths(
    project_dir=project_root,
    workspace_dir=project_root.parent,
    raw_api_response=project_root / "data" / "raw" / "crossref_response.json",
    raw_records_json=project_root / "data" / "raw" / "crossref_records.json",
    clean_csv=project_root / "data" / "clean" / "papers_clean.csv",
    clean_json=project_root / "data" / "clean" / "papers_clean.json",
    chroma_dir=project_root / "data" / "chroma",
    embeddings_json=project_root / "data" / "embeddings" / "papers_embeddings.json",
    corrupted_clean_csv=project_root / "data" / "clean" / "papers_clean_corrupted.csv",
    corrupted_clean_json=project_root / "data" / "clean" / "papers_clean_corrupted.json",
    corrupted_embeddings_json=project_root / "data" / "embeddings" / "papers_embeddings_corrupted.json",
    repaired_clean_csv=project_root / "data" / "clean" / "papers_clean_repaired.csv",
    repaired_clean_json=project_root / "data" / "clean" / "papers_clean_repaired.json",
    repaired_embeddings_json=project_root / "data" / "embeddings" / "papers_embeddings_repaired.json",
    eval_testset=project_root / "data" / "eval" / "test_set.json",
    baseline_metrics=project_root / "data" / "results" / "baseline_metrics.json",
    baseline_answers=project_root / "data" / "results" / "baseline_answers.json",
    demo_answers=project_root / "data" / "results" / "agent_demo_answers.json",
    quality_dir=project_root / "data" / "quality",
    gx_dir=project_root / "data" / "quality" / "gx",
    freshness_report=project_root / "data" / "quality" / "freshness_report.json",
    baseline_report=project_root / "data" / "reports" / "phase1_report.md",
    corruption_log=project_root / "data" / "results" / "corruption_log.json",
    corrupted_metrics=project_root / "data" / "results" / "corrupted_metrics.json",
    corrupted_answers=project_root / "data" / "results" / "corrupted_answers.json",
    repaired_metrics=project_root / "data" / "results" / "repaired_metrics.json",
    repaired_answers=project_root / "data" / "results" / "repaired_answers.json",
    comparison_report=project_root / "data" / "reports" / "corruption_report.md",
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

print("✓ Settings created")

# Test parse_crossref_payload
print("\n" + "="*60)
print("TEST 1: Testing parse_crossref_payload function")
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
            }
        ]
    }
}

records = parse_crossref_payload(mock_payload)
print(f"✓ Parsed {len(records)} records from mock data")

for i, rec in enumerate(records):
    print(f"\n  Record {i+1}:")
    print(f"    paper_id: {rec.paper_id}")
    print(f"    title: {rec.title}")
    print(f"    authors: {rec.authors}")
    print(f"    summary: {rec.summary}")
    print(f"    categories: {rec.categories}")
    print(f"    published: {rec.published}")

# Test cleaning
print("\n" + "="*60)
print("TEST 2: Testing build_clean_dataframe function")
print("="*60)

from datetime import UTC, datetime
run_date = datetime.now(UTC)

df = build_clean_dataframe(records, run_date, settings)
print(f"✓ Cleaned DataFrame created with {len(df)} rows")
print(f"✓ Columns: {list(df.columns)}")

if not df.empty:
    print("\n✓ Sample cleaned data (first row):")
    row = df.iloc[0]
    print(f"  paper_id: {row['paper_id']}")
    print(f"  title: {row['title']}")
    print(f"  authors_joined: {row['authors_joined']}")
    print(f"  categories_joined: {row['categories_joined']}")
    print(f"  summary: {row['summary']}")
    print(f"  published: {row['published']}")
    print(f"  age_days: {row['age_days']}")
    print(f"  text_for_embedding: {row['text_for_embedding']}")

# Test file saving
print("\n" + "="*60)
print("TEST 3: Testing file saving functionality")
print("="*60)

# Save raw response
write_json(settings.paths.raw_api_response, mock_payload)
print(f"✓ Raw response saved to: {settings.paths.raw_api_response}")

# Save raw records
records_data = [PaperRecord.__annotations__]
write_json(settings.paths.raw_records_json, records_data)
print(f"✓ Raw records saved to: {settings.paths.raw_records_json}")

# Save cleaned data
if not df.empty:
    from core.utils import write_csv, write_json
    write_csv(df, settings.paths.clean_csv)
    print(f"✓ Cleaned CSV saved to: {settings.paths.clean_csv}")
    
    write_json(df.to_dict(orient="records"), settings.paths.clean_json)
    print(f"✓ Cleaned JSON saved to: {settings.paths.clean_json}")

print("\n" + "="*60)
print("ALL TESTS PASSED SUCCESSFULLY!")
print("="*60)