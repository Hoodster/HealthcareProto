"""Pipeline service for comparing Expert System, GenAI, and RAG approaches."""

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
    GroundTruth,
    ApproachMetrics,
)

# RAG imports
from retrieved_augmentation.abstract import Document
from retrieved_augmentation.embedder import OpenAIEmbedder
from retrieved_augmentation.document_processor import HealthcareDocumentProcessor
from retrieved_augmentation.augmentor import HealthcareContextAugmentor
from retrieved_augmentation.example_usage import InMemoryVectorStore, SimpleRetriever


class PipelineService:
    """Service for evaluating MIMIC patients through multiple approaches."""
    
    def __init__(self):
        self.rule_engine = RuleEngine()
        self.ai_service = AIModelService()
    
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
            approaches: List of approaches to run ['expert', 'genai', 'rag_full']
                       Default: all three
            include_raw_context: Whether to include raw PatientContext in response
        
        Returns:
            PipelineComparisonResult with results from selected approaches
        """
        if approaches is None:
            approaches = ["expert", "genai", "rag_full"]
        
        # Build patient context from MIMIC
        patient_context = build_mimic_patient_context(subject_id, hadm_id, db)
        
        # Compute ground truth
        ground_truth = self._compute_ground_truth(subject_id, hadm_id, patient_context, db)
        
        # Initialize result
        result = PipelineComparisonResult(
            subject_id=subject_id,
            hadm_id=hadm_id,
            ground_truth=ground_truth,
            raw_patient_context=None
        )
        
        if include_raw_context:
            result.raw_patient_context = patient_context.model_dump()
        
        # Run selected approaches
        if "expert" in approaches:
            result.expert_result = self._approach_expert(patient_context)
            result.metrics["expert"] = self._compute_metrics(
                result.expert_result, ground_truth, approach="expert"
            )
        
        if "genai" in approaches:
            result.genai_result = self._approach_genai(patient_context)
            result.metrics["genai"] = self._compute_metrics(
                result.genai_result, ground_truth, approach="genai"
            )
        
        if "rag_full" in approaches:
            result.rag_full_result = self._approach_rag_full(patient_context)
            result.metrics["rag_full"] = self._compute_metrics(
                result.rag_full_result, ground_truth, approach="rag_full"
            )
        
        return result
    
    def _approach_expert(self, patient_context: PatientContext) -> ExpertSystemResult:
        """Approach A: Expert System Only."""
        start_time = time.time()
        
        decision = self.rule_engine.evaluate(patient_context)
        
        latency_ms = (time.time() - start_time) * 1000
        
        return ExpertSystemResult(
            decision=decision,
            latency_ms=latency_ms
        )
    
    def _approach_genai(self, patient_context: PatientContext) -> GenAIResult:
        """Approach B: GenAI Only (with patient context)."""
        start_time = time.time()
        
        # Format patient context for LLM
        prompt = self._format_patient_prompt(patient_context)
        prompt += "\n\nQuestion: Evaluate this patient's cardiac medication safety. List any high-risk factors, drug interactions, or contraindications."
        
        response = self.ai_service.chat(prompt)
        
        # Extract mentioned risks (simple keyword matching)
        detected_risks = self._extract_risks_from_text(response)
        
        latency_ms = (time.time() - start_time) * 1000
        
        return GenAIResult(
            response=response,
            detected_risks=detected_risks,
            latency_ms=latency_ms
        )
    
    def _approach_rag_full(self, patient_context: PatientContext) -> RAGFullResult:
        """Approach C: RAG + GenAI + Expert System."""
        start_time = time.time()
        
        # Step 1: Run expert system to get alerts
        expert_decision = self.rule_engine.evaluate(patient_context)
        expert_alerts = [alert.message for alert in expert_decision.alerts]
        
        # Step 2: Create temporary RAG index with patient data
        rag_context = self._create_rag_index(patient_context)
        
        # Step 3: Format comprehensive prompt with RAG context + Expert alerts
        prompt = "# Retrieved Patient Information:\n\n"
        prompt += rag_context + "\n\n"
        
        if expert_alerts:
            prompt += "# Expert System Alerts:\n"
            for alert in expert_alerts:
                prompt += f"- {alert}\n"
            prompt += "\n"
        
        prompt += "# Question:\n"
        prompt += "Based on the patient information and expert system alerts above, provide a comprehensive assessment of this patient's cardiac medication safety. Include:\n"
        prompt += "1. Key risk factors\n"
        prompt += "2. Drug interaction concerns\n"
        prompt += "3. Clinical recommendations\n"
        
        response = self.ai_service.chat(prompt)
        
        # Extract mentioned risks
        detected_risks = self._extract_risks_from_text(response)
        
        latency_ms = (time.time() - start_time) * 1000
        
        return RAGFullResult(
            response=response,
            sources_used=4,  # cardiac, medications, renal, demographics
            expert_alerts=expert_alerts,
            detected_risks=detected_risks,
            latency_ms=latency_ms
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
            f"Renal Function: eGFR {patient_context.egfr} mL/min/1.73m² ({egfr_status}), QTc {patient_context.qtc} ms"
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
        
        parts.append(f"- QTc: {patient_context.qtc} ms")
        parts.append(f"- eGFR: {patient_context.egfr} mL/min/1.73m²")
        
        if patient_context.conditions:
            parts.append(f"- Conditions: {', '.join(patient_context.conditions)}")
        
        if patient_context.medications:
            parts.append(f"- Medications: {', '.join(patient_context.medications)}")
        
        return "\n".join(parts)
    
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
    
    def _compute_ground_truth(
        self,
        subject_id: int,
        hadm_id: int,
        patient_context: PatientContext,
        db: Session
    ) -> GroundTruth:
        """Compute ground truth using A+B combined approach."""
        guideline_violations = []
        
        # Warstwa 1: Guideline Proxy
        
        # Rule 1: ≥2 QT-prolonging drugs
        patient_drugs = {drug.lower().strip() for drug in patient_context.medications}
        qt_drugs = patient_drugs & QT_PROLONGING_DRUGS
        if len(qt_drugs) >= 2:
            guideline_violations.append("QT_INTERACTION")
        
        # Rule 2: Severe renal impairment
        if patient_context.egfr < 30:
            guideline_violations.append("SEVERE_RENAL_IMPAIRMENT")
        
        # Rule 3: Critical QTc
        if patient_context.qtc > 500:
            guideline_violations.append("CRITICAL_QTC")
        
        # Warstwa 2: Actual Outcome
        admission = db.get(models.MimicAdmission, hadm_id)
        
        adverse_outcome = False
        death_during_treatment = False
        
        if admission:
            adverse_outcome = bool(admission.hospital_expire_flag == 1)
            
            # Check if death occurred during treatment (if prescriptions exist)
            if adverse_outcome and admission.deathtime:
                # Simple heuristic: death during admission = death during treatment
                death_during_treatment = True
        
        # Combined: high_risk if guideline violated OR adverse outcome
        is_high_risk = bool(guideline_violations) or adverse_outcome
        
        return GroundTruth(
            is_high_risk=is_high_risk,
            guideline_violations=guideline_violations,
            adverse_outcome=adverse_outcome,
            death_during_treatment=death_during_treatment
        )
    
    def _compute_metrics(
        self,
        approach_result,
        ground_truth: GroundTruth,
        approach: str
    ) -> ApproachMetrics:
        """Compute metrics for an approach."""
        # Determine if approach detected high risk
        detected_high_risk = False
        
        if approach == "expert":
            # Expert: contraindicated OR high/critical alerts
            decision = approach_result.decision
            detected_high_risk = decision.contraindicated or any(
                alert.severity.value in ["critical", "high"] for alert in decision.alerts
            )
        
        elif approach == "genai":
            # GenAI: detected any serious risks
            detected_high_risk = any(
                risk in approach_result.detected_risks
                for risk in ["qt_prolongation", "contraindication", "drug_interaction"]
            )
        
        elif approach == "rag_full":
            # RAG+Full: detected risks or expert alerts present
            detected_high_risk = bool(approach_result.expert_alerts) or any(
                risk in approach_result.detected_risks
                for risk in ["qt_prolongation", "contraindication", "drug_interaction"]
            )
        
        # Confusion matrix
        true_positive = detected_high_risk and ground_truth.is_high_risk
        false_positive = detected_high_risk and not ground_truth.is_high_risk
        true_negative = not detected_high_risk and not ground_truth.is_high_risk
        false_negative = not detected_high_risk and ground_truth.is_high_risk
        
        # Calculate metrics
        recall = None
        precision = None
        f1 = None
        
        if ground_truth.is_high_risk:  # For recall, we need positive cases
            recall = 1.0 if true_positive else 0.0
        
        if detected_high_risk:  # For precision, we need detections
            precision = 1.0 if true_positive else 0.0
        
        if recall is not None and precision is not None and (recall + precision) > 0:
            f1 = 2 * (precision * recall) / (precision + recall)
        
        return ApproachMetrics(
            detected_high_risk=detected_high_risk,
            true_positive=true_positive if true_positive else None,
            false_positive=false_positive if false_positive else None,
            true_negative=true_negative if true_negative else None,
            false_negative=false_negative if false_negative else None,
            recall=recall,
            precision=precision,
            f1=f1
        )
