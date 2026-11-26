from langchain_core.embeddings import DeterministicFakeEmbedding

from src.docassist.chunking import load_chunks
from src.docassist.retrieve import DenseRetriever, LexicalRetriever, tokenize


def test_tokenize_keeps_and_splits_snake_case():
    tokens = tokenize("Set sample_size to -1")
    assert "sample_size" in tokens
    assert "sample" in tokens and "size" in tokens


def test_lexical_finds_exact_option_name():
    retriever = LexicalRetriever(load_chunks("fixed"))
    top = retriever.search("what does union_by_name do", k=3)
    assert len(top) == 3
    assert [r["rank"] for r in top] == [1, 2, 3]
    assert "union_by_name" in top[0]["text"]
    assert top[0]["score"] >= top[1]["score"] >= top[2]["score"]


def test_lexical_results_carry_source_labels():
    hit = LexicalRetriever(load_chunks("headings")).search("hive partitioning", k=1)[0]
    for key in ("chunk_id", "text", "title", "file", "web_url", "score", "rank"):
        assert key in hit


def test_dense_plumbing_with_fake_embeddings(tmp_path):
    # Fake embeddings carry no meaning. This only proves the Chroma code works:
    # building, searching, ranking, and not duplicating on a second start.
    chunks = load_chunks("headings")
    fake = DeterministicFakeEmbedding(size=32)

    retriever = DenseRetriever(chunks, "headings", embeddings=fake, persist_dir=tmp_path)
    hits = retriever.search("anything", k=4)
    assert len(hits) == 4
    assert [h["rank"] for h in hits] == [1, 2, 3, 4]
    assert all(h["chunk_id"] in retriever.chunks for h in hits)

    again = DenseRetriever(chunks, "headings", embeddings=fake, persist_dir=tmp_path)
    assert len(again.store.get()["ids"]) == len(chunks)


def test_dense_exact_text_is_nearest_to_itself(tmp_path):
    chunks = load_chunks("fixed")
    fake = DeterministicFakeEmbedding(size=32)
    retriever = DenseRetriever(chunks, "fixed", embeddings=fake, persist_dir=tmp_path)
    target = chunks[10]
    top = retriever.search(target["search_text"], k=1)[0]
    assert top["chunk_id"] == target["chunk_id"]
