from __future__ import annotations

from datetime import UTC, datetime

import pandas as pd

from core.config import Settings, load_settings
from core.utils import read_json
from evaluation.metrics import evaluate_pipeline
from evaluation.testset import build_test_set
from ingestion.cleaning import build_clean_dataframe
from ingestion.crossref import fetch_source_records, load_raw_records
from observability.quality import build_freshness_report, run_data_quality_checks
from observability.reporting import generate_phase1_report
from retrieval.index import LocalEmbeddingIndex


def build_baseline_report(settings: Settings) -> None:
    """Render data/reports/phase1_report.md from the persisted baseline artifacts.

    Every input is already on disk after ``main`` has run, so the markdown can be
    regenerated without re-fetching Crossref or paying for another judge pass.
    """
    paths = settings.paths
    required = [paths.clean_csv, paths.raw_records_json, paths.baseline_metrics,
                paths.quality_dir / "baseline_quality.json", paths.freshness_report]
    missing = [str(path) for path in required if not path.exists()]
    if missing:
        raise FileNotFoundError("Cannot build the baseline report; missing artifacts: " + ", ".join(missing))

    clean_records = len(pd.read_csv(paths.clean_csv, keep_default_na=False))
    generate_phase1_report(
        paths.baseline_report,
        {"source": settings.source_api,
         "raw_records": len(load_raw_records(paths.raw_records_json)),
         "clean_records": clean_records},
        read_json(paths.baseline_metrics),
        read_json(paths.quality_dir / "baseline_quality.json"),
        read_json(paths.freshness_report),
    )
    print(f"Baseline report written: {paths.baseline_report}")


def main(report_only: bool = False) -> None:
    settings = load_settings()
    if report_only:
        build_baseline_report(settings)
        return

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
