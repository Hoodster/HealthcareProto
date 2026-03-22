from __future__ import annotations

import datetime as dt

from pydantic import BaseModel

from models.schemas import (
    AIChatRequest,
    AIChatResponse,
    AuthResponse,
    ChatCreate,
    ChatOut,
    LoginRequest,
    MessageCreate,
    MessageOut,
    ProfileOut,
    RegisterRequest,
)


class HistoryRecordCreate(BaseModel):
    kind: str
    note: str
    occurred_at: dt.datetime | None = None
    attachments: list[str] | None = None
