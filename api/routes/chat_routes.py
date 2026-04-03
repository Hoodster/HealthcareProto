from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from api.db import get_db_session
import models.schemas as schemas
from api.auth import get_current_user
from api.models import User
from api.services.chat_service import ChatService


router = APIRouter(prefix="/chats", tags=["chats"])


@router.post("", response_model=schemas.ChatOut)
def create_chat(
    payload: schemas.ChatCreate,
    db: Session = Depends(get_db_session),
    user: User = Depends(get_current_user),
):
    return ChatService.create_chat(db, user.id, payload)


@router.get("", response_model=list[schemas.ChatOut])
def list_chats(db: Session = Depends(get_db_session), user: User = Depends(get_current_user)):
    return ChatService.list_chats(db, user.id)


@router.get("/{chat_id}", response_model=schemas.ChatOut)
def get_chat(chat_id: int, db: Session = Depends(get_db_session), user: User = Depends(get_current_user)):
    return ChatService.get_chat(db, user.id, chat_id)


@router.get("/{chat_id}/messages", response_model=list[schemas.MessageOut])
def list_messages(chat_id: int, db: Session = Depends(get_db_session), user: User = Depends(get_current_user)):
    return ChatService.list_messages(db, user.id, chat_id)


@router.post("/{chat_id}/messages", response_model=schemas.MessageOut)
def add_message(
    chat_id: int,
    payload: schemas.MessageCreate,
    db: Session = Depends(get_db_session),
    user: User = Depends(get_current_user),
):
    return ChatService.add_message(db, user.id, chat_id, payload)


@router.post("/{chat_id}/ai", response_model=schemas.AIChatResponse)
def chat_with_ai(
    chat_id: int,
    payload: schemas.AIChatRequest,
    db: Session = Depends(get_db_session),
    user: User = Depends(get_current_user),
):
    return ChatService.chat_with_ai(db, user.id, chat_id, payload)
