from __future__ import annotations
from typing import Optional, Any
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from api.ai_models import ChatGPTAIModel
from api.auth import HPDbSession
import models.schemas as schemas
from api.models import ChatMessage, User

class ChatService:
    
    @staticmethod
    def send_chat_message(db: HPDbSession, payload: schemas.MessageIn, current_user: Optional[User] = None) -> ChatMessage:
        if not payload.session_id:
            stmt = select(ChatMessage.session_id).order_by(ChatMessage.created_at.desc()).limit(1)
            result = db.execute(stmt).scalar()
            payload.session_id = result or str(uuid4())
        
        new_question = ChatMessage(
            sender_role="user", 
            content=payload.content, 
            session_id=payload.session_id, 
            user_id=current_user.id if current_user else None)
        db.add(new_question)
        
        ai_answer = ChatGPTAIModel().answer(payload.content)
        new_response = ChatMessage(
            sender_role="assistant", 
            content=ai_answer, 
            session_id=payload.session_id
        )
        db.add(new_response)
        db.commit()
        db.refresh(new_response)

        return new_question

    @staticmethod
    def list_chats(db: Session, user_id: str) -> list[Any]:
        stmt = select(ChatMessage.session_id, ChatMessage.created_at).where(ChatMessage.user_id == user_id).distinct(ChatMessage.session_id).order_by(ChatMessage.created_at.desc())
        return list(db.execute(stmt).all())

    @staticmethod
    def get_chat(db: Session, chat_id: str) -> list[ChatMessage]:
        stmt = select(ChatMessage).where(ChatMessage.session_id == chat_id).order_by(ChatMessage.created_at.asc())
        chats = list(db.execute(stmt).scalars().all())
        if not chats:
            raise HTTPException(status_code=404, detail="Chat not found")
        return chats