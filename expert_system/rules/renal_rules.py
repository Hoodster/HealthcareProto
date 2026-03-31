"""Rules for renal function evaluation."""

from expert_system.rules.base_rule import BaseRule
from expert_system.models.patient_context import PatientContext
from expert_system.models.decision_context import DecisionContext, AlertSeverity


class SevereRenalImpairmentRule(BaseRule):
    """
    Severe renal impairment rule.
    
    IF eGFR < 30 mL/min/1.73m² THEN:
    - Add critical alert
    - Require significant dose reduction
    - Many drugs contraindicated or require alternative dosing
    """
    
    def __init__(self):
        super().__init__()
        self.category = "renal"
        self.threshold = 30  # mL/min/1.73m²
    
    def condition(self, patient: PatientContext) -> bool:
        return patient.egfr < self.threshold
    
    def action(self, patient: PatientContext, decision: DecisionContext) -> None:
        decision.add_alert(
            message=f"Severe renal impairment: eGFR {patient.egfr} mL/min/1.73m² (Stage 4-5 CKD)",
            severity=AlertSeverity.CRITICAL,
            rule_name=self.name,
            category=self.category
        )
        decision.add_alert(
            message="Many antiarrhythmic drugs require dose reduction or are contraindicated",
            severity=AlertSeverity.CRITICAL,
            rule_name=self.name,
            category=self.category
        )
        
        decision.set_dose_adjustment(
            adjusted_dose="Reduce to 25-50% of standard dose, or avoid if possible",
            reason=f"Severe renal impairment (eGFR: {patient.egfr} mL/min/1.73m²)",
            original_dose="Standard dose"
        )
    
    def explanation(self, patient: PatientContext) -> str:
        return (
            f"Severe renal impairment detected with eGFR of {patient.egfr} mL/min/1.73m² "
            f"(threshold: <{self.threshold}). This represents Stage 4-5 chronic kidney disease. "
            f"Most antiarrhythmic drugs are renally cleared and require significant dose reduction "
            f"or alternative therapy. Consult nephrology and clinical pharmacology."
        )


class ModerateRenalImpairmentRule(BaseRule):
    """
    Moderate renal impairment rule.
    
    IF 30 <= eGFR < 60 mL/min/1.73m² THEN:
    - Add high alert
    - Recommend dose adjustment
    - Monitor drug levels if available
    """
    
    def __init__(self):
        super().__init__()
        self.category = "renal"
        self.lower_threshold = 30  # mL/min/1.73m²
        self.upper_threshold = 60  # mL/min/1.73m²
    
    def condition(self, patient: PatientContext) -> bool:
        return self.lower_threshold <= patient.egfr < self.upper_threshold
    
    def action(self, patient: PatientContext, decision: DecisionContext) -> None:
        decision.add_alert(
            message=f"Moderate renal impairment: eGFR {patient.egfr} mL/min/1.73m² (Stage 3 CKD)",
            severity=AlertSeverity.HIGH,
            rule_name=self.name,
            category=self.category
        )
        decision.add_alert(
            message="Dose adjustment recommended - monitor for drug accumulation",
            severity=AlertSeverity.HIGH,
            rule_name=self.name,
            category=self.category
        )
        
        decision.set_dose_adjustment(
            adjusted_dose="Reduce to 50-75% of standard dose",
            reason=f"Moderate renal impairment (eGFR: {patient.egfr} mL/min/1.73m²)",
            original_dose="Standard dose"
        )
    
    def explanation(self, patient: PatientContext) -> str:
        return (
            f"Moderate renal impairment detected with eGFR of {patient.egfr} mL/min/1.73m² "
            f"(range: {self.lower_threshold}-{self.upper_threshold}). This is Stage 3 CKD. "
            f"Dose reduction is recommended for most antiarrhythmic drugs. "
            f"Monitor serum drug levels if available and watch for signs of toxicity."
        )


class MildRenalImpairmentRule(BaseRule):
    """
    Mild renal impairment rule.
    
    IF 60 <= eGFR < 90 mL/min/1.73m² THEN:
    - Add moderate alert
    - Recommend monitoring
    """
    
    def __init__(self):
        super().__init__()
        self.category = "renal"
        self.lower_threshold = 60  # mL/min/1.73m²
        self.upper_threshold = 90  # mL/min/1.73m²
    
    def condition(self, patient: PatientContext) -> bool:
        return self.lower_threshold <= patient.egfr < self.upper_threshold
    
    def action(self, patient: PatientContext, decision: DecisionContext) -> None:
        decision.add_alert(
            message=f"Mild renal impairment: eGFR {patient.egfr} mL/min/1.73m²",
            severity=AlertSeverity.MODERATE,
            rule_name=self.name,
            category=self.category
        )
        decision.add_alert(
            message="Standard dosing generally acceptable - monitor renal function",
            severity=AlertSeverity.LOW,
            rule_name=self.name,
            category=self.category
        )
    
    def explanation(self, patient: PatientContext) -> str:
        return (
            f"Mild renal impairment detected with eGFR of {patient.egfr} mL/min/1.73m². "
            f"Standard dosing is generally acceptable but monitor renal function "
            f"and watch for signs of drug accumulation, especially in elderly patients."
        )
