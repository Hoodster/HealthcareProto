from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from v011.api import schemas
from v011.api.auth import get_current_user, get_db
from v011.api.models import Chat, Message, Patient, User
from v011.api.services.ai_model_service import AIModelService


router = APIRouter(prefix="/chats", tags=["chats"])


def _get_chat(db: Session, user: User, chat_id: int) -> Chat:
    chat = db.get(Chat, chat_id)
    if not chat or chat.owner_user_id != user.id:
        raise HTTPException(status_code=404, detail="Chat not found")
    return chat


@router.post("", response_model=schemas.ChatOut)
def create_chat(
    payload: schemas.ChatCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if payload.patient_id is not None:
        patient = db.get(Patient, payload.patient_id)
        if not patient or patient.owner_user_id != user.id:
            raise HTTPException(status_code=404, detail="Patient not found")
    chat = Chat(owner_user_id=user.id, patient_id=payload.patient_id, title=payload.title)
    db.add(chat)
    db.commit()
    db.refresh(chat)
    return chat


@router.get("", response_model=list[schemas.ChatOut])
def list_chats(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    stmt = select(Chat).where(Chat.owner_user_id == user.id).order_by(Chat.created_at.desc())
    return list(db.execute(stmt).scalars().all())


@router.get("/{chat_id}", response_model=schemas.ChatOut)
def get_chat(chat_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return _get_chat(db, user, chat_id)


@router.get("/{chat_id}/messages", response_model=list[schemas.MessageOut])
def list_messages(chat_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    chat = _get_chat(db, user, chat_id)
    stmt = select(Message).where(Message.chat_id == chat.id).order_by(Message.created_at.asc())
    return list(db.execute(stmt).scalars().all())


@router.post("/{chat_id}/messages", response_model=schemas.MessageOut)
def add_message(
    chat_id: int,
    payload: schemas.MessageCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    chat = _get_chat(db, user, chat_id)
    msg = Message(chat_id=chat.id, role=payload.role, content=payload.content)
    db.add(msg)
    db.commit()
    db.refresh(msg)
    return msg


@router.post("/{chat_id}/ai", response_model=schemas.AIChatResponse)
def chat_with_ai(
    chat_id: int,
    payload: schemas.AIChatRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    chat = _get_chat(db, user, chat_id)

    user_msg = Message(chat_id=chat.id, role="user", content=payload.message)
    db.add(user_msg)
    db.flush()

    stmt = select(Message).where(Message.chat_id == chat.id).order_by(Message.created_at.asc())
    prior = list(db.execute(stmt).scalars().all())

    messages = []
    if payload.system_prompt:
        messages.append({"role": "system", "content": payload.system_prompt})
    for m in prior:
        messages.append({"role": m.role, "content": m.content})

    service = AIModelService()
    assistant_text = service.chat(messages=messages, model=payload.model)

    assistant_msg = Message(chat_id=chat.id, role="assistant", content=assistant_text)
    db.add(assistant_msg)
    db.commit()

    return schemas.AIChatResponse(assistant_message=assistant_text, model=(payload.model or "default"))
