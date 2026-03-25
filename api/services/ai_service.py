from __future__ import annotations

from typing import Any, Dict, List, Optional

from openai import OpenAI

from api.config import get_openai_api_key, get_openai_model

SYSTEM_DEFAULT_PROMPT = (
    "You are a helpful and precise assistant for healthcare professionals. "
    "Answer questions as concisely as possible. If you don't know the answer, say you don't know."
)

MAX_TOKENS = 600

class AIModelService:
    def __init__(self, model: Optional[str] = None, system_prompt: Optional[str] = None) -> None:
        api_key = get_openai_api_key()
        if not api_key:
            raise RuntimeError(
                "OPENAI_API_KEY not set. Set OPENAI_API_KEY in the environment or in .env."
            )
        self.client = OpenAI(api_key=api_key)
        self._selected_model = model or get_openai_model()
        self._system_prompt = system_prompt or SYSTEM_DEFAULT_PROMPT
        
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
        return self.client.models.list()

    def chat(
        self,
        *,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        temperature: float = 0.2,
        max_tokens: int = 512,
    ) -> str:
        used_model = model or self._selected_model
        
        kwargs = {
            "model": used_model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        
        completion = self.client.chat.completions.create(**kwargs)
        return (completion.choices[0].message.content or "").strip()
    
    def summarize(self, text: str, model: Optional[str] = None) -> str:
        prompt = f"Summarize the following text:\n\n{text}"
        used_model = model or self._selected_model
        
        answer = self.client.responses.create(
            model=used_model,
            input=prompt,
            tools=[{
                "type": "file_search",
                "vector_store_ids": ["vsd_..."]
            }]
        )
        return (answer.output_text or "").strip()
    
    def embed(self, text: str):
        response = self.client.embeddings.create(
            model="text-embedding-3-small",
            input=text
        )
        return response.data[0].embedding if response.data else None
    