from __future__ import annotations

from typing import Any, Dict, List, Optional

from openai import OpenAI

from v011.api.config import get_openai_api_key, get_openai_model


class AIModelService:
    def __init__(self) -> None:
        api_key = get_openai_api_key()
        if not api_key:
            raise RuntimeError(
                "OPENAI_API_KEY not set. Set OPENAI_API_KEY in the environment or in .env."
            )
        self._client = OpenAI(api_key=api_key)

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
        used_model = model or get_openai_model()
        completion = self._client.chat.completions.create(
            model=used_model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return (completion.choices[0].message.content or "").strip()
