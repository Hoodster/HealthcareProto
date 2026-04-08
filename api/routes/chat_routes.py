from __future__ import annotations
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from api.db import get_db_session
from api.services import ai_service
import models.schemas as schemas
from api.auth import get_current_user
from api.models import User
from api.services.chat_service import ChatService


router = APIRouter(prefix="/chats", tags=["chats"], dependencies=[Depends(get_current_user), Depends(get_db_session)])


@router.post("/send", response_model=schemas.MessageOut)
def send_chat_message(
    payload: schemas.MessageIn,
    user: Optional[User] = Depends(get_current_user),
    db: Session = Depends(get_db_session)
):
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
        messages=[schemas.MessageOut.from_orm(msg) for msg in messages]
    )