"""Build eval/results/REPORT.md from the result files and paste it into the README.

    python eval/make_report.py

Everything in the report is read from eval/results/*.csv, so it can never drift from the
real runs. The README block between the RESULTS markers is replaced each time.
"""
import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

RESULTS = ROOT / "eval" / "results"
README = ROOT / "README.md"
START, END = "<!-- RESULTS:START -->", "<!-- RESULTS:END -->"


def table(df):
    """Markdown table without extra dependencies."""
    df = df.copy()
    cols = list(df.columns)
    lines = ["| " + " | ".join(str(c) for c in cols) + " |", "|" + "|".join("---" for _ in cols) + "|"]
    for _, row in df.iterrows():
        cells = []
        for c in cols:
            v = row[c]
            if isinstance(v, float):
                v = "" if pd.isna(v) else (f"{v:.0f}" if v == int(v) and "hit" not in c and "mrr" not in c else f"{v:.3g}")
            cells.append(str(v).replace("|", "\\|"))
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)


def build():
    out = []
    summary = pd.read_csv(RESULTS / "retrieval_summary.csv")
    per_q = pd.read_csv(RESULTS / "retrieval_per_question.csv")
    info = json.loads((RESULTS / "run_info.json").read_text())

    out.append("### Retrieval (no LLM involved)\n")
    out.append(
        "Share of the 20 answerable questions where the right passage came back in the top k. "
        "**Page** = the right page is in the top k. **Evidence** = a top-k passage contains the sentence that "
        "answers the question. One question = 5 percentage points.\n"
    )
    cols = ["retriever", "strategy", "page_hit@1", "page_hit@3", "page_hit@5",
            "evidence_hit@1", "evidence_hit@3", "evidence_hit@5", "mrr_page"]
    out.append(table(summary[cols]) + "\n")
    configs = sorted(set(summary["retriever"] + "/" + summary["strategy"]))
    if not any(c.startswith("dense") for c in configs):
        out.append("> Dense (embedding) retrieval has **not been run yet** in this repo version, so only the keyword "
                   "baseline is reported. Run `python eval/run_retrieval_eval.py` to add it.\n")

    stats = pd.read_csv(RESULTS / "chunk_stats.csv")
    out.append("### Chunking strategies\n")
    out.append(table(stats) + "\n")

    answerable = per_q[per_q["answerable"]].copy()
    answerable["config"] = answerable["retriever"] + " / " + answerable["strategy"]
    misses = answerable[(answerable["page_hit@1"] == 0) | (answerable["evidence_hit@1"] == 0)]
    out.append("### Where retrieval missed at rank 1\n")
    if len(misses):
        view = misses[["question_id", "config", "page_rank", "evidence_rank", "top1_chunk", "question"]]
        out.append(table(view) + "\n")
        out.append("`page_rank` / `evidence_rank` = position of the first correct passage (empty = not in the top 10).\n")
    else:
        out.append("None.\n")

    per_q["config"] = per_q["retriever"] + " / " + per_q["strategy"]
    scores = per_q.groupby(["config", "answerable"])["top1_score"].agg(["min", "mean", "max"]).round(2).reset_index()
    out.append("### Top-1 search score: answerable vs unanswerable questions\n")
    out.append(table(scores) + "\n")
    out.append("If the ranges overlap, a score cut-off alone cannot decide when to refuse.\n")

    answers_path = RESULTS / "answer_results.csv"
    out.append("### Answer quality (separate from retrieval)\n")
    if answers_path.exists():
        answers = pd.read_csv(answers_path)
        counts = answers.groupby(["retriever", "strategy", "outcome"]).size().reset_index(name="questions")
        out.append(table(counts) + "\n")
        answered = answers[answers["outcome"] == "answered"]
        labelled = answered[answered["human_correct"].notna()]
        out.append(f"Human-labelled: {len(labelled)} of {len(answered)} 'answered' rows. ")
        if len(labelled):
            acc = labelled.groupby(["retriever", "strategy"])["human_correct"].mean().round(3).reset_index()
            out.append("Share judged correct among labelled rows:\n\n" + table(acc) + "\n")
        else:
            out.append("Correctness has not been labelled yet, so no accuracy is reported.\n")
    else:
        out.append("> Answer evaluation has **not been run yet** (it needs an Anthropic API key). "
                   "No answer-quality numbers are reported.\n")

    out.append("### Run details\n")
    rows = [{"config": k, "run_at": v["run_at"], "python": v["python"],
             "embedding_model": v["embedding_model"] or "-", "questions": v["questions"]} for k, v in info.items()]
    out.append(table(pd.DataFrame(rows)) + "\n")
    return "\n".join(out)


def main():
    body = build()
    (RESULTS / "REPORT.md").write_text("# Evaluation report (generated)\n\n" + body, encoding="utf-8")
    text = README.read_text(encoding="utf-8")
    if START in text and END in text:
        head, rest = text.split(START, 1)
        _, tail = rest.split(END, 1)
        README.write_text(head + START + "\n" + body + "\n" + END + tail, encoding="utf-8")
        print("README results block updated.")
    print("Wrote eval/results/REPORT.md")


if __name__ == "__main__":
    main()
