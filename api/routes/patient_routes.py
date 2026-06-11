from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

import models.schemas as schema
from api.auth import HPCurrentUser, HPDbSession
from api.services.patient_service import PatientService


router = APIRouter(prefix="/patients", tags=["patients"])


def _authorize_patient(patient_id: str, user, db) -> None:
    patient = PatientService.get_by_id(db, patient_id)
    if not user.staff and patient.user_id != user.id:
        raise HTTPException(status_code=403, detail="Not authorized for this patient")


@router.get("", response_model=list[schema.PatientOut])
def list_patients(db: HPDbSession, user: HPCurrentUser):
    if user.staff:
        patients = PatientService.list_patients(db)
    else:
        patients = PatientService.list_patients(db, user_id=user.id)
    return [PatientService.patient_to_out(db, p) for p in patients]


@router.get("/{patient_id}", response_model=schema.PatientDetailOut)
def get_patient(
    patient_id: str,
    db: HPDbSession,
    user: HPCurrentUser,
):
    """Return patient profile and resolved clinical context (MIMIC-linked or manual history)."""
    _authorize_patient(patient_id, user, db)
    return PatientService.get_patient_detail(db, patient_id)


@router.put("/{patient_id}/mimic", response_model=schema.PatientOut)
def assign_mimic_patient(
    patient_id: str,
    payload: schema.MimicLinkIn,
    db: HPDbSession,
    user: HPCurrentUser,
):
    """Link an app patient profile to a MIMIC-III subject/admission."""
    _authorize_patient(patient_id, user, db)
    try:
        patient = PatientService.assign_mimic(
            db, patient_id, payload.subject_id, payload.hadm_id
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return PatientService.patient_to_out(db, patient)


@router.delete("/{patient_id}/mimic", response_model=schema.PatientOut)
def unassign_mimic_patient(
    patient_id: str,
    db: HPDbSession,
    user: HPCurrentUser,
):
    """Remove MIMIC-III link from a patient profile."""
    _authorize_patient(patient_id, user, db)
    patient = PatientService.unassign_mimic(db, patient_id)
    return PatientService.patient_to_out(db, patient)


@router.post("/{patient_id}/history", response_model=schema.PatientHistoryOut)
def add_history_entry(
    patient_id: str,
    payload: schema.PatientHistoryCreate,
    db: HPDbSession,
    user: HPCurrentUser,
):
    _authorize_patient(patient_id, user, db)
    return PatientService.add_history_record(
        db, patient_id, payload.kind, payload.note, payload.occurred_at
    )


@router.get("/{patient_id}/history", response_model=list[schema.PatientHistoryOut])
def list_history(
    patient_id: str,
    db: HPDbSession,
    user: HPCurrentUser,
    kind: str | None = Query(default=None),
):
    _authorize_patient(patient_id, user, db)
    return PatientService.list_history(db, patient_id, kind=kind)
