"""Measure ANSWER quality separately from retrieval. Needs ANTHROPIC_API_KEY.

    export ANTHROPIC_API_KEY=...        (never commit this)
    python eval/run_answer_eval.py --retriever dense

For every question we run retrieval, give the top-k passages to the model, and record
what happened. Each row gets an automatic `outcome` that separates the two failure types:

  answerable questions
    retrieval_miss_refused    the answer was NOT in the retrieved passages, the model refused (good behaviour)
    retrieval_miss_answered   the answer was NOT in the retrieved passages, the model answered anyway (check it)
    wrongly_refused           the answer WAS in the passages, the model refused (generation failure)
    answered                  the answer WAS in the passages, the model answered (needs a human check)
  unanswerable questions
    correct_refusal           the model said it could not find the answer
    should_have_refused       the model answered a question the documents do not cover

Whether an `answered` response is actually CORRECT is a judgement. It is left blank in the
`human_correct` column (1 = correct, 0 = wrong) for you to fill in. Accuracy is only reported
from rows that have been labelled, and the report says how many.
"""
import argparse
import datetime
import json
import re
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from eval.verify_questions import load_questions  # noqa: E402
from src.docassist.chunking import STRATEGIES  # noqa: E402
from src.docassist.generate import DEFAULT_MODEL, answer_question  # noqa: E402
from src.docassist.retrieve import get_retriever  # noqa: E402

RESULTS = ROOT / "eval" / "results"
PATH = RESULTS / "answer_results.csv"


def squash(text):
    return re.sub(r"\s+", " ", text).strip().lower()


def classify(q, passages, result):
    context = " ".join(squash(p["text"]) for p in passages)
    refused = not result["answerable"]
    if not q["answerable"]:
        return "correct_refusal" if refused else "should_have_refused"
    evidence_in_context = any(squash(e) in context for e in q["gold_evidence"])
    if not evidence_in_context:
        return "retrieval_miss_refused" if refused else "retrieval_miss_answered"
    return "wrongly_refused" if refused else "answered"


def evaluate_answers(questions, retriever, retriever_name, strategy, k, answer_fn, model):
    rows = []
    for q in questions:
        passages = retriever.search(q["question"], k=k)
        result = answer_fn(q["question"], passages)
        gold = set(q["gold_pages"])
        cited_files = {c.split("#")[0] for c in result["citations"]}
        rows.append(
            {
                "question_id": q["id"],
                "question": q["question"],
                "answerable": q["answerable"],
                "qtype": q["qtype"],
                "topic": q["topic"],
                "retriever": retriever_name,
                "strategy": strategy,
                "k": k,
                "model": model,
                "outcome": classify(q, passages, result),
                "model_said_answerable": result["answerable"],
                "answer": result["answer"],
                "citations": json.dumps(result["citations"]),
                "invalid_citations": json.dumps(result["invalid_citations"]),
                "uncited": result["uncited"],
                "parse_error": result["parse_error"],
                "cited_gold_page": bool(q["answerable"] and result["answerable"] and cited_files & gold),
                "human_correct": "",
                "human_notes": "",
            }
        )
    return rows


def merge_and_save(new_rows, path=PATH):
    new = pd.DataFrame(new_rows)
    run_at = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")
    new["run_at"] = run_at
    if path.exists():
        old = pd.read_csv(path, dtype={"human_correct": str})
        key = set(zip(new["retriever"], new["strategy"], new["k"], new["model"]))
        mask = old.apply(lambda r: (r["retriever"], r["strategy"], r["k"], r["model"]) in key, axis=1)
        # Keep any human labels already entered for the same question/config.
        labels = old[mask].set_index(["question_id", "retriever", "strategy", "k", "model"])[["human_correct", "human_notes"]]
        new = new.set_index(["question_id", "retriever", "strategy", "k", "model"])
        for col in ("human_correct", "human_notes"):
            existing = labels[col].reindex(new.index)
            new[col] = existing.where(existing.notna(), new[col])
        new = new.reset_index()
        combined = pd.concat([old[~mask], new], ignore_index=True)
    else:
        combined = new
    path.parent.mkdir(parents=True, exist_ok=True)
    combined.to_csv(path, index=False)
    return combined


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--retriever", choices=["lexical", "dense"], default="dense")
    parser.add_argument("--strategies", default="fixed,headings")
    parser.add_argument("-k", type=int, default=5)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    args = parser.parse_args()

    import os

    if not os.environ.get("ANTHROPIC_API_KEY"):
        sys.exit("Set ANTHROPIC_API_KEY first (export ANTHROPIC_API_KEY=...). Nothing was run.")

    import anthropic

    client = anthropic.Anthropic()
    questions = load_questions()
    all_rows = []
    for strategy in [s.strip() for s in args.strategies.split(",")]:
        if strategy not in STRATEGIES:
            sys.exit(f"Unknown strategy {strategy}")
        retriever = get_retriever(args.retriever, strategy)
        rows = evaluate_answers(
            questions, retriever, args.retriever, strategy, args.k,
            lambda question, passages: answer_question(question, passages, client=client, model=args.model),
            args.model,
        )
        all_rows.extend(rows)
        print(f"done {args.retriever}/{strategy}")
    combined = merge_and_save(all_rows)
    print(combined.groupby(["retriever", "strategy", "outcome"]).size().to_string())
    print(f"\nSaved to {PATH}. Fill in the human_correct column for the 'answered' rows.")


if __name__ == "__main__":
    main()
