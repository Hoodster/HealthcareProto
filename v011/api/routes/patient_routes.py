from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session


import v011.api.schemas as schema
from v011.api.auth import get_current_user, get_db
from v011.api.models import Patient, PatientFile, PatientHistoryEntry, User
from v011.api.schemas.patient_schema import PatientCreate
from v011.api.services.db_service import PatientService


router = APIRouter(prefix="/patients", tags=["patients"])


@router.post("", response_model=Patient)
def create_patient(
    payload: schema.PatientCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return PatientService.create_patient(db, user.id, payload)

@router.get("", response_model=list[schema.PatientOut])
def list_patients(db: Session = Depends(get_db)):
    return PatientService.list_patients(db)


@router.get("/{patient_id}", response_model=schema.PatientOut)
def get_patient(patient_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return PatientService.get_by_id(db, patient_id)


@router.post("/{patient_id}/files", response_model=schema.PatientFileOut)
def add_patient_file(
    patient_id: str,
    payload: schema.PatientFileCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    patient = PatientService.get_by_id(db, patient_id)
    pf = PatientFile(patient_id='', filename=payload.filename, content_text=payload.content_text)
    db.add(pf)
    db.commit()
    db.refresh(pf)
    return pf


@router.get("/{patient_id}/files", response_model=list[schema.PatientFileOut])
def list_patient_files(patient_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    patient = PatientService.get_by_id(db, patient_id)
    stmt = select(PatientFile).where(PatientFile.patient_id == patient_id).order_by(PatientFile.created_at.desc())
    return list(db.execute(stmt).scalars().all())


@router.post("/{patient_id}/history", response_model=schema.PatientHistoryOut)
def add_history_entry(
    patient_id: str,
    payload: schema.PatientHistoryCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    patient = PatientService.get_by_id(db, patient_id)
    entry = PatientHistoryEntry(
        patient_id='',
        kind=payload.kind,
        note=payload.note,
        occurred_at=payload.occurred_at,
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry


@router.get("/{patient_id}/history", response_model=list[schema.PatientHistoryOut])
def list_history(patient_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    patient = PatientService.get_by_id(db, patient_id)
    stmt = (
        select(PatientHistoryEntry)
        .where(PatientHistoryEntry.patient_id == patient_id)
        .order_by(PatientHistoryEntry.created_at.desc())
    )
    return list(db.execute(stmt).scalars().all())

@router.get("/{patient_id}/visits", response_model=list[schema.PatientHistoryOut])
def list_visits(patient_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    stmt = (
        select(PatientHistoryEntry)
        .where(PatientHistoryEntry.patient_id == patient_id, PatientHistoryEntry.kind == "visit")
        .order_by(PatientHistoryEntry.created_at.desc())
    )
    return list(db.execute(stmt).scalars().all())
