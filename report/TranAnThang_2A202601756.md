# Member Role Report — Day 10: Data Pipeline & Data Observability

> Mỗi thành viên trong nhóm tự hoàn thành mẫu này để báo cáo đúng vai trò, phần việc và mức hiểu của mình. Không sao chép nguyên báo cáo chung hoặc báo cáo của thành viên khác. Thay nội dung trong dấu `[ ]` và xóa các dòng hướng dẫn không cần thiết trước khi nộp.

## 1. Thông tin cá nhân

| Thông tin         | Nội dung                  |
| ------------------ | -------------------------- |
| Họ và tên       | Trần An Thắng           |
| MSSV               | 2A202601756                |
| Khóa/Lớp         | K4                        |
| Tên nhóm         | VuaTuat                  |
| Vai trò chính    | Data Ingestion & Validation |
| Repository         | K4_Day10_Data-Pipeline-Data-Observability-VuaTuat |
| Ngày hoàn thành | 2026-08-06                |

## 2. Vai trò và phạm vi công việc

### Phần việc sở hữu

| Module/deliverable | File/hàm phụ trách | Input nhận vào | Output bàn giao  | Trạng thái |
| ------------------ | --------------------- | ---------------- | ----------------- | -------------------------------------------- |
| Crossref Ingestion | `src/ingestion/crossref.py` | Crossref API JSON response | `PaperRecord` objects | Hoàn thành |
| Raw Data Parsing | `parse_crossref_payload()` | API JSON payload | List[PaperRecord] | Hoàn thành |
| API Fetch với Retry | `fetch_source_records()`, `_call_api_with_retry()` | Settings config | Raw JSON + parsed records | Hoàn thành |
| Validation & Audit | `validate_raw_records()`, `generate_audit_report()` | List[PaperRecord] | AuditReport, issues list | Hoàn thành |
| Field Completeness Check | `verify_field_completeness()` | List[PaperRecord] | Field coverage dict | Hoàn thành |

### Việc hỗ trợ ngoài phạm vi chính

| Hoạt động                         | Thành viên/module được hỗ trợ | Kết quả                    |
| ------------------------------------ | ------------------------------------ | ---------------------------- |
| Test contract cleaning | Module cleaning | `script/validate_clean_contract.py` chạy pass |

## 3. Kết quả theo vai trò

| Nhiệm vụ đã thực hiện | File/hàm/artifact liên quan | Kết quả bàn giao       | Cách xác minh         |
| --------------------------- | ----------------------------- | ------------------------- | ----------------------- |
| Fetch Crossref API | `src/ingestion/crossref.py::fetch_source_records()` | 24 records từ API | `script/run_phase1.py` output |
| Parse API response | `src/ingestion/crossref.py::parse_crossref_payload()` | List[PaperRecord] với 11 fields | Unit tests pass |
| Lưu raw response | API JSON → `data/raw/crossref_response.json` | 226.7 KB raw data | File exists |
| Lưu parsed records | Parse → `data/raw/crossref_records.json` | 24 records parsed | JSON schema valid |
| Validate records | `validate_raw_records()` | 24/24 valid, 9 warnings | Audit report generated |
| Generate audit report | `generate_audit_report()` | Coverage metrics, sample records | Console output verified |

**Output cụ thể:**
- Raw API Response: `data/raw/crossref_response.json` (226.7 KB)
- Parsed Records: `data/raw/crossref_records.json` (24 records)
- Audit Report với field coverage:
  - paper_id: 24/24 (100.0%)
  - title: 24/24 (100.0%)
  - summary: 24/24 (100.0%)
  - authors: 24/24 (100.0%)
  - categories: 15/24 (62.5%)
  - published: 24/24 (100.0%)
  - updated: 24/24 (100.0%)
  - abs_url: 24/24 (100.0%)

## 4. Giải thích phần kỹ thuật đã thực hiện

### Vấn đề cần giải quyết

Thu thập dữ liệu từ Crossref API với các yêu cầu:
1. Query papers theo từ khóa ("agentic retrieval augmented generation large language model")
2. Lọc chỉ lấy records có đầy đủ title và abstract
3. Retry khi gặp HTTP 429/503
4. Lưu cả raw response và parsed records
5. Validation trước khi bàn giao cho cleaning

### Cách triển khai

**1. Stable Paper ID Generation:**
- SHA256 hash của `DOI|title` để tạo 16-character hex ID
- Đảm bảo cùng paper luôn tạo cùng ID

**2. API Call với Retry:**
- Exponential backoff: `wait = base ** attempt`
- Xử lý `Retry-After` header nếu có
- Retry cho 429 và 503 errors

**3. HTML Tag Stripping:**
- Regex `<[^>]+>` để loại bỏ HTML tags từ abstract
- Crossref trả về abstract với JATS XML format

**4. Date Extraction:**
- Ưu tiên `issued` field, fallback sang `published`
- Updated date từ `indexed.date-time`
- Format: YYYY-MM-DD

**5. Category Fallback:**
- Crossref không có `subject` field cho tất cả papers
- Fallback sang `container-title` (journal name) làm category

**6. Validation Logic:**
- Critical issues (missing DOI, invalid title, duplicates) → record bị loại
- Warnings (missing category) → record vẫn valid nhưng log warning

### Input, output và contract

| Thành phần                   | Mô tả                                     |
| ------------------------------ | ------------------------------------------- |
| Input                          | Crossref API JSON response (dict)         |
| Output                         | List[PaperRecord], AuditReport            |
| Module phụ thuộc             | `core.config.Settings`                    |
| Module sử dụng output        | `ingestion.cleaning`                      |
| Điều kiện lỗi cần xử lý | HTTP 429/503, missing fields, HTML tags, invalid dates |

### Cách xác minh

```bash
# Run phase1 pipeline (end-to-end)
PYTHONPATH=src python script/run_phase1.py

# Output: "Baseline complete: 24 clean records"
```

- **Kết quả mong đợi:** 24 records với đầy đủ 11 fields, valid dates
- **Kết quả thực tế:** 24 records, 100% field coverage trừ categories (62.5%)
- **Artifact/log:** `data/raw/crossref_records.json`, `data/reports/phase1_report.md`

## 5. Một quyết định kỹ thuật quan trọng

- **Bối cảnh:** Crossref API không có `subject` field cho 9/24 papers (37.5%). Nếu bỏ qua, cleaning pipeline sẽ nhận records với empty categories.

- **Các phương án đã cân nhắc:**
  1. Bỏ qua records không có subject → mất 37.5% data
  2. Gán "Unknown" cho category → cleaning phải xử lý
  3. Dùng journal name (container-title) làm fallback → giữ ngữ nghĩa

- **Phương án đã chọn:** Option 3 - Dùng `container-title` làm fallback category

- **Lý do:** Journal name mang ngữ nghĩa về domain của paper. Ví dụ: "Journal of AI Analytics and Applications" cho biết paper thuộc lĩnh vực AI. Dùng "unknown" không có giá trị thông tin.

- **Bằng chứng quyết định phù hợp:** 15/24 papers có categories từ subject hoặc container-title. 9 papers dùng container-title fallback, vẫn có thông tin về domain.

## 6. Một lỗi hoặc blocker đã xử lý

- **Triệu chứng/lỗi nguyên văn:**
  ```
  AssertionError: assert r1.summary == "This is a test abstract."
  ```

- **Lệnh hoặc bước tái hiện:**
  ```bash
  python test_crossref.py
  # Test fail: abstract có HTML tags <p>...</p>
  ```

- **Nguyên nhân gốc:** Crossref trả về abstract với JATS XML format `<p>This is a test abstract.</p>`. Hàm `_normalize_text()` chưa strip HTML tags.

- **Cách xử lý:**
  ```python
  # Thêm regex để strip HTML
  _HTML_TAG_RE = re.compile(r"<[^>]+>")
  
  def _strip_html(text: str) -> str:
      return _HTML_TAG_RE.sub("", text)
  
  def _normalize_text(text: str | None) -> str:
      if not text:
          return ""
      text = _strip_html(text)
      return " ".join(text.split())
  ```

- **Cách xác minh sau khi sửa:**
  ```bash
  python test_crossref.py
  # ✓ parse_crossref_payload tests passed!
  ```

- **Điều học được:** Luôn luôn strip HTML/XML tags khi parse text từ external APIs, đặc biệt là Crossref sử dụng JATS format.

## 7. Hiểu biết về luồng end-to-end

Giải thích ngắn gọn bằng lời của bạn:

1. **Dữ liệu đi từ Crossref đến vector index như thế nào?**
   Crossref API → Raw JSON (`data/raw/crossref_response.json`) → Parse to PaperRecord (`data/raw/crossref_records.json`) → Validate → Clean to DataFrame (`data/clean/papers_clean.csv`) → Embed text_for_embedding với MiniLM → Store in ChromaDB collection `papers-baseline`.

2. **Evaluation set và ground-truth document IDs dùng để đo retrieval/answer quality ra sao?**
   Test set (`data/eval/test_set.json`) chứa 10 questions, mỗi question có query và expected paper_id (ground-truth). Khi RAG agent query, vector search trả về top-k documents từ Chroma. So sánh retrieved IDs với ground-truth để tính hit_rate (q có match không), token F1 (answer overlap), judge_score (LLM judge).

3. **Quality checks khác freshness monitoring ở điểm nào trong bài lab?**
   - **Quality checks** (10 checks): đo lường structural data quality (missing fields, duplicates, NaN, text length)
   - **Freshness monitoring**: đo lường temporal data quality (age_days > threshold, oldest_published date)
   - Cả hai đều là signals trong observability, xuất hiện trong `data/reports/phase1_report.md` (section Observability) và `data/reports/corruption_report.md` (section 4).

4. **Vì sao phải dùng cùng test set cho baseline, corrupted và repaired?**
   Để đảm bảo comparison fair và có ý nghĩa. Nếu dùng test sets khác nhau, không thể biết metric changes là do corruption/repair hay do test set differences. Frozen test set đảm bảo cùng 10 questions được hỏi trên cả 3 states.

5. **Repair được xem là thành công dựa trên artifact và metric nào?**
   - **Artifacts**: `data/clean/papers_clean_repaired.csv` (24 rows, identical paper_id set với baseline), `data/reports/corruption_report.md`
   - **Metrics phục hồi**: retrieval_hit_rate = 0.8 (baseline), mean_token_f1 = 0.4821, judge_accuracy = 0.5, mean_judge_score = 2.8
   - **Quality signals phục hồi**: quality status PASS, is_fresh True, stale_rows = 0

## 8. Phân tích kết quả

### Metrics chính

| Metric/signal          | Baseline | Corrupted | Repaired | Nhận xét của cá nhân |
| ---------------------- | -------: | --------: | -------: | ------------------------- |
| `retrieval_hit_rate` | 0.8000 | 0.8000 | 0.8000 | Không thay đổi - top_k=4 / 24 docs vẫn tìm được paper dù summary bị corrupt |
| `mean_token_f1`      | 0.4821 | 0.3035 | 0.4821 | Degrade -37.1%, phục hồi hoàn toàn sau repair |
| `judge_accuracy`     | 0.5000 | 0.3000 | 0.5000 | Degrade -40.0%, phục hồi hoàn toàn |
| `mean_judge_score`   | 2.8000 | 2.2000 | 2.8000 | Degrade -21.4%, phục hồi hoàn toàn |
| Quality checks         | 10/10 PASS | FAIL (3 checks) | 10/10 PASS | paper_id_unique, summary_min_length, freshness_age_days fail khi corrupt |
| Freshness status       | is_fresh=True | is_fresh=False | is_fresh=True | stale_rows: 0 → 4 → 0 (4 records bị set published=2000-01-01) |

### Kết luận từ số liệu

**Chuỗi 1: Data corruption → quality/freshness signal thay đổi → agent metric thay đổi**
- Corruption scenarios (drop_latest_record, blank_summary, inject_summary_noise, duplicate_record, truncate_title, stale_published_date) → quality status FAIL (paper_id_unique fail do duplicate, summary_min_length fail do blank, freshness_age_days fail do stale dates), is_fresh=False, stale_rows=4
- → Agent metrics: mean_token_f1 0.4821 → 0.3035, judge_accuracy 0.5 → 0.3, mean_judge_score 2.8 → 2.2

**Chuỗi 2: Repair action → quality/freshness signal phục hồi → agent metric phục hồi**
- Repair (rebuild from `data/raw/crossref_records.json`) → quality status PASS (10/10 checks), is_fresh=True, stale_rows=0
- → Agent metrics phục hồi: mean_token_f1 0.4821, judge_accuracy 0.5, mean_judge_score 2.8

**Corruption nào ảnh hưởng rõ nhất và vì sao?**
- `stale_published_date` (4 records) và `inject_summary_noise` (4 records) có impact lớn nhất. 
- Lý do: stale dates trip freshness monitor và corrupt answer của date-questions; noise trong summary đẩy document ra khỏi embedding space của question, làm giảm F1 từ 0.82 → 0.04 (q4).

**Kết quả nào khác với kỳ vọng ban đầu?**
- `retrieval_hit_rate` không thay đổi (0.8 cả 3 states). Kỳ vọng ban đầu là hit_rate sẽ giảm khi corrupt. Thực tế: với top_k=4 / 24 docs, kể cả khi summary bị blank, title vẫn match với query nên hit_rate giữ nguyên. q7 thậm chí flip từ MISS → hit (shorter embedding text raises title similarity).

## 9. Điều học được và hướng cải thiện

### Ba điều quan trọng nhất

1. **Luôn strip HTML/XML tags khi parse text từ external APIs.** Crossref và nhiều APIs trả về structured markup cần được clean trước khi sử dụng.

2. **Validation nên phân biệt critical errors và warnings.** Records với warnings vẫn có thể sử dụng được nếu core fields đầy đủ.

3. **Frozen test set là thiết yếu cho controlled comparison.** Cùng test set đảm bảo metric changes là do data changes, không phải do test set randomness.

4. **Repair provenance quan trọng.** Repaired dataset phải rebuild từ raw snapshot (frozen tại C2), không đọc lại corrupted CSV. Đảm bảo reproducibility và tránh circular dependency.

### Nếu có thêm thời gian

Cải thiện category extraction bằng cách:
- Query Crossref subject API endpoint riêng
- Hoặc dùng LLM để classify papers từ title/summary
- Metric: Category coverage target ≥ 90% (hiện tại 62.5%)

## 10. Cam kết của thành viên

Đánh dấu sau khi tự kiểm tra:

- [x] Nội dung báo cáo phản ánh đúng phần việc và mức hiểu của tôi.
- [x] Tôi có thể giải thích luồng end-to-end, không chỉ module mình phụ trách.
- [x] Mọi kết luận về kết quả đều có artifact hoặc metric để đối chiếu.
- [x] Tôi không ghi "đã chạy thành công" cho phần chưa được kiểm chứng.
- [x] Báo cáo không chứa `.env`, API key, token hoặc secret.
- [x] Báo cáo này không phải bản sao nguyên văn của báo cáo nhóm hoặc báo cáo thành viên khác.

**Họ và tên:** Trần An Thắng
**Ngày xác nhận:** 2026-08-06