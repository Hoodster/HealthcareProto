from v010.abstraction.application_setup import ApplicationSetup, ApplicationConfig, ServiceConfig, DatabaseConfig
from v010.configuration.databases.sqlite_service import SqliteService
from v010.configuration.embedders.basic_embedding_service import BasicEmbeddingService
from basic_retriever_service import BasicRetrieverService


class LocalConfigSetup(ApplicationSetup):
    def __init__(self):
        # Configure services with sensible defaults
        db_service = SqliteService('sqlite_local_db')
        ebm_service = BasicEmbeddingService()
        ret_service = BasicRetrieverService()
        app_cfg = ApplicationConfig(
            default_cfg=ServiceConfig(model_name="sentence-transformers/all-MiniLM-L6-v2"),
            database_cfg=DatabaseConfig(connection_string='sqlite_local_db')
        )
        super().__init__(ret_service, ebm_service, db_service, app_cfg)