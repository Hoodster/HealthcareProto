"""Drug-specific QTc rules (require measured QTc from chartevents when available)."""

from expert_system.rules.base_rule import BaseRule
from expert_system.models.patient_context import PatientContext
from expert_system.models.decision_context import DecisionContext, AlertSeverity


class SotalolQTContraindicationRule(BaseRule):
    """Sotalol + QTc > 450 ms before AF/AFL therapy — contraindication per labeling."""

    def __init__(self):
        super().__init__()
        self.category = "cardiac"
        self.threshold = 450

    def condition(self, patient: PatientContext) -> bool:
        from expert_system.guideline_checks import check_sotalol_qt_contraindication

        return check_sotalol_qt_contraindication(patient)

    def action(self, patient: PatientContext, decision: DecisionContext) -> None:
        decision.contraindicated = True
        decision.add_alert(
            message=(
                f"Sotalol with QTc {patient.qtc} ms > {self.threshold} ms — "
                "avoid initiation per AF/AFL labeling"
            ),
            severity=AlertSeverity.CRITICAL,
            rule_name=self.name,
            category=self.category,
        )

    def explanation(self, patient: PatientContext) -> str:
        return (
            f"Patient on sotalol with QTc {patient.qtc} ms exceeding {self.threshold} ms. "
            "Sotalol is contraindicated when baseline QT interval is prolonged."
        )


class DofetilideQTContraindicationRule(BaseRule):
    """Dofetilide + QTc > 440 ms, or > 500 ms with conduction disease."""

    def __init__(self):
        super().__init__()
        self.category = "cardiac"
        self.baseline_threshold = 440
        self.severe_threshold = 500

    def condition(self, patient: PatientContext) -> bool:
        from expert_system.guideline_checks import check_dofetilide_qt_contraindication

        return check_dofetilide_qt_contraindication(patient)

    def action(self, patient: PatientContext, decision: DecisionContext) -> None:
        decision.contraindicated = True
        decision.add_alert(
            message=(
                f"Dofetilide with QTc {patient.qtc} ms — contraindicated per "
                "dofetilide labeling (QTc > 440 ms or > 500 ms with conduction disease)"
            ),
            severity=AlertSeverity.CRITICAL,
            rule_name=self.name,
            category=self.category,
        )

    def explanation(self, patient: PatientContext) -> str:
        return (
            f"Dofetilide requires QTc ≤ {self.baseline_threshold} ms for initiation "
            f"(≤ {self.severe_threshold} ms if conduction disease). "
            f"Measured QTc: {patient.qtc} ms."
        )
