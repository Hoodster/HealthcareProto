from typing import List

from v010.abstraction.application_setup import ApplicationSetup
from v010.configurations.databases.sqlite_service import SqliteService
from v010.configurations.embedders.basic_embedding_service import BasicEmbeddingService
from v010.configurations.retrievers.basic_retriever_service import BasicRetrieverService


class LocalConfigSetup(ApplicationSetup):

    def __init__(self, retriever, embedder, config):
        db_service = SqliteService('sqlite_local_db')
        ebm_service = BasicEmbeddingService("basic-embedder-model", "local-embedder-key")
        ret_service = BasicRetrieverService("retriever", "db_service")
        super().__init__(ret_service, ebm_service, db_service, config)