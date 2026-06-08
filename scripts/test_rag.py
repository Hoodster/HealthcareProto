"""
Verify the RAG knowledge store loads and returns relevant context.

Usage:
    python scripts/test_rag.py
    python scripts/test_rag.py --query "amiodarone QTc prolongation" --top-k 3
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from dotenv import load_dotenv

load_dotenv(_PROJECT_ROOT / ".env")

from api.rag_store import get_rag_status, init_rag_store, retrieve_context

_DEFAULT_QUERIES = [
    "amiodarone QTc prolongation",
    "supraventricular tachycardia treatment",
    "atrial fibrillation catheter ablation",
]


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify RAG retrieval works.")
    parser.add_argument(
        "--query",
        action="append",
        help="Query to test (repeatable). Defaults to a built-in clinical set.",
    )
    parser.add_argument("--top-k", type=int, default=3, help="Chunks to retrieve per query.")
    args = parser.parse_args()

    init_rag_store()
    status = get_rag_status()

    print("RAG status:")
    for key, value in status.items():
        print(f"  {key}: {value}")

    if not status["enabled"]:
        print("\nFAIL: RAG store is not enabled.")
        if not status["knowledge_file_exists"]:
            print("  Hint: run `python scripts/seed_rag_knowledge.py` to build artifacts/rag_knowledge.json")
        else:
            print("  Hint: ensure API_OPENAI is set in .env for query embedding.")
        return 1

    queries = args.query or _DEFAULT_QUERIES
    failures = 0

    print("\nRetrieval checks:")
    for query in queries:
        context = retrieve_context(query, top_k=args.top_k)
        ok = bool(context.strip())
        label = "OK" if ok else "FAIL"
        print(f"  [{label}] {query!r} -> {len(context)} chars")
        if ok:
            preview = context.replace("\n", " ")[:160]
            print(f"        {preview}...")
        else:
            failures += 1

    if failures:
        print(f"\nFAIL: {failures} quer{'y' if failures == 1 else 'ies'} returned empty context.")
        return 1

    print("\nPASS: RAG retrieval is working.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
