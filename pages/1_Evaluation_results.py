"""Evaluation dashboard: reads the real result files in eval/results/. Nothing is typed in by hand."""
import json
from pathlib import Path

import pandas as pd
import streamlit as st

RESULTS = Path(__file__).resolve().parents[1] / "eval" / "results"

st.set_page_config(page_title="Evaluation results", layout="wide")
st.title("Evaluation results")
st.caption(
    "30 questions: 20 answerable from the docs, 10 not. Retrieval and answer quality are measured separately. "
    "Every number below is read from eval/results/."
)

summary_path = RESULTS / "retrieval_summary.csv"
per_q_path = RESULTS / "retrieval_per_question.csv"
if not summary_path.exists():
    st.warning("No results yet. Run `python eval/run_retrieval_eval.py` first.")
    st.stop()

summary = pd.read_csv(summary_path)
summary["config"] = summary["retriever"] + " / " + summary["strategy"]
per_q = pd.read_csv(per_q_path)
per_q["config"] = per_q["retriever"] + " / " + per_q["strategy"]

st.subheader("Retrieval: does search bring back the right passage?")
st.write(
    "**Page hit@k**: the right page is among the top k passages. "
    "**Evidence hit@k**: a top-k passage actually contains the sentence that answers the question (stricter). "
    "Based on the 20 answerable questions."
)

metrics = ["page_hit@1", "page_hit@3", "page_hit@5", "evidence_hit@1", "evidence_hit@3", "evidence_hit@5", "mrr_page"]
left, right = st.columns(2)
with left:
    st.markdown("**Page hit@k**")
    st.bar_chart(summary.set_index("config")[["page_hit@1", "page_hit@3", "page_hit@5"]], height=300, stack=False)
with right:
    st.markdown("**Evidence hit@k**")
    st.bar_chart(summary.set_index("config")[["evidence_hit@1", "evidence_hit@3", "evidence_hit@5"]], height=300, stack=False)
st.dataframe(summary[["config", "n_answerable"] + metrics], hide_index=True, use_container_width=True)
st.caption("Small sample (20 answerable questions): one question is 5 percentage points. Treat small gaps as noise.")

st.subheader("Where retrieval missed")
answerable = per_q[per_q["answerable"]]
misses = answerable[(answerable["page_hit@1"] == 0) | (answerable["evidence_hit@1"] == 0)]
st.dataframe(
    misses[["question_id", "config", "page_rank", "evidence_rank", "top1_chunk", "question"]],
    hide_index=True, use_container_width=True,
)
st.caption("Rank = position of the first correct passage among the top 10. Empty = not in the top 10.")

st.subheader("Can the search score tell answerable from unanswerable questions?")
scores = per_q.groupby(["config", "answerable"])["top1_score"].agg(["min", "mean", "max"]).round(3).reset_index()
st.dataframe(scores, hide_index=True, use_container_width=True)
st.caption("If the ranges overlap, a score cut-off alone cannot decide when to say 'I couldn't find enough information'.")

answers_path = RESULTS / "answer_results.csv"
st.subheader("Answer quality (separate from retrieval)")
if answers_path.exists():
    answers = pd.read_csv(answers_path)
    answers["config"] = answers["retriever"] + " / " + answers["strategy"]
    counts = answers.groupby(["config", "outcome"]).size().unstack(fill_value=0)
    st.bar_chart(counts, height=320, stack=False)
    st.dataframe(counts.reset_index(), hide_index=True, use_container_width=True)
    labelled = answers[(answers["outcome"] == "answered") & answers["human_correct"].notna()]
    st.write(f"Human-labelled answers: **{len(labelled)}** of {int((answers['outcome'] == 'answered').sum())} answered rows.")
    if len(labelled):
        st.write(labelled.groupby("config")["human_correct"].mean().round(3).rename("share judged correct"))
else:
    st.info("Answer evaluation has not been run yet (needs an Anthropic API key): `python eval/run_answer_eval.py`.")

info_path = RESULTS / "run_info.json"
if info_path.exists():
    with st.expander("How these runs were configured"):
        st.json(json.loads(info_path.read_text()))
