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

    @staticmethod
    def patient_clinical_chat(
        db: Session,
        user_id: str,
        patient_id: str,
        payload: schemas.ClinicalChatRequest,
    ) -> schemas.ClinicalChatResponse:
        """Chat endpoint that feeds patient data through the expert system before calling LLM."""
        from expert_system import RuleEngine
        from api.services.patient_service import PatientService

        # 1. Build PatientContext from DB records
        patient_context = PatientService.build_patient_context(patient_id, db)

        # 2. Run expert system
        engine = RuleEngine()
        decision = engine.evaluate(patient_context)

        # 3a. RxNorm drug interactions (optional – gracefully skip if API unavailable)
        rxnorm_section = ""
        try:
            from api.services.drug_service import DrugService
            interactions = DrugService.check_interactions(patient_context.medications)
            if interactions:
                lines = "\n".join(
                    f"  [{i['severity'].upper()}] {i['drug_1']} ↔ {i['drug_2']}: {i['description']}"
                    for i in interactions
                )
                rxnorm_section = f"\n\nRxNorm drug interactions:\n{lines}"
        except Exception:
            pass

        # 3b. Try RAG retrieval (optional – gracefully skip if index not seeded)
        rag_chunks: list[str] = []
        rag_used = False
        try:
            from v011.retrieved_augumentation.rag_system import MedicalRAGSystem
            rag = MedicalRAGSystem()
            results = rag.retrieve(payload.message, top_k=3)
            rag_chunks = [r.get("text", "") for r in results if r.get("text")]
            rag_used = bool(rag_chunks)
        except Exception:
            pass

        # 4. Build system prompt enriched with clinical context
        alert_lines = "\n".join(
            f"  [{a.severity.upper()}] {a.category}: {a.message}"
            for a in decision.alerts
        )
        contraindication_line = (
            "⚠ CONTRAINDICATED" if decision.contraindicated else "No absolute contraindication detected"
        )
        med_line = ", ".join(patient_context.medications) or "none recorded"
        condition_line = ", ".join(patient_context.conditions) or "none recorded"
        rag_section = (
            "\n\nRelevant literature:\n" + "\n---\n".join(rag_chunks)
            if rag_chunks else ""
        )

        system_prompt = (
            "You are a clinical decision support assistant. "
            "The following expert system analysis has been performed for this patient. "
            "Use this information to inform your answer, but do not repeat every alert verbatim.\n\n"
            f"Patient summary:\n"
            f"  Age: {patient_context.age or 'unknown'}, Gender: {patient_context.gender or 'unknown'}\n"
            f"  QTc: {patient_context.qtc} ms, eGFR: {patient_context.egfr} mL/min/1.73m²\n"
            f"  Medications: {med_line}\n"
            f"  Conditions: {condition_line}\n\n"
            f"Expert system result:\n"
            f"  Status: {contraindication_line}\n"
            f"  Risk score: {decision.risk_score}/100\n"
            f"  Alerts:\n{alert_lines if alert_lines else '  None'}"
            f"{rxnorm_section}"
            f"{rag_section}"
        )

        # 5. Call LLM
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": payload.message},
        ]
        assistant_text = AIModelService().chat(messages=messages, model=payload.model)

        alerts_out = [
            schemas.ClinicalAlert(
                message=a.message,
                severity=a.severity.value if hasattr(a.severity, "value") else str(a.severity),
                category=a.category,
                rule_name=a.rule_name,
            )
            for a in decision.alerts
        ]

        return schemas.ClinicalChatResponse(
            assistant_message=assistant_text,
            model=(payload.model or "default"),
            contraindicated=decision.contraindicated,
            risk_score=decision.risk_score,
            alerts=alerts_out,
            rag_used=rag_used,
        )
