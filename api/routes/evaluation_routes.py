"""API routes for expert system drug safety evaluation."""

from typing import Annotated, List
from fastapi import APIRouter, HTTPException, Depends, Query
from expert_system.models.patient_context import PatientContext
from expert_system.models.decision_context import DecisionContext
from expert_system.engine.rule_engine import RuleEngine
from api.auth import get_current_user

router = APIRouter(prefix="/evaluate", tags=["expert-system"], dependencies=[Depends(get_current_user)])

# Global rule engine instance (singleton pattern)
_rule_engine = None


def get_rule_engine() -> RuleEngine:
    """Get or create rule engine instance."""
    global _rule_engine
    if _rule_engine is None:
        _rule_engine = RuleEngine()
    return _rule_engine


@router.post("", response_model=DecisionContext, summary="Evaluate drug safety for patient")
async def evaluate_patient(
    patient: PatientContext,
    engine: RuleEngine = Depends(get_rule_engine)
) -> DecisionContext:
    """
    Evaluate drug safety for a patient based on clinical context.

    This endpoint applies a rule-based expert system to evaluate whether
    antiarrhythmic drugs are safe and appropriate for the given patient.

    **Input:** Patient clinical context (QTc, eGFR, medications, conditions)

    **Output:** Decision context with:
    - Contraindication status
    - Clinical alerts (critical, high, moderate, low)
    - Dose adjustment recommendations
    - Detailed explanations for all decisions
    - Overall risk score (0-100)

    **Example scenarios:**
    - QTc > 500ms → Contraindicated due to torsade de pointes risk
    - eGFR < 30 → Severe dose reduction required
    - Patient on QT-prolonging drugs → Critical drug interaction alert
    """
    try:
        decision = engine.evaluate(patient)
        return decision
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error evaluating patient: {str(e)}"
        )


@router.post("/batch", response_model=List[DecisionContext], summary="Batch evaluate multiple patients")
async def evaluate_patients_batch(
    patients: List[PatientContext],
    engine: RuleEngine = Depends(get_rule_engine)
) -> List[DecisionContext]:
    """
    Evaluate drug safety for multiple patients in a single request.

    Useful for screening patient cohorts or analyzing historical data.
    """
    try:
        decisions = engine.evaluate_batch(patients)
        return decisions
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error in batch evaluation: {str(e)}"
        )


@router.get("/rules", summary="Get loaded rules information")
async def get_rules_info(
    engine: RuleEngine = Depends(get_rule_engine)
) -> dict:
    """
    Get information about currently loaded rules.

    Returns summary of all rules including:
    - Total count
    - Enabled/disabled status
    - Rules grouped by category
    - Individual rule details
    """
    return engine.get_rules_summary()

@router.get("/drugservice", summary="Drug service test")
async def get_drug_service_test():
    from api.services.drug_service import DrugService
    interactions = DrugService.check_interactions(["amiodarone", "metoprolol", "clarithromycin"])
    return {"interactions": interactions}


@router.post("/rules/{rule_name}/enable", summary="Enable a rule")
async def enable_rule(
    rule_name: str,
    engine: RuleEngine = Depends(get_rule_engine)
) -> dict:
    """Enable a specific rule by name."""
    success = engine.enable_rule(rule_name)
    if not success:
        raise HTTPException(status_code=404, detail=f"Rule not found: {rule_name}")
    return {"message": f"Rule '{rule_name}' enabled", "success": True}


@router.post("/rules/{rule_name}/disable", summary="Disable a rule")
async def disable_rule(
    rule_name: str,
    engine: RuleEngine = Depends(get_rule_engine)
) -> dict:
    """Disable a specific rule by name."""
    success = engine.disable_rule(rule_name)
    if not success:
        raise HTTPException(status_code=404, detail=f"Rule not found: {rule_name}")
    return {"message": f"Rule '{rule_name}' disabled", "success": True}

@router.post("/drugs/search", summary="Search for drug RXCUI")
async def search_drug_rxcui(
    drug_name: str,
    search: Annotated[int, Query(ge=0, le=9, description="0=exact, 1=normalized, 2=exact-or-normalized, 9=approximate")] = 2,
) -> dict:
    """Search for a drug's RxNorm RXCUI identifier."""
    from api.services.drug_service import DrugService, RxNormSearchMode
    rxcui = DrugService.get_rxcui(drug_name, search=search)  # type: ignore[arg-type]
    if rxcui is None:
        raise HTTPException(status_code=404, detail=f"RXCUI not found for drug: {drug_name}")
    return {"drug_name": drug_name, "rxcui": rxcui}

@router.get("/example", response_model=dict, summary="Get example patient contexts")
async def get_examples() -> dict:
    """
    Get example patient contexts for testing.

    Returns various clinical scenarios with expected outcomes.
    """
    return {
        "examples": [
            {
                "name": "High-risk cardiac patient",
                "description": "Severe QT prolongation with drug interaction",
                "patient": {
                    "patient_id": "EXAMPLE_001",
                    "qtc": 520,
                    "egfr": 75,
                    "medications": ["amiodarone", "metoprolol"],
                    "conditions": ["atrial fibrillation", "hypertension"],
                    "age": 72,
                    "gender": "M"
                },
                "expected_outcome": "Contraindicated - QTc > 500ms + QT-prolonging drug"
            },
            {
                "name": "Renal impairment patient",
                "description": "Moderate CKD requiring dose adjustment",
                "patient": {
                    "patient_id": "EXAMPLE_002",
                    "qtc": 430,
                    "egfr": 25,
                    "medications": ["lisinopril", "metformin"],
                    "conditions": ["chronic kidney disease", "diabetes"],
                    "age": 68,
                    "gender": "F"
                },
                "expected_outcome": "Severe dose reduction required - eGFR < 30"
            },
            {
                "name": "Low-risk patient",
                "description": "Normal parameters, no contraindications",
                "patient": {
                    "patient_id": "EXAMPLE_003",
                    "qtc": 420,
                    "egfr": 95,
                    "medications": ["aspirin"],
                    "conditions": ["hypertension"],
                    "age": 55,
                    "gender": "M"
                },
                "expected_outcome": "Safe - no alerts or contraindications"
            },
            {
                "name": "Multiple risk factors",
                "description": "Moderate QT + renal impairment + drug interactions",
                "patient": {
                    "patient_id": "EXAMPLE_004",
                    "qtc": 485,
                    "egfr": 42,
                    "medications": ["clarithromycin", "metoprolol", "ketoconazole"],
                    "conditions": ["pneumonia", "hypertension", "ckd stage 3"],
                    "age": 70,
                    "gender": "F"
                },
                "expected_outcome": "Multiple alerts - caution advised with dose reduction"
            }
        ]
    }
