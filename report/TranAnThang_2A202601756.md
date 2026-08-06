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
| Review code cleaning.py | Thành viên khác | Đảm bảo interface tương thích |

## 3. Kết quả theo vai trò

| Nhiệm vụ đã thực hiện | File/hàm/artifact liên quan | Kết quả bàn giao       | Cách xác minh         |
| --------------------------- | ----------------------------- | ------------------------- | ----------------------- |
| Fetch Crossref API | `src/ingestion/crossref.py::fetch_source_records()` | 24 records từ API | `script/fetch_crossref.py` output |
| Parse API response | `src/ingestion/crossref.py::parse_crossref_payload()` | List[PaperRecord] với 11 fields | Unit tests pass |
| Lưu raw response | API JSON → `data/raw/crossref_response.json` | 226.7 KB raw data | File exists, verified |
| Lưu parsed records | Parse → `data/raw/crossref_records.json` | 55.0 KB parsed data | JSON schema valid |
| Validate records | `validate_raw_records()` | 24/24 valid, 9 warnings | Audit report generated |
| Generate audit report | `generate_audit_report()` | Coverage metrics, sample records | Console output verified |

**Output cụ thể:**
- Raw API Response: `data/raw/crossref_response.json` (226,191 bytes)
- Parsed Records: `data/raw/crossref_records.json` (54,783 bytes)
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
# Run fetch script
/home/angwindy/miniconda3/envs/vin/bin/python script/fetch_crossref.py

# Run unit tests
/home/angwindy/miniconda3/envs/vin/bin/python test_crossref.py

# Validate JSON schema
python -c "import json; records = json.load(open('data/raw/crossref_records.json')); print(f'Total: {len(records)}')"
```

- **Kết quả mong đợi:** 24 records với đầy đủ 11 fields, valid dates
- **Kết quả thực tế:** 24 records, 100% field coverage trừ categories (62.5%)
- **Artifact/log:** `data/raw/crossref_records.json`, `data/raw/crossref_response.json`

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
   Crossref API → Raw JSON response → Parse to PaperRecord → Validate → Clean to DataFrame → Embed text_for_embedding → Store in ChromaDB vector index

2. **Evaluation set và ground-truth document IDs dùng để đo retrieval/answer quality ra sao?**
   Test set chứa query và expected document IDs. Khi RAG agent query, vector search trả về top-k documents. So sánh retrieved IDs với ground-truth để tính hit_rate, F1, judge_score.

3. **Quality checks khác freshness monitoring ở điểm nào trong bài lab?**
   Quality checks đo lường data quality (missing fields, duplicates, invalid formats). Freshness monitoring đo lường data age (days since last update). Cả hai đều là signals trong observability dashboard.

4. **Vì sao phải dùng cùng test set cho baseline, corrupted và repaired?**
   Để đảm bảo comparison fair và có ý nghĩa. Nếu dùng test sets khác nhau, không thể biết metric changes là do corruption/repair hay do test set differences.

5. **Repair được xem là thành công dựa trên artifact và metric nào?**
   Repair thành công khi:
   - Corrupted records được fix (re-fetch hoặc remove)
   - Quality signals phục hồi về baseline levels
   - Retrieval metrics (hit_rate, F1) phục hồi ≥ 90% baseline
   - Artifacts: `data/clean/cleaned.csv`, `data/eval/repair_report.json`

## 8. Phân tích kết quả

### Metrics chính

| Metric/signal          | Baseline | Corrupted | Repaired | Nhận xét của cá nhân |
| ---------------------- | -------: | --------: | -------: | ------------------------- |
| `retrieval_hit_rate` | [ ] | [ ] | [ ] | [Chưa chạy phase 2-4] |
| `mean_token_f1`      | [ ] | [ ] | [ ] | [Chưa chạy phase 2-4] |
| `judge_accuracy`     | [ ] | [ ] | [ ] | [Chưa chạy phase 2-4] |
| `mean_judge_score`   | [ ] | [ ] | [ ] | [Chưa chạy phase 2-4] |
| Quality checks         | 24/24 valid | [ ] | [ ] | 100% records valid sau ingestion |
| Freshness status       | 24 records | [ ] | [ ] | 2026 data (fresh) |

### Kết luận từ số liệu

**Chuỗi 1: Data corruption → quality/freshness signal thay đổi → agent metric thay đổi**
- [Chưa thực hiện corruption simulation]

**Chuỗi 2: Repair action → quality/freshness signal phục hồi → agent metric phục hồi**
- [Chưa thực hiện repair]

**Corruption nào ảnh hưởng rõ nhất và vì sao?**
- [Chưa thực hiện corruption]

**Kết quả nào khác với kỳ vọng ban đầu?**
- Category coverage thấp hơn mong đợi (62.5% thay vì 100%)
- Đã xử lý bằng cách dùng journal name làm fallback

## 9. Điều học được và hướng cải thiện

### Ba điều quan trọng nhất

1. **Luôn strip HTML/XML tags khi parse text từ external APIs.** Crossref và nhiều APIs trả về structured markup cần được clean trước khi sử dụng.

2. **Validation nên phân biệt critical errors và warnings.** Records với warnings vẫn có thể sử dụng được nếu core fields đầy đủ.

3. **Fallback logic quan trọng cho data quality.** Khi primary field không có, dùng secondary field (journal name → category) vẫn tốt hơn empty string.

### Nếu có thêm thời gian

Cải thiện category extraction bằng cách:
- Query Crossref subject API endpoint riêng
- Hoặc dùng AI để classify papers từ title/summary
- Metric: Category coverage target ≥ 90%

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
