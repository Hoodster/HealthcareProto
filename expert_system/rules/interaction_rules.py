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


# CYP3A4/P-gp inducers — reduce antiarrhythmic / DOAC levels
CYP_INDUCERS = {
    "rifampin", "rifampicin", "carbamazepine", "phenobarbital", "phenytoin",
    "st john's wort", "st johns wort",
}


# Antiplatelet agents — bleeding / QT combo proxy
ANTIPLATELET_DRUGS = {
    "aspirin", "clopidogrel", "prasugrel", "ticagrelor", "dipyridamole",
}


# Rate-control agents (not in ANTIARRHYTHMIC_DRUGS cohort filter)
RATE_CONTROL_DRUGS = {"digoxin", "diltiazem", "verapamil"}


# Class IC sodium-channel blockers
CLASS_IC_DRUGS = {"flecainide", "propafenone"}


# Non-dihydropyridine calcium channel blockers
NON_DHP_CCB = {"diltiazem", "verapamil"}


# Antiarrhythmics with bradycardia / AV block risk
BRADYCARDIA_RISK_AAD = {"amiodarone", "sotalol", "dronedarone"}


# Antiarrhythmic drugs by Vaughan-Williams class — core domain of this platform.
# Class IA/IB/IC (Na-channel blockers) and Class III (K-channel blockers).
ANTIARRHYTHMIC_DRUGS = {
    # Class IA
    "quinidine", "procainamide", "disopyramide",
    # Class IB
    "lidocaine", "mexiletine",
    # Class IC
    "flecainide", "propafenone",
    # Class III
    "amiodarone", "dronedarone", "sotalol", "dofetilide", "ibutilide",
}


# Antiarrhythmics that are renally cleared — accumulate in renal impairment and
# are contraindicated / require strict dose adjustment at low eGFR.
RENALLY_CLEARED_ANTIARRHYTHMICS = {
    "sotalol", "dofetilide", "procainamide", "disopyramide",
}

# QT-prolonging antiarrhythmics subset
QT_AAD_DRUGS = ANTIARRHYTHMIC_DRUGS & QT_PROLONGING_DRUGS


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
        from expert_system.guideline_checks import check_qt_rule_fires

        return check_qt_rule_fires(patient)

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
        from expert_system.guideline_checks import check_cyp_inhibitor

        return check_cyp_inhibitor(patient)

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
        from expert_system.guideline_checks import check_beta_blocker_interaction

        return check_beta_blocker_interaction(patient)

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


class DatabaseDrugInteractionRule(BaseRule):
    """
    Drug interaction rule backed by the DrugBank database (app.drug_interactions).

    For each pair of patient medications that has an entry in the database,
    emits a HIGH alert with the DrugBank interaction description.

    Falls back silently when the drug DB store is not loaded.
    """

    def __init__(self):
        super().__init__()
        self.category = "interaction"

    def _get_interactions(self, patient: PatientContext):
        try:
            from api.drug_db_store import get_drug_interactions, is_initialized
            if not is_initialized():
                return []
            return get_drug_interactions(patient.medications)
        except Exception:
            return []

    def condition(self, patient: PatientContext) -> bool:
        from expert_system.guideline_checks import check_drugbank_interaction

        return check_drugbank_interaction(patient)

    def action(self, patient: PatientContext, decision: DecisionContext) -> None:
        interactions = self._get_interactions(patient)
        for drug_a, drug_b, description in interactions:
            short_desc = (description[:200] + "…") if len(description) > 200 else description
            decision.add_alert(
                message=(
                    f"DrugBank interaction: {drug_a} + {drug_b}. "
                    f"{short_desc}"
                ),
                severity=AlertSeverity.HIGH,
                rule_name=self.name,
                category=self.category,
            )

    def explanation(self, patient: PatientContext) -> str:
        interactions = self._get_interactions(patient)
        if not interactions:
            return ""
        lines = [f"- {a} + {b}: {desc[:150]}…" if len(desc) > 150 else f"- {a} + {b}: {desc}"
                 for a, b, desc in interactions]
        return (
            "The following drug-drug interactions were identified in the DrugBank database:\n"
            + "\n".join(lines)
        )


class RenalContraindicatedAntiarrhythmicRule(BaseRule):
    """
    Renal-clearance safety rule for antiarrhythmic drugs.

    IF patient takes a renally-cleared antiarrhythmic (sotalol, dofetilide,
    procainamide, disopyramide) AND eGFR < 30 THEN:
    - sotalol / dofetilide → contraindicated (proarrhythmia / torsade risk)
    - procainamide / disopyramide → high alert, strict dose reduction
    """

    SEVERE_EGFR = 30

    def __init__(self):
        super().__init__()
        self.category = "interaction"

    def _affected(self, patient: PatientContext) -> set[str]:
        patient_drugs = {drug.lower().strip() for drug in patient.medications}
        return patient_drugs & RENALLY_CLEARED_ANTIARRHYTHMICS

    def condition(self, patient: PatientContext) -> bool:
        from expert_system.guideline_checks import check_renal_contraindicated_aad

        return check_renal_contraindicated_aad(patient)

    def action(self, patient: PatientContext, decision: DecisionContext) -> None:
        affected = self._affected(patient)
        contraindicated = affected & {"sotalol", "dofetilide"}
        caution = affected - contraindicated

        if contraindicated:
            drugs = ", ".join(sorted(contraindicated))
            decision.add_alert(
                message=(
                    f"Renally-cleared antiarrhythmic contraindicated at eGFR "
                    f"{patient.egfr}: {drugs}"
                ),
                severity=AlertSeverity.CRITICAL,
                rule_name=self.name,
                category=self.category,
            )
            decision.set_contraindicated(
                f"{drugs} accumulate in severe renal impairment (eGFR {patient.egfr} < 30) "
                f"with high risk of QT prolongation and torsade de pointes"
            )

        if caution:
            drugs = ", ".join(sorted(caution))
            decision.add_alert(
                message=(
                    f"Renally-cleared antiarrhythmic requires strict dose reduction at eGFR "
                    f"{patient.egfr}: {drugs}"
                ),
                severity=AlertSeverity.HIGH,
                rule_name=self.name,
                category=self.category,
            )
            if not decision.dose_adjustment:
                decision.set_dose_adjustment(
                    adjusted_dose="Reduce dose and monitor ECG, or switch to non-renally-cleared agent",
                    reason=f"Renally-cleared antiarrhythmic ({drugs}) at eGFR {patient.egfr}",
                    original_dose="Standard dose",
                )

    def explanation(self, patient: PatientContext) -> str:
        affected = self._affected(patient)
        return (
            f"Patient takes renally-cleared antiarrhythmic(s): {', '.join(sorted(affected))} "
            f"with eGFR {patient.egfr} mL/min/1.73m² (< {self.SEVERE_EGFR}). These agents "
            f"accumulate in severe renal impairment. Sotalol and dofetilide are contraindicated "
            f"due to dose-dependent QT prolongation and torsade de pointes; procainamide and "
            f"disopyramide require strict dose reduction and ECG monitoring."
        )


class CYPInducerInteractionRule(BaseRule):
    """CYP3A4/P-gp inducers may reduce antiarrhythmic drug levels."""

    def __init__(self):
        super().__init__()
        self.category = "interaction"

    def condition(self, patient: PatientContext) -> bool:
        from expert_system.guideline_checks import check_cyp_inducer

        return check_cyp_inducer(patient)

    def action(self, patient: PatientContext, decision: DecisionContext) -> None:
        patient_drugs = {drug.lower().strip() for drug in patient.medications}
        inducers = list(patient_drugs & CYP_INDUCERS)
        decision.add_alert(
            message=f"CYP inducer interaction: {', '.join(inducers)}",
            severity=AlertSeverity.MODERATE,
            rule_name=self.name,
            category=self.category,
        )

    def explanation(self, patient: PatientContext) -> str:
        patient_drugs = {drug.lower().strip() for drug in patient.medications}
        inducers = list(patient_drugs & CYP_INDUCERS)
        return (
            f"Patient takes CYP inducers ({', '.join(inducers)}) which may reduce "
            "levels of CYP-metabolized antiarrhythmics — monitor efficacy."
        )


class AntiplateletQtRiskRule(BaseRule):
    """Antiplatelet + QT-prolonging drug — bleeding and arrhythmia risk proxy."""

    def __init__(self):
        super().__init__()
        self.category = "interaction"

    def condition(self, patient: PatientContext) -> bool:
        from expert_system.guideline_checks import check_antiplatelet_qt_risk

        return check_antiplatelet_qt_risk(patient)

    def action(self, patient: PatientContext, decision: DecisionContext) -> None:
        patient_drugs = {drug.lower().strip() for drug in patient.medications}
        antiplatelets = list(patient_drugs & ANTIPLATELET_DRUGS)
        decision.add_alert(
            message=(
                f"Antiplatelet ({', '.join(antiplatelets)}) with QT-prolonging therapy — "
                "elevated bleeding and arrhythmia monitoring needed"
            ),
            severity=AlertSeverity.MODERATE,
            rule_name=self.name,
            category=self.category,
        )

    def explanation(self, patient: PatientContext) -> str:
        return (
            "Combined antiplatelet and QT-prolonging therapy increases bleeding risk "
            "and requires ECG monitoring per AF/chronic coronary disease guidelines."
        )


class AmiodaroneMonitoringRule(BaseRule):
    """Educational flag: amiodarone requires multi-organ monitoring."""

    def __init__(self):
        super().__init__()
        self.category = "interaction"

    def condition(self, patient: PatientContext) -> bool:
        from expert_system.guideline_checks import check_amiodarone_monitoring

        return check_amiodarone_monitoring(patient)

    def action(self, patient: PatientContext, decision: DecisionContext) -> None:
        decision.add_alert(
            message=(
                "Amiodarone — schedule thyroid, liver, pulmonary, and ocular monitoring; "
                "review drug interactions"
            ),
            severity=AlertSeverity.MODERATE,
            rule_name=self.name,
            category=self.category,
        )

    def explanation(self, patient: PatientContext) -> str:
        return (
            "Amiodarone requires periodic monitoring of thyroid, liver, pulmonary, "
            "and ocular function due to organ toxicity and extensive drug interactions."
        )
