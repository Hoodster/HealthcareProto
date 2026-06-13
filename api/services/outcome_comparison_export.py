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
    "antiarrhythmic_drugs",
    "on_antiarrhythmic",
    "icu_admitted",
    "los_days",
    "discharge_location",
    "egfr",
    "expert_rule_tags",
    "expert_safety_concern",
    "genai_safety_concern",
    "rag_safety_concern",
    "same_concern_genai_rag",
    "genai_detected_risks",
    "rag_detected_risks",
    "rag_sources",
    "rag_sources_used",
    "genai_response_excerpt",
    "rag_response_excerpt",
]


def _sources_str(sources: list[dict]) -> str:
    return "|".join(
        f"{s.get('filename', '?')}:{s.get('score', '')}" for s in sources
    )


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
                "antiarrhythmic_drugs": "|".join(row.antiarrhythmic_drugs),
                "on_antiarrhythmic": row.on_antiarrhythmic,
                "icu_admitted": row.icu_admitted,
                "los_days": row.los_days if row.los_days is not None else "",
                "discharge_location": row.discharge_location or "",
                "egfr": row.egfr,
                "expert_rule_tags": "|".join(row.expert_rule_tags),
                "expert_safety_concern": row.expert_safety_concern,
                "genai_safety_concern": row.genai_safety_concern,
                "rag_safety_concern": row.rag_safety_concern,
                "same_concern_genai_rag": row.same_concern_genai_rag,
                "genai_detected_risks": "|".join(row.genai_detected_risks),
                "rag_detected_risks": "|".join(row.rag_detected_risks),
                "rag_sources": _sources_str(row.rag_sources),
                "rag_sources_used": row.rag_sources_used,
                "genai_response_excerpt": row.genai_response_excerpt or "",
                "rag_response_excerpt": row.rag_response_excerpt or "",
            })


def _fmt(v) -> str:
    return "—" if v is None else f"{v}"


def _concern(v) -> str:
    return "TAK" if v else ("nie" if v is not None else "—")


def _is_disagreement(row) -> bool:
    signals = {
        v for v in (row.expert_safety_concern, row.genai_safety_concern, row.rag_safety_concern)
        if v is not None
    }
    return len(signals) > 1


def write_markdown(report: OutcomeComparisonReport, path: Path) -> None:
    """Professor-friendly antiarrhythmic drug-safety report (Markdown tables).

    No classification metrics (MIMIC has no gold-standard safety label). Instead:
    (2) descriptive association of each approach's concern with the death outcome,
    (3) qualitative case studies where the approaches disagree.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    s = report.summary
    lines: list[str] = []

    lines.append("# Bezpieczeństwo leków przeciwarytmicznych — expert vs GenAI vs RAG")
    lines.append("")
    lines.append(
        f"Filtr: `{report.outcome_filter}` | Przypadki: **{s.total_rows}** "
        f"(zgony: {s.died_count}, przeżyli: {s.survived_count}; "
        f"na antyarytmiku: {s.on_antiarrhythmic_count}; ICU: {s.icu_admitted_count})."
    )
    lines.append("")
    lines.append(
        "> MIMIC **nie zawiera** etykiety „zagrożenie bezpieczeństwa leku”, więc raport "
        "**nie liczy** precyzji/czułości/F1. Pokazujemy (1) jak często każde podejście "
        "zgłasza obawę, (2) opisowy związek tej obawy ze zgonem oraz (3) studia przypadków, "
        "gdzie podejścia się różnią. To analiza retrospektywna, nie predykcja śmierci."
    )
    lines.append("")

    # Section 1: selectivity + descriptive association with death
    lines.append("## 1. Jak często zgłaszają obawę i jak to się ma do zgonu (opisowo)")
    lines.append("")
    lines.append("| Podejście | % obaw (ogółem) | % obaw wśród ZMARŁYCH | % obaw wśród PRZEŻYWAJĄCYCH |")
    lines.append("|---|---|---|---|")
    lines.append(
        f"| expert | {_fmt(s.expert_concern_pct)} | {_fmt(s.expert_concern_among_died_pct)} "
        f"| {_fmt(s.expert_concern_among_survived_pct)} |"
    )
    lines.append(
        f"| genai | {_fmt(s.genai_concern_pct)} | {_fmt(s.genai_concern_among_died_pct)} "
        f"| {_fmt(s.genai_concern_among_survived_pct)} |"
    )
    lines.append(
        f"| rag | {_fmt(s.rag_concern_pct)} | {_fmt(s.rag_concern_among_died_pct)} "
        f"| {_fmt(s.rag_concern_among_survived_pct)} |"
    )
    lines.append("")
    lines.append(
        "_Niższy „% obaw ogółem” = większa selektywność. Różnica między kolumną „zmarli” "
        "a „przeżywający” pokazuje, czy obawa wiąże się z gorszym wynikiem (opisowo, bez wnioskowania przyczynowego)._"
    )
    lines.append("")

    if s.on_antiarrhythmic_count:
        lines.append("### Antyarytmik × outcome (stratyfikacja)")
        lines.append("")
        lines.append("| Podejście | % obaw (AA + zmarli) | % obaw (AA + przeżyli) |")
        lines.append("|---|---|---|")
        lines.append(
            f"| expert | {_fmt(s.expert_concern_among_antiarrhythmic_died_pct)} "
            f"| {_fmt(s.expert_concern_among_antiarrhythmic_survived_pct)} |"
        )
        lines.append(
            f"| genai | {_fmt(s.genai_concern_among_antiarrhythmic_died_pct)} "
            f"| {_fmt(s.genai_concern_among_antiarrhythmic_survived_pct)} |"
        )
        lines.append(
            f"| rag | {_fmt(s.rag_concern_among_antiarrhythmic_died_pct)} "
            f"| {_fmt(s.rag_concern_among_antiarrhythmic_survived_pct)} |"
        )
        lines.append("")

    if s.icu_admitted_count:
        lines.append("### ICU (stratyfikacja)")
        lines.append("")
        lines.append("| Podejście | % obaw (ICU) |")
        lines.append("|---|---|")
        lines.append(f"| expert | {_fmt(s.expert_concern_among_icu_pct)} |")
        lines.append(f"| genai | {_fmt(s.genai_concern_among_icu_pct)} |")
        lines.append(f"| rag | {_fmt(s.rag_concern_among_icu_pct)} |")
        lines.append("")

    # Section 2: inter-method (dis)agreement
    lines.append("## 2. Zgodność i rozbieżności między podejściami")
    lines.append("")
    lines.append(
        f"Zgodność GenAI vs RAG: **{_fmt(s.genai_rag_agreement_pct)}%** "
        f"(oba: {s.both_concern}, tylko GenAI: {s.genai_only_concern}, "
        f"tylko RAG: {s.rag_only_concern}, żadne: {s.neither_concern})."
    )
    lines.append("")
    lines.append(
        f"Przypadki z **rozbieżnym** sygnałem (expert/GenAI/RAG nie wszystkie równe): "
        f"**{s.disagreement_count}** z {s.total_rows}."
    )
    lines.append("")

    # Section 3: qualitative case studies of disagreements
    disagreements = [r for r in report.rows if _is_disagreement(r)]
    lines.append("## 3. Studia przypadków — rozbieżności (z odpowiedziami AI)")
    lines.append("")
    if not disagreements:
        lines.append("_Brak rozbieżności w tym przebiegu — wszystkie podejścia zgodne._")
    else:
        for r in disagreements:
            anti = ", ".join(r.antiarrhythmic_drugs) or "brak"
            top_src = "—"
            if r.rag_sources:
                top = max(r.rag_sources, key=lambda s: s.get("score", 0) or 0)
                top_src = f"{top.get('filename', '?')} ({top.get('score', '')})"
            lines.append(
                f"### Pacjent {r.subject_id} — {r.primary_diagnosis or '—'} "
                f"(zgon: {'TAK' if r.mimic_died else 'nie'})"
            )
            lines.append("")
            lines.append(
                f"- Antyarytmiki: **{anti}** | leki QT: {r.qt_drug_count} | eGFR: {r.egfr:.0f}"
            )
            lines.append(
                f"- Sygnał — expert: **{_concern(r.expert_safety_concern)}**, "
                f"GenAI: **{_concern(r.genai_safety_concern)}**, RAG: **{_concern(r.rag_safety_concern)}**"
            )
            if r.expert_rule_tags:
                lines.append(f"- Expert rule tags: {', '.join(r.expert_rule_tags)}")
            lines.append(f"- Top źródło RAG: {top_src}")
            if r.genai_response_excerpt:
                lines.append(f"- GenAI: _{r.genai_response_excerpt}_")
            if r.rag_response_excerpt:
                lines.append(f"- RAG: _{r.rag_response_excerpt}_")
            lines.append("")

    lines.append("---")
    lines.append("")
    lines.append(
        "_Sygnał GenAI/RAG = strukturalny werdykt LLM per pacjent (`SAFETY_VERDICT`), nie detekcja "
        "słów kluczowych. Źródła RAG pokazują najwyżej ocenione źródło + score (różny per pacjent); "
        "korpus wytycznych jest niewielki, więc nazwy plików się powtarzają, ale dopasowanie chunków/score różnicuje przypadki._"
    )
    lines.append("")
    lines.append(
        "_Definicje sygnału bezpieczeństwa per podejście: zob. "
        "[study_example/METHODOLOGY.md](../study_example/METHODOLOGY.md)._"
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def print_summary(report: OutcomeComparisonReport) -> None:
    s = report.summary
    print("\n" + "=" * 72)
    print("ANTIARRHYTHMIC DRUG SAFETY — EXPERT vs GENAI vs RAG (descriptive)")
    print("=" * 72)
    print(
        f"Filter: {report.outcome_filter}  |  Rows: {s.total_rows}  "
        f"(died: {s.died_count}, survived: {s.survived_count}, "
        f"on antiarrhythmic: {s.on_antiarrhythmic_count})"
    )
    print(f"Approaches: {', '.join(report.approaches)}")
    print()
    print(f"{'approach':10} {'concern%':>9} {'amg died%':>10} {'amg surv%':>10}")
    rows = [
        ("expert", s.expert_concern_pct, s.expert_concern_among_died_pct, s.expert_concern_among_survived_pct),
        ("genai", s.genai_concern_pct, s.genai_concern_among_died_pct, s.genai_concern_among_survived_pct),
        ("rag", s.rag_concern_pct, s.rag_concern_among_died_pct, s.rag_concern_among_survived_pct),
    ]
    for name, overall, died, surv in rows:
        print(f"{name:10} {_fmt(overall):>9} {_fmt(died):>10} {_fmt(surv):>10}")
    print(f"\nGenAI vs RAG agreement: {s.genai_rag_agreement_pct}%")
    print(
        f"  both: {s.both_concern}  genai only: {s.genai_only_concern}  "
        f"rag only: {s.rag_only_concern}  neither: {s.neither_concern}"
    )
    print(f"Disagreement cases (expert/genai/rag not all equal): {s.disagreement_count}/{s.total_rows}")
