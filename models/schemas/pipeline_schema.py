"""Pipeline evaluation schemas."""

from typing import Optional
from pydantic import BaseModel, Field
from expert_system.models.decision_context import DecisionContext


class GroundTruth(BaseModel):
    """Ground truth for evaluation (A+B combined approach)."""
    
    is_high_risk: bool = Field(description="Overall risk classification")
    guideline_violations: list[str] = Field(
        default_factory=list,
        description="List of violated clinical guidelines"
    )
    adverse_outcome: bool = Field(
        default=False,
        description="Whether adverse outcome occurred (hospital_expire_flag=1)"
    )
    death_during_treatment: bool = Field(
        default=False,
        description="Whether death occurred during prescription period"
    )


class ApproachMetrics(BaseModel):
    """Metrics for a single approach."""
    
    detected_high_risk: bool = Field(description="Whether approach detected high risk")
    true_positive: Optional[bool] = Field(None, description="Correct high risk detection")
    false_positive: Optional[bool] = Field(None, description="Incorrect alarm")
    true_negative: Optional[bool] = Field(None, description="Correct safe classification")
    false_negative: Optional[bool] = Field(None, description="Missed high risk")
    
    # Summary metrics
    recall: Optional[float] = Field(None, ge=0, le=1, description="Recall/sensitivity")
    precision: Optional[float] = Field(None, ge=0, le=1, description="Precision")
    f1: Optional[float] = Field(None, ge=0, le=1, description="F1 score")


class ExpertSystemResult(BaseModel):
    """Result from expert system evaluation."""
    
    decision: DecisionContext = Field(description="Expert system decision")
    latency_ms: float = Field(description="Evaluation latency in milliseconds")


class GenAIResult(BaseModel):
    """Result from GenAI evaluation."""
    
    response: str = Field(description="AI-generated response")
    detected_risks: list[str] = Field(
        default_factory=list,
        description="Risks mentioned by AI"
    )
    latency_ms: float = Field(description="Generation latency in milliseconds")


class RAGFullResult(BaseModel):
    """Result from RAG + GenAI + Expert evaluation."""
    
    response: str = Field(description="AI-generated response with RAG context")
    sources_used: int = Field(description="Number of RAG documents retrieved")
    expert_alerts: list[str] = Field(
        default_factory=list,
        description="Expert system alerts included"
    )
    detected_risks: list[str] = Field(
        default_factory=list,
        description="Risks mentioned by AI"
    )
    latency_ms: float = Field(description="Total pipeline latency in milliseconds")


class PipelineComparisonResult(BaseModel):
    """Complete comparison result from pipeline evaluation."""
    
    subject_id: int = Field(description="MIMIC patient subject_id")
    hadm_id: int = Field(description="MIMIC admission hadm_id")
    
    # Approach results (optional based on requested approaches)
    expert_result: Optional[ExpertSystemResult] = None
    genai_result: Optional[GenAIResult] = None
    rag_full_result: Optional[RAGFullResult] = None
    
    # Ground truth and metrics
    ground_truth: GroundTruth = Field(description="Ground truth for this patient")
    metrics: dict[str, ApproachMetrics] = Field(
        default_factory=dict,
        description="Metrics per approach (expert/genai/rag_full)"
    )
    
    # Optional raw data
    raw_patient_context: Optional[dict] = Field(
        None,
        description="Raw PatientContext (if include_raw_context=True)"
    )


class CardiacPatientSummary(BaseModel):
    """Summary of a cardiac patient for testing."""
    
    subject_id: int
    hadm_id: int
    gender: Optional[str] = None
    age: Optional[int] = None
    diagnoses_count: int = Field(description="Number of diagnoses")
    primary_diagnosis: Optional[str] = Field(None, description="Primary cardiac diagnosis")
    has_prescriptions: bool = Field(description="Whether patient has prescription data")
    hospital_expire_flag: Optional[int] = Field(None, description="Death during hospitalization")
