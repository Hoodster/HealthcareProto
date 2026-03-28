from fastapi import params
from pydantic.dataclasses import dataclass
from sqlalchemy import distinct, select, or_, and_
from sqlalchemy.orm import Session, selectinload, joinedload
from api import models
from typing import Optional, Any

def __get_heart_patients_query__(
    subject_id: Optional[int] = None,
    with_icu_stay: Optional[bool] = False
                                 ):
    
    # Base - select patients with eagerly loaded relationships
    statement = (
        select(models.MimicPatient)
        .join(models.MimicDiagnosisICD, models.MimicPatient.subject_id == models.MimicDiagnosisICD.subject_id)
        .join(models.MimicICDDiagnosisDefinition, models.MimicDiagnosisICD.icd9_code == models.MimicICDDiagnosisDefinition.icd9_code)
        .options(
            selectinload(models.MimicPatient.diagnoses).selectinload(models.MimicDiagnosisICD.icd_definition),
            selectinload(models.MimicPatient.admissions),
        )
    )
    
    if with_icu_stay:
        statement = statement.join(
            models.MimicICUStay,
            and_(
                models.MimicPatient.subject_id == models.MimicICUStay.subject_id,
                models.MimicDiagnosisICD.hadm_id == models.MimicICUStay.hadm_id
            )
        ).options(selectinload(models.MimicPatient.icustays))
    
    statement = statement.where(
        or_(
            models.MimicDiagnosisICD.icd9_code.like("426%"),
            models.MimicDiagnosisICD.icd9_code.like("428%"),
            models.MimicDiagnosisICD.icd9_code.in_(["42731", "42732", "4271", "2768"])
        )
    ).distinct().order_by(models.MimicPatient.subject_id)
    
    return statement

def get_all_patients(db: Session):
    result = db.query(models.MimicPatient).all()
    print(f"Retrieved {len(result)} patients from MIMIC-III")
    return result


def get_heart_patients(db: Session, subject_id: Optional[int] = None, with_icu_stay: bool = False):
    sql = __get_heart_patients_query__(subject_id, with_icu_stay)
    result = db.execute(sql)
    query_result = result.scalars().unique().all()
    
    # Convert to dictionaries with extended diagnosis information
    return [
        {
            "subject_id": p.subject_id,
            "gender": p.gender,
            "dob": p.dob,
            "dod": p.dod,
            "dod_hosp": p.dod_hosp,
            "dod_ssn": p.dod_ssn,
            "expire_flag": p.expire_flag,
            "diagnoses": [
                {
                    "icd9_code": d.icd9_code,
                    "seq_num": d.seq_num,
                    "hadm_id": d.hadm_id,
                    "diagnosis_definition": {
                        "short_title": d.icd_definition.short_title if d.icd_definition else None,
                        "long_title": d.icd_definition.long_title if d.icd_definition else None
                    } if hasattr(d, 'icd_definition') else None
                }
                for d in p.diagnoses
            ],
            "admissions": [
                {
                    "hadm_id": a.hadm_id,
                    "admittime": a.admittime,
                    "dischtime": a.dischtime,
                    "admission_type": a.admission_type,
                    "diagnosis": a.diagnosis
                }
                for a in p.admissions
            ] if hasattr(p, 'admissions') else [],
            "icustays": [
                {
                    "icustay_id": icu.icustay_id,
                    "intime": icu.intime,
                    "outtime": icu.outtime,
                    "first_careunit": icu.first_careunit,
                    "los": icu.los
                }
                for icu in p.icustays
            ] if with_icu_stay and hasattr(p, 'icustays') else []
        }
        for p in query_result
    ]
