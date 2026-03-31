"""Benchmark metrics for evaluating clinical decision support approaches."""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from api.benchmarks.benchmark_runner import BenchmarkResult, BenchmarkCase


def recall_alerts(result: "BenchmarkResult", case: "BenchmarkCase") -> float:
    """
    What fraction of expected alert categories were actually triggered?
    recall = |expected ∩ detected| / |expected|
    """
    expected = set(case.ground_truth.get("expected_alert_categories", []))
    if not expected:
        return 1.0
    detected = {a["category"] for a in result.alerts}
    return len(expected & detected) / len(expected)


def precision_alerts(result: "BenchmarkResult", case: "BenchmarkCase") -> float:
    """
    What fraction of triggered alert categories were actually expected?
    precision = |expected ∩ detected| / |detected|
    """
    detected = {a["category"] for a in result.alerts}
    if not detected:
        return 1.0
    expected = set(case.ground_truth.get("expected_alert_categories", []))
    return len(expected & detected) / len(detected)


def contraindication_accuracy(result: "BenchmarkResult", case: "BenchmarkCase") -> float:
    """1.0 if contraindicated matches expected, 0.0 otherwise."""
    expected = case.ground_truth.get("expected_contraindicated", False)
    return 1.0 if result.contraindicated == expected else 0.0


def dose_adjustment_accuracy(result: "BenchmarkResult", case: "BenchmarkCase") -> float:
    """1.0 if dose_adjustment_expected matches result, 0.0 otherwise."""
    expected = case.ground_truth.get("expected_dose_adjustment", False)
    return 1.0 if result.dose_adjustment_present == expected else 0.0


def mean_latency(results: list["BenchmarkResult"]) -> float:
    """Mean latency in milliseconds."""
    if not results:
        return 0.0
    return sum(r.latency_ms for r in results) / len(results)
