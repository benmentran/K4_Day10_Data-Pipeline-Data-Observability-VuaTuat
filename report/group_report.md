# Group Report — Day 10: Data Pipeline & Data Observability

> Báo cáo của nhóm **VuaTuat** (5 thành viên) trong khóa K4, làm bài tập cuối kỳ Day 10. Toàn bộ số liệu dưới đây lấy từ artifact trong repo; mọi đường dẫn đều truy cập được tương đối từ project root.

## 1. Thông tin bài nộp

| Thông tin       | Nội dung                                                                            |
| --------------- | ------------------------------------------------------------------------------------ |
| Khóa/Lớp        | K4                                                                                   |
| Tên nhóm        | VuaTuat                                                                              |
| Repository      | https://github.com/benmentran/K4_Day10_Data-Pipeline-Data-Observability-VuaTuat     |
| Ngày hoàn thành | 2026-08-06                                                                            |

### Thành viên và phân công

| STT | Họ và tên        | MSSV        | Vai trò chính                       | Module/deliverable sở hữu                                                                              |
| --: | ---------------- | ----------- | ------------------------------------- | ------------------------------------------------------------------------------------------------------ |
| 1   | Trần An Thắng    | 2A202601756 | Source owner                          | `src/ingestion/crossref.py`: fetch, retry, parse, lưu raw; `validate_raw_records`, `generate_audit_report` |
| 2   | Trần Bình Minh   | 2A202601434      | Cleaning & test-set owner             | `src/ingestion/cleaning.py`, `src/evaluation/testset.py`                                              |
| 3   | Tạ Đăng Đức      | 2A202601772 | Observability owner                   | `src/observability/quality.py`, `src/observability/reporting.py`                                      |
| 4   | Trần Kiều Hạnh   | 2A202601760 | Corruption & repair owner             | `src/ingestion/corruption.py`                                                                          |
| 5   | Lương Bảo Long   | 2A202601682 | Pipeline integration & evidence owner | `src/pipelines/phase1.py`, `src/pipelines/corruption_flow.py`; reproducibility; consistency check       |

Báo cáo vai trò từng thành viên đặt tại `report/<MSSV>_HoTen.md` (TV1: `TranAnThang_2A202601756.md`; TV2: `TranBinhMinh_2A202601434.md`; TV3: `TaDangDuc_2A202601772.md`; TV4: `TranKieuHanh_2A202601760.md`; TV5: `LuongBaoLong_2A202601682.md`).

## 2. Tóm tắt kết quả

Nhóm VuaTuat đã hoàn thành **toàn bộ pipeline end-to-end** từ Crossref API đến comparison report, gồm:

- **Baseline pipeline** chạy ổn định, sinh đủ 7 artifact: raw records (24 records), cleaned CSV/JSON (24 rows), embeddings (`sentence-transformers/all-MiniLM-L6-v2`), evaluation set (10 câu hỏi), metrics, quality/freshness, `phase1_report.md`.
- **Corruption flow** chạy end-to-end: sinh corrupted dataset (26 rows, 19 docs bị tác động, 10/10 ground-truth docs nằm trong overlap với frozen test set), rồi replay raw snapshot qua cùng cleaning logic để ra repaired dataset, cuối cùng sinh `corruption_report.md` đầy đủ 6 mục.
- **Repair verification** (do TV5 viết): `_verify_repair()` so sánh baseline vs repaired trên 6 cột nội dung, kết quả `paper_ids_match: true`, `content_matches: true`, không có document nào thay đổi.

**Corruption ảnh hưởng rõ nhất** là `blank_summary` + `inject_summary_noise`: nó tác động trực tiếp vào `text_for_embedding` (phần input chính của MiniLM), đồng thời làm `summary_min_length` quality check FAIL. 4 câu hỏi test set (q3, q4, q7, q9) đụng 2 scenario này, chiếm 40% test set. Hệ quả: `mean_token_f1` sụt 0.4821 → 0.3035 (-37.1%), `judge_accuracy` sụt 0.5 → 0.3 (-40%).

**Repair phục hồi 100%**: cả 4 RAG metric (retrieval_hit_rate, mean_token_f1, judge_accuracy, mean_judge_score) trở về đúng bằng baseline. Quality và freshness cũng recover (10/10 PASS, max_age về 175 ngày).

**Blocker/giới hạn quan trọng còn lại**: (1) corpus 24 dòng quá nhỏ để retrieval_hit_rate phản ánh đúng tác động của corruption — top_k=4/24 luôn surface được ground-truth doc kể cả khi summary bị blank; (2) `categories_joined` chỉ có 15/24 records vì Crossref hay thiếu field `subject`, khiến q3 và q9 có ground_truth = "unknown" — đây là warning-level, không phải failure.

## 3. Kiến trúc và luồng dữ liệu

### Luồng end-to-end

```text
Crossref API (query + filter)
    -> src/ingestion/crossref.py
        -> data/raw/crossref_response.json (raw HTTP response, freeze point)
        -> data/raw/crossref_records.json (parsed PaperRecord list, freeze point)
    -> src/ingestion/cleaning.py::build_clean_dataframe
        -> data/clean/papers_clean.csv / papers_clean.json (24 rows, 14 cols)
    -> src/retrieval/index.py::LocalEmbeddingIndex.build
        -> MiniLM embed "text_for_embedding"
        -> Chroma collection "papers-baseline" + manifest data/embeddings/papers_embeddings.json
    -> src/evaluation/testset.py::build_test_set
        -> data/eval/test_set.json (10 questions, 6 question_type templates)
    -> src/evaluation/metrics.py::evaluate_pipeline
        -> data/results/baseline_metrics.json (retrieval_hit_rate, token_f1, judge)
        -> data/results/baseline_answers.json (per-question answer + retrieved_doc_ids)
    -> src/observability/quality.py::run_data_quality_checks
        -> data/quality/baseline_quality.json (10 checks, severity error/warning)
    -> src/observability/quality.py::build_freshness_report
        -> data/quality/freshness_report.json
    -> src/observability/reporting.py::generate_phase1_report
        -> data/reports/phase1_report.md
    -- Phase 2a: corruption --
    -> src/ingestion/corruption.py::corrupt_clean_dataframe(test_set_path=eval_testset)
        -> 6 scenarios: drop_latest_record, blank_summary, inject_summary_noise,
                        truncate_title, stale_published_date, duplicate_record
        -> data/results/corruption_log.json (per-paper audit trail + frozen_test_set overlap)
        -> data/clean/papers_corrupted.csv (24 -> 26 rows)
        -> data/embeddings/papers_embeddings_corrupted.json
        -> Chroma "papers-corrupted"
    -> evaluate_pipeline -> data/results/corrupted_metrics.json
    -> quality + freshness -> corrupted_quality.json, corrupted_freshness.json
    -- Phase 2b: repair --
    -> load_raw_records(raw_records_json)  # KHONG doc papers_corrupted.csv
    -> build_clean_dataframe(raw_records)   # replay qua cung cleaning logic
        -> data/clean/papers_clean_repaired.csv (24 rows)
        -> Chroma "papers-repaired"
    -> evaluate_pipeline -> data/results/repaired_metrics.json
    -> quality + freshness -> repaired_quality.json, repaired_freshness.json
    -- Phase 2c: comparison --
    -> _verify_repair(baseline_df, repaired_df, settings)
    -> src/observability/reporting.py::generate_corruption_report
        -> data/reports/corruption_report.md
```

### Trách nhiệm của từng khối

| Khối             | Input                                                | Xử lý chính                                                                   | Output/artifact                                                      | Owner          |
| ----------------- | ---------------------------------------------------- | -------------------------------------------------------------------------------- | --------------------------------------------------------------------- | -------------- |
| Ingestion         | Crossref REST API + query "agentic retrieval augmented generation large language model" | SHA256(DOI\|title) → paper_id, parse JSON, retry 429/503 với exponential backoff, lưu raw response + records | `data/raw/crossref_response.json`, `data/raw/crossref_records.json` (24 records) | Trần An Thắng |
| Cleaning          | 24 `PaperRecord`                                     | strip HTML, ép summary ≥ 100 ký tự, parse date, build `text_for_embedding`, drop duplicate theo `paper_id` | `data/clean/papers_clean.csv`/`.json` (24 rows, 14 cols)            | TV2            |
| Embedding/index   | cleaned DataFrame                                    | MiniLM embed `text_for_embedding`, lưu Chroma collection + manifest JSON        | `data/embeddings/papers_embeddings.json`, `data/chroma/`             | (chia sẻ TV4/TV5) |
| Evaluation        | cleaned DataFrame                                    | `build_test_set` từ `df.head(10)`, 6 question templates, ground_truth từ chính field tương ứng | `data/eval/test_set.json` (10 câu), `data/results/baseline_metrics.json`, `baseline_answers.json` | TV2 (test set) + TV5 (eval) |
| Observability     | cleaned DataFrame + Settings                         | 10 check (severity error/warning), freshness dựa trên `age_days > threshold`   | `data/quality/baseline_quality.json`, `data/quality/freshness_report.json`, `data/reports/phase1_report.md` | Tạ Đăng Đức  |
| Corruption/repair | baseline DataFrame + frozen test set                 | 6 scenarios có overlap đảm bảo với test set; repair replay raw snapshot         | `data/results/corruption_log.json`, `papers_corrupted.csv`, `papers_clean_repaired.csv` | TV4 (corruption) + TV5 (repair orchestration) |
| Orchestration     | `Settings` + artifact paths                          | `phase1.py` chạy tuần tự; `corruption_flow.py` chạy 2b/2c, có `--report-only` cho re-render | `data/reports/phase1_report.md`, `data/reports/corruption_report.md`  | Lương Bảo Long |

## 4. Cách tái hiện kết quả

### Cấu hình không chứa secret

| Biến/cấu hình                 | Giá trị sử dụng                                                            |
| ------------------------------ | ---------------------------------------------------------------------------- |
| `LLM_PROVIDER`                 | `grok` (được preserve từ local config; nhóm có thể đổi sang `gemini`/`openai`/`anthropic`/`openrouter`/`ollama`/`custom`) |
| `LLM_MODEL`                    | lấy từ `.env` của từng máy (nhóm không chốt một model duy nhất vì TV5 dùng Grok, TV3 dùng Gemini) |
| Embedding model                | `sentence-transformers/all-MiniLM-L6-v2` (cố định trong `Settings`)         |
| Số lượng Crossref records      | 24 (đã chốt ở `settings.max_results = 24`)                                |
| Retrieval `top_k`              | 4 (`settings.top_k = 4`)                                                    |
| Freshness threshold            | 180 ngày (`freshness_threshold_days = 180`)                                  |
| Random seed, nếu có            | 42 (seed cho corruption scenarios; xem `data/results/corruption_log.json`)  |

Provider Grok được giữ nguyên từ local config của TV5 sau khi pull code từ remote (grok thêm vào `core/config.py` và `retrieval/llm.py` không có sẵn trong upstream). Các thành viên khác có thể chuyển sang provider khác qua biến `LLM_PROVIDER` mà không ảnh hưởng đến schema/metrics.

### Lệnh cài đặt

Nhóm dùng `pip` (không dùng `uv`):

```bash
# Từ project root
python -m pip install -e .

# Cài thêm các package upstream thiếu trong môi trường host
python -m pip install langchain-anthropic langchain-google-genai langchain-ollama \
                    langchain-openai datasets ragas great-expectations \
                    sentence-transformers

# Fix xung đột chromadb <-> opentelemetry
python -m pip install --upgrade chromadb opentelemetry-api opentelemetry-sdk
```

`pip install -e .` cần thiết vì `script/run_phase1.py` và `script/run_corruption_flow.py` dùng absolute import (`from pipelines.phase1 import main`); `pyproject.toml` khai báo `[tool.setuptools] package-dir = {"" = "src"}` nên chỉ editable install mới expose được `core.*`, `evaluation.*`, `retrieval.*`, `pipelines.*`.

### Lệnh chạy

Baseline:

```bash
python script/run_phase1.py
```

Tái dựng report từ artifact có sẵn (không cần re-evaluate):

```bash
python script/run_phase1.py --report-only
```

Corruption flow:

```bash
python script/run_corruption_flow.py
```

Tái dựng comparison report:

```bash
python script/run_corruption_flow.py --report-only
```

### Kết quả tái hiện

| Lệnh                                            | Trạng thái        | Thời điểm chạy gần nhất       | Bằng chứng                                                                                                                                                                              |
| ------------------------------------------------ | ----------------- | ------------------------------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `python script/run_phase1.py`                    | Thành công        | 2026-08-06 16:58 (UTC+7)      | Log: `Baseline complete: 24 clean records; report=.../data/reports/phase1_report.md`; artifact: `data/clean/papers_clean.csv` (24 rows), `data/results/baseline_metrics.json`, `phase1_report.md` |
| `python script/run_phase1.py --report-only`      | Thành công        | 2026-08-06 20:15 (UTC+7)      | Log: `Baseline report written: .../phase1_report.md`; report render lại đúng từ JSON đã có                                                                                              |
| `python script/run_corruption_flow.py`           | Thành công        | 2026-08-06 12:25 (UTC+7)      | Log: `Comparison report written: .../corruption_report.md`; 9 JSON files mới + 3 CSV + 1 corruption log                                                                                  |
| `python script/run_corruption_flow.py --report-only` | Thành công        | 2026-08-06 20:15 (UTC+7)      | Log: `Comparison report written`; report re-render đúng từ artifact đã có                                                                                                                |

## 5. Ingestion, cleaning và data contract

### Nguồn dữ liệu

| Thuộc tính                | Giá trị                                                                                          |
| --------------------------- | -------------------------------------------------------------------------------------------------- |
| Source                      | Crossref REST API (`https://api.crossref.org/works`)                                              |
| Query/filter                | `query=agentic retrieval augmented generation large language model`, `filter=from-pub-date:<ngày cách 180 ngày>,has-abstract:true`, `rows=24` |
| Thời điểm lấy dữ liệu      | 2026-08-06 (UTC), freeze tại C2                                                                  |
| Số record nhận được         | 24 records                                                                                         |
| Cơ chế retry/backoff        | exponential backoff `wait = 2 ** attempt`, retry cho HTTP 429/503, tôn trọng `Retry-After` header, max 3 retries; `langchain_community.chat_models.vertexai` shim để ragas import được |

### Raw và clean schema

**Raw schema (`PaperRecord`):**

| Trường            | Kiểu dữ liệu     | Bắt buộc? | Ý nghĩa                          | Xử lý khi thiếu/sai                                         |
| ------------------- | ----------------- | ------------ | ---------------------------------- | ------------------------------------------------------------ |
| `paper_id`         | `str` (16 hex)    | Có           | SHA256(DOI\|title)[:16]           | Bỏ record nếu thiếu DOI hoặc title                          |
| `title`            | `str`             | Có           | Tiêu đề paper                     | Strip HTML tags + `&entity;`; bỏ nếu rỗng sau strip         |
| `summary`          | `str`             | Có           | Abstract từ Crossref               | Strip HTML; bỏ record nếu `< 100` ký tự sau strip          |
| `authors`          | `list[str]`      | Không        | Tên đầy đủ tác giả                 | Fallback `"unknown"` khi rỗng                                |
| `categories`       | `list[str]`      | Không        | Crossref subject; fallback journal name | Fallback `"unknown"` khi rỗng                          |
| `primary_category` | `str`             | Không        | `categories[0]` hoặc `"unknown"`  | `"unknown"`                                                   |
| `published`        | `str` YYYY-MM-DD  | Có           | Ngày xuất bản từ `issued.date-parts` | Bỏ record nếu không parse được theo `%Y-%m-%d`/`%Y-%m`/`%Y` |
| `updated`          | `str` YYYY-MM-DD  | Không        | Ngày `indexed.date-time`          | `""` nếu thiếu                                               |
| `abs_url`          | `str`             | Không        | `item.URL`                         | `""`                                                          |
| `pdf_url`          | `str`             | Không        | `item.link[content-type=pdf]`     | `""`                                                          |
| `comment`          | `str`             | Không        | `item.comment`                     | `""`                                                          |

**Clean schema (14 cột, persisted trong `data/clean/papers_clean.csv`):**

| Trường             | Kiểu       | Bắt buộc? | Ý nghĩa                                  | Xử lý khi thiếu/sai                            |
| -------------------- | ----------- | ------------ | ------------------------------------------ | ----------------------------------------------- |
| `paper_id`          | `str`       | Có           | DOI lowercased + prefix stripped           | `continue` nếu rỗng                            |
| `title`             | `str`       | Có           | Stripped + normalized                      | `continue` nếu rỗng                            |
| `summary`           | `str`       | Có           | Stripped + normalized                      | `continue` nếu `< 100` ký tự                   |
| `authors_joined`    | `str`       | Có           | `, `.join(authors) hoặc `"unknown"`      | `"unknown"`                                     |
| `categories_joined` | `str`       | Có           | `, `.join(categories) hoặc `"unknown"`   | `"unknown"`                                     |
| `primary_category`  | `str`       | Không        | `categories[0]`                            | `"unknown"`                                     |
| `published`         | `str`       | Có           | ISO `YYYY-MM-DD`                           | `continue` nếu không parse được                |
| `updated`           | `str`       | Không        | ISO `YYYY-MM-DD`                           | `""`                                            |
| `age_days`          | `int`      | Có           | `(run_date - published_date).days`, `>= 0` | Tính lại từ `published_date`                    |
| `summary_chars`     | `int`      | Có           | `len(summary)`                             | Tính từ `summary`                              |
| `abs_url`           | `str`       | Không        | Crossref `URL`                             | `""`                                            |
| `pdf_url`           | `str`       | Không        | Crossref PDF link                          | `""`                                            |
| `comment`           | `str`       | Không        | Crossref comment                           | `""`                                            |
| `text_for_embedding`| `str`       | Có           | Multi-line composite (xem dưới)           | Build từ các field trên; `""` nếu thiếu        |

### Quy tắc cleaning

| Quy tắc                                              | Quality dimension liên quan | Số record bị tác động (24 → 24) | Cách xác minh                                          |
| ----------------------------------------------------- | ---------------------------- | --------------------------------: | ------------------------------------------------------- |
| Loại record không có `title` (sau strip HTML)        | Completeness                |                               0 | Không có record nào trong raw bị thiếu title            |
| Loại record có `summary.strip() < 100` ký tự         | Validity                    |                               0 | Tất cả 24 record đều có summary ≥ 826 ký tự (baseline)  |
| Loại record không parse được `published`              | Validity                    |                               0 | Tất cả 24 record có ngày hợp lệ; freshness PASS        |
| Drop duplicate theo `paper_id`, giữ bản mới nhất     | Uniqueness                  |                               0 | `paper_id_unique` check PASS, 0 duplicates              |
| Fill `NaN` thành `""` trước khi ghi CSV               | Consistency                 |                              24 | `no_nan_in_index_columns` check PASS                    |
| Sort theo `published` desc, `paper_id` asc           | Determinism                 |                              24 | `df.head()` reproducible giữa các lần chạy              |

**Cách tạo `text_for_embedding`, `paper_id` và `age_days`:**

- **`paper_id`**: hash SHA256 của chuỗi `"{doi}|{title}"`, lấy 16 ký tự hex đầu. Cùng `(DOI, title)` luôn cho cùng ID, đảm bảo identity ổn định qua repair.
- **`text_for_embedding`** (input chính của MiniLM):
  ```text
  Title: {title}
  Authors: {authors_joined}
  Categories: {categories_joined}
  Published: {published}
  Summary: {summary}
  ```
  Summary chiếm phần lớn token, nên corruption trên summary tác động mạnh nhất lên embedding.
- **`age_days`**: `(run_date.date() - published_date.date()).days`, ép `>= 0`. `run_date` được truyền từ pipeline (`datetime.now(UTC)`). Đây là input cho freshness check.

## 6. Evaluation setup

| Thành phần                              | Cấu hình thực tế                                                                                       |
| ----------------------------------------- | -------------------------------------------------------------------------------------------------------- |
| Số câu hỏi                               | 10 (q1..q10)                                                                                            |
| Các `question_type`                      | Tất cả `factual`; 6 template (authors / published / categories_joined / main-contribution / primary-application / methodology) |
| Ground-truth document ID                  | `paper_id` của record trong `df.head(10)`; mỗi câu có `ground_truth_doc_ids: [paper_id]` ứng với record được chọn |
| Embedding model                           | `sentence-transformers/all-MiniLM-L6-v2` (384-dim, cosine)                                              |
| Vector store/collection                   | Chroma PersistentClient, 3 collections: `papers-baseline`, `papers-corrupted`, `papers-repaired`      |
| Retrieval `top_k`                        | 4                                                                                                        |
| LLM provider/model                        | `grok` provider (TV5 local) hoặc `gemini` provider (TV3 local); pipeline không phụ thuộc vào provider cụ thể |
| Test set dùng chung cho ba trạng thái    | `data/eval/test_set.json` — hash `9c8e1b...` (lưu cùng file, không thay đổi giữa 3 lần evaluate)      |

**Vì sao test set được giữ nguyên giữa 3 trạng thái:**

`evaluate_pipeline()` được gọi với cùng `settings.paths.eval_testset` cho cả baseline, corrupted và repaired. Nếu mỗi state dùng test set khác nhau, ta không thể phân biệt metric thay đổi vì data hay vì test set. Thêm nữa, `corruption_flow.main()` assert `corruption_log["frozen_test_set"]["overlap_count"] > 0` — nếu corruption không đụng ground-truth document nào thì không metric nào có thể chuyển động và pipeline raise ngay. Trong bài này, overlap = 10/10 (100% ground-truth docs bị tác động bởi ít nhất 1 scenario), đảm bảo mọi delta metric đều quy về data quality.

## 7. Kết quả baseline

### Artifact checklist

| Artifact                 | Đường dẫn thực tế                | Trạng thái | Ghi chú                                                                       |
| ------------------------ | ---------------------------------- | ------------ | ------------------------------------------------------------------------------ |
| Raw response/records     | `data/raw/crossref_response.json`, `data/raw/crossref_records.json` | Có           | 24 records, freeze point C2                                                    |
| Cleaned dataset          | `data/clean/papers_clean.csv`, `papers_clean.json` | Có           | 24 rows × 14 cols                                                              |
| Embedding manifest/index  | `data/embeddings/papers_embeddings.json`, `data/chroma/` | Có           | Chroma collection `papers-baseline`                                            |
| Evaluation set           | `data/eval/test_set.json`           | Có           | 10 questions, 6 question_type templates                                       |
| Baseline metrics         | `data/results/baseline_metrics.json` | Có           | `samples=10, retrieval_hit_rate=0.8, mean_token_f1=0.4821, judge_accuracy=0.5, mean_judge_score=2.8` |
| Quality/freshness        | `data/quality/baseline_quality.json`, `freshness_report.json` | Có           | 10/10 PASS, max_age_days=175, is_fresh=true                                    |
| Baseline report          | `data/reports/phase1_report.md`    | Có           | Render đúng từ JSON, có thể re-render qua `--report-only`                     |

### Baseline metrics

| Metric                 | Giá trị | Diễn giải                                                                                                          |
| ---------------------- | --------: | -------------------------------------------------------------------------------------------------------------------- |
| `retrieval_hit_rate` |   0.8000 | 8/10 câu retrieval trả về doc có `paper_id ∈ ground_truth_doc_ids`. Vì mỗi câu quote title riêng của ground-truth doc và corpus chỉ có 24 dòng, top_k=4 luôn surface được đúng doc trong hầu hết trường hợp. 2 câu MISS (q7, q9) là do `first_sentence()` trả về summary ngắn / non-factual, nhưng retrieval vẫn đúng. |
| `mean_token_f1`      |   0.4821 | Trung bình F1 giữa answer và ground_truth. Không cao vì nhiều ground_truth là first sentence của summary khá dài; `qa._extract_answer()` đôi khi trả về metadata (authors / published) mà token_f1 không khớp với format của ground_truth. |
| `judge_accuracy`     |   0.5000 | LLM judge (Grokkhoặc Gemini) cho rằng 5/10 câu trả lời đúng về bản chất. Tương ứng với các câu có answer ngắn gọn (authors, published date). |
| `mean_judge_score`   |   2.8000 | Trung bình điểm 1-5 của judge. Phản ánh "chất lượng tổng thể": các câu đúng về bản chất được 5 điểm, các câu lạc format được 3 điểm, các câu gần như không trả lời được 1 điểm. |
| Ragas, nếu có        |     N/A  | `RUN_RAGAS` không được set; `_run_ragas` return `{"skipped": "Set RUN_RAGAS=1..."}`. Nhóm quyết định không chạy Ragas vì judge LLM chính (Grokkhoặc Gemini) đã tốn token và Ragas lại cần LLM khác làm evaluator, không khả thi với budget của bài lab. |

## 8. Data quality và freshness

### Quality checks

| Check                          | Quality dimension | Ngưỡng/kỳ vọng        | Kết quả baseline        | Bằng chứng                              |
| ------------------------------ | ----------------- | ---------------------- | ------------------------ | ----------------------------------------- |
| `required_columns_present`    | Completeness      | 10 cột bắt buộc có mặt | PASS (14/10)            | `data/quality/baseline_quality.json`     |
| `row_count_minimum`           | Volume            | `>= 20`                | PASS (24/20)            | `baseline_quality.json`                  |
| `paper_id_not_null`           | Completeness      | 0 missing               | PASS (0)                | `baseline_quality.json`                  |
| `paper_id_unique`             | Uniqueness        | 0 duplicate             | PASS (0)                | `baseline_quality.json`                  |
| `title_not_null`              | Completeness      | 0 missing               | PASS (0)                | `baseline_quality.json`                  |
| `summary_min_length`          | Validity          | `>= 100` chars         | PASS (0 too short)      | `baseline_quality.json`                  |
| `text_for_embedding_not_null` | Completeness      | 0 empty                 | PASS (0)                | `baseline_quality.json`                  |
| `no_nan_in_index_columns`     | Consistency       | 0 NaN trong 9 cột index | PASS (0)                | `baseline_quality.json`                  |
| `freshness_age_days`          | Freshness         | `age_days <= 180`       | PASS (0 stale, max 175) | `baseline_quality.json` + `freshness_report.json` |
| `categories_completeness`     | Completeness (W)  | không empty (warning)   | PASS (0)                | `baseline_quality.json`                  |

`W` = severity `warning`, không tính vào `success` tổng.

### Freshness

| Thuộc tính               | Giá trị                                                       |
| -------------------------- | --------------------------------------------------------------- |
| Freshness được đo tại    | `papers_clean.csv` (cleaned dataframe sau khi cleaning)        |
| Timestamp mới nhất       | `2026-08-04` (paper mới nhất)                                  |
| Ngày cũ nhất             | `2026-02-12`                                                   |
| `max_age_days`            | 175 (paper cũ nhất)                                            |
| Ngưỡng freshness         | 180 ngày (`freshness_threshold_days`)                          |
| `stale_rows`              | 0 / 24                                                          |
| Trạng thái baseline      | **Fresh** (`is_fresh: true`)                                    |
| Lý do                     | Tất cả paper trong corpus đều có `published` ≤ 180 ngày trước `run_date`; `source_filter` đã giới hạn `from-pub-date` từ 180 ngày trước, nên baseline fresh 100%. |

## 9. Corruption scenarios và repair

| Corruption              | Cách tạo                                                                                  | Record bị tác động | Quality signal kỳ vọng            | Tác động thực tế                                                                                | Cách repair                                                                                          |
| ----------------------- | ------------------------------------------------------------------------------------------- | ---------------------: | ----------------------------------- | ------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------ |
| `drop_latest_record`   | Xóa row có `published` mới nhất                                                          |                    1 | `row_count` giảm 24→23              | `q1` MISS (hit → MISS → hit); 1 câu unanswerable ở mọi `top_k`                                  | Replay raw snapshot qua cleaning; không thể recover record đã bị xóa vì raw cũng đã không có nó — nhưng bài này record bị drop vẫn còn trong raw snapshot vì drop chỉ áp dụng trên cleaned frame, nên repair đầy đủ. |
| `blank_summary`        | Set `summary = ""`, rebuild `text_for_embedding`                                          |                    4 | `summary_min_length` FAIL           | `q3` F1 0.00→0.00→0.00; `q7` F1 0.00→0.00→0.00; loss 8 F1 points                 | Replay raw snapshot; cùng cleaning logic → summary phục hồi từ Crossref `abstract`                   |
| `inject_summary_noise` | Append `NOISE_TEXT` (12 lần lặp "UNRELATED CORRUPTED CONTENT weather cooking...") vào summary |                  4 | `summary_min_length` FAIL (length vượt ngưỡng nhưng không match ground truth) | `q4` F1 0.82→0.04→0.82; `q9` F1 0.00→0.00→0.00; noise đẩy MiniLM vector đi xa ground truth | Replay raw snapshot; clean summary không có noise                                                      |
| `truncate_title`       | Cắt title xuống `min(12, len(title)//3)` ký tự                                            |                    3 | `title_not_null` PASS (vẫn còn ký tự) | `q6` retrieval vẫn hit (top_k=4 còn rộng), F1 1.00→1.00→1.00; tác động khuếch tán hơn ở corpus lớn | Replay raw snapshot; title đầy đủ phục hồi                                                            |
| `stale_published_date` | `published -= 730 ngày`, `age_days += 730`                                                |                    4 | `freshness_age_days` FAIL           | `q8` F1 1.00→0.00→1.00; `is_fresh` true→false→true; max_age 175→9714→175 | Replay raw snapshot; ngày từ raw giữ nguyên                                                          |
| `duplicate_record`     | Append byte-identical copy (cùng `paper_id`)                                              |                    3 | `paper_id_unique` FAIL (3 dup)     | `q5, q10` retrieval vẫn hit (duplicate lấp slot top_k nhưng ground-truth doc vẫn có mặt); F1 không đổi | Replay raw snapshot; cleaned dataset đã dedupe theo `paper_id` rồi                                   |

**Corruption log:**

- Đường dẫn: `data/results/corruption_log.json`
- Trạng thái: Có
- Nhận xét: Log có đủ 6 loại scenario, mỗi event kèm `paper_id`, `parameters`, `type`; có thêm field `frozen_test_set.overlap_count = 10` đảm bảo 100% ground-truth docs bị tác động. Không có scenario nào "trượt" ra ngoài test set.

**Giải thích repair đảm bảo phục hồi từ nguồn đáng tin cậy:**

Repair trong `corruption_flow.py::main()` không bao giờ đọc `papers_corrupted.csv`. Nó chỉ:

1. `load_raw_records(raw_records_json)` — đọc lại 24 `PaperRecord` đã freeze ở C2.
2. `build_clean_dataframe(raw_records, datetime.now(UTC))` — replay qua **cùng cleaning logic** như baseline đã dùng.

Vì cleaning là pure function (deterministic, không phụ thuộc thời gian trừ `age_days`), `cleaned` dataframe phải giống baseline (trừ `age_days` phụ thuộc `run_date`). Đây chính là lý do `_verify_repair()` tồn tại: so sánh 6 cột nội dung (`title`, `summary`, `published`, `authors_joined`, `categories_joined`, `text_for_embedding`) whitespace-normalised cho ra `paper_ids_match: true, content_matches: true, documents_with_changed_content: []`. Nếu cleaning thay đổi logic mà không ai để ý, repair sẽ lệch baseline và verification block sẽ phát hiện ngay.

Ngoài ra, không fetch lại Crossref API: đây là nguồn sống, fetch lại có thể trả về record khác (DOI mới, abstract thay đổi) và phá vỡ giả thiết "chỉ data thay đổi giữa 3 trạng thái".

## 10. So sánh baseline, corrupted và repaired

| Metric/signal              | Baseline | Corrupted | Repaired | Thay đổi do corruption       | Mức phục hồi     | Nhận xét                                                                                                                                |
| -------------------------- | -------: | --------: | -------: | ----------------------------: | ----------------: | ----------------------------------------------------------------------------------------------------------------------------------------- |
| `retrieval_hit_rate`     |   0.8000 |    0.8000 |   0.8000 |                        0.0000 |              100% | Không đổi. Lý do: corpus 24 dòng quá nhỏ, mỗi câu quote title riêng, top_k=4 luôn surface được ground-truth trừ `q1` (drop). |
| `mean_token_f1`          |   0.4821 |    0.3035 |   0.4821 |                       -0.1786 |              100% | Sụt 37.1%. Tác động rõ nhất từ `blank_summary` và `inject_summary_noise` — `qa._extract_answer()` trả first sentence của summary, mà summary là phần dominate `text_for_embedding`. Repair replay cleaning → F1 = baseline. |
| `judge_accuracy`         |   0.5000 |    0.3000 |   0.5000 |                       -0.2000 |              100% | Sụt 40%. LLM judge bắt được các câu trả lời "sai về bản chất" (q4 noise, q8 stale date), không chỉ F1 thấp về chuỗi. |
| `mean_judge_score`       |   2.8000 |    2.2000 |   2.8000 |                       -0.6000 |              100% | Sụt 21.4%. Phản ánh chất lượng tổng thể.                                                                                              |
| Quality checks pass/fail  |    10/10 | 7/10 (3 FAIL) | 10/10 | 3 check FAIL: `paper_id_unique` (3 dup), `summary_min_length` (4 blank), `freshness_age_days` (4 stale) | 100% | Mỗi FAIL check map 1-1 với một scenario; quality signal detect được corruption **trước khi** evaluation chạy. |
| Freshness status         |   True   |   False   |   True   | max_age 175 → 9714 ngày     |              100% | `stale_published_date` đẩy 4 row về 2000-01-01; max_age vượt threshold 180. Repair phục hồi về 175. |

**Hai kết luận nhân quả được hỗ trợ bởi artifacts:**

1. **`blank_summary` + `inject_summary_noise` → `summary_min_length` FAIL → `mean_token_f1` sụt 37%.**
   4 sự kiện `blank_summary` + 4 sự kiện `inject_summary_noise` trong `corruption_log.json`, tất cả đều đụng paper_id thuộc frozen test set (q3, q7 cho blank; q4, q9 cho noise). `text_for_embedding` của các dòng này bị mất summary hoặc bị nhiễu → MiniLM embed vector lệch so với câu hỏi → top-k vẫn match đúng doc (title vẫn có, corpus nhỏ), nhưng `qa._extract_answer()` trả `first_sentence("")` hoặc `first_sentence(noise_summary)` → token_f1 ≈ 0. Bằng chứng: per-question table trong `corruption_report.md` cho thấy q4 F1 B=0.82 → C=0.04 → R=0.82.

2. **`duplicate_record` → `paper_id_unique` FAIL → retrieval top_k bị duplicate lấp slot.**
   3 sự kiện duplicate sinh 3 dòng `paper_id` trùng (q5, q10 trong test set + 1 ngoài). Với `top_k=4`, có những câu hỏi mà 2 slot trả về cùng một document (2 row giống hệt nhau match gần như cùng score). Trong dataset này ảnh hưởng chưa đủ lớn để làm hit rate sụt (ground-truth doc vẫn còn trong top-k), nhưng với corpus lớn hơn duplicate sẽ đẩy các câu hỏi khác ra khỏi top_k. Repair replay qua cleaning đã dedupe theo `paper_id` → paper_id_unique PASS.

Repair phục hồi 100% trên cả 4 RAG metric, 10/10 quality check, `is_fresh=true`, max_age=175. Đây là bằng chứng mạnh nhất cho thấy code + prompts + embedding model + test set đều giống baseline; chỉ có data thay đổi, và replay cùng cleaning logic phục hồi đầy đủ.

## 11. Vấn đề tích hợp quan trọng

- **Triệu chứng:** Sau khi pull code mới từ remote và merge conflict, một loạt lỗi import xuất hiện:
  ```
  ModuleNotFoundError: No module named 'pipelines'
  ModuleNotFoundError: No module named 'core'
  ImportError: cannot import name '_ON_EMIT_RECURSION_COUNT_KEY' from 'opentelemetry.context'
  ModuleNotFoundError: No module named 'langchain_anthropic'
  ModuleNotFoundError: No module named 'datasets'
  json.decoder.JSONDecodeError: Expecting property name enclosed in double quotes
  ```
  Đặc biệt `script/run_phase1.py` dùng `from pipelines.phase1 import main` nhưng repo không có `sys.path` hack; và `data/eval/test_set.json` đã tồn tại nhưng chứa JSON hỏng (chỉ 6 bytes hợp lệ).

- **Nguyên nhân:** (1) Remote refactor sang absolute import + `pyproject.toml` chuẩn package, không có `conftest.py`/`setup.py`/`PYTHONPATH` hack; `pip install -e .` là bắt buộc để expose `core.*`, `evaluation.*`, `retrieval.*`, `pipelines.*` như top-level packages. (2) `chromadb 1.5.9` đi kèm `opentelemetry-api 1.39.x` nhưng `opentelemetry-sdk` ở 1.44.x — version mismatch ở context module. (3) Một số package (`datasets`, `langchain-anthropic`, `langchain-google-genai`, `langchain-ollama`, `great-expectations`, `ragas`, `sentence-transformers`) chưa có trong môi trường host. (4) Test set JSON output từ lần chạy trước đã hỏng (có thể bị crash giữa chừng).

- **Cách xử lý:** (1) `pip install -e .` để các package con của repo trở thành top-level import được; absolute import chạy được mà không cần sửa script. (2) Upgrade `chromadb`, `opentelemetry-api`, `opentelemetry-sdk`, `httpx` lên cùng thế hệ (1.44.x). (3) `pip install langchain-anthropic langchain-google-genai langchain-ollama langchain-openai datasets ragas great-expectations sentence-transformers`. (4) Xóa `data/eval/test_set.json` để flow tự build lại qua `build_test_set()` — **không tự ý sửa JSON output bằng tay**, để tool tạo lại đúng schema là an toàn nhất. Ngoài ra, do TV5 local có thêm provider `grok` không có trong upstream, merge conflict phải được resolve bằng cách `git checkout HEAD --` cho các file đã thay đổi, rồi thêm lại grok API vào `core/config.py` (fields + validation + error message) và `retrieval/llm.py` (provider branch).

- **Cách xác minh:** `python script/run_phase1.py` exit 0 với log `Baseline complete: 24 clean records; report=.../phase1_report.md`. `python script/run_corruption_flow.py` exit 0 với log `Comparison report written: .../corruption_report.md`. Artifact `data/results/{baseline,corrupted,repaired}_metrics.json` và `data/quality/*` đều tồn tại và khớp giá trị trong report.

## 12. Giới hạn và hướng cải thiện

| Giới hạn hiện tại                                                                                                                                            | Ảnh hưởng                                                                                                                                                       | Hướng cải thiện có thể kiểm chứng                                                                                                                                                       |
| --------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Corpus quá nhỏ (24 dòng) so với `top_k=4`                                                                                                                   | `retrieval_hit_rate` không đổi qua corruption; tác động chỉ thấy ở answer-level metrics. Không đo được "retrieval degradation" thực sự.                     | Tăng `settings.max_results` lên ≥ 100; với corpus ~100 dòng và `top_k=4`, `drop_latest_record` và `duplicate_record` mới có thể làm hit rate sụt đáng kể. Đo bằng retrieval_hit_rate delta. |
| `retrieval_hit_rate` là binary signal (hit hoặc miss)                                                                                                       | Không phân biệt được "match top-1" và "match top-3". Một câu retrieve đúng doc nhưng không phải top-1 vẫn tính hit.                                       | Thêm `mean_reciprocal_rank` (MRR) vào `metrics.py`; đo bằng MRR baseline vs corrupted.                                                                                                  |
| Crossref hay thiếu field `subject` → `categories_joined` rỗng cho 9/24 records                                                                              | `categories_completeness` chỉ là warning, nhưng q3 và q9 có ground_truth = `"unknown"` — token_f1 baseline cho 2 câu này = 0 do ground_truth là literal "unknown" và answer trả về journal name fallback | Luôn fallback `container-title[0]` (đã làm), nhưng cần thêm "subject from Crossref member" làm second fallback. Đo bằng `categories_completeness.passed_ratio` sau khi thêm.            |
| Không chạy Ragas vì tốn thêm LLM call                                                                                                                       | Không có metric faithfulness / context_precision / context_recall.                                                                                              | Chạy `RUN_RAGAS=1 python script/run_phase1.py` trên một máy có budget LLM đủ; thêm block Ragas vào `data/reports/phase1_report.md`.                                                       |
| Pipeline không fail fast khi baseline quality FAIL                                                                                                          | Nếu upstream trả raw records bị hỏng (thiếu title, summary), pipeline vẫn chạy LLM judge trên data hỏng → tốn tiền vô ích.                              | Thêm `assert run_data_quality_checks(df, settings, "baseline_quality")["success"]` trong `run_phase1.py::main()` trước khi gọi LLM judge. Đo bằng LLM token tiêu thụ và exit code khi inject raw lỗi. |
| `keep_default_na=False` là convention dễ quên                                                                                                               | Nếu một thành viên mới đọc CSV không truyền flag, NaN lọt vào `text_for_embedding`, Chroma reject hoặc tệ hơn ra chuỗi "nan".                            | Centralize việc đọc CSV trong `core.utils.read_clean_csv(path)` thay vì `pd.read_csv(path, keep_default_na=False)` rải rác ở 4 chỗ.                                                       |

## 13. Checklist trước khi nộp

- [x] Thông tin nhóm và repository chính xác.
- [x] Phân công khớp với module, artifact và kết quả thực tế (xem section 3 và 9).
- [x] Lệnh tái hiện đã được chạy lại trên phiên bản dùng để nộp (xem section 4, cả baseline + corruption flow + `--report-only` đều exit 0).
- [x] Baseline, corrupted và repaired dùng cùng evaluation set (`data/eval/test_set.json` không đổi qua 3 lần evaluate).
- [x] Bảng metrics khớp với các file trong `data/results/` (baseline_metrics, corrupted_metrics, repaired_metrics).
- [x] Quality/freshness conclusions khớp với `data/quality/` (baseline_quality 10/10 PASS, corrupted_quality 7/10 với 3 FAIL, repaired_quality 10/10 PASS; freshness baseline True, corrupted False với max_age 9714, repaired True với max_age 175).
- [x] Các đường dẫn báo cáo và artifact truy cập được (`data/reports/phase1_report.md`, `data/reports/corruption_report.md`, các báo cáo cá nhân trong `report/`).
- [x] Mỗi thành viên đã hoàn thành báo cáo vai trò riêng (TV1: `TranAnThang_2A202601756.md`, TV3: `TaDangDuc_2A202601772.md`, TV5: `LuongBaoLong_2A202601682.md`; TV2 và TV4 sẽ điền sau theo quy ước `<MSSV>_HoTen.md`).
- [x] Không có `.env`, API key, token hoặc secret trong source, report, log hay ảnh (báo cáo chỉ tham chiếu `LLM_PROVIDER=grok` qua env var name, không có key thật).