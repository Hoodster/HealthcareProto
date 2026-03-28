#!/usr/bin/env python3
"""
Test script for expert system demonstration.
Run: python -m expert_system.test_cases
"""

from expert_system import RuleEngine, PatientContext, DecisionContext
from expert_system.models.decision_context import AlertSeverity


def print_decision(patient_name: str, decision: DecisionContext):
    """Pretty print decision results."""
    print(f"\n{'='*80}")
    print(f"EVALUATION: {patient_name}")
    print('='*80)
    
    # Contraindication status
    status = "❌ CONTRAINDICATED" if decision.contraindicated else "✓ Not contraindicated"
    print(f"\nStatus: {status}")
    print(f"Risk Score: {decision.risk_score}/100")
    
    # Alerts
    if decision.alerts:
        print(f"\nAlerts ({len(decision.alerts)}):")
        for alert in decision.alerts:
            icon = {
                AlertSeverity.CRITICAL: "🔴",
                AlertSeverity.HIGH: "🟠",
                AlertSeverity.MODERATE: "🟡",
                AlertSeverity.LOW: "🔵"
            }[alert.severity]
            print(f"  {icon} [{alert.severity.upper()}] {alert.message}")
            print(f"     Category: {alert.category} | Rule: {alert.rule_name}")
    else:
        print("\n✓ No alerts")
    
    # Dose adjustment
    if decision.dose_adjustment:
        print(f"\nDose Adjustment:")
        print(f"  Recommended: {decision.dose_adjustment.adjusted_dose}")
        print(f"  Reason: {decision.dose_adjustment.reason}")
    
    # Explanations
    if decision.explanations:
        print(f"\nExplanations ({len(decision.explanations)}):")
        for i, exp in enumerate(decision.explanations, 1):
            print(f"  {i}. {exp[:100]}..." if len(exp) > 100 else f"  {i}. {exp}")
    
    # Triggered rules
    print(f"\nTriggered Rules: {', '.join(decision.triggered_rules)}")


def test_high_risk_cardiac():
    """Test case: High QTc + QT-prolonging drug."""
    patient = PatientContext(
        patient_id="TEST_001",
        qtc=520,
        egfr=75,
        medications=["amiodarone", "metoprolol", "aspirin"],
        conditions=["atrial fibrillation", "hypertension"],
        age=72,
        gender="M",
        weight=85
    )
    
    engine = RuleEngine()
    decision = engine.evaluate(patient)
    print_decision("High-Risk Cardiac Patient", decision)
    
    assert decision.contraindicated, "Should be contraindicated due to QTc > 500"
    assert decision.risk_score >= 65, "Risk score should be high"


def test_severe_renal_impairment():
    """Test case: Severe CKD requiring major dose adjustment."""
    patient = PatientContext(
        patient_id="TEST_002",
        qtc=430,
        egfr=25,
        medications=["lisinopril", "metformin", "furosemide"],
        conditions=["chronic kidney disease stage 4", "diabetes"],
        age=68,
        gender="F",
        weight=70
    )
    
    engine = RuleEngine()
    decision = engine.evaluate(patient)
    print_decision("Severe Renal Impairment Patient", decision)
    
    assert decision.dose_adjustment is not None, "Should have dose adjustment"
    assert any("renal" in alert.category for alert in decision.alerts), "Should have renal alerts"


def test_low_risk_patient():
    """Test case: Normal patient, no contraindications."""
    patient = PatientContext(
        patient_id="TEST_003",
        qtc=420,
        egfr=95,
        medications=["aspirin", "atorvastatin"],
        conditions=["hypertension"],
        age=55,
        gender="M",
        weight=80
    )
    
    engine = RuleEngine()
    decision = engine.evaluate(patient)
    print_decision("Low-Risk Patient", decision)
    
    assert not decision.contraindicated, "Should not be contraindicated"
    assert decision.risk_score < 30, "Risk score should be low"


def test_multiple_risk_factors():
    """Test case: Multiple overlapping risk factors."""
    patient = PatientContext(
        patient_id="TEST_004",
        qtc=485,
        egfr=42,
        medications=["clarithromycin", "metoprolol", "ketoconazole", "ondansetron"],
        conditions=["pneumonia", "hypertension", "ckd stage 3"],
        age=70,
        gender="F",
        weight=65
    )
    
    engine = RuleEngine()
    decision = engine.evaluate(patient)
    print_decision("Multiple Risk Factors Patient", decision)
    
    assert len(decision.alerts) >= 3, "Should have multiple alerts"
    assert decision.dose_adjustment is not None, "Should have dose adjustment"


def test_drug_interactions():
    """Test case: Multiple drug-drug interactions."""
    patient = PatientContext(
        patient_id="TEST_005",
        qtc=460,
        egfr=70,
        medications=["amiodarone", "metoprolol", "verapamil", "clarithromycin"],
        conditions=["atrial fibrillation"],
        age=65,
        gender="M",
        weight=88
    )
    
    engine = RuleEngine()
    decision = engine.evaluate(patient)
    print_decision("Drug Interaction Patient", decision)
    
    interaction_alerts = [a for a in decision.alerts if a.category == "interaction"]
    assert len(interaction_alerts) >= 2, "Should have multiple interaction alerts"


def test_batch_evaluation():
    """Test case: Batch evaluation of multiple patients."""
    patients = [
        PatientContext(patient_id=f"BATCH_{i}", qtc=400 + i*20, egfr=90 - i*10, 
                      medications=[], conditions=[], age=50+i, gender="M", weight=75.0)
        for i in range(5)
    ]
    
    engine = RuleEngine()
    decisions = engine.evaluate_batch(patients)
    
    print(f"\n{'='*80}")
    print("BATCH EVALUATION")
    print('='*80)
    print(f"\nEvaluated {len(decisions)} patients:")
    for i, (patient, decision) in enumerate(zip(patients, decisions), 1):
        status = "CONTRA" if decision.contraindicated else "OK"
        print(f"  {i}. {patient.patient_id}: QTc={patient.qtc}, eGFR={patient.egfr} "
              f"→ {status} (risk: {decision.risk_score}, alerts: {len(decision.alerts)})")
    
    assert len(decisions) == len(patients), "Should evaluate all patients"


def run_all_tests():
    """Run all test cases."""
    print("\n" + "="*80)
    print("EXPERT SYSTEM TEST SUITE")
    print("="*80)
    
    tests = [
        ("High-Risk Cardiac", test_high_risk_cardiac),
        ("Severe Renal Impairment", test_severe_renal_impairment),
        ("Low-Risk Patient", test_low_risk_patient),
        ("Multiple Risk Factors", test_multiple_risk_factors),
        ("Drug Interactions", test_drug_interactions),
        ("Batch Evaluation", test_batch_evaluation),
    ]
    
    passed = 0
    failed = 0
    
    for test_name, test_func in tests:
        try:
            test_func()
            passed += 1
            print(f"\n✓ {test_name} - PASSED")
        except AssertionError as e:
            failed += 1
            print(f"\n✗ {test_name} - FAILED: {str(e)}")
        except Exception as e:
            failed += 1
            print(f"\n✗ {test_name} - ERROR: {str(e)}")
    
    print(f"\n{'='*80}")
    print(f"TEST RESULTS: {passed} passed, {failed} failed")
    print('='*80)
    
    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    exit(0 if success else 1)
