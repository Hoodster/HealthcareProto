"""Pilot cohort export — expert / LLM / RAG risk levels for thesis experiments."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Optional

from sqlalchemy.orm import Session

from api.services.ai_service import DEFAULT_LLM_MODELS, normalize_llm_provider
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

from api.services.outcome_comparison_service import OutcomeComparisonRow

OutcomeFilter = Literal["all", "died", "survived"]

# Tags that map to expert risk level 2 when expert_safety_concern is true (API export).
_EXPERT_CRITICAL_TAGS = frozenset(
    {
        "SOTALOL_RENAL_CONTRAINDICATION",
        "DOFETILIDE_RENAL_CONTRAINDICATION",
        "SOTALOL_QT_CONTRAINDICATION",
        "DOFETILIDE_QT_CONTRAINDICATION",
        "CLASS_IC_STRUCTURAL_HF",
        "DRONEDARONE_HF",
        "DRONEDARONE_PERMANENT_AF",
        "QT_INTERACTION",
        "QT_AAD_COMBO",
    }
)


def expert_risk_from_api_row(row: OutcomeComparisonRow) -> int:
    if not row.expert_safety_concern:
        return 0
    tags = set(row.expert_rule_tags or [])
    if tags & _EXPERT_CRITICAL_TAGS:
        return 2
    if tags:
        return 1
    # Older API without rule_tags: safety_concern implies critical/high alert
    return 2


def llm_risk_from_api_concern(concern: bool | None, risks: list[str]) -> int:
    if not concern:
        return 0
    if any(r in risks for r in ("contraindication", "qt_prolongation")):
        return 2
    return 1

PILOT_COLUMNS = [
    "subject_id",
    "hadm_id",
    "llm_provider",
    "llm_model",
    "outcome",
    "on_antiarrhythmic",
    "icu_admitted",
    "los_days",
    "expert_risk",
    "expert_tags",
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
    llm_provider: str
    llm_model: str
    outcome: str
    on_antiarrhythmic: bool
    icu_admitted: bool
    los_days: Optional[float]
    expert_risk: int
    expert_tags: str
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
    expert_agreement_pct: float = 0.0
    rag_agreement_pct: float = 0.0


class PilotService:
    @staticmethod
    def run(
        db: Session,
        *,
        limit: int = 100,
        offset: int = 0,
        outcome_filter: OutcomeFilter = "all",
        antiarrhythmic_only: bool = False,
        llm_provider: str = "openai",
        llm_model: Optional[str] = None,
    ) -> tuple[list[PilotRow], PilotSummary]:
        provider = normalize_llm_provider(llm_provider)
        model = llm_model or DEFAULT_LLM_MODELS[provider]
        pipeline = PipelineService(llm_provider=provider, llm_model=model)
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
            expert_tag_list: list[str] = []
            if result.expert_result:
                expert_level = expert_risk_level(result.expert_result.decision)
                expert_flag_list = expert_flags(result.expert_result.decision)
                expert_tag_list = list(result.expert_result.rule_tags or [])

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
                    llm_provider=provider,
                    llm_model=model,
                    outcome=outcome,
                    on_antiarrhythmic=on_aa,
                    icu_admitted=ref.icu_admitted,
                    los_days=ref.los_days,
                    expert_risk=expert_level,
                    expert_tags="|".join(expert_tag_list),
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
    def rows_from_outcome_comparison(
        api_rows: list[OutcomeComparisonRow],
        *,
        llm_provider: str = "openai",
        llm_model: Optional[str] = None,
    ) -> list[PilotRow]:
        """Map outcome-comparison API rows to pilot CSV rows (E1–E3 metrics)."""
        provider = normalize_llm_provider(llm_provider)
        model = llm_model or DEFAULT_LLM_MODELS[provider]
        rows: list[PilotRow] = []

        for row in api_rows:
            outcome = "died" if row.mimic_died else "survived"
            expert_level = expert_risk_from_api_row(row)
            llm_level = llm_risk_from_api_concern(row.genai_safety_concern, row.genai_detected_risks)
            rag_level = llm_risk_from_api_concern(row.rag_safety_concern, row.rag_detected_risks)
            expert_tag_list = list(row.expert_rule_tags or [])
            llm_flag_list = list(row.genai_detected_risks)
            rag_flag_list = list(row.rag_detected_risks)
            if row.rag_sources:
                rag_flag_list.append(f"sources:{len(row.rag_sources)}")
            expert_flag_list = expert_tag_list

            rows.append(
                PilotRow(
                    subject_id=row.subject_id,
                    hadm_id=row.hadm_id,
                    llm_provider=provider,
                    llm_model=model,
                    outcome=outcome,
                    on_antiarrhythmic=row.on_antiarrhythmic,
                    icu_admitted=row.icu_admitted,
                    los_days=row.los_days,
                    expert_risk=expert_level,
                    expert_tags="|".join(expert_tag_list),
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
                        rag_sources=row.rag_sources,
                        outcome=outcome,
                    ),
                    genai_excerpt=row.genai_response_excerpt or "",
                    rag_excerpt=row.rag_response_excerpt or "",
                    rag_sources="|".join(
                        f"{s.get('filename', '?')}:{s.get('score', '')}" for s in row.rag_sources
                    ),
                )
            )
        return rows

    @staticmethod
    def _summarize(rows: list[PilotRow]) -> PilotSummary:
        n = len(rows) or 1
        full = sum(1 for r in rows if r.agreement == "full")
        partial = sum(1 for r in rows if r.agreement == "partial")
        disagree = sum(1 for r in rows if r.agreement == "disagreement")
        rag_only = sum(1 for r in rows if r.rag_risk >= 1 and r.llm_risk == 0)
        genai_only = sum(1 for r in rows if r.llm_risk >= 1 and r.rag_risk == 0)
        expert_match = sum(
            1 for r in rows if r.expert_risk == r.llm_risk and r.expert_risk == r.rag_risk
        )
        rag_match = sum(1 for r in rows if r.expert_risk == r.rag_risk)
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
            expert_agreement_pct=round(100.0 * expert_match / n, 1),
            rag_agreement_pct=round(100.0 * rag_match / n, 1),
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
                    "llm_provider": r.llm_provider,
                    "llm_model": r.llm_model,
                    "outcome": r.outcome,
                    "on_antiarrhythmic": r.on_antiarrhythmic,
                    "icu_admitted": r.icu_admitted,
                    "los_days": r.los_days if r.los_days is not None else "",
                    "expert_risk": r.expert_risk,
                    "expert_tags": r.expert_tags,
                    "llm_risk": r.llm_risk,
                    "rag_risk": r.rag_risk,
                    "expert_flags": r.expert_flags,
                    "llm_flags": r.llm_flags,
                    "rag_flags": r.rag_flags,
                    "agreement": r.agreement,
                    "comment": r.comment,
                }
            )
