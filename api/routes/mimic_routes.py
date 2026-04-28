from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from api.auth import get_current_user
from api.db import get_db_session
from api.services.mimic_service import get_heart_patients, get_all_patients, build_mimic_patient_context
from models.schemas.pipeline_schema import CardiacPatientSummary
from api import models
from datetime import datetime


router = APIRouter(prefix="/mimic", tags=["mimic"], dependencies=[Depends(get_current_user)])


@router.post("/test")
def create_chat(
    db: Session = Depends(get_db_session),
):
    return get_all_patients(db)

@router.get("")
def get_mimic(
    db: Session = Depends(get_db_session),
    subject_id: int | None = None,
    with_icu_stay: bool = True
):
    return get_heart_patients(db, subject_id, with_icu_stay)


@router.get("/patient-context/{subject_id}/{hadm_id}")
def get_mimic_patient_context(
    subject_id: int,
    hadm_id: int,
    db: Session = Depends(get_db_session),
):
    """Build and return the PatientContext derived from MIMIC-III data for a given admission."""
    ctx = build_mimic_patient_context(subject_id, hadm_id, db)
    return ctx.model_dump()


@router.post("/benchmark")
def run_mimic_benchmark(
    n_patients: int = Query(default=20, ge=1, le=200),
    modes: list[str] = Query(default=["expert_only", "llm_only", "full_pipeline"]),
    db: Session = Depends(get_db_session),
):
    """
    Run A/B/C benchmark on real MIMIC-III AFib patients.

    Ground-truth proxy:
    - If a patient has ≥2 QT-prolonging drugs simultaneously → expected CRITICAL alert (interaction)
    - If eGFR < 60 → expected dose adjustment
    """
    from api.benchmarks.benchmark_runner import BenchmarkRunner, BenchmarkCase
    from expert_system.rules.interaction_rules import QT_PROLONGING_DRUGS

    # Get AFib/AFlutter patients
    patients_raw = get_heart_patients(db, with_icu_stay=False)

    cases: list[BenchmarkCase] = []
    for p in patients_raw[:n_patients * 3]:  # fetch extra to filter
        subject_id = p["subject_id"]
        admissions = p.get("admissions", [])
        if not admissions:
            continue
        hadm_id = admissions[0]["hadm_id"]
        if hadm_id is None:
            continue

        try:
            patient_ctx = build_mimic_patient_context(subject_id, hadm_id, db)
        except Exception:
            continue

        # Build proxy ground truth
        qt_meds = {m for m in patient_ctx.medications if m in QT_PROLONGING_DRUGS}
        expected_alert_categories = []
        if len(qt_meds) >= 2:
            expected_alert_categories.append("interaction")
        if patient_ctx.egfr < 60:
            expected_alert_categories.append("renal")

        gt = {
            "expected_contraindicated": False,
            "expected_alert_categories": expected_alert_categories,
            "expected_dose_adjustment": patient_ctx.egfr < 60,
        }

        cases.append(BenchmarkCase(
            case_id=f"MIMIC_{subject_id}_{hadm_id}",
            description=f"MIMIC patient {subject_id} admission {hadm_id}",
            patient=patient_ctx,
            question="Assess drug safety and any contraindications for this cardiac patient.",
            ground_truth=gt,
        ))

        if len(cases) >= n_patients:
            break

    if not cases:
        return {"error": "No MIMIC patients with prescription data found"}

    runner = BenchmarkRunner()
    report = runner.compare(cases, modes=["expert_only", "llm_only", "full_pipeline"])
    return report


@router.get("/cardiac-patients", response_model=list[CardiacPatientSummary])
def get_cardiac_patients_summary(
    limit: int = Query(default=50, ge=1, le=500),
    with_prescriptions: bool = Query(default=True, description="Filter patients with prescriptions"),
    db: Session = Depends(get_db_session),
):
    """
    Get a summary list of cardiac patients suitable for pipeline evaluation.
    
    Returns patient summaries with:
    - Basic demographics (gender, age)
    - Admission details (hadm_id)
    - Diagnosis count and primary cardiac diagnosis
    - Hospital mortality flag
    - Whether patient has prescription data
    
    This endpoint is designed for batch evaluation scripts to discover
    which patients are available for testing.
    
    Args:
        limit: Maximum number of patients to return (default: 50)
        with_prescriptions: Only include patients with prescription data (default: true)
        
    Returns:
        List of CardiacPatientSummary objects
    """
    # Get heart patients from service
    patients_raw = get_heart_patients(db, with_icu_stay=False)
    
    summaries = []
    for p in patients_raw:
        subject_id = p["subject_id"]
        admissions = p.get("admissions", [])
        
        if not admissions:
            continue
        
        # Use first admission for simplicity
        admission = admissions[0]
        hadm_id = admission.get("hadm_id")
        
        if hadm_id is None:
            continue
        
        # Check if patient has prescriptions (if filtering enabled)
        if with_prescriptions:
            prescription_count = db.query(models.MimicPrescription).filter(
                models.MimicPrescription.subject_id == subject_id,
                models.MimicPrescription.hadm_id == hadm_id
            ).count()
            
            if prescription_count == 0:
                continue
        
        # Calculate age from admission time and DOB
        age = None
        if p.get("dob") and admission.get("admittime"):
            dob = p["dob"]
            admittime = admission["admittime"]
            if isinstance(dob, datetime) and isinstance(admittime, datetime):
                age = (admittime - dob).days // 365
        
        # Get primary cardiac diagnosis
        diagnoses = p.get("diagnoses", [])
        primary_diagnosis = None
        if diagnoses:
            # Find first cardiac diagnosis (seq_num=1 or first in list)
            cardiac_diagnoses = [d for d in diagnoses if d.get("hadm_id") == hadm_id]
            if cardiac_diagnoses:
                primary = min(cardiac_diagnoses, key=lambda d: d.get("seq_num", 999))
                if primary.get("diagnosis_definition"):
                    primary_diagnosis = primary["diagnosis_definition"].get("short_title")
        
        # Get hospital expiration flag for this admission
        admission_obj = db.get(models.MimicAdmission, hadm_id)
        hospital_expire_flag = admission_obj.hospital_expire_flag if admission_obj else None
        
        summary = CardiacPatientSummary(
            subject_id=subject_id,
            hadm_id=hadm_id,
            gender=p.get("gender"),
            age=age,
            diagnoses_count=len([d for d in diagnoses if d.get("hadm_id") == hadm_id]),
            primary_diagnosis=primary_diagnosis,
            has_prescriptions=True,  # Always true when this code is reached
            hospital_expire_flag=hospital_expire_flag
        )
        
        summaries.append(summary)
        
        if len(summaries) >= limit:
            break
    
    return summaries
