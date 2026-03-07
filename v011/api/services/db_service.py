from abc import ABC
from typing import TypeVar

from fastapi import Depends
from sqlalchemy import DateTime
from sqlalchemy.orm import Session
from v011.api import schemas
from v011.api.auth import get_db
from v011.api.models import Patient, PatientFile, PatientHistoryEntry, PatientHistoryEntry
from v011.api.services.ai_service import AIModelService

class DbServiceBase(ABC):
    def __init__(self) -> None:
        ai_service = AIModelService()
        self._ai_service = ai_service
        pass

class PatientService(DbServiceBase):
    
    @staticmethod
    def create_patient(db: Session,
                       user_id: str, 
                       patient_dto: schemas.PatientCreate) -> Patient:
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
    def list_patients(db: Session) -> list[Patient]:
        return db.query(Patient).scalar().all()
    
    @staticmethod
    def get_by_id(db: Session, patient_id: str) -> Patient | None:
        return db.get(Patient, patient_id)
    
    @staticmethod
    def add_history_record(db: Session, patient_id: str, kind: str, note: str, occurred_at: DateTime | None) -> PatientHistoryEntry:
        patient = PatientService.get_by_id(db, patient_id)
        if not patient:
            raise ValueError("Patient not found")
        
        entry = PatientHistoryEntry(
            patient_id=patient_id,
            kind=kind,
            note=note,
            occurred_at=occurred_at
        )
        
        db.add(entry)
        db.commit()
        db.refresh(entry)
        return entry
    
    @staticmethod
    def summarize_patient_profile(db: Session, patient_id: str) -> str:
        patient = PatientService.get_by_id(db, patient_id)
        if not patient:
            raise ValueError("Patient not found")
        
        files = db.query(PatientFile).filter(PatientFile.patient_id == patient_id).all()
        history = db.query(PatientHistoryEntry).filter(PatientHistoryEntry.patient_id == patient_id).all()
        
        profile_text = f"Patient {patient.first_name} {patient.last_name}, born on {patient.dob}, sex: {patient.sex}\n\n"
        
        summarization = "Summarize the following patient information:\n\n"
        summarization += profile_text
        if files:
            summarization += "Files:\n"
            for f in files:
                summarization += f"- {f.filename}: {f.content_text[:100]}...\n"
        if history:
            summarization += "History:\n"
            for h in history:
                summarization += f"- [{h.occurred_at}] {h.kind}: {h.note[:100]}...\n"
                
        json_schema = {
            "type": "object",
            "properties": {
                "summary": {"type": "string"}
            },
            "required": ["summary"]
        }
        
        
        
        
    
class DocumentationService(DbServiceBase):
    
    @staticmethod
    def attach_document(db: Session, patient_id: str, filename: str, content_text: str):
        doc = PatientFile(
            patient_id=patient_id,
            filename=filename,
            content_text=content_text
        )
        db.add(doc)
        db.commit()
        db.refresh(doc)
        return doc
