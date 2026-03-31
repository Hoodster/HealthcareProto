"""
Annotated clinical test cases used as ground-truth for benchmarking.
Extends the 5 cases from expert_system/test_cases.py with 5 additional edge cases.
"""
from __future__ import annotations

from expert_system import PatientContext
from api.benchmarks.benchmark_runner import BenchmarkCase

BENCHMARK_CASES: list[BenchmarkCase] = [
    # ── Reuse from expert_system/test_cases.py ──────────────────────────────

    BenchmarkCase(
        case_id="TEST_001",
        description="High QTc + amiodarone → contraindicated",
        patient=PatientContext(
            patient_id="TEST_001",
            qtc=520,
            egfr=75,
            medications=["amiodarone", "metoprolol", "aspirin"],
            conditions=["atrial fibrillation", "hypertension"],
            age=72,
            gender="M",
            weight=85.0,
        ),
        question="Is the current antiarrhythmic therapy safe for this patient?",
        ground_truth={
            "expected_contraindicated": True,
            "expected_alert_categories": ["cardiac", "interaction"],
            "expected_dose_adjustment": False,
        },
    ),
    BenchmarkCase(
        case_id="TEST_002",
        description="Severe CKD (eGFR 25) + metformin → dose adjustment",
        patient=PatientContext(
            patient_id="TEST_002",
            qtc=430,
            egfr=25,
            medications=["lisinopril", "metformin", "furosemide"],
            conditions=["chronic kidney disease stage 4", "diabetes"],
            age=68,
            gender="F",
            weight=70.0,
        ),
        question="Any renal dosing concerns for this patient?",
        ground_truth={
            "expected_contraindicated": False,
            "expected_alert_categories": ["renal"],
            "expected_dose_adjustment": True,
        },
    ),
    BenchmarkCase(
        case_id="TEST_003",
        description="Low-risk patient — no contraindications expected",
        patient=PatientContext(
            patient_id="TEST_003",
            qtc=420,
            egfr=95,
            medications=["aspirin", "atorvastatin"],
            conditions=["hypertension"],
            age=55,
            gender="M",
            weight=80.0,
        ),
        question="Is this patient's medication list safe?",
        ground_truth={
            "expected_contraindicated": False,
            "expected_alert_categories": [],
            "expected_dose_adjustment": False,
        },
    ),
    BenchmarkCase(
        case_id="TEST_004",
        description="Multiple QT-prolonging agents + moderate CKD",
        patient=PatientContext(
            patient_id="TEST_004",
            qtc=485,
            egfr=42,
            medications=["clarithromycin", "metoprolol", "ketoconazole", "ondansetron"],
            conditions=["pneumonia", "hypertension", "ckd stage 3"],
            age=70,
            gender="F",
            weight=65.0,
        ),
        question="What are the drug safety concerns for this patient?",
        ground_truth={
            "expected_contraindicated": False,
            "expected_alert_categories": ["cardiac", "renal", "interaction"],
            "expected_dose_adjustment": True,
        },
    ),
    BenchmarkCase(
        case_id="TEST_005",
        description="Amiodarone + CYP inhibitors → multiple interaction alerts",
        patient=PatientContext(
            patient_id="TEST_005",
            qtc=460,
            egfr=70,
            medications=["amiodarone", "metoprolol", "verapamil", "clarithromycin"],
            conditions=["atrial fibrillation"],
            age=65,
            gender="M",
            weight=88.0,
        ),
        question="Are there drug interaction concerns with this antiarrhythmic regimen?",
        ground_truth={
            "expected_contraindicated": False,
            "expected_alert_categories": ["interaction"],
            "expected_dose_adjustment": False,
        },
    ),

    # ── Additional edge cases ────────────────────────────────────────────────

    BenchmarkCase(
        case_id="EDGE_001",
        description="Critical QTc (>500) without QT-prolonging drugs",
        patient=PatientContext(
            patient_id="EDGE_001",
            qtc=510,
            egfr=80,
            medications=["aspirin", "atorvastatin", "ramipril"],
            conditions=["long qt syndrome"],
            age=45,
            gender="F",
            weight=60.0,
        ),
        question="Is the measured QTc clinically significant?",
        ground_truth={
            "expected_contraindicated": True,
            "expected_alert_categories": ["cardiac"],
            "expected_dose_adjustment": False,
        },
    ),
    BenchmarkCase(
        case_id="EDGE_002",
        description="End-stage renal disease eGFR<15",
        patient=PatientContext(
            patient_id="EDGE_002",
            qtc=440,
            egfr=12,
            medications=["metoprolol", "furosemide", "erythropoietin"],
            conditions=["end-stage renal disease", "hypertension"],
            age=60,
            gender="M",
            weight=75.0,
        ),
        question="What dose adjustments are needed for ESRD?",
        ground_truth={
            "expected_contraindicated": False,
            "expected_alert_categories": ["renal"],
            "expected_dose_adjustment": True,
        },
    ),
    BenchmarkCase(
        case_id="EDGE_003",
        description="Polypharmacy: 3 QT-prolonging agents simultaneously",
        patient=PatientContext(
            patient_id="EDGE_003",
            qtc=465,
            egfr=60,
            medications=["azithromycin", "haloperidol", "methadone", "omeprazole"],
            conditions=["schizophrenia", "opioid dependence", "pneumonia"],
            age=50,
            gender="M",
            weight=70.0,
        ),
        question="Does this polypharmacy regimen carry QT prolongation risk?",
        ground_truth={
            "expected_contraindicated": False,
            "expected_alert_categories": ["interaction"],
            "expected_dose_adjustment": False,
        },
    ),
    BenchmarkCase(
        case_id="EDGE_004",
        description="Borderline QTc (450–470) — moderate alert only",
        patient=PatientContext(
            patient_id="EDGE_004",
            qtc=460,
            egfr=85,
            medications=["ondansetron", "ramipril"],
            conditions=["nausea", "hypertension"],
            age=40,
            gender="F",
            weight=65.0,
        ),
        question="Is ondansetron safe given the QTc?",
        ground_truth={
            "expected_contraindicated": False,
            "expected_alert_categories": ["cardiac", "interaction"],
            "expected_dose_adjustment": False,
        },
    ),
    BenchmarkCase(
        case_id="EDGE_005",
        description="Elderly patient, beta-blocker + antiarrhythmic bradycardia risk",
        patient=PatientContext(
            patient_id="EDGE_005",
            qtc=440,
            egfr=55,
            medications=["bisoprolol", "amiodarone"],
            conditions=["atrial fibrillation", "heart failure"],
            age=82,
            gender="M",
            weight=72.0,
        ),
        question="Is the amiodarone + bisoprolol combination safe in this elderly patient?",
        ground_truth={
            "expected_contraindicated": False,
            "expected_alert_categories": ["interaction", "renal"],
            "expected_dose_adjustment": True,
        },
    ),
]
