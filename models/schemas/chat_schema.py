from __future__ import annotations

import datetime as dt
from typing import Any, Literal, Optional

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


class AIChatResponse(BaseModel):
    assistant_message: str
    model: str


class ClinicalChatRequest(BaseModel):
    message: str = Field(..., description="Clinical question about the patient")
    model: Optional[str] = None


class ClinicalAlert(BaseModel):
    message: str
    severity: str
    category: str
    rule_name: str


class ClinicalChatResponse(BaseModel):
    assistant_message: str
    model: str
    contraindicated: bool
    risk_score: int
    alerts: list[ClinicalAlert]
    rag_used: bool = False
