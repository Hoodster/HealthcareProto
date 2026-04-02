from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Any, Optional

@dataclass
class AIModelPrompts:
    system_prompt: str
    question_prompt: str
    summary_prompt: str

class AIModel(ABC):
    def __init__(self, name: str, description: str, model: str, prompts: Optional[AIModelPrompts] = None):
        self.name = name
        self.description = description
        self.model = model
        self.prompts = prompts or AIModelPrompts(
            system_prompt="",
            question_prompt="",
            summary_prompt=""
        )
        
    @abstractmethod
    def answer(self, question: str) -> str:
        raise NotImplementedError("Subclasses must implement this method")
    
    @abstractmethod
    def summarize(self, text: str) -> str:
        raise NotImplementedError("Subclasses must implement this method")
    
    @abstractmethod
    def list_models(self) -> Any:
        raise NotImplementedError("Subclasses must implement this method")
