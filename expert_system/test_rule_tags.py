"""Tests for expert rule tag mapping."""

from expert_system.models.decision_context import DecisionContext
from expert_system.models.patient_context import PatientContext
from expert_system.rule_tags import expert_rule_tags


def test_expert_rule_tags_from_fired_rules():
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
