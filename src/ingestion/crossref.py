from __future__ import annotations

import hashlib
import json
import logging
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from urllib.parse import urlencode

import requests

from core.config import Settings


logger = logging.getLogger(__name__)


CROSSREF_API_BASE = "https://api.crossref.org/works"


def _generate_paper_id(doi: str, title: str) -> str:
    """Tao stable paper_id tu DOI va title hash."""
    raw = f"{doi}|{title}".encode("utf-8")
    return hashlib.sha256(raw).hexdigest()[:16]


def _normalize_text(text: str | None) -> str:
    """Chuan hoa text: loai bo whitespace thua, tra ve empty string neu None."""
    if not text:
        return ""
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
