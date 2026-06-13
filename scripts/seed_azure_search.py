#!/usr/bin/env python3
"""Seed Azure AI Search index from artifacts/rag_knowledge.json (BYO vectors).

Usage:
    export RAG_BACKEND=azure_search
    export AZURE_SEARCH_ENDPOINT=https://....search.windows.net
    export AZURE_SEARCH_KEY=...
    export AZURE_SEARCH_INDEX=healthcare-rag
    python scripts/seed_azure_search.py
"""

from __future__ import annotations

import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from dotenv import load_dotenv

load_dotenv(_PROJECT_ROOT / ".env")


def main() -> int:
    from api.rag_search_store import init_rag_store, seed_guidelines_from_json

    init_rag_store()
    n = seed_guidelines_from_json()
    print(f"Seeded {n} guideline chunks to Azure AI Search.")
    return 0 if n >= 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
