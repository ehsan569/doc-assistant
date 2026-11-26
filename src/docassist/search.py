"""Command-line search. No LLM involved: this shows what retrieval finds.

    python -m src.docassist.search "how do I read a csv with a different delimiter?"
    python -m src.docassist.search "what is hive partitioning" --strategy headings --retriever dense -k 3
"""
import argparse

from .retrieve import get_retriever


def main():
    parser = argparse.ArgumentParser(description="Search the DuckDB docs.")
    parser.add_argument("question")
    parser.add_argument("--strategy", choices=["fixed", "headings"], default="headings")
    parser.add_argument("--retriever", choices=["lexical", "dense"], default="dense")
    parser.add_argument("-k", type=int, default=5)
    args = parser.parse_args()

    retriever = get_retriever(args.retriever, args.strategy)
    for hit in retriever.search(args.question, k=args.k):
        print(f"\n#{hit['rank']}  score={hit['score']:.3f}  {hit['chunk_id']}")
        print(f"    {hit['title']}  |  {hit['heading'] or '(no heading)'}")
        print(f"    {hit['web_url']}")
        preview = " ".join(hit["text"].split())[:300]
        print(f"    {preview}...")


if __name__ == "__main__":
    main()
