"""Benchmark API routes — POST /benchmark/run."""
from __future__ import annotations

from typing import Literal, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from api.benchmarks.benchmark_runner import BenchmarkReport, BenchmarkRunner, Mode
from api.benchmarks.test_dataset import BENCHMARK_CASES

router = APIRouter(prefix="/benchmark", tags=["benchmark"])


class BenchmarkRunRequest(BaseModel):
    mode: Optional[Literal["expert_only", "llm_only", "full_pipeline", "all"]] = "all"
    case_ids: Optional[list[str]] = None  # None = run all cases
    model: Optional[str] = None


@router.post("/run", response_model=BenchmarkReport)
def run_benchmark(payload: BenchmarkRunRequest) -> BenchmarkReport:
    """
    Run the A/B/C benchmark comparison.

    - mode='all' runs all three modes (expert_only, llm_only, full_pipeline)
    - case_ids filters to specific benchmark cases; omit to run all 10 cases
    - model overrides the OpenAI model used by the LLM modes
    """
    cases = BENCHMARK_CASES
    if payload.case_ids:
        id_set = set(payload.case_ids)
        cases = [c for c in cases if c.case_id in id_set]
        if not cases:
            raise HTTPException(status_code=404, detail="No matching benchmark cases found")

    _all: list[Mode] = ["expert_only", "llm_only", "full_pipeline"]
    modes: list[Mode] = _all if payload.mode == "all" else [payload.mode]  # type: ignore[list-item]

    runner = BenchmarkRunner(model=payload.model)
    return runner.compare(cases, modes=modes)


@router.get("/cases")
def list_cases():
    """List available benchmark cases with metadata."""
    return [
        {
            "case_id": c.case_id,
            "description": c.description,
            "ground_truth": c.ground_truth,
        }
        for c in BENCHMARK_CASES
    ]
