"""Rules using patient conditions (ICD-9 mapped comorbidities)."""

from expert_system.rules.base_rule import BaseRule
from expert_system.models.patient_context import PatientContext
from expert_system.models.decision_context import DecisionContext, AlertSeverity
from expert_system.guideline_checks import (
    check_av_block_brady_risk,
    check_class_ic_structural_hf,
    check_ccb_hf,
    check_digoxin_renal_age,
    check_dronedarone_hf,
    patient_drugs,
    CLASS_IC_DRUGS,
    NON_DHP_CCB,
)


class ClassICStructuralHeartRule(BaseRule):
    """Flecainide/propafenone contraindicated in structural heart disease or HF."""

    def __init__(self):
        super().__init__()
        self.category = "condition"

    def condition(self, patient: PatientContext) -> bool:
        return check_class_ic_structural_hf(patient)

    def action(self, patient: PatientContext, decision: DecisionContext) -> None:
        drugs = sorted(patient_drugs(patient) & CLASS_IC_DRUGS)
        decision.add_alert(
            message=(
                f"Class IC antiarrhythmic ({', '.join(drugs)}) with structural heart disease "
                f"or heart failure — avoid or use with extreme caution"
            ),
            severity=AlertSeverity.CRITICAL,
            rule_name=self.name,
            category=self.category,
        )
        decision.set_contraindicated(
            f"Class IC agents ({', '.join(drugs)}) are contraindicated in significant "
            "structural heart disease and heart failure (proarrhythmia risk)"
        )

    def explanation(self, patient: PatientContext) -> str:
        drugs = sorted(patient_drugs(patient) & CLASS_IC_DRUGS)
        return (
            f"Patient takes {', '.join(drugs)} with structural heart disease, ischemic "
            "heart disease, or heart failure. Class IC antiarrhythmics increase mortality "
            "in structural heart disease per AF guidelines."
        )


class DronedaroneHeartFailureRule(BaseRule):
    """Dronedarone is contraindicated in heart failure (decompensated/advanced proxy)."""

    def __init__(self):
        super().__init__()
        self.category = "condition"

    def condition(self, patient: PatientContext) -> bool:
        return check_dronedarone_hf(patient)

    def action(self, patient: PatientContext, decision: DecisionContext) -> None:
        decision.add_alert(
            message="Dronedarone with heart failure — contraindicated per AF guidelines",
            severity=AlertSeverity.CRITICAL,
            rule_name=self.name,
            category=self.category,
        )
        decision.set_contraindicated(
            "Dronedarone is contraindicated in heart failure (increased mortality)"
        )

    def explanation(self, patient: PatientContext) -> str:
        return (
            "Patient takes dronedarone with a heart failure diagnosis. Dronedarone is "
            "contraindicated in heart failure including NYHA class IV and decompensated HF."
        )


class NonDhpCcbHeartFailureRule(BaseRule):
    """Non-dihydropyridine CCBs (diltiazem, verapamil) avoided in HFrEF."""

    def __init__(self):
        super().__init__()
        self.category = "condition"

    def condition(self, patient: PatientContext) -> bool:
        return check_ccb_hf(patient)

    def action(self, patient: PatientContext, decision: DecisionContext) -> None:
        ccbs = sorted(patient_drugs(patient) & NON_DHP_CCB)
        decision.add_alert(
            message=(
                f"Non-DHP calcium channel blocker ({', '.join(ccbs)}) with heart failure — "
                "negative inotropic effect"
            ),
            severity=AlertSeverity.HIGH,
            rule_name=self.name,
            category=self.category,
        )

    def explanation(self, patient: PatientContext) -> str:
        ccbs = sorted(patient_drugs(patient) & NON_DHP_CCB)
        return (
            f"Patient takes {', '.join(ccbs)} with heart failure. Non-dihydropyridine CCBs "
            "have negative inotropic effects and are generally avoided in HFrEF."
        )


class DigoxinRenalAgeRule(BaseRule):
    """Digoxin requires caution in severe renal impairment or elderly patients."""

    def __init__(self):
        super().__init__()
        self.category = "condition"

    def condition(self, patient: PatientContext) -> bool:
        return check_digoxin_renal_age(patient)

    def action(self, patient: PatientContext, decision: DecisionContext) -> None:
        reasons = []
        if patient.egfr < 30:
            reasons.append(f"eGFR {patient.egfr}")
        if patient.age and patient.age >= 75:
            reasons.append(f"age {patient.age}")
        decision.add_alert(
            message=f"Digoxin safety concern ({', '.join(reasons)}) — reduce dose and monitor levels",
            severity=AlertSeverity.HIGH,
            rule_name=self.name,
            category=self.category,
        )

    def explanation(self, patient: PatientContext) -> str:
        return (
            f"Digoxin with {'severe renal impairment' if patient.egfr < 30 else ''}"
            f"{' and ' if patient.egfr < 30 and patient.age and patient.age >= 75 else ''}"
            f"{'advanced age' if patient.age and patient.age >= 75 else ''}. "
            "Renal clearance and age affect digoxin toxicity risk."
        )


class AvBlockBradycardiaRiskRule(BaseRule):
    """AV block with bradycardia-risk drugs (beta-blockers, amiodarone, sotalol)."""

    def __init__(self):
        super().__init__()
        self.category = "condition"

    def condition(self, patient: PatientContext) -> bool:
        return check_av_block_brady_risk(patient)

    def action(self, patient: PatientContext, decision: DecisionContext) -> None:
        decision.add_alert(
            message="AV block with bradycardia-risk medications — monitor HR and conduction",
            severity=AlertSeverity.HIGH,
            rule_name=self.name,
            category=self.category,
        )

    def explanation(self, patient: PatientContext) -> str:
        return (
            "Patient has AV block and takes bradycardia-risk drugs (beta-blocker and/or "
            "amiodarone/sotalol). Risk of symptomatic bradycardia or high-grade block."
        )
