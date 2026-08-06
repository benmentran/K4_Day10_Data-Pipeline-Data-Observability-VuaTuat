# Baseline Pipeline Report

## Source

- source: Crossref REST API
- raw_records: 24
- clean_records: 24

## RAG metrics

| Metric | Baseline |
|---|---:|
| retrieval_hit_rate | 0.8000 |
| mean_token_f1 | 0.4821 |
| judge_accuracy | 0.5000 |
| mean_judge_score | 2.8000 |

## Observability

- Quality: **PASS** (10/10 checks, failed: none)
- Fresh: **True** (threshold 180 days, oldest 2026-02-12)
- Stale rows: 0

### Data quality checks

| Check | Severity | Result | Observed | Expected |
|---|---|---|---:|---:|
| required_columns_present | error | PASS | 14 | 10 |
| row_count_minimum | error | PASS | 24 | >= 20 |
| paper_id_not_null | error | PASS | 0 | 0 |
| paper_id_unique | error | PASS | 0 | 0 |
| title_not_null | error | PASS | 0 | 0 |
| summary_min_length | error | PASS | 0 | 0 |
| text_for_embedding_not_null | error | PASS | 0 | 0 |
| no_nan_in_index_columns | error | PASS | 0 | 0 |
| freshness_age_days | error | PASS | 0 | 0 |
| categories_completeness | warning | PASS | 0 | 0 |
