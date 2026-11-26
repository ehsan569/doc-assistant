"""Download the 20 DuckDB documentation pages used as the corpus.

Pinned to one commit of duckdb/duckdb-web so everyone gets identical text.
Run from the repo root:  python scripts/fetch_corpus.py
"""
import json
import urllib.request
from pathlib import Path

REPO = "duckdb/duckdb-web"
COMMIT = "f32864d7570205e0863066c84e84bea87022df64"
VERSION = "2.0"

# 20 pages: some overlap in topic on purpose (CSV x3, Parquet x2, performance x6),
# so retrieval has to pick the right page, not just any page about the topic.
PAGES = [
    "clients/python/overview",
    "clients/python/data_ingestion",
    "configuration/overview",
    "data/csv/overview",
    "data/csv/auto_detection",
    "data/csv/tips",
    "data/json/overview",
    "data/parquet/overview",
    "data/parquet/tips",
    "data/partitioning/hive_partitioning",
    "guides/performance/how_to_tune_workloads",
    "guides/performance/indexing",
    "guides/performance/join_operations",
    "guides/performance/oom",
    "guides/performance/file_formats",
    "guides/performance/import",
    "operations_manual/limits",
    "sql/functions/window_functions",
    "sql/statements/copy",
    "sql/statements/attach",
]

OUT = Path(__file__).resolve().parent.parent / "corpus"


def main() -> None:
    (OUT / "docs").mkdir(parents=True, exist_ok=True)
    manifest = []
    for page in PAGES:
        raw_url = f"https://raw.githubusercontent.com/{REPO}/{COMMIT}/docs/{VERSION}/{page}.md"
        text = urllib.request.urlopen(raw_url, timeout=30).read().decode("utf-8")
        filename = page.replace("/", "__") + ".md"
        (OUT / "docs" / filename).write_text(text, encoding="utf-8")
        manifest.append(
            {
                "file": filename,
                "page": page,
                "raw_url": raw_url,
                # Human-readable page on the DuckDB website, used for clickable source links.
                "web_url": f"https://duckdb.org/docs/stable/{page}",
                "characters": len(text),
            }
        )
        print(f"ok  {page}  ({len(text):,} chars)")
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"\n{len(manifest)} pages written to {OUT}")


if __name__ == "__main__":
    main()
