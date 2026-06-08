#!/usr/bin/env python3
"""
Porównanie LLM vs RAG vs outcome MIMIC — jeden skrypt.

Domyślnie woła wdrożony serwis Azure. Flaga --local omija HTTP i czyta bezpośrednio z DB (DB_URL w .env).

Przykład:
    python scripts/run_comparison.py --limit 20
    python scripts/run_comparison.py --limit 15 --outcome died --json artifacts/report.json
    python scripts/run_comparison.py --local --limit 10
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path
from urllib.parse import urlencode

import httpx

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from dotenv import load_dotenv

load_dotenv(_PROJECT_ROOT / ".env")

from api.services.outcome_comparison_export import print_summary, write_csv
from api.services.outcome_comparison_service import OutcomeComparisonReport, OutcomeComparisonService

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
    outcome: str,
    approaches: list[str],
    timeout: int,
) -> OutcomeComparisonReport:
    params = [("limit", limit), ("outcome", outcome), *[("approaches", a) for a in approaches]]
    path = f"/hp_proto/api/pipeline/outcome-comparison?{urlencode(params, doseq=True)}"

    with httpx.Client(base_url=base_url.rstrip("/"), follow_redirects=True) as client:
        token = _login(client, email, password)
        resp = client.get(
            path,
            headers={"Authorization": f"Bearer {token}"},
            timeout=timeout,
        )
        if resp.status_code != 200:
            raise RuntimeError(f"API error ({resp.status_code}): {resp.text}")
        return OutcomeComparisonReport.model_validate(resp.json())


def run_local(
    *,
    limit: int,
    outcome: str,
    approaches: list[str],
) -> OutcomeComparisonReport:
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from api.config import get_database_connection_url

    engine = create_engine(get_database_connection_url())
    db = sessionmaker(bind=engine)()
    try:
        return OutcomeComparisonService.run(
            db,
            limit=limit,
            approaches=approaches,
            outcome_filter=outcome,  # type: ignore[arg-type]
        )
    finally:
        db.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="MIMIC outcome comparison (LLM vs RAG)")
    parser.add_argument("--local", action="store_true", help="Run against local DB instead of API")
    parser.add_argument("--base-url", default=DEFAULT_API, help=f"API base URL (default: {DEFAULT_API})")
    parser.add_argument("--email", default=DEFAULT_EMAIL)
    parser.add_argument("--password", default=DEFAULT_PASSWORD)
    parser.add_argument("--limit", type=int, default=20, help="Number of cases (1–200 on API)")
    parser.add_argument("--outcome", choices=["all", "died", "survived"], default="all")
    parser.add_argument(
        "--approaches",
        nargs="+",
        default=["genai", "rag_full"],
        choices=["genai", "rag_full"],
    )
    parser.add_argument("--output", type=Path, default=None, help="CSV path")
    parser.add_argument("--json", type=Path, default=None, help="JSON report path")
    parser.add_argument("--timeout", type=int, default=900, help="HTTP timeout (seconds)")
    args = parser.parse_args()

    try:
        if args.local:
            print(f"Local DB mode (limit={args.limit}, outcome={args.outcome})…")
            report = run_local(
                limit=args.limit,
                outcome=args.outcome,
                approaches=args.approaches,
            )
        else:
            print(f"API: {args.base_url} (limit={args.limit}, outcome={args.outcome})…")
            report = run_via_api(
                base_url=args.base_url,
                email=args.email,
                password=args.password,
                limit=args.limit,
                outcome=args.outcome,
                approaches=args.approaches,
                timeout=args.timeout,
            )

        if not report.rows:
            print("No rows — is MIMIC loaded?", file=sys.stderr)
            return 1

        out_csv = args.output or (
            _PROJECT_ROOT / "artifacts" / f"comparison_{datetime.now():%Y%m%d_%H%M%S}.csv"
        )
        write_csv(report, out_csv)
        print(f"CSV: {out_csv}")

        if args.json:
            args.json.parent.mkdir(parents=True, exist_ok=True)
            args.json.write_text(report.model_dump_json(indent=2), encoding="utf-8")
            print(f"JSON: {args.json}")

        print_summary(report)
        return 0
    except (RuntimeError, httpx.HTTPError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
