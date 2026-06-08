"""
RAG knowledge store — guidelines + per-patient document chunks.

Guidelines load from artifacts/rag_knowledge.json at startup.
Patient documents are indexed from app.med_documents (sync on startup + on upload).
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

log = logging.getLogger(__name__)

_DEFAULT_JSON = Path(__file__).resolve().parent.parent / "artifacts" / "rag_knowledge.json"
_MIN_SCORE = 0.22

_store = None  # InMemoryVectorStore | None
_embedder = None  # OpenAIEmbedder | None
_patient_docs_indexed: set[int] = set()


def init_rag_store(json_path: Optional[Path] = None) -> None:
    """Load guideline chunks into the in-memory vector store."""
    global _store, _embedder

    if _store is not None:
        return

    from retrieved_augmentation.example_usage import InMemoryVectorStore
    from retrieved_augmentation.abstract import DocumentChunk
    from retrieved_augmentation.embedder import OpenAIEmbedder

    path = json_path or _DEFAULT_JSON
    store = InMemoryVectorStore()

    if path.exists():
        try:
            with open(path, encoding="utf-8") as fh:
                raw: list[dict] = json.load(fh)
            chunks: list[DocumentChunk] = []
            for item in raw:
                metadata = {**item.get("metadata", {}), "doc_type": "guideline"}
                chunks.append(
                    DocumentChunk(
                        content=item["content"],
                        metadata=metadata,
                        chunk_id=item["chunk_id"],
                        doc_id=item["doc_id"],
                        chunk_index=item["chunk_index"],
                        embedding=item.get("embedding"),
                    )
                )
            store.add(chunks)
            log.info("RAG guidelines loaded: %d chunks from %s", len(chunks), path.name)
        except Exception as exc:
            log.error("Failed to load RAG knowledge file: %s", exc)
    else:
        log.warning("RAG knowledge file not found at %s — guideline RAG disabled.", path)

    try:
        embedder = OpenAIEmbedder()
    except RuntimeError as exc:
        log.warning("OpenAI embedder unavailable (%s) — RAG disabled.", exc)
        return

    _store = store
    _embedder = embedder


def sync_patient_documents(db: Session) -> dict[str, int]:
    """Index all patient_docfile rows from the database into the RAG store."""
    from api.models import MedDocument

    if _store is None or _embedder is None:
        return {"documents": 0, "chunks": 0}

    stmt = (
        select(MedDocument)
        .where(
            MedDocument.document_type == "patient_docfile",
            MedDocument.content_text.isnot(None),
        )
        .order_by(MedDocument.created_at.asc())
    )
    docs = list(db.execute(stmt).scalars().all())
    total_chunks = 0
    for doc in docs:
        if not doc.content_text or not doc.content_text.strip():
            continue
        total_chunks += index_patient_document(
            doc.content_text,
            patient_id=doc.patient_id,
            med_doc_id=doc.id,
            filename=doc.filename,
        )
    return {"documents": len(docs), "chunks": total_chunks}


def index_patient_document(
    text: str,
    *,
    patient_id: str,
    med_doc_id: int,
    filename: str,
) -> int:
    """Chunk, embed, and index a patient document. Returns number of chunks indexed."""
    global _patient_docs_indexed

    if _store is None or _embedder is None:
        log.warning("RAG store not ready — skipping index for doc %s", med_doc_id)
        return 0

    from uuid import uuid4
    from retrieved_augmentation.abstract import DocumentChunk, ChunkingStrategy
    from retrieved_augmentation.document_processor import HealthcareDocumentProcessor

    doc_uuid = f"patient_{patient_id}_doc_{med_doc_id}"
    _store.delete(doc_uuid)

    processor = HealthcareDocumentProcessor(default_chunk_size=500, default_overlap=50)
    cleaned = processor.clean(text)
    if not cleaned.strip():
        return 0

    text_chunks = processor.chunk(
        cleaned,
        strategy=ChunkingStrategy.SLIDING_WINDOW,
        chunk_size=500,
        overlap=50,
    )
    if not text_chunks:
        return 0

    chunks: list[DocumentChunk] = []
    for idx, chunk_text in enumerate(text_chunks):
        chunks.append(
            DocumentChunk(
                content=chunk_text,
                metadata={
                    "doc_type": "patient_docfile",
                    "patient_id": patient_id,
                    "med_doc_id": med_doc_id,
                    "filename": filename,
                },
                chunk_id=f"{doc_uuid}_chunk_{idx}",
                doc_id=doc_uuid,
                chunk_index=idx,
            )
        )

    embeddings = _embedder.embed_batch([c.content for c in chunks])
    for chunk, emb in zip(chunks, embeddings):
        chunk.embedding = emb

    _store.add(chunks)
    _patient_docs_indexed.add(med_doc_id)
    log.info(
        "Indexed patient document %s (%s): %d chunks for patient %s",
        med_doc_id,
        filename,
        len(chunks),
        patient_id,
    )
    return len(chunks)


def remove_patient_document(med_doc_id: int, patient_id: str) -> None:
    if _store is None:
        return
    doc_uuid = f"patient_{patient_id}_doc_{med_doc_id}"
    _store.delete(doc_uuid)
    _patient_docs_indexed.discard(med_doc_id)


def build_rag_query(user_message: str, patient_context: Any | None = None) -> str:
    """Enrich the retrieval query with patient clinical context when available."""
    parts = [user_message.strip()]
    if patient_context is None:
        return parts[0]

    if getattr(patient_context, "medications", None):
        parts.append("Medications: " + ", ".join(patient_context.medications))
    if getattr(patient_context, "conditions", None):
        parts.append("Conditions: " + ", ".join(patient_context.conditions))
    parts.append(f"eGFR {patient_context.egfr} mL/min/1.73m²")
    return "\n".join(parts)


def _rerank(query: str, results: list) -> list:
    from retrieved_augmentation.abstract import RetrievalResult

    if not results:
        return results

    query_terms = set(re.findall(r"[a-z0-9]+", query.lower()))
    if not query_terms:
        return results

    reranked: list[RetrievalResult] = []
    for result in results:
        chunk_terms = set(re.findall(r"[a-z0-9]+", result.chunk.content.lower()))
        overlap = len(query_terms & chunk_terms) / len(query_terms)
        result.score = result.score * 0.65 + overlap * 0.35
        reranked.append(result)

    reranked.sort(key=lambda x: x.score, reverse=True)
    for i, result in enumerate(reranked):
        result.rank = i + 1
    return reranked


def _format_results(results: list, section_title: str) -> str:
    if not results:
        return ""
    parts = [f"=== {section_title} ==="]
    for i, r in enumerate(results, 1):
        source = r.chunk.metadata.get("filename", r.chunk.doc_id)
        parts.append(f"[{i}] (source: {source}, score: {r.score:.2f})\n{r.chunk.content}")
    return "\n\n".join(parts)


def retrieve_context(
    query: str,
    top_k: int = 6,
    *,
    patient_id: str | None = None,
    min_score: float = _MIN_SCORE,
) -> str:
    """
    Retrieve guideline + optional patient-document context for an LLM prompt.

    Splits budget between clinical guidelines and patient-specific documents.
    """
    if _store is None or _embedder is None:
        return ""

    try:
        query_embedding = _embedder.embed(query)
    except Exception as exc:
        log.warning("RAG query embedding failed: %s", exc)
        return ""

    guideline_k = max(2, top_k // 2)
    patient_k = max(2, top_k - guideline_k)

    try:
        guideline_hits = _store.search(
            query_embedding,
            top_k=guideline_k * 3,
            filters={"doc_type": "guideline"},
        )
        patient_hits: list = []
        if patient_id:
            patient_hits = _store.search(
                query_embedding,
                top_k=patient_k * 3,
                filters={"doc_type": "patient_docfile", "patient_id": patient_id},
            )
    except Exception as exc:
        log.warning("RAG retrieval failed: %s", exc)
        return ""

    guideline_results = [
        r for r in _rerank(query, guideline_hits)
        if r.score >= min_score
    ][:guideline_k]
    patient_results = [
        r for r in _rerank(query, patient_hits)
        if r.score >= min_score
    ][:patient_k] if patient_id else []

    if not guideline_results and not patient_results:
        return ""

    sections: list[str] = []
    g_text = _format_results(guideline_results[:guideline_k], "CLINICAL GUIDELINES")
    p_text = _format_results(patient_results[:patient_k], "PATIENT DOCUMENTS")
    if g_text:
        sections.append(g_text)
    if p_text:
        sections.append(p_text)
    return "\n\n".join(sections)


def get_rag_status() -> dict[str, Any]:
    path = _DEFAULT_JSON
    status: dict[str, Any] = {
        "enabled": _store is not None and _embedder is not None,
        "knowledge_file": str(path),
        "knowledge_file_exists": path.exists(),
        "patient_documents_indexed": len(_patient_docs_indexed),
    }
    if _store is not None:
        stats = _store.get_stats()
        status.update(stats)
        chunks = _store.chunks.values()
        status["guideline_chunks"] = sum(
            1 for c in chunks if c.metadata.get("doc_type") == "guideline"
        )
        status["patient_chunks"] = sum(
            1 for c in chunks if c.metadata.get("doc_type") == "patient_docfile"
        )
    return status
