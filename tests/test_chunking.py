import re
from pathlib import Path

import pytest

from src.docassist.chunking import STRATEGIES, chunk_stats, load_chunks
from src.docassist.loader import load_page

PAGES = {p.name: load_page(p) for p in sorted(Path("corpus/docs").glob("*.md"))}


def squash(text):
    return re.sub(r"\s+", " ", text).strip()


@pytest.mark.parametrize("strategy", STRATEGIES)
def test_every_page_gets_chunks(strategy):
    chunks = load_chunks(strategy)
    assert {c["file"] for c in chunks} == set(PAGES)


@pytest.mark.parametrize("strategy", STRATEGIES)
def test_chunk_ids_are_unique_and_labelled(strategy):
    chunks = load_chunks(strategy)
    ids = [c["chunk_id"] for c in chunks]
    assert len(ids) == len(set(ids))
    for c in chunks:
        assert c["chunk_id"].startswith(c["file"] + "#")
        assert c["text"].strip()
        assert c["title"]
        assert c["web_url"].startswith("https://duckdb.org/")
        assert c["strategy"] == strategy


@pytest.mark.parametrize("strategy", STRATEGIES)
def test_chunks_respect_size_limit(strategy):
    assert max(len(c["text"]) for c in load_chunks(strategy)) <= 1000


@pytest.mark.parametrize("strategy", STRATEGIES)
def test_chunk_text_comes_from_its_page(strategy):
    for c in load_chunks(strategy):
        assert squash(c["text"]) in squash(PAGES[c["file"]]["text"]), c["chunk_id"]


@pytest.mark.parametrize("strategy", STRATEGIES)
def test_end_of_every_page_is_covered(strategy):
    chunks = load_chunks(strategy)
    for name, page in PAGES.items():
        tail = squash(page["text"])[-40:]
        assert any(tail in squash(c["text"]) for c in chunks if c["file"] == name), name


def test_headings_strategy_records_headings_and_breadcrumbs():
    chunks = load_chunks("headings")
    with_heading = [c for c in chunks if c["heading"]]
    assert len(with_heading) > len(chunks) / 2
    for c in with_heading[:50]:
        assert c["search_text"].startswith(c["title"] + " > " + c["heading"])


def test_fixed_strategy_searches_the_same_text_it_shows():
    for c in load_chunks("fixed"):
        assert c["search_text"] == c["text"]


def test_stats_shape():
    stats = chunk_stats(load_chunks("fixed"))
    assert set(stats) == {"chunks", "min_chars", "mean_chars", "max_chars", "under_200_chars"}
