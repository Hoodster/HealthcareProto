from abc import ABC, abstractmethod

class DatabaseService(ABC):
    def __init__(self, name: str, connection_string: str, **kwargs):
        self._name = name
        self._connection_string = connection_string
        self._connection = None

    @abstractmethod
    def connect(self):
        pass

    @abstractmethod
    def disconnect(self):
        pass

    @abstractmethod
    def execute(self, script: str):
        pass