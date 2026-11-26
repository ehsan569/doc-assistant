"""Check the question set against the documents. Run from the repo root:

    python eval/verify_questions.py

For every ANSWERABLE question: at least one gold evidence phrase must appear
word-for-word in a gold page (after tidying whitespace).
For every UNANSWERABLE question: none of its "absent_terms" may appear anywhere
in the 20 pages. This keeps the "not in the documents" claim honest.
Exits with an error if anything fails.
"""
import json
import re
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.docassist.loader import load_page  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]


def squash(text):
    return re.sub(r"\s+", " ", text).strip().lower()


def load_questions(path=ROOT / "eval" / "questions.jsonl"):
    return [json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines() if line.strip()]


def main():
    pages = {p.name: squash(load_page(p)["text"]) for p in sorted((ROOT / "corpus" / "docs").glob("*.md"))}
    questions = load_questions()
    problems = []

    for q in questions:
        if q["answerable"]:
            for page in q["gold_pages"]:
                if page not in pages:
                    problems.append(f"{q['id']}: unknown gold page {page}")
            found = [
                (page, phrase)
                for page in q["gold_pages"]
                for phrase in q["gold_evidence"]
                if page in pages and squash(phrase) in pages[page]
            ]
            if not found:
                problems.append(f"{q['id']}: no gold evidence phrase found in gold pages")
            missing = [p for p in q["gold_evidence"] if not any(squash(p) in t for t in pages.values())]
            if missing:
                problems.append(f"{q['id']}: evidence phrase not in any page: {missing}")
        else:
            for term in q["absent_terms"]:
                where = [name for name, text in pages.items() if squash(term) in text]
                if where:
                    problems.append(f"{q['id']}: term {term!r} IS present in {where}")

    kinds = Counter(q["qtype"] for q in questions)
    print(f"{len(questions)} questions: {dict(kinds)}")
    if len({q["id"] for q in questions}) != len(questions):
        problems.append("duplicate question ids")
    if sum(q["answerable"] for q in questions) != 20 or sum(not q["answerable"] for q in questions) != 10:
        problems.append("expected 20 answerable and 10 unanswerable questions")

    if problems:
        print("\nPROBLEMS:")
        for p in problems:
            print(" -", p)
        sys.exit(1)
    print("All checks passed.")


if __name__ == "__main__":
    main()
