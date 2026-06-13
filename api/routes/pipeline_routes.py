"""API routes for pipeline evaluation (comparing Expert, GenAI, RAG approaches)."""

from typing import Optional
from fastapi import APIRouter, HTTPException, Depends, Query
from sqlalchemy.orm import Session

from api.db import get_db_session
from api.auth import get_current_user
from api.services.pipeline_service import PipelineService, normalize_approaches
from api.services.outcome_comparison_service import OutcomeComparisonService, OutcomeComparisonReport
from models.schemas.pipeline_schema import PipelineComparisonResult, AntiarrhythmicSafetyReport

router = APIRouter(
    prefix="/pipeline",
    tags=["pipeline"],
    dependencies=[Depends(get_current_user)]
)

# Singleton pipeline service
_pipeline_service = None


def get_pipeline_service() -> PipelineService:
    """Get or create pipeline service instance."""
    global _pipeline_service
    if _pipeline_service is None:
        _pipeline_service = PipelineService()
    return _pipeline_service


@router.post(
    "/evaluate-mimic/{subject_id}/{hadm_id}",
    response_model=PipelineComparisonResult,
    summary="Evaluate MIMIC patient through multiple approaches"
)
async def evaluate_mimic_patient(
    subject_id: int,
    hadm_id: int,
    approaches: Optional[list[str]] = Query(
        default=["expert", "genai", "rag"],
        description="Approaches to evaluate: expert, genai, rag (rag_full accepted as alias)"
    ),
    include_raw_context: bool = Query(
        default=False,
        description="Include raw PatientContext in response"
    ),
    db: Session = Depends(get_db_session),
    service: PipelineService = Depends(get_pipeline_service)
) -> PipelineComparisonResult:
    """
    Evaluate a MIMIC-III patient through multiple clinical decision approaches.
    
    This endpoint compares three approaches for cardiac medication safety assessment:
    
    **Approach A - Expert System Only:**
    - Pure rule-based evaluation
    - Deterministic, explainable
    - Based on clinical guidelines (eGFR, drug interactions, QT-prolonging drugs)
    
    **Approach B - GenAI Only:**
    - LLM-based evaluation with patient context
    - Uses GPT-4o to analyze patient data
    - Natural language risk assessment
    
    **Approach C - RAG + GenAI + Expert (Full Pipeline):**
    - Retrieval-Augmented Generation with patient data
    - Expert system alerts integrated
    - Comprehensive AI synthesis
    
    **Reference labels (layers A + B, separate — not a gold standard):**
    - Layer B proxy: ≥2 QT drugs, eGFR&lt;30
    - Layer A outcome: hospital_expire_flag, ICU, length of stay
    - Layers are **not** merged into a single classification target
    
    **Per-approach signals (no F1/precision/recall):**
    - `detected_high_risk` and `risk_level` (0=safe, 1=warning, 2=unsafe)
    - `risk_flags` — triggered rules or detected risk categories
    
    **Example Usage:**
    ```
    POST /pipeline/evaluate-mimic/40177/142345?approaches=expert&approaches=genai
    ```
    
    Args:
        subject_id: MIMIC-III patient subject_id
        hadm_id: MIMIC-III admission hadm_id
        approaches: List of approaches to run (default: all three)
        include_raw_context: Include raw PatientContext in response (default: false)
        
    Returns:
        PipelineComparisonResult with results from selected approaches,
        reference labels (layers A/B), and safety signals per approach
    """
    # Validate approaches
    valid_approaches = {"expert", "genai", "rag", "rag_full"}
    if approaches:
        invalid = set(approaches) - valid_approaches
        if invalid:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid approaches: {invalid}. Must be one of: {valid_approaches}"
            )
        approaches = normalize_approaches(approaches)
    
    try:
        result = service.evaluate_mimic_patient(
            subject_id=subject_id,
            hadm_id=hadm_id,
            db=db,
            approaches=approaches,
            include_raw_context=include_raw_context
        )
        return result
    
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error evaluating patient: {str(e)}"
        )


@router.get(
    "/outcome-comparison",
    response_model=OutcomeComparisonReport,
    summary="Compare LLM vs RAG against MIMIC in-hospital death outcomes",
)
def outcome_comparison(
    limit: int = Query(default=20, ge=1, le=200),
    offset: int = Query(
        default=0,
        ge=0,
        description="Patient index to start from (pagination cursor). Use response next_offset for next page.",
    ),
    outcome: str = Query(
        default="all",
        description="Filter: all | died | survived (MIMIC hospital_expire_flag)",
    ),
    approaches: list[str] = Query(
        default=["genai", "rag"],
        description="Approaches to compare (genai = LLM only, rag = RAG+LLM+expert; rag_full alias)",
    ),
    antiarrhythmic_only: bool = Query(
        default=False,
        description="Restrict cohort to patients exposed to antiarrhythmic drugs",
    ),
    db: Session = Depends(get_db_session),
):
    """
    Batch comparison for thesis work.

    - **mimic_died**: factual outcome from MIMIC (`hospital_expire_flag`)
    - **genai_safety_concern / rag_safety_concern**: system signal (see study_example/METHODOLOGY.md)

    Export CSV: `python scripts/run_comparison.py --limit 20`
    """
    if outcome not in ("all", "died", "survived"):
        raise HTTPException(status_code=400, detail="outcome must be all, died, or survived")
    valid = {"genai", "rag", "rag_full"}
    invalid = set(approaches) - valid
    if invalid:
        raise HTTPException(status_code=400, detail=f"Invalid approaches: {invalid}")
    approaches = normalize_approaches(approaches) or ["genai", "rag"]

    try:
        return OutcomeComparisonService.run(
            db,
            limit=limit,
            offset=offset,
            approaches=approaches,
            outcome_filter=outcome,  # type: ignore[arg-type]
            antiarrhythmic_only=antiarrhythmic_only,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/antiarrhythmic-safety/{subject_id}/{hadm_id}",
    response_model=AntiarrhythmicSafetyReport,
    summary="Per-patient antiarrhythmic drug-safety monitoring (expert + GenAI + RAG)",
)
def antiarrhythmic_safety(
    subject_id: int,
    hadm_id: int,
    db: Session = Depends(get_db_session),
    service: PipelineService = Depends(get_pipeline_service),
) -> AntiarrhythmicSafetyReport:
    """Monitor antiarrhythmic regimen safety via expert, GenAI and RAG."""
    try:
        return service.assess_antiarrhythmic_safety(subject_id, hadm_id, db)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
