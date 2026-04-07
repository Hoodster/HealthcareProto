from __future__ import annotations

import datetime as dt
from typing import Literal, Optional

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
    
    model_config = {
        "from_attributes": True
    }

class UserChatItemOut(BaseModel):
    """Summary of a chat session for list"""
    session_id: str
    latest_message_at: dt.datetime


class ChatInterface(BaseModel):
    """Chat session details"""
    session_id: str
    messages: list[MessageOut]
