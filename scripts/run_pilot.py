#!/usr/bin/env python3
"""Pilot experiment: export expert/LLM/RAG risk levels for thesis (E1–E3).

Domyślnie woła wdrożony serwis Azure (outcome-comparison). Flaga --local omija HTTP.

Example:
    python scripts/run_pilot.py --limit 100 --antiarrhythmic-only \\
        --llm-provider openai -o artifacts/pilot_100_openai.csv

    python scripts/run_pilot.py --local --limit 100 --antiarrhythmic-only \\
        --llm-provider openai -o artifacts/pilot_100_openai.csv
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from urllib.parse import urlencode

import httpx

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from dotenv import load_dotenv

load_dotenv(_PROJECT_ROOT / ".env")

from api.services.outcome_comparison_service import OutcomeComparisonReport
from api.services.pilot_service import PilotService, write_pilot_csv

DEFAULT_API = "https://azaphtn4tglr3jlgw.azurewebsites.net"
DEFAULT_EMAIL = "doctor@local"
DEFAULT_PASSWORD = "doctor"


def _login(client: httpx.Client, email: str, password: str) -> str:
    resp = client.post(
        "/hp_proto/api/auth/login",
        json={"email": email, "password": password},
        timeout=60,
    )
    data = resp.json()
    if resp.status_code != 200 or not data.get("access_token"):
        raise RuntimeError(f"Login failed ({resp.status_code}): {data}")
    return data["access_token"]


def run_via_api(
    *,
    base_url: str,
    email: str,
    password: str,
    limit: int,
    offset: int,
    chunk: int,
    outcome: str,
    antiarrhythmic_only: bool,
    llm_provider: str,
    llm_model: str | None,
    timeout: int,
) -> tuple[list, object]:
    """Fetch outcome-comparison pages and map to pilot rows."""
    api_rows: list = []
    cursor = max(offset, 0)
    resolved_provider = llm_provider
    resolved_model = llm_model

    with httpx.Client(base_url=base_url.rstrip("/"), follow_redirects=True) as client:
        token = _login(client, email, password)
        headers = {"Authorization": f"Bearer {token}"}

        while len(api_rows) < limit:
            page_size = min(chunk, limit - len(api_rows))
            params = [
                ("limit", page_size),
                ("offset", cursor),
                ("outcome", outcome),
                ("antiarrhythmic_only", str(antiarrhythmic_only).lower()),
                ("llm_provider", llm_provider),
                ("approaches", "genai"),
                ("approaches", "rag"),
            ]
            if llm_model:
                params.append(("llm_model", llm_model))
            path = f"/hp_proto/api/pipeline/outcome-comparison?{urlencode(params, doseq=True)}"
            resp = client.get(path, headers=headers, timeout=timeout)
            if resp.status_code != 200:
                raise RuntimeError(f"API error ({resp.status_code}): {resp.text}")
            page = OutcomeComparisonReport.model_validate(resp.json())
            if page.llm_provider:
                resolved_provider = page.llm_provider
            if page.llm_model:
                resolved_model = page.llm_model
            api_rows.extend(page.rows)
            print(
                f"  page offset={cursor} → +{len(page.rows)} rows (total {len(api_rows)}), "
                f"next_offset={page.next_offset}"
            )
            if page.next_offset is None or not page.rows:
                break
            cursor = page.next_offset

    pilot_rows = PilotService.rows_from_outcome_comparison(
        api_rows,
        llm_provider=resolved_provider,
        llm_model=resolved_model,
    )
    return pilot_rows, PilotService._summarize(pilot_rows)


def main() -> int:
    parser = argparse.ArgumentParser(description="Pilot cohort export for thesis")
    parser.add_argument(
        "--local",
        action="store_true",
        help="Run against local DB (DB_URL) instead of deployed API",
    )
    parser.add_argument("--base-url", default=DEFAULT_API, help=f"API base URL (default: {DEFAULT_API})")
    parser.add_argument("--email", default=DEFAULT_EMAIL)
    parser.add_argument("--password", default=DEFAULT_PASSWORD)
    parser.add_argument("--limit", type=int, default=100)
    parser.add_argument("--offset", type=int, default=0)
    parser.add_argument(
        "--chunk",
        type=int,
        default=3,
        help="Rows per API request (keep small — each row runs GenAI+RAG on server)",
    )
    parser.add_argument("--timeout", type=int, default=900, help="HTTP timeout per page (seconds)")
    parser.add_argument("--outcome", choices=["all", "died", "survived"], default="all")
    parser.add_argument("--antiarrhythmic-only", action="store_true")
    parser.add_argument(
        "--llm-provider",
        choices=["openai", "claude"],
        default="openai",
        help="Label for CSV; passed as API ?llm_provider= (server must have API keys)",
    )
    parser.add_argument(
        "--llm-model",
        default=None,
        help="Override LLM model label in CSV (default from provider)",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=None,
        help="Output CSV path (default: artifacts/pilot_100_<provider>.csv)",
    )
    args = parser.parse_args()

    output = args.output or Path(f"artifacts/pilot_100_{args.llm_provider}.csv")

    try:
        if args.local:
            from sqlalchemy import create_engine
            from sqlalchemy.orm import sessionmaker

            from api.config import get_database_connection_url

            engine = create_engine(get_database_connection_url())
            db = sessionmaker(bind=engine)()
            try:
                print(
                    f"Local pilot (provider={args.llm_provider}, limit={args.limit}, "
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
        else:
            print(
                f"API: {args.base_url} (provider={args.llm_provider}, limit={args.limit}, "
                f"chunk={args.chunk}, outcome={args.outcome})…"
            )
            rows, summary = run_via_api(
                base_url=args.base_url,
                email=args.email,
                password=args.password,
                limit=args.limit,
                offset=args.offset,
                chunk=args.chunk,
                outcome=args.outcome,
                antiarrhythmic_only=args.antiarrhythmic_only,
                llm_provider=args.llm_provider,
                llm_model=args.llm_model,
                timeout=args.timeout,
            )

        if not rows:
            print("No rows — is MIMIC loaded on the server?", file=sys.stderr)
            return 1

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
    except (RuntimeError, httpx.HTTPError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
