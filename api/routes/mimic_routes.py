from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from api.services.mimic_service import get_heart_patients, get_all_patients
import models.schemas as schemas
from api.services.dummy_service import DummyService
from api.auth import get_db


router = APIRouter(prefix="/mimic", tags=["mimic"])


@router.post("/test")
def create_chat(
    db: Session = Depends(get_db),
):
    return get_all_patients(db)

@router.get("")
def get_mimic(
    db: Session = Depends(get_db),
    subject_id: int | None = None,
    with_icu_stay: bool = True
):
    return get_heart_patients(db, subject_id, with_icu_stay)