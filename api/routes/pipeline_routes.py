"""API routes for pipeline evaluation (comparing Expert, GenAI, RAG approaches)."""

from typing import Optional
from fastapi import APIRouter, HTTPException, Depends, Query
from sqlalchemy.orm import Session

from api.db import get_db_session
from api.auth import get_current_user
from api.services.pipeline_service import PipelineService
from models.schemas.pipeline_schema import PipelineComparisonResult

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
        default=["expert", "genai", "rag_full"],
        description="Approaches to evaluate: expert, genai, rag_full"
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
    - Based on clinical guidelines (QTc, eGFR, drug interactions)
    
    **Approach B - GenAI Only:**
    - LLM-based evaluation with patient context
    - Uses GPT-4o to analyze patient data
    - Natural language risk assessment
    
    **Approach C - RAG + GenAI + Expert (Full Pipeline):**
    - Retrieval-Augmented Generation with patient data
    - Expert system alerts integrated
    - Comprehensive AI synthesis
    
    **Ground Truth (A+B Combined):**
    - Guideline violations (proxy rules): ≥2 QT drugs, eGFR<30, QTc>500
    - Actual outcomes (retrospective): hospital_expire_flag, death during treatment
    - Patient is high-risk if either condition is met
    
    **Metrics:**
    - Recall/Sensitivity: % of high-risk cases detected
    - Precision: % of alarms in truly high-risk cases
    - F1: Harmonic mean of precision and recall
    
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
        ground truth, and metrics for each approach
    """
    # Validate approaches
    valid_approaches = {"expert", "genai", "rag_full"}
    if approaches:
        invalid = set(approaches) - valid_approaches
        if invalid:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid approaches: {invalid}. Must be one of: {valid_approaches}"
            )
    
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
