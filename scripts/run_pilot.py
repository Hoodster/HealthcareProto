#!/usr/bin/env python3
"""Pilot experiment: export expert/LLM/RAG risk levels for thesis (E1–E3).

Example:
    python scripts/run_pilot.py --local --limit 100 --antiarrhythmic-only \\
        --llm-provider openai -o artifacts/pilot_100_openai.csv
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from dotenv import load_dotenv

load_dotenv(_PROJECT_ROOT / ".env")

from api.services.pilot_service import PilotService, write_pilot_csv


def main() -> int:
    parser = argparse.ArgumentParser(description="Pilot cohort export for thesis")
    parser.add_argument("--local", action="store_true", help="Run against local DB (DB_URL)")
    parser.add_argument("--limit", type=int, default=100)
    parser.add_argument("--offset", type=int, default=0)
    parser.add_argument("--outcome", choices=["all", "died", "survived"], default="all")
    parser.add_argument("--antiarrhythmic-only", action="store_true")
    parser.add_argument(
        "--llm-provider",
        choices=["openai", "claude"],
        required=True,
        help="LLM provider for GenAI/RAG completion (required)",
    )
    parser.add_argument(
        "--llm-model",
        default=None,
        help="Override LLM model (default from LLM_MODEL env or provider default)",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=None,
        help="Output CSV path (default: artifacts/pilot_100_<provider>.csv)",
    )
    args = parser.parse_args()

    if not args.local:
        print("Pilot requires --local (direct DB + API keys). Use run_comparison.py for API mode.")
        return 1

    output = args.output or Path(f"artifacts/pilot_100_{args.llm_provider}.csv")

    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from api.config import get_database_connection_url

    engine = create_engine(get_database_connection_url())
    db = sessionmaker(bind=engine)()
    try:
        print(
            f"Running pilot (provider={args.llm_provider}, limit={args.limit}, "
            f"outcome={args.outcome})…"
        )
        rows, summary = PilotService.run(
            db,
            limit=args.limit,
            offset=args.offset,
            outcome_filter=args.outcome,  # type: ignore[arg-type]
            antiarrhythmic_only=args.antiarrhythmic_only,
            llm_provider=args.llm_provider,
            llm_model=args.llm_model,
        )
    finally:
        db.close()

    write_pilot_csv(rows, output)
    print(f"Wrote {len(rows)} rows → {output}")
    print(
        f"E1 agreement: full={summary.full_agreement_pct}% "
        f"partial={summary.partial_agreement_pct}% "
        f"disagreement={summary.disagreement_pct}%"
    )
    print(
        f"E2 RAG-only concern: {summary.rag_only_concern}, "
        f"GenAI-only: {summary.genai_only_concern}"
    )
    print(f"E3 outcome: died={summary.died_count}, survived={summary.survived_count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
