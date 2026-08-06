from __future__ import annotations

from typing import Any

import pandas as pd

from core.utils import first_sentence, write_json


def build_test_set(df: pd.DataFrame, output_path) -> list[dict[str, Any]]:
    if df.empty:
        raise ValueError("Cannot build a test set from an empty dataframe.")
    samples: list[dict[str, Any]] = []
    question_specs = [
        ("summary", lambda r: f"What is '{r.title}' about?", lambda r: first_sentence(r.summary)),
        ("authors", lambda r: f"Who authored '{r.title}'?", lambda r: r.authors_joined),
        ("date", lambda r: f"When was '{r.title}' published?", lambda r: r.published),
        ("categories", lambda r: f"What categories does '{r.title}' belong to?", lambda r: r.categories_joined),
    ]
    selected = df.head(min(6, len(df)))
    for row_number, row in enumerate(selected.itertuples(index=False)):
        qtype, question, answer = question_specs[row_number % len(question_specs)]
        samples.append({"id": f"q{row_number + 1:02d}", "question_type": qtype,
                        "question": question(row), "ground_truth": str(answer(row)),
                        "ground_truth_doc_ids": [str(row.paper_id)]})
    write_json(output_path, samples)
    return samples
