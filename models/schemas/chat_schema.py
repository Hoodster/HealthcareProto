from __future__ import annotations

import datetime as dt
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


class MessageIn(BaseModel):
    role: Literal["user", "assistant", "system"] = "user"
    content: str


class MessageOut(BaseModel):
    role: str
    content: str
    created_at: dt.datetime
    

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
