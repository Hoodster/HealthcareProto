"""MIMIC outcome vs LLM/RAG safety-signal comparison — explicit, documented fields."""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from api.services.mimic_service import get_heart_patients
from api.services.pipeline_service import PipelineService, normalize_approaches
from expert_system.rules.interaction_rules import ANTIARRHYTHMIC_DRUGS, QT_PROLONGING_DRUGS

OutcomeFilter = Literal["all", "died", "survived"]


class OutcomeComparisonRow(BaseModel):
    subject_id: int
    hadm_id: int
    mimic_died: bool = Field(description="MIMIC admissions.hospital_expire_flag == 1")
    primary_diagnosis: Optional[str] = None
    medication_count: int = 0
    qt_drug_count: int = 0
    antiarrhythmic_drugs: list[str] = Field(
        default_factory=list,
        description="Antiarrhythmic drugs (Vaughan-Williams I/III) from MIMIC prescriptions",
    )
    on_antiarrhythmic: bool = Field(
        default=False,
        description="Whether the patient was exposed to any antiarrhythmic drug",
    )
    icu_admitted: bool = Field(
        default=False,
        description="ICU stay during this admission (MIMIC icustays)",
    )
    los_days: Optional[float] = Field(
        default=None,
        description="Length of stay in days (dischtime - admittime)",
    )
    discharge_location: Optional[str] = None
    egfr: float
    expert_rule_tags: list[str] = Field(
        default_factory=list,
        description="Guideline tags from fired expert rules",
    )
    genai_safety_concern: Optional[bool] = None
    rag_safety_concern: Optional[bool] = None
    genai_detected_risks: list[str] = Field(default_factory=list)
    rag_detected_risks: list[str] = Field(default_factory=list)
    rag_sources: list[dict] = Field(
        default_factory=list,
        description="RAG sources actually used by rag (filename, doc_type, score) — proof RAG processed sources",
    )
    rag_sources_used: int = Field(
        default=0, description="Number of RAG sources retrieved for rag"
    )
    genai_response_excerpt: Optional[str] = None
    rag_response_excerpt: Optional[str] = None
    same_concern_genai_rag: Optional[bool] = None
    expert_safety_concern: Optional[bool] = None


class OutcomeComparisonSummary(BaseModel):
    """Descriptive comparison — NO classification metrics.

    MIMIC has no gold-standard label for "antiarrhythmic safety concern", so we
    do NOT compute precision/recall/F1. We report (2) descriptive association of
    each approach's concern signal with the death outcome, and (3) inter-method
    (dis)agreement used to surface case studies.
    """

    total_rows: int
    died_count: int
    survived_count: int
    on_antiarrhythmic_count: int = 0
    icu_admitted_count: int = 0
    # Stratified: antiarrhythmic × outcome
    expert_concern_among_antiarrhythmic_died_pct: Optional[float] = None
    genai_concern_among_antiarrhythmic_died_pct: Optional[float] = None
    rag_concern_among_antiarrhythmic_died_pct: Optional[float] = None
    expert_concern_among_antiarrhythmic_survived_pct: Optional[float] = None
    genai_concern_among_antiarrhythmic_survived_pct: Optional[float] = None
    rag_concern_among_antiarrhythmic_survived_pct: Optional[float] = None
    # Stratified: ICU
    expert_concern_among_icu_pct: Optional[float] = None
    genai_concern_among_icu_pct: Optional[float] = None
    rag_concern_among_icu_pct: Optional[float] = None
    # Descriptive association with death — concern rate within each outcome group
    expert_concern_among_died_pct: Optional[float] = None
    genai_concern_among_died_pct: Optional[float] = None
    rag_concern_among_died_pct: Optional[float] = None
    expert_concern_among_survived_pct: Optional[float] = None
    genai_concern_among_survived_pct: Optional[float] = None
    rag_concern_among_survived_pct: Optional[float] = None
    # Overall concern rates (selectivity)
    expert_concern_pct: Optional[float] = None
    genai_concern_pct: Optional[float] = None
    rag_concern_pct: Optional[float] = None
    # (3) Inter-method agreement (genai vs rag) — supports disagreement case studies
    genai_rag_agreement_pct: Optional[float] = None
    genai_only_concern: int = 0
    rag_only_concern: int = 0
    both_concern: int = 0
    neither_concern: int = 0
    disagreement_count: int = Field(
        default=0, description="Rows where expert/GenAI/RAG signals are not all equal"
    )


class OutcomeComparisonReport(BaseModel):
    methodology: str = Field(
        default="See study_example/METHODOLOGY.md — mimic_died is MIMIC fact; "
        "safety_concern is system signal from code-defined rules."
    )
    approaches: list[str]
    outcome_filter: OutcomeFilter
    summary: OutcomeComparisonSummary
    rows: list[OutcomeComparisonRow]
    next_offset: Optional[int] = Field(
        default=None,
        description="Resume cursor for pagination: pass as ?offset= to fetch the next page. "
        "None means the patient list was exhausted.",
    )


def _excerpt(text: Optional[str], limit: int = 280) -> Optional[str]:
    if not text:
        return None
    t = " ".join(text.split())
    return t[:limit] + ("…" if len(t) > limit else "")


def _primary_diagnosis(patient_raw: dict, hadm_id: int) -> Optional[str]:
    diagnoses = patient_raw.get("diagnoses", [])
    cardiac = [d for d in diagnoses if d.get("hadm_id") == hadm_id]
    if not cardiac:
        return None
    primary = min(cardiac, key=lambda d: d.get("seq_num", 999))
    defn = primary.get("diagnosis_definition") or {}
    return defn.get("short_title") or primary.get("icd9_code")


class OutcomeComparisonService:
    @staticmethod
    def run(
        db: Session,
        *,
        limit: int = 30,
        offset: int = 0,
        approaches: Optional[list[str]] = None,
        outcome_filter: OutcomeFilter = "all",
        antiarrhythmic_only: bool = False,
    ) -> OutcomeComparisonReport:
        if approaches is None:
            approaches = ["genai", "rag"]
        else:
            approaches = normalize_approaches(approaches) or ["genai", "rag"]

        from api.services.mimic_service import get_patient_prescriptions

        pipeline = PipelineService()
        patients_raw = get_heart_patients(db, with_icu_stay=False)
        rows: list[OutcomeComparisonRow] = []
        next_offset: Optional[int] = None

        for idx in range(max(offset, 0), len(patients_raw)):
            # Stop once this page is full; expose a resume cursor so callers can
            # page through large cohorts without hitting the gateway timeout.
            if len(rows) >= limit:
                next_offset = idx
                break
            p = patients_raw[idx]
            subject_id = p["subject_id"]
            admissions = p.get("admissions") or []
            if not admissions:
                continue
            hadm_id = admissions[0].get("hadm_id")
            if hadm_id is None:
                continue

            # Cheap antiarrhythmic gate BEFORE expensive AI calls
            try:
                prescriptions = get_patient_prescriptions(subject_id, hadm_id, db)
            except Exception:
                prescriptions = []
            antiarrhythmics = sorted(
                {m.lower() for m in prescriptions} & ANTIARRHYTHMIC_DRUGS
            )
            if antiarrhythmic_only and not antiarrhythmics:
                continue

            try:
                result = pipeline.evaluate_mimic_patient(
                    subject_id,
                    hadm_id,
                    db,
                    approaches=["expert", *approaches],
                    include_raw_context=True,
                )
            except Exception:
                continue

            ref = result.reference_labels
            mimic_died = bool(ref.adverse_outcome)

            if outcome_filter == "died" and not mimic_died:
                continue
            if outcome_filter == "survived" and mimic_died:
                continue

            ctx = result.raw_patient_context or {}
            meds = ctx.get("medications") or []
            meds_lower = {m.lower() for m in meds}
            qt_count = len(meds_lower & QT_PROLONGING_DRUGS)
            antiarrhythmics = sorted(meds_lower & ANTIARRHYTHMIC_DRUGS) or antiarrhythmics

            genai_concern = None
            rag_concern = None
            expert_concern = None
            genai_risks: list[str] = []
            rag_risks: list[str] = []
            genai_excerpt = None
            rag_excerpt = None
            rag_sources: list[dict] = []
            rag_sources_used = 0

            if "expert" in result.metrics:
                expert_concern = result.metrics["expert"].detected_high_risk
            if result.genai_result and "genai" in result.metrics:
                genai_concern = result.metrics["genai"].detected_high_risk
                genai_risks = result.genai_result.detected_risks
                genai_excerpt = _excerpt(result.genai_result.response)
            if result.rag_result and "rag" in result.metrics:
                rag_concern = result.metrics["rag"].detected_high_risk
                rag_risks = result.rag_result.detected_risks
                rag_excerpt = _excerpt(result.rag_result.response)
                rag_sources = result.rag_result.rag_sources
                rag_sources_used = result.rag_result.sources_used

            same = None
            if genai_concern is not None and rag_concern is not None:
                same = genai_concern == rag_concern

            expert_tags: list[str] = []
            if result.expert_result:
                expert_tags = list(result.expert_result.rule_tags or [])

            rows.append(
                OutcomeComparisonRow(
                    subject_id=subject_id,
                    hadm_id=hadm_id,
                    mimic_died=mimic_died,
                    primary_diagnosis=_primary_diagnosis(p, hadm_id),
                    medication_count=len(meds),
                    qt_drug_count=qt_count,
                    antiarrhythmic_drugs=antiarrhythmics,
                    on_antiarrhythmic=bool(antiarrhythmics),
                    icu_admitted=ref.icu_admitted,
                    los_days=ref.los_days,
                    discharge_location=ref.discharge_location,
                    egfr=float(ctx.get("egfr", 90)),
                    expert_rule_tags=expert_tags,
                    genai_safety_concern=genai_concern,
                    rag_safety_concern=rag_concern,
                    genai_detected_risks=genai_risks,
                    rag_detected_risks=rag_risks,
                    rag_sources=rag_sources,
                    rag_sources_used=rag_sources_used,
                    genai_response_excerpt=genai_excerpt,
                    rag_response_excerpt=rag_excerpt,
                    same_concern_genai_rag=same,
                    expert_safety_concern=expert_concern,
                )
            )

        summary = OutcomeComparisonService._summarize(rows)
        return OutcomeComparisonReport(
            approaches=approaches,
            outcome_filter=outcome_filter,
            summary=summary,
            rows=rows,
            next_offset=next_offset,
        )

    @staticmethod
    def _summarize(rows: list[OutcomeComparisonRow]) -> OutcomeComparisonSummary:
        died = [r for r in rows if r.mimic_died]
        survived = [r for r in rows if not r.mimic_died]
        icu = [r for r in rows if r.icu_admitted]
        aa_died = [r for r in rows if r.on_antiarrhythmic and r.mimic_died]
        aa_survived = [r for r in rows if r.on_antiarrhythmic and not r.mimic_died]

        def _pct(concern_rows: list[OutcomeComparisonRow], attr: str) -> Optional[float]:
            vals = [getattr(r, attr) for r in concern_rows if getattr(r, attr) is not None]
            if not vals:
                return None
            return round(100.0 * sum(1 for v in vals if v) / len(vals), 1)

        paired = [
            r for r in rows
            if r.genai_safety_concern is not None and r.rag_safety_concern is not None
        ]
        agreement = None
        genai_only = rag_only = both = neither = 0
        for r in paired:
            g, rg = r.genai_safety_concern, r.rag_safety_concern
            if g and rg:
                both += 1
            elif g and not rg:
                genai_only += 1
            elif rg and not g:
                rag_only += 1
            else:
                neither += 1
        if paired:
            agreement = round(
                100.0 * sum(1 for r in paired if r.same_concern_genai_rag) / len(paired),
                1,
            )

        # (3) Disagreement = the three signals are not all equal (ignoring None)
        disagreement = 0
        for r in rows:
            signals = {
                v for v in (r.expert_safety_concern, r.genai_safety_concern, r.rag_safety_concern)
                if v is not None
            }
            if len(signals) > 1:
                disagreement += 1

        return OutcomeComparisonSummary(
            total_rows=len(rows),
            died_count=len(died),
            survived_count=len(survived),
            on_antiarrhythmic_count=sum(1 for r in rows if r.on_antiarrhythmic),
            icu_admitted_count=len(icu),
            expert_concern_among_antiarrhythmic_died_pct=_pct(aa_died, "expert_safety_concern"),
            genai_concern_among_antiarrhythmic_died_pct=_pct(aa_died, "genai_safety_concern"),
            rag_concern_among_antiarrhythmic_died_pct=_pct(aa_died, "rag_safety_concern"),
            expert_concern_among_antiarrhythmic_survived_pct=_pct(aa_survived, "expert_safety_concern"),
            genai_concern_among_antiarrhythmic_survived_pct=_pct(aa_survived, "genai_safety_concern"),
            rag_concern_among_antiarrhythmic_survived_pct=_pct(aa_survived, "rag_safety_concern"),
            expert_concern_among_icu_pct=_pct(icu, "expert_safety_concern"),
            genai_concern_among_icu_pct=_pct(icu, "genai_safety_concern"),
            rag_concern_among_icu_pct=_pct(icu, "rag_safety_concern"),
            expert_concern_among_died_pct=_pct(died, "expert_safety_concern"),
            genai_concern_among_died_pct=_pct(died, "genai_safety_concern"),
            rag_concern_among_died_pct=_pct(died, "rag_safety_concern"),
            expert_concern_among_survived_pct=_pct(survived, "expert_safety_concern"),
            genai_concern_among_survived_pct=_pct(survived, "genai_safety_concern"),
            rag_concern_among_survived_pct=_pct(survived, "rag_safety_concern"),
            expert_concern_pct=_pct(rows, "expert_safety_concern"),
            genai_concern_pct=_pct(rows, "genai_safety_concern"),
            rag_concern_pct=_pct(rows, "rag_safety_concern"),
            genai_rag_agreement_pct=agreement,
            genai_only_concern=genai_only,
            rag_only_concern=rag_only,
            both_concern=both,
            neither_concern=neither,
            disagreement_count=disagreement,
        )
