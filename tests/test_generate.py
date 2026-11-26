from types import SimpleNamespace

from src.docassist.generate import REFUSAL, answer_question, build_user_message, parse_response

PASSAGES = [
    {"chunk_id": "a.md#0", "title": "A", "heading": "Intro", "text": "The default is 12."},
    {"chunk_id": "b.md#3", "title": "B", "heading": "", "text": "Other text."},
]
IDS = [p["chunk_id"] for p in PASSAGES]


class FakeClient:
    """Stands in for the Anthropic client so no network or key is needed."""

    def __init__(self, text):
        self.text = text
        self.last_call = None
        self.messages = SimpleNamespace(create=self._create)

    def _create(self, **kwargs):
        self.last_call = kwargs
        return SimpleNamespace(content=[SimpleNamespace(type="text", text=self.text)])


def test_good_answer_keeps_valid_citations():
    r = parse_response('{"answerable": true, "answer": "It is 12.", "citations": ["a.md#0"]}', IDS)
    assert r["answerable"] and r["answer"] == "It is 12."
    assert r["citations"] == ["a.md#0"] and not r["uncited"] and not r["parse_error"]


def test_invented_citations_are_dropped_and_reported():
    r = parse_response('{"answerable": true, "answer": "x", "citations": ["a.md#0", "zzz.md#9"]}', IDS)
    assert r["citations"] == ["a.md#0"]
    assert r["invalid_citations"] == ["zzz.md#9"]


def test_answer_with_no_valid_citation_is_flagged():
    r = parse_response('{"answerable": true, "answer": "x", "citations": ["zzz.md#9"]}', IDS)
    assert r["answerable"] and r["uncited"]


def test_refusal_uses_the_fixed_message():
    r = parse_response('{"answerable": false, "answer": "", "citations": []}', IDS)
    assert not r["answerable"] and r["answer"] == REFUSAL


def test_json_inside_a_code_fence_is_read():
    r = parse_response('```json\n{"answerable": true, "answer": "ok", "citations": ["b.md#3"]}\n```', IDS)
    assert r["answer"] == "ok" and r["citations"] == ["b.md#3"]


def test_citation_in_square_brackets_is_accepted():
    r = parse_response('{"answerable": true, "answer": "ok", "citations": ["[a.md#0]"]}', IDS)
    assert r["citations"] == ["a.md#0"]


def test_garbage_is_a_parse_error_not_a_crash():
    r = parse_response("Sorry, I cannot help.", IDS)
    assert r["parse_error"] and not r["answerable"]


def test_answer_question_sends_passages_and_question():
    client = FakeClient('{"answerable": true, "answer": "12", "citations": ["a.md#0"]}')
    r = answer_question("What is the default?", PASSAGES, client=client, model="test-model")
    sent = client.last_call["messages"][0]["content"]
    assert "[a.md#0] (A > Intro)" in sent and "Question: What is the default?" in sent
    assert client.last_call["model"] == "test-model"
    assert r["citations"] == ["a.md#0"] and r["model"] == "test-model"


def test_prompt_lists_every_passage():
    message = build_user_message("q?", PASSAGES)
    assert "[a.md#0]" in message and "[b.md#3]" in message
