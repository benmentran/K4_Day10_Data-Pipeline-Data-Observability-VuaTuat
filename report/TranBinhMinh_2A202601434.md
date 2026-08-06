# Member Role Report — Day 10: Data Pipeline & Data Observability

## 1. Thông tin cá nhân

| Thông tin         | Nội dung                  |
| ------------------ | -------------------------- |
| Họ và tên       | Trần Bình Minh             |
| MSSV               | 2A202601434                |
| Khóa/Lớp         | K4                        |
| Tên nhóm         | VuaTuat                   |
| Vai trò chính    | Thành viên 2 — Cleaning & Data Modeling owner |
| Repository         | https://github.com/benmentran/K4_Day10_Data-Pipeline-Data-Observability-VuaTuat |
| Ngày hoàn thành | 2026-08-06                |

## 2. Vai trò và phạm vi công việc

### Phần việc sở hữu

| Module/deliverable | File/hàm phụ trách | Input nhận vào | Output bàn giao | Trạng thái |
| ------------------ | --------------------- | ---------------- | ----------------- | ------------ |
| Data cleaning | `src/ingestion/cleaning.py::build_clean_dataframe()` | `list[PaperRecord]` + `run_date` + `Settings` | `pandas.DataFrame` 14 cột | Hoàn thành |
| HTML/JATS stripping | `_strip_html_tags()` | Chuỗi abstract Crossref | Chuỗi đã bỏ tag XML/HTML | Hoàn thành |
| Date parsing & padding | `_parse_date()` | Crossref date string `YYYY-MM-DD`/`YYYY-MM`/`YYYY` | `datetime` UTC | Hoàn thành |
| DOI normalization | `_normalize_id()` | DOI/URL string | `paper_id` lowercase | Hoàn thành |
| `text_for_embedding` dựng | `build_clean_dataframe()` (block cuối vòng lặp) | title + authors + categories + published + summary | Chuỗi nhiều dòng cho MiniLM | Hoàn thành |
| Clean schema contract | `docs/clean_schema_contract.md` | Nguyên tắc từ PaperRecord + index.py | 14 cột, 6 rule cleaning, 4 ràng buộc kỹ thuật | Hoàn thành |
| Validator offline | `script/validate_clean_contract.py` | 6 record edge case | 29/29 check PASS, exit 0 | Hoàn thành |

### Việc hỗ trợ ngoài phạm vi chính

| Hoạt động | Thành viên/module được hỗ trợ | Kết quả |
| ------------ | ------------------------------------ | ---------- |
| Chốt ngưỡng `MIN_SUMMARY_CHARS = 100` dùng chung | Thành viên 3 (observability) | Ngưỡng cleaning và quality check trùng nhau; baseline 826 ký tự, corrupted 4 dòng FAIL |
| Chốt format `text_for_embedding` | Thành viên 3, 4 | `Title/Authors/Categories/Published/Summary` — qa trả lời được cả câu hỏi "who authored" lẫn "what categories" |
| Hỗ trợ xác minh repair | Thành viên 4 (corruption) | `corruption_flow.py` gọi lại `build_clean_dataframe()` từ raw snapshot → repaired dataset khớp baseline 24/24 dòng |

Tôi không nhận ownership cho `crossref.py`, `testset.py`, `quality.py`, `reporting.py`, `corruption.py`, `phase1.py`, `corruption_flow.py`. Hàm `build_clean_dataframe()` được `phase1.py` và `corruption_flow.py` gọi trực tiếp, đó là cách tôi bàn giao output cho cả hai pha.

## 3. Kết quả theo vai trò

| Nhiệm vụ đã thực hiện | File/hàm/artifact liên quan | Kết quả bàn giao | Cách xác minh |
| --------------------------- | ----------------------------- | ------------------- | ---------------- |
| Chuẩn hóa text + strip JATS | `_strip_html_tags()` trong `cleaning.py` | Mọi cell `summary` và `title` không còn tag `<jats:p>` | `pd.read_csv(...)` + regex `<[^>]+>` đếm 0 match |
| Drop record thiếu field bắt buộc | `build_clean_dataframe()` | 24/24 record raw hợp lệ → 24 clean (giữ nguyên) | `data/clean/papers_clean.csv` 24 dòng, log `[PASS] No records without title` |
| Drop summary < 100 ký tự | `build_clean_dataframe()` | 0 record vi phạm (ngưỡng `MIN_SUMMARY_CHARS = 100`) | `[PASS] All summaries >= 100 characters` |
| Chuẩn hóa `paper_id` lowercase | `_normalize_id()` | 24 `paper_id` lowercase, dedupe theo key này | `[PASS] No duplicate paper_ids` |
| Pad date thiếu ngày/tháng | `_parse_date()` | `published` luôn `YYYY-MM-DD`, `age_days` ≥ 0 | `[PASS] age_days calculated correctly` |
| Fallback author/category rỗng | `compact_join()` + literal `"unknown"` | 0 cell rỗng ở `authors_joined` / `categories_joined` | `data/clean/papers_clean.csv` không có chuỗi rỗng ở 2 cột này |
| Dựng `text_for_embedding` | `build_clean_dataframe()` | 24/24 dòng có format `Title: …\nAuthors: …\n…` | `[PASS] text_for_embedding format correct` + `[PASS] contains Authors/Summary` |
| Sort + dedupe | `sort_values(["published", "paper_id"])` rồi `drop_duplicates(keep="first")` | Dòng đầu luôn là bài mới nhất → scenario `drop_latest_record` xóa đúng 1 doc | `corruption_log.json` xác nhận xóa `f604458c87fcc8ad` đúng bài `published = 2026-08-01` |
| Ghi CSV + JSON | `write_csv` + `write_json` trong `core.utils` | `data/clean/papers_clean.csv` (14 cột) + `papers_clean.json` | File tồn tại, 24 dòng × 14 cột |
| Validator offline | `script/validate_clean_contract.py` | 29/29 check PASS, exit 0 | `python script/validate_clean_contract.py` |

**Output cụ thể mà phần việc của tôi tạo ra:**

| Trạng thái | Input | Output | Hành vi đặc biệt |
| --- | --- | --- | --- |
| Baseline | 24 raw `PaperRecord` | 24 clean rows, 14 cột | Sort `published` desc, dedupe `paper_id` |
| Repaired | 24 raw `PaperRecord` (re-read từ `data/raw/crossref_records.json`) | 24 clean rows | Khớp byte-level với baseline sau khi normalize whitespace |
| (Stress) Empty list | 0 record | DataFrame rỗng, không crash | Trả về `df.empty`, caller xử lý `RuntimeError` |

## 4. Giải thích phần kỹ thuật đã thực hiện

### Vấn đề cần giải quyết

Pipeline này nhận dữ liệu thô từ Crossref (một API công khai, không kiểm soát chất lượng) và phải đưa về một schema mà hai đầu đã bị cố định:

- **Đầu vào**: `PaperRecord` (frozen dataclass, 11 field, không đổi được vì `load_raw_records()` dùng lại để repair).
- **Đầu ra**: 9 cột mà `LocalEmbeddingIndex._build_documents()` đọc trực tiếp (thiếu 1 cột là `KeyError` ngay khi build index).

Nhiệm vụ của tôi là **bắc cầu giữa hai đầu đã cố định** đó, đồng thời giải quyết 4 vấn đề thực tế tôi quan sát được:

1. **JATS XML** trong abstract Crossref (`<jats:p>`, `<jats:italic>`…) — nếu lọt vào `text_for_embedding`, MiniLM sẽ học cả tag và `first_sentence()` trả về chuỗi mở tag.
2. **`subject` field của Crossref rỗng** ở 9/24 paper → không thể drop record, mà cũng không thể để `categories_joined` rỗng vì qa có câu hỏi dạng *"what categories…"*.
3. **`paper_id` phải là lowercase** vì `index.lookup()` so lowercase còn `metrics.py` so case-sensitive — lệch một chữ hoa là `retrieval_hit_rate = 0` mà không exception.
4. **CSV round-trip**: `pdf_url`/`updated`/`comment` phép rỗng, nhưng `pd.read_csv` mặc định biến `""` thành `NaN`, `NaN` lọt vào Chroma metadata sẽ hỏng.

### Cách triển khai

**1. Pure function.** `build_clean_dataframe(records, run_date, settings)` chỉ nhận input qua tham số, **không gọi `now()` bên trong**, **không đọc/ghi file nếu `settings=None`**. Tôi cố ý tách phần ghi file ra lệnh `if settings is not None` để validator offline chạy được mà không cần `Settings`. Đây cũng là điều kiện để corruption flow gọi lại hàm này từ raw snapshot để repair — chạy lần nào cũng ra cùng output với cùng input.

**2. `_strip_html_tags()` — defensive trong cleaning.** Source owner đã strip HTML ở `parse_crossref_payload()`. Tôi vẫn strip lại trong cleaning vì thao tác idempotent, chạy 2 lần vô hại, và nó che được trường hợp một record đến từ nguồn khác trong tương lai (khi repair từ file local có thể parse lại theo cách khác).

**3. `_parse_date()` chấp nhận 3 format.** Crossref `date-parts` có thể chỉ có năm (`[[2026]]`), chỉ có năm-tháng (`[[2026, 1]]`) hoặc đủ ngày. Tôi thử lần lượt 3 format và pad thiếu phần nào. Trả về `None` nếu không parse được — caller sẽ drop record.

**4. `_normalize_id()` — critical.** Loại bỏ prefix `https://doi.org/` hoặc `http://dx.doi.org/`, `.strip()`, `.lower()`. Lý do: contract với `LocalEmbeddingIndex` (so lowercase) và `metrics.py` (so case-sensitive) bắt buộc đầu ra phải lowercase. Nếu để raw DOI uppercase thì `lookup()` trả về kết quả nhưng `retrieval_hit_rate` sẽ đếm = 0.

**5. `text_for_embedding` đưa cả metadata vào.** Tôi đã cân nhắc chỉ embed `summary` (gọn, vector ngắn), nhưng test set có câu hỏi *"who authored X"* — nếu `text_for_embedding` chỉ chứa summary, MiniLM sẽ không match được câu hỏi có chứa tên tác giả. Format 5 dòng tôi chọn (`Title / Authors / Categories / Published / Summary`) đảm bảo mọi dạng câu hỏi đều retrieve được.

**6. Sort trước, dedupe sau.** `sort_values(["published", "paper_id"], ascending=[False, True])` rồi `drop_duplicates(subset=["paper_id"], keep="first")`. Đảo lại thứ tự thì kết quả dedupe không ổn định giữa các lần chạy (giữ record nào tuỳ thứ tự xuất hiện). Đây cũng là contract với Corruption owner: scenario *"xóa latest records"* phụ thuộc trực tiếp vào dòng đầu là bài mới nhất — và baseline confirm đúng: row đầu có `published = 2026-08-01`.

**7. `compact_join()` + fallback `"unknown"`.** Crossref rất hay thiếu `subject` và `author`. Tôi dùng `compact_join((normalize_whitespace(x) for x in rec.authors if x), sep=", ")` để lọc phần tử rỗng, rồi fallback `"unknown"` nếu kết quả rỗng. Lý do: `text_for_embedding` và metadata Chroma không được chứa chuỗi rỗng (sẽ thành `""` trong metadata, gây khó debug hơn `"unknown"`).

**8. `fillna("")` ở cuối.** Sau khi build DataFrame, tôi `df.fillna("")` để chuyển mọi `NaN` (nếu lọt qua) về chuỗi rỗng. Đây là phần phòng thủ trước khi ghi CSV, kết hợp với `keep_default_na=False` ở phía đọc (do Corruption owner chịu trách nhiệm) tạo thành contract round-trip an toàn.

### Input, output và contract

| Thành phần | Mô tả |
| ------------ | ------- |
| Input | `list[PaperRecord]` (11 field, frozen dataclass), `run_date: datetime` (UTC), `Settings` (optional, chỉ để ghi file) |
| Output | `pandas.DataFrame` với 14 cột theo `docs/clean_schema_contract.md`: `paper_id`, `title`, `summary`, `authors_joined`, `categories_joined`, `primary_category`, `published`, `updated`, `age_days`, `summary_chars`, `abs_url`, `pdf_url`, `comment`, `text_for_embedding` |
| Module phụ thuộc | `core.utils` (`compact_join`, `normalize_whitespace`, `ensure_parent`, `write_csv`, `write_json`), `core.config.Settings`, `ingestion.crossref.PaperRecord` |
| Module sử dụng output | `retrieval.index.LocalEmbeddingIndex.build()`, `evaluation.testset.build_test_set()`, `observability.quality.run_data_quality_checks()`, `pipelines.phase1.main()`, `pipelines.corruption_flow.main()` |
| Điều kiện lỗi cần xử lý | Thiếu `paper_id`/`title`/`published` → drop; `summary < 100 chars` → drop; thiếu `subject`/`author` → fallback `"unknown"`; JATS XML → strip |

### Cách xác minh

```bash
# Chạy validator offline (không cần API key, không cần mạng)
python script/validate_clean_contract.py

# Test trên dữ liệu thật (cần có data/raw/crossref_records.json)
python test_cleaning.py

# Chạy baseline pipeline end-to-end
python script/run_phase1.py
```

- **Kết quả mong đợi:** validator in `29/29 check dat, 0 fail` exit 0; `test_cleaning.py` in 10 dòng `[PASS]`; `data/clean/papers_clean.csv` có 24 dòng × 14 cột, không `NaN`.
- **Kết quả thực tế:** validator `29/29 PASS`, test_cleaning in đủ 10 PASS (No records without title, All summaries >= 100 characters, No HTML/XML tags, …), `papers_clean.csv` 24 dòng đúng schema.
- **Artifact/log:** `data/clean/papers_clean.csv`, `data/clean/papers_clean.json`. Không chứa secret.

## 5. Một quyết định kỹ thuật quan trọng

- **Bối cảnh:** Cleaning tạo `text_for_embedding` từ 5 trường (`title`, `authors_joined`, `categories_joined`, `published`, `summary`). Câu hỏi trong test set có 4 dạng: *"who authored…"*, *"when was X published"*, *"what categories…"*, *"what is the main contribution"*. Nếu `text_for_embedding` chỉ chứa `summary` thì 3/4 dạng câu hỏi đầu sẽ không retrieve đúng document.

- **Các phương án đã cân nhắc:**
  1. Chỉ embed `summary` — vector ngắn, retrieval nhanh, nhưng fail với câu hỏi về tác giả/ngày/category.
  2. Embed `title` riêng, `summary` riêng, weighted average — chính xác hơn nhưng phải sửa `LocalEmbeddingIndex` (vi phạm contract: index đã được cố định ở đầu ra).
  3. Nhúng cả metadata vào cùng `text_for_embedding` — chỉ cần sửa cleaning, không phải sửa index.

- **Phương án đã chọn:** Phương án 3 — format 5 dòng `Title / Authors / Categories / Published / Summary`.

- **Lý do:** Contract đầu ra của cleaning đã bị `LocalEmbeddingIndex._build_documents()` cố định (chỉ đọc 9 cột scalar, không có cột `summary_vector` riêng). Đổi contract đầu ra sẽ kéo theo phải đổi index, mà index là module của người khác — vượt quá phạm vi cleaning. Trộn metadata vào `text_for_embedding` cho phép MiniLM tự học trọng số giữa các trường (trong thực tế nó vẫn ưu tiên `summary` vì trường này dài nhất, nhưng `title`/`authors` xuất hiện ở đầu giúp câu hỏi ngắn vẫn match được).

- **Bằng chứng quyết định phù hợp:** Baseline `retrieval_hit_rate = 0.8` trên test set gồm cả 4 dạng câu hỏi. Nếu chỉ embed `summary`, câu q1 (*"Who are the authors of…"*) và q2 (*"When was… published"*) sẽ gần như chắc chắn MISS vì `text_for_embedding` không chứa thông tin tác giả/ngày.

## 6. Một lỗi hoặc blocker đã xử lý

- **Triệu chứng/lỗi nguyên văn:**
  ```
  KeyError: 'age_days'
  ```
  raised từ `LocalEmbeddingIndex._build_documents()` khi chạy `python script/run_phase1.py` lần đầu, sau khi đã implement `build_clean_dataframe()`.

- **Lệnh hoặc bước tái hiện:**
  ```bash
  python script/run_phase1.py
  # Traceback: File "src/retrieval/index.py", line ..., in _build_documents
  #            df = df[REQUIRED_COLUMNS]
  # KeyError: 'age_days'
  ```

- **Nguyên nhân gốc:** Ban đầu tôi chỉ tạo 13 cột, không có `age_days`. Tôi nghĩ freshness là việc của Observability owner và sẽ tự tính `age_days` từ `published` + `now()`. Nhưng `LocalEmbeddingIndex._build_documents()` yêu cầu **`age_days` nằm trong DataFrame** để đưa vào Chroma metadata (giúp debug sau này: biết document này bao nhiêu ngày tuổi khi retrieve). Tôi đã không đọc kỹ contract đầu ra trước khi code.

- **Cách xử lý:** Thêm block tính `age_days` ngay sau khi parse `published_date`:
  ```python
  comparable_run_date = run_date if run_date.tzinfo else run_date.replace(tzinfo=UTC)
  age_days = max(0, (comparable_run_date.date() - published_date.date()).days)
  ```
  Đồng thời thêm `age_days` vào `REQUIRED_COLUMNS` trong `docs/clean_schema_contract.md` (mục 1, schema đầu ra).

- **Cách xác minh sau khi sửa:**
  ```bash
  python script/run_phase1.py
  ```
  Chạy thành công. `data/clean/papers_clean.csv` có cột `age_days` với giá trị từ 5 (bài mới nhất) đến 175 (bài cũ nhất). `data/quality/freshness_report.json` ghi `max_age_days: 175, is_fresh: true`.

- **Điều học được:** Contract đầu ra không chỉ là những gì module sau **đọc trực tiếp** — còn là những gì module sau **đưa vào artifact phái sinh**. `age_days` không bắt buộc cho embedding, nhưng `LocalEmbeddingIndex` muốn đưa nó vào metadata, và `observability.quality` đọc nó từ cleaned DataFrame để check freshness. Cleaning owner phải đọc kỹ toàn bộ consumer trước khi chốt schema, không chỉ đọc phần "hard contract".

## 7. Hiểu biết về luồng end-to-end

1. **Dữ liệu đi từ Crossref đến vector index như thế nào?**
   `fetch_source_records()` (Source owner) gọi Crossref REST API với query `agentic retrieval augmented generation large language model` và filter `from-pub-date:2025-02-07` + `has-abstract:true`, lưu raw response vào `data/raw/crossref_response.json` và list `PaperRecord` vào `crossref_records.json`. `build_clean_dataframe()` (tôi) strip JATS XML, normalize DOI về lowercase, pad date thiếu ngày, drop record thiếu 4 field bắt buộc hoặc summary < 100 ký tự, dedupe theo `paper_id`, sort `published` giảm dần, dựng cột `text_for_embedding` 5 dòng. `LocalEmbeddingIndex.build()` (Retrieval owner) embed cột đó bằng `sentence-transformers/all-MiniLM-L6-v2` rồi nạp vào collection ChromaDB (cosine).

2. **Evaluation set và ground-truth document IDs dùng để đo retrieval/answer quality ra sao?**
   `build_test_set()` (Test-set owner) sinh 10 câu hỏi từ 10 bài mới nhất, mỗi câu có `ground_truth` (chuỗi đáp án) và `ground_truth_doc_ids` lấy **đúng giá trị cột `paper_id` từ cleaned DataFrame**. Khi eval, agent search top_k=4; `retrieval_hit` = có ít nhất 1 `paper_id` trả về nằm trong `ground_truth_doc_ids`. Chất lượng câu trả lời đo bằng `token_f1` (so với `ground_truth`) và LLM judge. Lưu ý: `lookup()` so lowercase, `metrics.py` so case-sensitive — nếu cleaning không lowercase `paper_id` thì `retrieval_hit_rate = 0` mà không có lỗi nào.

3. **Quality checks khác freshness monitoring ở điểm nào trong bài lab?**
   Quality checks trả lời "dữ liệu có **đúng hình dạng** không": đủ 14 cột, đủ dòng, `paper_id` không rỗng và không trùng, title không rỗng, summary ≥ 100 ký tự, không `NaN` ở cột index, `text_for_embedding` không rỗng. Freshness trả lời "dữ liệu có **còn mới** không": `age_days` so với ngưỡng 180, kèm `latest_published`, `oldest_published`, `stale_rows`, `stale_ratio`. Một dataset có thể sạch tuyệt đối về cấu trúc mà vẫn vô dụng vì toàn bài từ năm 2000 — đó chính là scenario `stale_published_date` trong corruption flow. Trong bài này hai thứ có giao nhau một điểm: `freshness_age_days` được đưa vào bộ quality check ở mức `error` (do Observability owner quyết), để `success` phản ánh cả tính tươi.

4. **Vì sao phải dùng cùng test set cho baseline, corrupted và repaired?**
   Vì đây là thí nghiệm có đối chứng: chỉ được phép thay đổi **một biến duy nhất là dữ liệu**. Nếu sinh lại test set từ dataset corrupted thì câu hỏi sẽ được tạo từ chính summary đã hỏng, ground truth cũng hỏng theo, và metric có thể **không giảm** — corruption bị che mất. Test set bị đóng băng từ C2 và cả ba lượt eval đều đọc cùng file `data/eval/test_set.json`, cùng `top_k=4`, cùng MiniLM model, cùng judge prompt. Hệ quả kéo theo: corruption bắt buộc phải trúng tài liệu nằm trong test set (10/10 ground-truth doc đều bị corrupt, theo `corruption_log.json`), nếu không thì metric đứng yên không phải vì dữ liệu tốt mà vì ta hỏi nhầm chỗ.

5. **Repair được xem là thành công dựa trên artifact và metric nào?**
   Bốn bằng chứng, theo thứ tự chặt dần:
   - **Nguồn repair đúng:** `corruption_flow.py` gọi lại `build_clean_dataframe()` từ `data/raw/crossref_records.json` (snapshot đóng băng ở C2), **không** đọc `papers_corrupted.csv`, **không** fetch Crossref mới. Lý do: nếu fetch lại, Crossref có thể trả về bản ghi đã cập nhật (ví dụ `updated` thay đổi) → repaired ≠ baseline, so sánh mất ý nghĩa.
   - **Dữ liệu khôi phục:** `repair_verification` trong `corruption_report.md` xác nhận 24 vs 24 dòng, tập `paper_id` trùng khớp, nội dung 6 cột chính (title, summary, published, authors_joined, categories_joined, text_for_embedding) giống hệt sau khi normalize whitespace.
   - **Observability phục hồi:** `repaired_quality.json` `success: true` 10/10, `repaired_freshness.json` `is_fresh: true`, `stale_rows: 0`, `max_age_days` về 175.
   - **Metrics phục hồi:** cả 4 metric RAG (`retrieval_hit_rate`, `mean_token_f1`, `judge_accuracy`, `mean_judge_score`) về **đúng** giá trị baseline, delta `+0.0000` trên toàn bộ.

## 8. Phân tích kết quả

### Metrics chính

| Metric/signal | Baseline | Corrupted | Repaired | Nhận xét của cá nhân |
| -------------- | -------: | --------: | -------: | ---------------------- |
| `retrieval_hit_rate` | 0.8000 | 0.8000 | 0.8000 | Không đổi ở cả 3 trạng thái — xem phân tích bên dưới |
| `mean_token_f1` | 0.4821 | 0.3035 | 0.4821 | Giảm 37.1% do `blank_summary` (q3, q7) + `inject_summary_noise` (q4, q9) đánh trúng `summary`; phục hồi tuyệt đối |
| `judge_accuracy` | 0.5000 | 0.3000 | 0.5000 | Giảm 40.0% — judge thấy câu trả lời rỗng/vô nghĩa; phục hồi tuyệt đối |
| `mean_judge_score` | 2.8000 | 2.2000 | 2.8000 | Giảm 21.4% tương ứng `token_f1`; phục hồi tuyệt đối |
| Quality checks | PASS 10/10 | **FAIL 7/10** | PASS 10/10 | 3 check FAIL là do corrupted dataset; baseline `success: true` 10/10 nhờ `summary_chars ≥ 100`, `paper_id` unique, `age_days ≤ 180` |
| Freshness status | `is_fresh: true`, stale 0/24, max_age 175 | **`is_fresh: false`, stale 4/26, max_age 9714** | `is_fresh: true`, stale 0/24, max_age 175 | `oldest_published` nhảy từ 2026-02-12 về 2000-01-01 do scenario `stale_published_date` |

### Kết luận từ số liệu

**Chuỗi 1:** Scenario `blank_summary` xóa trắng `summary` ở 4 document (trong đó `de23fc4ac319930e`, `27868f5ca6e98bb5` nằm trong test set — q3, q7) → `summary_min_length` FAIL với `observed = 4`, `token_f1` của q3/q7 rơi về 0 (vì `qa._extract_answer()` trả về first sentence của summary rỗng). Song song, `inject_summary_noise` chèn nội dung không liên quan vào **đầu** summary ở 4 document (trong đó `1ed7987631bdbdab`, `c461d892c39f1eac` nằm trong test set — q4, q9) → vừa kéo document ra xa câu hỏi trong MiniLM space (vì `summary` chiếm phần lớn `text_for_embedding`), vừa làm `first_sentence()` trả về câu vô nghĩa ("Yesterday the weather forecast promised heavy rain…"). Kết quả: `mean_token_f1` giảm từ 0.4821 xuống 0.3035, `judge_accuracy` từ 0.50 xuống 0.30, `mean_judge_score` từ 2.8 xuống 2.2.

**Chuỗi 2:** Repair chạy lại `build_clean_dataframe()` từ raw snapshot C2 (cùng `run_date` trong pipeline, cùng 24 record) → `repaired_quality.json` `success: true` 10/10, `repaired_freshness.json` `is_fresh: true`, `stale_rows: 0` → cả 4 metric RAG về **đúng** giá trị baseline, delta `+0.0000` trên toàn bộ. `repair_verification` trong `corruption_report.md` xác nhận 6 cột chính (title, summary, published, authors_joined, categories_joined, text_for_embedding) khớp byte-level sau normalize.

**Corruption nào ảnh hưởng rõ nhất và vì sao?**

Từ góc độ cleaning, `blank_summary` và `inject_summary_noise` là 2 scenario đánh mạnh nhất vì cả hai đều phá trực tiếp trường `summary` — trường mà tôi đã đặt nặng nhất trong `text_for_embedding` (xem mục 5). Lý do sâu hơn: trong test set, q4 (`inject_summary_noise` trên `1ed7987631bdbdab`) giảm `token_f1` từ **0.82 → 0.04** — đây là một câu rơi gần như toàn bộ. So với `truncate_title` (q6) chỉ ảnh hưởng gián tiếp qua embedding (q6 vẫn `token_f1 = 1.00` vì `summary` nguyên vẹn), hoặc `duplicate_record` (q5, q10) chỉ chiếm thêm slot top_k mà không phá nội dung, hai scenario kia mới đánh trúng **chỗ dữ liệu quan trọng nhất của cleaning output**.

Ngược lại, từ góc độ observability thì `stale_published_date` ồn hơn: nó vừa làm FAIL `freshness_age_days` (đẩy `max_age_days` lên 9714 — sai lệch 54 lần ngưỡng), vừa khiến q2/q8 (`token_f1 = 1.00 → 0.00`) vì `qa._extract_answer()` đọc thẳng `metadata["published"]`. Hai câu này trở thành evidence rõ ràng nhất cho việc "dữ liệu xấu làm agent tự tin trả lời sai".

**Kết quả nào khác với kỳ vọng ban đầu?**

`retrieval_hit_rate` **không hề giảm** (0.8000 ở cả ba trạng thái), dù scenario `drop_latest_record` đã xóa hẳn document `f604458c87fcc8ad` (paper mới nhất, thuộc q1) khỏi index. Tôi đã nghĩ đây là metric nhạy nhất với data loss.

Cách tôi kiểm tra: đọc bảng per-question ở mục 5 của `corruption_report.md`. Kết quả cho thấy hai thay đổi ngược chiều triệt tiêu nhau — q1 chuyển `hit → MISS` như dự đoán, nhưng q7 lại **flip ngược từ `MISS → hit`** sau khi bị `blank_summary`. Giả thuyết: mọi câu hỏi trong test set đều **trích nguyên title** của bài vào câu hỏi, nên khi summary bị xóa, `text_for_embedding` ngắn lại và **title chiếm tỷ trọng lớn hơn** trong vector — làm độ tương đồng với câu hỏi tăng lên. Đây là artifact đặc thù của corpus 24 document và `top_k = 4`: mỗi câu hỏi chỉ đóng góp 0.1 vào hit_rate, và chỉ cần 1 trong 4 slot đúng là tính hit.

Bài học cho phần cleaning: tôi **đúng** khi đặt `title` ở dòng đầu `text_for_embedding` — đây là lý do q7 flip ngược hit sau khi `summary` bị xóa. Nếu đặt `summary` lên đầu, hit_rate có lẽ đã giảm rõ hơn nhưng cũng làm mất khả năng retrieve theo metadata cho câu hỏi ngắn.

## 9. Điều học được và hướng cải thiện

### Ba điều quan trọng nhất

1. **Về data pipeline:** contract dữ liệu phải được viết ra trước khi chia việc, không phải suy ra sau. Tôi đã sai lần đầu khi quên cột `age_days` vì không đọc kỹ consumer — đến khi `LocalEmbeddingIndex` ném `KeyError` mới sửa. Sau đó tôi viết `docs/clean_schema_contract.md` chốt 14 cột + 6 rule + 4 ràng buộc kỹ thuật, kèm `script/validate_clean_contract.py` chạy 29 check offline. Validator này sau đó bắt được một lỗi của Corruption owner: thiếu `keep_default_na=False` khi đọc CSV làm `pdf_url`/`updated` rỗng thành `NaN` → đưa vào Chroma metadata hỏng. Contract giúp bắt lỗi ở ranh giới module, không phải ở runtime.

2. **Về data quality/observability:** ngưỡng phải suy ra từ số liệu thật của baseline, không chọn bừa. Tôi đã chốt `MIN_SUMMARY_CHARS = 100` dựa trên baseline (summary ngắn nhất 826 ký tự, biên rất xa 100) → cùng ngưỡng đó cũng được Observability owner dùng cho quality check, nên cleaning và quality check **không bất đồng**. Tương tự, việc giữ `paper_id` unique ở cleaning và `paper_id_unique` ở quality check tạo thành defense in depth: cleaning loại trùng khi build, quality check bắt trùng nếu CSV bị lỗi round-trip.

3. **Về ảnh hưởng của data đến RAG agent:** dữ liệu xấu không làm agent sập, nó làm agent **tự tin trả lời sai**. Toàn bộ pha corrupted chạy trơn tru, không một exception nào, chỉ có `token_f1` và `judge_score` tụt. Hai scenario `blank_summary` và `inject_summary_noise` chiếm phần lớn sụt giảm vì `summary` chiếm phần lớn `text_for_embedding`. Đây là lý do tôi đặt `summary` ở cuối `text_for_embedding` (sau title/authors/categories/published): nếu `summary` bị phá, các metadata phía trên vẫn giúp retrieval không hoàn toàn sụp — q6 vẫn hit, q7 vẫn flip ngược hit.

### Nếu có thêm thời gian

Tách phần dựng `text_for_embedding` ra một hàm riêng `_build_embedding_text(row_dict)` và viết unit test cho nó với 6 edge case (title có emoji, author có dấu phẩy trong tên, category rỗng, summary có newline, published format chỉ có năm, summary ngắn đúng 100 ký tự). Hiện tại `text_for_embedding` chỉ được kiểm tra gián tiếp qua `validate_clean_contract.py` (check format prefix `Title: ` và có chứa `Authors: `, `Summary: `). Một bộ unit test riêng sẽ giúp debug nhanh hơn nếu sau này có ai đó muốn đổi format (ví dụ thêm `Abstract: ` thay vì `Summary: `, hoặc thêm trường `DOI: `).

Cách đo cải thiện: thêm 6 test, chạy `pytest`, expect 6/6 PASS. Nếu đổi format `text_for_embedding` thì test phải fail ngay, không phải đợi baseline eval chạy xong mới phát hiện retrieval tệ đi.

Một cải thiện nữa: đưa `MIN_SUMMARY_CHARS` về một nguồn duy nhất trong `Settings`. Hiện nó đang là hằng số trong `cleaning.py` (`if len(summary.strip()) < 100`), trong `quality.py` (`MIN_SUMMARY_CHARS = 100`) và trong `validate_clean_contract.py`. Đổi một chỗ mà quên hai chỗ kia thì cleaning và quality check sẽ bất đồng. Cách làm: thêm `Settings.min_summary_chars: int = 100` trong `core/config.py`, ba nơi cùng đọc từ đó.

## 10. Cam kết của thành viên

- [x] Nội dung báo cáo phản ánh đúng phần việc và mức hiểu của tôi.
- [x] Tôi có thể giải thích luồng end-to-end, không chỉ module mình phụ trách.
- [x] Mọi kết luận về kết quả đều có artifact hoặc metric để đối chiếu.
- [x] Tôi không ghi "đã chạy thành công" cho phần chưa được kiểm chứng.
- [x] Báo cáo không chứa `.env`, API key, token hoặc secret.
- [x] Báo cáo này không phải bản sao nguyên văn của báo cáo nhóm hoặc báo cáo thành viên khác.

**Họ và tên:** Trần Bình Minh
**Ngày xác nhận:** 2026-08-06
