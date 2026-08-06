from __future__ import annotations

import json

import pandas as pd
import pytest

from ingestion.corruption import REQUIRED_COLUMNS, corrupt_clean_dataframe


def _clean_frame(row_count: int = 10) -> pd.DataFrame:
    rows = []
    for index in range(row_count):
        summary = f"A clean scholarly abstract about retrieval system number {index}. " * 3
        rows.append(
            {
                "paper_id": f"10.1000/{index}",
                "title": f"A complete paper title number {index}",
                "summary": summary,
                "authors_joined": "An Author",
                "categories_joined": "Information Retrieval",
                "published": f"2026-01-{index + 1:02d}",
                "age_days": 30 - index,
                "summary_chars": len(summary),
                "text_for_embedding": "old text",
                "primary_category": "Information Retrieval",
                "abs_url": f"https://doi.org/10.1000/{index}",
                "pdf_url": "",
                "updated": "",
                "comment": "",
            }
        )
    return pd.DataFrame(rows)


def test_corruption_is_auditable_and_does_not_mutate_baseline(tmp_path):
    baseline = _clean_frame()
    original = baseline.copy(deep=True)
    log_path = tmp_path / "corruption_log.json"

    corrupted = corrupt_clean_dataframe(baseline, log_path)
    log = json.loads(log_path.read_text(encoding="utf-8"))

    pd.testing.assert_frame_equal(baseline, original)
    assert log["input_rows"] == len(baseline)
    assert log["output_rows"] == len(corrupted)
    assert set(log["event_counts"]) >= {
        "drop_latest_record",
        "blank_summary",
        "inject_summary_noise",
        "truncate_title",
        "stale_published_date",
        "duplicate_record",
    }
    assert corrupted["paper_id"].duplicated().any()
    assert (corrupted["summary_chars"] == 0).any()
    assert (corrupted["age_days"] > 180).any()
    assert corrupted["text_for_embedding"].str.contains("Title:", regex=False).all()
    assert corrupted["text_for_embedding"].str.contains("Summary:", regex=False).all()


def test_corruption_is_deterministic(tmp_path):
    baseline = _clean_frame()
    first = corrupt_clean_dataframe(baseline, tmp_path / "first.json")
    second = corrupt_clean_dataframe(baseline, tmp_path / "second.json")
    pd.testing.assert_frame_equal(first, second)


def test_corruption_rejects_empty_or_invalid_input(tmp_path):
    with pytest.raises(ValueError, match="empty"):
        corrupt_clean_dataframe(pd.DataFrame(columns=sorted(REQUIRED_COLUMNS)), tmp_path / "empty.json")
    with pytest.raises(ValueError, match="missing columns"):
        corrupt_clean_dataframe(pd.DataFrame({"paper_id": ["x"]}), tmp_path / "invalid.json")
