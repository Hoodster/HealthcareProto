#!/usr/bin/env python3
"""Select 5–10 disagreement case studies from pilot CSV for thesis chapter."""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))


def _score_row(row: dict, *, cross_provider: bool = False) -> int:
    """Higher = more interesting for case study."""
    score = 0
    expert = int(row.get("expert_risk") or 0)
    llm = int(row.get("llm_risk") or 0)
    rag = int(row.get("rag_risk") or 0)
    outcome = row.get("outcome", "")

    if cross_provider:
        if row.get("openai_llm_risk") != row.get("claude_llm_risk"):
            score += 12
        if row.get("openai_rag_risk") != row.get("claude_rag_risk"):
            score += 10

    if expert >= 2 and llm == 0 and rag == 0:
        score += 10
    if rag > llm:
        score += 8
    if llm >= 1 and expert == 0 and not row.get("rag_flags"):
        score += 7
    if expert == 0 and rag >= 2:
        score += 9
    if outcome == "died" and max(expert, llm, rag) == 0:
        score += 6
    if outcome == "survived" and max(expert, llm, rag) >= 2:
        score += 5
    if row.get("agreement") == "disagreement":
        score += 4
    elif row.get("agreement") == "partial":
        score += 2
    return score


def _merge_provider_rows(openai_rows: list[dict], claude_rows: list[dict]) -> list[dict]:
    o_map = {(r["subject_id"], r["hadm_id"]): r for r in openai_rows}
    merged: list[dict] = []
    for cr in claude_rows:
        key = (cr["subject_id"], cr["hadm_id"])
        if key not in o_map:
            continue
        orow = o_map[key]
        merged.append(
            {
                **orow,
                "openai_llm_risk": orow.get("llm_risk"),
                "openai_rag_risk": orow.get("rag_risk"),
                "claude_llm_risk": cr.get("llm_risk"),
                "claude_rag_risk": cr.get("rag_risk"),
                "llm_provider": f"openai+claude",
            }
        )
    return merged


def select_cases(rows: list[dict], max_cases: int = 10, *, cross_provider: bool = False) -> list[dict]:
    ranked = sorted(rows, key=lambda r: _score_row(r, cross_provider=cross_provider), reverse=True)
    selected: list[dict] = []
    seen_patterns: set[str] = set()

    for row in ranked:
        if cross_provider:
            pattern = (
                f"{row.get('expert_risk')}-{row.get('openai_llm_risk')}-{row.get('claude_llm_risk')}-"
                f"{row.get('openai_rag_risk')}-{row.get('claude_rag_risk')}-{row.get('outcome')}"
            )
        else:
            pattern = f"{row.get('expert_risk')}-{row.get('llm_risk')}-{row.get('rag_risk')}-{row.get('outcome')}"
        if pattern in seen_patterns and len(selected) >= 5:
            continue
        seen_patterns.add(pattern)
        selected.append(row)
        if len(selected) >= max_cases:
            break
    return selected


def write_markdown(cases: list[dict], path: Path, source: Path, *, cross_provider: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    title = (
        "# Case studies — rozbieżności OpenAI vs Claude"
        if cross_provider
        else "# Case studies — rozbieżności expert / LLM / RAG"
    )
    lines = [
        title,
        "",
        f"Źródło: `{source}` | Przypadków: **{len(cases)}**",
        "",
    ]
    for i, row in enumerate(cases, 1):
        lines.append(f"## {i}. Pacjent {row['subject_id']} / admission {row['hadm_id']}")
        lines.append("")
        lines.append(
            f"- **Outcome:** {row.get('outcome', '—')} | ICU: {row.get('icu_admitted', '—')} | "
            f"LOS: {row.get('los_days', '—')}"
        )
        if cross_provider:
            lines.append(
                f"- **Ryzyko (0–2):** expert={row.get('expert_risk')} | "
                f"OpenAI LLM={row.get('openai_llm_risk')} RAG={row.get('openai_rag_risk')} | "
                f"Claude LLM={row.get('claude_llm_risk')} RAG={row.get('claude_rag_risk')}"
            )
        else:
            lines.append(
                f"- **Ryzyko (0–2):** expert={row.get('expert_risk')} | "
                f"LLM={row.get('llm_risk')} | RAG={row.get('rag_risk')} | "
                f"agreement={row.get('agreement')}"
            )
        lines.append(f"- **Expert tags:** {row.get('expert_tags') or '—'}")
        lines.append(f"- **Expert flags:** {row.get('expert_flags') or '—'}")
        if not cross_provider:
            lines.append(f"- **LLM flags:** {row.get('llm_flags') or '—'}")
            lines.append(f"- **RAG flags:** {row.get('rag_flags') or '—'}")
        lines.append(f"- **Komentarz:** {row.get('comment') or '—'}")
        lines.append("")

    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Select case studies from pilot CSV")
    parser.add_argument("--input", type=Path, default=Path("artifacts/pilot_100_openai.csv"))
    parser.add_argument("--claude-input", type=Path, default=None, help="Second CSV for OpenAI vs Claude cases")
    parser.add_argument("-o", "--output", type=Path, default=Path("artifacts/case_studies.md"))
    parser.add_argument("--max-cases", type=int, default=10)
    args = parser.parse_args()

    if args.claude_input:
        if not args.input.is_file() or not args.claude_input.is_file():
            print("Both --input and --claude-input must exist.")
            return 1
        with args.input.open(encoding="utf-8") as fh:
            openai_rows = list(csv.DictReader(fh))
        with args.claude_input.open(encoding="utf-8") as fh:
            claude_rows = list(csv.DictReader(fh))
        rows = _merge_provider_rows(openai_rows, claude_rows)
        cases = select_cases(rows, max_cases=args.max_cases, cross_provider=True)
        write_markdown(
            cases,
            args.output,
            Path(f"{args.input.name}+{args.claude_input.name}"),
            cross_provider=True,
        )
    else:
        if not args.input.is_file():
            print(f"Missing input: {args.input} — run scripts/run_pilot.py first.")
            return 1
        with args.input.open(encoding="utf-8") as fh:
            rows = list(csv.DictReader(fh))
        cases = select_cases(rows, max_cases=args.max_cases)
        write_markdown(cases, args.output, args.input)

    print(f"Selected {len(cases)} case studies → {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
