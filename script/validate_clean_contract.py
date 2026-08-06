"""Sample validation raw -> clean cho Checkpoint 0/1.

Chay 6 record edge case qua `build_clean_dataframe` va assert toan bo clean
schema contract (xem docs/clean_schema_contract.md).

Khong can mang, khong can API key, khong can Crossref -> chay duoc ngay ca khi
Source owner chua fetch xong du lieu that.

Usage:
    python script/validate_clean_contract.py

Exit code:
    0 = contract dat
    1 = co check fail
    2 = build_clean_dataframe chua implement (trang thai mong doi tai CP0)
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from pathlib import Path
import sys
import tempfile

# Cho phep chay truoc khi `pip install -e .`
_SRC = Path(__file__).resolve().parents[1] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

import pandas as pd

from ingestion.cleaning import build_clean_dataframe
from ingestion.crossref import PaperRecord

try:  # console Windows mac dinh cp1252
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # pragma: no cover
    pass


# --------------------------------------------------------------------------
# Contract (dong bo voi docs/clean_schema_contract.md)
# --------------------------------------------------------------------------

RUN_DATE = datetime(2026, 8, 6, tzinfo=UTC)
MIN_SUMMARY_CHARS = 100
FRESHNESS_THRESHOLD_DAYS = 180
PLACEHOLDER = "unknown"

# 9 cot ma LocalEmbeddingIndex._build_documents() doc truc tiep -> thieu la KeyError
INDEX_REQUIRED_COLUMNS = [
    "paper_id",
    "title",
    "text_for_embedding",
    "summary",
    "authors_joined",
    "categories_joined",
    "published",
    "abs_url",
    "pdf_url",
]

REQUIRED_COLUMNS = [
    "paper_id",
    "title",
    "summary",
    "authors_joined",
    "categories_joined",
    "primary_category",
    "published",
    "updated",
    "age_days",
    "summary_chars",
    "abs_url",
    "pdf_url",
    "comment",
    "text_for_embedding",
]

NON_EMPTY_COLUMNS = [
    "paper_id",
    "title",
    "summary",
    "authors_joined",
    "categories_joined",
    "primary_category",
    "published",
    "abs_url",
    "text_for_embedding",
]

# updated / pdf_url / comment duoc phep rong -> moi noi doc lai CSV phai dung
# pd.read_csv(..., keep_default_na=False)
ALLOWED_EMPTY_COLUMNS = ["updated", "pdf_url", "comment"]


# --------------------------------------------------------------------------
# Sample records: 6 edge case
# --------------------------------------------------------------------------

R1_CLEAN = PaperRecord(
    paper_id="10.1145/3701234.3701290",
    title="Agentic Retrieval Augmented Generation for Scientific Literature",
    summary=(
        "We present an agentic RAG system that plans multi-step retrieval over scholarly "
        "corpora. The agent decomposes questions, issues targeted searches, and verifies "
        "citations before answering."
    ),
    authors=["Mai Anh Nguyen", "Tomas Novak"],
    categories=["Information Retrieval", "Artificial Intelligence"],
    primary_category="Information Retrieval",
    published="2026-05-14",
    updated="2026-05-20",
    abs_url="https://doi.org/10.1145/3701234.3701290",
    pdf_url="https://example.org/papers/3701290.pdf",
    comment="12 pages, 4 figures",
)

# Edge case: abstract chua JATS XML + whitespace ban + author rong
R2_JATS = PaperRecord(
    paper_id="10.1162/tacl_a_00721",
    title="  Evaluating   Retrieval Quality\nunder Corpus Drift  ",
    summary=(
        "<jats:p>Retrieval quality degrades when the indexed corpus drifts away from the "
        "query distribution. <jats:italic>We quantify</jats:italic> this effect on four "
        "public benchmarks and report the failure modes.</jats:p>"
    ),
    authors=["  Lan   Pham  ", "", "Wei Zhang"],
    categories=["Computation and Language"],
    primary_category="Computation and Language",
    published="2026-03-02",
    updated="",
    abs_url="https://doi.org/10.1162/tacl_a_00721",
    pdf_url="",
    comment="",
)

# Edge case: date thieu ngay (date-parts [[2026, 1]]) + khong co categories
# -> phai song sot, pad ve 2026-01-01, categories/primary_category = "unknown"
# -> age_days > 180 nen day cung la sample "stale" cho freshness report
R3_PARTIAL_DATE = PaperRecord(
    paper_id="10.48550/arxiv.2601.01234",
    title="Data Quality Signals for Production RAG Systems",
    summary=(
        "Production RAG systems fail silently when upstream data quality drops. We propose "
        "a small set of freshness and completeness signals that predict downstream answer "
        "quality before users notice."
    ),
    authors=["Duc Ta"],
    categories=[],
    primary_category="",
    published="2026-01",
    updated="",
    abs_url="https://doi.org/10.48550/arxiv.2601.01234",
    pdf_url="",
    comment="",
)

# Edge case: duplicate cua R2, DOI viet hoa + con prefix URL -> phai bi dedupe
R4_DUPLICATE = PaperRecord(
    paper_id="HTTPS://DOI.ORG/10.1162/TACL_A_00721",
    title="Evaluating Retrieval Quality under Corpus Drift",
    summary=(
        "Retrieval quality degrades when the indexed corpus drifts away from the query "
        "distribution. We quantify this effect on four public benchmarks and report the "
        "failure modes observed."
    ),
    authors=["Lan Pham", "Wei Zhang"],
    categories=["Computation and Language"],
    primary_category="Computation and Language",
    published="2026-03-02",
    updated="",
    abs_url="https://doi.org/10.1162/tacl_a_00721",
    pdf_url="",
    comment="duplicate record from a second Crossref page",
)

# Edge case: summary rong -> phai bi drop
R5_EMPTY_SUMMARY = PaperRecord(
    paper_id="10.1109/tkde.2026.3312345",
    title="A Survey of Vector Databases",
    summary="   ",
    authors=["Anna Meyer"],
    categories=["Databases"],
    primary_category="Databases",
    published="2026-04-01",
    updated="",
    abs_url="https://doi.org/10.1109/tkde.2026.3312345",
    pdf_url="",
    comment="",
)

# Edge case: title rong -> phai bi drop (khong lookup duoc theo title)
R6_EMPTY_TITLE = PaperRecord(
    paper_id="10.1016/j.ipm.2026.103812",
    title="",
    summary=(
        "An extended abstract about hybrid sparse-dense search that lacks a usable title in "
        "the source metadata, which makes the record unusable for exact title lookup."
    ),
    authors=["Hoang Le"],
    categories=["Information Retrieval"],
    primary_category="Information Retrieval",
    published="2026-02-11",
    updated="",
    abs_url="https://doi.org/10.1016/j.ipm.2026.103812",
    pdf_url="",
    comment="",
)

SAMPLE_RECORDS = [
    R1_CLEAN,
    R2_JATS,
    R3_PARTIAL_DATE,
    R4_DUPLICATE,
    R5_EMPTY_SUMMARY,
    R6_EMPTY_TITLE,
]

# R4 bi dedupe vao R2; R5/R6 bi drop -> con lai 3, sort published giam dan
EXPECTED_PAPER_IDS = [
    "10.1145/3701234.3701290",  # 2026-05-14
    "10.1162/tacl_a_00721",  # 2026-03-02
    "10.48550/arxiv.2601.01234",  # 2026-01-01 (pad tu "2026-01")
]
EXPECTED_PUBLISHED = ["2026-05-14", "2026-03-02", "2026-01-01"]


# --------------------------------------------------------------------------
# Runner
# --------------------------------------------------------------------------


class Report:
    def __init__(self) -> None:
        self.rows: list[tuple[bool, str, str]] = []

    def check(self, name: str, ok: bool, detail: str = "") -> bool:
        self.rows.append((bool(ok), name, detail))
        return bool(ok)

    @property
    def failed(self) -> int:
        return sum(1 for ok, _, _ in self.rows if not ok)

    def render(self) -> None:
        for ok, name, detail in self.rows:
            mark = "PASS" if ok else "FAIL"
            line = f"  [{mark}] {name}"
            if detail and not ok:
                line += f"\n         -> {detail}"
            print(line)
        total = len(self.rows)
        print("-" * 72)
        print(f"  {total - self.failed}/{total} check dat, {self.failed} fail")


def _is_scalar_column(series: pd.Series) -> bool:
    return not any(isinstance(value, (list, dict, set, tuple)) for value in series)


def validate(df: pd.DataFrame) -> Report:
    report = Report()

    # --- 1. Kieu tra ve va cot ---------------------------------------------
    if not report.check("tra ve pandas DataFrame", isinstance(df, pd.DataFrame), f"nhan duoc {type(df)!r}"):
        return report

    missing_index = [c for c in INDEX_REQUIRED_COLUMNS if c not in df.columns]
    report.check(
        "du 9 cot hard-contract cua _build_documents()",
        not missing_index,
        f"thieu: {missing_index} -> se KeyError khi build index",
    )

    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    report.check("du 14 cot theo contract", not missing, f"thieu: {missing}")

    extra = [c for c in df.columns if c not in REQUIRED_COLUMNS]
    report.check("khong co cot thua ngoai contract", not extra, f"thua: {extra}")

    if missing:
        return report

    # --- 2. Loc / dedupe ----------------------------------------------------
    report.check(
        "loc dung so record (3 song sot / 6 input)",
        len(df) == 3,
        f"co {len(df)} dong, ky vong 3 (R4 dedupe, R5 summary rong, R6 title rong bi drop)",
    )

    report.check("paper_id unique", df["paper_id"].is_unique, "con duplicate sau dedupe")

    ids = list(df["paper_id"])
    report.check(
        "dung tap paper_id song sot",
        sorted(ids) == sorted(EXPECTED_PAPER_IDS),
        f"nhan duoc {sorted(ids)}\n            ky vong {sorted(EXPECTED_PAPER_IDS)}",
    )

    # --- 3. Normalize paper_id ---------------------------------------------
    report.check(
        "paper_id lowercase",
        all(pid == pid.lower() for pid in ids),
        f"con chu hoa: {[p for p in ids if p != p.lower()]} -> retrieval_hit_rate se = 0 mot cach am tham",
    )
    report.check(
        "paper_id da bo prefix doi.org",
        not any("doi.org" in pid for pid in ids),
        f"con prefix: {[p for p in ids if 'doi.org' in p]}",
    )

    # --- 4. Khong NaN, khong list ------------------------------------------
    na_columns = [c for c in REQUIRED_COLUMNS if df[c].isna().any()]
    report.check(
        "khong co NaN o bat ky cot nao",
        not na_columns,
        f"cot co NaN: {na_columns} -> NaN la float, lot vao Chroma metadata se loi",
    )

    list_columns = [c for c in REQUIRED_COLUMNS if not _is_scalar_column(df[c])]
    report.check(
        "khong cot nao chua list/dict (Chroma chi nhan scalar)",
        not list_columns,
        f"cot khong scalar: {list_columns}",
    )

    empty_required = [c for c in NON_EMPTY_COLUMNS if (df[c].astype(str).str.strip() == "").any()]
    report.check(
        "cac cot bat buoc khong rong",
        not empty_required,
        f"cot co gia tri rong: {empty_required}",
    )

    # --- 5. Date + age_days -------------------------------------------------
    published = list(df["published"].astype(str))
    iso_ok = []
    for value in published:
        try:
            date.fromisoformat(value)
            iso_ok.append(True)
        except ValueError:
            iso_ok.append(False)
    report.check(
        "published dung ISO YYYY-MM-DD dang string",
        all(iso_ok),
        f"gia tri sai dinh dang: {[v for v, ok in zip(published, iso_ok) if not ok]}",
    )

    partial = df.loc[df["paper_id"] == "10.48550/arxiv.2601.01234", "published"]
    report.check(
        "date thieu ngay duoc pad ve mung 1 ('2026-01' -> '2026-01-01')",
        len(partial) == 1 and str(partial.iloc[0]) == "2026-01-01",
        f"nhan duoc {list(partial)}",
    )

    if all(iso_ok):
        expected_age = [(RUN_DATE.date() - date.fromisoformat(v)).days for v in published]
        actual_age = [int(v) for v in df["age_days"]]
        report.check(
            "age_days khop (run_date - published)",
            expected_age == actual_age,
            f"nhan duoc {actual_age}, ky vong {expected_age}",
        )
        report.check("age_days >= 0", all(v >= 0 for v in actual_age), f"co gia tri am: {actual_age}")

    # --- 6. Sort ------------------------------------------------------------
    report.check(
        "sort theo published giam dan (moi nhat truoc)",
        published == EXPECTED_PUBLISHED,
        f"thu tu hien tai {published}, ky vong {EXPECTED_PUBLISHED}"
        " -> corruption scenario 'xoa latest records' phu thuoc thu tu nay",
    )

    # --- 7. Text cleaning ---------------------------------------------------
    dirty_jats = [pid for pid, s in zip(ids, df["summary"].astype(str)) if "<jats" in s.lower() or "</" in s]
    report.check(
        "summary da strip JATS XML",
        not dirty_jats,
        f"con tag XML o: {dirty_jats}",
    )

    dirty_ws = [
        pid
        for pid, t in zip(ids, df["title"].astype(str))
        if "  " in t or "\n" in t or t != t.strip()
    ]
    report.check("title da normalize whitespace", not dirty_ws, f"con whitespace ban o: {dirty_ws}")

    short = [
        (pid, n) for pid, n in zip(ids, df["summary_chars"]) if int(n) < MIN_SUMMARY_CHARS
    ]
    report.check(
        f"moi summary >= {MIN_SUMMARY_CHARS} ky tu",
        not short,
        f"qua ngan: {short}",
    )

    chars_ok = all(
        int(n) == len(str(s)) for n, s in zip(df["summary_chars"], df["summary"])
    )
    report.check("summary_chars == len(summary)", chars_ok)

    # --- 8. Joined columns + fallback --------------------------------------
    r2 = df.loc[df["paper_id"] == "10.1162/tacl_a_00721"]
    if len(r2) == 1:
        authors = str(r2["authors_joined"].iloc[0])
        report.check(
            "authors_joined bo phan tu rong va normalize",
            authors == "Lan Pham, Wei Zhang",
            f"nhan duoc {authors!r}, ky vong 'Lan Pham, Wei Zhang'",
        )

    r3 = df.loc[df["paper_id"] == "10.48550/arxiv.2601.01234"]
    if len(r3) == 1:
        report.check(
            f"categories rong -> fallback '{PLACEHOLDER}' (khong drop record)",
            str(r3["categories_joined"].iloc[0]) == PLACEHOLDER,
            f"nhan duoc {r3['categories_joined'].iloc[0]!r}",
        )
        report.check(
            f"primary_category rong -> fallback '{PLACEHOLDER}'",
            str(r3["primary_category"].iloc[0]) == PLACEHOLDER,
            f"nhan duoc {r3['primary_category'].iloc[0]!r}",
        )

    # --- 9. text_for_embedding ---------------------------------------------
    missing_parts: list[str] = []
    for _, row in df.iterrows():
        text = str(row["text_for_embedding"])
        for field in ("title", "authors_joined", "categories_joined", "published", "summary"):
            if str(row[field]) not in text:
                missing_parts.append(f"{row['paper_id']}: thieu {field}")
    report.check(
        "text_for_embedding chua title + authors + categories + published + summary",
        not missing_parts,
        "; ".join(missing_parts) + " -> cau hoi 'who authored X' se khong match duoc document",
    )

    # --- 10. CSV round-trip (corruption flow doc lai file nay) --------------
    with tempfile.TemporaryDirectory() as tmp:
        csv_path = Path(tmp) / "papers_clean.csv"
        df.to_csv(csv_path, index=False)
        reloaded = pd.read_csv(csv_path, keep_default_na=False)

        report.check(
            "CSV round-trip giu nguyen so dong va so cot",
            reloaded.shape == df.shape,
            f"truoc {df.shape}, sau {reloaded.shape}",
        )

        drifted = [
            c
            for c in INDEX_REQUIRED_COLUMNS
            if list(df[c].astype(str)) != list(reloaded[c].astype(str))
        ]
        report.check(
            "CSV round-trip khong lam doi gia tri 9 cot hard-contract",
            not drifted,
            f"cot bi doi: {drifted}",
        )

        stringified = [
            c
            for c in reloaded.columns
            if reloaded[c].astype(str).str.startswith(("['", "[\"", "{'")).any()
        ]
        report.check(
            "khong cot nao bi CSV bien list thanh chuoi \"['a', 'b']\"",
            not stringified,
            f"cot bi stringify: {stringified}",
        )

        na_after = [c for c in reloaded.columns if reloaded[c].isna().any()]
        report.check(
            "doc lai bang keep_default_na=False khong sinh NaN",
            not na_after,
            f"cot NaN sau round-trip: {na_after}",
        )

    return report


def main() -> int:
    print("=" * 72)
    print("  VALIDATE CLEAN SCHEMA CONTRACT  (raw -> clean)")
    print(f"  run_date = {RUN_DATE.date().isoformat()}  |  {len(SAMPLE_RECORDS)} sample records")
    print("=" * 72)

    try:
        df = build_clean_dataframe(SAMPLE_RECORDS, RUN_DATE)
    except NotImplementedError as exc:
        print()
        print("  build_clean_dataframe chua duoc implement.")
        print(f"  -> {exc}")
        print()
        print("  Day la trang thai mong doi tai CP0. Hoan thanh")
        print("  src/ingestion/cleaning.py roi chay lai script nay o CP1.")
        print("=" * 72)
        return 2

    report = validate(df)
    print()
    report.render()
    print()

    if report.failed:
        print("  KET QUA: contract CHUA dat. Xem docs/clean_schema_contract.md.")
        print("=" * 72)
        return 1

    print("  KET QUA: contract DAT. Clean schema san sang cho build index.")
    stale = int((df["age_days"] > FRESHNESS_THRESHOLD_DAYS).sum())
    print(f"  (ghi chu: {stale}/{len(df)} record co age_days > {FRESHNESS_THRESHOLD_DAYS}"
          " -> sample nay co ca case stale cho freshness report)")
    print("=" * 72)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
