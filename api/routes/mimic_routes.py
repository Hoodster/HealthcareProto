from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from api.services.mimic_service import get_heart_patients, get_all_patients, build_mimic_patient_context
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


@router.get("/patient-context/{subject_id}/{hadm_id}")
def get_mimic_patient_context(
    subject_id: int,
    hadm_id: int,
    db: Session = Depends(get_db),
):
    """Build and return the PatientContext derived from MIMIC-III data for a given admission."""
    ctx = build_mimic_patient_context(subject_id, hadm_id, db)
    return ctx.model_dump()


@router.post("/benchmark")
def run_mimic_benchmark(
    n_patients: int = Query(default=20, ge=1, le=200),
    modes: list[str] = Query(default=["expert_only", "llm_only", "full_pipeline"]),
    db: Session = Depends(get_db),
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

    valid_modes = ["expert_only", "llm_only", "full_pipeline"]
    selected_modes = [m for m in modes if m in valid_modes] or ["expert_only"]
    runner = BenchmarkRunner()
    report = runner.compare(cases, modes=selected_modes)
    return report
