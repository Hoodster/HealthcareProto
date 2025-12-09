"""Abstract retriever service for similarity search over embedded chunks/documents."""

from abc import ABC, abstractmethod
from typing import List, Dict


class RetrieverService(ABC):
    def __init__(self, model_name: str, api_key: str, **kwargs):
        self
        self._model_name = model_name
        self._api_key = api_key
        
    def answer_query(self, query: str, k: int = 5) -> str:
        raise NotImplementedError("Subclasses must implement this method")
