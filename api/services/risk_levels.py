"""Risk level mapping (0=safe, 1=warning, 2=unsafe) for pilot and reports."""

from __future__ import annotations

from typing import Optional

from expert_system.models.decision_context import DecisionContext


def expert_risk_level(decision: DecisionContext) -> int:
    """Map expert decision to 0/1/2."""
    if decision.contraindicated:
        return 2
    if any(a.severity.value == "critical" for a in decision.alerts):
        return 2
    if any(a.severity.value in ("high", "moderate") for a in decision.alerts):
        return 1
    return 0


def expert_flags(decision: DecisionContext) -> list[str]:
    """Compact flag list: rule_name:severity."""
    return [f"{a.rule_name}:{a.severity.value}" for a in decision.alerts]


def llm_risk_level(
    response: Optional[str],
    detected_risks: list[str],
    *,
    extract_verdict,
) -> int:
    """Map LLM/RAG response to 0/1/2."""
    verdict = extract_verdict(response or "")
    if verdict is True:
        if any(r in detected_risks for r in ("contraindication", "qt_prolongation")):
            return 2
        return 1
    if verdict is False:
        return 0
    if any(r in detected_risks for r in ("contraindication", "qt_prolongation")):
        return 2
    if detected_risks:
        return 1
    return 0


def three_way_agreement(expert: int, llm: int, rag: int) -> str:
    """full | partial | disagreement."""
    levels = {expert, llm, rag}
    if len(levels) == 1:
        return "full"
    if len(levels) == 2:
        return "partial"
    return "disagreement"


def auto_comment(
    *,
    expert: int,
    llm: int,
    rag: int,
    expert_flag_list: list[str],
    llm_flags: list[str],
    rag_flags: list[str],
    rag_sources: list[dict],
    outcome: str,
) -> str:
    """Short auto-generated comment for pilot CSV."""
    parts: list[str] = []
    if expert != llm:
        parts.append(f"Expert={expert} vs LLM={llm}")
    if llm != rag:
        parts.append(f"LLM={llm} vs RAG={rag}")
    if expert_flag_list and expert >= 2:
        parts.append(f"Expert: {expert_flag_list[0]}")
    if rag_sources and rag > llm:
        src = rag_sources[0].get("filename", "?")
        parts.append(f"RAG source: {src}")
    elif rag_flags and not llm_flags:
        parts.append("RAG detected risks LLM missed")
    if outcome == "died" and max(expert, llm, rag) == 0:
        parts.append("No concern despite death outcome")
    return "; ".join(parts) if parts else "All approaches aligned"
