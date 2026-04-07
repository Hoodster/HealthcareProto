from __future__ import annotations
from typing import Optional

from fastapi import APIRouter, Depends
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


@router.get("/chats", response_model=list[schemas.MessageOut])
def list_chats(user: User = Depends(get_current_user), db: Session = Depends(get_db_session)):
    return ChatService.list_chats(db=db, user_id=user.id)