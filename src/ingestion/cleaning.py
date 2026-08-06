from __future__ import annotations

import re
from datetime import UTC, datetime

import pandas as pd

from core.config import Settings
from core.utils import compact_join, ensure_parent, normalize_whitespace, write_csv, write_json
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


def _normalize_id(value: str) -> str:
    return re.sub(r"^https?://(?:dx\.)?doi\.org/", "", value.strip(), flags=re.I).lower()


def build_clean_dataframe(
    records: list[PaperRecord], run_date: datetime, settings: Settings | None = None
) -> pd.DataFrame:
    rows = []
    for rec in records:
        paper_id = _normalize_id(rec.paper_id)
        title = normalize_whitespace(_strip_html_tags(rec.title))
        summary = normalize_whitespace(_strip_html_tags(rec.summary))

        if not title:
            continue
        if len(summary.strip()) < 100:
            continue

        authors_joined = compact_join((normalize_whitespace(x) for x in rec.authors if x), sep=", ") or "unknown"
        categories_joined = compact_join((normalize_whitespace(x) for x in rec.categories if x), sep=", ") or "unknown"

        published_date = _parse_date(rec.published)
        if not paper_id or published_date is None:
            continue
        comparable_run_date = run_date if run_date.tzinfo else run_date.replace(tzinfo=UTC)
        age_days = max(0, (comparable_run_date.date() - published_date.date()).days)
        published = published_date.date().isoformat()
        updated_date = _parse_date(rec.updated)
        updated = updated_date.date().isoformat() if updated_date else ""

        primary_category = normalize_whitespace(rec.primary_category) or "unknown"
        text_for_embedding = "\n".join(
            [f"Title: {title}", f"Authors: {authors_joined}", f"Categories: {categories_joined}",
             f"Published: {published}", f"Summary: {summary}"]
        )

        rows.append(
            {
                "paper_id": paper_id,
                "title": title,
                "summary": summary,
                "authors_joined": authors_joined,
                "categories_joined": categories_joined,
                "primary_category": primary_category,
                "published": published,
                "updated": updated,
                "age_days": age_days,
                "summary_chars": len(summary),
                "abs_url": normalize_whitespace(rec.abs_url),
                "pdf_url": normalize_whitespace(rec.pdf_url),
                "comment": normalize_whitespace(rec.comment),
                "text_for_embedding": text_for_embedding,
            }
        )

    df = pd.DataFrame(rows)

    if df.empty:
        return df

    df = df.sort_values(["published", "paper_id"], ascending=[False, True])
    df = df.drop_duplicates(subset=["paper_id"], keep="first").reset_index(drop=True)
    df = df.fillna("")

    if settings is not None:
        ensure_parent(settings.paths.clean_csv)
        write_csv(df, settings.paths.clean_csv)
        ensure_parent(settings.paths.clean_json)
        write_json(settings.paths.clean_json, df.to_dict(orient="records"))

    return df
