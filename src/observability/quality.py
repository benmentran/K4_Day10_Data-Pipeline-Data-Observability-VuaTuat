from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import pandas as pd

from core.config import Settings
from core.utils import now_utc, write_json


logger = logging.getLogger(__name__)


# --------------------------------------------------------------------------
# Nguong quality - chot tai CP1 dua tren so lieu that cua baseline
# (24 dong, summary min 826 ky tu, age_days max 175).
# Nguong tot la nguong tach duoc baseline khoi corrupted dataset.
# --------------------------------------------------------------------------

MIN_ROWS = 20
MIN_SUMMARY_CHARS = 100

SEVERITY_ERROR = "error"
SEVERITY_WARNING = "warning"

# 9 cot ma LocalEmbeddingIndex._build_documents() doc truc tiep + age_days
INDEX_REQUIRED_COLUMNS = [
    "paper_id",
    "title",
    "summary",
    "authors_joined",
    "categories_joined",
    "published",
    "abs_url",
    "pdf_url",
    "text_for_embedding",
]
REQUIRED_COLUMNS = [*INDEX_REQUIRED_COLUMNS, "age_days"]


def _clean_str_series(df: pd.DataFrame, column: str) -> pd.Series:
    """Doc cot text ve dang string da strip, coi NaN la chuoi rong.

    Can thiet vi pd.read_csv mac dinh bien chuoi rong thanh NaN, va
    astype(str) tren NaN se ra chuoi 'nan' thay vi ''.
    """
    return df[column].fillna("").astype(str).str.strip()


def _build_check(
    name: str,
    success: bool,
    observed: Any,
    expected: Any,
    detail: str = "",
    severity: str = SEVERITY_ERROR,
) -> dict[str, Any]:
    """Moi check co cung shape de reporting.py render duoc thanh bang."""
    return {
        "name": name,
        "severity": severity,
        "success": bool(success),
        "observed": observed,
        "expected": expected,
        "detail": detail,
    }


def _check_required_columns(df: pd.DataFrame) -> dict[str, Any]:
    missing = [column for column in REQUIRED_COLUMNS if column not in df.columns]
    return _build_check(
        name="required_columns_present",
        success=not missing,
        observed=len(df.columns) - len(missing),
        expected=len(REQUIRED_COLUMNS),
        detail=f"Thieu cot: {missing}" if missing else "",
    )


def _check_row_count(df: pd.DataFrame) -> dict[str, Any]:
    return _build_check(
        name="row_count_minimum",
        success=len(df) >= MIN_ROWS,
        observed=len(df),
        expected=f">= {MIN_ROWS}",
        detail="Corpus qua nho, retrieval se khong du context" if len(df) < MIN_ROWS else "",
    )


def _check_paper_id_not_null(df: pd.DataFrame) -> dict[str, Any]:
    if "paper_id" not in df.columns:
        return _build_check("paper_id_not_null", False, "missing", 0, "Thieu cot paper_id")
    empty = int((_clean_str_series(df, "paper_id") == "").sum())
    return _build_check(
        name="paper_id_not_null",
        success=empty == 0,
        observed=empty,
        expected=0,
        detail=f"{empty} dong khong co paper_id" if empty else "",
    )


def _check_paper_id_unique(df: pd.DataFrame) -> dict[str, Any]:
    if "paper_id" not in df.columns:
        return _build_check("paper_id_unique", False, "missing", 0, "Thieu cot paper_id")
    duplicated = int(df["paper_id"].duplicated().sum())
    return _build_check(
        name="paper_id_unique",
        success=duplicated == 0,
        observed=duplicated,
        expected=0,
        detail=f"{duplicated} dong duplicate -> retrieval tra ve cung mot bai nhieu lan" if duplicated else "",
    )


def _check_title_not_null(df: pd.DataFrame) -> dict[str, Any]:
    if "title" not in df.columns:
        return _build_check("title_not_null", False, "missing", 0, "Thieu cot title")
    empty = int((_clean_str_series(df, "title") == "").sum())
    return _build_check(
        name="title_not_null",
        success=empty == 0,
        observed=empty,
        expected=0,
        detail=f"{empty} dong title rong -> index.lookup() theo title se truot" if empty else "",
    )


def _check_summary_length(df: pd.DataFrame) -> dict[str, Any]:
    if "summary" not in df.columns:
        return _build_check("summary_min_length", False, "missing", 0, "Thieu cot summary")

    # Contract clean schema khong co cot summary_chars -> tu tinh tu summary.
    if "summary_chars" in df.columns:
        lengths = pd.to_numeric(df["summary_chars"], errors="coerce").fillna(0).astype(int)
    else:
        lengths = _clean_str_series(df, "summary").str.len()

    too_short = int((lengths < MIN_SUMMARY_CHARS).sum())
    shortest = int(lengths.min()) if len(df) else 0
    return _build_check(
        name="summary_min_length",
        success=too_short == 0,
        observed=too_short,
        expected=0,
        detail=(
            f"{too_short} dong co summary < {MIN_SUMMARY_CHARS} ky tu (ngan nhat {shortest})"
            if too_short
            else ""
        ),
    )


def _check_text_for_embedding(df: pd.DataFrame) -> dict[str, Any]:
    if "text_for_embedding" not in df.columns:
        return _build_check("text_for_embedding_not_null", False, "missing", 0, "Thieu cot text_for_embedding")
    empty = int((_clean_str_series(df, "text_for_embedding") == "").sum())
    return _build_check(
        name="text_for_embedding_not_null",
        success=empty == 0,
        observed=empty,
        expected=0,
        detail=f"{empty} dong khong co noi dung de embed" if empty else "",
    )


def _check_no_nan_in_index_columns(df: pd.DataFrame) -> dict[str, Any]:
    present = [column for column in INDEX_REQUIRED_COLUMNS if column in df.columns]
    with_nan = [column for column in present if bool(df[column].isna().any())]
    return _build_check(
        name="no_nan_in_index_columns",
        success=not with_nan,
        observed=len(with_nan),
        expected=0,
        detail=(
            f"Cot co NaN: {with_nan}. NaN la float -> loi khi ghi vao Chroma metadata. "
            "Doc CSV bang pd.read_csv(path, keep_default_na=False)."
            if with_nan
            else ""
        ),
    )


def _check_freshness(df: pd.DataFrame, settings: Settings) -> dict[str, Any]:
    threshold = settings.freshness_threshold_days
    if "age_days" not in df.columns:
        return _build_check("freshness_age_days", False, "missing", 0, "Thieu cot age_days")

    ages = pd.to_numeric(df["age_days"], errors="coerce")
    stale = int((ages > threshold).sum())
    oldest = int(ages.max()) if len(df) and ages.notna().any() else 0
    return _build_check(
        name="freshness_age_days",
        success=stale == 0,
        observed=stale,
        expected=0,
        detail=(
            f"{stale} dong co age_days > {threshold} (cu nhat {oldest} ngay)"
            if stale
            else f"Bai cu nhat {oldest} ngay, nguong {threshold}"
        ),
    )


def _check_categories_completeness(df: pd.DataFrame) -> dict[str, Any]:
    """Warning-level: Crossref rat hay thieu field `subject`.

    Khong phai loi pipeline, nhung `qa._extract_answer` tra thang
    metadata["categories_joined"] cho cau hoi "what categories..." -> o rong
    lam token_f1 ve 0 ma khong co exception nao duoc nem ra.
    """
    if "categories_joined" not in df.columns:
        return _build_check(
            "categories_completeness", False, "missing", 0, "Thieu cot categories_joined", SEVERITY_WARNING
        )
    empty = int((_clean_str_series(df, "categories_joined") == "").sum())
    return _build_check(
        name="categories_completeness",
        success=empty == 0,
        observed=empty,
        expected=0,
        detail=(
            f"{empty}/{len(df)} dong khong co categories -> cau hoi 'what categories' se tra ve rong"
            if empty
            else ""
        ),
        severity=SEVERITY_WARNING,
    )


def run_data_quality_checks(df: pd.DataFrame, settings: Settings, report_name: str) -> dict[str, Any]:
    """Chay bo data quality checks tren cleaned dataframe.

    Ham duoc goi 3 lan voi report_name = "baseline" / "corrupted" / "repaired".
    Ket qua ghi ra file rieng theo report_name de khong ghi de len nhau.

    Args:
        df: Cleaned dataframe can kiem tra.
        settings: Cau hinh pipeline (lay quality_dir va freshness_threshold_days).
        report_name: Ten trang thai, dung lam ten file artifact.

    Returns:
        Dict ket qua cho reporting.py render, gom:
        report_name, generated_at, total_rows, success, checks,
        failed_checks, warnings, artifact_path.
        `success` chi tinh cac check severity="error"; warning khong lam fail.
    """
    checks = [
        _check_required_columns(df),
        _check_row_count(df),
        _check_paper_id_not_null(df),
        _check_paper_id_unique(df),
        _check_title_not_null(df),
        _check_summary_length(df),
        _check_text_for_embedding(df),
        _check_no_nan_in_index_columns(df),
        _check_freshness(df, settings),
        _check_categories_completeness(df),
    ]

    failed = [c["name"] for c in checks if not c["success"] and c["severity"] == SEVERITY_ERROR]
    warnings = [c["name"] for c in checks if not c["success"] and c["severity"] == SEVERITY_WARNING]

    artifact_path = Path(settings.paths.quality_dir) / f"{report_name}.json"
    payload: dict[str, Any] = {
        "report_name": report_name,
        "generated_at": now_utc().isoformat(),
        "total_rows": int(len(df)),
        "total_checks": len(checks),
        "passed_checks": sum(1 for c in checks if c["success"]),
        "success": not failed,
        "checks": checks,
        "failed_checks": failed,
        "warnings": warnings,
        "artifact_path": str(artifact_path),
    }

    write_json(artifact_path, payload)
    logger.info(
        "Quality [%s]: %s (%d/%d check dat, %d warning) -> %s",
        report_name,
        "PASS" if payload["success"] else "FAIL",
        payload["passed_checks"],
        len(checks),
        len(warnings),
        artifact_path,
    )
    if failed:
        logger.warning("Quality [%s] failed checks: %s", report_name, failed)
    return payload


def build_freshness_report(df: pd.DataFrame, settings: Settings, report_path) -> dict[str, Any]:
    """Tong hop freshness report cho mot trang thai dataset.

    report_path duoc truyen vao chu khong lay tu settings, vi config chi co
    duy nhat mot paths.freshness_report - corrupted/repaired phai ghi ra file
    khac de khong de len ket qua baseline.

    Args:
        df: Cleaned dataframe.
        settings: Cau hinh pipeline (lay freshness_threshold_days).
        report_path: Duong dan file JSON dau ra.

    Returns:
        Dict gom latest_published, oldest_published, stale_rows, total_rows,
        is_fresh, kem cac field phu tro cho reporting.
    """
    threshold = settings.freshness_threshold_days
    total_rows = int(len(df))
    report_path = Path(report_path)

    if total_rows == 0 or "published" not in df.columns or "age_days" not in df.columns:
        payload: dict[str, Any] = {
            "latest_published": None,
            "oldest_published": None,
            "stale_rows": 0,
            "total_rows": total_rows,
            "is_fresh": False,
            "threshold_days": threshold,
            "stale_ratio": 0.0,
            "max_age_days": None,
            "min_age_days": None,
            "generated_at": now_utc().isoformat(),
            "artifact_path": str(report_path),
            "detail": "Dataset rong hoac thieu cot published/age_days.",
        }
        write_json(report_path, payload)
        logger.warning("Freshness: khong du du lieu de danh gia -> %s", report_path)
        return payload

    published = _clean_str_series(df, "published")
    published = published[published != ""]
    ages = pd.to_numeric(df["age_days"], errors="coerce").dropna()

    stale_rows = int((ages > threshold).sum())
    payload = {
        # published la ISO YYYY-MM-DD nen so sanh chuoi cho dung thu tu thoi gian
        "latest_published": str(published.max()) if len(published) else None,
        "oldest_published": str(published.min()) if len(published) else None,
        "stale_rows": stale_rows,
        "total_rows": total_rows,
        "is_fresh": stale_rows == 0,
        "threshold_days": threshold,
        "stale_ratio": round(stale_rows / total_rows, 4),
        "max_age_days": int(ages.max()) if len(ages) else None,
        "min_age_days": int(ages.min()) if len(ages) else None,
        "generated_at": now_utc().isoformat(),
        "artifact_path": str(report_path),
        "detail": "",
    }

    write_json(report_path, payload)
    logger.info(
        "Freshness: %s (%d/%d dong stale, cu nhat %s ngay, nguong %d) -> %s",
        "FRESH" if payload["is_fresh"] else "STALE",
        stale_rows,
        total_rows,
        payload["max_age_days"],
        threshold,
        report_path,
    )
    return payload
