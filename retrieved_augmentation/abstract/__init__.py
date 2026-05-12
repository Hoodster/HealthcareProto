"""
Abstract base classes for Retrieval-Augmented Generation (RAG)
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple
from enum import Enum

from pydantic import BaseModel

from api import ai_models
from models.ai_model import AIModel


class ChunkingStrategy(Enum):
    """Chunking strategies for document processing."""
    SENTENCE = "sentence"
    PARAGRAPH = "paragraph"
    SEMANTIC = "semantic"
    SLIDING_WINDOW = "sliding_window"

@dataclass
class DocumentBase:
    """Base class for documents and chunks."""
    content: str
    metadata: Dict[str, Any]

@dataclass
class Document(DocumentBase):
    """Represents a document with content and metadata."""
    markdown: Optional[str] = None
    doc_id: Optional[str] = None
    doc_type: Optional[str] = None  # e.g., 'patient_record', 'knowledge_base', 'clinical_guideline'


@dataclass
class DocumentChunk(DocumentBase):
    """Represents a chunk of a document."""
    chunk_id: str
    doc_id: str
    chunk_index: int
    embedding: Optional[List[float]] = None


@dataclass
class RetrievalResult:
    """Result from a retrieval operation."""
    chunk: DocumentChunk
    score: float
    rank: int


@dataclass
class RAGContext:
    """Context assembled from retrieved documents."""
    query: str
    retrieved_chunks: List[RetrievalResult]
    metadata: Dict[str, Any]
    total_tokens: Optional[int] = None


class DocumentProcessor(ABC):
    """Abstract base class for processing and chunking documents."""
    
    @abstractmethod
    def process(self, document: Document) -> List[DocumentChunk]:
        """
        Process a document and split it into chunks.
        
        Args:
            document: The document to process
            
        Returns:
            List of document chunks
        """
        pass
    
    @abstractmethod
    def chunk(
        self, 
        text: str, 
        strategy: ChunkingStrategy = ChunkingStrategy.PARAGRAPH,
        chunk_size: int = 500,
        overlap: int = 50
    ) -> List[str]:
        """
        Chunk text using the specified strategy.
        
        Args:
            text: The text to chunk
            strategy: The chunking strategy to use
            chunk_size: Target size for each chunk (tokens or characters)
            overlap: Number of tokens/characters to overlap between chunks
            
        Returns:
            List of text chunks
        """
        pass
    
    @abstractmethod
    def clean(self, text: str) -> str:
        """
        Clean and normalize text.
        
        Args:
            text: The text to clean
            
        Returns:
            Cleaned text
        """
        pass
    
    @abstractmethod
    def extract_metadata(self, document: Document) -> Dict[str, Any]:
        """
        Extract metadata from a document.
        
        Args:
            document: The document to extract metadata from
            
        Returns:
            Dictionary of metadata
        """
        pass


class Embedder(ABC):
    """Abstract base class for generating embeddings."""
    
    @abstractmethod
    def embed(self, text: str) -> List[float]:
        """
        Generate an embedding for a single text.
        
        Args:
            text: The text to embed
            
        Returns:
            Embedding vector
        """
        pass
    
    @abstractmethod
    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """
        Generate embeddings for multiple texts.
        
        Args:
            texts: List of texts to embed
            
        Returns:
            List of embedding vectors
        """
        pass
    
    @abstractmethod
    def get_embedding_dimension(self) -> int:
        """
        Get the dimension of the embedding vectors.
        
        Returns:
            Embedding dimension
        """
        pass


class VectorStore(ABC):
    """Abstract base class for vector storage and similarity search."""
    
    @abstractmethod
    def add(self, chunks: List[DocumentChunk]) -> None:
        """
        Add document chunks to the vector store.
        
        Args:
            chunks: List of document chunks with embeddings
        """
        pass
    
    @abstractmethod
    def search(
        self, 
        query_embedding: List[float], 
        top_k: int = 5,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[RetrievalResult]:
        """
        Search for similar chunks using vector similarity.
        
        Args:
            query_embedding: The query embedding vector
            top_k: Number of top results to return
            filters: Optional metadata filters (e.g., doc_type, patient_id)
            
        Returns:
            List of retrieval results ordered by similarity
        """
        pass
    
    @abstractmethod
    def delete(self, doc_id: str) -> None:
        """
        Delete all chunks belonging to a document.
        
        Args:
            doc_id: The document ID to delete
        """
        pass
    
    @abstractmethod
    def update(self, chunk: DocumentChunk) -> None:
        """
        Update a document chunk in the store.
        
        Args:
            chunk: The updated chunk
        """
        pass
    
    @abstractmethod
    def get_stats(self) -> Dict[str, Any]:
        """
        Get statistics about the vector store.
        
        Returns:
            Dictionary with stats (total chunks, documents, etc.)
        """
        pass


class Retriever(ABC):
    """Abstract base class for document retrieval."""
    
    def __init__(self, embedder: Embedder, vector_store: VectorStore):
        self.embedder = embedder
        self.vector_store = vector_store
    
    @abstractmethod
    def retrieve(
        self, 
        query: str, 
        top_k: int = 5,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[RetrievalResult]:
        """
        Retrieve relevant document chunks for a query.
        
        Args:
            query: The search query
            top_k: Number of chunks to retrieve
            filters: Optional metadata filters
            
        Returns:
            List of retrieval results
        """
        pass
    
    @abstractmethod
    def rerank(
        self, 
        query: str, 
        results: List[RetrievalResult]
    ) -> List[RetrievalResult]:
        """
        Rerank retrieval results for better relevance.
        
        Args:
            query: The original query
            results: Initial retrieval results
            
        Returns:
            Reranked results
        """
        pass


class ContextAugmentor(ABC):
    """Abstract base class for augmenting queries with retrieved context."""
    
    @abstractmethod
    def augment(
        self, 
        query: str, 
        retrieved_results: List[RetrievalResult],
        max_tokens: Optional[int] = None
    ) -> RAGContext:
        """
        Augment a query with retrieved context.
        
        Args:
            query: The original query
            retrieved_results: Retrieved document chunks
            max_tokens: Maximum tokens to include in context
            
        Returns:
            RAG context with assembled information
        """
        pass
    
    @abstractmethod
    def format_context(self, rag_context: RAGContext) -> str:
        """
        Format the RAG context into a prompt-ready string.
        
        Args:
            rag_context: The RAG context to format
            
        Returns:
            Formatted context string
        """
        pass
    
    @abstractmethod
    def compress(self, text: str, max_tokens: int) -> str:
        """
        Compress text to fit within token limits.
        
        Args:
            text: The text to compress
            max_tokens: Maximum number of tokens
            
        Returns:
            Compressed text
        """
        pass


class RAGPipeline(ABC):
    """Abstract base class for complete RAG pipeline orchestration."""
    
    def __init__(
        self,
        document_processor: DocumentProcessor,
        embedder: Embedder,
        vector_store: VectorStore,
        retriever: Retriever,
        augmentor: ContextAugmentor
    ):
        self.document_processor = document_processor
        self.embedder = embedder
        self.vector_store = vector_store
        self.retriever = retriever
        self.augmentor = augmentor
    
    @abstractmethod
    def index_document(self, document: Document) -> str:
        """
        Index a document into the RAG system.
        
        Args:
            document: The document to index
            
        Returns:
            Document ID
        """
        pass
    
    @abstractmethod
    def query(
        self, 
        query: str, 
        top_k: int = 5,
        filters: Optional[Dict[str, Any]] = None,
        return_context: bool = False
    ) -> Tuple[str, Optional[RAGContext]]:
        """
        Execute a complete RAG query.
        
        Args:
            query: The user query
            top_k: Number of chunks to retrieve
            filters: Optional metadata filters
            return_context: Whether to return the RAG context
            
        Returns:
            Tuple of (formatted context/answer, optional RAG context)
        """
        pass
    
    @abstractmethod
    def update_document(self, document: Document) -> None:
        """
        Update an existing document in the index.
        
        Args:
            document: The updated document
        """
        pass
    
    @abstractmethod
    def delete_document(self, doc_id: str) -> None:
        """
        Delete a document from the index.
        
        Args:
            doc_id: The document ID to delete
        """
        pass


@dataclass
class RagServiceConfig:
    class GeneralConfig(BaseModel):
        model_config = {"arbitrary_types_allowed": True}
        ai_model: AIModel
        
    class AgentConfig(BaseModel):
        gpt_model: str
        response_format: str
    
    general: GeneralConfig
    agent: AgentConfig
    
class RagService(ABC):
    """Legacy abstract for RAG service (maintained for backward compatibility)."""
    
    def __init__(self, config: Optional[RagServiceConfig] = None):
        """
        Initialize RagService with config.
        
        Args:
            config: Can be:
                - RagServiceConfig instance
                - Dict with config data
                - JSON string with config data
                - None (uses defaults)
        """
        self._config = config or RagServiceConfig(
                general=RagServiceConfig.GeneralConfig(ai_model=ai_models.ChatGPTAIModel()),
                agent=RagServiceConfig.AgentConfig(
                    gpt_model="gpt-3.5-turbo",
                    response_format="json"
                )
            )

    @abstractmethod
    def retrieve(self, query: str):
        """Retrieve relevant documents for a query."""
        pass

    @abstractmethod
    def augment(self, query: str, retrieved_data):
        """Augment query with retrieved data."""
        pass