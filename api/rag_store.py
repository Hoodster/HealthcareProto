"""
RAG knowledge store — loaded once at application startup.

Usage:
    from api.rag_store import init_rag_store, retrieve_context

    # at startup:
    init_rag_store()

    # at query time:
    context_text = retrieve_context("amiodarone QTc prolongation", top_k=5)
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any, Optional

log = logging.getLogger(__name__)

# Resolve path relative to this file so it works regardless of cwd.
_DEFAULT_JSON = Path(__file__).resolve().parent.parent / "artifacts" / "rag_knowledge.json"

# Module-level singletons — populated by init_rag_store().
_store = None  # InMemoryVectorStore | None
_embedder = None  # OpenAIEmbedder | None


def init_rag_store(json_path: Optional[Path] = None) -> None:
    """
    Load rag_knowledge.json into the in-memory vector store.
    Safe to call multiple times — subsequent calls are no-ops.
    """
    global _store, _embedder

    if _store is not None:
        return  # already initialised

    path = json_path or _DEFAULT_JSON

    if not path.exists():
        log.warning("RAG knowledge file not found at %s — RAG context disabled.", path)
        return

    from retrieved_augmentation.example_usage import InMemoryVectorStore
    from retrieved_augmentation.abstract import DocumentChunk
    from retrieved_augmentation.embedder import OpenAIEmbedder

    try:
        with open(path, encoding="utf-8") as fh:
            raw: list[dict] = json.load(fh)
    except Exception as exc:
        log.error("Failed to load RAG knowledge file: %s", exc)
        return

    chunks: list[DocumentChunk] = []
    for item in raw:
        chunk = DocumentChunk(
            content=item["content"],
            metadata=item.get("metadata", {}),
            chunk_id=item["chunk_id"],
            doc_id=item["doc_id"],
            chunk_index=item["chunk_index"],
            embedding=item.get("embedding"),
        )
        chunks.append(chunk)

    store = InMemoryVectorStore()
    store.add(chunks)

    try:
        embedder = OpenAIEmbedder()
    except RuntimeError as exc:
        log.warning("OpenAI embedder unavailable (%s) — RAG context disabled.", exc)
        return

    _store = store
    _embedder = embedder
    log.info("RAG store loaded: %d chunks from %s", len(chunks), path.name)


def get_rag_status() -> dict[str, Any]:
    """Return current RAG store readiness for health checks and diagnostics."""
    path = _DEFAULT_JSON
    status: dict[str, Any] = {
        "enabled": _store is not None and _embedder is not None,
        "knowledge_file": str(path),
        "knowledge_file_exists": path.exists(),
    }
    if _store is not None:
        status.update(_store.get_stats())
    return status


def retrieve_context(query: str, top_k: int = 5) -> str:
    """
    Embed *query* and return the top-k retrieved chunks as a single string
    suitable for injection into an LLM prompt.

    Returns an empty string when the store is not initialised or on any error.
    """
    if _store is None or _embedder is None:
        return ""

    try:
        query_embedding = _embedder.embed(query)
        results = _store.search(query_embedding, top_k=top_k)
    except Exception as exc:
        log.warning("RAG retrieval failed: %s", exc)
        return ""

    if not results:
        return ""

    parts: list[str] = []
    for i, r in enumerate(results, 1):
        source = r.chunk.metadata.get("filename", r.chunk.doc_id)
        parts.append(f"[{i}] (source: {source})\n{r.chunk.content}")

    return "\n\n".join(parts)
