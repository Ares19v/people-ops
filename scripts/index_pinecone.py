"""Create the Pinecone index (if missing) and upsert the policy corpus.

Usage (from backend/):  python scripts/index_pinecone.py [--query "casual leave quota"]
Requires PINECONE_API_KEY in .env. Safe to re-run: chunk ids are stable, so records are overwritten in place.
"""
import argparse
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "backend"))

from app.core.config import settings
from app.rag.pinecone_retriever import policy_retriever


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--query", help="Run a test search after indexing")
    args = parser.parse_args()

    if not settings.PINECONE_API_KEY:
        print("PINECONE_API_KEY is not set (add it to .env).")
        return 1

    count = policy_retriever.index_corpus()
    print(f"Upserted {count} chunks into '{settings.PINECONE_INDEX}' (namespace 'policies').")

    # Records become searchable a few seconds after upsert.
    for _ in range(20):
        health = policy_retriever.health()
        if health.get("records", 0) >= count:
            break
        time.sleep(3)
    print(health)

    if args.query:
        for p in policy_retriever.search_pinecone(args.query, top_k=3):
            print(f"  {p.score:.3f}  {p.section}  [{p.chunk_id}]")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
