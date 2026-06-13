"""Pipeline service for comparing Expert System, GenAI, and RAG approaches."""

import re
import time
from typing import Optional
from sqlalchemy.orm import Session

from api.services.mimic_service import build_mimic_patient_context
from api.services.ai_service import AIModelService
from api import models
from expert_system.engine.rule_engine import RuleEngine
from expert_system.models.patient_context import PatientContext
from expert_system.rules.interaction_rules import QT_PROLONGING_DRUGS
from models.schemas.pipeline_schema import (
    PipelineComparisonResult,
    ExpertSystemResult,
    GenAIResult,
    RAGFullResult,
    ReferenceLabels,
    ApproachMetrics,
)
from api.services.risk_levels import expert_risk_level, expert_flags, expert_tags_from_decision, llm_risk_level

# RAG imports
from retrieved_augmentation.abstract import Document
from retrieved_augmentation.embedder import OpenAIEmbedder
from retrieved_augmentation.document_processor import HealthcareDocumentProcessor
from retrieved_augmentation.augmentor import HealthcareContextAugmentor
from retrieved_augmentation.example_usage import InMemoryVectorStore, SimpleRetriever


def normalize_approaches(approaches: Optional[list[str]]) -> Optional[list[str]]:
    """Map legacy ``rag_full`` to ``rag`` so routes and pipeline stay in sync."""
    if approaches is None:
        return None
    return ["rag" if a == "rag_full" else a for a in approaches]


class PipelineService:
    """Service for evaluating MIMIC patients through multiple approaches."""
    
    def __init__(
        self,
        llm_provider: Optional[str] = None,
        llm_model: Optional[str] = None,
    ):
        import os

        self.rule_engine = RuleEngine()
        provider = (llm_provider or os.getenv("LLM_PROVIDER", "openai")).lower()
        model = llm_model or os.getenv("LLM_MODEL")
        self.llm_provider = provider
        self.ai_service = AIModelService(ai_provider=provider, model=model)
    
    def evaluate_mimic_patient(
        self,
        subject_id: int,
        hadm_id: int,
        db: Session,
        approaches: Optional[list[str]] = None,
        include_raw_context: bool = False,
    ) -> PipelineComparisonResult:
        """
        Evaluate a MIMIC patient through selected approaches.
        
        Args:
            subject_id: MIMIC patient subject_id
            hadm_id: MIMIC admission hadm_id
            db: Database session
            approaches: List of approaches to run ['expert', 'genai', 'rag']
                       Default: all three
            include_raw_context: Whether to include raw PatientContext in response
        
        Returns:
            PipelineComparisonResult with results from selected approaches
        """
        if approaches is None:
            approaches = ["expert", "genai", "rag"]
        else:
            approaches = normalize_approaches(approaches) or ["expert", "genai", "rag"]
        
        # Build patient context from MIMIC
        patient_context = build_mimic_patient_context(subject_id, hadm_id, db)
        
        # Retrospective outcome labels (layer A)
        reference_labels = self._compute_reference_labels(
            subject_id, hadm_id, db
        )
        
        # Initialize result
        result = PipelineComparisonResult(
            subject_id=subject_id,
            hadm_id=hadm_id,
            reference_labels=reference_labels,
            raw_patient_context=None
        )
        
        if include_raw_context:
            result.raw_patient_context = patient_context.model_dump()
        
        # Run selected approaches
        if "expert" in approaches:
            result.expert_result = self._approach_expert(patient_context)
            result.metrics["expert"] = self._compute_metrics(
                result.expert_result, approach="expert", patient_context=patient_context
            )
        
        if "genai" in approaches:
            result.genai_result = self._approach_genai(patient_context)
            result.metrics["genai"] = self._compute_metrics(
                result.genai_result, approach="genai"
            )
        
        if "rag" in approaches:
            result.rag_result = self._approach_rag(patient_context)
            result.metrics["rag"] = self._compute_metrics(
                result.rag_result, approach="rag"
            )
        
        return result
    
    def _approach_expert(self, patient_context: PatientContext) -> ExpertSystemResult:
        """Approach A: Expert System Only."""
        start_time = time.time()
        
        decision = self.rule_engine.evaluate(patient_context)
        from expert_system.rule_tags import expert_rule_tags

        latency_ms = (time.time() - start_time) * 1000
        
        return ExpertSystemResult(
            decision=decision,
            rule_tags=expert_rule_tags(decision, patient_context),
            latency_ms=latency_ms
        )
    
    def _approach_genai(self, patient_context: PatientContext) -> GenAIResult:
        """Approach B: GenAI Only (with patient context)."""
        start_time = time.time()
        
        # Format patient context for LLM
        prompt = self._format_patient_prompt(patient_context)
        prompt += (
            "\n\nQuestion: Evaluate THIS patient's antiarrhythmic / cardiac medication safety. "
            "Flag only clinically significant, patient-specific concerns (real drug interactions, "
            "contraindications, dangerous QT or renal dosing) — do NOT flag generic background risks.\n"
            + self._VERDICT_INSTRUCTION
        )

        response = self.ai_service.chat(prompt)
        
        # Extract mentioned risks (simple keyword matching)
        detected_risks = self._extract_risks_from_text(response)
        
        latency_ms = (time.time() - start_time) * 1000
        
        return GenAIResult(
            response=response,
            detected_risks=detected_risks,
            latency_ms=latency_ms
        )
    
    def _approach_rag(self, patient_context: PatientContext) -> RAGFullResult:
        """Approach C: RAG + GenAI + Expert System."""
        start_time = time.time()
        
        # Step 1: Run expert system to get alerts
        expert_decision = self.rule_engine.evaluate(patient_context)
        expert_alerts = [alert.message for alert in expert_decision.alerts]
        
        # Step 2: Patient summary + vector RAG (guidelines + uploaded docs)
        from api.rag_store import build_rag_query, retrieve_context_with_sources

        rag_query = build_rag_query(
            "cardiac medication safety drug interactions QT prolongation renal dosing contraindications",
            patient_context,
        )
        guideline_context, rag_sources = retrieve_context_with_sources(
            rag_query,
            top_k=5,
            patient_id=patient_context.patient_id,
        )
        patient_summary = self._create_rag_index(patient_context)

        rag_sections = ["# Patient summary\n" + patient_summary]
        if guideline_context:
            rag_sections.append("# Retrieved clinical knowledge\n" + guideline_context)
        rag_context = "\n\n".join(rag_sections)
        sources_used = len(rag_sources) + 4

        # Step 3: Format comprehensive prompt with RAG context + Expert alerts
        prompt = "# Retrieved Patient Information:\n\n"
        prompt += rag_context + "\n\n"
        
        if expert_alerts:
            prompt += "# Expert System Alerts:\n"
            for alert in expert_alerts:
                prompt += f"- {alert}\n"
            prompt += "\n"
        
        prompt += "# Question:\n"
        prompt += "Based on the patient information, retrieved guidelines, and expert system alerts above, assess THIS patient's antiarrhythmic / cardiac medication safety. Include:\n"
        prompt += "1. Key patient-specific risk factors\n"
        prompt += "2. Drug interaction concerns\n"
        prompt += "3. Clinical recommendations grounded in the retrieved guidelines\n"
        prompt += (
            "Flag only clinically significant, patient-specific concerns — do NOT flag generic background risks.\n"
            + self._VERDICT_INSTRUCTION
        )

        response = self.ai_service.chat(prompt)
        
        # Extract mentioned risks
        detected_risks = self._extract_risks_from_text(response)
        
        latency_ms = (time.time() - start_time) * 1000
        
        return RAGFullResult(
            response=response,
            sources_used=sources_used,
            rag_sources=rag_sources,
            expert_alerts=expert_alerts,
            detected_risks=detected_risks,
            latency_ms=latency_ms
        )
    
    def assess_antiarrhythmic_safety(
        self,
        subject_id: int,
        hadm_id: int,
        db: Session,
    ):
        """Per-patient antiarrhythmic drug-safety monitoring report.

        Reuses evaluate_mimic_patient (expert + GenAI + RAG) and projects the
        result into an AntiarrhythmicSafetyReport. Safety score reuses the
        expert system risk_score (100 - risk_score).
        """
        from expert_system.rules.interaction_rules import ANTIARRHYTHMIC_DRUGS
        from models.schemas.pipeline_schema import (
            AntiarrhythmicSafetyReport,
            ApproachSafetyView,
            SafetyAlert,
        )

        result = self.evaluate_mimic_patient(
            subject_id,
            hadm_id,
            db,
            approaches=["expert", "genai", "rag"],
            include_raw_context=True,
        )

        ctx = result.raw_patient_context or {}
        meds = ctx.get("medications") or []
        meds_lower = {m.lower() for m in meds}
        antiarrhythmics = sorted(meds_lower & ANTIARRHYTHMIC_DRUGS)
        qt_drugs = sorted(meds_lower & QT_PROLONGING_DRUGS)
        egfr = float(ctx.get("egfr", 90))

        decision = result.expert_result.decision if result.expert_result else None
        expert_alerts = (
            [
                SafetyAlert(message=a.message, severity=a.severity.value, category=a.category)
                for a in decision.alerts
            ]
            if decision
            else []
        )
        risk_score = decision.risk_score if decision else 0
        dose_adjustment = (
            decision.dose_adjustment.adjusted_dose
            if decision and decision.dose_adjustment
            else None
        )

        def _view(approach: str) -> ApproachSafetyView:
            concern = (
                result.metrics[approach].detected_high_risk
                if approach in result.metrics
                else None
            )
            view = ApproachSafetyView(safety_concern=concern)
            if approach == "genai" and result.genai_result:
                view.detected_risks = result.genai_result.detected_risks
                view.response = result.genai_result.response
            elif approach == "rag" and result.rag_result:
                view.detected_risks = result.rag_result.detected_risks
                view.response = result.rag_result.response
                view.sources_used = result.rag_result.sources_used
                view.rag_sources = result.rag_result.rag_sources
            elif approach == "expert" and decision:
                view.detected_risks = sorted({a.category for a in decision.alerts})
            return view

        expert_view = _view("expert")
        genai_view = _view("genai")
        rag_view = _view("rag")

        concerns = [
            v.safety_concern
            for v in (expert_view, genai_view, rag_view)
            if v.safety_concern is not None
        ]
        agree = (len(set(concerns)) == 1) if len(concerns) >= 2 else None

        contraindicated = bool(decision and decision.contraindicated)
        safety_score = round(max(0.0, 100.0 - risk_score), 1)

        if contraindicated:
            recommendation = (
                "CONTRAINDICATED antiarrhythmic regimen — switch agent / avoid. "
                + (f"Adjust: {dose_adjustment}." if dose_adjustment else "")
            )
        elif risk_score >= 40:
            recommendation = "High drug-safety risk — review antiarrhythmic therapy and monitor ECG."
        elif risk_score > 0:
            recommendation = "Moderate risk — monitor (ECG, renal function, drug levels)."
        else:
            recommendation = "No major antiarrhythmic safety flags detected."

        return AntiarrhythmicSafetyReport(
            subject_id=subject_id,
            hadm_id=hadm_id,
            egfr=egfr,
            medications=list(meds),
            antiarrhythmic_drugs=antiarrhythmics,
            on_antiarrhythmic=bool(antiarrhythmics),
            qt_prolonging_drugs=qt_drugs,
            contraindicated=contraindicated,
            expert_risk_score=risk_score,
            safety_score=safety_score,
            expert_alerts=expert_alerts,
            dose_adjustment=dose_adjustment,
            expert=expert_view,
            genai=genai_view,
            rag=rag_view,
            approaches_agree=agree,
            mimic_died=bool(result.reference_labels.adverse_outcome),
            recommendation=recommendation,
        )

    def _create_rag_index(self, patient_context: PatientContext) -> str:
        """Create temporary RAG index and return formatted context string."""
        # Semantic grouping: 4 documents per patient
        documents_content = []
        
        # 1. Cardiac conditions
        if patient_context.conditions:
            cardiac_conditions = [c for c in patient_context.conditions if any(
                term in c.lower() for term in ['heart', 'cardiac', 'atrial', 'fibrillation', 'flutter', 'arrhythmia', 'chf']
            )]
            if cardiac_conditions:
                documents_content.append(
                    f"Cardiac Conditions: {', '.join(cardiac_conditions)}"
                )
        
        # 2. Current medications
        if patient_context.medications:
            meds_with_notes = []
            for med in patient_context.medications:
                notes = []
                if med.lower() in QT_PROLONGING_DRUGS:
                    notes.append("QT-prolonging")
                if notes:
                    meds_with_notes.append(f"{med} ({', '.join(notes)})")
                else:
                    meds_with_notes.append(med)
            
            documents_content.append(
                f"Current Medications: {', '.join(meds_with_notes)}"
            )
        
        # 3. Renal function
        egfr_status = "normal" if patient_context.egfr >= 90 else \
                     "mild impairment" if patient_context.egfr >= 60 else \
                     "moderate impairment" if patient_context.egfr >= 30 else \
                     "severe impairment"
        
        documents_content.append(
            f"Renal Function: eGFR {patient_context.egfr} mL/min/1.73m² ({egfr_status})"
        )
        
        # 4. Demographics
        demographics_parts = []
        if patient_context.age:
            demographics_parts.append(f"Age: {patient_context.age} years")
        if patient_context.gender:
            demographics_parts.append(f"Gender: {patient_context.gender}")
        if patient_context.weight:
            demographics_parts.append(f"Weight: {patient_context.weight} kg")
        
        if demographics_parts:
            documents_content.append("Demographics: " + ", ".join(demographics_parts))
        
        return "\n".join(documents_content)
    
    def _format_patient_prompt(self, patient_context: PatientContext) -> str:
        """Format patient context as text prompt for LLM."""
        parts = []
        
        parts.append(f"Patient Information:")
        
        if patient_context.age:
            parts.append(f"- Age: {patient_context.age} years")
        if patient_context.gender:
            parts.append(f"- Gender: {patient_context.gender}")
        
        parts.append(f"- eGFR: {patient_context.egfr} mL/min/1.73m²")
        
        if patient_context.conditions:
            parts.append(f"- Conditions: {', '.join(patient_context.conditions)}")
        
        if patient_context.medications:
            parts.append(f"- Medications: {', '.join(patient_context.medications)}")
        
        return "\n".join(parts)
    
    _VERDICT_INSTRUCTION = (
        "End your answer with EXACTLY one line, nothing after it:\n"
        "SAFETY_VERDICT: HIGH_RISK   — if this patient's regimen has a clinically "
        "significant, patient-specific drug-safety concern\n"
        "SAFETY_VERDICT: LOW_RISK    — otherwise"
    )

    def _extract_safety_verdict(self, text: str) -> Optional[bool]:
        """Parse the structured per-patient verdict emitted by the LLM.

        Returns True for HIGH_RISK, False for LOW_RISK, None if absent
        (caller falls back to keyword heuristic for backward compatibility).
        """
        if not text:
            return None
        match = re.search(
            r"SAFETY_VERDICT\s*:\s*(HIGH_RISK|LOW_RISK)", text, re.IGNORECASE
        )
        if not match:
            return None
        return match.group(1).upper() == "HIGH_RISK"

    def _extract_risks_from_text(self, text: str) -> list[str]:
        """Extract risk keywords from AI response."""
        text_lower = text.lower()
        detected = []
        
        risk_keywords = {
            "qt_prolongation": ["qt", "qtc", "prolongation", "torsade"],
            "renal_impairment": ["renal", "kidney", "egfr", "creatinine"],
            "drug_interaction": ["interaction", "combining", "concurrent"],
            "contraindication": ["contraindicated", "avoid", "should not"],
            "bradycardia": ["bradycardia", "slow heart"],
            "hyperkalemia": ["hyperkalemia", "potassium", "high potassium"],
        }
        
        for risk_name, keywords in risk_keywords.items():
            if any(keyword in text_lower for keyword in keywords):
                detected.append(risk_name)
        
        return detected
    
    def _compute_reference_labels(
        self,
        subject_id: int,
        hadm_id: int,
        db: Session
    ) -> ReferenceLabels:
        """Layer A outcome only — expert carries operationalized guidelines."""
        from api.services.mimic_service import get_admission_outcome_features

        admission = db.get(models.MimicAdmission, hadm_id)
        adverse_outcome = False
        death_during_treatment = False
        if admission:
            adverse_outcome = bool(admission.hospital_expire_flag == 1)
            if adverse_outcome and admission.deathtime:
                death_during_treatment = True

        icu_admitted, los_days, discharge_location = get_admission_outcome_features(
            subject_id, hadm_id, db
        )

        return ReferenceLabels(
            adverse_outcome=adverse_outcome,
            death_during_treatment=death_during_treatment,
            icu_admitted=icu_admitted,
            los_days=los_days,
            discharge_location=discharge_location,
        )
    
    def _compute_metrics(
        self,
        approach_result,
        approach: str,
        patient_context: Optional[PatientContext] = None,
    ) -> ApproachMetrics:
        """Safety signal for an approach (no F1 / classification metrics)."""
        detected_high_risk = False
        risk_level = 0
        risk_flags: list[str] = []
        
        if approach == "expert":
            decision = approach_result.decision
            risk_level = expert_risk_level(decision)
            tags = approach_result.rule_tags or expert_tags_from_decision(
                decision, patient_context
            )
            risk_flags = tags + expert_flags(decision)
            detected_high_risk = decision.contraindicated or any(
                a.severity.value in ("critical", "high") for a in decision.alerts
            )
        
        elif approach == "genai":
            verdict = self._extract_safety_verdict(approach_result.response)
            risk_level = llm_risk_level(
                approach_result.response,
                approach_result.detected_risks,
                extract_verdict=self._extract_safety_verdict,
            )
            risk_flags = list(approach_result.detected_risks)
            if verdict is None:
                detected_high_risk = any(
                    r in approach_result.detected_risks
                    for r in ("qt_prolongation", "contraindication", "drug_interaction")
                )
            else:
                detected_high_risk = verdict

        elif approach == "rag":
            verdict = self._extract_safety_verdict(approach_result.response)
            risk_level = llm_risk_level(
                approach_result.response,
                approach_result.detected_risks,
                extract_verdict=self._extract_safety_verdict,
            )
            risk_flags = list(approach_result.detected_risks)
            if approach_result.rag_sources:
                risk_flags.append(f"rag_sources:{len(approach_result.rag_sources)}")
            if verdict is None:
                detected_high_risk = any(
                    r in approach_result.detected_risks
                    for r in ("qt_prolongation", "contraindication", "drug_interaction")
                )
            else:
                detected_high_risk = verdict
        
        return ApproachMetrics(
            detected_high_risk=detected_high_risk,
            risk_level=risk_level,
            risk_flags=risk_flags,
        )
