from __future__ import annotations

from datetime import UTC, datetime

from core.config import load_settings
from core.utils import read_json
from evaluation.metrics import evaluate_pipeline
from evaluation.testset import build_test_set
from ingestion.cleaning import build_clean_dataframe
from ingestion.crossref import fetch_source_records, load_raw_records
from observability.quality import build_freshness_report, run_data_quality_checks
from observability.reporting import generate_phase1_report
from retrieval.index import LocalEmbeddingIndex


def main() -> None:
    settings = load_settings()
    if settings.refresh_source or not settings.paths.raw_records_json.exists():
        records = fetch_source_records(settings)
    else:
        records = load_raw_records(settings.paths.raw_records_json)
    df = build_clean_dataframe(records, datetime.now(UTC), settings)
    if df.empty:
        raise RuntimeError("Cleaning produced no records.")
    index = LocalEmbeddingIndex.build(df, settings, settings.paths.embeddings_json)
    if settings.refresh_test_set or not settings.paths.eval_testset.exists():
        build_test_set(df, settings.paths.eval_testset)
    bundle = evaluate_pipeline(settings, index, settings.paths.eval_testset,
                               settings.paths.baseline_metrics, settings.paths.baseline_answers)
    quality = run_data_quality_checks(df, settings, "baseline_quality")
    freshness = build_freshness_report(df, settings, settings.paths.freshness_report)
    generate_phase1_report(settings.paths.baseline_report,
                           {"source": settings.source_api, "raw_records": len(records), "clean_records": len(df)},
                           bundle.summary, quality, freshness)
    print(f"Baseline complete: {len(df)} clean records; report={settings.paths.baseline_report}")
