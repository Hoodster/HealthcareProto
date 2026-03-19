from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session


import api.schemas as schema
from api.auth import get_current_user, get_db
from api.models import PatientHistoryEntry, User
from api.services.db_service import PatientService


router = APIRouter(prefix="/patients", tags=["patients"])


@router.post("", response_model=schema.PatientOut)
def create_patient(
    payload: schema.PatientCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return PatientService.create_patient(db, user.id, payload)

@router.get("", response_model=list[schema.PatientOut])
def list_patients(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return PatientService.list_patients(db)


@router.get("/{patient_id}", response_model=schema.PatientOut)
def get_patient(patient_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return PatientService.get_by_id(db, patient_id, user.id)


@router.post("/{patient_id}/files", response_model=schema.PatientFileOut)
def add_patient_file(
    patient_id: str,
    payload: schema.PatientFileCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    from api.services.db_service import DocumentationService
    return DocumentationService.attach_document(
        db, user.id, patient_id, payload.filename, payload.content_text
    )


@router.get("/{patient_id}/files", response_model=list[schema.PatientFileOut])
def list_patient_files(patient_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    from api.services.db_service import DocumentationService
    return DocumentationService.list_documents(db, user.id, patient_id)


@router.post("/{patient_id}/history", response_model=schema.PatientHistoryOut)
def add_history_entry(
    patient_id: str,
    payload: schema.PatientHistoryCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return PatientService.add_history_record(
        db, user.id, patient_id, payload.kind, payload.note, payload.occurred_at
    )


@router.get("/{patient_id}/history", response_model=list[schema.PatientHistoryOut])
def list_history(patient_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    # Verify ownership
    PatientService.get_by_id(db, patient_id, user.id)
    stmt = (
        select(PatientHistoryEntry)
        .where(PatientHistoryEntry.patient_id == patient_id)
        .order_by(PatientHistoryEntry.created_at.desc())
    )
    return list(db.execute(stmt).scalars().all())

@router.get("/{patient_id}/visits", response_model=list[schema.PatientHistoryOut])
def list_visits(patient_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    # Verify ownership
    PatientService.get_by_id(db, patient_id, user.id)
    stmt = (
        select(PatientHistoryEntry)
        .where(PatientHistoryEntry.patient_id == patient_id, PatientHistoryEntry.kind == "visit")
        .order_by(PatientHistoryEntry.created_at.desc())
    )
    return list(db.execute(stmt).scalars().all())
