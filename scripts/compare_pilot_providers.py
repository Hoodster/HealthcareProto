#!/usr/bin/env python3
"""Compare pilot CSVs from OpenAI and Claude — E1–E3 side-by-side + provider delta."""

from __future__ import annotations

import argparse
import csv
import sys
from dataclasses import dataclass
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))


@dataclass
class ProviderStats:
    name: str
    model: str
    n: int
    full_pct: float
    partial_pct: float
    disagree_pct: float
    avg_expert_flags: float
    avg_llm_flags: float
    avg_rag_flags: float
    rag_only: int
    genai_only: int
    llm_expert_agree_pct: float
    rag_expert_agree_pct: float
    concern_died_expert: float
    concern_died_llm: float
    concern_died_rag: float
    concern_survived_expert: float
    concern_survived_llm: float
    concern_survived_rag: float


def _read_csv(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def _key(row: dict) -> tuple[str, str]:
    return (row["subject_id"], row["hadm_id"])


def _pct(n: int, d: int) -> float:
    return round(100.0 * n / d, 1) if d else 0.0


def _concern_pct(rows: list[dict], outcome: str, field: str) -> float:
    subset = [r for r in rows if r.get("outcome") == outcome]
    if not subset:
        return 0.0
    hits = sum(1 for r in subset if int(r.get(field) or 0) >= 1)
    return _pct(hits, len(subset))


def _summarize(rows: list[dict], provider_name: str) -> ProviderStats:
    n = len(rows) or 1
    model = rows[0].get("llm_model", "—") if rows else "—"
    full = sum(1 for r in rows if r.get("agreement") == "full")
    partial = sum(1 for r in rows if r.get("agreement") == "partial")
    disagree = sum(1 for r in rows if r.get("agreement") == "disagreement")
    rag_only = sum(
        1 for r in rows if int(r.get("rag_risk") or 0) >= 1 and int(r.get("llm_risk") or 0) == 0
    )
    genai_only = sum(
        1 for r in rows if int(r.get("llm_risk") or 0) >= 1 and int(r.get("rag_risk") or 0) == 0
    )
    llm_agree = sum(1 for r in rows if int(r.get("expert_risk") or 0) == int(r.get("llm_risk") or 0))
    rag_agree = sum(1 for r in rows if int(r.get("expert_risk") or 0) == int(r.get("rag_risk") or 0))

    def _avg_flags(field: str) -> float:
        total = sum(len((r.get(field) or "").split("|")) if r.get(field) else 0 for r in rows)
        return round(total / n, 2)

    return ProviderStats(
        name=provider_name,
        model=model,
        n=len(rows),
        full_pct=_pct(full, n),
        partial_pct=_pct(partial, n),
        disagree_pct=_pct(disagree, n),
        avg_expert_flags=_avg_flags("expert_flags"),
        avg_llm_flags=_avg_flags("llm_flags"),
        avg_rag_flags=_avg_flags("rag_flags"),
        rag_only=rag_only,
        genai_only=genai_only,
        llm_expert_agree_pct=_pct(llm_agree, n),
        rag_expert_agree_pct=_pct(rag_agree, n),
        concern_died_expert=_concern_pct(rows, "died", "expert_risk"),
        concern_died_llm=_concern_pct(rows, "died", "llm_risk"),
        concern_died_rag=_concern_pct(rows, "died", "rag_risk"),
        concern_survived_expert=_concern_pct(rows, "survived", "expert_risk"),
        concern_survived_llm=_concern_pct(rows, "survived", "llm_risk"),
        concern_survived_rag=_concern_pct(rows, "survived", "rag_risk"),
    )


def _provider_deltas(openai_rows: list[dict], claude_rows: list[dict]) -> dict:
    o_map = {_key(r): r for r in openai_rows}
    c_map = {_key(r): r for r in claude_rows}
    common = set(o_map) & set(c_map)
    llm_diff = sum(
        1 for k in common if int(o_map[k].get("llm_risk") or 0) != int(c_map[k].get("llm_risk") or 0)
    )
    rag_diff = sum(
        1 for k in common if int(o_map[k].get("rag_risk") or 0) != int(c_map[k].get("rag_risk") or 0)
    )
    expert_mismatch = sum(
        1
        for k in common
        if o_map[k].get("expert_risk") != c_map[k].get("expert_risk")
        or o_map[k].get("expert_tags") != c_map[k].get("expert_tags")
    )
    return {
        "common_n": len(common),
        "llm_risk_diff": llm_diff,
        "rag_risk_diff": rag_diff,
        "expert_mismatch": expert_mismatch,
    }


def _write_markdown(
    openai: ProviderStats,
    claude: ProviderStats,
    deltas: dict,
    path: Path,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Porównanie providerów LLM — pilotaż N=100",
        "",
        f"OpenAI: `{openai.model}` (N={openai.n}) | Claude: `{claude.model}` (N={claude.n})",
        "",
        "## 6.1 E1 — zgodność expert / LLM / RAG",
        "",
        "| Metryka | OpenAI | Claude | Δ (Claude−OpenAI) |",
        "|---------|--------|--------|-------------------|",
        f"| Full agreement % | {openai.full_pct} | {claude.full_pct} | {round(claude.full_pct - openai.full_pct, 1)} |",
        f"| Partial agreement % | {openai.partial_pct} | {claude.partial_pct} | {round(claude.partial_pct - openai.partial_pct, 1)} |",
        f"| Disagreement % | {openai.disagree_pct} | {claude.disagree_pct} | {round(claude.disagree_pct - openai.disagree_pct, 1)} |",
        f"| Śr. flag expert / LLM / RAG | {openai.avg_expert_flags} / {openai.avg_llm_flags} / {openai.avg_rag_flags} | "
        f"{claude.avg_expert_flags} / {claude.avg_llm_flags} / {claude.avg_rag_flags} | — |",
        "",
        "## 6.2 E2 — RAG vs LLM",
        "",
        "| Metryka | OpenAI | Claude |",
        "|---------|--------|--------|",
        f"| RAG-only concern | {openai.rag_only} | {claude.rag_only} |",
        f"| GenAI-only concern | {openai.genai_only} | {claude.genai_only} |",
        "",
        "## 6.3 E3 — outcome vs sygnał (concern %)",
        "",
        "| Grupa | Expert O | LLM O | RAG O | Expert C | LLM C | RAG C |",
        "|-------|----------|-------|-------|----------|-------|-------|",
        f"| Zmarli | {openai.concern_died_expert} | {openai.concern_died_llm} | {openai.concern_died_rag} | "
        f"{claude.concern_died_expert} | {claude.concern_died_llm} | {claude.concern_died_rag} |",
        f"| Przeżyli | {openai.concern_survived_expert} | {openai.concern_survived_llm} | {openai.concern_survived_rag} | "
        f"{claude.concern_survived_expert} | {claude.concern_survived_llm} | {claude.concern_survived_rag} |",
        "",
        "## 6.5 Porównanie providerów",
        "",
        f"- Wspólna kohorta (łączenie subject_id/hadm_id): **{deltas['common_n']}**",
        f"- LLM risk różny OpenAI≠Claude: **{deltas['llm_risk_diff']}**",
        f"- RAG risk różny OpenAI≠Claude: **{deltas['rag_risk_diff']}**",
        f"- Expert mismatch między plikami (powinno być 0): **{deltas['expert_mismatch']}**",
        "",
        "| Δ agreement z expertem | OpenAI | Claude |",
        "|------------------------|--------|--------|",
        f"| LLM risk = expert risk % | {openai.llm_expert_agree_pct} | {claude.llm_expert_agree_pct} |",
        f"| RAG risk = expert risk % | {openai.rag_expert_agree_pct} | {claude.rag_expert_agree_pct} |",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Compare OpenAI vs Claude pilot CSVs")
    parser.add_argument("--openai", type=Path, required=True)
    parser.add_argument("--claude", type=Path, required=True)
    parser.add_argument("-o", "--output", type=Path, default=Path("artifacts/pilot_comparison.md"))
    args = parser.parse_args()

    for p in (args.openai, args.claude):
        if not p.is_file():
            print(f"Missing: {p}")
            return 1

    openai_rows = _read_csv(args.openai)
    claude_rows = _read_csv(args.claude)
    openai_stats = _summarize(openai_rows, "openai")
    claude_stats = _summarize(claude_rows, "claude")
    deltas = _provider_deltas(openai_rows, claude_rows)
    _write_markdown(openai_stats, claude_stats, deltas, args.output)
    print(f"Wrote comparison → {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
