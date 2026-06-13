"""Shared guideline predicates used by expert rules."""

from __future__ import annotations

from expert_system.models.patient_context import PatientContext
from expert_system.rules.interaction_rules import (
    ANTIARRHYTHMIC_DRUGS,
    BETA_BLOCKERS,
    CYP_INHIBITORS,
    CYP_INDUCERS,
    QT_AAD_DRUGS,
    QT_PROLONGING_DRUGS,
    RENALLY_CLEARED_ANTIARRHYTHMICS,
    ANTIPLATELET_DRUGS,
    RATE_CONTROL_DRUGS,
    BRADYCARDIA_RISK_AAD,
    CLASS_IC_DRUGS,
    NON_DHP_CCB,
)

EGFR_SEVERE = 30
EGFR_MODERATE_LO = 30
EGFR_MODERATE_HI = 60
EGFR_MILD_LO = 60
EGFR_MILD_HI = 90
ELDERLY_AGE = 75

HEART_FAILURE_PATTERNS = ("heart failure", "428")
ISCHEMIC_HD_PATTERNS = ("ischemic heart", "414", "coronary", "myocardial")
VALVE_DISEASE_PATTERNS = ("valve", "424", "mitral stenosis", "mechanical valve")
AV_BLOCK_PATTERNS = ("atrioventricular block", "426", "av block")


def patient_drugs(patient: PatientContext) -> set[str]:
    return {drug.lower().strip() for drug in patient.medications}


def condition_matches(patient: PatientContext, patterns: tuple[str, ...]) -> bool:
    for cond in patient.conditions:
        cl = cond.lower()
        for pattern in patterns:
            if pattern in cl:
                return True
    return False


def has_heart_failure(patient: PatientContext) -> bool:
    return condition_matches(patient, HEART_FAILURE_PATTERNS)


def has_structural_or_ihd(patient: PatientContext) -> bool:
    return (
        has_heart_failure(patient)
        or condition_matches(patient, ISCHEMIC_HD_PATTERNS)
        or condition_matches(patient, VALVE_DISEASE_PATTERNS)
    )


def has_av_block(patient: PatientContext) -> bool:
    return condition_matches(patient, AV_BLOCK_PATTERNS)


def check_qt_interaction(patient: PatientContext) -> bool:
    return len(patient_drugs(patient) & QT_PROLONGING_DRUGS) >= 2


def check_qt_aad_combo(patient: PatientContext) -> bool:
    drugs = patient_drugs(patient)
    qt = drugs & QT_PROLONGING_DRUGS
    aad_qt = drugs & QT_AAD_DRUGS
    return bool(aad_qt) and len(qt) >= 2


def check_severe_renal(patient: PatientContext) -> bool:
    return patient.egfr < EGFR_SEVERE


def check_moderate_renal(patient: PatientContext) -> bool:
    return EGFR_MODERATE_LO <= patient.egfr < EGFR_MODERATE_HI


def check_mild_renal(patient: PatientContext) -> bool:
    return EGFR_MILD_LO <= patient.egfr < EGFR_MILD_HI


def check_renal_contraindicated_aad(patient: PatientContext) -> bool:
    drugs = patient_drugs(patient)
    return patient.egfr < EGFR_SEVERE and bool(drugs & RENALLY_CLEARED_ANTIARRHYTHMICS)


def check_cyp_inhibitor(patient: PatientContext) -> bool:
    return bool(patient_drugs(patient) & CYP_INHIBITORS)


def check_cyp_inducer(patient: PatientContext) -> bool:
    return bool(patient_drugs(patient) & CYP_INDUCERS)


def check_beta_blocker_interaction(patient: PatientContext) -> bool:
    drugs = patient_drugs(patient)
    if not (drugs & BETA_BLOCKERS):
        return False
    return bool(drugs & (ANTIARRHYTHMIC_DRUGS | BRADYCARDIA_RISK_AAD))


def check_av_block_brady_risk(patient: PatientContext) -> bool:
    if not has_av_block(patient):
        return False
    drugs = patient_drugs(patient)
    return bool(drugs & (BETA_BLOCKERS | BRADYCARDIA_RISK_AAD))


def check_class_ic_structural_hf(patient: PatientContext) -> bool:
    drugs = patient_drugs(patient)
    return bool(drugs & CLASS_IC_DRUGS) and has_structural_or_ihd(patient)


def check_dronedarone_hf(patient: PatientContext) -> bool:
    return "dronedarone" in patient_drugs(patient) and has_heart_failure(patient)


def check_ccb_hf(patient: PatientContext) -> bool:
    drugs = patient_drugs(patient)
    return bool(drugs & NON_DHP_CCB) and has_heart_failure(patient)


def check_digoxin_renal_age(patient: PatientContext) -> bool:
    if "digoxin" not in patient_drugs(patient):
        return False
    age = patient.age or 0
    return patient.egfr < EGFR_SEVERE or age >= ELDERLY_AGE


def check_amiodarone_monitoring(patient: PatientContext) -> bool:
    return "amiodarone" in patient_drugs(patient)


def check_antiplatelet_qt_risk(patient: PatientContext) -> bool:
    drugs = patient_drugs(patient)
    return bool(drugs & ANTIPLATELET_DRUGS) and bool(drugs & QT_PROLONGING_DRUGS)


def check_drugbank_interaction(patient: PatientContext) -> bool:
    try:
        from api.drug_db_store import get_drug_interactions, is_initialized

        if not is_initialized():
            return False
        return bool(get_drug_interactions(patient.medications))
    except Exception:
        return False


def check_qt_rule_fires(patient: PatientContext) -> bool:
    """Expert QT rule: additive combo or multiple QT drugs."""
    return check_qt_interaction(patient) or check_qt_aad_combo(patient)
