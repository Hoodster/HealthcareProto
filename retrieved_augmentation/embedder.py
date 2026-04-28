"""
OpenAI-based embedder implementation for RAG.
"""

from typing import List
from openai import OpenAI

from api.config import get_openai_api_key
from retrieved_augmentation.abstract import Embedder


class OpenAIEmbedder(Embedder):
    """Embedder using OpenAI's embedding models."""
    
    def __init__(self, model: str = "text-embedding-3-small"):
        """
        Initialize the OpenAI embedder.
        
        Args:
            model: The OpenAI embedding model to use
                  Options: 'text-embedding-3-small', 'text-embedding-3-large'
        """
        self.model = model
        api_key = get_openai_api_key()
        if not api_key:
            raise RuntimeError(
                "API_OPENAI not set. Set API_OPENAI in the environment or in .env."
            )
        self.client = OpenAI(api_key=api_key)
        
        # Set embedding dimensions based on model
        self._dimension = 1536 if model == "text-embedding-3-small" else 3072
    
    def embed(self, text: str) -> List[float]:
        """
        Generate an embedding for a single text.
        
        Args:
            text: The text to embed
            
        Returns:
            Embedding vector
        """
        if not text or not text.strip():
            raise ValueError("Cannot embed empty text")
        
        response = self.client.embeddings.create(
            model=self.model,
            input=text
        )
        return response.data[0].embedding if response.data else []
    
    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """
        Generate embeddings for multiple texts.
        
        Args:
            texts: List of texts to embed
            
        Returns:
            List of embedding vectors
        """
        if not texts:
            return []
        
        # Filter out empty texts but keep track of indices
        valid_texts = [(i, text) for i, text in enumerate(texts) if text and text.strip()]
        if not valid_texts:
            return [[] for _ in texts]
        
        indices, valid_text_list = zip(*valid_texts)
        
        response = self.client.embeddings.create(
            model=self.model,
            input=list(valid_text_list)
        )
        
        # Reconstruct full list with empty embeddings for invalid texts
        embeddings = [[] for _ in texts]
        for idx, embedding_data in zip(indices, response.data):
            embeddings[idx] = embedding_data.embedding
        
        return embeddings
    
    def get_embedding_dimension(self) -> int:
        """
        Get the dimension of the embedding vectors.
        
        Returns:
            Embedding dimension
        """
        return self._dimension
