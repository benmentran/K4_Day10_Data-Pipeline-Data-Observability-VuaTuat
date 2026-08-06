"""Test script cho Crossref ingestion module."""
from __future__ import annotations

import json
import logging
import sys
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))


def test_parse_crossref_payload():
    """Test parse_crossref_payload voi mock payload."""
    from ingestion.crossref import parse_crossref_payload, PaperRecord, _generate_paper_id

    mock_payload = {
        "message": {
            "items": [
                {
                    "DOI": "10.1234/test.001",
                    "title": ["Test Paper Title"],
                    "abstract": "<p>This is a test abstract.</p>",
                    "author": [
                        {"given": "John", "family": "Doe"},
                        {"given": "Jane", "family": "Smith"},
                    ],
                    "subject": ["Computer Science", "Machine Learning"],
                    "published": {"date-parts": [[2024, 6, 15]]},
                    "indexed": {"date-time": "2024-06-20T10:00:00Z"},
                    "URL": "https://doi.org/10.1234/test.001",
                    "link": [
                        {
                            "URL": "https://example.com/test.pdf",
                            "content-type": "application/pdf",
                        }
                    ],
                    "comment": "Published at conference X",
                },
                {
                    "DOI": "10.1234/test.002",
                    "title": ["Another Test Paper"],
                    "abstract": None,
                    "author": [{"family": "Unknown"}],
                    "subject": ["Physics"],
                    "published": {"date-parts": [[2024]]},
                    "indexed": {"date-time": "2024-07-01T00:00:00Z"},
                    "URL": "https://doi.org/10.1234/test.002",
                    "link": [],
                },
            ]
        }
    }

    records = parse_crossref_payload(mock_payload)

    assert len(records) == 2, f"Expected 2 records, got {len(records)}"

    r1 = records[0]
    assert isinstance(r1, PaperRecord)
    assert r1.paper_id == _generate_paper_id("10.1234/test.001", "Test Paper Title")
    assert r1.title == "Test Paper Title"
    assert r1.summary == "This is a test abstract."
    assert r1.authors == ["John Doe", "Jane Smith"]
    assert r1.categories == ["Computer Science", "Machine Learning"]
    assert r1.primary_category == "Computer Science"
    assert r1.published == "2024-06-15"
    assert r1.updated == "2024-06-20"
    assert r1.abs_url == "https://doi.org/10.1234/test.001"
    assert r1.pdf_url == "https://example.com/test.pdf"
    assert r1.comment == "Published at conference X"

    r2 = records[1]
    assert r2.title == "Another Test Paper"
    assert r2.summary == ""
    assert r2.authors == ["Unknown"]
    assert r2.published == "2024-01-01"
    assert r2.updated == "2024-07-01"

    print("✓ parse_crossref_payload tests passed!")


def test_load_raw_records():
    """Test load_raw_records voi mock JSON file."""
    from ingestion.crossref import load_raw_records, PaperRecord

    test_file = PROJECT_ROOT / "data" / "raw" / "test_records.json"
    test_file.parent.mkdir(parents=True, exist_ok=True)

    mock_records = [
        {
            "paper_id": "abc123def456",
            "title": "Test Paper",
            "summary": "Test summary",
            "authors": ["Author One"],
            "categories": ["CS"],
            "primary_category": "CS",
            "published": "2024-01-01",
            "updated": "2024-01-02",
            "abs_url": "https://example.com",
            "pdf_url": "https://example.com/pdf",
            "comment": "Test comment",
        }
    ]

    with open(test_file, "w", encoding="utf-8") as f:
        json.dump(mock_records, f, ensure_ascii=False, indent=2)

    records = load_raw_records(test_file)

    assert len(records) == 1
    assert records[0].paper_id == "abc123def456"
    assert records[0].title == "Test Paper"

    test_file.unlink()
    print("✓ load_raw_records tests passed!")


def test_paper_id_stability():
    """Test stable paper_id generation."""
    from ingestion.crossref import _generate_paper_id

    id1 = _generate_paper_id("10.1234/test", "Title A")
    id2 = _generate_paper_id("10.1234/test", "Title A")
    id3 = _generate_paper_id("10.1234/test", "Title B")

    assert id1 == id2, "Same DOI+Title should produce same ID"
    assert id1 != id3, "Different content should produce different ID"
    assert len(id1) == 16, "ID should be 16 characters"

    print("✓ paper_id stability tests passed!")


def test_crossref_api_call():
    """Test Crossref API call (neu co network)."""
    from ingestion.crossref import _build_api_url, CROSSREF_API_BASE

    class MockSettings:
        source_query = "machine learning"
        source_filter = "from-pub-date:2024-01-01"
        max_results = 5

    settings = MockSettings()
    url = _build_api_url(settings)

    assert CROSSREF_API_BASE in url
    assert "query=machine+learning" in url
    assert "rows=5" in url
    assert "filter=from-pub-date%3A2024-01-01" in url

    print("✓ API URL building tests passed!")


def test_field_validation():
    """Test validation: records phai co day du field cho cleaning."""
    from ingestion.crossref import parse_crossref_payload, PaperRecord

    payload = {
        "message": {
            "items": [
                {
                    "DOI": "10.1234/valid",
                    "title": ["Valid Paper"],
                    "abstract": "Abstract text",
                    "author": [{"given": "A", "family": "B"}],
                    "subject": ["Science"],
                    "published": {"date-parts": [[2024, 1, 1]]},
                    "updated": "2024-01-02",
                    "URL": "https://doi.org/10.1234/valid",
                }
            ]
        }
    }

    records = parse_crossref_payload(payload)
    r = records[0]

    required_for_cleaning = [
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

    for field in required_for_cleaning:
        value = getattr(r, field, None)
        assert value is not None, f"Field '{field}' should not be None"

    assert isinstance(r.paper_id, str) and len(r.paper_id) > 0
    assert isinstance(r.title, str) and len(r.title) > 0
    assert isinstance(r.authors, list)
    assert isinstance(r.categories, list)

    print("✓ field validation tests passed!")


def test_validation_and_audit():
    """Test validation, audit report, and cleaning handoff."""
    from ingestion.crossref import (
        validate_raw_records,
        verify_field_completeness,
        generate_audit_report,
        REQUIRED_FIELDS_FOR_CLEANING,
        PaperRecord,
    )

    # Mock records
    records = [
        PaperRecord(
            paper_id="abc123",
            title="Valid Paper Title",
            summary="Valid summary",
            authors=["Author One"],
            categories=["CS"],
            primary_category="CS",
            published="2024-01-01",
            updated="2024-01-02",
            abs_url="https://doi.org/10.1234/valid",
            pdf_url="https://example.com/valid.pdf",
            comment="",
        ),
        PaperRecord(
            paper_id="def456",
            title="Ab",  # Too short (< 5 chars)
            summary="",
            authors=[],  # No authors
            categories=[],
            primary_category="",
            published="2024",  # Wrong format
            updated="2024-01-02",
            abs_url="https://doi.org/10.1234/invalid",
            pdf_url="",
            comment="",
        ),
        PaperRecord(
            paper_id="ghi789",
            title="Another Paper",
            summary="Summary",
            authors=["Author Two"],
            categories=["Physics"],
            primary_category="Physics",
            published="2024-06-15",
            updated="2024-06-20",
            abs_url="https://doi.org/10.1234/another",
            pdf_url="",
            comment="",
        ),
    ]

    # Test validation
    valid, issues = validate_raw_records(records)
    assert len(valid) == 2, f"Expected 2 valid records, got {len(valid)}"
    # Record 2 has: short title, no authors, invalid date = 3 issues
    # Record 1 and 3 should be valid
    assert len(issues) >= 2, f"Expected at least 2 issues, got {len(issues)}"

    # Check issue types found
    issue_types = {issue.issue_type for issue in issues}
    assert "INVALID_TITLE" in issue_types
    assert "MISSING_AUTHORS" in issue_types
    # Check date issue was detected
    date_issues = [i for i in issues if i.issue_type == "INVALID_DATE"]
    assert len(date_issues) >= 1, "Should detect invalid date format"

    # Test field completeness
    field_counts = verify_field_completeness(records)
    assert "paper_id" in field_counts
    assert "title" in field_counts
    assert all(field in field_counts for field in REQUIRED_FIELDS_FOR_CLEANING)

    # Test audit report generation
    from pathlib import Path
    report = generate_audit_report(
        records=records,
        raw_path=Path("/fake/raw.json"),
        record_path=Path("/fake/records.json"),
        max_samples=2,
    )
    assert report.total_records == 3
    assert report.valid_records == 2
    assert report.records_with_issues == 1
    assert len(report.sample_records) == 2

    print("✓ validation_and_audit tests passed!")


if __name__ == "__main__":
    print("\n=== Testing Crossref Ingestion Module ===\n")

    test_paper_id_stability()
    test_parse_crossref_payload()
    test_load_raw_records()
    test_crossref_api_call()
    test_field_validation()
    test_validation_and_audit()

    print("\n=== All tests passed! ===")
