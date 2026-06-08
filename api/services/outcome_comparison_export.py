"""CSV/JSON export helpers for outcome comparison reports."""

from __future__ import annotations

import csv
from pathlib import Path

from api.services.outcome_comparison_service import OutcomeComparisonReport

CSV_COLUMNS = [
    "subject_id",
    "hadm_id",
    "mimic_died",
    "primary_diagnosis",
    "medication_count",
    "qt_drug_count",
    "egfr",
    "guideline_violations",
    "expert_safety_concern",
    "genai_safety_concern",
    "rag_safety_concern",
    "same_concern_genai_rag",
    "genai_detected_risks",
    "rag_detected_risks",
    "genai_response_excerpt",
    "rag_response_excerpt",
]


def write_csv(report: OutcomeComparisonReport, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        for row in report.rows:
            writer.writerow({
                "subject_id": row.subject_id,
                "hadm_id": row.hadm_id,
                "mimic_died": row.mimic_died,
                "primary_diagnosis": row.primary_diagnosis or "",
                "medication_count": row.medication_count,
                "qt_drug_count": row.qt_drug_count,
                "egfr": row.egfr,
                "guideline_violations": "|".join(row.guideline_violations),
                "expert_safety_concern": row.expert_safety_concern,
                "genai_safety_concern": row.genai_safety_concern,
                "rag_safety_concern": row.rag_safety_concern,
                "same_concern_genai_rag": row.same_concern_genai_rag,
                "genai_detected_risks": "|".join(row.genai_detected_risks),
                "rag_detected_risks": "|".join(row.rag_detected_risks),
                "genai_response_excerpt": row.genai_response_excerpt or "",
                "rag_response_excerpt": row.rag_response_excerpt or "",
            })


def print_summary(report: OutcomeComparisonReport) -> None:
    s = report.summary
    print("\n" + "=" * 72)
    print("MIMIC OUTCOME vs LLM / RAG")
    print("=" * 72)
    print(
        f"Filter: {report.outcome_filter}  |  Rows: {s.total_rows}  "
        f"(died: {s.died_count}, survived: {s.survived_count})"
    )
    print(f"Approaches: {', '.join(report.approaches)}")
    print()
    print("Safety concern among DIED in hospital:")
    print(f"  genai:    {s.genai_concern_among_died_pct}%")
    print(f"  rag_full: {s.rag_concern_among_died_pct}%")
    print()
    print("Safety concern among SURVIVED:")
    print(f"  genai:    {s.genai_concern_among_survived_pct}%")
    print(f"  rag_full: {s.rag_concern_among_survived_pct}%")
    print()
    print(f"LLM vs RAG agreement: {s.genai_rag_agreement_pct}%")
    print(
        f"  both: {s.both_concern}  genai only: {s.genai_only_concern}  "
        f"rag only: {s.rag_only_concern}  neither: {s.neither_concern}"
    )
