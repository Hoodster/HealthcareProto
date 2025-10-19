from abc import ABC
from dataclasses import dataclass
from typing import Optional, Dict, List

from v010.abstraction.database_service import DatabaseService
from v010.abstraction.embedding_service import EmbeddingService
from v010.abstraction.retriever_service import RetrieverService

@dataclass
class ServiceConfig:
    model_name: str
    api_key: str

@dataclass
class DatabaseConfig:
    connection_string: str
    api_key: str

@dataclass
class ApplicationConfig:
    default_cfg: ServiceConfig
    database_cfg: DatabaseConfig
    retriever_cfg: Optional[ServiceConfig] = None
    embedder_cfg: Optional[ServiceConfig] = None

ApplicationSetupInstance = Dict[str, object]

class ApplicationSetup(ABC):
    _retriever: RetrieverService
    _embedder: EmbeddingService
    _database: DatabaseService
    _config: ApplicationConfig

    def __init__(self,
                 retriever: RetrieverService,
                 embedder: EmbeddingService,
                 database: DatabaseService,
                 config: ApplicationConfig):
        self._retriever = retriever
        self._embedder = embedder
        self._database = database
        self._config = config

    @classmethod
    def index_documents(cls, documents: List[str]) -> List[List[float]]:
        if not cls._embedder:
            raise Exception("Embedding service not configured")
        return cls._embedder.embed(documents)

    @classmethod
    def send_query(cls, query: str) -> str:
        if not cls._retriever:
            raise Exception("Retriever service not configured")
        return cls._retriever.retrieve(query)
