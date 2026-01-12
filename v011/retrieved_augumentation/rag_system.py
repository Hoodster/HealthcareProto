from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

import numpy as np
import faiss  # type: ignore
from openai import OpenAI  # type: ignore
from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)


@dataclass
class MedicalRagSystemOptions:
    """Static configuration for the Medical RAG pipeline."""

    chunk_file: str = "processed_data/chunks.json"
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    openai_model: str = "gpt-4o-mini"
    top_k: int = 5
    max_generation_tokens: int = 512
    max_context_chars: int = 4000
    system_prompt: str = (
        "You are a cardiology specialist. Base every answer strictly on the supplied "
        "context that comes from atrial fibrillation (AF) guidelines and drug monographs. "
        "Cite section IDs or page numbers when available and call out if the context "
        "does not contain sufficient evidence."
    )
    prompt_template: str = (
        "You are helping clinicians answer questions about atrial fibrillation management.\n"
        "Use ONLY the context snippets below. If an answer is not supported by the context, "
        "say you do not have enough information.\n\n"
        "Context:\n{context}\n\n"
        "Question: {question}\n\n"
        "Answer:"
    )


@dataclass
class MedicalRagSystemParams:
    """Runtime parameters for the Medical RAG System."""

    data_collection: str = "."
    ai_model: Optional[str] = None
    temperature: float = 0.2
    top_k: Optional[int] = None
    api_key: Optional[str] = None


class MedicalRAGSystem:
    """End-to-end Retrieval-Augmented Generation for medical QA."""

    def __init__(
        self,
        data_collection: str = "./data/medical_articles",
        *,
        options: Optional[MedicalRagSystemOptions] = None,
        params: Optional[MedicalRagSystemParams] = None,
    ) -> None:
        self.options = options or MedicalRagSystemOptions()
        self.params = params or MedicalRagSystemParams(data_collection=data_collection)
        if params and params.data_collection != data_collection:
            logger.info(
                "Using data_collection from MedicalRagSystemParams (%s) instead of constructor argument (%s).",
                params.data_collection,
                data_collection,
            )
        self.collection_root = Path(self.params.data_collection).expanduser()
        self._chunk_path = self._resolve_path(self.options.chunk_file)
        self._chunks = self._load_chunks(self._chunk_path)
        self._embedder = SentenceTransformer(self.options.embedding_model)
        self._chunk_embeddings = self._embed_texts([chunk["text"] for chunk in self._chunks])
        self._index = self._build_index(self._chunk_embeddings)
        self._client = self._create_openai_client()
        self._model_name = self.params.ai_model or self.options.openai_model
        logger.info("MedicalRAGSystem ready with %d chunks.", len(self._chunks))

    # ------------------------------------------------------------------
    # Initialization helpers
    # ------------------------------------------------------------------
    def _resolve_path(self, relative: str) -> Path:
        candidate = Path(relative).expanduser()
        search_paths = []
        if candidate.is_absolute():
            search_paths.append(candidate)
        else:
            search_paths.append(self.collection_root / relative)
            search_paths.append(Path.cwd() / relative)
            search_paths.append(candidate)
        for path in search_paths:
            if path.exists():
                return path
        raise FileNotFoundError(
            f"Could not find '{relative}'. Tried relative to '{self.collection_root}' and the working directory."
        )

    def _load_chunks(self, path: Path) -> List[Dict[str, Any]]:
        with path.open("r", encoding="utf-8") as handle:
            raw = json.load(handle)
        if not isinstance(raw, list):
            raise ValueError(f"Chunk store at {path} must be a list.")
        chunks: List[Dict[str, Any]] = []
        for entry in raw:
            text = (entry.get("text") or "").strip()
            if not text:
                continue
            chunks.append(dict(entry))
        if not chunks:
            raise ValueError(f"No valid chunks found in {path}.")
        return chunks

    def _embed_texts(self, texts: Sequence[str]) -> np.ndarray:
        embeddings = self._embedder.encode(
            list(texts),
            convert_to_numpy=True,
            show_progress_bar=len(texts) > 25,
        ).astype("float32")
        faiss.normalize_L2(embeddings)
        return embeddings

    def _build_index(self, embeddings: np.ndarray) -> faiss.IndexFlatIP:
        if embeddings.ndim != 2:
            raise ValueError("Embeddings must be a 2D array.")
        index = faiss.IndexFlatIP(embeddings.shape[1])
        index.add(embeddings)
        return index

    def _create_openai_client(self) -> OpenAI:
        api_key = self.params.api_key or os.getenv("OPENAI_API_KEY") or os.getenv("OPEN_API_KEY")
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY not configured; unable to initialize OpenAI client.")
        return OpenAI(api_key=api_key)

    # ------------------------------------------------------------------
    # Retrieval + generation
    # ------------------------------------------------------------------
    def retrieve(self, query: str, top_k: Optional[int] = None) -> List[Dict[str, Any]]:
        query = query.strip()
        if not query:
            return []
        k = top_k or self.params.top_k or self.options.top_k
        query_vec = self._embed_texts([query])
        scores, indices = self._index.search(query_vec, k)
        retrieved: List[Dict[str, Any]] = []
        for score, idx in zip(scores[0], indices[0]):
            if idx < 0 or idx >= len(self._chunks):
                continue
            chunk = dict(self._chunks[idx])
            chunk["score"] = float(score)
            retrieved.append(chunk)
        return retrieved

    def answer_question(
        self,
        question: str,
        *,
        top_k: Optional[int] = None,
        temperature: Optional[float] = None,
    ) -> Dict[str, Any]:
        contexts = self.retrieve(question, top_k=top_k)
        context_block = self._format_context(contexts)
        prompt = self.options.prompt_template.format(context=context_block, question=question.strip())
        completion = self._client.chat.completions.create(
            model=self._model_name,
            messages=[
                {"role": "system", "content": self.options.system_prompt},
                {"role": "user", "content": prompt},
            ],
            temperature=temperature if temperature is not None else self.params.temperature,
            max_tokens=self.options.max_generation_tokens,
        )
        answer_text = (completion.choices[0].message.content or "").strip()
        return {
            "answer": answer_text,
            "context": contexts,
            "usage": getattr(completion, "usage", None),
        }

    # ------------------------------------------------------------------
    # Utilities
    # ------------------------------------------------------------------
    def _format_context(self, contexts: Sequence[Dict[str, Any]]) -> str:
        if not contexts:
            return "No supporting context was retrieved."
        snippets: List[str] = []
        for idx, chunk in enumerate(contexts, start=1):
            section = chunk.get("section")
            page = chunk.get("page")
            tags = []
            if section:
                tags.append(f"section {section}")
            if page is not None:
                tags.append(f"page {page}")
            header = f"[{idx}] {' | '.join(tags)}" if tags else f"[{idx}]"
            text = " ".join(chunk.get("text", "").split())
            snippets.append(f"{header}\n{text}")
        context_text = "\n\n".join(snippets)
        if self.options.max_context_chars and len(context_text) > self.options.max_context_chars:
            context_text = context_text[: self.options.max_context_chars].rstrip() + "\n...\n[context truncated]"
        return context_text

    def __call__(self, question: str, **kwargs: Any) -> Dict[str, Any]:
        """Shortcut so the instance can be called like a function."""
        return self.answer_question(question, **kwargs)
    
