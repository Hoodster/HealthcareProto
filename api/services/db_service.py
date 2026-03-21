from abc import ABC
from datetime import datetime
from typing import Optional

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

import models.schemas as schemas
from api.models import Patient, PatientFile, PatientHistoryEntry
from api.services.ai_service import AIModelService


class DbServiceBase(ABC):
    def __init__(self) -> None:
        self._ai_service = AIModelService()


class PatientService(DbServiceBase):
    
    @staticmethod
    def create_patient(
        db: Session,
        user_id: str, 
        patient_dto: schemas.PatientCreate
    ) -> Patient:
        """Create a new patient"""
        patient = Patient(
            user_id=user_id,
            first_name=patient_dto.first_name,
            last_name=patient_dto.last_name,
            dob=patient_dto.dob,
            sex=patient_dto.sex
        )
        db.add(patient)
        db.commit()
        db.refresh(patient)
        return patient
    
    @staticmethod
    def list_patients(db: Session, user_id: str) -> list[Patient]:
        """List all patients for a user"""
        stmt = select(Patient).where(Patient.user_id == user_id).order_by(
            Patient.created_at.desc()
        )
        return list(db.execute(stmt).scalars().all())
    
    @staticmethod
    def get_by_id(db: Session, patient_id: str, user_id: str) -> Patient:
        """Get patient by ID with ownership check"""
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
        occurred_at: Optional[datetime] = None
    ) -> PatientHistoryEntry:
        """Add history entry with ownership verification"""
        # Verify patient exists and belongs to user
        patient = PatientService.get_by_id(db, patient_id, user_id)
        
        entry = PatientHistoryEntry(
            patient_id=patient_id,
            kind=kind,
            note=note,
            occurred_at=occurred_at or datetime.utcnow()
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
        """List patient history entries with optional kind filtering"""
        PatientService.get_by_id(db, patient_id, user_id)

        stmt = select(PatientHistoryEntry).where(
            PatientHistoryEntry.patient_id == patient_id
        )
        if kind is not None:
            stmt = stmt.where(PatientHistoryEntry.kind == kind)

        stmt = stmt.order_by(PatientHistoryEntry.created_at.desc())
        return list(db.execute(stmt).scalars().all())
    
    @staticmethod
    def summarize_patient_profile(db: Session, patient_id: str, user_id: str) -> str:
        """Generate AI summary of patient profile"""
        # Verify ownership
        patient = PatientService.get_by_id(db, patient_id, user_id)
        
        # Get related data
        files = db.query(PatientFile).filter(
            PatientFile.patient_id == patient_id
        ).all()
        
        history = db.query(PatientHistoryEntry).filter(
            PatientHistoryEntry.patient_id == patient_id
        ).order_by(PatientHistoryEntry.occurred_at.desc()).limit(50).all()
        
        # Build context
        profile_text = f"Patient {patient.first_name} {patient.last_name}, born on {patient.dob}, sex: {patient.sex}\n\n"
        
        if files:
            profile_text += "Files:\n"
            for f in files:
                content_preview = f.content_text[:100] if f.content_text else "No content"
                profile_text += f"- {f.filename}: {content_preview}...\n"
        
        if history:
            profile_text += "\nHistory:\n"
            for h in history:
                note_preview = h.note[:100] if h.note else ""
                profile_text += f"- [{h.occurred_at}] {h.kind}: {note_preview}...\n"
        
        # Create AI service and generate summary
        ai_service = AIModelService()
        
        messages = [
            {
                "role": "system",
                "content": "You are a medical AI assistant. Summarize patient information concisely."
            },
            {
                "role": "user",
                "content": f"Summarize the following patient information:\n\n{profile_text}"
            }
        ]
        
        summary = ai_service.chat(
            messages=messages,
            temperature=0.2,
            max_tokens=500
        )
        
        return summary


class DocumentationService(DbServiceBase):
    
    @staticmethod
    def attach_document(
        db: Session, 
        user_id: str,
        patient_id: str, 
        filename: str, 
        content_text: str
    ) -> PatientFile:
        """Attach document to patient with ownership verification"""
        # Verify patient exists and belongs to user
        patient = PatientService.get_by_id(db, patient_id, user_id)
        
        doc = PatientFile(
            patient_id=patient_id,
            filename=filename,
            content_text=content_text
        )
        
        db.add(doc)
        db.commit()
        db.refresh(doc)
        return doc
    
    @staticmethod
    def list_documents(
        db: Session,
        user_id: str,
        patient_id: str
    ) -> list[PatientFile]:
        """List all documents for a patient"""
        # Verify ownership
        patient = PatientService.get_by_id(db, patient_id, user_id)
        
        return db.query(PatientFile).filter(
            PatientFile.patient_id == patient_id
        ).order_by(PatientFile.created_at.desc()).all()
    
    @staticmethod
    def get_document(
        db: Session,
        user_id: str,
        patient_id: str,
        document_id: str
    ) -> PatientFile:
        """Get specific document with ownership verification"""
        # Verify patient ownership
        patient = PatientService.get_by_id(db, patient_id, user_id)
        
        doc = db.get(PatientFile, document_id)
        if not doc or doc.patient_id != patient_id:
            raise HTTPException(status_code=404, detail="Document not found")
        
        return doc
