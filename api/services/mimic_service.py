from fastapi import params
from pydantic.dataclasses import dataclass
from sqlalchemy import distinct, select, or_, and_
from sqlalchemy.orm import Session, selectinload, joinedload
from api import models
from typing import Optional, Any

CREATININE_ITEMID = 50912  # MIMIC-III d_labitems: Creatinine (Blood)

# Minimal ICD-9 → human-readable condition mapping for conditions we care about
_ICD9_CONDITIONS: dict[str, str] = {
    "42731": "atrial fibrillation",
    "42732": "atrial flutter",
    "4271": "paroxysmal atrial tachycardia",
    "4280": "congestive heart failure - unspecified",
    "4281": "left heart failure",
    "4289": "heart failure - other",
    "4260": "atrioventricular block - complete",
    "4261": "atrioventricular block - other",
    "42613": "atrioventricular block - other",
    "42610": "atrioventricular block - complete",
    "4262": "left bundle-branch block",
    "4263": "right bundle-branch block",
    "2768": "hyperpotassemia",
}

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


# ============================================================================
# MIMIC-III PatientContext builder (Phase 6 — MIMIC validation)
# ============================================================================

def get_patient_prescriptions(subject_id: int, hadm_id: int, db: Session) -> list[str]:
    """Return a deduplicated list of generic drug names prescribed during an admission."""
    stmt = (
        select(models.MimicPrescription.drug_name_generic)
        .where(
            models.MimicPrescription.subject_id == subject_id,
            models.MimicPrescription.hadm_id == hadm_id,
            models.MimicPrescription.drug_name_generic.isnot(None),
        )
        .distinct()
    )
    rows = db.execute(stmt).scalars().all()
    return [r.strip().lower() for r in rows if r and r.strip()]


def get_lab_creatinine(subject_id: int, hadm_id: int, db: Session) -> Optional[float]:
    """Return the most recent creatinine (itemid=50912) value for an admission, or None."""
    stmt = (
        select(models.MimicLabEvent.valuenum)
        .where(
            models.MimicLabEvent.subject_id == subject_id,
            models.MimicLabEvent.hadm_id == hadm_id,
            models.MimicLabEvent.itemid == CREATININE_ITEMID,
            models.MimicLabEvent.valuenum.isnot(None),
        )
        .order_by(models.MimicLabEvent.charttime.desc())
        .limit(1)
    )
    return db.execute(stmt).scalar_one_or_none()


def _mdrd_egfr(creatinine: float, age: int, gender: str) -> float:
    """
    Simplified MDRD formula for eGFR estimation.
    eGFR = 186 × (Cr)^-1.154 × (Age)^-0.203 × [0.742 if female]
    """
    if creatinine <= 0 or age <= 0:
        return 90.0
    egfr = 186.0 * (creatinine ** -1.154) * (age ** -0.203)
    if gender and gender.upper() == 'F':
        egfr *= 0.742
    return round(egfr, 1)


def build_mimic_patient_context(subject_id: int, hadm_id: int, db: Session):
    """
    Build a PatientContext from MIMIC-III data for use with the expert system.

    Sources:
    - medications: MimicPrescription.drug_name_generic
    - eGFR: derived from last creatinine (itemid=50912) via MDRD formula
    - QTc: fallback 420 ms (no ECG events in MIMIC model)
    - conditions: ICD-9 diagnoses mapped to human-readable strings
    - age: patients.dob vs admissions.admittime
    """
    from expert_system.models.patient_context import PatientContext

    # Load patient + admission
    patient = db.get(models.MimicPatient, subject_id)
    if patient is None:
        raise ValueError(f"MIMIC patient {subject_id} not found")
    admission = db.get(models.MimicAdmission, hadm_id)
    if admission is None:
        raise ValueError(f"MIMIC admission {hadm_id} not found")

    # Age
    age: Optional[int] = None
    if patient.dob and admission.admittime:
        delta = admission.admittime - patient.dob
        age = max(0, int(delta.days / 365.25))
        # MIMIC shifts DOB by ~300 yr for patients >=89 — clamp to reasonable range
        if age > 120:
            age = 91

    # Gender
    gender: Optional[str] = None
    if patient.gender:
        gender = patient.gender.upper()  # 'M' or 'F'

    # Medications
    medications = get_patient_prescriptions(subject_id, hadm_id, db)

    # eGFR via MDRD
    creatinine = get_lab_creatinine(subject_id, hadm_id, db)
    if creatinine is not None and age:
        egfr = _mdrd_egfr(creatinine, age, gender or 'M')
    else:
        egfr = 90.0

    # Conditions from ICD-9
    stmt_diag = (
        select(models.MimicDiagnosisICD.icd9_code)
        .where(
            models.MimicDiagnosisICD.subject_id == subject_id,
            models.MimicDiagnosisICD.hadm_id == hadm_id,
            models.MimicDiagnosisICD.icd9_code.isnot(None),
        )
    )
    icd_codes = db.execute(stmt_diag).scalars().all()
    conditions: list[str] = []
    for code in icd_codes:
        if not code:
            continue
        mapped = _ICD9_CONDITIONS.get(code)
        if mapped and mapped not in conditions:
            conditions.append(mapped)
        elif not mapped:
            # Use raw code as fallback so rules can still pattern-match
            label = f"icd9:{code}"
            if label not in conditions:
                conditions.append(label)

    return PatientContext(
        patient_id=f"MIMIC_{subject_id}_{hadm_id}",
        qtc=420.0,  # placeholder — no ECG chartevents in current model
        egfr=egfr,
        medications=medications,
        conditions=conditions,
        age=age,
        gender=gender,
        weight=60.0,  # todo: placeholder — weight chartevents are sparse and noisy
    )

