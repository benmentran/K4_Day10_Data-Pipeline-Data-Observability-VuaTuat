from __future__ import annotations

from typing import Any

import pandas as pd

from core.config import Settings
from core.utils import write_json


def run_data_quality_checks(df: pd.DataFrame, settings: Settings, report_name: str) -> dict[str, Any]:
    checks = {
        "row_count_positive": len(df) > 0,
        "paper_id_not_null": "paper_id" in df and df["paper_id"].astype(str).str.strip().ne("").all(),
        "paper_id_unique": "paper_id" in df and df["paper_id"].is_unique,
        "title_not_null": "title" in df and df["title"].astype(str).str.strip().ne("").all(),
        "summary_min_100_chars": "summary_chars" in df and pd.to_numeric(df["summary_chars"], errors="coerce").ge(100).all(),
        "freshness_within_threshold": "age_days" in df and pd.to_numeric(df["age_days"], errors="coerce").le(settings.freshness_threshold_days).all(),
    }
    payload = {
        "report_name": report_name,
        "status": "PASS" if all(checks.values()) else "FAIL",
        "total_rows": len(df),
        "checks": [{"name": name, "status": "PASS" if passed else "FAIL"} for name, passed in checks.items()],
        "failed_checks": [name for name, passed in checks.items() if not passed],
    }
    write_json(settings.paths.quality_dir / f"{report_name}.json", payload)
    return payload


def build_freshness_report(df: pd.DataFrame, settings: Settings, report_path) -> dict[str, Any]:
    dates = pd.to_datetime(df.get("published", pd.Series(dtype=str)), errors="coerce")
    ages = pd.to_numeric(df.get("age_days", pd.Series(dtype=float)), errors="coerce")
    stale_rows = int((ages > settings.freshness_threshold_days).sum())
    payload = {
        "latest_published": dates.max().date().isoformat() if dates.notna().any() else None,
        "oldest_published": dates.min().date().isoformat() if dates.notna().any() else None,
        "stale_rows": stale_rows,
        "total_rows": len(df),
        "threshold_days": settings.freshness_threshold_days,
        "is_fresh": bool(len(df) > 0 and stale_rows == 0 and dates.notna().all()),
    }
    write_json(report_path, payload)
    return payload
