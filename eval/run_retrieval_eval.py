"""Measure retrieval ONLY (no LLM): does search bring back the right passage?

    python eval/run_retrieval_eval.py                       # lexical + dense, both chunking strategies
    python eval/run_retrieval_eval.py --retrievers lexical  # no model download needed

For each answerable question we record:
  * page hit@k      the right PAGE is among the top k chunks
  * evidence hit@k  a top-k chunk actually CONTAINS the sentence that answers the question
(evidence is the stricter test: the right page can come back with the wrong part of it)

For unanswerable questions there is nothing to find, so we only record the top score,
to see later whether a score threshold could help the assistant refuse.

Results are merged into eval/results/: configurations you re-run replace their old rows,
the others are kept. Nothing here is estimated; every number comes from a run.
"""
import argparse
import datetime
import json
import platform
import re
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from eval.verify_questions import load_questions  # noqa: E402
from src.docassist.chunking import STRATEGIES, chunk_stats, load_chunks  # noqa: E402
from src.docassist.retrieve import EMBED_MODEL, get_retriever  # noqa: E402

RESULTS = ROOT / "eval" / "results"
KS = (1, 3, 5)
MAX_K = 10


def squash(text):
    return re.sub(r"\s+", " ", text).strip().lower()


def first_rank(hits, predicate):
    for hit in hits:
        if predicate(hit):
            return hit["rank"]
    return None


def evaluate_question(q, hits):
    row = {
        "question_id": q["id"],
        "question": q["question"],
        "answerable": q["answerable"],
        "qtype": q["qtype"],
        "topic": q["topic"],
        "top1_chunk": hits[0]["chunk_id"],
        "top1_score": round(hits[0]["score"], 4),
        "top5_chunks": json.dumps([h["chunk_id"] for h in hits[:5]]),
    }
    if q["answerable"]:
        gold_pages = set(q["gold_pages"])
        phrases = [squash(p) for p in q["gold_evidence"]]
        page_rank = first_rank(hits, lambda h: h["file"] in gold_pages)
        evidence_rank = first_rank(hits, lambda h: any(p in squash(h["text"]) for p in phrases))
        row["page_rank"] = page_rank
        row["evidence_rank"] = evidence_rank
        row["mrr_page"] = round(1 / page_rank, 4) if page_rank else 0.0
        for k in KS:
            row[f"page_hit@{k}"] = int(page_rank is not None and page_rank <= k)
            row[f"evidence_hit@{k}"] = int(evidence_rank is not None and evidence_rank <= k)
    return row


def summarise(per_question):
    answerable = per_question[per_question["answerable"]]
    rows = []
    for (retriever, strategy), group in answerable.groupby(["retriever", "strategy"]):
        row = {"retriever": retriever, "strategy": strategy, "n_answerable": len(group)}
        for k in KS:
            row[f"page_hit@{k}"] = round(group[f"page_hit@{k}"].mean(), 3)
        for k in KS:
            row[f"evidence_hit@{k}"] = round(group[f"evidence_hit@{k}"].mean(), 3)
        row["mrr_page"] = round(group["mrr_page"].mean(), 3)
        rows.append(row)
    return pd.DataFrame(rows)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--retrievers", default="lexical,dense")
    args = parser.parse_args()
    wanted = [r.strip() for r in args.retrievers.split(",")]

    RESULTS.mkdir(parents=True, exist_ok=True)
    questions = load_questions()
    now = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")

    new_rows, ran = [], []
    for retriever_name in wanted:
        for strategy in STRATEGIES:
            try:
                retriever = get_retriever(retriever_name, strategy)
            except ImportError as error:
                print(f"SKIPPED {retriever_name}/{strategy}: {error}")
                continue
            for q in questions:
                hits = retriever.search(q["question"], k=MAX_K)
                row = evaluate_question(q, hits)
                row.update(retriever=retriever_name, strategy=strategy, run_at=now)
                new_rows.append(row)
            ran.append((retriever_name, strategy))
            print(f"done {retriever_name}/{strategy}")

    if not new_rows:
        sys.exit("Nothing ran.")

    new = pd.DataFrame(new_rows)
    path = RESULTS / "retrieval_per_question.csv"
    if path.exists():
        old = pd.read_csv(path)
        keep = old[~old.apply(lambda r: (r["retriever"], r["strategy"]) in ran, axis=1)]
        combined = pd.concat([keep, new], ignore_index=True)
    else:
        combined = new
    combined["answerable"] = combined["answerable"].astype(bool)
    combined.to_csv(path, index=False)

    summary = summarise(combined)
    summary.to_csv(RESULTS / "retrieval_summary.csv", index=False)

    stats = []
    for strategy in STRATEGIES:
        stats.append({"strategy": strategy, **chunk_stats(load_chunks(strategy))})
    pd.DataFrame(stats).to_csv(RESULTS / "chunk_stats.csv", index=False)

    info_path = RESULTS / "run_info.json"
    info = json.loads(info_path.read_text()) if info_path.exists() else {}
    for retriever_name, strategy in ran:
        info[f"{retriever_name}/{strategy}"] = {
            "run_at": now,
            "python": platform.python_version(),
            "embedding_model": EMBED_MODEL if retriever_name == "dense" else None,
            "questions": len(questions),
            "chunking": {"fixed": "1000 chars, 150 overlap", "headings": "split at # ## ###, then max 1000 chars, 150 overlap, breadcrumb added to searched text"}[strategy],
        }
    info_path.write_text(json.dumps(info, indent=2))

    print("\n" + summary.to_string(index=False))


if __name__ == "__main__":
    main()
