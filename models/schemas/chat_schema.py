from __future__ import annotations

import datetime as dt
from typing import Literal, Optional

from pydantic import BaseModel, Field

from api.llm_params import LlmProvider

ChatMode = Literal["llm", "rag"]


class MessageIn(BaseModel):
    content: str
    session_id: Optional[str] = Field(
        default=None,
        description="Chat session id. Omit to start a new session; reuse the id from the previous reply to continue.",
    )
    patient_id: Optional[str] = Field(
        default=None,
        description="When set, clinical context is resolved (MIMIC link or manual history)",
    )
    mode: ChatMode = Field(
        default="rag",
        description="llm = GenAI only; rag = GenAI + retrieved guidelines/patient documents",
    )
    llm_provider: Optional[LlmProvider] = Field(
        default=None,
        description="GenAI provider: openai or claude. Default from env LLM_PROVIDER",
        json_schema_extra={"examples": ["openai", "claude"]},
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "content": "Czy amiodaron z sotalolem to ryzyko QT?",
                    "mode": "rag",
                    "llm_provider": "claude",
                },
                {
                    "content": "Podsumuj ryzyko leków pacjenta",
                    "mode": "llm",
                    "llm_provider": "openai",
                    "session_id": "550e8400-e29b-41d4-a716-446655440000",
                },
            ]
        }
    }


class MessageOut(BaseModel):
    sender_role: str
    content: str
    created_at: dt.datetime
    session_id: str

    model_config = {
        "from_attributes": True
    }


class ChatReplyOut(BaseModel):
    """Assistant reply with mode metadata (RAG sources empty in llm mode)."""
    session_id: str = Field(
        description="Chat session id — send on the next message to continue this conversation",
    )
    message: MessageOut
    mode: ChatMode
    rag_sources: list[dict] = Field(default_factory=list)


class UserChatItemOut(BaseModel):
    """Summary of a chat session for list"""
    session_id: str
    latest_message_at: dt.datetime


class ChatInterface(BaseModel):
    """Chat session details"""
    session_id: str
    messages: list[MessageOut]
