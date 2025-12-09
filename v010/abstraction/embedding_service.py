"""Base abstractions for embedding services used in RAG pipeline.

Responsibilities:
 - Validate supported file extensions
 - Extract raw text from supported files
 - Convert text (or chunks) into embedding vectors
 - Provide higher-level convenience for embedding from file paths

Concrete implementations should:
 - Implement `embed_texts`
 - Implement `extract_text`
 - Optionally implement batching / caching
"""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Iterable, List, Dict, Sequence

SUPPORTED_EXTENSIONS = {"txt", "pdf", "md"}  # extend when docx/xlsx/pptx parsers are added


class EmbeddingService(ABC):
    def __init__(self, model_name: str, **kwargs):
        self._model_name = model_name

    # -------- Extension / validation helpers ---------
    @staticmethod
    def _verify_extension(file_extension: str) -> None:
        if file_extension.lower() not in SUPPORTED_EXTENSIONS:
            raise ValueError(
                f"Unsupported file extension: {file_extension}. Supported: {', '.join(sorted(SUPPORTED_EXTENSIONS))}"
            )

    # -------- Low-level extraction ---------
    @abstractmethod
    def extract_text(self, path: str) -> str:
        """Return raw textual content from a file path (single document)."""
        raise NotImplementedError

    # -------- Embedding primitives ---------
    @abstractmethod
    def embed_texts(self, texts: Sequence[str]) -> List[List[float]]:
        """Embed a batch of texts returning list of embedding vectors (floats)."""
        raise NotImplementedError

    # -------- High-level convenience ---------
    def embed_from_files(self, file_paths: Iterable[str]) -> List[Dict]:
        """Embed full documents (with naive chunking fallback) and return metadata dicts.

        Output schema per item:
        {"source": <path>, "text": <full_text>, "embedding": <vector>}
        """
        paths = list(file_paths)
        if not paths:
            return []

        texts: List[str] = []
        for p in paths:
            ext = Path(p).suffix.replace(".", "").lower()
            self._verify_extension(ext)
            texts.append(self.extract_text(p))

        vectors = self.embed_texts(texts)
        results: List[Dict] = []
        for path, text, vec in zip(paths, texts, vectors):
            results.append({"source": path, "text": text, "embedding": vec})
        return results

    # Optional override point for chunk-level embedding if needed later
    def embed_chunks(self, chunks: Sequence[Dict]) -> List[Dict]:
        """Embed list of chunk dicts {source, chunk, id} -> returns with 'embedding'."""
        texts = [c["chunk"] for c in chunks]
        vectors = self.embed_texts(texts)
        enriched = []
        for c, v in zip(chunks, vectors):
            e = dict(c)
            e["embedding"] = v
            enriched.append(e)
        return enriched

    # -------- Default chunking path (can be overridden) ---------
    def embed_file_chunks(self, path: str, chunk_size: int = 800, overlap: int = 100) -> List[dict]:
        from v010.utils.embedding.chunker import chunk_text

        text = self.extract_text(path)
        chunks = chunk_text(text, chunk_size=chunk_size, overlap=overlap)
        return self.embed_chunks([{**c, "source": path} for c in chunks])
