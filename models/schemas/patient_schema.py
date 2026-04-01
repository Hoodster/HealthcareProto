from typing import Literal

from pydantic import BaseModel
import datetime as dt

PatientSex = Literal["male", "female"]


class PatientCreate(BaseModel):
    first_name: str
    last_name: str
    dob: dt.date | None = None
    sex: PatientSex


class PatientOut(BaseModel):
    id: str
    first_name: str
    last_name: str
    dob: dt.date | None
    sex: PatientSex | None
    created_at: dt.datetime

    class Config:
        from_attributes = True


class PatientFileCreate(BaseModel):
    filename: str
    content_text: str


class PatientFileOut(BaseModel):
    id: str
    filename: str
    content_text: str
    created_at: dt.datetime

    class Config:
        from_attributes = True


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

    class Config:
        from_attributes = True
