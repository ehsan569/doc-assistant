"""Two ways to find the chunks that best match a question.

LexicalRetriever  BM25 keyword matching. No model download. A fair baseline.
DenseRetriever    Embeddings stored in Chroma. Matches on meaning, not just words.

Both expose:  search(question, k) -> list of result dicts
Each result is the chunk dict plus "score" (higher = better) and "rank" (1 = best).
"""
import os
import re
from pathlib import Path

from .chunking import load_chunks

EMBED_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
DEFAULT_CHROMA_DIR = Path(
    os.environ.get("DOCASSIST_CHROMA_DIR", Path.home() / ".docassist" / "chroma_db")
)


def tokenize(text):
    """Lowercase word tokens. snake_case names are kept whole AND split into parts,
    so 'sample_size' matches both 'sample_size' and 'sample size'."""
    tokens = []
    for word in re.findall(r"[A-Za-z0-9_]+", text.lower()):
        tokens.append(word)
        if "_" in word:
            tokens.extend(part for part in word.split("_") if part)
    return tokens


def _results(chunks_with_scores):
    out = []
    for rank, (chunk, score) in enumerate(chunks_with_scores, start=1):
        item = dict(chunk)
        item["score"] = float(score)
        item["rank"] = rank
        out.append(item)
    return out


class LexicalRetriever:
    name = "lexical"

    def __init__(self, chunks):
        from rank_bm25 import BM25Okapi

        self.chunks = chunks
        self.bm25 = BM25Okapi([tokenize(c["search_text"]) for c in chunks])

    def search(self, question, k=5):
        scores = self.bm25.get_scores(tokenize(question))
        order = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:k]
        return _results((self.chunks[i], scores[i]) for i in order)


def get_embeddings():
    """The local embedding model (free, runs on your machine, downloads once)."""
    from langchain_huggingface import HuggingFaceEmbeddings

    return HuggingFaceEmbeddings(
        model_name=EMBED_MODEL, encode_kwargs={"normalize_embeddings": True}
    )


class DenseRetriever:
    name = "dense"

    def __init__(self, chunks, strategy, embeddings=None, persist_dir=None):
        from langchain_chroma import Chroma

        self.chunks = {c["chunk_id"]: c for c in chunks}
        embeddings = embeddings or get_embeddings()
        persist_dir = Path(persist_dir or DEFAULT_CHROMA_DIR)
        persist_dir.mkdir(parents=True, exist_ok=True)

        self.store = Chroma(
            collection_name=f"duckdb_{strategy}",
            embedding_function=embeddings,
            persist_directory=str(persist_dir),
            collection_metadata={"hnsw:space": "cosine"},
        )
        # Rebuild if the stored collection does not match the current chunks.
        stored = set(self.store.get()["ids"])
        if stored != set(self.chunks):
            if stored:
                self.store.delete(ids=list(stored))
            self.store.add_texts(
                texts=[c["search_text"] for c in chunks],
                metadatas=[{"chunk_id": c["chunk_id"]} for c in chunks],
                ids=[c["chunk_id"] for c in chunks],
            )

    def search(self, question, k=5):
        hits = self.store.similarity_search_with_score(question, k=k)
        # Chroma returns cosine distance (0 = identical); turn it into a similarity.
        return _results(
            (self.chunks[doc.metadata["chunk_id"]], 1.0 - distance)
            for doc, distance in hits
        )


def get_retriever(kind, strategy, embeddings=None, persist_dir=None):
    chunks = load_chunks(strategy)
    if kind == "lexical":
        return LexicalRetriever(chunks)
    if kind == "dense":
        return DenseRetriever(chunks, strategy, embeddings, persist_dir)
    raise ValueError(f"kind must be 'lexical' or 'dense', got {kind!r}")
