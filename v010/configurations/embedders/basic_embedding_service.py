from v010.abstraction.embedding_service import EmbeddingService


class BasicEmbeddingService(EmbeddingService):

    def __init__(self, model_name: str, api_key: str, **kwargs):
        super().__init__(model_name, api_key, **kwargs)
        

