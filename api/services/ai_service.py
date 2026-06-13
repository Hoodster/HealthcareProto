from __future__ import annotations

import os
from typing import Any, Literal, Optional

from api.ai_models import MAX_TOKENS, ChatGPTAIModel, ClaudeAIModel
from api.config import get_claude_api_key, get_openai_api_key

LLMProviderName = Literal["openai", "claude"]

DEFAULT_LLM_MODELS: dict[LLMProviderName, str] = {
    "openai": "gpt-4o",
    "claude": "claude-sonnet-4-20250514",
}


def normalize_llm_provider(provider: Optional[str]) -> LLMProviderName:
    """Map env/CLI values to internal provider id."""
    raw = (provider or os.getenv("LLM_PROVIDER", "openai")).lower()
    if raw in ("openai", "chatgpt"):
        return "openai"
    if raw in ("claude", "anthropic"):
        return "claude"
    raise ValueError(f"Unsupported LLM provider: {provider!r} (use openai or claude)")


class AIModelService:
    def __init__(
        self,
        ai_provider: Optional[str] = None,
        model: Optional[str] = None,
    ) -> None:
        self.provider = normalize_llm_provider(ai_provider)
        self.model = model or os.getenv("LLM_MODEL") or DEFAULT_LLM_MODELS[self.provider]

        if self.provider == "openai":
            if not get_openai_api_key():
                raise RuntimeError(
                    "API_OPENAI not set. Set API_OPENAI in the environment or in .env."
                )
            self.client = ChatGPTAIModel(model=self.model)
        else:
            if not get_claude_api_key():
                raise RuntimeError(
                    "API_CLAUDE not set. Set API_CLAUDE in the environment or in .env."
                )
            self.client = ClaudeAIModel(model=self.model)

    def __chunk_text(self, text: str, max_tokens=MAX_TOKENS):
        sentences = text.split(". ")
        chunks = []
        for sentence, token in zip(sentences, sentences[1:] + [""]):
            sentece_tokens = len(sentence.split())
            if not chunks or len(chunks[-1].split()) + sentece_tokens <= max_tokens:
                chunks[-1] = (chunks[-1] + " " + sentence).strip() if chunks else sentence
            else:
                chunks.append(sentence)
        return chunks

    def list_models(self) -> Any:
        return self.client.list_models()

    def chat(self, message: str) -> str:
        return self.client.answer(message)

    def summarize(self, text: str) -> str:
        return self.client.summarize(text)
