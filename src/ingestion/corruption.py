from __future__ import annotations

from collections import Counter
from datetime import timedelta
from math import ceil
from pathlib import Path
from typing import Any

import pandas as pd

from core.utils import write_json


REQUIRED_COLUMNS = {
    "paper_id",
    "title",
    "summary",
    "authors_joined",
    "categories_joined",
    "published",
    "age_days",
    "summary_chars",
    "text_for_embedding",
}

# The noise is intentionally unrelated to the scholarly corpus. Repeating it gives
# the corruption enough weight to measurably disturb MiniLM retrieval on a small
# (roughly 24-document) lab dataset.
NOISE_TEXT = " ".join(
    [
        "UNRELATED CORRUPTED CONTENT weather cooking football travel shopping random tokens"
    ]
    * 12
)


def _embedding_text(row: pd.Series) -> str:
    """Rebuild the embedding text using the clean-schema contract."""
    return "\n".join(
        [
            f"Title: {row['title']}",
            f"Authors: {row['authors_joined']}",
            f"Categories: {row['categories_joined']}",
            f"Published: {row['published']}",
            f"Summary: {row['summary']}",
        ]
    )


def _scenario_size(row_count: int, fraction: float = 0.2) -> int:
    return min(row_count, max(1, ceil(row_count * fraction))) if row_count else 0


def corrupt_clean_dataframe(df: pd.DataFrame, output_log_path) -> pd.DataFrame:
    """Create deterministic, auditable corruptions without mutating ``df``.

    Corruptions deliberately keep the clean dataframe schema intact so the same
    embedding/evaluation pipeline can measure their downstream impact. The
    returned dataframe contains missing summaries, noisy summaries, truncated
    titles, stale dates and duplicate IDs; some newest records are also removed.
    Every affected paper is recorded in ``output_log_path``.
    """
    missing_columns = sorted(REQUIRED_COLUMNS.difference(df.columns))
    if missing_columns:
        raise ValueError(f"Cannot corrupt dataframe; missing columns: {missing_columns}")
    if df.empty:
        raise ValueError("Cannot corrupt an empty dataframe.")

    corrupted = df.copy(deep=True).reset_index(drop=True)
    events: list[dict[str, Any]] = []
    input_rows = len(corrupted)

    # Cleaning guarantees newest-first order, but sorting here makes this contract
    # explicit and protects the scenario when callers provide a shuffled frame.
    published_dates = pd.to_datetime(corrupted["published"], errors="coerce")
    latest_order = published_dates.sort_values(ascending=False, na_position="last").index.tolist()
    # Never remove the only row: the remaining corruption scenarios still need a
    # document to operate on and the downstream index cannot be empty.
    drop_count = min(_scenario_size(input_rows, 0.15), max(0, input_rows - 1))
    dropped_indices = latest_order[:drop_count]
    for index in dropped_indices:
        row = corrupted.loc[index]
        events.append(
            {
                "type": "drop_latest_record",
                "paper_id": str(row["paper_id"]),
                "parameters": {"published": str(row["published"])},
            }
        )
    corrupted = corrupted.drop(index=dropped_indices).reset_index(drop=True)

    affected_count = _scenario_size(len(corrupted))
    indices = list(corrupted.index)

    # Allocate from different offsets where possible. On very small inputs the
    # scenarios may overlap, which is preferable to silently skipping coverage.
    blank_indices = indices[:affected_count]
    noise_indices = [indices[(affected_count + i) % len(indices)] for i in range(affected_count)]
    title_indices = [indices[(2 * affected_count + i) % len(indices)] for i in range(affected_count)]
    stale_indices = [indices[(3 * affected_count + i) % len(indices)] for i in range(affected_count)]

    for index in blank_indices:
        paper_id = str(corrupted.at[index, "paper_id"])
        before_chars = len(str(corrupted.at[index, "summary"]))
        corrupted.at[index, "summary"] = ""
        corrupted.at[index, "summary_chars"] = 0
        events.append(
            {
                "type": "blank_summary",
                "paper_id": paper_id,
                "parameters": {"before_chars": before_chars, "after_chars": 0},
            }
        )

    for index in noise_indices:
        paper_id = str(corrupted.at[index, "paper_id"])
        summary = str(corrupted.at[index, "summary"])
        noisy_summary = f"{summary} {NOISE_TEXT}".strip()
        corrupted.at[index, "summary"] = noisy_summary
        corrupted.at[index, "summary_chars"] = len(noisy_summary)
        events.append(
            {
                "type": "inject_summary_noise",
                "paper_id": paper_id,
                "parameters": {"noise_chars": len(NOISE_TEXT)},
            }
        )

    for index in title_indices:
        paper_id = str(corrupted.at[index, "paper_id"])
        title = str(corrupted.at[index, "title"])
        truncated = title[: max(1, min(12, len(title) // 3))]
        corrupted.at[index, "title"] = truncated
        events.append(
            {
                "type": "truncate_title",
                "paper_id": paper_id,
                "parameters": {"before": title, "after": truncated},
            }
        )

    stale_days = 730
    for index in stale_indices:
        paper_id = str(corrupted.at[index, "paper_id"])
        before = pd.to_datetime(corrupted.at[index, "published"], errors="coerce")
        if pd.isna(before):
            events.append(
                {
                    "type": "stale_published_date_skipped",
                    "paper_id": paper_id,
                    "parameters": {"reason": "invalid published date"},
                }
            )
            continue
        after = before - timedelta(days=stale_days)
        corrupted.at[index, "published"] = after.date().isoformat()
        corrupted.at[index, "age_days"] = int(corrupted.at[index, "age_days"]) + stale_days
        events.append(
            {
                "type": "stale_published_date",
                "paper_id": paper_id,
                "parameters": {
                    "before": before.date().isoformat(),
                    "after": after.date().isoformat(),
                    "days_added_to_age": stale_days,
                },
            }
        )

    duplicate_count = min(2, max(1, ceil(len(corrupted) * 0.1)))
    duplicates = corrupted.iloc[:duplicate_count].copy(deep=True)
    for _, row in duplicates.iterrows():
        events.append(
            {
                "type": "duplicate_record",
                "paper_id": str(row["paper_id"]),
                "parameters": {"copies_added": 1},
            }
        )
    corrupted = pd.concat([corrupted, duplicates], ignore_index=True)

    # All mutations that affect retrieval are now reflected in the actual content
    # sent to MiniLM. This also rebuilds the text for duplicate rows.
    corrupted["text_for_embedding"] = corrupted.apply(_embedding_text, axis=1)
    corrupted["summary_chars"] = corrupted["summary"].astype(str).str.len().astype(int)

    event_counts = Counter(event["type"] for event in events)
    log_payload = {
        "input_rows": input_rows,
        "output_rows": len(corrupted),
        "rows_dropped": drop_count,
        "duplicate_rows_added": duplicate_count,
        "event_counts": dict(sorted(event_counts.items())),
        "events": events,
    }
    write_json(Path(output_log_path), log_payload)
    return corrupted
