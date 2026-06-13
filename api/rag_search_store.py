"""Azure AI Search backend for RAG (BYO vectors)."""

from __future__ import annotations

import json
import logging
import os
import re
from pathlib import Path
from typing import Any, Optional

from sqlalchemy.orm import Session

log = logging.getLogger(__name__)

_DEFAULT_JSON = Path(__file__).resolve().parent.parent / "artifacts" / "rag_knowledge.json"
_MIN_SCORE = 0.22
_INDEX_NAME = os.getenv("AZURE_SEARCH_INDEX", "healthcare-rag")
_initialized = False
_client = None
_embedder = None


def _endpoint() -> str:
    return os.getenv("AZURE_SEARCH_ENDPOINT", "").rstrip("/")


def _api_key() -> str:
    return os.getenv("AZURE_SEARCH_KEY", "")


def _get_client():
    global _client
    if _client is not None:
        return _client
    from azure.core.credentials import AzureKeyCredential
    from azure.search.documents import SearchClient

    endpoint = _endpoint()
    key = _api_key()
    if not endpoint or not key:
        raise RuntimeError("AZURE_SEARCH_ENDPOINT and AZURE_SEARCH_KEY required for RAG_BACKEND=azure_search")
    _client = SearchClient(endpoint, _INDEX_NAME, AzureKeyCredential(key))
    return _client


def _get_index_client():
    from azure.core.credentials import AzureKeyCredential
    from azure.search.documents.indexes import SearchIndexClient
    from azure.search.documents.indexes.models import (
        HnswAlgorithmConfiguration,
        HnswParameters,
        SearchField,
        SearchFieldDataType,
        SearchIndex,
        SimpleField,
        VectorSearch,
        VectorSearchAlgorithmKind,
        VectorSearchProfile,
    )

    endpoint = _endpoint()
    key = _api_key()
    index_client = SearchIndexClient(endpoint, AzureKeyCredential(key))

    fields = [
        SimpleField(name="id", type=SearchFieldDataType.String, key=True),
        SearchField(name="content", type=SearchFieldDataType.String, searchable=True),
        SearchField(
            name="contentVector",
            type=SearchFieldDataType.Collection(SearchFieldDataType.Single),
            searchable=True,
            vector_search_dimensions=1536,
            vector_search_profile_name="default",
        ),
        SimpleField(name="doc_type", type=SearchFieldDataType.String, filterable=True, facetable=True),
        SimpleField(name="filename", type=SearchFieldDataType.String, filterable=True),
        SimpleField(name="patient_id", type=SearchFieldDataType.String, filterable=True),
        SimpleField(name="chunk_id", type=SearchFieldDataType.String),
        SimpleField(name="doc_id", type=SearchFieldDataType.String, filterable=True),
    ]
    vector_search = VectorSearch(
        algorithms=[
            HnswAlgorithmConfiguration(
                name="hnsw",
                kind=VectorSearchAlgorithmKind.HNSW,
                parameters=HnswParameters(metric="cosine"),
            )
        ],
        profiles=[VectorSearchProfile(name="default", algorithm_configuration_name="hnsw")],
    )
    index = SearchIndex(name=_INDEX_NAME, fields=fields, vector_search=vector_search)
    index_client.create_or_update_index(index)
    return index_client


def init_rag_store(json_path: Optional[Path] = None) -> None:
    """Ensure Search index exists and embedder is ready. Guidelines seeded separately."""
    global _initialized, _embedder

    if _initialized:
        return

    from retrieved_augmentation.embedder import OpenAIEmbedder

    try:
        _get_index_client()
        _embedder = OpenAIEmbedder()
        _initialized = True
        log.info("Azure AI Search RAG backend ready (index=%s)", _INDEX_NAME)
    except Exception as exc:
        log.error("Azure Search init failed: %s", exc)
        raise


def seed_guidelines_from_json(json_path: Optional[Path] = None) -> int:
    """Upload pre-embedded guideline chunks from rag_knowledge.json."""
    path = json_path or _DEFAULT_JSON
    if not path.exists():
        log.warning("Guideline JSON not found: %s", path)
        return 0

    init_rag_store()
    client = _get_client()

    with open(path, encoding="utf-8") as fh:
        raw: list[dict] = json.load(fh)

    docs = []
    for item in raw:
        emb = item.get("embedding")
        if not emb:
            continue
        meta = item.get("metadata", {})
        chunk_id = item["chunk_id"]
        docs.append(
            {
                "id": chunk_id,
                "content": item["content"],
                "contentVector": emb,
                "doc_type": "guideline",
                "filename": meta.get("filename", meta.get("source", "guideline")),
                "patient_id": "",
                "chunk_id": chunk_id,
                "doc_id": item.get("doc_id", chunk_id),
            }
        )

    if not docs:
        return 0

    batch_size = 500
    for i in range(0, len(docs), batch_size):
        client.merge_or_upload_documents(docs[i : i + batch_size])
    log.info("Seeded %d guideline chunks to Azure Search", len(docs))
    return len(docs)


def sync_patient_documents(db: Session) -> dict[str, int]:
    """Index patient documents from DB into Azure Search."""
    from api.models import MedDocument
    from sqlalchemy import select

    if not _initialized:
        init_rag_store()

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
        if doc.content_text and doc.content_text.strip():
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
    if not _initialized:
        init_rag_store()

    from retrieved_augmentation.abstract import ChunkingStrategy
    from retrieved_augmentation.document_processor import HealthcareDocumentProcessor

    processor = HealthcareDocumentProcessor(default_chunk_size=500, default_overlap=50)
    cleaned = processor.clean(text)
    if not cleaned.strip():
        return 0

    chunks = processor.chunk(
        cleaned,
        strategy=ChunkingStrategy.SLIDING_WINDOW,
        chunk_size=500,
        overlap=50,
    )
    if not chunks:
        return 0

    doc_uuid = f"patient_{patient_id}_doc_{med_doc_id}"
    if _embedder is None:
        raise RuntimeError("Embedder not initialized")
    embeddings = _embedder.embed_batch(chunks)
    client = _get_client()
    docs = []
    for idx, (chunk_text, emb) in enumerate(zip(chunks, embeddings)):
        chunk_id = f"{doc_uuid}_chunk_{idx}"
        docs.append(
            {
                "id": chunk_id,
                "content": chunk_text,
                "contentVector": emb,
                "doc_type": "patient_docfile",
                "filename": filename,
                "patient_id": patient_id,
                "chunk_id": chunk_id,
                "doc_id": doc_uuid,
            }
        )

    client.merge_or_upload_documents(docs)
    return len(docs)


def remove_patient_document(med_doc_id: int, patient_id: str) -> None:
    if not _initialized:
        return
    client = _get_client()
    doc_uuid = f"patient_{patient_id}_doc_{med_doc_id}"
    # Best-effort delete by doc_id filter — chunk count unknown; skip if expensive
    try:
        results = client.search("", filter=f"doc_id eq '{doc_uuid}'", select=["id"], top=500)
        ids = [{"id": r["id"]} for r in results]
        if ids:
            client.delete_documents(ids)
    except Exception as exc:
        log.warning("Failed to remove patient doc from Search: %s", exc)


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


def _rerank(query: str, hits: list[dict]) -> list[dict]:
    query_terms = set(re.findall(r"[a-z0-9]+", query.lower()))
    if not query_terms:
        return hits
    for hit in hits:
        chunk_terms = set(re.findall(r"[a-z0-9]+", hit.get("content", "").lower()))
        overlap = len(query_terms & chunk_terms) / len(query_terms)
        hit["score"] = hit.get("score", 0) * 0.65 + overlap * 0.35
    hits.sort(key=lambda x: x.get("score", 0), reverse=True)
    return hits


def retrieve_context_with_sources(
    query: str,
    top_k: int = 6,
    *,
    patient_id: str | None = None,
    min_score: float = _MIN_SCORE,
) -> tuple[str, list[dict[str, Any]]]:
    if not _initialized:
        init_rag_store()

    query_embedding = _embedder and _embedder.embed(query) or []
    client = _get_client()

    from azure.search.documents.models import VectorizedQuery

    guideline_k = max(2, top_k // 2)
    patient_k = max(2, top_k - guideline_k)

    def _vector_search(filter_expr: str, k: int) -> list[dict]:
        vq = VectorizedQuery(
            vector=query_embedding,
            k_nearest_neighbors=k * 3,
            fields="contentVector",
        )
        results = client.search(
            search_text=None,
            vector_queries=[vq],
            filter=filter_expr,
            select=["content", "filename", "doc_type", "chunk_id"],
        )
        hits: list[dict] = []
        for r in results:
            row = dict(r)
            row["score"] = float(row.pop("@search.score", 0.0))
            hits.append(row)
        return hits

    guideline_hits = _rerank(query, _vector_search("doc_type eq 'guideline'", guideline_k))
    guideline_hits = [h for h in guideline_hits if h.get("score", 0) >= min_score][:guideline_k]

    patient_hits: list[dict] = []
    if patient_id:
        patient_hits = _rerank(
            query,
            _vector_search(f"doc_type eq 'patient_docfile' and patient_id eq '{patient_id}'", patient_k),
        )
        patient_hits = [h for h in patient_hits if h.get("score", 0) >= min_score][:patient_k]

    sections: list[str] = []
    sources: list[dict] = []

    def _append(hits: list[dict], title: str) -> None:
        if not hits:
            return
        parts = [f"=== {title} ==="]
        for i, h in enumerate(hits, 1):
            fn = h.get("filename", "?")
            score = h.get("score", 0)
            parts.append(f"[{i}] (source: {fn}, score: {score:.2f})\n{h.get('content', '')}")
            sources.append(
                {
                    "filename": fn,
                    "doc_type": h.get("doc_type", "guideline"),
                    "score": round(float(score), 3),
                    "chunk_id": h.get("chunk_id", ""),
                }
            )
        sections.append("\n\n".join(parts))

    _append(guideline_hits, "CLINICAL GUIDELINES")
    _append(patient_hits, "PATIENT DOCUMENTS")
    return "\n\n".join(sections), sources


def retrieve_context(
    query: str,
    top_k: int = 6,
    *,
    patient_id: str | None = None,
    min_score: float = _MIN_SCORE,
) -> str:
    text, _ = retrieve_context_with_sources(
        query, top_k, patient_id=patient_id, min_score=min_score
    )
    return text


def get_rag_status() -> dict[str, Any]:
    return {
        "enabled": _initialized,
        "backend": "azure_search",
        "index": _INDEX_NAME,
        "endpoint": _endpoint() or None,
    }
