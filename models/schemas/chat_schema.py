from __future__ import annotations

import datetime as dt
from typing import Literal, Optional

from pydantic import BaseModel, Field


class ChatCreate(BaseModel):
    title: str | None = None


class ChatOut(BaseModel):
    id: int
    title: str | None
    created_at: dt.datetime

    class Config:
        from_attributes = True


class MessageCreate(BaseModel):
    role: Literal["user", "assistant", "system"] = "user"
    content: str


class MessageOut(BaseModel):
    id: int
    role: str
    content: str
    created_at: dt.datetime

    class Config:
        from_attributes = True


class AIChatRequest(BaseModel):
    message: str = Field(..., description="User message to send to the AI")
    system_prompt: Optional[str] = None
    model: Optional[str] = None


class AIChatResponse(BaseModel):
    assistant_message: str
    model: str
