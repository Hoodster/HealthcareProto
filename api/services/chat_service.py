from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

import models.schemas as schemas
from api.models import Chat, Message
from api.services.ai_service import AIModelService


class ChatService:
    @staticmethod
    def create_chat(db: Session, user_id: str, payload: schemas.ChatCreate) -> Chat:
        chat = Chat(user_id=user_id, title=payload.title)
        db.add(chat)
        db.commit()
        db.refresh(chat)
        return chat

    @staticmethod
    def list_chats(db: Session, user_id: str) -> list[Chat]:
        stmt = select(Chat).where(Chat.user_id == user_id).order_by(Chat.created_at.desc())
        return list(db.execute(stmt).scalars().all())

    @staticmethod
    def get_chat(db: Session, user_id: str, chat_id: int) -> Chat:
        chat = db.get(Chat, chat_id)
        if not chat:
            raise HTTPException(status_code=404, detail="Chat not found")
        if chat.user_id != user_id:
            raise HTTPException(status_code=403, detail="Access denied")
        return chat

    @staticmethod
    def list_messages(db: Session, user_id: str, chat_id: int) -> list[Message]:
        chat = ChatService.get_chat(db, user_id, chat_id)
        stmt = select(Message).where(Message.chat_id == chat.id).order_by(Message.created_at.asc())
        return list(db.execute(stmt).scalars().all())

    @staticmethod
    def add_message(
        db: Session,
        user_id: str,
        chat_id: int,
        payload: schemas.MessageCreate,
    ) -> Message:
        chat = ChatService.get_chat(db, user_id, chat_id)
        msg = Message(chat_id=chat.id, role=payload.role, content=payload.content)
        db.add(msg)
        db.commit()
        db.refresh(msg)
        return msg

    @staticmethod
    def chat_with_ai(
        db: Session,
        user_id: str,
        chat_id: int,
        payload: schemas.AIChatRequest,
    ) -> schemas.AIChatResponse:
        chat = ChatService.get_chat(db, user_id, chat_id)

        user_msg = Message(chat_id=chat.id, role="user", content=payload.message)
        db.add(user_msg)
        db.flush()

        stmt = select(Message).where(Message.chat_id == chat.id).order_by(Message.created_at.asc())
        prior_messages = list(db.execute(stmt).scalars().all())

        messages: list[dict[str, str]] = []
        if payload.system_prompt:
            messages.append({"role": "system", "content": payload.system_prompt})
        for message in prior_messages:
            messages.append({"role": message.role, "content": message.content})

        assistant_text = AIModelService().chat(messages=messages, model=payload.model)

        assistant_msg = Message(chat_id=chat.id, role="assistant", content=assistant_text)
        db.add(assistant_msg)
        db.commit()

        return schemas.AIChatResponse(
            assistant_message=assistant_text,
            model=(payload.model or "default"),
        )
