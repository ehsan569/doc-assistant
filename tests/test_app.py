from pathlib import Path

from streamlit.testing.v1 import AppTest

import src.docassist.generate as generate

APP = str(Path(__file__).resolve().parents[1] / "app.py")


def run_app(question, monkeypatch, fake_result=None):
    monkeypatch.setenv("DOCASSIST_DEFAULT_RETRIEVER", "lexical")
    if fake_result is None:
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    else:
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key-not-real")
        monkeypatch.setattr(generate, "answer_question", lambda q, p, **kw: fake_result(p))
    at = AppTest.from_file(APP, default_timeout=60).run()
    at.text_input[0].set_value(question)
    at.button[0].click().run()
    return at


def test_without_api_key_it_still_shows_passages(monkeypatch):
    at = run_app("What does union_by_name do?", monkeypatch)
    assert not at.exception
    assert any("ANTHROPIC_API_KEY" in i.value for i in at.info)
    assert any("union_by_name" in m.value for m in at.markdown)


def test_answer_shows_sources_with_links(monkeypatch):
    def fake(passages):
        return {"answerable": True, "answer": "It unifies schemas.", "citations": [passages[0]["chunk_id"]],
                "invalid_citations": [], "uncited": False, "parse_error": False}

    at = run_app("What does union_by_name do?", monkeypatch, fake)
    assert not at.exception
    text = " ".join(m.value for m in at.markdown)
    assert "**Sources:**" in text and "https://duckdb.org/" in text
    assert "used in the answer" in text


def test_refusal_is_shown_as_a_warning(monkeypatch):
    def fake(passages):
        return {"answerable": False, "answer": generate.REFUSAL, "citations": [], "invalid_citations": [],
                "uncited": False, "parse_error": False}

    at = run_app("How do I connect DuckDB to Snowflake?", monkeypatch, fake)
    assert not at.exception
    assert any(generate.REFUSAL in w.value for w in at.warning)


def test_results_page_renders_from_the_result_files():
    page = str(Path(__file__).resolve().parents[1] / "pages" / "1_Evaluation_results.py")
    at = AppTest.from_file(page, default_timeout=60).run()
    assert not at.exception
    assert any("Retrieval" in s.value for s in at.subheader)
    assert len(at.dataframe) >= 3
