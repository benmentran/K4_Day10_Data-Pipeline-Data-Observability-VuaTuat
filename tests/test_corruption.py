from __future__ import annotations

import json

import pandas as pd
import pytest

from ingestion.corruption import (
    REQUIRED_COLUMNS,
    SCENARIO_DESCRIPTIONS,
    STALE_PUBLISHED_DATE,
    UNRELATED_TEXT,
    corrupt_clean_dataframe,
)


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


def _frozen_test_set(tmp_path, row_count: int = 10):
    """A frozen test set shaped like C2: newest papers first, one date question."""
    questions = []
    for offset, paper_index in enumerate(range(row_count - 1, row_count - 8, -1)):
        template = "When was 'paper {i}' published?" if offset == 1 else "What does 'paper {i}' contribute?"
        questions.append(
            {
                "id": f"q{offset + 1}",
                "question_type": "factual",
                "question": template.format(i=paper_index),
                "ground_truth": "irrelevant for corruption planning",
                "ground_truth_doc_ids": [f"10.1000/{paper_index}"],
            }
        )
    path = tmp_path / "test_set.json"
    path.write_text(json.dumps(questions), encoding="utf-8")
    return path, questions


def test_every_scenario_hits_the_frozen_test_set(tmp_path):
    baseline = _clean_frame()
    test_set_path, questions = _frozen_test_set(tmp_path)
    log_path = tmp_path / "corruption_log.json"

    corrupt_clean_dataframe(baseline, log_path, test_set_path=test_set_path)
    log = json.loads(log_path.read_text(encoding="utf-8"))

    # A corruption that misses the evaluated documents cannot move any metric.
    for scenario in SCENARIO_DESCRIPTIONS:
        hits = log["scenarios"][scenario]["frozen_test_set_paper_ids"]
        assert hits, f"scenario {scenario} does not overlap the frozen test set"
    frozen = log["frozen_test_set"]
    assert frozen["scenarios_without_test_set_overlap"] == []
    assert frozen["overlap_count"] == len(questions)
    assert frozen["overlap_ratio"] == 1.0
    assert {item["question_id"] for item in frozen["questions_affected"]} == {q["id"] for q in questions}

    # The date question must be the one that receives the stale date, because a
    # stale date is only observable in the answer of a date question.
    scenario_by_question = {item["question_id"]: item["scenario"] for item in frozen["questions_affected"]}
    assert scenario_by_question["q2"] == "stale_published_date"


def test_stale_dates_are_rewritten_to_year_2000(tmp_path):
    baseline = _clean_frame()
    corrupted = corrupt_clean_dataframe(baseline, tmp_path / "log.json")

    stale = corrupted[corrupted["published"] == STALE_PUBLISHED_DATE.isoformat()]
    assert not stale.empty
    assert (stale["age_days"] > 365 * 20).all()


def test_noise_reaches_text_for_embedding(tmp_path):
    baseline = _clean_frame()
    log_path = tmp_path / "log.json"
    corrupted = corrupt_clean_dataframe(baseline, log_path)
    log = json.loads(log_path.read_text(encoding="utf-8"))

    noisy_ids = log["scenarios"]["inject_summary_noise"]["paper_ids"]
    noisy = corrupted[corrupted["paper_id"].isin(noisy_ids)]
    assert not noisy.empty
    # Unrelated content prepended (so first_sentence() picks it up) and random
    # characters that exist only in the embedded text.
    assert noisy["summary"].str.startswith(UNRELATED_TEXT).all()
    assert noisy["text_for_embedding"].str.contains(UNRELATED_TEXT, regex=False).all()

    random_chars = {
        event["paper_id"]: event["parameters"]["random_chars_appended_to_text_for_embedding"]
        for event in log["events"]
        if event["type"] == "inject_summary_noise"
    }
    for row in noisy.itertuples():
        trailing = row.text_for_embedding.rsplit("\n", 1)[-1]
        assert len(trailing) == random_chars[row.paper_id]
        assert trailing not in row.summary


def test_duplicates_keep_the_original_paper_id(tmp_path):
    baseline = _clean_frame()
    log_path = tmp_path / "log.json"
    corrupted = corrupt_clean_dataframe(baseline, log_path)
    log = json.loads(log_path.read_text(encoding="utf-8"))

    duplicate_ids = set(log["scenarios"]["duplicate_record"]["paper_ids"])
    counts = corrupted["paper_id"].value_counts()
    assert duplicate_ids
    assert all(counts[paper_id] == 2 for paper_id in duplicate_ids)
    dropped_ids = set(log["scenarios"]["drop_latest_record"]["paper_ids"])
    assert not dropped_ids & set(corrupted["paper_id"])


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
