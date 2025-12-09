from typing import Type
from v010.abstraction.application_setup import ServiceConfig, ApplicationConfig
from v010.abstraction.embedding_service import EmbeddingService
from v010.abstraction.retriever_service import RetrieverService
from v010.abstraction.database_service import DatabaseService

class ServiceFactory:
    """Factory for creating service instances from configuration"""
    
    @staticmethod
    def create_embedder(config: ServiceConfig, embedder_class: Type[EmbeddingService]) -> EmbeddingService:
        """Create embedding service from config"""
        extra = config.extra_params or {}
        return embedder_class(
            model_name=config.model_name,
            api_key=config.api_key,
            **extra
        )
    
    @staticmethod
    def create_retriever(config: ServiceConfig, retriever_class: Type[RetrieverService]) -> RetrieverService:
        """Create retriever service from config"""
        extra = config.extra_params or {}
        return retriever_class(
            model_name=config.model_name,
            api_key=config.api_key,
            **extra
        )
    
    @staticmethod
    def create_database(config: DatabaseConfig, database_class: Type[DatabaseService]) -> DatabaseService:
        """Create database service from config"""
        return database_class(
            connection_string=config.connection_string,
            api_key=config.api_key
        )