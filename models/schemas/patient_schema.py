from typing import Literal

from pydantic import BaseModel
import datetime as dt

PatientSex = Literal["male", "female"]


class MimicLinkIn(BaseModel):
    subject_id: int
    hadm_id: int


class PatientOut(BaseModel):
    patient_id: str
    user_id: str | None
    dob: dt.date | None
    sex: PatientSex | None
    mimic_subject_id: int | None = None
    mimic_hadm_id: int | None = None
    mimic_primary_diagnosis: str | None = None
    
    model_config = {
        "from_attributes": True
    }


class PatientDetailOut(BaseModel):
    """Patient profile plus resolved clinical context (MIMIC-linked or manual history)."""
    patient: PatientOut
    context: dict


class PatientCreate(BaseModel):
    user_id: str | None = None
    dob: dt.date | None = None
    sex: PatientSex | None = None


class PatientFileCreate(BaseModel):
    filename: str
    content_text: str


class PatientFileOut(BaseModel):
    id: str
    filename: str
    content_text: str
    created_at: dt.datetime


class PatientHistoryCreate(BaseModel):
    kind: str
    note: str
    occurred_at: dt.datetime | None = None


class PatientHistoryOut(BaseModel):
    id: int
    kind: str
    note: str
    occurred_at: dt.datetime | None
    created_at: dt.datetime
    
    model_config = {
        "from_attributes": True
    }


class DocumentProcessOut(BaseModel):
    doc_id: int
    patient_id: str
    filename: str
    entries_created: int
    entries: list[PatientHistoryOut]
