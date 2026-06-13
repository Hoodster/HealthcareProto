from __future__ import annotations

from typing import Optional
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from api.auth import HPDbSession
from api.rag_store import build_rag_query, retrieve_context_with_sources
from api.services.ai_service import AIModelService
from api.services.patient_service import PatientService
import models.schemas as schemas
from api.models import ChatMessage, User


class ChatService:

    @staticmethod
    def send_chat_message(
        db: HPDbSession,
        payload: schemas.MessageIn,
        current_user: Optional[User] = None,
    ) -> schemas.ChatReplyOut:
        current_user_id = current_user.id if current_user else None

        if not payload.session_id:
            payload.session_id = str(uuid4())
        elif current_user_id:
            owner_stmt = (
                select(ChatMessage.user_id)
                .where(ChatMessage.session_id == payload.session_id)
                .limit(1)
            )
            owner_id = db.execute(owner_stmt).scalar()
            if owner_id is not None and owner_id != current_user_id:
                raise HTTPException(status_code=403, detail="Not authorized for this chat session")

        history_stmt = (
            select(ChatMessage)
            .where(ChatMessage.session_id == payload.session_id)
            .order_by(ChatMessage.created_at.asc())
        )
        if current_user_id:
            history_stmt = history_stmt.where(ChatMessage.user_id == current_user_id)
        prior_messages = db.execute(history_stmt).scalars().all()
        history = [
            {"role": msg.sender_role, "content": msg.content}
            for msg in prior_messages
            if msg.sender_role in ("user", "assistant")
        ]

        new_question = ChatMessage(
            sender_role="user",
            content=payload.content,
            session_id=payload.session_id,
            user_id=current_user_id,
        )
        db.add(new_question)

        patient_ctx = None
        if payload.patient_id:
            patient = PatientService.get_by_id(db, payload.patient_id)
            if current_user and not current_user.staff and patient.user_id != current_user.id:
                raise HTTPException(status_code=403, detail="Not authorized for this patient")
            patient_ctx = PatientService.resolve_patient_context(payload.patient_id, db)

        rag_sources: list[dict] = []
        rag_ctx: str | None = None
        if payload.mode == "rag":
            rag_query = build_rag_query(payload.content, patient_ctx)
            rag_ctx, rag_sources = retrieve_context_with_sources(
                rag_query,
                top_k=6,
                patient_id=payload.patient_id,
            )
            rag_ctx = rag_ctx or None

        try:
            provider = payload.llm_provider.value if payload.llm_provider else None
            ai = AIModelService(ai_provider=provider)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except RuntimeError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc

        ai_answer = ai.client.answer(
            payload.content,
            patient_data=patient_ctx,
            history=history,
            rag_context=rag_ctx,
        )
        new_response = ChatMessage(
            sender_role="assistant",
            content=ai_answer,
            session_id=payload.session_id,
            user_id=current_user_id,
        )
        db.add(new_response)
        db.commit()
        db.refresh(new_response)

        return schemas.ChatReplyOut(
            session_id=payload.session_id,
            message=schemas.MessageOut(
                sender_role=new_response.sender_role,
                content=new_response.content,
                created_at=new_response.created_at,
                session_id=payload.session_id,
            ),
            mode=payload.mode,
            rag_sources=rag_sources,
        )

    @staticmethod
    def list_chats(db: Session, user_id: str) -> list[schemas.UserChatItemOut]:
        """List all chat sessions for a user with their latest message timestamp."""
        stmt = (
            select(ChatMessage.session_id, ChatMessage.created_at)
            .where(ChatMessage.user_id == user_id, ChatMessage.session_id.isnot(None))
            .distinct(ChatMessage.session_id)
            .order_by(ChatMessage.session_id, ChatMessage.created_at.desc())
        )
        results = db.execute(stmt).all()
        return [schemas.UserChatItemOut(session_id=row[0], latest_message_at=row[1]) for row in results]

    @staticmethod
    def get_chat(db: Session, chat_id: str, user_id: str | None = None) -> list[ChatMessage]:
        stmt = select(ChatMessage).where(ChatMessage.session_id == chat_id)
        if user_id:
            stmt = stmt.where(ChatMessage.user_id == user_id)
        stmt = stmt.order_by(ChatMessage.created_at.asc())
        chats = list(db.execute(stmt).scalars().all())
        if not chats:
            raise HTTPException(status_code=404, detail="Chat not found")
        return chats
