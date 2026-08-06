from __future__ import annotations

import re
from datetime import UTC, datetime

import pandas as pd

from core.config import Settings
from core.utils import compact_join, ensure_parent, write_csv, write_json
from ingestion.crossref import PaperRecord


def _strip_html_tags(text: str) -> str:
    cleaned = re.sub(r"<[^>]+>", " ", text)
    cleaned = re.sub(r"&[a-z]+;", " ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


def _parse_date(date_str: str) -> datetime | None:
    if not date_str:
        return None
    for fmt in ("%Y-%m-%d", "%Y-%m", "%Y"):
        try:
            return datetime.strptime(date_str, fmt).replace(tzinfo=UTC)
        except ValueError:
            continue
    return None


def build_clean_dataframe(records: list[PaperRecord], run_date: datetime, settings: Settings) -> pd.DataFrame:
    rows = []
    for rec in records:
        title = _strip_html_tags(rec.title)
        summary = _strip_html_tags(rec.summary)

        if not title:
            continue
        if len(summary.strip()) < 100:
            continue

        authors_joined = compact_join(rec.authors, sep=", ")
        categories_joined = compact_join(rec.categories, sep=", ")

        published_date = _parse_date(rec.published)
        if published_date is not None:
            age_days = (run_date - published_date).days
        else:
            age_days = -1

        text_for_embedding = f"Title: {title} | Authors: {authors_joined} | Summary: {summary}"

        rows.append(
            {
                "paper_id": rec.paper_id,
                "title": title,
                "summary": summary,
                "authors_joined": authors_joined,
                "categories_joined": categories_joined,
                "primary_category": rec.primary_category,
                "published": rec.published,
                "updated": rec.updated,
                "age_days": age_days,
                "abs_url": rec.abs_url,
                "pdf_url": rec.pdf_url,
                "comment": rec.comment,
                "text_for_embedding": text_for_embedding,
            }
        )

    df = pd.DataFrame(rows)

    if df.empty:
        return df

    df = df.drop_duplicates(subset=["paper_id"])
    df = df.sort_values("age_days", ascending=True).reset_index(drop=True)

    ensure_parent(settings.paths.clean_csv)
    write_csv(df, settings.paths.clean_csv)
    ensure_parent(settings.paths.clean_json)
    write_json(settings.paths.clean_json, df.to_dict(orient="records"))

    return df