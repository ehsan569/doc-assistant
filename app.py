"""Streamlit app: ask a question, see the answer AND the passages it was built from.

    streamlit run app.py

Needs ANTHROPIC_API_KEY for answers. Without it, the app still shows search results.
"""
import os

import streamlit as st

from src.docassist.generate import DEFAULT_MODEL, REFUSAL, answer_question
from src.docassist.retrieve import get_retriever

st.set_page_config(page_title="DuckDB docs assistant", layout="wide")
st.title("DuckDB docs assistant")
st.caption(
    "Answers come only from 20 pages of the DuckDB documentation. "
    "The passages used are shown on the right so you can check every claim."
)

has_key = bool(os.environ.get("ANTHROPIC_API_KEY"))
default_retriever = os.environ.get("DOCASSIST_DEFAULT_RETRIEVER", "dense")

with st.sidebar:
    st.header("Settings")
    retriever_kind = st.selectbox(
        "Search method", ["dense", "lexical"], index=["dense", "lexical"].index(default_retriever),
        help="dense = meaning-based (embeddings). lexical = keyword-based (BM25).",
    )
    strategy = st.selectbox("Chunking", ["headings", "fixed"], help="How the pages were cut up before indexing.")
    k = st.slider("Passages to retrieve", 2, 8, 5)
    st.write(f"Model: `{DEFAULT_MODEL}`" if has_key else "No `ANTHROPIC_API_KEY` found: showing search results only.")


@st.cache_resource(show_spinner="Loading the search index (the first run downloads the embedding model)...")
def load_retriever(kind, chunking):
    return get_retriever(kind, chunking)


with st.form("ask"):
    question = st.text_input("Your question", placeholder="e.g. What is the default memory limit in DuckDB?")
    submitted = st.form_submit_button("Ask")

if submitted and question.strip():
    try:
        retriever = load_retriever(retriever_kind, strategy)
    except ImportError as error:
        st.error(f"Could not start the {retriever_kind} search: {error}. Try the lexical option.")
        st.stop()

    passages = retriever.search(question, k=k)
    result = None
    if has_key:
        with st.spinner("Reading the passages..."):
            try:
                result = answer_question(question, passages)
            except Exception as error:  # network, key or quota problems
                st.error(f"The model call failed: {error}")

    number = {p["chunk_id"]: i for i, p in enumerate(passages, start=1)}
    left, right = st.columns([1, 1], gap="large")

    with left:
        st.subheader("Answer")
        if result is None:
            if not has_key:
                st.info("Set ANTHROPIC_API_KEY to get a written answer. The retrieved passages are shown on the right.")
        elif result["parse_error"]:
            st.error("The model's reply could not be read. Try again.")
        elif not result["answerable"]:
            st.warning(REFUSAL)
        else:
            st.write(result["answer"])
            if result["uncited"]:
                st.error("This answer cites no valid passage, so it cannot be checked. Do not rely on it.")
            else:
                links = []
                for chunk_id in result["citations"]:
                    p = passages[number[chunk_id] - 1]
                    links.append(f"[{number[chunk_id]}]({p['web_url']}) {p['title']}")
                st.markdown("**Sources:** " + " · ".join(links))
            if result["invalid_citations"]:
                st.caption(f"Ignored citations that were not in the retrieved passages: {result['invalid_citations']}")

    with right:
        st.subheader("Passages retrieved")
        cited = set(result["citations"]) if result else set()
        for p in passages:
            with st.container(border=True):
                where = p["title"] + (f" › {p['heading']}" if p["heading"] else "")
                tag = "  ✅ used in the answer" if p["chunk_id"] in cited else ""
                st.markdown(f"**[{number[p['chunk_id']]}] [{where}]({p['web_url']})**{tag}")
                st.caption(f"{p['chunk_id']} · score {p['score']:.3f}")
                st.markdown(p["text"])
