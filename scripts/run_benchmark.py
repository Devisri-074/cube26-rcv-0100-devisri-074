"""
CLI Benchmark Runner for InspectIQ™ Autonomous Inspection Engine.
Executes all 13 canonical scenarios, outputs performance metrics,
confusion matrix, and SLA latency benchmarks.
"""

import sys
import os
import time
from tabulate import tabulate

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.app.core.vision_agent import ReceivingInspectionAgent
from backend.app.scenarios.dataset import ScenarioRepository


def main():
    agent = ReceivingInspectionAgent()
    scenarios = ScenarioRepository.get_all_scenarios()

    print("================================================================================")
    print("  InspectIQ (TM) ENTERPRISE BENCHMARK & QUALITY VERIFICATION SUITE")
    print("================================================================================")
    print(f"Total Scenarios Evaluated: {len(scenarios)}\n")

    table_data = []
    latencies = []
    correct_count = 0

    for sc in scenarios:
        t0 = time.perf_counter()
        record = agent.inspect_shipment(
            po=sc.po,
            extracted_features=sc.features,
            catalog=sc.catalog
        )
        elapsed_ms = (time.perf_counter() - t0) * 1000.0
        latencies.append(elapsed_ms)

        is_match = (record.verdict == sc.expected_verdict)
        if is_match:
            correct_count += 1
            status_str = "[PASS]"
        else:
            status_str = "[FAIL]"

        discrepancy_snippet = record.discrepancies[0][:32] if record.discrepancies else "None (Conforming)"

        table_data.append([
            sc.scenario_id.replace("SCENARIO_", ""),
            sc.category[:16],
            sc.expected_verdict.value,
            record.verdict.value,
            f"{record.overall_confidence*100:.1f}%",
            f"{elapsed_ms:.2f}ms",
            status_str,
            discrepancy_snippet
        ])

    headers = ["Scenario ID", "Category", "Expected", "Actual", "Conf", "Latency", "Status", "Discrepancy Snippet"]
    print(tabulate(table_data, headers=headers, tablefmt="grid"))

    accuracy = (correct_count / len(scenarios)) * 100.0
    latencies.sort()
    p50 = latencies[len(latencies) // 2]
    p95 = latencies[int(len(latencies) * 0.95)]
    p99 = latencies[-1]
    avg_lat = sum(latencies) / len(latencies)

    print("\n--------------------------------------------------------------------------------")
    print(f"  OVERALL BENCHMARK ACCURACY: {accuracy:.2f}% ({correct_count}/{len(scenarios)} correct)")
    print(f"  LATENCY SLA: Mean={avg_lat:.2f}ms | P50={p50:.2f}ms | P95={p95:.2f}ms | P99={p99:.2f}ms")
    print("--------------------------------------------------------------------------------\n")


if __name__ == "__main__":
    main()
