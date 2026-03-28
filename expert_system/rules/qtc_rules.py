"""Rules for QTc interval evaluation."""

from expert_system.rules.base_rule import BaseRule
from expert_system.models.patient_context import PatientContext
from expert_system.models.decision_context import DecisionContext, AlertSeverity


class HighQTcRule(BaseRule):
    """
    Critical QTc prolongation rule.
    
    IF QTc > 500ms THEN:
    - Contraindicate antiarrhythmic drugs
    - Add critical alert
    - High risk of torsade de pointes
    """
    
    def __init__(self):
        super().__init__()
        self.category = "cardiac"
        self.threshold = 500  # ms
    
    def condition(self, patient: PatientContext) -> bool:
        return patient.qtc > self.threshold
    
    def action(self, patient: PatientContext, decision: DecisionContext) -> None:
        decision.set_contraindicated(
            f"QTc exceeds safe threshold ({patient.qtc}ms > {self.threshold}ms)"
        )
        decision.add_alert(
            message=f"Critical QTc prolongation: {patient.qtc}ms (normal: <450ms men, <460ms women)",
            severity=AlertSeverity.CRITICAL,
            rule_name=self.name,
            category=self.category
        )
        decision.add_alert(
            message="High risk of torsade de pointes - antiarrhythmic drugs may be life-threatening",
            severity=AlertSeverity.CRITICAL,
            rule_name=self.name,
            category=self.category
        )
    
    def explanation(self, patient: PatientContext) -> str:
        return (
            f"QTc interval is severely prolonged at {patient.qtc}ms (threshold: {self.threshold}ms). "
            f"Antiarrhythmic drugs are contraindicated due to high risk of ventricular arrhythmias "
            f"including torsade de pointes."
        )


class ModerateQTcRule(BaseRule):
    """
    Moderate QTc prolongation rule.
    
    IF 470ms < QTc <= 500ms THEN:
    - Add high-severity alert
    - Recommend caution and monitoring
    - Consider dose reduction
    """
    
    def __init__(self):
        super().__init__()
        self.category = "cardiac"
        self.lower_threshold = 470  # ms
        self.upper_threshold = 500  # ms
    
    def condition(self, patient: PatientContext) -> bool:
        return self.lower_threshold < patient.qtc <= self.upper_threshold
    
    def action(self, patient: PatientContext, decision: DecisionContext) -> None:
        decision.add_alert(
            message=f"Moderate QTc prolongation: {patient.qtc}ms",
            severity=AlertSeverity.HIGH,
            rule_name=self.name,
            category=self.category
        )
        decision.add_alert(
            message="Use antiarrhythmic drugs with extreme caution - frequent ECG monitoring required",
            severity=AlertSeverity.HIGH,
            rule_name=self.name,
            category=self.category
        )
        
        # Suggest dose reduction
        decision.set_dose_adjustment(
            adjusted_dose="Reduce to 50-75% of standard dose",
            reason=f"Moderate QTc prolongation ({patient.qtc}ms)",
            original_dose="Standard dose"
        )
    
    def explanation(self, patient: PatientContext) -> str:
        return (
            f"QTc interval is moderately prolonged at {patient.qtc}ms "
            f"(range: {self.lower_threshold}-{self.upper_threshold}ms). "
            f"Antiarrhythmic drugs may be used with caution, dose reduction, "
            f"and frequent ECG monitoring (at least daily initially)."
        )


class MildQTcRule(BaseRule):
    """
    Mild QTc prolongation rule.
    
    IF 450ms < QTc <= 470ms THEN:
    - Add moderate alert
    - Recommend monitoring
    """
    
    def __init__(self):
        super().__init__()
        self.category = "cardiac"
        self.lower_threshold = 450  # ms
        self.upper_threshold = 470  # ms
    
    def condition(self, patient: PatientContext) -> bool:
        return self.lower_threshold < patient.qtc <= self.upper_threshold
    
    def action(self, patient: PatientContext, decision: DecisionContext) -> None:
        decision.add_alert(
            message=f"Mildly prolonged QTc: {patient.qtc}ms",
            severity=AlertSeverity.MODERATE,
            rule_name=self.name,
            category=self.category
        )
        decision.add_alert(
            message="ECG monitoring recommended during antiarrhythmic therapy",
            severity=AlertSeverity.MODERATE,
            rule_name=self.name,
            category=self.category
        )
    
    def explanation(self, patient: PatientContext) -> str:
        return (
            f"QTc interval is mildly prolonged at {patient.qtc}ms "
            f"(range: {self.lower_threshold}-{self.upper_threshold}ms). "
            f"Regular ECG monitoring is recommended if antiarrhythmic drugs are initiated."
        )
