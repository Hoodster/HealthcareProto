from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class DatabaseConfig:
    name: str
    connection_string: str

class DatabaseService(ABC):
    def __init__(self, config: DatabaseConfig, **kwargs):
        self._name = config.name
        self._connection_string = config.connection_string
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