from __future__ import annotations

from typing import Any, Dict, List, Optional

from openai import OpenAI

from api.config import get_openai_api_key, get_openai_model

SYSTEM_DEFAULT_PROMPT = (
    "You are a helpful and precise assistant for healthcare professionals. "
    "Answer questions as concisely as possible. If you don't know the answer, say you don't know."
)


class AIModelService:
    def __init__(self, model: Optional[str] = None, system_prompt: Optional[str] = None) -> None:
        api_key = get_openai_api_key()
        if not api_key:
            raise RuntimeError(
                "OPENAI_API_KEY not set. Set OPENAI_API_KEY in the environment or in .env."
            )
        self._client = OpenAI(api_key=api_key)
        self._selected_model = model or get_openai_model()
        self._system_prompt = system_prompt or SYSTEM_DEFAULT_PROMPT

    def list_models(self) -> Any:
        return self._client.models.list()

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
        
        completion = self._client.chat.completions.create(**kwargs)
        return (completion.choices[0].message.content or "").strip()
    
    def summarize(self, text: str, model: Optional[str] = None) -> str:
        prompt = f"Summarize the following text:\n\n{text}"
        used_model = model or self._selected_model
        
        answer = self._client.responses.create(
            model=used_model,
            input=prompt,
            tools=[{
                "type": "file_search",
                "vector_store_ids": ["vsd_..."]
            }]
        )
        return (answer.output_text or "").strip()
    