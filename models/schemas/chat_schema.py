from __future__ import annotations

import datetime as dt
from typing import Literal, Optional

from pydantic import BaseModel, Field

ChatMode = Literal["llm", "rag"]


class MessageIn(BaseModel):
    content: str
    session_id: Optional[str] = None
    patient_id: Optional[str] = Field(
        default=None,
        description="When set, clinical context is resolved (MIMIC link or manual history)",
    )
    mode: ChatMode = Field(
        default="rag",
        description="llm = GenAI only; rag = GenAI + retrieved guidelines/patient documents",
    )


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
