"""
Scenario Benchmark & Evaluation API Routes.
"""

from fastapi import APIRouter, HTTPException
from typing import List, Dict, Any
import time
from PIL import Image
import os
from ..core.models import EvidenceRecord, InspectionVerdict
from ..core.vision_agent import ReceivingInspectionAgent
from ..scenarios.dataset import ScenarioRepository, InspectionScenario

router = APIRouter(prefix="/api/scenarios", tags=["Scenarios"])
agent = ReceivingInspectionAgent()


@router.get("", response_model=List[Dict[str, Any]])
def list_all_scenarios():
    """Returns metadata for all benchmark scenarios."""
    scenarios = ScenarioRepository.get_all_scenarios()
    result = []
    for sc in scenarios:
        result.append({
            "scenario_id": sc.scenario_id,
            "title": sc.title,
            "category": sc.category,
            "description": sc.description,
            "po": sc.po.model_dump(),
            "expected_verdict": sc.expected_verdict.value,
            "image_url": f"/static/images/{sc.image_filename}" if sc.image_filename else None
        })
    return result


@router.post("/run/{scenario_id}", response_model=Dict[str, Any])
def run_single_scenario(scenario_id: str):
    """Executes inspection on a single benchmark scenario."""
    scenarios = {sc.scenario_id: sc for sc in ScenarioRepository.get_all_scenarios()}
    if scenario_id not in scenarios:
        raise HTTPException(status_code=404, detail=f"Scenario '{scenario_id}' not found.")

    sc = scenarios[scenario_id]
    img = None
    img_path = os.path.join("data", "images", sc.image_filename)
    if os.path.exists(img_path):
        img = Image.open(img_path)

    record = agent.inspect_shipment(
        po=sc.po,
        image=img,
        extracted_features=sc.features,
        catalog=sc.catalog
    )

    is_match = (record.verdict == sc.expected_verdict)
    return {
        "scenario_id": sc.scenario_id,
        "title": sc.title,
        "expected_verdict": sc.expected_verdict.value,
        "actual_verdict": record.verdict.value,
        "is_correct": is_match,
        "evidence_record": record.model_dump()
    }


@router.post("/benchmark", response_model=Dict[str, Any])
def run_full_benchmark():
    """
    Executes all scenarios across the test suite, measuring correctness,
    confusion matrix, and processing latencies.
    """
    scenarios = ScenarioRepository.get_all_scenarios()
    total = len(scenarios)
    passed = 0
    results = []
    latencies_ms = []

    matrix = {
        "ACCEPT": {"ACCEPT": 0, "EXCEPTION": 0, "UNCERTAIN": 0, "REJECT": 0},
        "EXCEPTION": {"ACCEPT": 0, "EXCEPTION": 0, "UNCERTAIN": 0, "REJECT": 0},
        "UNCERTAIN": {"ACCEPT": 0, "EXCEPTION": 0, "UNCERTAIN": 0, "REJECT": 0},
        "REJECT": {"ACCEPT": 0, "EXCEPTION": 0, "UNCERTAIN": 0, "REJECT": 0},
    }

    start_bench = time.time()

    for sc in scenarios:
        t0 = time.time()
        img = None
        img_path = os.path.join("data", "images", sc.image_filename)
        if os.path.exists(img_path):
            img = Image.open(img_path)

        record = agent.inspect_shipment(
            po=sc.po,
            image=img,
            extracted_features=sc.features,
            catalog=sc.catalog
        )
        elapsed = (time.time() - t0) * 1000.0
        latencies_ms.append(elapsed)

        is_correct = (record.verdict == sc.expected_verdict)
        if is_correct:
            passed += 1

        exp_v = sc.expected_verdict.value
        act_v = record.verdict.value
        if exp_v in matrix and act_v in matrix[exp_v]:
            matrix[exp_v][act_v] += 1

        results.append({
            "scenario_id": sc.scenario_id,
            "title": sc.title,
            "category": sc.category,
            "expected_verdict": exp_v,
            "actual_verdict": act_v,
            "is_correct": is_correct,
            "confidence": record.overall_confidence,
            "latency_ms": round(elapsed, 2),
            "discrepancies": record.discrepancies,
            "sha256": record.immutable_sha256[:12]
        })

    total_bench_ms = (time.time() - start_bench) * 1000.0
    latencies_ms.sort()
    p50 = latencies_ms[len(latencies_ms) // 2] if latencies_ms else 0
    p95 = latencies_ms[int(len(latencies_ms) * 0.95)] if latencies_ms else 0
    p99 = latencies_ms[-1] if latencies_ms else 0

    return {
        "total_scenarios": total,
        "correct_evaluations": passed,
        "accuracy_pct": round((passed / total) * 100.0, 2),
        "total_benchmark_time_ms": round(total_bench_ms, 2),
        "latency_metrics_ms": {
            "p50": round(p50, 2),
            "p95": round(p95, 2),
            "p99": round(p99, 2),
            "mean": round(sum(latencies_ms) / len(latencies_ms), 2) if latencies_ms else 0
        },
        "confusion_matrix": matrix,
        "scenario_results": results
    }
