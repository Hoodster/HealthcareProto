#!/usr/bin/env python3
"""
MIMIC-III benchmark script — runs A/B/C comparison on real cardiac patients.

Usage:
    python -m scripts.mimic_benchmark [--n N] [--modes expert_only llm_only full_pipeline]

Requirements:
    - PostgreSQL with MIMIC-III loaded in 'mimiciii' schema
    - OPENAI_API_KEY set in environment (skip 'llm_only'/'full_pipeline' if unavailable)
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Make sure project root is on the path when running as a script
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from api.config import get_database_connection_url
from api.services.mimic_service import build_mimic_patient_context, get_heart_patients
from api.benchmarks.benchmark_runner import BenchmarkCase, BenchmarkRunner
from expert_system.rules.interaction_rules import QT_PROLONGING_DRUGS


def build_cases(db_session, n_patients: int) -> list[BenchmarkCase]:
    patients_raw = get_heart_patients(db_session, with_icu_stay=False)
    cases: list[BenchmarkCase] = []

    for p in patients_raw:
        if len(cases) >= n_patients:
            break
        subject_id = p["subject_id"]
        admissions = p.get("admissions", [])
        if not admissions:
            continue
        hadm_id = admissions[0]["hadm_id"]
        if hadm_id is None:
            continue

        try:
            ctx = build_mimic_patient_context(subject_id, hadm_id, db_session)
        except Exception as exc:
            print(f"  skip {subject_id}/{hadm_id}: {exc}", file=sys.stderr)
            continue

        qt_meds = {m for m in ctx.medications if m in QT_PROLONGING_DRUGS}
        expected_alert_categories = []
        if len(qt_meds) >= 2:
            expected_alert_categories.append("interaction")
        if ctx.egfr < 60:
            expected_alert_categories.append("renal")

        cases.append(BenchmarkCase(
            case_id=f"MIMIC_{subject_id}_{hadm_id}",
            description=f"MIMIC patient {subject_id} admission {hadm_id}",
            patient=ctx,
            question="Assess drug safety and identify any contraindications for this cardiac patient.",
            ground_truth={
                "expected_contraindicated": False,
                "expected_alert_categories": expected_alert_categories,
                "expected_dose_adjustment": ctx.egfr < 60,
            },
        ))

    return cases


def print_report(report) -> None:
    print("\n" + "=" * 70)
    print("MIMIC-III BENCHMARK RESULTS")
    print("=" * 70)
    for r in report.reports:
        print(f"\nMode: {r.mode.upper():<20}  N={r.n_cases}")
        print(f"  Recall (alerts):           {r.mean_recall:.3f}")
        print(f"  Precision (alerts):        {r.mean_precision:.3f}")
        print(f"  Contraindication accuracy: {r.mean_contraindication_accuracy:.3f}")
        print(f"  Dose-adjustment accuracy:  {r.mean_dose_adjustment_accuracy:.3f}")
        print(f"  Mean latency:              {r.mean_latency_ms:.1f} ms")
    print()


def main() -> None:
    parser = argparse.ArgumentParser(description="Run MIMIC-III A/B/C benchmark")
    parser.add_argument("--n", type=int, default=20, help="Number of patients (default: 20)")
    parser.add_argument(
        "--modes",
        nargs="+",
        default=["expert_only"],
        choices=["expert_only", "llm_only", "full_pipeline"],
        help="Benchmark modes to run (default: expert_only)",
    )
    parser.add_argument("--output", type=str, default=None, help="Path to write JSON report")
    args = parser.parse_args()

    db_url = get_database_connection_url()
    engine = create_engine(db_url)
    db = sessionmaker(bind=engine)()


    try:
        print(f"Building benchmark cases from MIMIC-III (target: {args.n} patients)…")
        cases = build_cases(db, args.n)
        if not cases:
            print("No MIMIC patients found. Is MIMIC-III loaded in the database?", file=sys.stderr)
            sys.exit(1)
        print(f"  → {len(cases)} cases built")

        runner = BenchmarkRunner()
        print(f"Running modes: {args.modes}…")
        report = runner.compare(cases, modes=args.modes)

        print_report(report)

        if args.output:
            out_path = Path(args.output)
            out_path.write_text(report.model_dump_json(indent=2), encoding="utf-8")
            print(f"Report saved to {out_path}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
