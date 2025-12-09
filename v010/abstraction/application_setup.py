from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional, Dict, List

from v010.abstraction.database_service import DatabaseService
from v010.abstraction.embedding_service import EmbeddingService
from v010.abstraction.retriever_service import RetrieverService
from v010.configuration.databases.sqlite_service import SqliteService
from v010.configuration.embedders.basic_embedding_service import BasicEmbeddingService
from basic_retriever_service import BasicRetrieverService
from v010.utils.embedding.formatter import format_answer


@dataclass
class ServiceConfig:
    model_name: str
    api_key: str
    # Add optional kwargs for flexibility
    extra_params: Optional[Dict] = None

@dataclass
class DatabaseConfig:
    connection_string: str
    api_key: str
    # Consider: database_type, pool_size, timeout, etc.

@dataclass
class ApplicationConfig:
    default_cfg: ServiceConfig
    database_cfg: DatabaseConfig = SqliteService
    retriever_cfg: Optional[ServiceConfig] = BasicRetrieverService
    embedder_cfg: Optional[ServiceConfig] = BasicEmbeddingService
    open_api_key: str = os.environ.get("OPENAI_API_KEY", "")
    embedding_model: str = os.environ.get("EMBEDDING_MODEL", "")
    chat_model: str = os.environ.get("CHAT_MODEL", "")


ApplicationSetupInstance = Dict[str, object]

class ApplicationSetup(ABC):
    """
    Base class for application setup with dependency injection.
    Manages retriever, embedder, and database services.
    """
    
    def __init__(self,
                 retriever: RetrieverService,
                 embedder: EmbeddingService,
                 database: DatabaseService,
                 config: ApplicationConfig):
        self._retriever = retriever
        self._embedder = embedder
        self._database = database
        self._config = config
        
        # Validate services are properly initialized
        self._validate_services()
    
    def _validate_services(self) -> None:
        """Validate that all required services are properly configured"""
        if not self._embedder:
            raise ValueError("Embedding service must be provided")
        if not self._retriever:
            raise ValueError("Retriever service must be provided")
        if not self._database:
            raise ValueError("Database service must be provided")
    
    def index_documents(self, documents: List[str]) -> List[List[float]]:
        """
        Index documents by generating embeddings.
        
        Args:
            documents: List of text documents to embed
            
        Returns:
            List of embedding vectors
            
        Raises:
            Exception: If embedding service is not configured
        """
        if not self._embedder:
            raise Exception("Embedding service not configured")
        # Fixed: proper method name (assuming embed_batch or embed_documents)
        return self._embedder.embed_batch(documents)
    
    def send_query(self, query: str, top_k: int = 5) -> str:
        """
        Send query to retriever service.
        
        Args:
            query: Search query string
            top_k: Number of top results to return
            
        Returns:
            Formatted response from retriever
            
        Raises:
            Exception: If retriever service is not configured
        """
        if not self._retriever:
            raise Exception("Retriever service not configured")
        # Fixed: proper method name and added top_k parameter
        return self._retriever.answer_query(query, k=top_k)
    
    def store_embeddings(self, embeddings: List[List[float]], metadata: List[Dict]) -> None:
        """
        Store embeddings and metadata in database.
        
        Args:
            embeddings: List of embedding vectors
            metadata: List of metadata dicts for each embedding
        """
        if not self._database:
            raise Exception("Database service not configured")
        self._database.store(embeddings, metadata)
    
    @abstractmethod
    def initialize(self) -> None:
        """Initialize the application setup. Subclasses must implement."""
        pass
    
    @abstractmethod
    def cleanup(self) -> None:
        """Cleanup resources. Subclasses must implement."""
        pass
    
    @property
    def config(self) -> ApplicationConfig:
        """Get application configuration"""
        return self._config
    
    @property
    def retriever(self) -> RetrieverService:
        """Get retriever service"""
        return self._retriever
    
    @property
    def embedder(self) -> EmbeddingService:
        """Get embedding service"""
        return self._embedder
    
    @property
    def database(self) -> DatabaseService:
        """Get database service"""
        return self._database
