"""
Benchmark runner: compares three clinical decision modes
  A — expert_only  : RuleEngine only, no LLM
  B — llm_only     : raw OpenAI chat, no rules
  C — full_pipeline: expert system + RAG + LLM (Phase 2 endpoint logic)
"""
from __future__ import annotations

import time
from typing import Any, Literal

from pydantic import BaseModel

from expert_system import RuleEngine, PatientContext
from api.services.ai_service import AIModelService
from api.benchmarks import metrics as m_module

Mode = Literal["expert_only", "llm_only", "full_pipeline"]


class BenchmarkCase(BaseModel):
    case_id: str
    description: str
    patient: PatientContext
    question: str
    ground_truth: dict[str, Any]  # keys: expected_contraindicated, expected_alert_categories, expected_dose_adjustment


class BenchmarkResult(BaseModel):
    case_id: str
    mode: Mode
    contraindicated: bool
    risk_score: int
    alerts: list[dict]          # list of {category, severity, message}
    dose_adjustment_present: bool
    response_text: str
    latency_ms: float


class ModeReport(BaseModel):
    mode: Mode
    n_cases: int
    mean_recall: float
    mean_precision: float
    mean_contraindication_accuracy: float
    mean_dose_adjustment_accuracy: float
    mean_latency_ms: float


class BenchmarkReport(BaseModel):
    reports: list[ModeReport]
    raw_results: list[BenchmarkResult]


class BenchmarkRunner:
    def __init__(self, model: str | None = None):
        self._model = model

    # ------------------------------------------------------------------
    # Single-mode runners
    # ------------------------------------------------------------------

    def run_expert_only(self, case: BenchmarkCase) -> BenchmarkResult:
        t0 = time.perf_counter()
        engine = RuleEngine()
        decision = engine.evaluate(case.patient)
        latency = (time.perf_counter() - t0) * 1000

        alerts = [
            {"category": a.category, "severity": a.severity.value if hasattr(a.severity, "value") else str(a.severity), "message": a.message}
            for a in decision.alerts
        ]
        summary = (
            f"Contraindicated: {decision.contraindicated}. "
            f"Risk score: {decision.risk_score}/100. "
            f"Alerts: {len(alerts)}. "
            + "; ".join(a["message"] for a in alerts[:3])
        )
        return BenchmarkResult(
            case_id=case.case_id,
            mode="expert_only",
            contraindicated=decision.contraindicated,
            risk_score=decision.risk_score,
            alerts=alerts,
            dose_adjustment_present=decision.dose_adjustment is not None,
            response_text=summary,
            latency_ms=latency,
        )

    def run_llm_only(self, case: BenchmarkCase) -> BenchmarkResult:
        t0 = time.perf_counter()
        ai = AIModelService()
        med_line = ", ".join(case.patient.medications) or "none"
        system_prompt = (
            "You are a clinical pharmacology AI assistant. "
            "Answer concisely whether the patient's current therapy is safe, "
            "identify any contraindications or drug interactions, and note if dose adjustment is needed."
        )
        user_msg = (
            f"Patient: age {case.patient.age}, gender {case.patient.gender}, "
            f"QTc {case.patient.qtc} ms, eGFR {case.patient.egfr} mL/min/1.73m². "
            f"Medications: {med_line}. "
            f"Conditions: {', '.join(case.patient.conditions) or 'none'}. "
            f"Question: {case.question}"
        )
        response = ai.chat(
            messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": user_msg}],
            model=self._model,
            max_tokens=400,
        )
        latency = (time.perf_counter() - t0) * 1000

        # LLM-only: no structured output from expert system
        return BenchmarkResult(
            case_id=case.case_id,
            mode="llm_only",
            contraindicated=False,
            risk_score=0,
            alerts=[],
            dose_adjustment_present=False,
            response_text=response,
            latency_ms=latency,
        )

    def run_full_pipeline(self, case: BenchmarkCase) -> BenchmarkResult:
        t0 = time.perf_counter()
        engine = RuleEngine()
        decision = engine.evaluate(case.patient)

        # Optional RAG
        rag_chunks: list[str] = []
        try:
            from v011.retrieved_augumentation.rag_system import MedicalRAGSystem
            rag = MedicalRAGSystem()
            results = rag.retrieve(case.question, top_k=3)
            rag_chunks = [r.get("text", "") for r in results if r.get("text")]
        except Exception:
            pass

        alert_lines = "\n".join(
            f"  [{a.severity.value if hasattr(a.severity, 'value') else a.severity}] {a.category}: {a.message}"
            for a in decision.alerts
        )
        rag_section = "\n\nRelevant literature:\n" + "\n---\n".join(rag_chunks) if rag_chunks else ""
        system_prompt = (
            "You are a clinical decision support assistant. "
            f"Expert system result: contraindicated={decision.contraindicated}, "
            f"risk={decision.risk_score}/100.\nAlerts:\n{alert_lines or 'none'}"
            f"{rag_section}"
        )
        med_line = ", ".join(case.patient.medications) or "none"
        user_msg = (
            f"Patient: age {case.patient.age}, gender {case.patient.gender}, "
            f"QTc {case.patient.qtc} ms, eGFR {case.patient.egfr} mL/min/1.73m². "
            f"Medications: {med_line}. "
            f"Conditions: {', '.join(case.patient.conditions) or 'none'}. "
            f"Question: {case.question}"
        )
        response = AIModelService().chat(
            messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": user_msg}],
            model=self._model,
            max_tokens=400,
        )
        latency = (time.perf_counter() - t0) * 1000

        alerts = [
            {"category": a.category, "severity": a.severity.value if hasattr(a.severity, "value") else str(a.severity), "message": a.message}
            for a in decision.alerts
        ]
        return BenchmarkResult(
            case_id=case.case_id,
            mode="full_pipeline",
            contraindicated=decision.contraindicated,
            risk_score=decision.risk_score,
            alerts=alerts,
            dose_adjustment_present=decision.dose_adjustment is not None,
            response_text=response,
            latency_ms=latency,
        )

    # ------------------------------------------------------------------
    # Compare all modes
    # ------------------------------------------------------------------

    def compare(self, cases: list[BenchmarkCase], modes: list[Mode] | None = None) -> BenchmarkReport:
        if modes is None:
            modes = ["expert_only", "llm_only", "full_pipeline"]

        runner_map = {
            "expert_only": self.run_expert_only,
            "llm_only": self.run_llm_only,
            "full_pipeline": self.run_full_pipeline,
        }

        all_results: list[BenchmarkResult] = []
        for mode in modes:
            for case in cases:
                result = runner_map[mode](case)
                all_results.append(result)

        mode_reports: list[ModeReport] = []
        for mode in modes:
            mode_results = [r for r in all_results if r.mode == mode]
            mode_cases = {c.case_id: c for c in cases}
            recalls = [m_module.recall_alerts(r, mode_cases[r.case_id]) for r in mode_results]
            precisions = [m_module.precision_alerts(r, mode_cases[r.case_id]) for r in mode_results]
            contra_acc = [m_module.contraindication_accuracy(r, mode_cases[r.case_id]) for r in mode_results]
            dose_acc = [m_module.dose_adjustment_accuracy(r, mode_cases[r.case_id]) for r in mode_results]

            def _mean(vals: list[float]) -> float:
                return sum(vals) / len(vals) if vals else 0.0

            mode_reports.append(ModeReport(
                mode=mode,
                n_cases=len(mode_results),
                mean_recall=round(_mean(recalls), 4),
                mean_precision=round(_mean(precisions), 4),
                mean_contraindication_accuracy=round(_mean(contra_acc), 4),
                mean_dose_adjustment_accuracy=round(_mean(dose_acc), 4),
                mean_latency_ms=round(m_module.mean_latency(mode_results), 2),
            ))

        return BenchmarkReport(reports=mode_reports, raw_results=all_results)
