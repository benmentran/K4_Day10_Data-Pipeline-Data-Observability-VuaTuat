from __future__ import annotations

from datetime import UTC, datetime

import pandas as pd

from core.config import load_settings
from core.utils import read_json, write_csv, write_json
from evaluation.metrics import evaluate_pipeline
from ingestion.cleaning import build_clean_dataframe
from ingestion.corruption import corrupt_clean_dataframe
from ingestion.crossref import load_raw_records
from observability.quality import build_freshness_report, run_data_quality_checks
from observability.reporting import generate_corruption_report
from retrieval.index import LocalEmbeddingIndex


def main() -> None:
    settings = load_settings()
    required = [settings.paths.clean_csv, settings.paths.baseline_metrics,
                settings.paths.eval_testset, settings.paths.raw_records_json]
    missing = [str(path) for path in required if not path.exists()]
    if missing:
        raise FileNotFoundError("Run phase 1 first; missing artifacts: " + ", ".join(missing))

    baseline_metrics = read_json(settings.paths.baseline_metrics)
    baseline = pd.read_csv(settings.paths.clean_csv, keep_default_na=False)
    corrupted = corrupt_clean_dataframe(baseline, settings.paths.corruption_log)
    write_csv(corrupted, settings.paths.corrupted_clean_csv)
    write_json(settings.paths.corrupted_clean_json, corrupted.to_dict(orient="records"))
    corrupted_index = LocalEmbeddingIndex.build(corrupted, settings, settings.paths.corrupted_embeddings_json)
    corrupted_bundle = evaluate_pipeline(settings, corrupted_index, settings.paths.eval_testset,
                                         settings.paths.corrupted_metrics, settings.paths.corrupted_answers)
    corrupted_quality = run_data_quality_checks(corrupted, settings, "corrupted_quality")
    corrupted_freshness = build_freshness_report(
        corrupted, settings, settings.paths.quality_dir / "corrupted_freshness.json")

    # Controlled repair: rebuild from the exact raw snapshot used by baseline.
    raw_records = load_raw_records(settings.paths.raw_records_json)
    repaired = build_clean_dataframe(raw_records, datetime.now(UTC))
    write_csv(repaired, settings.paths.repaired_clean_csv)
    write_json(settings.paths.repaired_clean_json, repaired.to_dict(orient="records"))
    repaired_index = LocalEmbeddingIndex.build(repaired, settings, settings.paths.repaired_embeddings_json)
    repaired_bundle = evaluate_pipeline(settings, repaired_index, settings.paths.eval_testset,
                                        settings.paths.repaired_metrics, settings.paths.repaired_answers)
    repaired_quality = run_data_quality_checks(repaired, settings, "repaired_quality")
    repaired_freshness = build_freshness_report(
        repaired, settings, settings.paths.quality_dir / "repaired_freshness.json")

    generate_corruption_report(settings.paths.comparison_report, baseline_metrics,
                               corrupted_bundle.summary, repaired_bundle.summary,
                               corrupted_quality, repaired_quality,
                               corrupted_freshness, repaired_freshness)
    print(f"Corruption flow complete: report={settings.paths.comparison_report}")
