#!/usr/bin/env python3
"""
Bezpieczeństwo antyarytmików: expert vs GenAI vs RAG vs outcome MIMIC — jeden skrypt.

Domyślnie woła wdrożony serwis Azure. Flaga --local omija HTTP i czyta bezpośrednio z DB (DB_URL w .env).

Przykład:
    python scripts/run_comparison.py --limit 20 --markdown artifacts/safety.md
    python scripts/run_comparison.py --limit 30 --antiarrhythmic-only --markdown artifacts/safety.md
    python scripts/run_comparison.py --local --limit 10 --outcome died
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

from api.services.outcome_comparison_export import print_summary, write_csv, write_markdown
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
    offset: int,
    chunk: int,
    outcome: str,
    approaches: list[str],
    antiarrhythmic_only: bool,
    llm_provider: str | None,
    llm_model: str | None,
    timeout: int,
) -> OutcomeComparisonReport:
    """Fetch the cohort in small pages (offset/next_offset) and merge.

    Each request only asks for `chunk` rows so it completes well under the
    App Service ~230s gateway timeout, then we resume via next_offset until we
    have `limit` rows or the patient list is exhausted. This is why a large
    `--limit` works even though a single big request would 504.
    """
    rows: list = []
    cursor = max(offset, 0)
    exhausted = False
    next_offset = None
    base_meta: dict = {}

    with httpx.Client(base_url=base_url.rstrip("/"), follow_redirects=True) as client:
        token = _login(client, email, password)
        headers = {"Authorization": f"Bearer {token}"}

        while len(rows) < limit:
            page_size = min(chunk, limit - len(rows))
            params = [
                ("limit", page_size),
                ("offset", cursor),
                ("outcome", outcome),
                ("antiarrhythmic_only", str(antiarrhythmic_only).lower()),
                *[("approaches", a) for a in approaches],
            ]
            if llm_provider:
                params.append(("llm_provider", llm_provider))
            if llm_model:
                params.append(("llm_model", llm_model))
            path = f"/hp_proto/api/pipeline/outcome-comparison?{urlencode(params, doseq=True)}"
            resp = client.get(path, headers=headers, timeout=timeout)
            if resp.status_code != 200:
                raise RuntimeError(f"API error ({resp.status_code}): {resp.text}")
            page = OutcomeComparisonReport.model_validate(resp.json())
            if not base_meta:
                base_meta = {
                    "methodology": page.methodology,
                    "approaches": page.approaches,
                    "outcome_filter": page.outcome_filter,
                    "llm_provider": page.llm_provider,
                    "llm_model": page.llm_model,
                }
            rows.extend(page.rows)
            next_offset = page.next_offset
            print(f"  page offset={cursor} → +{len(page.rows)} rows (total {len(rows)}), next_offset={next_offset}")
            if next_offset is None:
                exhausted = True
                break
            cursor = next_offset

    report = OutcomeComparisonReport(
        llm_provider=base_meta.get("llm_provider"),
        llm_model=base_meta.get("llm_model"),
        approaches=base_meta.get("approaches", approaches),
        outcome_filter=base_meta.get("outcome_filter", outcome),  # type: ignore[arg-type]
        summary=OutcomeComparisonService._summarize(rows),
        rows=rows,
        next_offset=None if exhausted else next_offset,
    )
    if base_meta.get("methodology"):
        report.methodology = base_meta["methodology"]
    return report


def run_local(
    *,
    limit: int,
    offset: int,
    outcome: str,
    approaches: list[str],
    antiarrhythmic_only: bool,
    llm_provider: str | None,
    llm_model: str | None,
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
            offset=offset,
            approaches=approaches,
            outcome_filter=outcome,  # type: ignore[arg-type]
            antiarrhythmic_only=antiarrhythmic_only,
            llm_provider=llm_provider,
            llm_model=llm_model,
        )
    finally:
        db.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="Antiarrhythmic drug-safety comparison (expert vs GenAI vs RAG)")
    parser.add_argument("--local", action="store_true", help="Run against local DB instead of API")
    parser.add_argument("--base-url", default=DEFAULT_API, help=f"API base URL (default: {DEFAULT_API})")
    parser.add_argument("--email", default=DEFAULT_EMAIL)
    parser.add_argument("--password", default=DEFAULT_PASSWORD)
    parser.add_argument("--limit", type=int, default=20, help="Total number of cases to collect")
    parser.add_argument("--offset", type=int, default=0, help="Patient index to start from (pagination)")
    parser.add_argument(
        "--chunk",
        type=int,
        default=8,
        help="Rows per API request — kept small so each call stays under the ~230s gateway timeout",
    )
    parser.add_argument("--outcome", choices=["all", "died", "survived"], default="all")
    parser.add_argument(
        "--approaches",
        nargs="+",
        default=["genai", "rag"],
        choices=["genai", "rag"],
    )
    parser.add_argument(
        "--antiarrhythmic-only",
        action="store_true",
        help="Restrict cohort to patients exposed to antiarrhythmic drugs",
    )
    parser.add_argument(
        "--llm-provider",
        choices=["openai", "claude"],
        default=None,
        help="GenAI/RAG LLM provider (API query param; default: server env LLM_PROVIDER)",
    )
    parser.add_argument("--llm-model", default=None, help="Override LLM model id")
    parser.add_argument("--output", type=Path, default=None, help="CSV path")
    parser.add_argument("--markdown", type=Path, default=None, help="Markdown safety report path")
    parser.add_argument("--json", type=Path, default=None, help="JSON report path")
    parser.add_argument("--timeout", type=int, default=900, help="HTTP timeout (seconds)")
    args = parser.parse_args()

    try:
        if args.local:
            print(f"Local DB mode (limit={args.limit}, outcome={args.outcome})…")
            report = run_local(
                limit=args.limit,
                offset=args.offset,
                outcome=args.outcome,
                approaches=args.approaches,
                antiarrhythmic_only=args.antiarrhythmic_only,
                llm_provider=args.llm_provider,
                llm_model=args.llm_model,
            )
        else:
            print(
                f"API: {args.base_url} (limit={args.limit}, chunk={args.chunk}, "
                f"offset={args.offset}, outcome={args.outcome}, "
                f"llm={args.llm_provider or 'default'})…"
            )
            report = run_via_api(
                base_url=args.base_url,
                email=args.email,
                password=args.password,
                limit=args.limit,
                offset=args.offset,
                chunk=args.chunk,
                outcome=args.outcome,
                approaches=args.approaches,
                antiarrhythmic_only=args.antiarrhythmic_only,
                llm_provider=args.llm_provider,
                llm_model=args.llm_model,
                timeout=args.timeout,
            )

        if not report.rows:
            print("No rows — is MIMIC loaded?", file=sys.stderr)
            return 1

        # Recompute the summary locally so the descriptive analysis is independent
        # of the deployed server version (row-level signals come from the API).
        report.summary = OutcomeComparisonService._summarize(report.rows)

        out_csv = args.output or (
            _PROJECT_ROOT / "artifacts" / f"comparison_{datetime.now():%Y%m%d_%H%M%S}.csv"
        )
        write_csv(report, out_csv)
        print(f"CSV: {out_csv}")

        if args.markdown:
            write_markdown(report, args.markdown)
            print(f"Markdown: {args.markdown}")

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
