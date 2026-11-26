"""Turn the evaluation results into clean tables for Power BI.

    python eval/export_powerbi.py

Writes CSV files to powerbi/data/. Run it again after every evaluation run, then press
Refresh in Power BI. Column names avoid '@' and spaces so they are easy to use in DAX.
"""
import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from eval.verify_questions import load_questions  # noqa: E402

RESULTS = ROOT / "eval" / "results"
OUT = ROOT / "powerbi" / "data"


def main():
    OUT.mkdir(parents=True, exist_ok=True)

    questions = pd.DataFrame(
        [
            {
                "question_id": q["id"],
                "question": q["question"],
                "answerable": q["answerable"],
                "qtype": q["qtype"],
                "topic": q["topic"],
                "gold_pages": "; ".join(q["gold_pages"]),
                "competes_with": "; ".join(q["competes_with"]),
                "notes": q["notes"],
            }
            for q in load_questions()
        ]
    )
    questions.to_csv(OUT / "dim_questions.csv", index=False)

    retrieval = pd.read_csv(RESULTS / "retrieval_per_question.csv")
    retrieval = retrieval.rename(columns=lambda c: c.replace("@", "_at_"))
    retrieval["config"] = retrieval["retriever"] + " / " + retrieval["strategy"]
    keep = [
        "question_id", "retriever", "strategy", "config", "page_rank", "evidence_rank", "mrr_page",
        "page_hit_at_1", "page_hit_at_3", "page_hit_at_5",
        "evidence_hit_at_1", "evidence_hit_at_3", "evidence_hit_at_5",
        "top1_chunk", "top1_score", "run_at",
    ]
    retrieval[keep].to_csv(OUT / "fact_retrieval.csv", index=False)

    summary = pd.read_csv(RESULTS / "retrieval_summary.csv").rename(columns=lambda c: c.replace("@", "_at_"))
    summary["config"] = summary["retriever"] + " / " + summary["strategy"]
    summary.to_csv(OUT / "retrieval_summary.csv", index=False)

    pd.read_csv(RESULTS / "chunk_stats.csv").to_csv(OUT / "chunk_stats.csv", index=False)

    answers_path = RESULTS / "answer_results.csv"
    if answers_path.exists():
        answers = pd.read_csv(answers_path)
        answers["config"] = answers["retriever"] + " / " + answers["strategy"]
        answers.to_csv(OUT / "fact_answers.csv", index=False)
        print("answers exported:", len(answers), "rows")
    else:
        print("No answer results yet (run eval/run_answer_eval.py first). fact_answers.csv not written.")
        (OUT / "fact_answers.csv").unlink(missing_ok=True)

    info = RESULTS / "run_info.json"
    if info.exists():
        rows = [{"config": k, **{kk: (json.dumps(vv) if isinstance(vv, dict) else vv) for kk, vv in v.items()}}
                for k, v in json.loads(info.read_text()).items()]
        pd.DataFrame(rows).to_csv(OUT / "run_info.csv", index=False)

    print("Wrote:", ", ".join(sorted(p.name for p in OUT.glob("*.csv"))))


if __name__ == "__main__":
    main()
