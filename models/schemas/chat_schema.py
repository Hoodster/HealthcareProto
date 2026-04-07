from __future__ import annotations

import datetime as dt
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


class MessageIn(BaseModel):
    role: Literal["user", "assistant", "system"] = "user"
    content: str
    session_id: Optional[str] = None


class MessageOut(BaseModel):
    role: str
    content: str
    created_at: dt.datetime
    session_id: str
    
class ChatInterface(BaseModel):
    session_id: str
    messages: list[MessageOut]
