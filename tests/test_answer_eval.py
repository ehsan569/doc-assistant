import pandas as pd

from eval.run_answer_eval import classify, evaluate_answers, merge_and_save
from eval.verify_questions import load_questions
from src.docassist.retrieve import get_retriever

ANSWERED = {"answerable": True, "answer": "x", "citations": [], "invalid_citations": [], "uncited": True, "parse_error": False}
REFUSED = {"answerable": False, "answer": "no", "citations": [], "invalid_citations": [], "uncited": False, "parse_error": False}


def question(answerable, evidence=("needle",)):
    return {"answerable": answerable, "gold_evidence": list(evidence), "gold_pages": ["a.md"]}


def passages(text):
    return [{"text": text}]


def test_outcomes_for_answerable_questions():
    q = question(True)
    assert classify(q, passages("has the needle in it"), ANSWERED) == "answered"
    assert classify(q, passages("has the needle in it"), REFUSED) == "wrongly_refused"
    assert classify(q, passages("nothing relevant"), ANSWERED) == "retrieval_miss_answered"
    assert classify(q, passages("nothing relevant"), REFUSED) == "retrieval_miss_refused"


def test_outcomes_for_unanswerable_questions():
    q = question(False, evidence=())
    assert classify(q, passages("anything"), REFUSED) == "correct_refusal"
    assert classify(q, passages("anything"), ANSWERED) == "should_have_refused"


def test_full_run_with_a_fake_model_covers_all_30_questions(tmp_path):
    questions = load_questions()
    retriever = get_retriever("lexical", "fixed")
    rows = evaluate_answers(questions, retriever, "lexical", "fixed", 5, lambda q, p: REFUSED, "fake-model")
    assert len(rows) == 30
    outcomes = {r["outcome"] for r in rows}
    assert outcomes <= {"correct_refusal", "retrieval_miss_refused", "wrongly_refused"}
    assert sum(r["outcome"] == "correct_refusal" for r in rows) == 10

    path = tmp_path / "answers.csv"
    merge_and_save(rows, path)
    saved = pd.read_csv(path, dtype={"human_correct": str})
    saved.loc[0, "human_correct"] = "1"
    saved.to_csv(path, index=False)

    # Re-running the same configuration must keep a human label that was already entered.
    merged = merge_and_save(rows, path)
    assert len(merged) == 30
    assert str(merged.loc[0, "human_correct"]) in ("1", "1.0")
