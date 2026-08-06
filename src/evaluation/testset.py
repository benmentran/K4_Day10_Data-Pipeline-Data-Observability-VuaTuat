from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd


def build_test_set(df: pd.DataFrame, output_path: Path | str) -> list[dict[str, Any]]:
    """Build evaluation test set from cleaned dataframe.

    Args:
        df: Cleaned papers DataFrame with columns including
            paper_id, title, authors_joined, categories_joined, summary, published
        output_path: Path to write the JSON test set

    Returns:
        List of question dictionaries with the required schema:
        {
            "id": str,
            "question_type": str,
            "question": str,
            "ground_truth": str,
            "ground_truth_doc_ids": list[str]
        }
    """
    if len(df) == 0:
        raise ValueError("DataFrame is empty, cannot build test set")

    test_questions: list[dict[str, Any]] = []

    # Define question templates with different types
    question_templates = [
        # Author questions
        {
            "question_type": "factual",
            "template": "Who are the authors of '{title}'?",
            "field": "authors_joined",
            "ground_truth_field": "authors_joined",
        },
        # Publication date questions
        {
            "question_type": "factual",
            "template": "When was '{title}' published?",
            "field": "published",
            "ground_truth_field": "published",
        },
        # Category questions
        {
            "question_type": "factual",
            "template": "What category/journal is '{title}' published in?",
            "field": "categories_joined",
            "ground_truth_field": "categories_joined",
        },
        # Summary/description questions
        {
            "question_type": "factual",
            "template": "What is the main contribution of '{title}'?",
            "field": "summary",
            "ground_truth_field": "summary",
        },
        # Application/use case questions
        {
            "question_type": "factual",
            "template": "What is the primary application of the method described in '{title}'?",
            "field": "summary",
            "ground_truth_field": "summary",
        },
        # Methodology questions
        {
            "question_type": "factual",
            "template": "What methodology does '{title}' employ?",
            "field": "summary",
            "ground_truth_field": "summary",
        },
    ]

    # Sample papers for questions (ensure diversity)
    sample_indices = list(range(min(10, len(df))))
    sample_indices = sample_indices[: min(10, len(df))]

    for idx, paper_idx in enumerate(sample_indices):
        if paper_idx >= len(df):
            continue

        row = df.iloc[paper_idx]
        template = question_templates[idx % len(question_templates)]

        title = row.get("title", "")
        # Truncate title for question to keep it readable
        short_title = title[:60] + "..." if len(title) > 60 else title

        question = template["template"].format(title=short_title)

        ground_truth = str(row.get(template["ground_truth_field"], ""))

        # Clean up ground truth (take first sentence for long text)
        if len(ground_truth) > 300:
            ground_truth = ground_truth[:300].rsplit(".", 1)[0] + "."

        test_questions.append({
            "id": f"q{idx + 1}",
            "question_type": template["question_type"],
            "question": question,
            "ground_truth": ground_truth,
            "ground_truth_doc_ids": [str(row.get("paper_id", ""))],
        })

    # Write to output file
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(test_questions, f, indent=2, ensure_ascii=False)

    return test_questions


def load_test_set(path: Path | str) -> list[dict[str, Any]]:
    """Load test set from JSON file.

    Args:
        path: Path to the test set JSON file

    Returns:
        List of question dictionaries
    """
    path = Path(path)
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)
