"""Pipeline evaluation schemas."""

from typing import Optional
from pydantic import BaseModel, Field
from expert_system.models.decision_context import DecisionContext


class ReferenceLabels(BaseModel):
    """Retrospective reference labels — layers A and B kept separate (no composite gold standard)."""

    guideline_violations: list[str] = Field(
        default_factory=list,
        description="Layer B proxy tags from evaluate_guideline_violations() (17 rule families)",
    )
    adverse_outcome: bool = Field(
        default=False,
        description="Layer A: hospital_expire_flag == 1",
    )
    death_during_treatment: bool = Field(
        default=False,
        description="Death during admission (retrospective)",
    )
    icu_admitted: bool = Field(
        default=False,
        description="Layer A: ICU stay during this admission",
    )
    los_days: Optional[float] = Field(
        default=None,
        description="Layer A: length of stay in days",
    )
    discharge_location: Optional[str] = Field(
        default=None,
        description="Layer A: discharge disposition from MIMIC",
    )


class ApproachMetrics(BaseModel):
    """Per-approach safety signal (no classification metrics vs a gold label)."""

    detected_high_risk: bool = Field(description="Whether approach flagged high safety concern")
    risk_level: int = Field(
        default=0,
        ge=0,
        le=2,
        description="0=safe, 1=warning, 2=unsafe",
    )
    risk_flags: list[str] = Field(
        default_factory=list,
        description="Triggered rules or detected risk categories",
    )


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
    rag_sources: list[dict] = Field(
        default_factory=list,
        description="Retrieved sources actually used (filename, doc_type, score)"
    )
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
    rag_result: Optional[RAGFullResult] = None
    
    # Reference labels and per-approach signals
    reference_labels: ReferenceLabels = Field(
        description="Retrospective MIMIC reference (layers A/B, not a gold standard)",
    )
    metrics: dict[str, ApproachMetrics] = Field(
        default_factory=dict,
        description="Safety signals per approach (expert/genai/rag)",
    )
    
    # Optional raw data
    raw_patient_context: Optional[dict] = Field(
        None,
        description="Raw PatientContext (if include_raw_context=True)"
    )


class SafetyAlert(BaseModel):
    """Single expert-system alert projected for the safety report."""
    message: str
    severity: str
    category: str


class ApproachSafetyView(BaseModel):
    """Per-approach safety signal for the per-patient monitoring report."""
    safety_concern: Optional[bool] = Field(
        default=None, description="Whether this approach flagged a drug-safety concern"
    )
    detected_risks: list[str] = Field(default_factory=list)
    response: Optional[str] = Field(
        default=None, description="LLM response (GenAI/RAG only)"
    )
    sources_used: Optional[int] = Field(
        default=None, description="RAG sources retrieved (RAG only)"
    )
    rag_sources: list[dict] = Field(
        default_factory=list, description="RAG sources actually used (RAG only)"
    )


class AntiarrhythmicSafetyReport(BaseModel):
    """Per-patient antiarrhythmic drug-safety monitoring report.

    Combines the expert system, GenAI and RAG views on the safety of the
    patient's antiarrhythmic regimen. Retrospective MIMIC outcome is included
    for reference only (never used by the approaches at evaluation time).
    """
    subject_id: int
    hadm_id: int
    egfr: float
    medications: list[str] = Field(default_factory=list)
    antiarrhythmic_drugs: list[str] = Field(
        default_factory=list, description="Antiarrhythmic drugs (Vaughan-Williams I/III)"
    )
    on_antiarrhythmic: bool = False
    qt_prolonging_drugs: list[str] = Field(default_factory=list)

    contraindicated: bool = Field(
        default=False, description="Expert system marked the regimen contraindicated"
    )
    expert_risk_score: int = Field(default=0, ge=0, le=100)
    safety_score: float = Field(
        default=100.0, ge=0, le=100,
        description="100 - expert risk_score (100 = safest, 0 = highest risk)",
    )
    expert_alerts: list[SafetyAlert] = Field(default_factory=list)
    dose_adjustment: Optional[str] = None

    expert: ApproachSafetyView = Field(default_factory=ApproachSafetyView)
    genai: ApproachSafetyView = Field(default_factory=ApproachSafetyView)
    rag: ApproachSafetyView = Field(default_factory=ApproachSafetyView)

    approaches_agree: Optional[bool] = Field(
        default=None, description="Whether expert/GenAI/RAG concern signals all agree"
    )
    mimic_died: Optional[bool] = Field(
        default=None, description="Retrospective MIMIC outcome (reference only)"
    )
    recommendation: str = Field(
        default="", description="One-line safety recommendation summary"
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
