from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session


from api.db import get_db_session
import models.schemas as schema
from api.auth import HPDbSession, get_current_user
from api.models import User
from api.services.patient_service import DocumentationService, PatientService
from api.services.chat_service import ChatService


router = APIRouter(prefix="/patients", tags=["patients"])


@router.post("", response_model=schema.PatientOut)
def create_patient(
    payload: schema.PatientCreate,
    db: HPDbSession
):
    return PatientService.create_patient_profile(db, payload)


@router.get("", response_model=list[schema.PatientOut])
def list_patients(db: Session = Depends(get_db_session), user: User = Depends(get_current_user)):
    return PatientService.list_patients(db, user.id)


@router.get("/{patient_id}", response_model=schema.PatientOut)
def get_patient(patient_id: str, db: Session = Depends(get_db_session), user: User = Depends(get_current_user)):
    return PatientService.get_by_id(db, patient_id)


@router.post("/{patient_id}/files", response_model=schema.PatientFileOut)
def add_patient_file(
    patient_id: str,
    payload: schema.PatientFileCreate,
    db: Session = Depends(get_db_session),
    user: User = Depends(get_current_user),
):
    return DocumentationService.attach_document(
        db, patient_id, payload.filename, payload.content_text
    )


@router.get("/{patient_id}/files", response_model=list[schema.PatientFileOut])
def list_patient_files(patient_id: str, db: Session = Depends(get_db_session), user: User = Depends(get_current_user)):
    return DocumentationService.list_documents(db, patient_id)


@router.post("/{patient_id}/history", response_model=schema.PatientHistoryOut)
def add_history_entry(
    patient_id: str,
    payload: schema.PatientHistoryCreate,
    db: Session = Depends(get_db_session),
    user: User = Depends(get_current_user),
):
    return PatientService.add_history_record(
        db, patient_id, payload.kind, payload.note, payload.occurred_at
    )


@router.get("/{patient_id}/history", response_model=list[schema.PatientHistoryOut])
def list_history(
    patient_id: str,
    kind: str | None = Query(default=None),
    db: Session = Depends(get_db_session),
):
    return PatientService.list_history(db, patient_id, kind=kind)



@router.get("/{patient_id}/context")
def get_patient_context(
    patient_id: str,
    db: Session = Depends(get_db_session),
    user: User = Depends(get_current_user),
):
    """Return the PatientContext as built from the patient's history records."""
    PatientService.get_by_id(db, patient_id)  # authorization check
    ctx = PatientService.build_patient_context(patient_id, db)
    return ctx.model_dump()


@router.delete("/patients")
def delete_all_patients(db: Session = Depends(get_db_session)):
    """Dangerous endpoint to delete all patient records - for testing purposes."""
    PatientService.delete_all_patients(db)
    return {"detail": "All patients deleted"}
