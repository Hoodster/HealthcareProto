"""Rules for drug-drug interactions."""

from expert_system.rules.base_rule import BaseRule
from expert_system.models.patient_context import PatientContext
from expert_system.models.decision_context import DecisionContext, AlertSeverity


# Known QT-prolonging drugs (partial list for demonstration)
QT_PROLONGING_DRUGS = {
    # Antiarrhythmics (Class IA and III)
    "amiodarone", "sotalol", "quinidine", "procainamide", "disopyramide", "dofetilide", "ibutilide",

    # Antibiotics
    "azithromycin", "clarithromycin", "erythromycin", "levofloxacin", "moxifloxacin", "ciprofloxacin",

    # Antipsychotics
    "haloperidol", "quetiapine", "ziprasidone", "risperidone", "olanzapine",

    # Antidepressants
    "citalopram", "escitalopram", "amitriptyline",

    # Antiemetics
    "ondansetron", "metoclopramide",

    # Antifungals
    "fluconazole", "ketoconazole",

    # Others
    "methadone", "domperidone"
}


# Drugs that inhibit CYP enzymes and can increase antiarrhythmic levels
CYP_INHIBITORS = {
    "ketoconazole", "itraconazole", "clarithromycin", "erythromycin",
    "diltiazem", "verapamil", "amiodarone", "dronedarone",
    "fluoxetine", "paroxetine", "ritonavir"
}


# Beta-blockers that can cause additive bradycardia with antiarrhythmics
BETA_BLOCKERS = {
    "metoprolol", "atenolol", "bisoprolol", "carvedilol", "propranolol",
    "labetalol", "nebivolol", "nadolol"
}


class QTProlongingDrugInteractionRule(BaseRule):
    """
    Drug interaction rule for QT-prolonging medications.

    IF patient takes drugs that prolong QT THEN:
    - Add critical alert
    - List interacting drugs
    - Warn of additive risk
    """

    def __init__(self):
        super().__init__()
        self.category = "interaction"

    def condition(self, patient: PatientContext) -> bool:
        """Check if patient takes any QT-prolonging drugs."""
        patient_drugs = {drug.lower().strip() for drug in patient.medications}
        return bool(patient_drugs & QT_PROLONGING_DRUGS)

    def action(self, patient: PatientContext, decision: DecisionContext) -> None:
        patient_drugs = {drug.lower().strip() for drug in patient.medications}
        interacting_drugs = list(patient_drugs & QT_PROLONGING_DRUGS)

        decision.add_alert(
            message=f"Drug interaction: Patient taking QT-prolonging medications: {', '.join(interacting_drugs)}",
            severity=AlertSeverity.CRITICAL,
            rule_name=self.name,
            category=self.category
        )
        decision.add_alert(
            message="Additive QT prolongation risk - consider alternative therapy or enhanced monitoring",
            severity=AlertSeverity.CRITICAL,
            rule_name=self.name,
            category=self.category
        )

    def explanation(self, patient: PatientContext) -> str:
        patient_drugs = {drug.lower().strip() for drug in patient.medications}
        interacting_drugs = list(patient_drugs & QT_PROLONGING_DRUGS)

        return (
            f"Patient is currently taking QT-prolonging medications: {', '.join(interacting_drugs)}. "
            f"Adding another antiarrhythmic drug creates additive risk of QT prolongation "
            f"and torsade de pointes. Consider discontinuing non-essential QT-prolonging drugs, "
            f"using alternative therapy, or implementing intensive ECG monitoring."
        )


class CYPInhibitorInteractionRule(BaseRule):
    """
    Drug interaction rule for CYP enzyme inhibitors.

    IF patient takes CYP inhibitors THEN:
    - Risk of increased antiarrhythmic levels
    - Recommend dose reduction
    """

    def __init__(self):
        super().__init__()
        self.category = "interaction"

    def condition(self, patient: PatientContext) -> bool:
        patient_drugs = {drug.lower().strip() for drug in patient.medications}
        return bool(patient_drugs & CYP_INHIBITORS)

    def action(self, patient: PatientContext, decision: DecisionContext) -> None:
        patient_drugs = {drug.lower().strip() for drug in patient.medications}
        inhibitors = list(patient_drugs & CYP_INHIBITORS)

        decision.add_alert(
            message=f"Drug interaction: CYP enzyme inhibitors detected: {', '.join(inhibitors)}",
            severity=AlertSeverity.HIGH,
            rule_name=self.name,
            category=self.category
        )
        decision.add_alert(
            message="Risk of increased antiarrhythmic drug levels - consider dose reduction",
            severity=AlertSeverity.HIGH,
            rule_name=self.name,
            category=self.category
        )

        if not decision.dose_adjustment:  # Don't override existing adjustment
            decision.set_dose_adjustment(
                adjusted_dose="Reduce to 50% of standard dose initially",
                reason=f"CYP inhibitor interaction: {', '.join(inhibitors)}",
                original_dose="Standard dose"
            )

    def explanation(self, patient: PatientContext) -> str:
        patient_drugs = {drug.lower().strip() for drug in patient.medications}
        inhibitors = list(patient_drugs & CYP_INHIBITORS)

        return (
            f"Patient is taking CYP enzyme inhibitors: {', '.join(inhibitors)}. "
            f"These drugs can reduce metabolism of many antiarrhythmics, "
            f"leading to increased drug levels and risk of toxicity. "
            f"Dose reduction and therapeutic drug monitoring (if available) are recommended."
        )


class BetaBlockerInteractionRule(BaseRule):
    """
    Drug interaction rule for beta-blockers.

    IF patient takes beta-blockers THEN:
    - Risk of bradycardia with some antiarrhythmics
    - Recommend heart rate monitoring
    """

    def __init__(self):
        super().__init__()
        self.category = "interaction"

    def condition(self, patient: PatientContext) -> bool:
        patient_drugs = {drug.lower().strip() for drug in patient.medications}
        return bool(patient_drugs & BETA_BLOCKERS)

    def action(self, patient: PatientContext, decision: DecisionContext) -> None:
        patient_drugs = {drug.lower().strip() for drug in patient.medications}
        beta_blockers = list(patient_drugs & BETA_BLOCKERS)

        decision.add_alert(
            message=f"Beta-blocker interaction: {', '.join(beta_blockers)}",
            severity=AlertSeverity.MODERATE,
            rule_name=self.name,
            category=self.category
        )
        decision.add_alert(
            message="Risk of additive bradycardia - monitor heart rate closely",
            severity=AlertSeverity.MODERATE,
            rule_name=self.name,
            category=self.category
        )

    def explanation(self, patient: PatientContext) -> str:
        patient_drugs = {drug.lower().strip() for drug in patient.medications}
        beta_blockers = list(patient_drugs & BETA_BLOCKERS)

        return (
            f"Patient is taking beta-blocker(s): {', '.join(beta_blockers)}. "
            f"Combined with certain antiarrhythmics (e.g., amiodarone, sotalol), "
            f"there is increased risk of bradycardia and AV block. "
            f"Monitor heart rate and consider reducing beta-blocker dose if needed."
        )
