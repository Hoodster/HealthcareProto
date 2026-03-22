from __future__ import annotations

from datetime import datetime

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

import models.schemas as schemas
from api.models import Patient, PatientFile, PatientHistoryEntry
from api.services.ai_service import AIModelService


class PatientService:
    @staticmethod
    def create_patient(
        db: Session,
        user_id: str,
        patient_dto: schemas.PatientCreate,
    ) -> Patient:
        patient = Patient(
            user_id=user_id,
            first_name=patient_dto.first_name,
            last_name=patient_dto.last_name,
            dob=patient_dto.dob,
            sex=patient_dto.sex,
        )
        db.add(patient)
        db.commit()
        db.refresh(patient)
        return patient

    @staticmethod
    def list_patients(db: Session, user_id: str) -> list[Patient]:
        stmt = select(Patient).where(Patient.user_id == user_id).order_by(
            Patient.created_at.desc()
        )
        return list(db.execute(stmt).scalars().all())

    @staticmethod
    def get_by_id(db: Session, patient_id: str, user_id: str) -> Patient:
        patient = db.get(Patient, patient_id)
        if not patient:
            raise HTTPException(status_code=404, detail="Patient not found")
        if patient.user_id != user_id:
            raise HTTPException(status_code=403, detail="Access denied")
        return patient

    @staticmethod
    def add_history_record(
        db: Session,
        user_id: str,
        patient_id: str,
        kind: str,
        note: str,
        occurred_at: datetime | None = None,
    ) -> PatientHistoryEntry:
        PatientService.get_by_id(db, patient_id, user_id)

        entry = PatientHistoryEntry(
            patient_id=patient_id,
            kind=kind,
            note=note,
            occurred_at=occurred_at or datetime.utcnow(),
        )

        db.add(entry)
        db.commit()
        db.refresh(entry)
        return entry

    @staticmethod
    def list_history(
        db: Session,
        user_id: str,
        patient_id: str,
        *,
        kind: str | None = None,
    ) -> list[PatientHistoryEntry]:
        PatientService.get_by_id(db, patient_id, user_id)

        stmt = select(PatientHistoryEntry).where(
            PatientHistoryEntry.patient_id == patient_id
        )
        if kind is not None:
            stmt = stmt.where(PatientHistoryEntry.kind == kind)

        stmt = stmt.order_by(
            PatientHistoryEntry.occurred_at.desc(),
            PatientHistoryEntry.created_at.desc(),
        )
        return list(db.execute(stmt).scalars().all())

    @staticmethod
    def summarize_patient_profile(db: Session, patient_id: str, user_id: str) -> str:
        patient = PatientService.get_by_id(db, patient_id, user_id)

        files = db.query(PatientFile).filter(
            PatientFile.patient_id == patient_id
        ).all()
        history = (
            db.query(PatientHistoryEntry)
            .filter(PatientHistoryEntry.patient_id == patient_id)
            .order_by(PatientHistoryEntry.occurred_at.desc())
            .limit(50)
            .all()
        )

        profile_text = (
            f"Patient {patient.first_name} {patient.last_name}, "
            f"born on {patient.dob}, sex: {patient.sex}\n\n"
        )

        if files:
            profile_text += "Files:\n"
            for file in files:
                content_preview = file.content_text[:100] if file.content_text else "No content"
                profile_text += f"- {file.filename}: {content_preview}...\n"

        if history:
            profile_text += "\nHistory:\n"
            for entry in history:
                note_preview = entry.note[:100] if entry.note else ""
                profile_text += f"- [{entry.occurred_at}] {entry.kind}: {note_preview}...\n"

        summary = AIModelService().chat(
            messages=[
                {
                    "role": "system",
                    "content": "You are a medical AI assistant. Summarize patient information concisely.",
                },
                {
                    "role": "user",
                    "content": f"Summarize the following patient information:\n\n{profile_text}",
                },
            ],
            temperature=0.2,
            max_tokens=500,
        )
        return summary


class DocumentationService:
    @staticmethod
    def attach_document(
        db: Session,
        user_id: str,
        patient_id: str,
        filename: str,
        content_text: str,
    ) -> PatientFile:
        PatientService.get_by_id(db, patient_id, user_id)

        doc = PatientFile(
            patient_id=patient_id,
            filename=filename,
            content_text=content_text,
        )

        db.add(doc)
        db.commit()
        db.refresh(doc)
        return doc

    @staticmethod
    def list_documents(
        db: Session,
        user_id: str,
        patient_id: str,
    ) -> list[PatientFile]:
        PatientService.get_by_id(db, patient_id, user_id)

        stmt = select(PatientFile).where(PatientFile.patient_id == patient_id).order_by(
            PatientFile.created_at.desc()
        )
        return list(db.execute(stmt).scalars().all())

    @staticmethod
    def get_document(
        db: Session,
        user_id: str,
        patient_id: str,
        document_id: str,
    ) -> PatientFile:
        PatientService.get_by_id(db, patient_id, user_id)

        doc = db.get(PatientFile, document_id)
        if not doc or doc.patient_id != patient_id:
            raise HTTPException(status_code=404, detail="Document not found")

        return doc
