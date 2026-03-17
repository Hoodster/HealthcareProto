from __future__ import annotations

import datetime as dt
from typing import Literal, Optional

from pydantic import BaseModel, EmailStr, Field


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6)
    full_name: str | None = None
    role: str | None = None


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class AuthResponse(BaseModel):
    token: str
    user_id: int
    email: EmailStr


class ProfileOut(BaseModel):
    user_id: int
    full_name: str | None
    role: str | None
    created_at: dt.datetime

    class Config:
        from_attributes = True

class ChatCreate(BaseModel):
    patient_id: int | None = None
    title: str | None = None


class ChatOut(BaseModel):
    id: int
    patient_id: int | None
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
    

class HistoryRecordCreate(BaseModel):
    kind: str
    note: str
    occurred_at: dt.datetime | None = None
    attachments: Optional[list[str]] = None
