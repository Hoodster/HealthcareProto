"""
Retrieval-Augmented Generation (RAG) module for healthcare application.

This module provides comprehensive RAG capabilities including:
- Abstract base classes for RAG components
- OpenAI-based embedder
- Healthcare document processor  
- Context augmentor
- Example implementations

Usage:
    from retrieved_augmentation import (
        Document,
        DocumentChunk,
        OpenAIEmbedder,
        HealthcareDocumentProcessor,
        HealthcareContextAugmentor
    )
"""

from retrieved_augmentation.abstract import (
    ChunkingStrategy,
    Document,
    DocumentChunk,
    RetrievalResult,
    RAGContext,
    DocumentProcessor,
    Embedder,
    VectorStore,
    Retriever,
    ContextAugmentor,
    RAGPipeline,
    RagService,
)

from retrieved_augmentation.embedder import OpenAIEmbedder
from retrieved_augmentation.document_processor import HealthcareDocumentProcessor
from retrieved_augmentation.augmentor import HealthcareContextAugmentor

__all__ = [
    # Enums
    'ChunkingStrategy',
    
    # Data models
    'Document',
    'DocumentChunk',
    'RetrievalResult',
    'RAGContext',
    
    # Abstract base classes
    'DocumentProcessor',
    'Embedder',
    'VectorStore',
    'Retriever',
    'ContextAugmentor',
    'RAGPipeline',
    'RagService',
    
    # Concrete implementations
    'OpenAIEmbedder',
    'HealthcareDocumentProcessor',
    'HealthcareContextAugmentor',
]
