"""Cut cleaned pages into chunks, in two different ways.

Strategy "fixed":    cut every ~1000 characters, ignoring the page structure.
Strategy "headings": cut at markdown headings first, then split any long section.
                     Each chunk also gets a breadcrumb ("Page title > Section")
                     added to the text that is *searched* (not the text that is shown).

Every chunk is a dict:
    chunk_id     "<file>#<n>", unique, used for citations
    text         the passage shown to the reader and sent to the LLM
    search_text  the text that gets indexed (same as text for "fixed")
    title        page title
    file         source file name in corpus/docs
    web_url      link to the page on duckdb.org
    heading      section heading path ("" for the fixed strategy)
    strategy     "fixed" or "headings"
"""
import json
import re
from pathlib import Path

from langchain_text_splitters import (
    MarkdownHeaderTextSplitter,
    RecursiveCharacterTextSplitter,
)

from .loader import load_page

ROOT = Path(__file__).resolve().parents[2]
CORPUS_DIR = ROOT / "corpus"
DOCS_DIR = CORPUS_DIR / "docs"

STRATEGIES = ("fixed", "headings")


def load_web_urls():
    """Map file name -> page URL, from corpus/manifest.json."""
    manifest = json.loads((CORPUS_DIR / "manifest.json").read_text(encoding="utf-8"))
    return {entry["file"]: entry["web_url"] for entry in manifest}


def _chunk(page, number, text, search_text, web_url, heading, strategy):
    return {
        "chunk_id": f"{page['file']}#{number}",
        "text": text,
        "search_text": search_text,
        "title": page["title"],
        "file": page["file"],
        "web_url": web_url,
        "heading": heading,
        "strategy": strategy,
    }


def chunk_page_fixed(page, chunk_size=1000, chunk_overlap=150, web_url=None):
    """Strategy A: fixed-size pieces with overlap."""
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size, chunk_overlap=chunk_overlap
    )
    pieces = splitter.split_text(page["text"])
    return [
        _chunk(page, i, piece, piece, web_url, "", "fixed")
        for i, piece in enumerate(pieces)
    ]


def chunk_page_headings(page, max_size=1000, chunk_overlap=150, web_url=None):
    """Strategy B: split at headings, then cap the size of long sections."""
    header_splitter = MarkdownHeaderTextSplitter(
        headers_to_split_on=[("#", "h1"), ("##", "h2"), ("###", "h3")],
        strip_headers=False,
    )
    size_splitter = RecursiveCharacterTextSplitter(
        chunk_size=max_size, chunk_overlap=chunk_overlap
    )
    sections = header_splitter.split_text(page["text"])

    chunks = []
    number = 0
    for section in sections:
        heading_parts = [
            section.metadata[key]
            for key in ("h1", "h2", "h3")
            if key in section.metadata
        ]
        heading = " > ".join(heading_parts)
        breadcrumb = page["title"] + (" > " + heading if heading else "")
        # The header splitter joins lines with two spaces + newline; tidy that up.
        content = re.sub(r" +\n", "\n", section.page_content)
        for piece in size_splitter.split_text(content):
            search_text = breadcrumb + "\n\n" + piece
            chunks.append(_chunk(page, number, piece, search_text, web_url, heading, "headings"))
            number += 1
    return chunks


def load_chunks(strategy="fixed", **kwargs):
    """Chunk all 20 pages with one strategy."""
    if strategy not in STRATEGIES:
        raise ValueError(f"strategy must be one of {STRATEGIES}, got {strategy!r}")
    chunker = chunk_page_fixed if strategy == "fixed" else chunk_page_headings
    web_urls = load_web_urls()
    chunks = []
    for path in sorted(DOCS_DIR.glob("*.md")):
        page = load_page(path)
        chunks.extend(chunker(page, web_url=web_urls.get(page["file"]), **kwargs))
    return chunks


def chunk_stats(chunks):
    """Count and size summary, for the README and the dashboard."""
    sizes = [len(c["text"]) for c in chunks]
    return {
        "chunks": len(chunks),
        "min_chars": min(sizes),
        "mean_chars": round(sum(sizes) / len(sizes), 1),
        "max_chars": max(sizes),
        "under_200_chars": sum(1 for s in sizes if s < 200),
    }


if __name__ == "__main__":
    for name in STRATEGIES:
        print(name, chunk_stats(load_chunks(name)))
