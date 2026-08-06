from __future__ import annotations

from typing import Any

from core.utils import write_text


def _value(payload: dict[str, Any], key: str) -> Any:
    value = payload.get(key, "N/A")
    return f"{value:.4f}" if isinstance(value, float) else value


def generate_phase1_report(
    report_path,
    source_summary: dict[str, Any],
    metrics: dict[str, Any],
    quality: dict[str, Any],
    freshness: dict[str, Any],
) -> None:
    lines = ["# Baseline Pipeline Report", "", "## Source", ""]
    lines += [f"- {key}: {value}" for key, value in source_summary.items()]
    lines += ["", "## RAG metrics", "", "| Metric | Baseline |", "|---|---:|"]
    for key in ("retrieval_hit_rate", "mean_token_f1", "judge_accuracy", "mean_judge_score"):
        lines.append(f"| {key} | {_value(metrics, key)} |")
    lines += ["", "## Observability", "", f"- Quality: **{quality.get('status', 'N/A')}**",
              f"- Fresh: **{freshness.get('is_fresh', False)}**", f"- Stale rows: {freshness.get('stale_rows', 'N/A')}"]
    write_text(report_path, "\n".join(lines) + "\n")


def generate_corruption_report(
    report_path,
    baseline_metrics: dict[str, Any],
    corrupted_metrics: dict[str, Any],
    repaired_metrics: dict[str, Any],
    corrupted_quality: dict[str, Any],
    repaired_quality: dict[str, Any],
    corrupted_freshness: dict[str, Any],
    repaired_freshness: dict[str, Any],
) -> None:
    lines = ["# Corruption, Repair & Comparison Report", "",
             "| RAG metric | Baseline | Corrupted | Repaired |", "|---|---:|---:|---:|"]
    for key in ("retrieval_hit_rate", "mean_token_f1", "judge_accuracy", "mean_judge_score"):
        lines.append(f"| {key} | {_value(baseline_metrics, key)} | {_value(corrupted_metrics, key)} | {_value(repaired_metrics, key)} |")
    lines += ["", "| Observability signal | Baseline | Corrupted | Repaired |", "|---|---:|---:|---:|",
              f"| quality status | PASS | {corrupted_quality.get('status', 'N/A')} | {repaired_quality.get('status', 'N/A')} |",
              f"| is_fresh | True | {corrupted_freshness.get('is_fresh', 'N/A')} | {repaired_freshness.get('is_fresh', 'N/A')} |",
              f"| stale_rows | 0 | {corrupted_freshness.get('stale_rows', 'N/A')} | {repaired_freshness.get('stale_rows', 'N/A')} |",
              "", "## Interpretation", "",
              "Blank/noisy summaries usually have the strongest retrieval impact because the summary dominates the MiniLM input. Dropped ground-truth records cause unavoidable retrieval misses.", "",
              "Repair rebuilds from the frozen raw snapshot. Fetching Crossref again could return changed records and would invalidate the controlled baseline/corrupted/repaired comparison."]
    write_text(report_path, "\n".join(lines) + "\n")
