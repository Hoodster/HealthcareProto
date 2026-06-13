"""API routes for pipeline evaluation (comparing Expert, GenAI, RAG approaches)."""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from api.config import get_claude_api_key, get_openai_api_key
from api.db import get_db_session
from api.auth import get_current_user
from api.llm_params import LLM_MODEL_QUERY, LLM_PROVIDER_QUERY, LlmProvider, provider_value
from api.services.ai_service import DEFAULT_LLM_MODELS, normalize_llm_provider
from api.services.pipeline_service import PipelineService, normalize_approaches
from api.services.outcome_comparison_service import OutcomeComparisonService, OutcomeComparisonReport
from models.schemas.pipeline_schema import PipelineComparisonResult, AntiarrhythmicSafetyReport

router = APIRouter(
    prefix="/pipeline",
    tags=["pipeline"],
    dependencies=[Depends(get_current_user)],
)


def _pipeline_service(
    llm_provider: LLM_PROVIDER_QUERY = None,
    llm_model: LLM_MODEL_QUERY = None,
) -> PipelineService:
    try:
        return PipelineService(
            llm_provider=provider_value(llm_provider),
            llm_model=llm_model,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get(
    "/llm-providers",
    summary="Available LLM providers for GenAI/RAG",
)
def list_llm_providers():
    """Which providers are configured and their default models."""
    return {
        "providers": [
            {
                "id": LlmProvider.openai.value,
                "default_model": DEFAULT_LLM_MODELS["openai"],
                "configured": bool(get_openai_api_key()),
                "usage": "GenAI/RAG completion; RAG embeddings always use OpenAI",
            },
            {
                "id": LlmProvider.claude.value,
                "default_model": DEFAULT_LLM_MODELS["claude"],
                "configured": bool(get_claude_api_key()),
                "usage": "GenAI/RAG completion only",
            },
        ],
        "openapi": {
            "pipeline_query": "llm_provider=openai|claude on evaluate-mimic, outcome-comparison, antiarrhythmic-safety",
            "chat_body": "llm_provider in POST /chats/send JSON (MessageIn)",
        },
    }


@router.post(
    "/evaluate-mimic/{subject_id}/{hadm_id}",
    response_model=PipelineComparisonResult,
    summary="Evaluate MIMIC patient through multiple approaches",
)
async def evaluate_mimic_patient(
    subject_id: int,
    hadm_id: int,
    approaches: Optional[list[str]] = Query(
        default=["expert", "genai", "rag"],
        description="Approaches to evaluate: expert, genai, rag (rag_full accepted as alias)",
    ),
    include_raw_context: bool = Query(
        default=False,
        description="Include raw PatientContext in response",
    ),
    llm_provider: LLM_PROVIDER_QUERY = None,
    llm_model: LLM_MODEL_QUERY = None,
    db: Session = Depends(get_db_session),
) -> PipelineComparisonResult:
    """
    Evaluate a MIMIC-III patient through multiple clinical decision approaches.

    **LLM switch:** query param `llm_provider` = `openai` or `claude` (optional `llm_model`).
    """
    service = _pipeline_service(llm_provider=llm_provider, llm_model=llm_model)
    valid_approaches = {"expert", "genai", "rag", "rag_full"}
    if approaches:
        invalid = set(approaches) - valid_approaches
        if invalid:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid approaches: {invalid}. Must be one of: {valid_approaches}",
            )
        approaches = normalize_approaches(approaches)

    try:
        return service.evaluate_mimic_patient(
            subject_id=subject_id,
            hadm_id=hadm_id,
            db=db,
            approaches=approaches,
            include_raw_context=include_raw_context,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error evaluating patient: {str(e)}") from e


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
    llm_provider: LLM_PROVIDER_QUERY = None,
    llm_model: LLM_MODEL_QUERY = None,
    db: Session = Depends(get_db_session),
):
    """
    Batch comparison for thesis work.

    **LLM switch:** query param `llm_provider` = `openai` or `claude`.
    """
    if outcome not in ("all", "died", "survived"):
        raise HTTPException(status_code=400, detail="outcome must be all, died, or survived")
    valid = {"genai", "rag", "rag_full"}
    invalid = set(approaches) - valid
    if invalid:
        raise HTTPException(status_code=400, detail=f"Invalid approaches: {invalid}")
    approaches = normalize_approaches(approaches) or ["genai", "rag"]

    try:
        provider = normalize_llm_provider(provider_value(llm_provider))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    try:
        PipelineService(llm_provider=provider, llm_model=llm_model)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    try:
        return OutcomeComparisonService.run(
            db,
            limit=limit,
            offset=offset,
            approaches=approaches,
            outcome_filter=outcome,  # type: ignore[arg-type]
            antiarrhythmic_only=antiarrhythmic_only,
            llm_provider=provider,
            llm_model=llm_model,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get(
    "/antiarrhythmic-safety/{subject_id}/{hadm_id}",
    response_model=AntiarrhythmicSafetyReport,
    summary="Per-patient antiarrhythmic drug-safety monitoring (expert + GenAI + RAG)",
)
def antiarrhythmic_safety(
    subject_id: int,
    hadm_id: int,
    llm_provider: LLM_PROVIDER_QUERY = None,
    llm_model: LLM_MODEL_QUERY = None,
    db: Session = Depends(get_db_session),
) -> AntiarrhythmicSafetyReport:
    """Monitor antiarrhythmic regimen safety. Query param `llm_provider`: openai | claude."""
    service = _pipeline_service(llm_provider=llm_provider, llm_model=llm_model)
    try:
        return service.assess_antiarrhythmic_safety(subject_id, hadm_id, db)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e
