"""Helper module to simulate the config loading"""
from pathlib import Path
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Optional
import os

@dataclass(frozen=True)
class Paths:
    project_dir: Path
    workspace_dir: Path
    raw_api_response: Path
    raw_records_json: Path
    clean_csv: Path
    clean_json: Path

@dataclass(frozen=True)
class Settings:
    source_api: str
    source_query: str
    source_filter: str
    max_results: int
    paths: Paths

# Create simple settings function
def get_simple_settings():
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
    )
    
    return Settings(
        source_api="Crossref REST API",
        source_query="agentic retrieval augmented generation large language model",
        source_filter="from-pub-date:2023-01-01,has-abstract:true",
        max_results=30,
        paths=paths
    )