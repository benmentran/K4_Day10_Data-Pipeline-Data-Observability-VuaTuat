# Clean Schema Contract — Day 10 Data Pipeline

> Chốt tại **Checkpoint 0**. Owner: Cleaning & data modeling.
> Đây là hợp đồng dữ liệu giữa `raw` và mọi module phía sau. Ai đổi contract này phải báo cả nhóm trước khi commit.

## 0. Vì sao contract này tồn tại

Contract không do nhóm tự nghĩ ra — nó **đã bị starter cố định sẵn ở hai đầu**:

| Đầu | Bị cố định bởi | Ở đâu |
| --- | --- | --- |
| Input | `PaperRecord` (`@dataclass(frozen=True)`, 11 field) | [`src/ingestion/crossref.py`](../src/ingestion/crossref.py) |
| Output | 9 cột mà `LocalEmbeddingIndex._build_documents()` đọc trực tiếp | [`src/retrieval/index.py`](../src/retrieval/index.py) |

Nhiệm vụ của `build_clean_dataframe()` là bắc cầu giữa hai thứ đã cố định đó. **Không sửa `PaperRecord`** — `load_raw_records()` dùng lại nó khi repair từ raw ở Pha 2, đổi field sẽ làm vỡ corruption flow.

## 1. Schema đầu ra — 14 cột

Cột đánh dấu 🔒 là **hard contract**: `_build_documents()` truy cập thẳng, thiếu là `KeyError` khi build index.

| # | Cột | Kiểu | Non-empty | Nguồn / công thức | Ai tiêu thụ |
| --- | --- | --- | --- | --- | --- |
| 1 | `paper_id` 🔒 | str | ✅ | DOI đã normalize | index id, `lookup()`, `ground_truth_doc_ids` |
| 2 | `title` 🔒 | str | ✅ | `record.title` normalize | `lookup()` theo title, metadata |
| 3 | `summary` 🔒 | str | ✅ | `record.summary` strip JATS + normalize | qa trả lời factual (`first_sentence`) |
| 4 | `authors_joined` 🔒 | str | ✅ | `compact_join(authors)` | qa trả lời *"who authored…"* |
| 5 | `categories_joined` 🔒 | str | ✅ | `compact_join(categories)` | qa trả lời *"what categories…"* |
| 6 | `primary_category` | str | ✅ | `record.primary_category` | phân tích, report |
| 7 | `published` 🔒 | str | ✅ | ISO `YYYY-MM-DD` | qa trả lời *"when was… published"*, freshness |
| 8 | `updated` | str | — | ISO hoặc `""` | trace |
| 9 | `age_days` | int | ✅ | `(run_date.date() - published).days` | **freshness report** |
| 10 | `summary_chars` | int | ✅ | `len(summary)` | **quality check** phát hiện summary rỗng |
| 11 | `abs_url` 🔒 | str | ✅ | `record.abs_url` | metadata |
| 12 | `pdf_url` 🔒 | str | — | `record.pdf_url` hoặc `""` | metadata |
| 13 | `comment` | str | — | `record.comment` hoặc `""` | trace |
| 14 | `text_for_embedding` 🔒 | str | ✅ | xem §3 | **nội dung đem đi embed** |

### Hai ràng buộc kỹ thuật bắt buộc

**(a) Không cột nào được là `list` / `dict`.**
Chroma metadata chỉ nhận scalar (`str` / `int` / `float` / `bool`). Đó chính là lý do tồn tại `authors_joined` và `categories_joined` thay vì `authors` / `categories`.

**(b) Không `NaN` ở bất kỳ cột nào.**
`NaN` là `float` → lọt vào Chroma metadata sẽ lỗi hoặc làm hỏng câu trả lời của agent. Field thiếu phải fill `""` hoặc `"unknown"`, **không bao giờ để `None` / `NaN`**.

## 2. Rule cleaning

### 2.1 Loại bỏ record

Drop khi thiếu một trong 4 field bắt buộc: `paper_id`, `title`, `summary`, `published`.
Drop khi `summary_chars < MIN_SUMMARY_CHARS = 100`.

> Con số 100 là contract dùng chung: Observability owner viết quality check dựa đúng ngưỡng này.

### 2.2 Chuẩn hóa text

- Mọi field text đi qua `normalize_whitespace()` ([`core/utils.py`](../src/core/utils.py)).
- **Abstract Crossref chứa JATS XML** (`<jats:p>`, `<jats:italic>`…) → **bắt buộc strip tag trước khi normalize**. Bỏ bước này thì embedding học phải rác XML và `first_sentence()` trả về thẻ mở.
- Strip JATS làm **defensive trong cleaning** kể cả khi Source owner đã strip ở `parse_crossref_payload` — thao tác idempotent, chạy 2 lần vô hại.

### 2.3 `paper_id`

```
bỏ prefix "https://doi.org/" hoặc "http://dx.doi.org/"  →  .strip()  →  .lower()
```

> **Lý do bắt buộc thống nhất:** `index.lookup()` so khớp bằng lowercase, nhưng `metrics.py` so `doc_id in ground_truth_doc_ids` **case-sensitive**. Lệch hoa/thường thì `retrieval_hit_rate = 0` mà **không có lỗi nào được ném ra** — hỏng ngầm, rất khó debug.

### 2.4 Date

- Crossref trả `date-parts` có thể thiếu month/day (`[[2026, 1]]`) → **pad về `1`**, output ISO `YYYY-MM-DD` dạng **string** (không phải `Timestamp`, vì phải vào Chroma metadata).
- `age_days` tính từ tham số `run_date` **truyền vào hàm**, không gọi `now()` bên trong → pipeline deterministic, chạy lại ra cùng số.
- `age_days` luôn `>= 0`.

### 2.5 Duplicate

- Khóa dedupe: `paper_id` sau khi normalize.
- **Sort trước, `keep="first"` sau** — nếu dedupe trước khi sort thì kết quả không ổn định giữa các lần chạy.
- Sort cuối cùng: `published` **giảm dần** (mới nhất trước).

> Thứ tự này là contract với Corruption owner: scenario *"xóa latest records"* phụ thuộc trực tiếp vào việc dòng đầu là bài mới nhất.

### 2.6 Authors / categories

- Author name = `given + " " + family`; thiếu `given` thì lấy `family`. Bỏ phần tử rỗng (`compact_join` đã tự lọc).
- `categories` từ Crossref **rất hay rỗng** → **không drop record**. Fallback:
  - `categories_joined` rỗng → `"unknown"`
  - `primary_category` rỗng → `"unknown"`
  - `authors_joined` rỗng → `"unknown"`
- Separator thống nhất: `", "`.

## 3. `text_for_embedding`

```
Title: {title}
Authors: {authors_joined}
Categories: {categories_joined}
Published: {published}
Summary: {summary}
```

**Vì sao đưa cả metadata vào chứ không chỉ `summary`:** test set có câu hỏi dạng *"who authored X"*, *"when was X published"*. Nếu chỉ embed summary, câu hỏi chứa tên tác giả không match được document → `retrieval_hit_rate` tụt dù dữ liệu hoàn toàn sạch.

**Hệ quả cần nhớ khi phân tích ở Pha 2:** `summary` chiếm phần lớn `text_for_embedding`, nên corruption *blank summary* và *add noise* mới là hai scenario đánh mạnh nhất vào retrieval.

## 4. ⚠ Bẫy CSV round-trip

`data/clean/papers_clean.csv` **được corruption flow đọc lại** bằng `pd.read_csv`. Hai hệ quả:

1. **Không giữ cột kiểu list trong CSV.** `["a","b"]` round-trip thành chuỗi `"['a', 'b']"` — hỏng ngầm, không báo lỗi.
2. **Chuỗi rỗng `""` bị `pd.read_csv` biến thành `NaN`** theo mặc định. Cột `pdf_url` / `updated` / `comment` được phép rỗng, nên mọi nơi đọc lại CSV **phải dùng**:

```python
pd.read_csv(path, keep_default_na=False)
```

> Đây là contract với Corruption & integration owner. Quên `keep_default_na=False` → `NaN` lọt vào Chroma metadata ở lần rebuild index.

## 5. Ranh giới trách nhiệm

| Việc | Ai làm | Ghi chú |
| --- | --- | --- |
| Gọi API, retry, lưu raw response/records | Source owner | Trả `PaperRecord` **nguyên trạng**, không cần chuẩn hóa |
| Strip JATS, normalize, dedupe, derive cột | **Cleaning owner** | Chịu toàn bộ trách nhiệm chuẩn hóa |
| Sinh `ground_truth_doc_ids` | Test-set owner | Lấy **đúng giá trị cột `paper_id`**, không tự chế ID |
| Quality check / freshness | Observability owner | Dùng `summary_chars`, `age_days`, ngưỡng 100 và `freshness_threshold_days = 180` |
| Corrupt / repair | Corruption owner | Corrupt trên CSV; **repair = chạy lại `build_clean_dataframe` từ raw**, không patch tay |

`build_clean_dataframe()` phải **pure**: chỉ nhận `records` + `run_date`, không đọc/ghi file, không gọi `now()`. Đây là điều kiện để repair từ raw tái lập được đúng baseline.

## 6. Xác minh

```bash
python script/validate_clean_contract.py
```

Script chạy 6 record edge case đi qua `build_clean_dataframe` và assert toàn bộ contract ở trên, **không cần mạng và không cần API key**.

| Exit code | Ý nghĩa |
| --- | --- |
| `0` | Contract đạt |
| `1` | Có check fail |
| `2` | `build_clean_dataframe` chưa implement (trạng thái mong đợi tại CP0) |
