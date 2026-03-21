from typing import List, Dict
import numpy as np
import faiss

from v010.abstraction.retriever_service import RetrieverService
from sentence_transformers import SentenceTransformer


class BasicRetrieverService(RetrieverService):
    """FAISS flat L2 index over normalized sentence-transformer embeddings."""

    def __init__(self, model_name: str = "sentence-transformers/all-MiniLM-L6-v2", api_key: str | None = None, **kwargs):
        super().__init__(model_name, api_key or "", **kwargs)
        self._embedder = SentenceTransformer(model_name)
        self._dim = self._embedder.get_sentence_embedding_dimension()
        # Use IndexFlatIP (cosine via normalized embeddings)
        self._index = faiss.IndexFlatIP(self._dim)
        self._items: List[Dict] = []  # parallel array to map ids -> payloads

    def _ensure_normalized(self, vecs: np.ndarray) -> np.ndarray:
        norms = np.linalg.norm(vecs, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        return vecs / norms

    def add(self, items: List[Dict]):
        if not items:
            return
        # Expect items with 'embedding' (list[float])
        vecs = np.array([np.array(it["embedding"], dtype=np.float32) for it in items], dtype=np.float32)
        n, x = self._ensure_normalized(vecs)
        # FAISS expects shape (n, dim)
        self._index.add(n, x)
        self._items.extend(items)

    def _embed_query(self, query: str) -> np.ndarray:
        q = self._embedder.encode([query], convert_to_numpy=True).astype(np.float32)
        return self._ensure_normalized(q)

    def retrieve(self, query: str, top_k: int = 5) -> List[Dict]:
        if self._index.ntotal == 0:
            return []
        q = self._embed_query(query)
        D, I = self._index.search(q, top_k)
        scores = D[0]
        idxs = I[0]
        results: List[Dict] = []
        for score, idx in zip(scores, idxs):
            if idx < 0 or idx >= len(self._items):
                continue
            item = dict(self._items[idx])
            item["score"] = float(score)
            results.append(item)
        return results