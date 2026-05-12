from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from api.ai_models import MAX_TOKENS, ChatGPTAIModel
from api.config import get_openai_api_key

AIServiceProvider = Literal['ChatGPT']

class AIModelService:
    def __init__(self, ai_provider: Optional[AIServiceProvider] = 'ChatGPT', model: Optional[str] = 'gpt-4o') -> None:
        api_key = get_openai_api_key()
        if not api_key:
            raise RuntimeError(
                "API_OPENAI not set. Set API_OPENAI in the environment or in .env."
            )
        if ai_provider == 'ChatGPT':
            self.client = ChatGPTAIModel(model=model)
        else:
            raise ValueError(f"Unsupported AI provider: {ai_provider}")
        
        
    def __chunk_text(self, text: str, max_tokens = MAX_TOKENS):
        sentences = text.split('. ')
        chunks = []
        for sentence, token in zip(sentences, sentences[1:] + [""]):
            sentece_tokens = len(sentence.split())
            if not chunks or len(chunks[-1].split()) + sentece_tokens <= max_tokens:
                chunks[-1] = (chunks[-1] + ' ' + sentence).strip() if chunks else sentence
            else:
                chunks.append(sentence)
        return chunks


    def list_models(self) -> Any:
        return self.client.list_models()
    
    
    def chat(
        self,
        message: str,
    ) -> str:
        return self.client.answer(message)
    
    
    def summarize(self, text: str) -> str:
        return self.client.summarize(text)

#TODO: move to ai_models
    # def embed(self, text: str):
    #     response = self.client.embeddings.create(
    #         model="text-embedding-3-small",
    #         input=text
    #     )
    #     return response.data[0].embedding if response.data else None
