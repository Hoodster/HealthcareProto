"""Abstract retriever service for similarity search over embedded chunks/documents."""

from abc import ABC, abstractmethod
from typing import List, Dict


class RetrieverService(ABC):
    def __init__(self, model_name: str, api_key: str, **kwargs):
        self._model_name = model_name
        self._api_key = api_key

    @abstractmethod
    def add(self, items: List[Dict]):
        """Add embedded items to index. Each item must contain 'embedding'."""
        raise NotImplementedError

    @abstractmethod
    def retrieve(self, query: str, top_k: int = 5) -> List[Dict]:
        """Return top_k most similar items with score."""
        raise NotImplementedError