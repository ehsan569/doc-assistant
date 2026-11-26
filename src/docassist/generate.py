"""Turn retrieved passages into a cited answer, or an honest refusal.

The model is told to answer ONLY from the passages, to cite the passage ids it used,
and to say when the passages do not contain the answer. It replies with a small JSON
object so the program can check the citations instead of trusting free text:

    {"answerable": true/false, "answer": "...", "citations": ["file.md#3", ...]}

Citations that do not match a passage we actually supplied are dropped and reported.
"""
import json
import os
import re

REFUSAL = "I couldn't find enough information in the documents to answer that."
DEFAULT_MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-5-5")

SYSTEM_PROMPT = """You are a documentation assistant for DuckDB. You are given numbered passages \
from the DuckDB documentation and a question.

Rules:
1. Answer ONLY from the passages. Do not use outside knowledge, even if you are sure you know the answer.
2. If the passages do not contain enough information to answer the question, set "answerable" to false.
3. If the passages answer only part of the question, answer that part and say what is missing.
4. Cite every passage you relied on, using its id exactly as written in square brackets.
5. Keep the answer short and concrete. Keep exact option names, numbers and SQL as written.

Reply with ONE JSON object and nothing else:
{"answerable": true or false, "answer": "your answer, or an empty string if not answerable", "citations": ["id", "id"]}"""


def format_passages(passages):
    blocks = []
    for p in passages:
        where = p["title"] + (f" > {p['heading']}" if p.get("heading") else "")
        blocks.append(f"[{p['chunk_id']}] ({where})\n{p['text']}")
    return "\n\n---\n\n".join(blocks)


def build_user_message(question, passages):
    return f"Passages:\n\n{format_passages(passages)}\n\nQuestion: {question}"


def parse_response(raw_text, valid_ids):
    """Read the model's JSON reply. Never raises; problems are reported in the result."""
    result = {
        "answerable": False,
        "answer": "",
        "citations": [],
        "invalid_citations": [],
        "uncited": False,
        "parse_error": False,
        "raw": raw_text,
    }
    match = re.search(r"\{.*\}", raw_text, flags=re.DOTALL)
    try:
        data = json.loads(match.group(0)) if match else None
        if not isinstance(data, dict):
            raise ValueError("no JSON object")
        answerable = bool(data.get("answerable"))
        answer = str(data.get("answer") or "").strip()
        cited = [str(c).strip().strip("[]") for c in (data.get("citations") or [])]
    except (ValueError, TypeError):
        result["parse_error"] = True
        return result

    valid = set(valid_ids)
    result["citations"] = [c for c in dict.fromkeys(cited) if c in valid]
    result["invalid_citations"] = [c for c in dict.fromkeys(cited) if c not in valid]
    if not answerable or not answer:
        result["answerable"] = False
        result["answer"] = REFUSAL
    else:
        result["answerable"] = True
        result["answer"] = answer
        result["uncited"] = not result["citations"]
    return result


def answer_question(question, passages, client=None, model=None, max_tokens=800):
    """Ask the model. `passages` are the chunk dicts returned by retrieval."""
    if client is None:
        import anthropic

        client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY from the environment
    model = model or DEFAULT_MODEL
    response = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": build_user_message(question, passages)}],
    )
    raw = "".join(block.text for block in response.content if getattr(block, "type", "text") == "text")
    result = parse_response(raw, [p["chunk_id"] for p in passages])
    result["model"] = model
    return result
