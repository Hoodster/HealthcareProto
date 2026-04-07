from __future__ import annotations

import re
from datetime import datetime, date

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from api.auth import HPCurrentUser, HPDbSession
import models.schemas as schemas
from api.models import Patient, PatientFile, PatientHistoryEntry, User
from api.services.ai_service import AIModelService

_QTC_RE = re.compile(r'\bqtc\s*[=:]\s*(\d+(?:\.\d+)?)', re.IGNORECASE)
_EGFR_RE = re.compile(r'\begfr\s*[=:]\s*(\d+(?:\.\d+)?)', re.IGNORECASE)
_DOSE_RE = re.compile(r'\b\d+(?:\.\d+)?\s*(?:mg|mcg|g|ml|iu)\b', re.IGNORECASE)

_PRESCRIPTION_KINDS = {'prescription', 'medication_change', 'anticoagulation'}
_CONDITION_KINDS = {'diagnosis', 'symptom', 'episode_af', 'health_history'}
_ECG_KINDS = {'diagnostic_ecg', 'diagnostic_holter'}


class PatientService:
    @staticmethod
    def create_patient_profile(
        db: Session,
        patient_dto: schemas.PatientCreate,
    ) -> Patient:
        patient = Patient(
            user_id=patient_dto.user_id,
            dob=patient_dto.dob,
            sex=patient_dto.sex,
        )
        db.add(patient)
        db.commit()
        db.refresh(patient)
        return patient

    @staticmethod
    def list_patients(db: Session, user_id: str) -> list[Patient]:
        stmt = select(Patient).where(Patient.user_id == user_id)
        return list(db.execute(stmt).scalars().all())

    @staticmethod
    def get_by_id(db: Session, patient_id: str) -> Patient:
        patient = db.get(Patient, patient_id)
        if not patient:
            raise HTTPException(status_code=404, detail="Patient not found")
        return patient

    @staticmethod
    def add_history_record(
        db: Session,
        patient_id: str,
        kind: str,
        note: str,
        occurred_at: datetime | None = None,
    ) -> PatientHistoryEntry:
        PatientService.get_by_id(db, patient_id)

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
        patient_id: str,
        *,
        kind: str | None = None,
    ) -> list[PatientHistoryEntry]:
        PatientService.get_by_id(db, patient_id)

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
    def summarize_patient_profile(db: Session, patient_id: str) -> str:
        patient = PatientService.get_by_id(db, patient_id)

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
            f"Patient data:"
            f"age {date.today().year - patient.dob.year if patient.dob else 'unknown'}, sex: {patient.sex}\n\n"
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

        ai_service = AIModelService()
        return ai_service.summarize(profile_text)

    @staticmethod
    def build_patient_context(patient_id: str, db: Session):
        """Build a PatientContext for the expert system from the patient's DB records."""
        from expert_system.models.patient_context import PatientContext

        patient = db.get(Patient, patient_id)
        if not patient:
            raise HTTPException(status_code=404, detail="Patient not found")

        # Age from dob
        age: int | None = None
        if patient.dob:
            today = date.today()
            age = today.year - patient.dob.year - (
                (today.month, today.day) < (patient.dob.month, patient.dob.day)
            )

        # Normalise sex → M/F/Other
        gender: str | None = None
        if patient.sex:
            s = patient.sex.strip().lower()
            if s in ('m', 'male', 'mężczyzna', 'mezczyzna'):
                gender = 'M'
            elif s in ('f', 'female', 'k', 'kobieta'):
                gender = 'F'
            else:
                gender = patient.sex

        # Fetch history entries newest first
        stmt = (
            select(PatientHistoryEntry)
            .where(PatientHistoryEntry.patient_id == patient_id)
            .order_by(PatientHistoryEntry.occurred_at.desc(), PatientHistoryEntry.created_at.desc())
        )
        entries = list(db.execute(stmt).scalars().all())

        qtc = 420.0
        egfr = 90.0
        medications: list[str] = []
        conditions: list[str] = []

        for entry in entries:
            kind = entry.kind
            note = (entry.note or "").strip()

            if kind == 'lab_result':
                m = _EGFR_RE.search(note)
                if m and egfr == 90.0:
                    egfr = float(m.group(1))
                m2 = _QTC_RE.search(note)
                if m2 and qtc == 420.0:
                    qtc = float(m2.group(1))

            elif kind in _ECG_KINDS:
                m = _QTC_RE.search(note)
                if m and qtc == 420.0:
                    qtc = float(m.group(1))

            elif kind in _PRESCRIPTION_KINDS:
                # Strip dosage info and take the first token as the drug name
                cleaned = _DOSE_RE.sub('', note).strip()
                drug = cleaned.split()[0].lower() if cleaned else None
                if drug and drug not in medications:
                    medications.append(drug)

            elif kind in _CONDITION_KINDS:
                cond = note.lower()
                if cond and cond not in conditions:
                    conditions.append(cond)

        return PatientContext(
            patient_id=patient_id,
            qtc=qtc,
            egfr=egfr,
            medications=medications,
            conditions=conditions,
            age=age,
            gender=gender,
            weight=None,
        )
        
    @staticmethod
    def delete_all_patients(db: Session, user: User | None = None):
        """Delete all patient records"""
        if not user or not user.staff or not user.staff.role == 'admin':
            raise HTTPException(status_code=403, detail="Admin privileges required")
        db.query(Patient).delete()
        db.commit()


class DocumentationService:
    @staticmethod
    def attach_document(
        db: Session,
        patient_id: str,
        filename: str,
        content_text: str,
    ) -> PatientFile:
        PatientService.get_by_id(db, patient_id)

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
        patient_id: str,
    ) -> list[PatientFile]:
        PatientService.get_by_id(db, patient_id)

        stmt = select(PatientFile).where(PatientFile.patient_id == patient_id).order_by(
            PatientFile.created_at.desc()
        )
        return list(db.execute(stmt).scalars().all())

    @staticmethod
    def get_document(
        db: Session,
        patient_id: str,
        document_id: str,
    ) -> PatientFile:
        PatientService.get_by_id(db, patient_id)

        doc = db.get(PatientFile, document_id)
        if not doc or doc.patient_id != patient_id:
            raise HTTPException(status_code=404, detail="Document not found")

        return doc