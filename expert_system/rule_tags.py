"""Map fired expert rules to compact guideline tags (expert = operationalized guidelines)."""

from __future__ import annotations

from expert_system.models.decision_context import DecisionContext
from expert_system.models.patient_context import PatientContext

RULE_TO_TAG: dict[str, str] = {
    "SevereRenalImpairmentRule": "SEVERE_RENAL_IMPAIRMENT",
    "ModerateRenalImpairmentRule": "MODERATE_RENAL_IMPAIRMENT",
    "MildRenalImpairmentRule": "MILD_RENAL_IMPAIRMENT",
    "CYPInhibitorInteractionRule": "CYP_INHIBITOR_INTERACTION",
    "CYPInducerInteractionRule": "CYP_INDUCER_INTERACTION",
    "BetaBlockerInteractionRule": "BETA_BLOCKER_INTERACTION",
    "DatabaseDrugInteractionRule": "DRUGBANK_INTERACTION",
    "SotalolRenalContraindicationRule": "SOTALOL_RENAL_CONTRAINDICATION",
    "DofetilideRenalContraindicationRule": "DOFETILIDE_RENAL_CONTRAINDICATION",
    "RenalCautionAntiarrhythmicRule": "RENAL_CAUTION_AAD",
    "AmiodaroneMonitoringRule": "AMIODARONE_MONITORING",
    "ClassICStructuralHeartRule": "CLASS_IC_STRUCTURAL_HF",
    "DronedaroneHeartFailureRule": "DRONEDARONE_HF",
    "DronedaronePermanentAFRule": "DRONEDARONE_PERMANENT_AF",
    "NonDhpCcbHeartFailureRule": "CCB_HF",
    "DigoxinRenalAgeRule": "DIGOXIN_RENAL_AGE",
    "AvBlockBradycardiaRiskRule": "AV_BLOCK_BRADY_RISK",
    "SotalolQTContraindicationRule": "SOTALOL_QT_CONTRAINDICATION",
    "DofetilideQTContraindicationRule": "DOFETILIDE_QT_CONTRAINDICATION",
}


def expert_rule_tags(
    decision: DecisionContext,
    patient: PatientContext | None = None,
) -> list[str]:
    """Tags derived from rules the expert engine fired."""
    tags: list[str] = []
    fired = set(decision.triggered_rules)

    for rule_name, tag in RULE_TO_TAG.items():
        if rule_name in fired:
            tags.append(tag)

    if "QTProlongingDrugInteractionRule" in fired and patient is not None:
        from expert_system.guideline_checks import check_qt_aad_combo, check_qt_interaction

        if check_qt_interaction(patient):
            tags.append("QT_INTERACTION")
        if check_qt_aad_combo(patient):
            tags.append("QT_AAD_COMBO")

    return sorted(set(tags))
