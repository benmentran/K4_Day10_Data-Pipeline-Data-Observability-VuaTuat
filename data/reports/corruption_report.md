# Corruption, Repair & Comparison Report

Generated: 2026-08-06T15:59:01.513143+00:00

Three states of the same corpus, evaluated with the **same frozen test set** and the same retrieval/judge configuration. Only the data changes between states, so every metric difference below is attributable to data quality.

| State | Dataset | Rows | Chroma collection |
|---|---|---:|---|
| Baseline | `data/clean/papers_clean.csv` | 24 | `papers-baseline` |
| Corrupted | `data/clean/papers_corrupted.csv` | 26 | `papers-corrupted` |
| Repaired | `data/clean/papers_clean_repaired.csv` | 24 | `papers-repaired` |

## 1. What was corrupted

| Scenario | Docs hit | Frozen test-set questions hit | Effect |
|---|---:|---|---|
| `drop_latest_record` | 1 | q1 | Delete the newest record entirely (silent data loss at the source). |
| `blank_summary` | 4 | q3, q7 | Blank the summary so the document embeds on metadata only. |
| `inject_summary_noise` | 4 | q4, q9 | Prepend unrelated content to the summary and append random characters to text_for_embedding. |
| `duplicate_record` | 3 | q10, q5 | Append a byte-identical copy of the row, paper_id included. |
| `truncate_title` | 3 | q6 | Truncate the title to a fragment. |
| `stale_published_date` | 4 | q2, q8 | Rewrite published to 2000-01-01 to defeat the freshness check. |

- Rows: 24 -> 26 (1 deleted, 3 duplicated).
- Documents corrupted: 19.
- **Overlap with the frozen test set: 10/10 ground-truth documents** (ratio 1.0). Scenarios with no test-set overlap: none.
- Seed `42`; full per-document audit trail in `data/results/corruption_log.json`.

## 2. Headline

- `retrieval_hit_rate`: **did not move** (0.8000 in the corrupted state); **fully recovered** to 0.8000 after repair.
- `mean_token_f1`: **degraded** 0.4821 -> 0.3035 (-37.1%); **fully recovered** to 0.4821 after repair.
- `judge_accuracy`: **degraded** 0.5000 -> 0.3000 (-40.0%); **fully recovered** to 0.5000 after repair.
- `mean_judge_score`: **degraded** 2.8000 -> 2.2000 (-21.4%); **fully recovered** to 2.8000 after repair.

`retrieval_hit_rate` is a coarse signal on a corpus this small: every question quotes its own document's title, so top_k=4 out of ~24 documents still surfaces the right paper even after its summary is destroyed - and a shorter embedding text can even *raise* title similarity (q7 flips from MISS to hit once its summary is blanked). The damage is therefore visible in the answer-level metrics rather than in the hit rate; the deleted record (q1) is the one case where retrieval provably cannot recover.

## 3. RAG metrics on the frozen test set

| Metric | Baseline | Corrupted | Repaired | Corrupted - Baseline | Repaired - Baseline |
|---|---:|---:|---:|---:|---:|
| retrieval_hit_rate | 0.8000 | 0.8000 | 0.8000 | +0.0000 | +0.0000 |
| mean_token_f1 | 0.4821 | 0.3035 | 0.4821 | -0.1786 | +0.0000 |
| judge_accuracy | 0.5000 | 0.3000 | 0.5000 | -0.2000 | +0.0000 |
| mean_judge_score | 2.8000 | 2.2000 | 2.8000 | -0.6000 | +0.0000 |

## 4. Observability signals

| Signal | Baseline | Corrupted | Repaired |
|---|---|---|---|
| quality status | PASS | FAIL | PASS |
| failed checks | none | paper_id_unique, summary_min_length, freshness_age_days | none |
| total_rows | 24 | 26 | 24 |
| is_fresh | True | False | True |
| stale_rows | 0 | 4 | 0 |
| max_age_days | 175 | 9714 | 175 |
| oldest_published | 2026-02-12 | 2000-01-01 | 2026-02-12 |

## 5. Per-question impact

Retrieval hit and token F1 for every question of the frozen test set.

| Q | Scenario applied to its ground-truth doc | Retrieval B/C/R | token F1 B/C/R |
|---|---|---|---|
| q1 | `drop_latest_record` | hit / MISS / hit | 0.00 / 0.00 / 0.00 |
| q2 | `stale_published_date` | hit / hit / hit | 0.00 / 0.00 / 0.00 |
| q3 | `blank_summary` | hit / hit / hit | 0.00 / 0.00 / 0.00 |
| q4 | `inject_summary_noise` | hit / hit / hit | 0.82 / 0.04 / 0.82 |
| q5 | `duplicate_record` | hit / hit / hit | 1.00 / 1.00 / 1.00 |
| q6 | `truncate_title` | hit / hit / hit | 1.00 / 1.00 / 1.00 |
| q7 | `blank_summary` | MISS / hit / MISS | 0.00 / 0.00 / 0.00 |
| q8 | `stale_published_date` | hit / hit / hit | 1.00 / 0.00 / 1.00 |
| q9 | `inject_summary_noise` | MISS / MISS / MISS | 0.00 / 0.00 / 0.00 |
| q10 | `duplicate_record` | hit / hit / hit | 1.00 / 1.00 / 1.00 |

## 6. Interpretation

**Repair provenance.** The repaired dataset is rebuilt from `data/raw/crossref_records.json` (the raw snapshot frozen at C2) through the same cleaning logic as the baseline - the corrupted CSV is never read back. Fetching Crossref again could return changed records and would invalidate the controlled comparison.

- Repaired vs baseline documents: 24 vs 24; identical paper_id set: **True**.
- Documents missing after repair: none.
- Content identical on title, summary, published, authors_joined, categories_joined, text_for_embedding (whitespace-normalised): **True**; documents that changed: none.

**Why the metrics move.** `text_for_embedding` is dominated by the summary, so blanked and noise-prefixed summaries push a document away from its own question in MiniLM space, and `qa._extract_answer` returns the first sentence of that summary - an empty or off-topic answer scores ~0 token F1. Deleting the newest record makes its question unanswerable at any top_k. Stale dates corrupt the answer of date questions directly and trip the freshness monitor. Duplicated paper_ids consume top_k slots with a repeat of the same document and break the uniqueness check.

**What this proves.** Bad data degrades the agent even though the code, the prompts, the embedding model and the test set are byte-identical across the three runs; rebuilding the clean layer from the raw snapshot restores the baseline behaviour. Quality and freshness checks flag the corrupted state before any evaluation is run, which is the point of the observability layer.
