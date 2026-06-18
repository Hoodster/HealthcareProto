"""Tests for expert rule tag mapping."""

from expert_system.models.decision_context import DecisionContext
from expert_system.models.patient_context import PatientContext
from expert_system.rule_tags import expert_rule_tags


def test_expert_rule_tags_renal_sotalol():
    patient = PatientContext(age=70, medications=["sotalol"], egfr=35.0, conditions=[])
    decision = DecisionContext(
        triggered_rules=["SotalolRenalContraindicationRule"],
        alerts=[],
    )
    tags = expert_rule_tags(decision, patient)
    assert "SOTALOL_RENAL_CONTRAINDICATION" in tags


def test_expert_rule_tags_dronedarone_hf():
    patient = PatientContext(
        age=75,
        medications=["dronedarone"],
        egfr=90.0,
        conditions=["heart failure"],
    )
    decision = DecisionContext(
        triggered_rules=["DronedaroneHeartFailureRule"],
        alerts=[],
    )
    tags = expert_rule_tags(decision, patient)
    assert "DRONEDARONE_HF" in tags
