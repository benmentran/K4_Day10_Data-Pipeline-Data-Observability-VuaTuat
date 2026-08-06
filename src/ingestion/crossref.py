from __future__ import annotations

import hashlib
import json
import logging
import re
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from urllib.parse import urlencode

import requests

from core.config import Settings


logger = logging.getLogger(__name__)


CROSSREF_API_BASE = "https://api.crossref.org/works"

# Regex de loai bo HTML tags
_HTML_TAG_RE = re.compile(r"<[^>]+>")


def _strip_html(text: str) -> str:
    """Loai bo HTML tags tu text."""
    return _HTML_TAG_RE.sub("", text)


def _generate_paper_id(doi: str, title: str) -> str:
    """Tao stable paper_id tu DOI va title hash."""
    raw = f"{doi}|{title}".encode("utf-8")
    return hashlib.sha256(raw).hexdigest()[:16]


def _normalize_text(text: str | None) -> str:
    """Chuan hoa text: loai bo whitespace thua va HTML tags, tra ve empty string neu None."""
    if not text:
        return ""
    text = _strip_html(text)
    return " ".join(text.split())


def _extract_authors(author_list: list[dict]) -> list[str]:
    """Tach danh sach authors thanh list ten day du."""
    authors = []
    for author in author_list:
        given = author.get("given", "")
        family = author.get("family", "")
        if family:
            name = f"{given} {family}".strip() if given else family
            authors.append(name)
    return authors


def _extract_urls(item: dict) -> tuple[str, str]:
    """Tach abstract URL va PDF URL tu Crossref item."""
    abstract_url = ""
    pdf_url = ""

    if "URL" in item:
        abstract_url = item["URL"]

    for link in item.get("link", []):
        if link.get("content-type", "").startswith("application/pdf"):
            pdf_url = link.get("URL", "")
            break

    return abstract_url, pdf_url


def _extract_date(item: dict) -> tuple[str, str]:
    """Tach published date va updated date tu Crossref item."""
    published = ""
    updated = ""

    if "published" in item and item["published"]:
        date_parts = item["published"].get("date-parts", [[]])
        if date_parts and date_parts[0]:
            parts = date_parts[0]
            if len(parts) >= 3:
                published = f"{parts[0]}-{parts[1]:02d}-{parts[2]:02d}"
            elif len(parts) == 2:
                published = f"{parts[0]}-{parts[1]:02d}-01"
            elif len(parts) == 1:
                published = f"{parts[0]}-01-01"

    if "updated" in item:
        updated = item["updated"][:10] if len(item["updated"]) >= 10 else item["updated"]

    return published, updated


@dataclass(frozen=True)
class PaperRecord:
    paper_id: str
    title: str
    summary: str
    authors: list[str]
    categories: list[str]
    primary_category: str
    published: str
    updated: str
    abs_url: str
    pdf_url: str
    comment: str


def parse_crossref_payload(payload: dict) -> list[PaperRecord]:
    """Parse Crossref payload thanh list PaperRecord.

    Args:
        payload: JSON response tu Crossref API.

    Returns:
        List cac PaperRecord hop le.
    """
    records = []
    items = payload.get("message", {}).get("items", [])

    for item in items:
        doi = _normalize_text(item.get("DOI", ""))
        titles = item.get("title", [])
        title = _normalize_text(titles[0] if titles else "")

        if not doi or not title:
            logger.warning(f"Bo qua record thieu DOI hoac title: DOI={doi}")
            continue

        abstract = _normalize_text(item.get("abstract", ""))
        authors = _extract_authors(item.get("author", []))
        subjects = [_normalize_text(s) for s in item.get("subject", [])]
        primary_category = subjects[0] if subjects else ""
        published, updated = _extract_date(item)
        abs_url, pdf_url = _extract_urls(item)
        comment = _normalize_text(item.get("comment", ""))

        paper_id = _generate_paper_id(doi, title)

        record = PaperRecord(
            paper_id=paper_id,
            title=title,
            summary=abstract,
            authors=authors,
            categories=subjects,
            primary_category=primary_category,
            published=published,
            updated=updated,
            abs_url=abs_url,
            pdf_url=pdf_url,
            comment=comment,
        )
        records.append(record)

    logger.info(f"Parsed {len(records)} records tu {len(items)} items")
    return records


def _build_api_url(settings: Settings) -> str:
    """Xay dung URL cho Crossref API query."""
    params = {
        "query": settings.source_query,
        "filter": settings.source_filter,
        "rows": settings.max_results,
        "mailto": "data-pipeline@example.com",
    }
    return f"{CROSSREF_API_BASE}?{urlencode(params)}"


def _call_api_with_retry(url: str, max_retries: int = 3, backoff_base: float = 2.0) -> dict:
    """Goi Crossref API voi retry exponential backoff cho 429/503.

    Args:
        url: API endpoint URL.
        max_retries: So lan retry toi da.
        backoff_base: Base cho exponential backoff (giay).

    Returns:
        JSON response tu API.

    Raises:
        requests.HTTPError: Neu tat ca retries deu that bai.
    """
    for attempt in range(max_retries):
        try:
            response = requests.get(url, timeout=30)
            status = response.status_code

            if status == 200:
                return response.json()

            if status in (429, 503):
                retry_after = response.headers.get("Retry-After")
                wait_time = int(retry_after) if retry_after and retry_after.isdigit() else backoff_base ** attempt
                logger.warning(f"API returned {status}, retrying in {wait_time:.1f}s (attempt {attempt + 1}/{max_retries})")
                time.sleep(wait_time)
                continue

            response.raise_for_status()

        except requests.RequestException as e:
            if attempt < max_retries - 1:
                wait_time = backoff_base ** attempt
                logger.warning(f"Request failed: {e}, retrying in {wait_time:.1f}s")
                time.sleep(wait_time)
                continue
            raise

    raise RuntimeError(f"API call failed after {max_retries} attempts")


def fetch_source_records(settings: Settings) -> list[PaperRecord]:
    """Goi Crossref API, luu raw response, parse thanh records.

    Args:
        settings: Cau hinh pipeline.

    Returns:
        List PaperRecord tu Crossref.
    """
    url = _build_api_url(settings)
    logger.info(f"Fetching from Crossref: {url[:100]}...")

    raw_response = _call_api_with_retry(url)

    settings.paths.raw_api_response.parent.mkdir(parents=True, exist_ok=True)
    with open(settings.paths.raw_api_response, "w", encoding="utf-8") as f:
        json.dump(raw_response, f, ensure_ascii=False, indent=2)
    logger.info(f"Saved raw API response to {settings.paths.raw_api_response}")

    records = parse_crossref_payload(raw_response)

    settings.paths.raw_records_json.parent.mkdir(parents=True, exist_ok=True)
    records_data = [
        {
            "paper_id": r.paper_id,
            "title": r.title,
            "summary": r.summary,
            "authors": r.authors,
            "categories": r.categories,
            "primary_category": r.primary_category,
            "published": r.published,
            "updated": r.updated,
            "abs_url": r.abs_url,
            "pdf_url": r.pdf_url,
            "comment": r.comment,
        }
        for r in records
    ]
    with open(settings.paths.raw_records_json, "w", encoding="utf-8") as f:
        json.dump(records_data, f, ensure_ascii=False, indent=2)
    logger.info(f"Saved {len(records)} records to {settings.paths.raw_records_json}")

    return records


def load_raw_records(path: Path) -> list[PaperRecord]:
    """Doc JSON snapshot va map thanh PaperRecord.

    Args:
        path: Duong dan toi file JSON chua records.

    Returns:
        List PaperRecord tu file.
    """
    if not path.exists():
        raise FileNotFoundError(f"Raw records file not found: {path}")

    with open(path, encoding="utf-8") as f:
        records_data = json.load(f)

    records = []
    for data in records_data:
        record = PaperRecord(
            paper_id=data["paper_id"],
            title=data["title"],
            summary=data["summary"],
            authors=data["authors"],
            categories=data["categories"],
            primary_category=data["primary_category"],
            published=data["published"],
            updated=data["updated"],
            abs_url=data["abs_url"],
            pdf_url=data["pdf_url"],
            comment=data["comment"],
        )
        records.append(record)

    logger.info(f"Loaded {len(records)} records from {path}")
    return records


# =============================================================================
# Checkpoint 2: Validation & Audit for Cleaning Handoff
# =============================================================================


@dataclass(frozen=True)
class ValidationIssue:
    """The hieu mot van de phat hien khi validate raw records."""
    record_idx: int
    doi: str
    paper_id: str
    field: str
    issue_type: str
    message: str


@dataclass(frozen=True)
class AuditReport:
    """Bao cao audit cho raw records, dung de bàn giao cho cleaning."""
    total_records: int
    valid_records: int
    records_with_issues: int
    issues: list[ValidationIssue]
    sample_records: list[PaperRecord]
    raw_path: Path
    record_path: Path


def validate_raw_records(records: list[PaperRecord]) -> tuple[list[PaperRecord], list[ValidationIssue]]:
    """Doi chieu raw records, phat hien DOI/ID loi va cac van de khac.

    Args:
        records: List PaperRecord da parse tu Crossref.

    Returns:
        Tuple (valid_records, issues). valid_records la records hop le,
        issues la danh sach cac van de phat hien.
    """
    issues = []
    valid_records = []

    seen_paper_ids: dict[str, int] = {}
    seen_DOIs: dict[str, int] = {}

    for idx, record in enumerate(records):
        record_issues = []

        # Check DOI ton tai va hop le
        if not record.abs_url:
            record_issues.append(ValidationIssue(
                record_idx=idx,
                doi=record.abs_url,
                paper_id=record.paper_id,
                field="abs_url",
                issue_type="MISSING_URL",
                message="Record khong co DOI/URL",
            ))

        # Check title
        if not record.title or len(record.title) < 5:
            record_issues.append(ValidationIssue(
                record_idx=idx,
                doi=record.abs_url,
                paper_id=record.paper_id,
                field="title",
                issue_type="INVALID_TITLE",
                message=f"Title qua ngan hoac rong: '{record.title[:50] if record.title else ''}'",
            ))

        # Check duplicate paper_id
        if record.paper_id in seen_paper_ids:
            first_idx = seen_paper_ids[record.paper_id]
            record_issues.append(ValidationIssue(
                record_idx=idx,
                doi=record.abs_url,
                paper_id=record.paper_id,
                field="paper_id",
                issue_type="DUPLICATE_ID",
                message=f"Duplicate paper_id voi record o index {first_idx}",
            ))
        else:
            seen_paper_ids[record.paper_id] = idx

        # Check duplicate DOI (qua URL)
        if record.abs_url and record.abs_url in seen_DOIs:
            first_idx = seen_DOIs[record.abs_url]
            record_issues.append(ValidationIssue(
                record_idx=idx,
                doi=record.abs_url,
                paper_id=record.paper_id,
                field="abs_url",
                issue_type="DUPLICATE_DOI",
                message=f"Duplicate DOI voi record o index {first_idx}",
            ))
        elif record.abs_url:
            seen_DOIs[record.abs_url] = idx

        # Check date formats
        if record.published:
            # Check neu khong phai YYYY-MM-DD
            date_parts = record.published.split("-")
            if len(date_parts) != 3 or len(date_parts[0]) != 4 or len(date_parts[1]) != 2 or len(date_parts[2]) != 2:
                record_issues.append(ValidationIssue(
                    record_idx=idx,
                    doi=record.abs_url,
                    paper_id=record.paper_id,
                    field="published",
                    issue_type="INVALID_DATE",
                    message=f"Published date khong dung format (YYYY-MM-DD): '{record.published}'",
                ))

        # Check authors
        if not record.authors:
            record_issues.append(ValidationIssue(
                record_idx=idx,
                doi=record.abs_url,
                paper_id=record.paper_id,
                field="authors",
                issue_type="MISSING_AUTHORS",
                message="Record khong co thong tin tac gia",
            ))

        if record_issues:
            issues.extend(record_issues)
        else:
            valid_records.append(record)

    return valid_records, issues


REQUIRED_FIELDS_FOR_CLEANING = [
    "paper_id",
    "title",
    "summary",
    "authors",
    "categories",
    "primary_category",
    "published",
    "updated",
    "abs_url",
]


def verify_field_completeness(records: list[PaperRecord]) -> dict[str, int]:
    """Xac minh raw records co day du field de cleaning khong can doan.

    Returns:
        Dictionary mapping field_name -> so record co field nay.
    """
    field_counts = {field: 0 for field in REQUIRED_FIELDS_FOR_CLEANING}

    for record in records:
        for field in REQUIRED_FIELDS_FOR_CLEANING:
            value = getattr(record, field, None)
            if value is not None:
                if isinstance(value, str):
                    field_counts[field] += 1 if value else 0
                elif isinstance(value, list):
                    field_counts[field] += 1 if value else 0
                else:
                    field_counts[field] += 1

    return field_counts


def generate_audit_report(
    records: list[PaperRecord],
    raw_path: Path,
    record_path: Path,
    max_samples: int = 3,
) -> AuditReport:
    """Tao bao cao audit de ban giao cho cleaning team.

    Args:
        records: List PaperRecord.
        raw_path: Duong dan toi raw API response.
        record_path: Duong dan toi parsed records JSON.
        max_samples: So luong sample records trong bao cao.

    Returns:
        AuditReport chua thong tin day du de bàn giao.
    """
    valid_records, issues = validate_raw_records(records)
    field_counts = verify_field_completeness(records)

    # Lay mau records dai dien
    sample_records = records[:max_samples]

    report = AuditReport(
        total_records=len(records),
        valid_records=len(valid_records),
        records_with_issues=len(records) - len(valid_records),
        issues=issues,
        sample_records=sample_records,
        raw_path=raw_path,
        record_path=record_path,
    )

    logger.info(f"Audit report: {len(valid_records)}/{len(records)} records valid, "
                f"{len(issues)} issues found")
    for field, count in field_counts.items():
        coverage = (count / len(records) * 100) if records else 0
        logger.info(f"  {field}: {count}/{len(records)} ({coverage:.1f}%)")

    return report


def print_audit_summary(report: AuditReport) -> None:
    """In tom tat audit report ra console."""
    print("\n" + "=" * 60)
    print("CROSSREF INGESTION - AUDIT REPORT")
    print("=" * 60)
    print(f"\nTotal Records: {report.total_records}")
    print(f"Valid Records: {report.valid_records}")
    print(f"Records with Issues: {report.records_with_issues}")
    print(f"\n--- Field Coverage ---")
    for field in REQUIRED_FIELDS_FOR_CLEANING:
        print(f"  {field}: available")

    print(f"\n--- Sample Records (for cleaning team) ---")
    for i, rec in enumerate(report.sample_records):
        print(f"\n  Sample {i + 1}:")
        print(f"    paper_id: {rec.paper_id}")
        print(f"    title: {rec.title[:80]}..." if len(rec.title) > 80 else f"    title: {rec.title}")
        print(f"    authors: {', '.join(rec.authors[:3])}{'...' if len(rec.authors) > 3 else ''}")
        print(f"    published: {rec.published}")
        print(f"    abs_url: {rec.abs_url}")

    if report.issues:
        print(f"\n--- Issues Found ({len(report.issues)}) ---")
        for issue in report.issues[:10]:
            print(f"  [{issue.issue_type}] {issue.message}")
        if len(report.issues) > 10:
            print(f"  ... and {len(report.issues) - 10} more issues")

    print("\n--- Handoff Info for Cleaning Team ---")
    print(f"  Raw API Response: {report.raw_path}")
    print(f"  Parsed Records: {report.record_path}")
    print(f"\n  Records are ready for cleaning.build_clean_dataframe()")
    print("=" * 60 + "\n")


def run_validation_and_audit(settings: Settings) -> AuditReport:
    """Chay validation day du va tao audit report.

    Day la entry point cho checkpoint 2 - goi sau khi fetch_source_records.

    Args:
        settings: Cau hinh pipeline.

    Returns:
        AuditReport day du.
    """
    # Load records tu file (hoac fetch moi)
    if settings.paths.raw_records_json.exists():
        records = load_raw_records(settings.paths.raw_records_json)
    else:
        records = fetch_source_records(settings)

    report = generate_audit_report(
        records=records,
        raw_path=settings.paths.raw_api_response,
        record_path=settings.paths.raw_records_json,
    )

    print_audit_summary(report)

    return report
