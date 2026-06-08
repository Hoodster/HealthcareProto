"""MIMIC outcome vs LLM/RAG safety-signal comparison — explicit, documented fields."""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from api.services.mimic_service import get_heart_patients
from api.services.pipeline_service import PipelineService
from expert_system.rules.interaction_rules import QT_PROLONGING_DRUGS

OutcomeFilter = Literal["all", "died", "survived"]


class OutcomeComparisonRow(BaseModel):
    subject_id: int
    hadm_id: int
    mimic_died: bool = Field(description="MIMIC admissions.hospital_expire_flag == 1")
    primary_diagnosis: Optional[str] = None
    medication_count: int = 0
    qt_drug_count: int = 0
    egfr: float
    guideline_violations: list[str] = Field(
        description="Proxy rules only — NOT clinical ground truth"
    )
    genai_safety_concern: Optional[bool] = None
    rag_safety_concern: Optional[bool] = None
    genai_detected_risks: list[str] = Field(default_factory=list)
    rag_detected_risks: list[str] = Field(default_factory=list)
    genai_response_excerpt: Optional[str] = None
    rag_response_excerpt: Optional[str] = None
    same_concern_genai_rag: Optional[bool] = None
    expert_safety_concern: Optional[bool] = None


class OutcomeComparisonSummary(BaseModel):
    total_rows: int
    died_count: int
    survived_count: int
    genai_concern_among_died_pct: Optional[float] = None
    rag_concern_among_died_pct: Optional[float] = None
    genai_concern_among_survived_pct: Optional[float] = None
    rag_concern_among_survived_pct: Optional[float] = None
    genai_rag_agreement_pct: Optional[float] = None
    genai_only_concern: int = 0
    rag_only_concern: int = 0
    both_concern: int = 0
    neither_concern: int = 0


class OutcomeComparisonReport(BaseModel):
    methodology: str = Field(
        default="See study_example/METHODOLOGY.md — mimic_died is MIMIC fact; "
        "safety_concern is system signal from code-defined rules."
    )
    approaches: list[str]
    outcome_filter: OutcomeFilter
    summary: OutcomeComparisonSummary
    rows: list[OutcomeComparisonRow]


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
        approaches: Optional[list[str]] = None,
        outcome_filter: OutcomeFilter = "all",
    ) -> OutcomeComparisonReport:
        if approaches is None:
            approaches = ["genai", "rag_full"]

        pipeline = PipelineService()
        patients_raw = get_heart_patients(db, with_icu_stay=False)
        rows: list[OutcomeComparisonRow] = []

        for p in patients_raw:
            if len(rows) >= limit:
                break
            subject_id = p["subject_id"]
            admissions = p.get("admissions") or []
            if not admissions:
                continue
            hadm_id = admissions[0].get("hadm_id")
            if hadm_id is None:
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

            gt = result.ground_truth
            mimic_died = bool(gt.adverse_outcome)

            if outcome_filter == "died" and not mimic_died:
                continue
            if outcome_filter == "survived" and mimic_died:
                continue

            ctx = result.raw_patient_context or {}
            meds = ctx.get("medications") or []
            qt_count = len({m.lower() for m in meds} & QT_PROLONGING_DRUGS)

            genai_concern = None
            rag_concern = None
            expert_concern = None
            genai_risks: list[str] = []
            rag_risks: list[str] = []
            genai_excerpt = None
            rag_excerpt = None

            if "expert" in result.metrics:
                expert_concern = result.metrics["expert"].detected_high_risk
            if result.genai_result and "genai" in result.metrics:
                genai_concern = result.metrics["genai"].detected_high_risk
                genai_risks = result.genai_result.detected_risks
                genai_excerpt = _excerpt(result.genai_result.response)
            if result.rag_full_result and "rag_full" in result.metrics:
                rag_concern = result.metrics["rag_full"].detected_high_risk
                rag_risks = result.rag_full_result.detected_risks
                rag_excerpt = _excerpt(result.rag_full_result.response)

            same = None
            if genai_concern is not None and rag_concern is not None:
                same = genai_concern == rag_concern

            rows.append(
                OutcomeComparisonRow(
                    subject_id=subject_id,
                    hadm_id=hadm_id,
                    mimic_died=mimic_died,
                    primary_diagnosis=_primary_diagnosis(p, hadm_id),
                    medication_count=len(meds),
                    qt_drug_count=qt_count,
                    egfr=float(ctx.get("egfr", 90)),
                    guideline_violations=list(gt.guideline_violations),
                    genai_safety_concern=genai_concern,
                    rag_safety_concern=rag_concern,
                    genai_detected_risks=genai_risks,
                    rag_detected_risks=rag_risks,
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
        )

    @staticmethod
    def _summarize(rows: list[OutcomeComparisonRow]) -> OutcomeComparisonSummary:
        died = [r for r in rows if r.mimic_died]
        survived = [r for r in rows if not r.mimic_died]

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

        return OutcomeComparisonSummary(
            total_rows=len(rows),
            died_count=len(died),
            survived_count=len(survived),
            genai_concern_among_died_pct=_pct(died, "genai_safety_concern"),
            rag_concern_among_died_pct=_pct(died, "rag_safety_concern"),
            genai_concern_among_survived_pct=_pct(survived, "genai_safety_concern"),
            rag_concern_among_survived_pct=_pct(survived, "rag_safety_concern"),
            genai_rag_agreement_pct=agreement,
            genai_only_concern=genai_only,
            rag_only_concern=rag_only,
            both_concern=both,
            neither_concern=neither,
        )
