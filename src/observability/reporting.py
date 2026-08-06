from __future__ import annotations

from typing import Any

from core.utils import now_utc, write_text


METRIC_KEYS = ("retrieval_hit_rate", "mean_token_f1", "judge_accuracy", "mean_judge_score")


def _value(payload: dict[str, Any], key: str) -> Any:
    value = payload.get(key, "N/A")
    return f"{value:.4f}" if isinstance(value, float) else value


def _delta(payload: dict[str, Any], baseline: dict[str, Any], key: str) -> str:
    value, reference = payload.get(key), baseline.get(key)
    if not isinstance(value, (int, float)) or not isinstance(reference, (int, float)):
        return "N/A"
    difference = float(value) - float(reference)
    return f"{difference:+.4f}"


def _quality_status(payload: dict[str, Any] | None) -> str:
    if not payload:
        return "N/A"
    return "PASS" if payload.get("success") else "FAIL"


def _failed_checks(payload: dict[str, Any] | None) -> str:
    if not payload:
        return "N/A"
    failed = payload.get("failed_checks") or []
    return ", ".join(failed) if failed else "none"


def _answers_by_id(answers: list[dict[str, Any]] | None) -> dict[str, dict[str, Any]]:
    return {str(item.get("id", "")): item for item in (answers or [])}


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
    for key in METRIC_KEYS:
        lines.append(f"| {key} | {_value(metrics, key)} |")
    lines += ["", "## Observability", "",
              f"- Quality: **{_quality_status(quality)}** "
              f"({quality.get('passed_checks', 'N/A')}/{quality.get('total_checks', 'N/A')} checks, "
              f"failed: {_failed_checks(quality)})",
              f"- Fresh: **{freshness.get('is_fresh', False)}** "
              f"(threshold {freshness.get('threshold_days', 'N/A')} days, "
              f"oldest {freshness.get('oldest_published', 'N/A')})",
              f"- Stale rows: {freshness.get('stale_rows', 'N/A')}",
              "", "### Data quality checks", "",
              "| Check | Severity | Result | Observed | Expected |", "|---|---|---|---:|---:|"]
    for check in quality.get("checks", []):
        lines.append(
            f"| {check.get('name')} | {check.get('severity')} | "
            f"{'PASS' if check.get('success') else 'FAIL'} | "
            f"{check.get('observed')} | {check.get('expected')} |"
        )
    write_text(report_path, "\n".join(lines) + "\n")


def _headline_lines(
    baseline: dict[str, Any], corrupted: dict[str, Any], repaired: dict[str, Any]
) -> list[str]:
    """Summarise, from the numbers themselves, what corruption cost and what repair bought back."""
    tolerance = 1e-9
    lines = ["## 2. Headline", ""]
    hit_rate_held = False

    for key in METRIC_KEYS:
        values = [state.get(key) for state in (baseline, corrupted, repaired)]
        if not all(isinstance(value, (int, float)) for value in values):
            continue
        base, bad, fixed = (float(value) for value in values)
        loss = bad - base

        if loss < -tolerance:
            percent = f" ({loss / base:+.1%})" if abs(base) > tolerance else ""
            verdict = f"**degraded** {base:.4f} -> {bad:.4f}{percent}"
        elif abs(loss) <= tolerance:
            verdict = f"**did not move** ({base:.4f} in the corrupted state)"
            hit_rate_held = hit_rate_held or key == "retrieval_hit_rate"
        else:
            verdict = f"**improved** {base:.4f} -> {bad:.4f}"

        if abs(fixed - base) <= tolerance:
            recovery = f"**fully recovered** to {fixed:.4f} after repair"
        elif fixed > bad + tolerance:
            recovery = f"partially recovered to {fixed:.4f} ({fixed - base:+.4f} vs baseline)"
        else:
            recovery = f"did **not** recover ({fixed:.4f} after repair)"
        lines.append(f"- `{key}`: {verdict}; {recovery}.")

    if hit_rate_held:
        lines += [
            "",
            "`retrieval_hit_rate` is a coarse signal on a corpus this small: every question quotes its own "
            "document's title, so top_k=4 out of ~24 documents still surfaces the right paper even after its "
            "summary is destroyed - and a shorter embedding text can even *raise* title similarity (q7 flips "
            "from MISS to hit once its summary is blanked). The damage is therefore visible in the "
            "answer-level metrics rather than in the hit rate; the deleted record (q1) is the one case where "
            "retrieval provably cannot recover.",
        ]
    lines.append("")
    return lines


def _corruption_scenario_section(corruption_log: dict[str, Any] | None) -> list[str]:
    if not corruption_log:
        return []

    scenarios = corruption_log.get("scenarios", {})
    frozen = corruption_log.get("frozen_test_set", {})
    lines = ["## 1. What was corrupted", "",
             "| Scenario | Docs hit | Frozen test-set questions hit | Effect |", "|---|---:|---|---|"]
    for name, payload in scenarios.items():
        if not payload.get("count"):
            continue
        questions = ", ".join(payload.get("frozen_test_set_question_ids") or []) or "-"
        lines.append(f"| `{name}` | {payload['count']} | {questions} | {payload.get('description', '')} |")

    overlap = frozen.get("overlap_count", 0)
    total_ground_truth = len(frozen.get("ground_truth_paper_ids") or [])
    uncovered = frozen.get("scenarios_without_test_set_overlap") or []
    lines += [
        "",
        f"- Rows: {corruption_log.get('input_rows')} -> {corruption_log.get('output_rows')} "
        f"({corruption_log.get('rows_dropped')} deleted, {corruption_log.get('duplicate_rows_added')} duplicated).",
        f"- Documents corrupted: {corruption_log.get('documents_corrupted')}.",
        f"- **Overlap with the frozen test set: {overlap}/{total_ground_truth} ground-truth documents** "
        f"(ratio {frozen.get('overlap_ratio', 0)}). Scenarios with no test-set overlap: "
        f"{', '.join(uncovered) if uncovered else 'none'}.",
        f"- Seed `{corruption_log.get('seed')}`; full per-document audit trail in `data/results/corruption_log.json`.",
        "",
    ]
    return lines


def _per_question_section(
    corruption_log: dict[str, Any] | None,
    baseline_answers: list[dict[str, Any]] | None,
    corrupted_answers: list[dict[str, Any]] | None,
    repaired_answers: list[dict[str, Any]] | None,
) -> list[str]:
    baseline_by_id = _answers_by_id(baseline_answers)
    corrupted_by_id = _answers_by_id(corrupted_answers)
    repaired_by_id = _answers_by_id(repaired_answers)
    if not baseline_by_id or not corrupted_by_id:
        return []

    scenario_by_question = {
        str(item.get("question_id")): str(item.get("scenario"))
        for item in ((corruption_log or {}).get("frozen_test_set", {}).get("questions_affected") or [])
    }

    def hit(payload: dict[str, Any] | None) -> str:
        if payload is None:
            return "n/a"
        return "hit" if payload.get("retrieval_hit") else "MISS"

    def f1(payload: dict[str, Any] | None) -> str:
        if payload is None:
            return "n/a"
        return f"{float(payload.get('token_f1', 0.0)):.2f}"

    lines = ["## 5. Per-question impact", "",
             "Retrieval hit and token F1 for every question of the frozen test set.", "",
             "| Q | Scenario applied to its ground-truth doc | Retrieval B/C/R | token F1 B/C/R |",
             "|---|---|---|---|"]
    for question_id, baseline_item in baseline_by_id.items():
        corrupted_item = corrupted_by_id.get(question_id)
        repaired_item = repaired_by_id.get(question_id)
        scenario = scenario_by_question.get(question_id, "-")
        lines.append(
            f"| {question_id} | `{scenario}` | "
            f"{hit(baseline_item)} / {hit(corrupted_item)} / {hit(repaired_item)} | "
            f"{f1(baseline_item)} / {f1(corrupted_item)} / {f1(repaired_item)} |"
        )
    lines.append("")
    return lines


def generate_corruption_report(
    report_path,
    baseline_metrics: dict[str, Any],
    corrupted_metrics: dict[str, Any],
    repaired_metrics: dict[str, Any],
    corrupted_quality: dict[str, Any],
    repaired_quality: dict[str, Any],
    corrupted_freshness: dict[str, Any],
    repaired_freshness: dict[str, Any],
    *,
    baseline_quality: dict[str, Any] | None = None,
    baseline_freshness: dict[str, Any] | None = None,
    corruption_log: dict[str, Any] | None = None,
    baseline_answers: list[dict[str, Any]] | None = None,
    corrupted_answers: list[dict[str, Any]] | None = None,
    repaired_answers: list[dict[str, Any]] | None = None,
    dataset_summary: list[dict[str, Any]] | None = None,
    repair_verification: dict[str, Any] | None = None,
) -> None:
    """Render the three-state (baseline / corrupted / repaired) comparison report."""
    lines = [
        "# Corruption, Repair & Comparison Report",
        "",
        f"Generated: {now_utc().isoformat()}",
        "",
        "Three states of the same corpus, evaluated with the **same frozen test set** and the same "
        "retrieval/judge configuration. Only the data changes between states, so every metric "
        "difference below is attributable to data quality.",
        "",
    ]

    if dataset_summary:
        lines += ["| State | Dataset | Rows | Chroma collection |", "|---|---|---:|---|"]
        for row in dataset_summary:
            lines.append(
                f"| {row.get('state')} | `{row.get('dataset')}` | {row.get('rows')} | `{row.get('collection')}` |"
            )
        lines.append("")

    lines += _corruption_scenario_section(corruption_log)
    lines += _headline_lines(baseline_metrics, corrupted_metrics, repaired_metrics)

    lines += ["## 3. RAG metrics on the frozen test set", "",
              "| Metric | Baseline | Corrupted | Repaired | Corrupted - Baseline | Repaired - Baseline |",
              "|---|---:|---:|---:|---:|---:|"]
    for key in METRIC_KEYS:
        lines.append(
            f"| {key} | {_value(baseline_metrics, key)} | {_value(corrupted_metrics, key)} | "
            f"{_value(repaired_metrics, key)} | {_delta(corrupted_metrics, baseline_metrics, key)} | "
            f"{_delta(repaired_metrics, baseline_metrics, key)} |"
        )

    lines += ["", "## 4. Observability signals", "",
              "| Signal | Baseline | Corrupted | Repaired |", "|---|---|---|---|",
              f"| quality status | {_quality_status(baseline_quality)} | {_quality_status(corrupted_quality)} | "
              f"{_quality_status(repaired_quality)} |",
              f"| failed checks | {_failed_checks(baseline_quality)} | {_failed_checks(corrupted_quality)} | "
              f"{_failed_checks(repaired_quality)} |",
              f"| total_rows | {(baseline_quality or {}).get('total_rows', 'N/A')} | "
              f"{corrupted_quality.get('total_rows', 'N/A')} | {repaired_quality.get('total_rows', 'N/A')} |",
              f"| is_fresh | {(baseline_freshness or {}).get('is_fresh', 'N/A')} | "
              f"{corrupted_freshness.get('is_fresh', 'N/A')} | {repaired_freshness.get('is_fresh', 'N/A')} |",
              f"| stale_rows | {(baseline_freshness or {}).get('stale_rows', 'N/A')} | "
              f"{corrupted_freshness.get('stale_rows', 'N/A')} | {repaired_freshness.get('stale_rows', 'N/A')} |",
              f"| max_age_days | {(baseline_freshness or {}).get('max_age_days', 'N/A')} | "
              f"{corrupted_freshness.get('max_age_days', 'N/A')} | {repaired_freshness.get('max_age_days', 'N/A')} |",
              f"| oldest_published | {(baseline_freshness or {}).get('oldest_published', 'N/A')} | "
              f"{corrupted_freshness.get('oldest_published', 'N/A')} | "
              f"{repaired_freshness.get('oldest_published', 'N/A')} |",
              ""]

    lines += _per_question_section(corruption_log, baseline_answers, corrupted_answers, repaired_answers)

    lines += ["## 6. Interpretation", ""]
    if repair_verification:
        lines += [
            f"**Repair provenance.** The repaired dataset is rebuilt from `{repair_verification.get('source')}` "
            "(the raw snapshot frozen at C2) through the same cleaning logic as the baseline - the corrupted CSV "
            "is never read back. Fetching Crossref again could return changed records and would invalidate the "
            "controlled comparison.",
            "",
            f"- Repaired vs baseline documents: {repair_verification.get('repaired_rows')} vs "
            f"{repair_verification.get('baseline_rows')}; identical paper_id set: "
            f"**{repair_verification.get('paper_ids_match')}**.",
            f"- Documents missing after repair: {repair_verification.get('missing_after_repair') or 'none'}.",
            f"- Content identical on {', '.join(repair_verification.get('content_columns_compared') or [])} "
            f"(whitespace-normalised): **{repair_verification.get('content_matches')}**; "
            f"documents that changed: {repair_verification.get('documents_with_changed_content') or 'none'}.",
            "",
        ]
    lines += [
        "**Why the metrics move.** `text_for_embedding` is dominated by the summary, so blanked and "
        "noise-prefixed summaries push a document away from its own question in MiniLM space, and "
        "`qa._extract_answer` returns the first sentence of that summary - an empty or off-topic answer scores "
        "~0 token F1. Deleting the newest record makes its question unanswerable at any top_k. Stale dates "
        "corrupt the answer of date questions directly and trip the freshness monitor. Duplicated paper_ids "
        "consume top_k slots with a repeat of the same document and break the uniqueness check.",
        "",
        "**What this proves.** Bad data degrades the agent even though the code, the prompts, the embedding "
        "model and the test set are byte-identical across the three runs; rebuilding the clean layer from the "
        "raw snapshot restores the baseline behaviour. Quality and freshness checks flag the corrupted state "
        "before any evaluation is run, which is the point of the observability layer.",
    ]
    write_text(report_path, "\n".join(lines) + "\n")
