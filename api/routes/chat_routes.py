from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from api.db import get_db_session
import models.schemas as schemas
from api.auth import get_current_user
from api.models import User
from api.services.chat_service import ChatService


router = APIRouter(prefix="/chats", tags=["chats"], dependencies=[Depends(get_current_user), Depends(get_db_session)])


@router.post("/send", response_model=schemas.ChatReplyOut)
def send_chat_message(
    payload: schemas.MessageIn,
    user: Optional[User] = Depends(get_current_user),
    db: Session = Depends(get_db_session),
):
    """
    Send a chat message (mode `llm` or `rag`).

    **Session:** omit `session_id` to start a new conversation; reuse `session_id`
    from the response on follow-up messages.

    **LLM switch:** set `llm_provider` to `openai` or `claude` in the JSON body
    (optional `llm_model`). Response echoes `llm_provider` / `llm_model` used.
    RAG retrieval always uses OpenAI embeddings regardless of provider.
    """
    return ChatService.send_chat_message(payload=payload, current_user=user, db=db)


@router.get("", response_model=list[schemas.UserChatItemOut])
def list_chats(user: User = Depends(get_current_user), db: Session = Depends(get_db_session)):
    """List all chat sessions for the current user."""
    return ChatService.list_chats(db=db, user_id=user.id)


@router.get("/{chat_id}", response_model=schemas.ChatInterface)
def get_chat(chat_id: str, db: Session = Depends(get_db_session)):
    """Get all messages for a specific chat session."""
    messages = ChatService.get_chat(db=db, chat_id=chat_id)
    if not messages:
        raise HTTPException(status_code=404, detail="Chat session not found")
    return schemas.ChatInterface(
        session_id=chat_id,
        messages=[schemas.MessageOut.model_validate(msg) for msg in messages],
    )
