# Member Role Report — Day 10: Data Pipeline & Data Observability

## 1. Thông tin cá nhân

| Thông tin         | Nội dung                       |
| ------------------| -------------------------------|
| Họ và tên         | Trần Kiều Hạnh                 |
| MSSV              | 2A202601760                    |
| Khóa/Lớp          | K4                             |
| Tên nhóm          | VuaTuat                        |
| Vai trò chính     | Corruption & repair owner      |
| Repository        | https://github.com/benmentran/K4_Day10_Data-Pipeline-Data-Observability-VuaTuat    |
| Ngày hoàn thành   | 2026-08-06                     |

## 2. Vai trò và phạm vi công việc

### Phần việc sở hữu

| Module/deliverable | File/hàm phụ trách | Input nhận vào | Output bàn giao  | Trạng thái                                 |
| ------------------ | --------------------- | ---------------- | ----------------- | -------------------------------------------- |
| Corruption engine | `src/ingestion/corruption.py` — `corrupt_clean_dataframe`, `build_corruption_plan`, `_build_log` | Cleaned dataframe baseline (24 rows, 14 cols) + frozen test set `data/eval/test_set.json` | `data/clean/papers_corrupted.csv`/`.json` (26 rows), `data/results/corruption_log.json` (audit trail 19 docs, overlap 10/10) | Hoàn thành |
| Corruption scenarios | `src/ingestion/corruption.py` — 6 scenario constants + mutation logic (`drop_latest_record`, `blank_summary`, `inject_summary_noise`, `truncate_title`, `stale_published_date`, `duplicate_record`) | Cleaned dataframe | Corrupted dataframe giữ nguyên clean schema (14 cols) để pipeline embedding/evaluation tái sử dụng được | Hoàn thành |
| Corruption unit tests | `tests/test_corruption.py` — 7 test functions | Synthetic clean frame + frozen test set | 7/7 test PASS, xác minh determinism, auditability, overlap với test set | Hoàn thành |
| Embedding/index cho corrupted state | `src/retrieval/index.py::LocalEmbeddingIndex.build` (chia sẻ với TV5) | Corrupted dataframe | `data/embeddings/papers_embeddings_corrupted.json`, Chroma collection `papers-corrupted` | Hoàn thành |

### Việc hỗ trợ ngoài phạm vi chính

| Hoạt động                         | Thành viên/module được hỗ trợ | Kết quả                    |
| ------------------------------------ | ------------------------------------ | ---------------------------- |
| Debug lỗi đọc CSV corrupted (blank summary thành NaN) | TV5 — `src/pipelines/corruption_flow.py::_read_clean_csv` | Phát hiện cần `keep_default_na=False` khi đọc `papers_corrupted.csv` để summary rỗng giữ nguyên `""`, không thành NaN làm crash Chroma metadata write |

## 3. Kết quả theo vai trò

| Nhiệm vụ đã thực hiện | File/hàm/artifact liên quan | Kết quả bàn giao       | Cách xác minh         |
| --------------------------- | ----------------------------- | ------------------------- | ----------------------- |
| Thiết kế 6 corruption scenario có chủ đích, deterministic (seed 42) | `src/ingestion/corruption.py` | `data/results/corruption_log.json`: input 24 → output 26 rows, 19 docs bị tác động, event_counts đủ 6 loại scenario | `python -m pytest tests/test_corruption.py -v` — 7/7 PASS; `test_corruption_is_deterministic` assert 2 lần chạy cho frame giống hệt nhau |
| Đảm bảo corruption đụng 100% ground-truth docs của frozen test set | `build_corruption_plan` trong `src/ingestion/corruption.py` | `corruption_log.json["frozen_test_set"]`: `overlap_count = 10`, `overlap_ratio = 1.0`, `scenarios_without_test_set_overlap = []` | `python script/run_corruption_flow.py` — pipeline assert `overlap_count > 0`; log ghi đủ 10 câu q1..q10 kèm scenario tương ứng |
| Ghi audit trail từng mutation | `_build_log` + `record()` trong `src/ingestion/corruption.py` | 19 events, mỗi event có `type`, `paper_id`, `question_ids`, `in_frozen_test_set`, `parameters` (before/after chars, age_days, preview noise) | Đọc `data/results/corruption_log.json`; `test_corruption_is_auditable_and_does_not_mutate_baseline` assert baseline không bị mutate |
| Chạy corruption flow end-to-end | `src/pipelines/corruption_flow.py` (phối hợp TV5) | `data/clean/papers_corrupted.csv` (26 rows), `data/results/corrupted_metrics.json`, `data/quality/corrupted_quality.json`, `data/quality/corrupted_freshness.json`, `data/reports/corruption_report.md` | `python script/run_corruption_flow.py` exit 0, log `Comparison report written: .../corruption_report.md` |

**Output cụ thể:**

`data/results/corruption_log.json` là artifact chính của phần việc corruption: ghi đầy đủ 6 scenario, 19 document bị tác động, 10/10 ground-truth document của frozen test set nằm trong overlap (q1→drop, q2/q8→stale, q3/q7→blank, q4/q9→noise, q5/q10→duplicate, q6→truncate). Nhờ log này, mọi delta metric giữa baseline và corrupted đều quy được về đúng scenario và đúng câu hỏi bị ảnh hưởng — ví dụ q4 có token F1 sụt 0.82 → 0.04 vì `inject_summary_noise`, q8 sụt 1.00 → 0.00 vì `stale_published_date`.

## 4. Giải thích phần kỹ thuật đã thực hiện

### Vấn đề cần giải quyết

Làm sao tạo ra dữ liệu lỗi có chủ đích (corruption) để chứng minh **data quality ảnh hưởng trực tiếp đến chất lượng RAG agent**, đồng thời vẫn giữ được tính tái lập và khả năng truy vết. Yêu cầu quan trọng nhất: corruption phải đụng đúng các document mà evaluation set thực sự hỏi — nếu corruption chỉ chạm document không ai query thì không metric nào chuyển động, và pipeline phải fail ngay thay vì âm thầm cho kết quả vô nghĩa.

### Cách triển khai

Triển khai `corrupt_clean_dataframe()` theo nguyên tắc **deterministic + auditable + không mutate input**:

1. **Lập kế hoạch trước khi mutate** (`build_corruption_plan`): duyệt frozen test set, với mỗi `ground_truth_doc_ids` chưa bị claim, gán scenario dựa trên hình dạng câu hỏi — câu hỏi về ngày (`when was|publication date|published`) nhận `stale_published_date` vì chỉ câu hỏi dạng ngày mới đo được lỗi ngày trong answer; các câu còn lại xoay vòng qua `blank_summary`, `inject_summary_noise`, `duplicate_record`, `truncate_title`. Sau đó dùng `EXTRA_TARGETS` để rải thêm corruption sang document ngoài test set (round-robin qua `_allocate`), làm corruption trông giống sự cố upstream thật thay vì "tấn công có chọn lọc" 10 document được đánh giá.

2. **Chọn noise prepend thay vì append**: `UNRELATED_TEXT` được prepend vào summary (không append) vì `qa._extract_answer()` trả về *câu đầu tiên* của summary. Nếu append, embedding bị nhiễu nhưng answer vẫn trông ổn — sẽ đánh giá thấp thiệt hại thực tế. Ngoài ra còn append 320 ký tự ngẫu nhiên vào riêng `text_for_embedding` (không thuộc field nào của clean schema) để nhiễu đúng phần MiniLM embed mà không phá schema.

3. **Rebuild `text_for_embedding` sau mọi mutation**: mọi thay đổi (blank, noise, truncate, stale, duplicate) phải chạm tới text MiniLM thực sự embed. Hàm `_embedding_text()` dựng lại đúng contract 5 dòng `Title/Authors/Categories/Published/Summary`, sau đó gắn random noise cho các dòng bị noise. `summary_chars` cũng được tính lại.

4. **Audit trail đầy đủ**: mỗi mutation ghi event với `type`, `paper_id`, `question_ids`, `in_frozen_test_set`, `parameters` (before/after chars, before/after age_days, preview noise). `_build_log` tổng hợp thành `scenarios`, `event_counts`, `frozen_test_set` (overlap_count, overlap_ratio, questions_affected) — đây là bằng chứng để nối metric delta với đúng scenario.

5. **Determinism**: toàn bộ dùng `random.Random(seed)` với `CORRUPTION_SEED = 42`, không phụ thuộc wall-clock randomness, nên baseline → corrupted → repaired tái lập được chính xác giữa các lần chạy.

### Input, output và contract

| Thành phần                   | Mô tả                                     |
| ------------------------------ | ------------------------------------------- |
| Input                          | Cleaned dataframe baseline (24 rows, 14 cols: `paper_id`, `title`, `summary`, `authors_joined`, `categories_joined`, `published`, `age_days`, `summary_chars`, `text_for_embedding`, ...) + `test_set_path` trỏ `data/eval/test_set.json` (10 câu, mỗi câu có `ground_truth_doc_ids`) |
| Output                         | Corrupted dataframe giữ nguyên 14 cols (26 rows: 1 drop, 3 duplicate) + `data/results/corruption_log.json` (audit trail) |
| Module phụ thuộc             | `core/utils.py` (`now_utc`, `read_json`, `write_json`); `data/eval/test_set.json` do TV2 build; cleaned dataframe do `src/ingestion/cleaning.py` tạo |
| Module sử dụng output        | `src/pipelines/corruption_flow.py` (TV5) — đọc corrupted frame để build index, evaluate, quality/freshness; `src/retrieval/index.py::LocalEmbeddingIndex.build` |
| Điều kiện lỗi cần xử lý | Thiếu cột bắt buộc → `ValueError("missing columns")`; dataframe rỗng → `ValueError("empty")`; overlap = 0 → `corruption_flow.main()` raise `RuntimeError` để không chạy evaluation vô nghĩa |

### Cách xác minh

```bash
python -m pytest tests/test_corruption.py -v
python script/run_corruption_flow.py
python script/run_corruption_flow.py --report-only
```

- **Kết quả mong đợi:** 7/7 test PASS; corruption flow exit 0 với log `Comparison report written: .../corruption_report.md`; `corruption_log.json` có `overlap_count = 10`, `overlap_ratio = 1.0`.
- **Kết quả thực tế:** 7/7 test PASS (determinism, auditability, overlap, stale date, noise reach embedding, duplicate giữ paper_id, reject invalid input); corruption flow chạy thành công, sinh đủ 9 JSON + 3 CSV + 1 corruption log; `corrupted_metrics.json` ghi `mean_token_f1 = 0.3035`, `judge_accuracy = 0.3`, `mean_judge_score = 2.2`.
- **Artifact/log:** `data/results/corruption_log.json`, `data/clean/papers_corrupted.csv`, `data/reports/corruption_report.md` (không chứa secret).

## 5. Một quyết định kỹ thuật quan trọng

- **Bối cảnh:** Khi thiết kế scenario `inject_summary_noise`, cần quyết định đặt `UNRELATED_TEXT` (nội dung lạc đề về thời tiết/nấu ăn) vào vị trí nào trong summary — prepend hay append.
- **Các phương án đã cân nhắc:**
  1. **Append** noise vào cuối summary: embedding bị nhiễu nhưng `qa._extract_answer()` trả `first_sentence(summary)` vẫn là câu đầu tiên sạch → answer trông ổn, chỉ embedding lệch.
  2. **Prepend** noise vào đầu summary: cả embedding lẫn answer đều bị nhiễu vì câu đầu tiên trả về chính là noise.
- **Phương án đã chọn:** Prepend `UNRELATED_TEXT` vào đầu summary, đồng thời append 320 ký tự ngẫu nhiên vào riêng `text_for_embedding`.
- **Lý do:** Mục tiêu của corruption là mô phỏng sự cố upstream thật và đo đúng thiệt hại lên agent. Nếu chỉ append, metric answer-level (token_f1, judge) gần như không đổi vì answer vẫn lấy từ câu đầu sạch — sẽ đánh giá thấp mức độ nghiêm trọng. Prepend làm cả hai tầng (embedding + answer) cùng suy giảm, phản ánh đúng việc dữ liệu nhiễu ở vị trí quan trọng nhất của summary. Random chars chỉ nằm trong `text_for_embedding` vì chúng không thuộc field nào của clean schema — giữ schema 14 cột nguyên vẹn để pipeline embedding/evaluation tái sử dụng được.
- **Bằng chứng quyết định phù hợp:** `corruption_log.json` ghi `unrelated_prefix_chars = 168` và `random_chars_appended_to_text_for_embedding = 320`; `test_noise_reaches_text_for_embedding` assert `summary.str.startswith(UNRELATED_TEXT)` và trailing 320 chars chỉ tồn tại trong `text_for_embedding`, không nằm trong summary. Kết quả đo: q4 token F1 sụt 0.82 → 0.04 (corrupted) rồi phục hồi 0.82 (repaired) — noise prepend đã tác động đúng lên answer.

## 6. Một lỗi hoặc blocker đã xử lý

- **Triệu chứng/lỗi nguyên văn:** Khi đọc `data/clean/papers_corrupted.csv` bằng `pd.read_csv(path)` mặc định, các dòng bị `blank_summary` có `summary` rỗng bị chuyển thành `NaN`; Chroma metadata write crash với lỗi kiểu `ValueError: Expected metadata value to be a str/int/float/bool, got nan` (hoặc tương đương), làm pipeline corruption flow dừng giữa chừng.
- **Lệnh hoặc bước tái hiện:** `python script/run_corruption_flow.py` sau khi corrupted CSV được ghi; bước `LocalEmbeddingIndex.build(corrupted, ...)` đọc lại CSV và crash khi ghi metadata chứa `NaN`.
- **Nguyên nhân gốc:** Pandas mặc định parse ô rỗng trong CSV thành `NaN` (`keep_default_na=True`). Summary rỗng là một trạng thái corruption hợp lệ (blank summary), nhưng khi đọc lại, `""` biến thành `NaN` — vừa crash Chroma metadata write, vừa **che giấu corruption**: quality check `summary_min_length` không còn thấy summary rỗng nữa mà thấy NaN, làm sai lệch observability.
- **Cách xử lý:** Sửa `_read_clean_csv()` trong `src/pipelines/corruption_flow.py` truyền `keep_default_na=False` để summary rỗng giữ nguyên `""` khi đọc lại. Đồng thời trong `corruption.py`, sau khi blank summary tôi rebuild `summary_chars = summary.astype(str).str.len()` để cột này phản ánh đúng độ dài 0.
- **Cách xác minh sau khi sửa:** `python script/run_corruption_flow.py` exit 0; `data/quality/corrupted_quality.json` ghi `summary_min_length` FAIL với `observed = 4`, detail `"4 dong co summary < 100 ky tu (ngan nhat 0)"` — corruption không còn bị che giấu; `test_corruption_is_auditable_and_does_not_mutate_baseline` assert `(corrupted["summary_chars"] == 0).any()`.
- **Điều học được:** Khi thiết kế corruption/observability, phải kiểm tra toàn bộ đường đọc lại dữ liệu (read path), không chỉ đường ghi. Một giá trị rỗng hợp lệ có thể bị framework biến thành `NaN` và làm cả pipeline lẫn quality check hiểu sai trạng thái dữ liệu — `keep_default_na=False` là convention bắt buộc khi đọc CSV có field rỗng có nghĩa.

## 7. Hiểu biết về luồng end-to-end

1. **Crossref → vector index:** `src/ingestion/crossref.py` gọi Crossref REST API với query `agentic retrieval augmented generation large language model`, filter `from-pub-date` (180 ngày) và `has-abstract:true`, retry 429/503 bằng exponential backoff, parse thành 24 `PaperRecord` và freeze tại `data/raw/crossref_records.json`. `src/ingestion/cleaning.py::build_clean_dataframe` strip HTML, ép summary ≥ 100 ký tự, parse ngày, drop duplicate theo `paper_id`, dựng `text_for_embedding` (Title/Authors/Categories/Published/Summary) → `data/clean/papers_clean.csv` (24 rows × 14 cols). `src/retrieval/index.py::LocalEmbeddingIndex.build` embed `text_for_embedding` bằng MiniLM (`all-MiniLM-L6-v2`, 384-dim) và lưu vào Chroma collection `papers-baseline` cùng manifest JSON.

2. **Evaluation set & ground-truth IDs:** `src/evaluation/testset.py::build_test_set` tạo 10 câu hỏi từ `df.head(10)` với 6 template (authors / published / categories_joined / main-contribution / primary-application / methodology). Mỗi câu có `ground_truth_doc_ids: [paper_id]` trỏ đúng record được chọn. `evaluate_pipeline` dùng test set này để: (a) retrieval — kiểm tra `paper_id` của top-k có nằm trong `ground_truth_doc_ids` không (retrieval_hit_rate); (b) answer — so token F1 giữa answer và ground_truth, và LLM judge chấm đúng/sai (judge_accuracy, mean_judge_score).

3. **Quality checks vs freshness:** Quality checks đo **cấu trúc và nội dung** của dataset: completeness (cột bắt buộc, không null), uniqueness (`paper_id_unique`), validity (`summary_min_length` ≥ 100), consistency (`no_nan_in_index_columns`) — chạy trên cleaned dataframe bất kể thời gian. Freshness monitoring đo riêng **độ mới của dữ liệu theo thời gian**: `age_days = run_date - published`, so với threshold 180 ngày, sinh `is_fresh`, `stale_rows`, `max_age_days`. Trong bài, `stale_published_date` làm `freshness_age_days` FAIL (max_age 175 → 9714) trong khi các quality check khác vẫn PASS — chứng tỏ hai loại tín hiệu bổ sung cho nhau.

4. **Cùng test set cho 3 trạng thái:** `evaluate_pipeline` được gọi với cùng `data/eval/test_set.json` (hash không đổi) cho baseline, corrupted và repaired. Nếu mỗi trạng thái dùng test set khác, không thể phân biệt metric thay đổi vì data hay vì test set. Corruption flow còn assert `overlap_count > 0` — corruption phải đụng ground-truth docs (bài này 10/10) thì mọi delta metric mới quy được về data quality.

5. **Repair thành công dựa trên:** (a) `_verify_repair()` trong `corruption_flow.py` so sánh baseline vs repaired trên 6 cột nội dung (whitespace-normalised): `paper_ids_match: true`, `content_matches: true`, `documents_with_changed_content: []`; (b) cả 4 RAG metric repaired trở về đúng baseline (retrieval_hit_rate 0.8, mean_token_f1 0.4821, judge_accuracy 0.5, mean_judge_score 2.8); (c) quality 10/10 PASS và freshness `is_fresh: true`, `max_age_days = 175` — khớp baseline. Repair không đọc `papers_corrupted.csv` mà replay raw snapshot qua cùng cleaning logic, nên phục hồi là "provable" chứ không phải vá tay.

## 8. Phân tích kết quả

### Metrics chính

| Metric/signal          | Baseline | Corrupted | Repaired | Nhận xét của cá nhân |
| ---------------------- | -------: | --------: | -------: | ------------------------- |
| `retrieval_hit_rate` |    0.8000 |    0.8000 |   0.8000 | Không đổi vì corpus chỉ 24 dòng, top_k=4 luôn surface được ground-truth doc (trừ q1 bị drop). Đây là giới hạn của dataset nhỏ, không phải corruption vô hại. |
| `mean_token_f1`      |    0.4821 |    0.3035 |   0.4821 | Sụt 37.1% do `blank_summary` + `inject_summary_noise` — summary chiếm phần lớn `text_for_embedding` và `_extract_answer` lấy first sentence của summary. Phục hồi 100% sau repair. |
| `judge_accuracy`     |    0.5000 |    0.3000 |   0.5000 | Sụt 40%. LLM judge bắt được các câu "sai về bản chất" (q4 noise, q8 stale date) chứ không chỉ F1 chuỗi thấp. |
| `mean_judge_score`   |    2.8000 |    2.2000 |   2.8000 | Sụt 21.4%, phản ánh chất lượng tổng thể câu trả lời. |
| Quality checks         |    10/10 |     7/10 |    10/10 | 3 FAIL ở corrupted: `paper_id_unique` (3 dup), `summary_min_length` (4 blank), `freshness_age_days` (4 stale) — mỗi FAIL map 1-1 với một scenario. |
| Freshness status       |    True |    False |     True | `stale_published_date` đẩy max_age 175 → 9714 ngày; repair phục hồi về 175. |

### Kết luận từ số liệu

Hoàn thành hai chuỗi nguyên nhân–bằng chứng sau:

1. **`blank_summary` + `inject_summary_noise` → `summary_min_length` FAIL → `mean_token_f1` sụt 37.1%.** 4 sự kiện blank + 4 sự kiện noise trong `corruption_log.json` đều đụng paper_id thuộc frozen test set (q3, q7 cho blank; q4, q9 cho noise). `text_for_embedding` của các dòng này mất summary hoặc bị prepend noise → MiniLM embed vector lệch, `_extract_answer` trả first sentence rỗng/off-topic → token_f1 ≈ 0. Bằng chứng per-question: q4 F1 0.82 → 0.04 → 0.82 trong `corruption_report.md`.
2. **`stale_published_date` → `freshness_age_days` FAIL → `judge_accuracy` sụt.** 4 sự kiện stale (q2, q8 + 2 ngoài test set) đẩy `published` về 2000-01-01, `age_days` 9714 > threshold 180 → `is_fresh: false`. Câu hỏi dạng ngày (q8) trả lời sai ngày → judge chấm sai, F1 1.00 → 0.00 → 1.00. Repair replay raw snapshot phục hồi ngày gốc → freshness True, max_age 175.

Corruption nào ảnh hưởng rõ nhất và vì sao?

`blank_summary` + `inject_summary_noise` ảnh hưởng rõ nhất vì chúng tác động trực tiếp vào `summary` — phần chiếm đa số token trong `text_for_embedding` (input chính của MiniLM) và đồng thời là nguồn của `first_sentence()` mà `_extract_answer` trả về. Hai scenario này đụng 4/10 câu hỏi (q3, q4, q7, q9), làm `mean_token_f1` sụt 0.4821 → 0.3035 và `judge_accuracy` sụt 0.5 → 0.3. Ngược lại `truncate_title` và `duplicate_record` gần như không làm metric answer-level đổi vì title vẫn còn đủ để retrieval hit và summary vẫn sạch.

Kết quả nào khác với kỳ vọng ban đầu?

Kỳ vọng `retrieval_hit_rate` sẽ sụt khi summary bị blank/noise vì vector embedding lệch đi. Thực tế hit rate không đổi (0.8) vì corpus quá nhỏ (24 dòng) và mỗi câu quote title riêng của ground-truth doc — top_k=4/24 luôn surface được đúng doc; thậm chí q7 còn flip từ MISS → hit khi summary bị blank vì embedding text ngắn hơn làm title similarity tăng. Tôi đã kiểm tra giả thuyết này bằng per-question table trong `corruption_report.md` (cột Retrieval B/C/R) và kết luận đây là giới hạn của dataset nhỏ, không phải corruption vô hại — tác động thật nằm ở answer-level metrics.

## 9. Điều học được và hướng cải thiện

### Ba điều quan trọng nhất

1. **Data pipeline:** Corruption phải được thiết kế có chủ đích và có audit trail — mỗi mutation ghi `paper_id`, `question_ids`, `parameters` để mọi delta metric quy được về đúng scenario. Determinism (seed 42) là điều kiện tiên quyết để so sánh baseline/corrupted/repaired có nghĩa.
2. **Data quality/observability:** Quality checks và freshness bổ sung cho nhau: quality đo cấu trúc/nội dung (uniqueness, validity, completeness), freshness đo độ mới theo thời gian. Trong bài, `stale_published_date` chỉ làm freshness FAIL mà quality khác vẫn PASS — nếu chỉ có một loại tín hiệu sẽ bỏ sót lỗi. Quan trọng hơn, quality check phát hiện corruption **trước khi** evaluation chạy (7/10 PASS ở corrupted), đúng vai trò "cảnh báo sớm".
3. **Ảnh hưởng của data đến RAG agent:** Cùng code, cùng prompt, cùng embedding model, cùng test set — chỉ đổi data là agent suy giảm rõ (F1 -37%, judge accuracy -40%). Summary là field nhạy cảm nhất vì nó vừa dominate embedding vừa là nguồn answer; corruption trên summary tác động mạnh hơn hẳn title hay duplicate.

### Nếu có thêm thời gian

Thêm scenario `swap_ground_truth` — hoán đổi summary giữa hai document để tạo "wrong but plausible" content: quality checks hiện tại (min_length, uniqueness, freshness) sẽ không bắt được vì summary vẫn dài, vẫn hợp lệ, chỉ sai chủ đề. Đây là loại corruption nguy hiểm nhất trong thực tế vì observability truyền thống không thấy. Cách đo: thêm quality check `summary_topic_consistency` (so cosine similarity giữa summary embedding và title embedding, ngưỡng ví dụ 0.3) và đo xem check này có FAIL ở corrupted state trong khi các check cũ vẫn PASS, đồng thời `mean_token_f1`/`judge_accuracy` sụt — chứng minh cần tín hiệu observability mới để bắt lớp lỗi này.

## 10. Cam kết của thành viên

Đánh dấu sau khi tự kiểm tra:

- [x] Nội dung báo cáo phản ánh đúng phần việc và mức hiểu của tôi.
- [x] Tôi có thể giải thích luồng end-to-end, không chỉ module mình phụ trách.
- [x] Mọi kết luận về kết quả đều có artifact hoặc metric để đối chiếu.
- [x] Tôi không ghi "đã chạy thành công" cho phần chưa được kiểm chứng.
- [x] Báo cáo không chứa `.env`, API key, token hoặc secret.
- [x] Báo cáo này không phải bản sao nguyên văn của báo cáo nhóm hoặc báo cáo thành viên khác.

**Họ và tên:** Trần Kiều Hạnh
**Ngày xác nhận:** 2026-08-06