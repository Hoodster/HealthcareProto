from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from v011.api import schemas
from v011.api.auth import get_current_user, get_db
from v011.api.models import Patient, PatientFile, PatientHistoryEntry, User


router = APIRouter(prefix="/patients", tags=["patients"])


@router.post("", response_model=schemas.PatientOut)
def create_patient(
    payload: schemas.PatientCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    patient = Patient(
        owner_user_id=user.id,
        first_name=payload.first_name,
        last_name=payload.last_name,
        dob=payload.dob,
        sex=payload.sex,
    )
    db.add(patient)
    db.commit()
    db.refresh(patient)
    return patient


@router.get("", response_model=list[schemas.PatientOut])
def list_patients(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    stmt = select(Patient).where(Patient.owner_user_id == user.id).order_by(Patient.created_at.desc())
    return list(db.execute(stmt).scalars().all())


def _get_patient(db: Session, user: User, patient_id: int) -> Patient:
    patient = db.get(Patient, patient_id)
    if not patient or patient.owner_user_id != user.id:
        raise HTTPException(status_code=404, detail="Patient not found")
    return patient


@router.get("/{patient_id}", response_model=schemas.PatientOut)
def get_patient(patient_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return _get_patient(db, user, patient_id)


@router.post("/{patient_id}/files", response_model=schemas.PatientFileOut)
def add_patient_file(
    patient_id: int,
    payload: schemas.PatientFileCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    patient = _get_patient(db, user, patient_id)
    pf = PatientFile(patient_id=patient.id, filename=payload.filename, content_text=payload.content_text)
    db.add(pf)
    db.commit()
    db.refresh(pf)
    return pf


@router.get("/{patient_id}/files", response_model=list[schemas.PatientFileOut])
def list_patient_files(patient_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    patient = _get_patient(db, user, patient_id)
    stmt = select(PatientFile).where(PatientFile.patient_id == patient.id).order_by(PatientFile.created_at.desc())
    return list(db.execute(stmt).scalars().all())


@router.post("/{patient_id}/history", response_model=schemas.PatientHistoryOut)
def add_history_entry(
    patient_id: int,
    payload: schemas.PatientHistoryCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    patient = _get_patient(db, user, patient_id)
    entry = PatientHistoryEntry(
        patient_id=patient.id,
        kind=payload.kind,
        note=payload.note,
        occurred_at=payload.occurred_at,
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry


@router.get("/{patient_id}/history", response_model=list[schemas.PatientHistoryOut])
def list_history(patient_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    patient = _get_patient(db, user, patient_id)
    stmt = (
        select(PatientHistoryEntry)
        .where(PatientHistoryEntry.patient_id == patient.id)
        .order_by(PatientHistoryEntry.created_at.desc())
    )
    return list(db.execute(stmt).scalars().all())
