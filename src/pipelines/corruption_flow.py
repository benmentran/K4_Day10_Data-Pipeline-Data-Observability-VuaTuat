from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd

from core.config import Settings, load_settings
from core.utils import normalize_whitespace, read_json, write_csv, write_json
from evaluation.metrics import evaluate_pipeline
from ingestion.cleaning import build_clean_dataframe
from ingestion.corruption import corrupt_clean_dataframe
from ingestion.crossref import load_raw_records
from observability.quality import build_freshness_report, run_data_quality_checks
from observability.reporting import generate_corruption_report
from retrieval.index import LocalEmbeddingIndex


METRIC_KEYS = ("retrieval_hit_rate", "mean_token_f1", "judge_accuracy", "mean_judge_score")


def _read_optional_json(path: Path) -> Any | None:
    return read_json(path) if path.exists() else None


def _read_clean_csv(path: Path) -> pd.DataFrame:
    # keep_default_na=False: a blanked summary must stay "" and not become NaN,
    # which would crash the Chroma metadata write and hide the corruption.
    return pd.read_csv(path, keep_default_na=False)


CONTENT_COLUMNS = ("title", "summary", "published", "authors_joined", "categories_joined", "text_for_embedding")


def _content_fingerprint(df: pd.DataFrame) -> dict[str, tuple[str, ...]]:
    """Per-document content, whitespace-normalised.

    The baseline CSV and a freshly repaired frame can differ purely in line
    endings (CRLF vs LF inside the multi-line text_for_embedding field), which is
    invisible to MiniLM but would show up as a false mismatch on a raw compare.
    """
    return {
        str(row["paper_id"]): tuple(normalize_whitespace(str(row[column])) for column in CONTENT_COLUMNS)
        for _, row in df.iterrows()
    }


def _verify_repair(baseline: pd.DataFrame, repaired: pd.DataFrame, settings: Settings) -> dict[str, Any]:
    """Confirm the repair restored the baseline corpus, not merely some corpus."""
    baseline_ids = set(baseline["paper_id"].astype(str))
    repaired_ids = set(repaired["paper_id"].astype(str))
    baseline_content = _content_fingerprint(baseline)
    repaired_content = _content_fingerprint(repaired)
    changed = sorted(
        paper_id for paper_id in baseline_ids & repaired_ids
        if baseline_content[paper_id] != repaired_content[paper_id]
    )
    return {
        "source": settings.paths.raw_records_json.relative_to(settings.paths.project_dir).as_posix(),
        "baseline_rows": int(len(baseline)),
        "repaired_rows": int(len(repaired)),
        "paper_ids_match": baseline_ids == repaired_ids,
        "missing_after_repair": sorted(baseline_ids - repaired_ids),
        "unexpected_after_repair": sorted(repaired_ids - baseline_ids),
        "content_columns_compared": list(CONTENT_COLUMNS),
        "content_matches": not changed,
        "documents_with_changed_content": changed,
    }


def build_comparison_report(settings: Settings) -> None:
    """Render data/reports/corruption_report.md from the persisted artifacts.

    Everything the report needs is already on disk after ``main`` has run, so the
    markdown can be regenerated without paying for another evaluation pass.
    """
    paths = settings.paths
    states = {
        "baseline": (paths.clean_csv, paths.baseline_metrics, settings.baseline_collection_name),
        "corrupted": (paths.corrupted_clean_csv, paths.corrupted_metrics, settings.corrupted_collection_name),
        "repaired": (paths.repaired_clean_csv, paths.repaired_metrics, settings.repaired_collection_name),
    }
    missing = [str(path) for csv_path, metrics_path, _ in states.values()
               for path in (csv_path, metrics_path) if not path.exists()]
    if missing:
        raise FileNotFoundError("Cannot build the comparison report; missing artifacts: " + ", ".join(missing))

    frames = {name: _read_clean_csv(csv_path) for name, (csv_path, _, _) in states.items()}
    dataset_summary = [
        {
            "state": name.capitalize(),
            "dataset": csv_path.relative_to(paths.project_dir).as_posix(),
            "rows": len(frames[name]),
            "collection": collection,
        }
        for name, (csv_path, _, collection) in states.items()
    ]

    generate_corruption_report(
        paths.comparison_report,
        read_json(paths.baseline_metrics),
        read_json(paths.corrupted_metrics),
        read_json(paths.repaired_metrics),
        read_json(paths.quality_dir / "corrupted_quality.json"),
        read_json(paths.quality_dir / "repaired_quality.json"),
        read_json(paths.quality_dir / "corrupted_freshness.json"),
        read_json(paths.quality_dir / "repaired_freshness.json"),
        baseline_quality=_read_optional_json(paths.quality_dir / "baseline_quality.json"),
        baseline_freshness=_read_optional_json(paths.freshness_report),
        corruption_log=_read_optional_json(paths.corruption_log),
        baseline_answers=_read_optional_json(paths.baseline_answers),
        corrupted_answers=_read_optional_json(paths.corrupted_answers),
        repaired_answers=_read_optional_json(paths.repaired_answers),
        dataset_summary=dataset_summary,
        repair_verification=_verify_repair(frames["baseline"], frames["repaired"], settings),
    )
    _print_comparison(
        read_json(paths.baseline_metrics),
        read_json(paths.corrupted_metrics),
        read_json(paths.repaired_metrics),
    )
    print(f"Comparison report written: {paths.comparison_report}")


def _print_comparison(baseline: dict[str, Any], corrupted: dict[str, Any], repaired: dict[str, Any]) -> None:
    print(f"{'metric':<20}{'baseline':>10}{'corrupted':>12}{'repaired':>11}")
    for key in METRIC_KEYS:
        values = [state.get(key) for state in (baseline, corrupted, repaired)]
        formatted = "".join(
            f"{value:>{width}.4f}" if isinstance(value, (int, float)) else f"{'N/A':>{width}}"
            for value, width in zip(values, (10, 12, 11), strict=True)
        )
        print(f"{key:<20}{formatted}")


def main(report_only: bool = False) -> None:
    settings = load_settings()
    if report_only:
        build_comparison_report(settings)
        return

    required = [settings.paths.clean_csv, settings.paths.baseline_metrics,
                settings.paths.eval_testset, settings.paths.raw_records_json]
    missing = [str(path) for path in required if not path.exists()]
    if missing:
        raise FileNotFoundError("Run phase 1 first; missing artifacts: " + ", ".join(missing))

    baseline = _read_clean_csv(settings.paths.clean_csv)

    # --- Phase 2a: controlled corruption --------------------------------
    # The frozen test set is handed to the corrupter so every scenario is
    # guaranteed to hit a document the evaluation actually asks about; a
    # corruption of documents nobody queries would move no metric at all.
    corrupted = corrupt_clean_dataframe(
        baseline,
        settings.paths.corruption_log,
        test_set_path=settings.paths.eval_testset,
    )
    write_csv(corrupted, settings.paths.corrupted_clean_csv)
    write_json(settings.paths.corrupted_clean_json, corrupted.to_dict(orient="records"))

    overlap = read_json(settings.paths.corruption_log)["frozen_test_set"]["overlap_count"]
    if not overlap:
        raise RuntimeError(
            "Corruption touched no document in the frozen test set, so no metric can move. "
            "Inspect data/results/corruption_log.json."
        )
    print(f"Corrupted {len(baseline)} -> {len(corrupted)} rows; {overlap} frozen-test-set documents affected.")

    corrupted_index = LocalEmbeddingIndex.build(corrupted, settings, settings.paths.corrupted_embeddings_json)
    evaluate_pipeline(settings, corrupted_index, settings.paths.eval_testset,
                      settings.paths.corrupted_metrics, settings.paths.corrupted_answers)
    run_data_quality_checks(corrupted, settings, "corrupted_quality")
    build_freshness_report(corrupted, settings, settings.paths.quality_dir / "corrupted_freshness.json")

    # --- Phase 2b: repair from the frozen raw snapshot ------------------
    # Repair never reads papers_corrupted.csv: it replays the C2 raw records
    # through the standard cleaning logic, which is what makes the recovery
    # provable rather than a hand-patched CSV.
    raw_records = load_raw_records(settings.paths.raw_records_json)
    repaired = build_clean_dataframe(raw_records, datetime.now(UTC))
    if repaired.empty:
        raise RuntimeError("Repair produced no records; the raw snapshot is unusable.")
    write_csv(repaired, settings.paths.repaired_clean_csv)
    write_json(settings.paths.repaired_clean_json, repaired.to_dict(orient="records"))

    repaired_index = LocalEmbeddingIndex.build(repaired, settings, settings.paths.repaired_embeddings_json)
    evaluate_pipeline(settings, repaired_index, settings.paths.eval_testset,
                      settings.paths.repaired_metrics, settings.paths.repaired_answers)
    run_data_quality_checks(repaired, settings, "repaired_quality")
    build_freshness_report(repaired, settings, settings.paths.quality_dir / "repaired_freshness.json")

    # --- Phase 2c: three-state comparison -------------------------------
    build_comparison_report(settings)
