"""Simple crossref fetcher for testing"""
import sys
import os
import json
from pathlib import Path
from datetime import UTC, datetime

# Add the src directory to the Python path
sys.path.insert(0, str(Path.cwd() / 'src'))

# Now try to import
try:
    from core.config import Settings, load_settings
    print("Successfully imported from core.config")
except ImportError as e:
    print(f"Import error: {e}")
    
    # Let's try a different approach - manually create what we need
    from dataclasses import dataclass
    
    @dataclass(frozen=True)
    class Paths:
        project_dir: Path
        workspace_dir: Path
        raw_api_response: Path
        raw_records_json: Path
        clean_csv: Path
        clean_json: Path
        chroma_dir: Path
        embeddings_json: Path
        corrupted_clean_csv: Path
        corrupted_clean_json: Path
        corrupted_embeddings_json: Path
        repaired_clean_csv: Path
        repaired_clean_json: Path
        repaired_embeddings_json: Path
        eval_testset: Path
        baseline_metrics: Path
        baseline_answers: Path
        demo_answers: Path
        quality_dir: Path
        gx_dir: Path
        freshness_report: Path
        baseline_report: Path
        corruption_log: Path
        corrupted_metrics: Path
        corrupted_answers: Path
        repaired_metrics: Path
        repaired_answers: Path
        comparison_report: Path

    @dataclass(frozen=True)
    class Settings:
        llm_provider: str
        model_name: str
        google_api_key: str | None
        openai_api_key: str | None
        anthropic_api_key: str | None
        openrouter_api_key: str | None
        openrouter_base_url: str
        ollama_base_url: str
        custom_llm_api_key: str | None
        custom_llm_base_url: str | None
        embedding_model: str
        baseline_collection_name: str
        corrupted_collection_name: str
        repaired_collection_name: str
        source_api: str
        source_query: str
        source_filter: str
        max_results: int
        top_k: int
        freshness_threshold_days: int
        refresh_source: bool
        refresh_test_set: bool
        paths: Paths

    # Create settings
    root = Path.cwd()
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
        source_query="machine learning",
        source_filter="has-abstract:true",
        max_results=20,
        top_k=4,
        freshness_threshold_days=180,
        refresh_source=False,
        refresh_test_set=False,
        paths=paths
    )
    
    print("Manually created settings")
    print(f"  source_query: {settings.source_query}")
    print(f"  max_results: {settings.max_results}")