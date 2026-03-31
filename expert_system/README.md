# Expert System for Drug Safety Evaluation

## Overview

A rule-based clinical decision support system for evaluating the safety and appropriateness of antiarrhythmic drugs based on patient-specific factors.

## Architecture

```
expert_system/
├── __init__.py
├── models/
│   ├── patient_context.py      # Patient clinical data model
│   └── decision_context.py     # Evaluation results model
├── rules/
│   ├── base_rule.py            # Abstract rule interface
│   ├── qtc_rules.py            # QTc prolongation rules
│   ├── renal_rules.py          # Renal function rules
│   └── interaction_rules.py    # Drug-drug interaction rules
├── engine/
│   └── rule_engine.py          # Core evaluation engine
└── README.md
```

## Features

### 1. **Patient Context Model**
- QTc interval (ms)
- eGFR (mL/min/1.73m²)
- Current medications
- Medical conditions
- Demographics (age, gender, weight)

### 2. **Decision Context Model**
- Contraindication status (yes/no)
- Clinical alerts (4 severity levels)
- Dose adjustment recommendations
- Detailed explanations for every decision
- Overall risk score (0-100)
- List of triggered rules

### 3. **Rule Types**

#### **QTc Rules**
- `HighQTcRule`: QTc > 500ms → Contraindicated
- `ModerateQTcRule`: 470-500ms → Dose reduction + monitoring
- `MildQTcRule`: 450-470ms → Monitoring recommended

#### **Renal Rules**
- `SevereRenalImpairmentRule`: eGFR < 30 → Critical dose reduction
- `ModerateRenalImpairmentRule`: eGFR 30-60 → Dose adjustment
- `MildRenalImpairmentRule`: eGFR 60-90 → Standard dosing with monitoring

#### **Drug Interaction Rules**
- `QTProlongingDrugInteractionRule`: Detects QT-prolonging medications
- `CYPInhibitorInteractionRule`: Identifies drugs affecting metabolism
- `BetaBlockerInteractionRule`: Warns of bradycardia risk

### 4. **Rule Engine**
- Evaluates patient against all rules
- Generates explainable decisions
- Supports enabling/disabling rules
- Batch evaluation capability

## API Endpoints

### `POST /hp_proto/api/evaluate`
Evaluate drug safety for a single patient.

**Request:**
```json
{
  "patient_id": "P12345",
  "qtc": 485,
  "egfr": 42,
  "medications": ["metoprolol", "clarithromycin"],
  "conditions": ["hypertension", "copd"],
  "age": 68,
  "gender": "F"
}
```

**Response:**
```json
{
  "contraindicated": false,
  "alerts": [
    {
      "message": "Moderate QTc prolongation: 485ms",
      "severity": "high",
      "rule_name": "ModerateQTcRule",
      "category": "cardiac"
    },
    {
      "message": "Moderate renal impairment: eGFR 42 mL/min/1.73m²",
      "severity": "high",
      "rule_name": "ModerateRenalImpairmentRule",
      "category": "renal"
    }
  ],
  "explanations": [
    "QTc interval is moderately prolonged at 485ms...",
    "Moderate renal impairment detected with eGFR of 42..."
  ],
  "dose_adjustment": {
    "adjusted_dose": "Reduce to 50-75% of standard dose",
    "reason": "Moderate renal impairment (eGFR: 42 mL/min/1.73m²)"
  },
  "risk_score": 50,
  "triggered_rules": ["ModerateQTcRule", "ModerateRenalImpairmentRule"]
}
```

### `POST /hp_proto/api/evaluate/batch`
Evaluate multiple patients in one request.

### `GET /hp_proto/api/evaluate/rules`
Get information about loaded rules.

### `GET /hp_proto/api/evaluate/example`
Get example patient scenarios for testing.

### `POST /hp_proto/api/evaluate/rules/{rule_name}/enable`
Enable a specific rule.

### `POST /hp_proto/api/evaluate/rules/{rule_name}/disable`
Disable a specific rule.

## Usage Examples

### Python Client

```python
import requests

# Patient data
patient = {
    "patient_id": "P001",
    "qtc": 520,
    "egfr": 75,
    "medications": ["amiodarone", "metoprolol"],
    "conditions": ["atrial fibrillation"],
    "age": 72,
    "gender": "M"
}

# Evaluate
response = requests.post(
    "http://localhost:8000/hp_proto/api/evaluate",
    json=patient
)

decision = response.json()

# Check results
if decision["contraindicated"]:
    print("⚠️ CONTRAINDICATED")
    
for alert in decision["alerts"]:
    print(f"[{alert['severity'].upper()}] {alert['message']}")

print("\nExplanations:")
for explanation in decision["explanations"]:
    print(f"- {explanation}")
```

### Using the Rule Engine Directly

```python
from expert_system import RuleEngine, PatientContext

# Create engine
engine = RuleEngine()

# Create patient
patient = PatientContext(
    patient_id="P001",
    qtc=520,
    egfr=75,
    medications=["amiodarone", "metoprolol"],
    conditions=["atrial fibrillation"]
)

# Evaluate
decision = engine.evaluate(patient)

# Access results
print(f"Contraindicated: {decision.contraindicated}")
print(f"Risk Score: {decision.risk_score}")
print(f"Alerts: {len(decision.alerts)}")
```

## Extending the System

### Adding New Rules

```python
from expert_system.rules.base_rule import BaseRule
from expert_system.models.patient_context import PatientContext
from expert_system.models.decision_context import DecisionContext, AlertSeverity

class CustomRule(BaseRule):
    def __init__(self):
        super().__init__()
        self.category = "custom"
    
    def condition(self, patient: PatientContext) -> bool:
        # Define when rule should fire
        return patient.age > 80
    
    def action(self, patient: PatientContext, decision: DecisionContext) -> None:
        # Define what happens when rule fires
        decision.add_alert(
            message="Elderly patient - extra caution advised",
            severity=AlertSeverity.MODERATE,
            rule_name=self.name,
            category=self.category
        )
    
    def explanation(self, patient: PatientContext) -> str:
        return f"Patient is {patient.age} years old - elderly patients require careful monitoring"

# Add to engine
engine.add_rule(CustomRule())
```

## Clinical Validation

⚠️ **IMPORTANT**: This is a prototype system for educational/research purposes.

**Requirements for clinical use:**
1. Validation against clinical guidelines (ESC, ACC/AHA)
2. Testing with real patient data
3. Review by clinical experts (cardiologists, pharmacologists)
4. Integration with EHR systems
5. Regulatory compliance (FDA, CE marking)
6. Regular updates with new drug data

## Future Enhancements

### Short-term
- [ ] Drug-specific rules (amiodarone, sotalol, flecainide, etc.)
- [ ] Genetic factors (LQTS, CYP2D6 polymorphisms)
- [ ] Lab value trending (not just snapshots)
- [ ] Rule conflict resolution
- [ ] Severity-based rule prioritization

### Long-term
- [ ] Machine learning integration for risk prediction
- [ ] Integration with MIMIC-III patient data
- [ ] Clinical trial evidence linking
- [ ] Real-time ECG analysis integration
- [ ] Pharmacokinetic modeling
- [ ] Outcomes tracking and feedback loop

## Testing

```bash
# Test with example patients
curl -X GET http://localhost:8000/hp_proto/api/evaluate/example

# Get rules summary
curl -X GET http://localhost:8000/hp_proto/api/evaluate/rules

# Test evaluation
curl -X POST http://localhost:8000/hp_proto/api/evaluate \
  -H "Content-Type: application/json" \
  -d '{
    "qtc": 520,
    "egfr": 75,
    "medications": ["amiodarone"],
    "conditions": ["atrial fibrillation"]
  }'
```

## Medical References

1. **QTc Intervals**: Drew BJ, et al. "Prevention of Torsade de Pointes in Hospital Settings." Circulation. 2010.
2. **Renal Dosing**: Ashley C, Dunleavy A. "The Renal Drug Handbook." 4th edition.
3. **Drug Interactions**: Baxter K. "Stockley's Drug Interactions." 11th edition.
4. **Clinical Guidelines**: ESC Guidelines for Atrial Fibrillation (2020)

## License

Educational/Research Use Only - Not for Clinical Decision Making
