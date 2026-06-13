"""Unit tests for layer B guideline checks."""

from expert_system.models.patient_context import PatientContext
from expert_system.guideline_checks import evaluate_guideline_violations


def test_qt_interaction_two_drugs():
    p = PatientContext(
        egfr=80,
        medications=["amiodarone", "azithromycin"],
    )
    tags = evaluate_guideline_violations(p)
    assert "QT_INTERACTION" in tags
    assert "QT_AAD_COMBO" in tags


def test_dronedarone_hf():
    p = PatientContext(
        egfr=55,
        medications=["dronedarone"],
        conditions=["congestive heart failure - unspecified"],
    )
    tags = evaluate_guideline_violations(p)
    assert "DRONEDARONE_HF" in tags


def test_class_ic_structural():
    p = PatientContext(
        egfr=70,
        medications=["flecainide"],
        conditions=["ischemic heart disease"],
    )
    tags = evaluate_guideline_violations(p)
    assert "CLASS_IC_STRUCTURAL_HF" in tags


def test_renal_sotalol():
    p = PatientContext(
        egfr=22,
        medications=["sotalol"],
    )
    tags = evaluate_guideline_violations(p)
    assert "SEVERE_RENAL_IMPAIRMENT" in tags
    assert "RENAL_CONTRAINDICATED_AAD" in tags


def test_digoxin_elderly():
    p = PatientContext(
        egfr=55,
        medications=["digoxin"],
        age=78,
    )
    tags = evaluate_guideline_violations(p)
    assert "DIGOXIN_RENAL_AGE" in tags


def test_beta_blocker_requires_aad():
    p = PatientContext(
        egfr=90,
        medications=["metoprolol"],
    )
    assert "BETA_BLOCKER_INTERACTION" not in evaluate_guideline_violations(p)

    p2 = PatientContext(
        egfr=90,
        medications=["metoprolol", "amiodarone"],
    )
    assert "BETA_BLOCKER_INTERACTION" in evaluate_guideline_violations(p2)
