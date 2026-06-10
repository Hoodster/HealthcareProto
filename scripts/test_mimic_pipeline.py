#!/usr/bin/env python3
"""
Test script for MIMIC pipeline evaluation using HTTP API.

This script calls the API endpoints to:
1. Fetch cardiac patients from MIMIC-III
2. Evaluate each patient through selected approaches
3. Aggregate metrics and save results

Usage:
    python scripts/test_mimic_pipeline.py --limit 10 --approaches expert genai rag
    python scripts/test_mimic_pipeline.py --api-url http://localhost:8000 --limit 20 --token YOUR_TOKEN
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

import requests
from requests.auth import HTTPBasicAuth


class MIMICPipelineTester:
    """HTTP client for testing MIMIC pipeline evaluation."""
    
    def __init__(
        self,
        api_url: str,
        token: Optional[str] = None,
        username: Optional[str] = None,
        password: Optional[str] = None
    ):
        self.api_url = api_url.rstrip("/")
        self.session = requests.Session()
        
        # Set up authentication
        if token:
            self.session.headers.update({"Authorization": f"Bearer {token}"})
        elif username and password:
            self.session.auth = HTTPBasicAuth(username, password)
        else:
            print("Warning: No authentication provided. API may reject requests.")
    
    def get_cardiac_patients(
        self,
        limit: int = 50,
        with_prescriptions: bool = True
    ) -> list[dict]:
        """Fetch cardiac patient summaries from API."""
        url = f"{self.api_url}/mimic/cardiac-patients"
        params = {
            "limit": limit,
            "with_prescriptions": with_prescriptions
        }
        
        print(f"Fetching up to {limit} cardiac patients...")
        response = self.session.get(url, params=params)
        response.raise_for_status()
        
        patients = response.json()
        print(f"✓ Retrieved {len(patients)} patients")
        return patients
    
    def evaluate_patient(
        self,
        subject_id: int,
        hadm_id: int,
        approaches: list[str],
        include_raw_context: bool = False
    ) -> dict:
        """Evaluate a single patient through the pipeline."""
        url = f"{self.api_url}/pipeline/evaluate-mimic/{subject_id}/{hadm_id}"
        params = {
            "approaches": approaches,
            "include_raw_context": include_raw_context
        }
        
        response = self.session.post(url, params=params)
        response.raise_for_status()
        
        return response.json()
    
    def run_evaluation(
        self,
        limit: int,
        approaches: list[str],
        include_raw_context: bool = False
    ) -> dict:
        """Run evaluation on multiple patients and aggregate results."""
        # Get patients
        patients = self.get_cardiac_patients(limit=limit)
        
        if not patients:
            print("No patients found. Exiting.")
            return {"error": "No patients found"}
        
        # Evaluate each patient
        results = []
        metrics_per_approach = {approach: [] for approach in approaches}
        
        print(f"\nEvaluating {len(patients)} patients through {len(approaches)} approach(es)...")
        print("-" * 80)
        
        for i, patient in enumerate(patients, 1):
            subject_id = patient["subject_id"]
            hadm_id = patient["hadm_id"]
            
            try:
                print(f"[{i}/{len(patients)}] Patient {subject_id}, Admission {hadm_id}... ", end="", flush=True)
                
                result = self.evaluate_patient(
                    subject_id=subject_id,
                    hadm_id=hadm_id,
                    approaches=approaches,
                    include_raw_context=include_raw_context
                )
                
                # Extract metrics
                for approach in approaches:
                    if approach in result["metrics"]:
                        metrics = result["metrics"][approach]
                        if metrics.get("f1") is not None:
                            metrics_per_approach[approach].append(metrics["f1"])
                
                results.append(result)
                print("✓")
                
            except requests.HTTPError as e:
                print(f"✗ HTTP {e.response.status_code}")
                print(f"    Error: {e.response.text}")
            except Exception as e:
                print(f"✗ {type(e).__name__}: {e}")
        
        print("-" * 80)
        
        # Aggregate metrics
        aggregated = self._aggregate_metrics(metrics_per_approach)
        
        # Build report
        report = {
            "timestamp": datetime.now().isoformat(),
            "api_url": self.api_url,
            "total_patients": len(patients),
            "evaluated_patients": len(results),
            "approaches": approaches,
            "aggregated_metrics": aggregated,
            "individual_results": results
        }
        
        return report
    
    def _aggregate_metrics(self, metrics_per_approach: dict[str, list[float]]) -> dict:
        """Aggregate F1 scores per approach."""
        aggregated = {}
        
        for approach, f1_scores in metrics_per_approach.items():
            if f1_scores:
                aggregated[approach] = {
                    "count": len(f1_scores),
                    "avg_f1": sum(f1_scores) / len(f1_scores),
                    "min_f1": min(f1_scores),
                    "max_f1": max(f1_scores)
                }
            else:
                aggregated[approach] = {
                    "count": 0,
                    "avg_f1": None,
                    "min_f1": None,
                    "max_f1": None
                }
        
        return aggregated
    
    def save_report(self, report: dict, output_path: Optional[Path] = None):
        """Save evaluation report to JSON file."""
        if output_path is None:
            # Create artifacts directory if it doesn't exist
            artifacts_dir = Path("artifacts")
            artifacts_dir.mkdir(exist_ok=True)
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = artifacts_dir / f"pipeline_results_{timestamp}.json"
        
        with open(output_path, "w") as f:
            json.dump(report, f, indent=2)
        
        print(f"\n✓ Report saved to: {output_path}")
    
    def print_summary(self, report: dict):
        """Print a human-readable summary of results."""
        print("\n" + "=" * 80)
        print("PIPELINE EVALUATION SUMMARY")
        print("=" * 80)
        
        print(f"Timestamp: {report['timestamp']}")
        print(f"API URL: {report['api_url']}")
        print(f"Patients evaluated: {report['evaluated_patients']}/{report['total_patients']}")
        print(f"Approaches: {', '.join(report['approaches'])}")
        
        print("\n" + "-" * 80)
        print("AGGREGATED METRICS (F1 Score)")
        print("-" * 80)
        
        for approach, metrics in report["aggregated_metrics"].items():
            if metrics["count"] > 0:
                print(f"{approach.upper():15s} | Count: {metrics['count']:3d} | "
                      f"Avg F1: {metrics['avg_f1']:.3f} | "
                      f"Min: {metrics['min_f1']:.3f} | Max: {metrics['max_f1']:.3f}")
            else:
                print(f"{approach.upper():15s} | No F1 scores calculated")
        
        print("=" * 80)


def main():
    parser = argparse.ArgumentParser(
        description="Test MIMIC pipeline evaluation via HTTP API",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Evaluate 10 patients with all approaches
  python scripts/test_mimic_pipeline.py --limit 10

  # Evaluate with specific approaches
  python scripts/test_mimic_pipeline.py --limit 20 --approaches expert genai

  # Use custom API URL and token
  python scripts/test_mimic_pipeline.py --api-url http://server:8000 --token abc123

  # Use username/password authentication
  python scripts/test_mimic_pipeline.py --username user --password pass
        """
    )
    
    parser.add_argument(
        "--api-url",
        default="http://localhost:8000",
        help="Base API URL (default: http://localhost:8000)"
    )
    parser.add_argument(
        "--token",
        help="Bearer token for authentication"
    )
    parser.add_argument(
        "--username",
        help="Username for basic authentication"
    )
    parser.add_argument(
        "--password",
        help="Password for basic authentication"
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=20,
        help="Maximum number of patients to evaluate (default: 20)"
    )
    parser.add_argument(
        "--approaches",
        nargs="+",
        choices=["expert", "genai", "rag"],
        default=["expert", "genai", "rag"],
        help="Approaches to evaluate (default: all)"
    )
    parser.add_argument(
        "--include-raw-context",
        action="store_true",
        help="Include raw PatientContext in results (increases response size)"
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Output file path (default: artifacts/pipeline_results_<timestamp>.json)"
    )
    parser.add_argument(
        "--no-save",
        action="store_true",
        help="Don't save results to file"
    )
    
    args = parser.parse_args()
    
    # Validate authentication
    if not args.token and not (args.username and args.password):
        print("Warning: No authentication provided.")
        print("You may need to provide --token or --username/--password")
        print("")
    
    # Create tester
    tester = MIMICPipelineTester(
        api_url=args.api_url,
        token=args.token,
        username=args.username,
        password=args.password
    )
    
    # Run evaluation
    try:
        report = tester.run_evaluation(
            limit=args.limit,
            approaches=args.approaches,
            include_raw_context=args.include_raw_context
        )
        
        # Print summary
        tester.print_summary(report)
        
        # Save report
        if not args.no_save:
            tester.save_report(report, args.output)
        
        return 0
    
    except requests.exceptions.ConnectionError:
        print(f"\n✗ Error: Could not connect to {args.api_url}")
        print("  Make sure the API server is running.")
        return 1
    
    except requests.exceptions.HTTPError as e:
        print(f"\n✗ HTTP Error {e.response.status_code}: {e.response.text}")
        return 1
    
    except Exception as e:
        print(f"\n✗ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
