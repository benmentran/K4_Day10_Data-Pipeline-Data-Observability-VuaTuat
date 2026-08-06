from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from pathlib import Path
import random
import re
from typing import Any

import pandas as pd

from core.utils import now_utc, read_json, write_json


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

# Corruption is seeded so the whole baseline -> corrupted -> repaired comparison
# can be reproduced exactly; nothing here depends on wall-clock randomness.
CORRUPTION_SEED = 42

# "Stale" means the freshness monitor must reject the row, not merely dislike it.
# Year 2000 is ~9700 days old against a 180 day threshold, so a single stale row
# is impossible to miss in the freshness report.
STALE_PUBLISHED_DATE = date(2000, 1, 1)

SCENARIO_DROP = "drop_latest_record"
SCENARIO_BLANK = "blank_summary"
SCENARIO_NOISE = "inject_summary_noise"
SCENARIO_DUPLICATE = "duplicate_record"
SCENARIO_TRUNCATE = "truncate_title"
SCENARIO_STALE = "stale_published_date"

SCENARIO_DESCRIPTIONS: dict[str, str] = {
    SCENARIO_DROP: "Delete the newest record entirely (silent data loss at the source).",
    SCENARIO_BLANK: "Blank the summary so the document embeds on metadata only.",
    SCENARIO_NOISE: "Prepend unrelated content to the summary and append random characters "
                    "to text_for_embedding.",
    SCENARIO_DUPLICATE: "Append a byte-identical copy of the row, paper_id included.",
    SCENARIO_TRUNCATE: "Truncate the title to a fragment.",
    SCENARIO_STALE: f"Rewrite published to {STALE_PUBLISHED_DATE.isoformat()} to defeat the freshness check.",
}

# Scenarios that are handed a share of the corpus outside the frozen test set, so
# the corruption looks like a real upstream incident instead of a hand-picked
# attack on the ten evaluated documents.
EXTRA_TARGETS: dict[str, int] = {
    SCENARIO_BLANK: 2,
    SCENARIO_NOISE: 2,
    SCENARIO_STALE: 2,
    SCENARIO_TRUNCATE: 2,
    SCENARIO_DUPLICATE: 1,
    SCENARIO_DROP: 0,
}

# Test-set documents whose question is not date-shaped are dealt out over these
# four scenarios in turn.
ROTATION = (SCENARIO_BLANK, SCENARIO_NOISE, SCENARIO_DUPLICATE, SCENARIO_TRUNCATE)

# qa._extract_answer answers these straight from the `published` metadata field,
# so a stale date is measurable in the answer, not only in the freshness report.
DATE_QUESTION_PATTERN = re.compile(r"when was|publication date|published on|published\s*\?", re.I)

# Deliberately off-topic for a scholarly RAG corpus. It is prepended (not
# appended) because qa._extract_answer returns the *first* sentence of the
# summary: a trailing block would corrupt the embedding but leave the answer
# looking fine, which would understate the damage.
UNRELATED_TEXT = (
    "Yesterday the weather forecast promised heavy rain, so we cancelled the football match, "
    "went shopping for cooking ingredients and booked a cheap holiday flight instead."
)
NOISE_ALPHABET = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789#$%&@!?*"
RANDOM_NOISE_CHARS = 320


@dataclass(frozen=True)
class CorruptionPlan:
    """Which paper_id is hit by which scenario, decided before anything mutates."""

    assignments: dict[str, list[str]] = field(default_factory=dict)
    test_set_ids: list[str] = field(default_factory=list)
    questions_by_paper_id: dict[str, list[str]] = field(default_factory=dict)

    def scenario_of(self, paper_id: str) -> str | None:
        for scenario, paper_ids in self.assignments.items():
            if paper_id in paper_ids:
                return scenario
        return None

    def test_set_hits(self, scenario: str) -> list[str]:
        return [pid for pid in self.assignments.get(scenario, []) if pid in set(self.test_set_ids)]


def load_test_set_questions(test_set_path: Path | str | None) -> list[dict[str, Any]]:
    """Read the frozen (C2) test set; an absent path means "no overlap constraint"."""
    if test_set_path is None:
        return []
    path = Path(test_set_path)
    if not path.exists():
        return []
    payload = read_json(path)
    return payload if isinstance(payload, list) else []


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


def _newest_first_ids(df: pd.DataFrame) -> list[str]:
    """Cleaning already sorts newest-first; re-derive it so a shuffled frame is safe."""
    published = pd.to_datetime(df["published"], errors="coerce")
    order = published.sort_values(ascending=False, na_position="last").index
    return [str(df.at[index, "paper_id"]) for index in order]


def _allocate(pool: list[str], targets: dict[str, int]) -> dict[str, list[str]]:
    """Deal ids round-robin so every scenario gets its first victim before any gets a second."""
    allocation: dict[str, list[str]] = {scenario: [] for scenario in targets}
    remaining = list(pool)
    for round_index in range(max(targets.values(), default=0)):
        for scenario, target in targets.items():
            if not remaining:
                return allocation
            if round_index < target:
                allocation[scenario].append(remaining.pop(0))
    return allocation


def build_corruption_plan(
    df: pd.DataFrame,
    test_set: list[dict[str, Any]] | None = None,
    seed: int = CORRUPTION_SEED,
) -> CorruptionPlan:
    """Assign each scenario its victims, guaranteeing overlap with the frozen test set.

    A corruption that only touches documents nobody asks about moves no metric, so
    the frozen test set drives the assignment: every document behind a question is
    claimed by exactly one scenario, and the scenario is picked to be *visible* in
    that question's answer (date questions get the stale date, everything else is
    answered from the summary and gets a summary-level corruption). Remaining
    capacity is filled from documents outside the test set.
    """
    test_set = test_set or []
    corpus_ids = [str(value) for value in df["paper_id"]]
    known = set(corpus_ids)

    questions_by_paper_id: dict[str, list[str]] = {}
    test_set_ids: list[str] = []
    for item in test_set:
        for doc_id in item.get("ground_truth_doc_ids", []) or []:
            doc_id = str(doc_id)
            questions_by_paper_id.setdefault(doc_id, []).append(str(item.get("id", "")))
            if doc_id in known and doc_id not in test_set_ids:
                test_set_ids.append(doc_id)

    assignments: dict[str, list[str]] = {scenario: [] for scenario in SCENARIO_DESCRIPTIONS}
    claimed: set[str] = set()

    # The newest record disappears: the strongest possible signal, because no
    # amount of retrieval tuning can find a document that is not in the index.
    # Guard the corpus against being emptied on tiny inputs.
    newest_first = _newest_first_ids(df)
    if newest_first and len(df) > 1:
        assignments[SCENARIO_DROP].append(newest_first[0])
        claimed.add(newest_first[0])

    rotation_index = 0
    for item in test_set:
        question = str(item.get("question", ""))
        for doc_id in item.get("ground_truth_doc_ids", []) or []:
            doc_id = str(doc_id)
            if doc_id not in known or doc_id in claimed:
                continue
            if DATE_QUESTION_PATTERN.search(question):
                scenario = SCENARIO_STALE
            else:
                scenario = ROTATION[rotation_index % len(ROTATION)]
                rotation_index += 1
            assignments[scenario].append(doc_id)
            claimed.add(doc_id)

    # Spread the same scenarios over untested documents. Every scenario keeps at
    # least one victim even when no test set is supplied, so the corruption log
    # stays comparable across runs.
    targets = dict(EXTRA_TARGETS)
    for scenario, paper_ids in assignments.items():
        if not paper_ids:
            targets[scenario] = max(1, targets[scenario])

    pool = [paper_id for paper_id in corpus_ids if paper_id not in claimed]
    random.Random(seed).shuffle(pool)
    for scenario, extra_ids in _allocate(pool, targets).items():
        assignments[scenario].extend(extra_ids)

    return CorruptionPlan(
        assignments=assignments,
        test_set_ids=test_set_ids,
        questions_by_paper_id=questions_by_paper_id,
    )


def _random_characters(rng: random.Random) -> str:
    return "".join(rng.choices(NOISE_ALPHABET, k=RANDOM_NOISE_CHARS))


def corrupt_clean_dataframe(
    df: pd.DataFrame,
    output_log_path: Path | str,
    test_set_path: Path | str | None = None,
    run_date: datetime | None = None,
    seed: int = CORRUPTION_SEED,
) -> pd.DataFrame:
    """Create deterministic, auditable corruptions without mutating ``df``.

    Corruptions keep the clean dataframe schema intact so the same embedding and
    evaluation pipeline can measure their downstream impact. The returned frame
    contains a deleted latest record, blanked summaries, noisy summaries,
    truncated titles, year-2000 publication dates and duplicated paper_ids.

    ``test_set_path`` points at the frozen C2 test set. When supplied, every
    scenario is guaranteed to hit at least one document that the test set asks
    about, and the audit log records exactly which question each corrupted
    document backs. Every mutation is written to ``output_log_path``.
    """
    missing_columns = sorted(REQUIRED_COLUMNS.difference(df.columns))
    if missing_columns:
        raise ValueError(f"Cannot corrupt dataframe; missing columns: {missing_columns}")
    if df.empty:
        raise ValueError("Cannot corrupt an empty dataframe.")

    corrupted = df.copy(deep=True).reset_index(drop=True)
    input_rows = len(corrupted)
    run_date = run_date or now_utc()
    if run_date.tzinfo is None:
        run_date = run_date.replace(tzinfo=UTC)

    test_set = load_test_set_questions(test_set_path)
    plan = build_corruption_plan(corrupted, test_set, seed=seed)
    rng = random.Random(seed)
    events: list[dict[str, Any]] = []
    test_set_ids = set(plan.test_set_ids)

    def record(scenario: str, paper_id: str, parameters: dict[str, Any]) -> None:
        events.append(
            {
                "type": scenario,
                "paper_id": paper_id,
                "question_ids": plan.questions_by_paper_id.get(paper_id, []),
                "in_frozen_test_set": paper_id in test_set_ids,
                "parameters": parameters,
            }
        )

    index_by_paper_id = {str(value): index for index, value in corrupted["paper_id"].items()}

    def rows_for(scenario: str) -> list[tuple[str, int]]:
        pairs = []
        for paper_id in plan.assignments.get(scenario, []):
            index = index_by_paper_id.get(paper_id)
            if index is not None:
                pairs.append((paper_id, index))
        return pairs

    # 1. Silent data loss -------------------------------------------------
    dropped = rows_for(SCENARIO_DROP)
    for paper_id, index in dropped:
        record(SCENARIO_DROP, paper_id, {"published": str(corrupted.at[index, "published"])})

    # 2. Blank summaries --------------------------------------------------
    for paper_id, index in rows_for(SCENARIO_BLANK):
        before_chars = len(str(corrupted.at[index, "summary"]))
        corrupted.at[index, "summary"] = ""
        record(SCENARIO_BLANK, paper_id, {"before_chars": before_chars, "after_chars": 0})

    # 3. Content noise ----------------------------------------------------
    random_noise_by_paper_id: dict[str, str] = {}
    for paper_id, index in rows_for(SCENARIO_NOISE):
        summary = str(corrupted.at[index, "summary"])
        random_characters = _random_characters(rng)
        corrupted.at[index, "summary"] = f"{UNRELATED_TEXT} {summary}".strip()
        random_noise_by_paper_id[paper_id] = random_characters
        record(
            SCENARIO_NOISE,
            paper_id,
            {
                "unrelated_prefix_chars": len(UNRELATED_TEXT),
                "random_chars_appended_to_text_for_embedding": len(random_characters),
                "preview": f"{UNRELATED_TEXT[:60]}... + {random_characters[:24]}...",
            },
        )

    # 4. Truncated titles -------------------------------------------------
    for paper_id, index in rows_for(SCENARIO_TRUNCATE):
        title = str(corrupted.at[index, "title"])
        truncated = title[: max(1, min(12, len(title) // 3))]
        corrupted.at[index, "title"] = truncated
        record(SCENARIO_TRUNCATE, paper_id, {"before": title, "after": truncated})

    # 5. Stale publication dates -----------------------------------------
    stale_published = STALE_PUBLISHED_DATE.isoformat()
    stale_age_days = max(0, (run_date.date() - STALE_PUBLISHED_DATE).days)
    for paper_id, index in rows_for(SCENARIO_STALE):
        before = str(corrupted.at[index, "published"])
        before_age = pd.to_numeric(corrupted.at[index, "age_days"], errors="coerce")
        corrupted.at[index, "published"] = stale_published
        corrupted.at[index, "age_days"] = stale_age_days
        record(
            SCENARIO_STALE,
            paper_id,
            {
                "before": before,
                "after": stale_published,
                "before_age_days": None if pd.isna(before_age) else int(before_age),
                "after_age_days": stale_age_days,
            },
        )

    # 6. Duplicates (same paper_id) ---------------------------------------
    duplicate_rows = rows_for(SCENARIO_DUPLICATE)
    for paper_id, _ in duplicate_rows:
        record(SCENARIO_DUPLICATE, paper_id, {"copies_added": 1})

    corrupted = corrupted.drop(index=[index for _, index in dropped])
    duplicates = corrupted.loc[[index for _, index in duplicate_rows if index in corrupted.index]]
    corrupted = pd.concat([corrupted, duplicates.copy(deep=True)], ignore_index=True)

    # Every mutation above must reach the text MiniLM actually embeds; this also
    # rebuilds the text of the duplicated rows. The random characters are appended
    # to text_for_embedding only, because they belong to no clean-schema field.
    corrupted["text_for_embedding"] = corrupted.apply(_embedding_text, axis=1)
    corrupted["text_for_embedding"] = [
        f"{text}\n{random_noise_by_paper_id[str(paper_id)]}"
        if str(paper_id) in random_noise_by_paper_id
        else text
        for paper_id, text in zip(corrupted["paper_id"], corrupted["text_for_embedding"], strict=False)
    ]
    corrupted["summary_chars"] = corrupted["summary"].astype(str).str.len().astype(int)
    corrupted = corrupted.reset_index(drop=True)

    write_json(Path(output_log_path), _build_log(plan, events, input_rows, len(corrupted),
                                                 len(dropped), len(duplicates), test_set,
                                                 test_set_path, run_date, seed))
    return corrupted


def _build_log(
    plan: CorruptionPlan,
    events: list[dict[str, Any]],
    input_rows: int,
    output_rows: int,
    rows_dropped: int,
    duplicate_rows_added: int,
    test_set: list[dict[str, Any]],
    test_set_path: Path | str | None,
    run_date: datetime,
    seed: int,
) -> dict[str, Any]:
    event_counts = Counter(event["type"] for event in events)
    test_set_ids = set(plan.test_set_ids)
    corrupted_ids = {paper_id for paper_ids in plan.assignments.values() for paper_id in paper_ids}

    scenarios = {
        scenario: {
            "description": SCENARIO_DESCRIPTIONS[scenario],
            "paper_ids": plan.assignments.get(scenario, []),
            "count": len(plan.assignments.get(scenario, [])),
            "frozen_test_set_paper_ids": plan.test_set_hits(scenario),
            "frozen_test_set_question_ids": sorted(
                question_id
                for paper_id in plan.test_set_hits(scenario)
                for question_id in plan.questions_by_paper_id.get(paper_id, [])
            ),
        }
        for scenario in SCENARIO_DESCRIPTIONS
    }

    questions_affected = []
    for item in test_set:
        for doc_id in item.get("ground_truth_doc_ids", []) or []:
            scenario = plan.scenario_of(str(doc_id))
            if scenario:
                questions_affected.append(
                    {
                        "question_id": str(item.get("id", "")),
                        "question": str(item.get("question", "")),
                        "paper_id": str(doc_id),
                        "scenario": scenario,
                    }
                )

    return {
        "generated_at": now_utc().isoformat(),
        "run_date": run_date.date().isoformat(),
        "seed": seed,
        "input_rows": input_rows,
        "output_rows": output_rows,
        "rows_dropped": rows_dropped,
        "duplicate_rows_added": duplicate_rows_added,
        "documents_corrupted": len(corrupted_ids),
        "scenarios": scenarios,
        "event_counts": dict(sorted(event_counts.items())),
        "frozen_test_set": {
            "path": str(test_set_path) if test_set_path else None,
            "questions": len(test_set),
            "ground_truth_paper_ids": sorted(test_set_ids),
            "corrupted_ground_truth_paper_ids": sorted(test_set_ids & corrupted_ids),
            "overlap_count": len(test_set_ids & corrupted_ids),
            "overlap_ratio": round(len(test_set_ids & corrupted_ids) / len(test_set_ids), 4)
            if test_set_ids
            else 0.0,
            "scenarios_without_test_set_overlap": sorted(
                scenario
                for scenario, payload in scenarios.items()
                if payload["count"] and not payload["frozen_test_set_paper_ids"]
            ),
            "questions_affected": questions_affected,
        },
        "events": events,
    }
