# Member Role Report — Day 10: Data Pipeline & Data Observability

> Thành viên 5 trong nhóm VuaTuat — chịu trách nhiệm chính cho orchestration, reproducibility và kiểm tra sự nhất quán giữa report với artifact. Báo cáo này tập trung vào hai flow pipeline end-to-end (`phase1` và `corruption_flow`), lệnh chạy, bằng chứng tích hợp và reproducibility.

## 1. Thông tin cá nhân

| Thông tin       | Nội dung                                                                                |
| --------------- | ---------------------------------------------------------------------------------------- |
| Họ và tên       | Lương Bảo Long                                                                          |
| MSSV            | 2A202601682                                                                              |
| Khóa/Lớp        | K4                                                                                       |
| Tên nhóm        | VuaTuat                                                                                  |
| Vai trò chính   | Thành viên 5 — Pipeline integration & evidence owner                                     |
| Repository      | https://github.com/benmentran/K4_Day10_Data-Pipeline-Data-Observability-VuaTuat           |
| Ngày hoàn thành | 2026-08-06                                                                                |

## 2. Vai trò và phạm vi công việc

### Phần việc sở hữu

| Module/deliverable                  | File/hàm phụ trách                                                     | Input nhận vào                                                    | Output bàn giao                                                                                          | Trạng thái        |
| ----------------------------------- | ----------------------------------------------------------------------- | ------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------- | ----------------- |
| Baseline orchestration             | `src/pipelines/phase1.py::main()`, `build_baseline_report()`           | `Settings`, `data/raw/crossref_records.json` hoặc Crossref API    | `data/clean/papers_clean.csv`, embeddings, metrics, quality, freshness, `data/reports/phase1_report.md`  | Hoàn thành        |
| Corruption + repair + comparison   | `src/pipelines/corruption_flow.py::main()`, `build_comparison_report()` | `Settings`, frozen test set, baseline CSV, raw snapshot             | `papers_corrupted.csv`, `papers_clean_repaired.csv`, 3 bộ metrics, 3 bộ quality, `corruption_report.md`    | Hoàn thành        |
| Repair verification                 | `_verify_repair()`                                                     | baseline + repaired DataFrames, `Settings`                          | Dict `repair_verification` (paper_ids_match, content_matches, missing_after_repair)                       | Hoàn thành        |
| CLI cho cả hai flow                | `script/run_phase1.py`, `script/run_corruption_flow.py`                | CLI flags (`--report-only`)                                         | Lệnh chạy có thể tái hiện                                                                                | Hoàn thành        |
| End-to-end reproducibility         | `pyproject.toml`, `pip install -e .`                                    | Python 3.11, environment file                                       | Môi trường chạy có thể reproduce từ máy sạch                                                             | Hoàn thành        |
| Consistency check giữa report và artifact | Cross-check giữa `*.md` reports và `*.json` artifacts              | reports, metrics, quality, freshness, corruption log                | Bảng đối chiếu giá trị (Section 3, 8)                                                                     | Hoàn thành        |

Tôi không nhận ownership cho `crossref.py` (TV1), `cleaning.py`/`testset.py` (TV2), `quality.py`/`reporting.py` (TV3) hay `corruption.py` (TV4). Phần việc của tôi đứng ở điểm hội tụ: nhận output của các module trên, nối chúng thành hai flow chạy ổn định, và xác minh rằng những gì report nói ra đều có trên disk.

### Việc hỗ trợ ngoài phạm vi chính

| Hoạt động                                          | Thành viên/module được hỗ trợ                              | Kết quả                                                                                          |
| --------------------------------------------------- | ------------------------------------------------------------- | ------------------------------------------------------------------------------------------------- |
| Resolve merge conflict sau khi pull remote            | Toàn nhóm                                                    | Code remote được sync, grok API trong `core/config.py` và `retrieval/llm.py` được giữ nguyên       |
| Cài `langchain-anthropic`, `langchain-google-genai`, `langchain-ollama`, `datasets`, `ragas`, `great-expectations` | Toàn nhóm                                                    | Pipeline import sạch, không còn `ModuleNotFoundError` cho `chromadb`/`langchain_anthropic`/`datasets` |
| Upgrade `chromadb`/`opentelemetry-api`/`opentelemetry-sdk`/`httpx` | Toàn nhóm                                                    | Fix `ImportError: _ON_EMIT_RECURSION_COUNT_KEY` từ `chromadb.telemetry.opentelemetry`              |
| `pip install -e .` để expose `core.*`, `evaluation.*`, `retrieval.*`, `pipelines.*` | Toàn nhóm                                                    | `script/run_phase1.py` dùng absolute import (không prefix `src.`) chạy được mà không cần PYTHONPATH hack |
| Xóa test set JSON hỏng để test set được tạo lại sạch | TV2 (test set owner)                                         | Tránh lỗi `json.decoder.JSONDecodeError` khi `evaluate_pipeline` đọc test set                       |

## 3. Kết quả theo vai trò

| Nhiệm vụ đã thực hiện                                                       | File/hàm/artifact liên quan                                                  | Kết quả bàn giao                                                          | Cách xác minh                                                                    |
| ---------------------------------------------------------------------------- | ------------------------------------------------------------------------------ | -------------------------------------------------------------------------- | --------------------------------------------------------------------------------- |
| Chạy baseline pipeline end-to-end                                             | `python script/run_phase1.py`                                                 | 24/24 clean records, report viết ra                                        | Log "Baseline complete: 24 clean records; report=.../phase1_report.md"            |
| Chạy corruption + repair + comparison end-to-end                              | `python script/run_corruption_flow.py`                                        | 3 bộ metrics + 3 bộ quality + comparison report                             | Log "Comparison report written: .../corruption_report.md"                          |
| Tái dựng baseline report từ artifact có sẵn (không cần re-evaluate)            | `script/run_phase1.py --report-only`                                          | `phase1_report.md` được render lại đúng từ JSON                             | `python script/run_phase1.py --report-only` → "Baseline report written"            |
| Tái dựng comparison report từ artifact có sẵn                                  | `script/run_corruption_flow.py --report-only`                                 | `corruption_report.md` được render lại đúng từ JSON                         | `python script/run_corruption_flow.py --report-only` → "Comparison report written"  |
| Verify repair thực sự khôi phục baseline content                                | `_verify_repair()` được gọi trong `build_comparison_report`                   | `paper_ids_match: true`, `content_matches: true`, missing_after_repair=[] | Bảng "Repair verification" trong `corruption_report.md`                             |
| Đảm bảo 3 trạng thái dùng cùng frozen test set                                | `evaluate_pipeline()` được gọi với cùng `settings.paths.eval_testset` cho cả 3 | `samples: 10` ở cả 3 file metrics, cùng `q01..q10`                         | `data/results/{baseline,corrupted,repaired}_metrics.json`                         |

**Output cụ thể mà phần việc của tôi tạo ra:**

Tôi đứng ra đảm bảo các con số trong báo cáo không mâu thuẫn với disk. Bảng đối chiếu dưới đây là bằng chứng tích hợp chính mà tôi chịu trách nhiệm:

| Giá trị trong report    | Artifact trên disk                                          | Khớp? |
| ----------------------- | ------------------------------------------------------------ | ----- |
| Baseline 24 clean       | `data/clean/papers_clean.csv` có 24 dòng                      | ✅    |
| Corrupted 26 rows       | `data/clean/papers_corrupted.csv` có 26 dòng                  | ✅    |
| Repaired 24 rows        | `data/clean/papers_clean_repaired.csv` có 24 dòng             | ✅    |
| `retrieval_hit_rate = 0.8` ở cả 3 | `data/results/{baseline,corrupted,repaired}_metrics.json` | ✅    |
| `mean_token_f1` 0.4821 → 0.3035 → 0.4821 | `data/results/*_metrics.json`                        | ✅    |
| Quality baseline PASS 10/10 | `data/quality/baseline_quality.json` (`passed_checks: 10`) | ✅    |
| Quality corrupted FAIL 3 check | `data/quality/corrupted_quality.json` (`paper_id_unique`, `summary_min_length`, `freshness_age_days`) | ✅    |
| Fresh baseline max_age 175 | `data/quality/freshness_report.json`                       | ✅    |
| Fresh corrupted max_age 9714 | `data/quality/corrupted_freshness.json`                    | ✅    |
| Repair `paper_ids_match: true`, `content_matches: true` | block "Repair verification" trong `corruption_report.md` | ✅    |

## 4. Giải thích phần kỹ thuật đã thực hiện

### Vấn đề cần giải quyết

Hai file pipeline (`phase1.py`, `corruption_flow.py`) phải:

1. **Chạy được end-to-end** với một lệnh duy nhất, từ raw snapshot đến comparison report.
2. **Không che giấu lỗi** — mọi artifact thiếu phải ném exception có thông điệp cụ thể.
3. **Đảm bảo tính nhất quán** giữa ba trạng thái (baseline, corrupted, repaired) bằng cách dùng cùng test set và cùng embedding model.
4. **Verify được** rằng repair thực sự khôi phục baseline, không phải chỉ là "tạo ra một dataset mới có cùng số dòng".
5. **Tái hiện được** — chạy lại `--report-only` từ artifact đã có, không cần gọi lại LLM judge hay Crossref API.

### Cách triển khai

**1. Phase 1 — Baseline pipeline (`src/pipelines/phase1.py::main`):**

Thứ tự thực thi cố định, mỗi bước ghi artifact xuống đĩa trước khi sang bước tiếp theo:

```
load_settings
  -> fetch_source_records(settings)            # nếu refresh_source hoặc chưa có raw_records_json
  -> build_clean_dataframe(records, now, settings)   # ghi clean_csv, clean_json
  -> LocalEmbeddingIndex.build(df, settings, embeddings_json)
  -> build_test_set(df, eval_testset)          # nếu refresh_test_set hoặc chưa có
  -> evaluate_pipeline(...)                    # ghi baseline_metrics.json, baseline_answers.json
  -> run_data_quality_checks(df, settings, "baseline_quality")
  -> build_freshness_report(df, settings, freshness_report)
  -> generate_phase1_report(baseline_report, ...)
```

Mỗi bước đều **ghi artifact trước khi gọi bước tiếp theo**. Nếu bước nào fail, ta biết artifact nào đang "có giá trị nhất" (latest valid artifact) và `phase1_report.md` có thể được tái dựng mà không cần chạy lại LLM judge. Đây là lý do `build_baseline_report()` tồn tại.

**2. Phase 2 — Corruption + repair + comparison (`src/pipelines/corruption_flow.py::main`):**

```
load_settings
  -> đọc baseline CSV (keep_default_na=False, lý do ở mục 6)
  -> corrupt_clean_dataframe(baseline, corruption_log,
                             test_set_path=eval_testset)
  -> write_csv(corrupted, corrupted_clean_csv)
  -> LocalEmbeddingIndex.build(corrupted, ..., corrupted_embeddings_json)
  -> evaluate_pipeline(settings, corrupted_index, eval_testset,
                       corrupted_metrics, corrupted_answers)
  -> run_data_quality_checks(corrupted, settings, "corrupted_quality")
  -> build_freshness_report(corrupted, ..., corrupted_freshness.json)
  -- Phase 2b: repair --
  -> load_raw_records(raw_records_json)        # KHÔNG đọc lại papers_corrupted.csv
  -> build_clean_dataframe(raw_records, now)
  -> write_csv(repaired, repaired_clean_csv)
  -> LocalEmbeddingIndex.build(repaired, ..., repaired_embeddings_json)
  -> evaluate_pipeline(settings, repaired_index, eval_testset,
                       repaired_metrics, repaired_answers)
  -> run_data_quality_checks(repaired, settings, "repaired_quality")
  -> build_freshness_report(repaired, ..., repaired_freshness.json)
  -- Phase 2c: comparison --
  -> build_comparison_report(settings)
       -> _verify_repair(baseline_df, repaired_df, settings)
       -> generate_corruption_report(...)
```

**3. `_verify_repair()` — đây là phần kỹ thuật tôi chịu trách nhiệm chính:**

Repair không có ý nghĩa nếu nó chỉ "tạo ra 24 dòng mới có summary". `_verify_repair()` so sánh baseline và repaired trên 6 cột nội dung (`title`, `summary`, `published`, `authors_joined`, `categories_joined`, `text_for_embedding`), whitespace-normalised, để:

- Loại bỏ nhiễu CRLF/LF khỏi round-trip CSV (khiến MiniLM vẫn embed giống nhau nhưng so sánh byte lại lệch).
- Phát hiện paper_id bị mất hoặc xuất hiện trong repaired mà baseline không có.
- Phát hiện nội dung bị thay đổi (ví dụ cleaning logic đổi nhưng không ai để ý).

Nếu bất kỳ field nào lệch, block `Repair verification` trong `corruption_report.md` sẽ in ra `documents_with_changed_content: [...]` — không thể bị "lấp liếm" bằng một con số tổng.

**4. CLI flags `--report-only`:**

Cả `run_phase1.py` và `run_corruption_flow.py` đều có flag `--report-only`. Khi bật, flow chỉ đọc JSON/CSV đã có trên đĩa và render lại Markdown. Đây là cách:

- Tránh tốn tiền gọi lại LLM judge khi chỉ muốn xem lại report.
- Bắt buộc `generate_phase1_report` / `generate_corruption_report` phải tự đủ từ JSON — một dạng "contract test" cho reporting.

**5. `keep_default_na=False` cho mọi lần đọc CSV:**

Mọi chỗ đọc `papers_corrupted.csv` đều truyền `keep_default_na=False`. Lý do: khi corruption blank summary thành `""`, nếu `pd.read_csv` mặc định parse `""` thành `NaN`, NaN sẽ lọt vào `text_for_embedding`, và:

- Chroma reject metadata vì `NaN` không phải JSON-serializable.
- Hoặc tệ hơn, `astype(str)` của NaN ra chuỗi `"nan"`, làm hỏng embedding input.

`keep_default_na=False` ép `""` phải là `""`, để quality check `summary_min_length` có thể phát hiện đúng scenario `blank_summary`.

### Input, output và contract

| Thành phần                    | Mô tả                                                                                              |
| ------------------------------ | ---------------------------------------------------------------------------------------------------- |
| Input (phase1)                 | `data/raw/crossref_records.json` hoặc Crossref API                                                  |
| Input (corruption_flow)        | `data/clean/papers_clean.csv`, `data/raw/crossref_records.json`, `data/eval/test_set.json`         |
| Output (phase1)                | `data/clean/papers_clean.csv`, `data/embeddings/papers_embeddings.json`, `data/eval/test_set.json`, `data/results/baseline_{metrics,answers}.json`, `data/quality/baseline_quality.json`, `data/quality/freshness_report.json`, `data/reports/phase1_report.md` |
| Output (corruption_flow)       | Tất cả artifact trên + `papers_corrupted.{csv,json}`, `papers_embeddings_corrupted.json`, `papers_clean_repaired.{csv,json}`, `papers_embeddings_repaired.json`, `corrupted_{metrics,answers}.json`, `repaired_{metrics,answers}.json`, `corrupted_quality.json`, `repaired_quality.json`, `corrupted_freshness.json`, `repaired_freshness.json`, `data/results/corruption_log.json`, `data/reports/corruption_report.md` |
| Module phụ thuộc               | `core.config`, `core.utils`, `ingestion.crossref/cleaning/corruption`, `retrieval.index`, `evaluation.metrics`, `observability.quality/reporting` |
| Module sử dụng output         | Toàn bộ nhóm (mọi thành viên đều đọc `data/results/*_metrics.json` và `data/quality/*.json` để viết báo cáo) |
| Điều kiện lỗi cần xử lý        | Thiếu artifact phase 1 khi chạy phase 2 → `FileNotFoundError` với danh sách file cụ thể; cleaning rỗng → `RuntimeError`; test set không overlap với corruption → `RuntimeError` yêu cầu inspect `corruption_log.json` |

### Cách xác minh

```bash
# Cài môi trường một lần
pip install -e .

# Baseline
python script/run_phase1.py

# Tái dựng report baseline không cần re-evaluate
python script/run_phase1.py --report-only

# Corruption + repair + comparison
python script/run_corruption_flow.py

# Tái dựng comparison report không cần re-evaluate
python script/run_corruption_flow.py --report-only
```

- **Kết quả mong đợi:**
  - Phase 1: log `Baseline complete: 24 clean records`, file `data/reports/phase1_report.md` tồn tại.
  - Phase 2: log `Comparison report written: .../corruption_report.md`, 9 file JSON mới (3× metrics + 3× quality + 3× freshness) + 3 CSV + 1 corruption log.
  - `--report-only` ở cả 2 flow phải thành công khi artifact đã tồn tại, thất bại có thông điệp rõ ràng khi thiếu artifact.
- **Kết quả thực tế:**
  - Phase 1: ✅ đã chạy, in đúng log, `data/reports/phase1_report.md` render đúng bảng metrics + bảng 10 check.
  - Phase 2: ✅ đã chạy, `data/reports/corruption_report.md` render đủ 6 mục, block "Repair verification" có `paper_ids_match: true`, `content_matches: true`.
  - `--report-only` ở cả 2 flow: ✅ chạy lại thành công, hai file markdown được ghi đè với cùng nội dung.
- **Artifact/log:** `data/reports/phase1_report.md`, `data/reports/corruption_report.md`. Không chứa secret.

## 5. Một quyết định kỹ thuật quan trọng

- **Bối cảnh:** Repair phase cần khôi phục baseline corpus, nhưng nguồn nào để replay?
- **Các phương án đã cân nhắc:**
  1. Đọc lại `papers_corrupted.csv` và "sửa ngược" từng corruption scenario.
  2. Fetch lại Crossref API bằng cùng query/filter như baseline.
  3. **Replay `data/raw/crossref_records.json` qua cùng `build_clean_dataframe()` như baseline đã dùng.**
- **Phương án đã chọn:** Phương án 3.
- **Lý do:**
  - **Correctness:** Crossref là nguồn sống, fetch lại có thể trả về record khác (DOI mới, abstract thay đổi). Điều này phá vỡ giả thiết "chỉ data thay đổi giữa 3 trạng thái" — vốn là điều kiện tiên quyết để mọi chênh lệch metric quy được về data quality.
  - **Reproducibility:** raw snapshot đã được freeze ở C2; chỉ cần đọc lại file đó là đủ.
  - **Consistency:** dùng cùng `build_clean_dataframe()` đảm bảo schema, threshold (`MIN_SUMMARY_CHARS`, `freshness_threshold_days`), drop rules đều giống baseline. Nếu cleaning đổi logic, ta phát hiện ngay qua `_verify_repair()`.
  - **Cost:** không tốn thêm một lần gọi Crossref.
- **Bằng chứng quyết định phù hợp:** Block `Repair verification` trong `corruption_report.md` cho cùng kết quả `paper_ids_match: true, content_matches: true, documents_with_changed_content: []` sau mỗi lần chạy, với điều kiện raw snapshot không bị đụng.

## 6. Một lỗi hoặc blocker đã xử lý

- **Triệu chứng/lỗi nguyên văn:**
  ```
  ModuleNotFoundError: No module named 'pipelines'
  ModuleNotFoundError: No module named 'core'
  ModuleNotFoundError: No module named 'langchain_anthropic'
  ImportError: cannot import name '_ON_EMIT_RECURSION_COUNT_KEY' from 'opentelemetry.context'
  ModuleNotFoundError: No module named 'datasets'
  json.decoder.JSONDecodeError: Expecting property name enclosed in double quotes: line 3 column 1 (char 6)
  ```
- **Lệnh hoặc bước tái hiện:** `python script/run_phase1.py`
- **Nguyên nhân gốc:**
  1. Hai file `script/run_phase1.py` và `script/run_corruption_flow.py` dùng absolute import (`from pipelines.phase1 import main`), nhưng repo không cung cấp `conftest.py` / `setup.py` / `sys.path` hack; `pyproject.toml` định nghĩa `[tool.setuptools] package-dir = {"" = "src"}` để `pip install -e .` mới expose được `pipelines.*`.
  2. `chromadb 1.5.9` đi kèm `opentelemetry-api 1.39.x` nhưng `opentelemetry-sdk` ở 1.44.x — context module bị version mismatch, không tìm thấy `_ON_EMIT_RECURSION_COUNT_KEY`.
  3. Một số package (`datasets`, `langchain-anthropic`, `langchain-google-genai`, `langchain-ollama`, `great-expectations`, `ragas`, `sentence-transformers`) chưa có trong môi trường host mặc dù có trong `requirements.txt`.
  4. `data/eval/test_set.json` đã tồn tại nhưng chứa JSON hỏng (chỉ có 6 bytes hợp lệ), khiến `evaluate_pipeline` fail.
- **Cách xử lý:**
  1. `pip install -e .` để `core.*`, `evaluation.*`, `retrieval.*`, `pipelines.*` được expose như top-level packages. Sau đó absolute import chạy được mà không cần sửa script.
  2. Upgrade `chromadb`, `opentelemetry-api`, `opentelemetry-sdk`, `httpx` lên phiên bản tương thích.
  3. `pip install langchain-anthropic langchain-google-genai langchain-ollama langchain-openai datasets ragas great-expectations sentence-transformers`.
  4. Xóa `data/eval/test_set.json` để flow tự build lại từ `build_test_set()`. Khi artifact bị hỏng ở giữa hai lần chạy, xóa là đúng — không tự ý sửa file JSON output, để tool tạo lại đúng schema.
- **Cách xác minh sau khi sửa:** Sau khi áp dụng 4 bước trên, `python script/run_phase1.py` ra log `Baseline complete: 24 clean records; report=.../phase1_report.md` và `python script/run_corruption_flow.py` ra `Comparison report written: .../corruption_report.md`. Bảng 10/10 quality check PASS trong baseline report.
- **Điều học được:**
  - Khi starter repo có `pyproject.toml` chuẩn package, **luôn `pip install -e .`** trước khi sửa script — đỡ phải patch `sys.path`.
  - Conflict giữa chromadb và opentelemetry không nên downgrade; upgrade cả ba (`chromadb`, `opentelemetry-api`, `opentelemetry-sdk`) lên cùng thế hệ thì hết.
  - Với JSON output, đừng bao giờ tự sửa bằng tay. Nếu có artifact đã từng tốt, xóa để flow build lại sẽ an toàn hơn.

## 7. Hiểu biết về luồng end-to-end

Giải thích ngắn gọn bằng lời của tôi:

1. **Dữ liệu đi từ Crossref đến vector index như thế nào?**
   Crossref REST API → `parse_crossref_payload()` chuẩn hóa thành `PaperRecord` → ghi xuống `data/raw/crossref_records.json` (đây là freeze point của C2) → `build_clean_dataframe()` strip HTML, lọc summary < 100 ký tự, build `text_for_embedding = "Title: ...\nAuthors: ...\nCategories: ...\nPublished: ...\nSummary: ..."` → `LocalEmbeddingIndex.build()` embed bằng `sentence-transformers/all-MiniLM-L6-v2` và lưu vào Chroma collection `papers-baseline` + manifest JSON. Chroma dùng cosine distance; manifest giữ `documents_by_paper_id` / `documents_by_title` để `index.lookup()` có thể tra cứu chính xác theo ID hay tiêu đề trong `qa.answer_question()`.

2. **Evaluation set và ground-truth document IDs dùng để đo retrieval/answer quality ra sao?**
   `build_test_set()` lấy `df.head(6)` và build 4 question types (summary/authors/date/categories) bằng cách gọi lại các hàm extract tương ứng để tạo `ground_truth`. Mỗi question kèm `ground_truth_doc_ids: [paper_id]` để `evaluate_pipeline()` check `retrieval_hit = any(doc_id in ground_truth_doc_ids for doc_id in result.retrieved_doc_ids)`. Vì vậy cùng test set cho cả 3 trạng thái là điều kiện tiên quyết để mọi delta metric quy về data quality.

3. **Quality checks khác freshness monitoring ở điểm nào trong bài lab?**
   Quality checks (10 check trong `quality.py`) đo **shape/schema** của cleaned dataframe ở một thời điểm: có đủ cột không, `paper_id` có unique không, summary có đủ dài không, có NaN trong cột index không. Freshness đo **độ cũ của dữ liệu** theo `age_days > freshness_threshold_days (180)`. Một dataset có thể PASS mọi quality check nhưng FAIL freshness (ví dụ `stale_published_date` scenario trong corruption log: data vẫn đủ cột, đủ dài, đúng schema, nhưng `age_days = 9714` → stale). Ngược lại, fresh dataset có thể FAIL quality nếu `duplicate_record` sinh ra 2 dòng cùng `paper_id`.

4. **Vì sao phải dùng cùng test set cho baseline, corrupted và repaired?**
   Vì `retrieval_hit_rate` và `mean_token_f1` chỉ có ý nghĩa so sánh khi cùng tập câu hỏi. Nếu mỗi state dùng test set khác nhau, ta không biết metric thay đổi vì data hay vì test set. Đây là lý do `evaluate_pipeline()` được gọi với cùng `eval_testset` cho cả 3 state, và lý do `corruption_flow.main()` assert `corruption_log["frozen_test_set"]["overlap_count"] > 0` — nếu corruption không đụng ground-truth document nào thì không metric nào có thể chuyển động.

5. **Repair được xem là thành công dựa trên artifact và metric nào?**
   Repair thành công khi thỏa cả 4 điều kiện:
   - `_verify_repair()` trả `paper_ids_match: true` và `content_matches: true` (tức là repaired dataframe chứa đúng 24 paper_id của baseline với cùng title/summary/published/authors/categories/text_for_embedding sau khi normalize whitespace).
   - `repaired_quality.json` có `success: true`, 10/10 check PASS.
   - `repaired_freshness.json` có `is_fresh: true`, `stale_rows: 0`.
   - `repaired_metrics.json` khớp `baseline_metrics.json` cho cả 4 metric (`retrieval_hit_rate`, `mean_token_f1`, `judge_accuracy`, `mean_judge_score`) — trong bài này cả 4 metric đều bằng đúng baseline, chứng tỏ replay qua cùng cleaning logic đã khôi phục hoàn toàn agent behavior.

## 8. Phân tích kết quả

### Metrics chính

| Metric/signal             | Baseline | Corrupted | Repaired | Nhận xét của cá nhân                                                                                                                |
| ------------------------- | -------: | --------: | -------: | ----------------------------------------------------------------------------------------------------------------------------------- |
| `retrieval_hit_rate`      |   0.8000 |    0.8000 |   0.8000 | Không đổi. Lý do: corpus chỉ có 24 dòng, mỗi câu hỏi quote title riêng, `top_k=4` vẫn tìm ra đúng doc kể cả khi summary bị blank/noise. Trừ `q1` (`drop_latest_record`) retrieval chắc chắn MISS. |
| `mean_token_f1`           |   0.4821 |    0.3035 |   0.4821 | Sụt 37.1%. Đây là metric phản ánh đúng tác động của corruption vì `qa._extract_answer()` trả first sentence của summary, mà summary lại là phần dominate `text_for_embedding` — blank summary → embed metadata-only → first sentence rỗng → token_f1 = 0. Repair replay lại đúng cleaning, nên F1 về đúng baseline. |
| `judge_accuracy`          |   0.5000 |    0.3000 |   0.5000 | Sụt 40%. LLM judge bắt được các trường hợp answer "sai về bản chất" (q4 bị noise prefix, q8 bị stale date), không chỉ F1 thấp về mặt chuỗi. |
| `mean_judge_score`        |   2.8000 |    2.2000 |   2.8000 | Sụt 21.4%. Judge cho điểm 1-5, score trung bình phản ánh "quality tổng thể" của câu trả lời. Cả 3 sụt đều recover về baseline. |
| Quality checks             |    10/10 |   7/10 FAIL ở 3 check | 10/10 | 3 check FAIL: `paper_id_unique` (3 dup từ `duplicate_record`), `summary_min_length` (4 từ `blank_summary`), `freshness_age_days` (4 từ `stale_published_date`). Quality signal **detect được corruption trước khi evaluation chạy**. |
| Freshness status           |      True |      False |     True | Baseline max_age 175 ngày < threshold 180. Corrupted max_age 9714 ngày (do 4 dòng bị đẩy về 2000-01-01). Repaired về 175. |

### Kết luận từ số liệu

Hai chuỗi nguyên nhân–bằng chứng:

1. **`blank_summary` + `inject_summary_noise` → `summary_min_length` FAIL → `mean_token_f1` sụt 37%.** Trong `corruption_log.json` có 4 sự kiện `blank_summary` và 4 sự kiện `inject_summary_noise`, tất cả đều nằm trên paper_id thuộc test set (q3, q7 cho blank; q4, q9 cho noise). `text_for_embedding` của các dòng này bị mất summary (hoặc bị nhiễu) → MiniLM embed một vector "lệch" so với câu hỏi → top-k retrieval vẫn có thể ra đúng doc (vì title match chiếm ưu thế ở corpus 24 dòng), nhưng `qa._extract_answer()` lại trả `first_sentence("")` hoặc `first_sentence(noise_summary)` → token_f1 ≈ 0. Bằng chứng: per-question table trong `corruption_report.md` cho thấy q4 có F1 B=0.82 → C=0.04 → R=0.82.

2. **`duplicate_record` → `paper_id_unique` FAIL → retrieval top_k bị "ăn" slot.** 3 sự kiện duplicate sinh ra 3 dòng `paper_id` trùng khớp với q5, q10. Khi retrieval trả về `top_k=4` mà trong đó có 2 slot là cùng một document (vì 2 dòng cùng paper_id match gần như nhau), các câu hỏi khác có thể bị đẩy ra khỏi top_k. Trong dataset này ảnh hưởng chưa đủ lớn để làm `retrieval_hit_rate` sụt, nhưng với corpus lớn hơn duplicate sẽ làm retrieval miss rất nhiều.

Corruption nào ảnh hưởng rõ nhất và vì sao? `blank_summary` + `inject_summary_noise`, vì nó tác động trực tiếp vào `text_for_embedding` — phần input chính của MiniLM — và đồng thời làm `summary_min_length` quality check FAIL. Trong 10 câu hỏi test set, 4 câu (q3, q4, q7, q9) đụng 2 scenario này, chiếm 40% test set. Đây cũng là scenario mà repair phục hồi 100% (repaired F1 = baseline F1 cho cùng câu hỏi).

Kết quả nào khác với kỳ vọng ban đầu? `retrieval_hit_rate` không đổi qua corruption (vẫn 0.8 ở cả 3 state) — ban đầu tôi kỳ vọng hit rate sụt mạnh vì `blank_summary` phá embedding. Giả thuyết kiểm tra: corpus quá nhỏ (24 dòng) + mỗi câu hỏi chứa chính title của ground-truth doc trong dấu nháy đơn → `qa.answer_question()` dò được match chính xác qua `index.lookup(title)` rồi chèn exact match lên đầu, retrieval hit không phụ thuộc embedding quality. Bằng chứng: trong per-question table, `q1` (`drop_latest_record`) là câu duy nhất có `Retrieval B=hit, C=MISS, R=hit` — đây mới là tình huống retrieval không thể recover vì document đã bị xóa hoàn toàn, không phải vì embedding xấu.

## 9. Điều học được và hướng cải thiện

### Ba điều quan trọng nhất

1. **Data pipeline thực tế không fail bằng exception — nó fail bằng silent wrong answer.** `blank_summary` không ném lỗi, không cảnh báo trong log, không vi phạm schema; chỉ làm `mean_token_f1` từ 0.82 xuống 0.04. Pipeline design phải giả định "code chạy đúng ≠ data đúng" và bắt buộc có observability layer để phát hiện.

2. **Observability layer (quality + freshness) làm việc đúng vai trò: detect corruption trước khi evaluation chạy.** Trong corrupted state, 3 check FAIL (`paper_id_unique`, `summary_min_length`, `freshness_age_days`) map 1-1 với 3 corruption scenarios (`duplicate_record`, `blank_summary`, `stale_published_date`). Nếu CI/CD chạy `run_data_quality_checks` trước khi trigger evaluation, ta có thể fail fast và bỏ qua LLM judge (tiết kiệm cost).

3. **Repair phải replay từ raw snapshot, không phải sửa ngược corrupted output.** Đây là nguyên tắc "single source of truth": raw records là canonical, cleaning là pure function, repair chỉ cần chạy lại pure function đó. Nếu cleaning có bug, ta phát hiện ngay qua `_verify_repair()` thay vì sửa thủ công từng dòng corrupted.

### Nếu có thêm thời gian

**Cải thiện:** Thêm một assertion trong `run_phase1.py::main()` rằng `run_data_quality_checks(df, settings, "baseline_quality")["success"] == True` — nếu baseline quality FAIL thì pipeline phải dừng thay vì tiếp tục evaluate với data đã hỏng. Hiện tại quality check chỉ ghi artifact, không raise.

**Lý do:** Tách baseline khỏi corrupted/repaired. Trong corrupted state, quality check FAIL là kỳ vọng (đó là cái ta muốn chứng minh), nhưng trong baseline state, quality FAIL nghĩa là upstream đã hỏng và ta đang đo nhầm.

**Cách đo cải thiện:** Khi bật assertion, chạy `python script/run_phase1.py` trên một raw snapshot cố tình thiếu title vài dòng (qua mock `fetch_source_records`): pipeline phải raise trước khi gọi LLM judge. Đo bằng exit code và lượng token LLM tiêu thụ (phải bằng 0 khi fail).

## 10. Cam kết của thành viên

Đánh dấu sau khi tự kiểm tra:

- [x] Nội dung báo cáo phản ánh đúng phần việc và mức hiểu của tôi.
- [x] Tôi có thể giải thích luồng end-to-end, không chỉ module mình phụ trách.
- [x] Mọi kết quả về kết quả đều có artifact hoặc metric để đối chiếu (`data/results/*.json`, `data/quality/*.json`, `data/reports/*.md`).
- [x] Tôi không ghi "đã chạy thành công" cho phần chưa được kiểm chứng — cả 2 flow đều đã chạy lại với exit code 0 và có log cụ thể.
- [x] Báo cáo không chứa `.env`, API key, token hoặc secret — báo cáo chỉ tham chiếu `LLM_PROVIDER=grok` qua env var name, không có key thật.
- [x] Báo cáo này không phải bản sao nguyên văn của báo cáo nhóm hoặc báo cáo thành viên khác.

**Họ và tên:** Lương Bảo Long
**Ngày xác nhận:** 2026-08-06