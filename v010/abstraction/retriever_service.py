from abc import ABC


class RetrieverService(ABC):
    def __init__(self, model_name: str, api_key: str, **kwargs):
        self._model_name = model_name
        self._api_key = api_key