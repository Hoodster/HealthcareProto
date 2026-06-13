"""Pilot cohort export — expert / LLM / RAG risk levels for thesis experiments."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Optional

from sqlalchemy.orm import Session

from api.services.mimic_service import get_heart_patients, get_patient_prescriptions
from api.services.pipeline_service import PipelineService
from api.services.risk_levels import (
    auto_comment,
    expert_flags,
    expert_risk_level,
    llm_risk_level,
    three_way_agreement,
)
from expert_system.rules.interaction_rules import ANTIARRHYTHMIC_DRUGS

OutcomeFilter = Literal["all", "died", "survived"]

PILOT_COLUMNS = [
    "subject_id",
    "hadm_id",
    "outcome",
    "on_antiarrhythmic",
    "icu_admitted",
    "los_days",
    "expert_risk",
    "llm_risk",
    "rag_risk",
    "expert_flags",
    "llm_flags",
    "rag_flags",
    "agreement",
    "comment",
]


@dataclass
class PilotRow:
    subject_id: int
    hadm_id: int
    outcome: str
    on_antiarrhythmic: bool
    icu_admitted: bool
    los_days: Optional[float]
    expert_risk: int
    llm_risk: int
    rag_risk: int
    expert_flags: str
    llm_flags: str
    rag_flags: str
    agreement: str
    comment: str
    genai_excerpt: str = ""
    rag_excerpt: str = ""
    rag_sources: str = ""


@dataclass
class PilotSummary:
    total: int
    full_agreement_pct: float
    partial_agreement_pct: float
    disagreement_pct: float
    died_count: int
    survived_count: int
    expert_flag_total: int
    llm_flag_total: int
    rag_flag_total: int
    rag_only_concern: int
    genai_only_concern: int


class PilotService:
    @staticmethod
    def run(
        db: Session,
        *,
        limit: int = 100,
        offset: int = 0,
        outcome_filter: OutcomeFilter = "all",
        antiarrhythmic_only: bool = False,
    ) -> tuple[list[PilotRow], PilotSummary]:
        pipeline = PipelineService()
        patients = get_heart_patients(db, with_icu_stay=False)
        rows: list[PilotRow] = []

        for idx in range(max(offset, 0), len(patients)):
            if len(rows) >= limit:
                break
            p = patients[idx]
            subject_id = p["subject_id"]
            admissions = p.get("admissions") or []
            if not admissions:
                continue
            hadm_id = admissions[0].get("hadm_id")
            if hadm_id is None:
                continue

            try:
                prescriptions = get_patient_prescriptions(subject_id, hadm_id, db)
            except Exception:
                prescriptions = []
            if antiarrhythmic_only and not ({m.lower() for m in prescriptions} & ANTIARRHYTHMIC_DRUGS):
                continue

            try:
                result = pipeline.evaluate_mimic_patient(
                    subject_id,
                    hadm_id,
                    db,
                    approaches=["expert", "genai", "rag"],
                )
            except Exception:
                continue

            ref = result.reference_labels
            outcome = "died" if ref.adverse_outcome else "survived"
            if outcome_filter == "died" and outcome != "died":
                continue
            if outcome_filter == "survived" and outcome != "survived":
                continue

            expert_level = 0
            expert_flag_list: list[str] = []
            if result.expert_result:
                expert_level = expert_risk_level(result.expert_result.decision)
                expert_flag_list = expert_flags(result.expert_result.decision)

            llm_level = 0
            llm_flag_list: list[str] = []
            genai_excerpt = ""
            if result.genai_result:
                llm_level = llm_risk_level(
                    result.genai_result.response,
                    result.genai_result.detected_risks,
                    extract_verdict=pipeline._extract_safety_verdict,
                )
                llm_flag_list = list(result.genai_result.detected_risks)
                genai_excerpt = (result.genai_result.response or "")[:280]

            rag_level = 0
            rag_flag_list: list[str] = []
            rag_excerpt = ""
            rag_sources_list: list[dict] = []
            if result.rag_result:
                rag_level = llm_risk_level(
                    result.rag_result.response,
                    result.rag_result.detected_risks,
                    extract_verdict=pipeline._extract_safety_verdict,
                )
                rag_flag_list = list(result.rag_result.detected_risks)
                if result.rag_result.rag_sources:
                    rag_flag_list.append(f"sources:{len(result.rag_result.rag_sources)}")
                rag_excerpt = (result.rag_result.response or "")[:280]
                rag_sources_list = result.rag_result.rag_sources

            meds_lower = set(prescriptions)
            on_aa = bool(meds_lower & ANTIARRHYTHMIC_DRUGS)

            rows.append(
                PilotRow(
                    subject_id=subject_id,
                    hadm_id=hadm_id,
                    outcome=outcome,
                    on_antiarrhythmic=on_aa,
                    icu_admitted=ref.icu_admitted,
                    los_days=ref.los_days,
                    expert_risk=expert_level,
                    llm_risk=llm_level,
                    rag_risk=rag_level,
                    expert_flags="|".join(expert_flag_list),
                    llm_flags="|".join(llm_flag_list),
                    rag_flags="|".join(rag_flag_list),
                    agreement=three_way_agreement(expert_level, llm_level, rag_level),
                    comment=auto_comment(
                        expert=expert_level,
                        llm=llm_level,
                        rag=rag_level,
                        expert_flag_list=expert_flag_list,
                        llm_flags=llm_flag_list,
                        rag_flags=rag_flag_list,
                        rag_sources=rag_sources_list,
                        outcome=outcome,
                    ),
                    genai_excerpt=genai_excerpt,
                    rag_excerpt=rag_excerpt,
                    rag_sources="|".join(
                        f"{s.get('filename', '?')}:{s.get('score', '')}" for s in rag_sources_list
                    ),
                )
            )

        return rows, PilotService._summarize(rows)

    @staticmethod
    def _summarize(rows: list[PilotRow]) -> PilotSummary:
        n = len(rows) or 1
        full = sum(1 for r in rows if r.agreement == "full")
        partial = sum(1 for r in rows if r.agreement == "partial")
        disagree = sum(1 for r in rows if r.agreement == "disagreement")
        rag_only = sum(1 for r in rows if r.rag_risk >= 1 and r.llm_risk == 0)
        genai_only = sum(1 for r in rows if r.llm_risk >= 1 and r.rag_risk == 0)
        return PilotSummary(
            total=len(rows),
            full_agreement_pct=round(100.0 * full / n, 1),
            partial_agreement_pct=round(100.0 * partial / n, 1),
            disagreement_pct=round(100.0 * disagree / n, 1),
            died_count=sum(1 for r in rows if r.outcome == "died"),
            survived_count=sum(1 for r in rows if r.outcome == "survived"),
            expert_flag_total=sum(len(r.expert_flags.split("|")) if r.expert_flags else 0 for r in rows),
            llm_flag_total=sum(len(r.llm_flags.split("|")) if r.llm_flags else 0 for r in rows),
            rag_flag_total=sum(len(r.rag_flags.split("|")) if r.rag_flags else 0 for r in rows),
            rag_only_concern=rag_only,
            genai_only_concern=genai_only,
        )


def write_pilot_csv(rows: list[PilotRow], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=PILOT_COLUMNS)
        writer.writeheader()
        for r in rows:
            writer.writerow(
                {
                    "subject_id": r.subject_id,
                    "hadm_id": r.hadm_id,
                    "outcome": r.outcome,
                    "on_antiarrhythmic": r.on_antiarrhythmic,
                    "icu_admitted": r.icu_admitted,
                    "los_days": r.los_days if r.los_days is not None else "",
                    "expert_risk": r.expert_risk,
                    "llm_risk": r.llm_risk,
                    "rag_risk": r.rag_risk,
                    "expert_flags": r.expert_flags,
                    "llm_flags": r.llm_flags,
                    "rag_flags": r.rag_flags,
                    "agreement": r.agreement,
                    "comment": r.comment,
                }
            )
