"""Shared LLM provider query/body params — visible in OpenAPI/Swagger."""

from __future__ import annotations

from enum import Enum
from typing import Annotated, Optional

from fastapi import Query


class LlmProvider(str, Enum):
    openai = "openai"
    claude = "claude"


LLM_PROVIDER_QUERY = Annotated[
    Optional[LlmProvider],
    Query(
        description="GenAI/RAG completion provider. Default: env LLM_PROVIDER or openai.",
        examples=["openai", "claude"],
    ),
]

LLM_MODEL_QUERY = Annotated[
    Optional[str],
    Query(
        description="Override LLM model id (e.g. gpt-4o, claude-sonnet-4-6)",
        examples=["gpt-4o", "claude-sonnet-4-6"],
    ),
]


def provider_value(provider: Optional[LlmProvider]) -> Optional[str]:
    return provider.value if provider is not None else None
