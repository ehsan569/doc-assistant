# Building the Power BI dashboard

**Status: not built yet.** This folder contains the data and the recipe. No `.pbix` file exists, because Power BI Desktop only runs on Windows and the project was built on Linux with a Mac as the user's machine. The steps below were written from the data's structure and have not been clicked through, so expect small label differences in the Power BI menus.

## Two ways to build it

* **Power BI Service (browser, works on a Mac):** sign in at app.powerbi.com with a work/school account (a Brunel account may work; personal Gmail accounts usually do not). Create a report from uploaded CSV files. Fewer modelling options than Desktop, but enough for the pages below.
* **Power BI Desktop on a Windows PC** (university lab or a borrowed machine): full modelling. Save the `.pbix` into this folder.

Either way, export screenshots into `docs/images/` and link them from the README. A screenshot is what a recruiter will actually see.

## 1. Refresh the data

```bash
python eval/run_retrieval_eval.py      # adds dense results
python eval/run_answer_eval.py --retriever dense   # needs ANTHROPIC_API_KEY
python eval/export_powerbi.py          # rewrites powerbi/data/*.csv
```

Load whichever of these CSVs exist from `powerbi/data/`:

| File | One row per | Use |
|---|---|---|
| `dim_questions.csv` | question (30) | question text, topic, answerable or not, type |
| `fact_retrieval.csv` | question x retriever x chunking | ranks, hit flags, top-1 score |
| `fact_answers.csv` (after the answer run) | question x retriever x chunking | outcome, answer, human label |
| `retrieval_summary.csv` | retriever x chunking | the headline table, already computed |
| `chunk_stats.csv` | chunking strategy | chunk counts and sizes |
| `run_info.csv` | run | model, Python version, dates |

## 2. Model

Relationships (both many-to-one, single direction from `dim_questions` to the fact table):

* `dim_questions[question_id]` 1 -> * `fact_retrieval[question_id]`
* `dim_questions[question_id]` 1 -> * `fact_answers[question_id]`

Leave the summary, chunk-stats and run-info tables unconnected.

In Power Query, check these column types: hit columns and `mrr_page` as Decimal, ranks as Whole number (blanks are expected for unanswerable questions), `answerable` as True/False.

## 3. Measures

Hit rates must be computed over **answerable questions only**; the unanswerable questions have blank hit columns, and the average ignores blanks, so a plain average is correct.

```DAX
Page Hit @1     = AVERAGE ( fact_retrieval[page_hit_at_1] )
Page Hit @3     = AVERAGE ( fact_retrieval[page_hit_at_3] )
Evidence Hit @1 = AVERAGE ( fact_retrieval[evidence_hit_at_1] )
Evidence Hit @5 = AVERAGE ( fact_retrieval[evidence_hit_at_5] )
MRR (page)      = AVERAGE ( fact_retrieval[mrr_page] )

Answerable Qs   = CALCULATE ( DISTINCTCOUNT ( dim_questions[question_id] ), dim_questions[answerable] = TRUE () )

Top-1 Score (answerable)   = CALCULATE ( AVERAGE ( fact_retrieval[top1_score] ), dim_questions[answerable] = TRUE () )
Top-1 Score (unanswerable) = CALCULATE ( AVERAGE ( fact_retrieval[top1_score] ), dim_questions[answerable] = FALSE () )

-- after the answer run:
Correct Refusal Rate =
DIVIDE (
    CALCULATE ( COUNTROWS ( fact_answers ), fact_answers[outcome] = "correct_refusal" ),
    CALCULATE ( COUNTROWS ( fact_answers ), dim_questions[answerable] = FALSE () )
)

Labelled Answers = CALCULATE ( COUNTROWS ( fact_answers ), fact_answers[outcome] = "answered", NOT ISBLANK ( fact_answers[human_correct] ) )
Human-judged Accuracy =
DIVIDE (
    CALCULATE ( SUM ( fact_answers[human_correct] ), fact_answers[outcome] = "answered" ),
    [Labelled Answers]
)
```

Show `Labelled Answers` next to `Human-judged Accuracy` so nobody reads an accuracy figure built from a handful of labelled rows.

## 4. Pages

**Page 1, Retrieval.** Clustered column chart: axis = `config`, values = Page Hit @1, Evidence Hit @1, Evidence Hit @5 (not stacked: they overlap, stacking would mislead). Table: the questions where `evidence_hit_at_1` = 0, with `question`, `page_rank`, `evidence_rank`, `top1_chunk`. A slicer on `config`.

**Page 2, Answers** (after the answer run). Stacked bar of `outcome` counts per `config` (stacking is right here, outcomes are exclusive). Cards: Correct Refusal Rate, Human-judged Accuracy, Labelled Answers. Table of `answer` and `human_notes` for `retrieval_miss_answered` and `should_have_refused` rows, which are the interesting failures.

**Page 3, Chunking and scores.** Clustered column of `chunk_stats` (chunks and mean_chars per strategy). Scatter or strip chart of `top1_score` by `answerable`: the two ranges overlap, which is the reason a score threshold cannot decide when to refuse.

## 5. Honesty checklist for the screenshots

* Title each page with the sample size ("20 answerable questions, 1 question = 5 points").
* Put the run date and model from `run_info.csv` on the page.
* Do not add an overall "accuracy" card unless it comes from labelled answer rows.
