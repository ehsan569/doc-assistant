# Evaluation report (generated)

### Retrieval (no LLM involved)

Share of the 20 answerable questions where the right passage came back in the top k. **Page** = the right page is in the top k. **Evidence** = a top-k passage contains the sentence that answers the question. One question = 5 percentage points.

| retriever | strategy | page_hit@1 | page_hit@3 | page_hit@5 | evidence_hit@1 | evidence_hit@3 | evidence_hit@5 | mrr_page |
|---|---|---|---|---|---|---|---|---|
| lexical | fixed | 0.95 | 1 | 1 | 0.9 | 0.95 | 0.95 | 0.975 |
| lexical | headings | 0.95 | 1 | 1 | 0.95 | 0.95 | 1 | 0.975 |

> Dense (embedding) retrieval has **not been run yet** in this repo version, so only the keyword baseline is reported. Run `python eval/run_retrieval_eval.py` to add it.

### Chunking strategies

| strategy | chunks | min_chars | mean_chars | max_chars | under_200_chars |
|---|---|---|---|---|---|
| fixed | 267 | 31 | 825 | 998 | 5 |
| headings | 318 | 38 | 677 | 1000 | 24 |

### Where retrieval missed at rank 1

| question_id | config | page_rank | evidence_rank | top1_chunk | question |
|---|---|---|---|---|---|
| q02 | lexical / fixed | 2 | 6 | data__csv__tips.md#2 | How many rows does DuckDB sample by default when detecting CSV column types? |
| q08 | lexical / fixed | 1 | 2 | guides__performance__indexing.md#1 | How much smaller was the storage size when the timestamp column was ordered in the microbenchmark? |
| q02 | lexical / headings | 2 | 4 | data__csv__tips.md#6 | How many rows does DuckDB sample by default when detecting CSV column types? |

`page_rank` / `evidence_rank` = position of the first correct passage (empty = not in the top 10).

### Top-1 search score: answerable vs unanswerable questions

| config | answerable | min | mean | max |
|---|---|---|---|---|
| lexical / fixed | False | 5.95 | 12.7 | 22.5 |
| lexical / fixed | True | 12.7 | 19.3 | 30.5 |
| lexical / headings | False | 8.77 | 13.4 | 22.6 |
| lexical / headings | True | 13.6 | 21.2 | 36.2 |

If the ranges overlap, a score cut-off alone cannot decide when to refuse.

### Answer quality (separate from retrieval)

> Answer evaluation has **not been run yet** (it needs an Anthropic API key). No answer-quality numbers are reported.

### Run details

| config | run_at | python | embedding_model | questions |
|---|---|---|---|---|
| lexical/fixed | 2026-11-26T19:01:07+00:00 | 3.13.18 | - | 30 |
| lexical/headings | 2026-11-26T19:01:07+00:00 | 3.13.18 | - | 30 |
