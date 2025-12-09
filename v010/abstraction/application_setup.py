import os
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
    api_key: str = ""


@dataclass
class DatabaseConfig:
    connection_string: str
    api_key: str = ""


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


class ApplicationSetup:
    def __init__(self,
                 retriever: RetrieverService,
                 embedder: EmbeddingService,
                 database: DatabaseService,
                 config: ApplicationConfig):
        self._retriever = retriever
        self._embedder = embedder
        self._database = database
        self._config = config

    def index_documents(self, documents: List[str]) -> int:
        if not self._embedder:
            raise Exception("Embedding service not configured")
        total_chunks = 0
        for path in documents:
            chunks = getattr(self._embedder, "embed_file_chunks", None)
            if callable(chunks):
                embedded_chunks = self._embedder.embed_file_chunks(path)
                self._retriever.add(embedded_chunks)
                total_chunks += len(embedded_chunks)
            else
                docs = self._embedder.embed_from_files([path])
                self._retriever.add(docs)
                total_chunks += len(docs)
        return total_chunks

    def send_query(self, query: str, top_k: int = 5) -> str:
        if not self._retriever:
            raise Exception("Retriever service not configured")
        results = self._retriever.retrieve(query, top_k=top_k)
        return format_answer(query, results)
