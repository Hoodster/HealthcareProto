"""Tests for shared guideline predicates used by expert rules."""

from expert_system.guideline_checks import (
    check_beta_blocker_interaction,
    check_dronedarone_hf,
    check_qt_aad_combo,
    check_qt_interaction,
    check_qt_rule_fires,
    check_severe_renal,
)
from expert_system.models.patient_context import PatientContext


def _patient(**kwargs) -> PatientContext:
    defaults = {
        "age": 70,
        "medications": [],
        "egfr": 90.0,
        "conditions": [],
    }
    defaults.update(kwargs)
    return PatientContext(**defaults)


def test_qt_interaction_two_qt_drugs():
    p = _patient(medications=["amiodarone", "sotalol"])
    assert check_qt_interaction(p)
    assert check_qt_rule_fires(p)


def test_qt_aad_combo():
    p = _patient(medications=["amiodarone", "sotalol"])
    assert check_qt_aad_combo(p)


def test_beta_blocker_interaction_with_aad():
    p = _patient(medications=["metoprolol", "amiodarone"])
    assert check_beta_blocker_interaction(p)


def test_severe_renal():
    p = _patient(egfr=25.0)
    assert check_severe_renal(p)


def test_dronedarone_hf():
    p = _patient(medications=["dronedarone"], conditions=["heart failure"])
    assert check_dronedarone_hf(p)


def test_beta_blocker_no_interaction_without_aad():
    p = _patient(medications=["metoprolol", "diltiazem"])
    assert not check_beta_blocker_interaction(p)
