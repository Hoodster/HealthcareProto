"""Basic embedding service using sentence-transformers with simple PDF/TXT/MD extraction.

Provides both document-level and chunk-level embeddings.
"""

from typing import List, Sequence
from pathlib import Path
from pdfminer.high_level import extract_text as pdf_extract_text
from sentence_transformers import SentenceTransformer

from v010.abstraction.embedding_service import EmbeddingService
from v010.utils.embedding.chunker import chunk_text


class BasicEmbeddingService(EmbeddingService):
    def __init__(self, model_name: str = "sentence-transformers/all-MiniLM-L6-v2", **kwargs):
        super().__init__(model_name, **kwargs)
        self._model = SentenceTransformer(model_name)

    # ---------- File extraction ----------
    def extract_text(self, path: str) -> str:
        ext = Path(path).suffix.lower().replace(".", "")
        if ext == "pdf":
            return pdf_extract_text(path) or ""
        elif ext in {"txt", "md"}:
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                return f.read()
        else:
            # Should be prevented by validator in base, keep defensive fallback
            raise ValueError(f"Unsupported extension for extraction: {ext}")

    # ---------- Embedding primitives ----------
    def embed_texts(self, texts: Sequence[str]) -> List[List[float]]:
        if not texts:
            return []
        embeddings = self._model.encode(list(texts), convert_to_numpy=True, normalize_embeddings=True)
        return [emb.tolist() for emb in embeddings]

    # ---------- Higher-level helpers ----------
    def embed_file_chunks(self, path: str, chunk_size: int = 800, overlap: int = 100) -> List[dict]:
        text = self.extract_text(path)
        chunks = chunk_text(text, chunk_size=chunk_size, overlap=overlap)
        enriched = []
        vectors = self.embed_texts([c["chunk"] for c in chunks])
        for c, v in zip(chunks, vectors):
            enriched.append({"source": path, **c, "embedding": v})
        return enriched


