"""
Canonical End-to-End Scenario Verification Test Suite.
Validates that all required test scenarios from the Problem Statement produce
100% correct verdicts, accurate discrepancy notes, and immutable evidence dossiers.
"""

import pytest
from backend.app.core.vision_agent import ReceivingInspectionAgent
from backend.app.scenarios.dataset import ScenarioRepository
from backend.app.core.models import InspectionVerdict


@pytest.fixture
def agent():
    return ReceivingInspectionAgent()


@pytest.fixture
def scenarios():
    return ScenarioRepository.get_all_scenarios()


def test_all_canonical_scenarios_produce_correct_verdicts(agent, scenarios):
    """
    Parametrized verification that EVERY scenario in the benchmark suite
    achieves ground truth correctness.
    """
    assert len(scenarios) >= 10, "Must contain all required problem statement scenarios."

    for sc in scenarios:
        record = agent.inspect_shipment(
            po=sc.po,
            extracted_features=sc.features,
            catalog=sc.catalog
        )

        assert record.verdict == sc.expected_verdict, (
            f"Scenario '{sc.scenario_id}' failed: Expected {sc.expected_verdict.value}, got {record.verdict.value}"
        )

        # Verify hash seal exists and is valid 64-char hex
        assert len(record.immutable_sha256) == 64
        assert record.immutable_sha256 == record.calculate_hash()

        # If expected discrepancy substring given, verify it is present
        if sc.expected_discrepancy_substr:
            all_discrepancies_text = " ".join(record.discrepancies) + " " + record.summary
            for c in record.checks.values():
                all_discrepancies_text += " " + c.reason
            assert sc.expected_discrepancy_substr.lower() in all_discrepancies_text.lower(), (
                f"Scenario '{sc.scenario_id}' missing expected discrepancy keyword '{sc.expected_discrepancy_substr}'"
            )


def test_scenario_01_correct_shipment(agent):
    sc = next(s for s in ScenarioRepository.get_all_scenarios() if s.scenario_id == "SCENARIO_01_CORRECT")
    record = agent.inspect_shipment(po=sc.po, extracted_features=sc.features, catalog=sc.catalog)
    assert record.verdict == InspectionVerdict.ACCEPT
    assert record.overall_confidence >= 0.95
    assert len(record.discrepancies) == 0


def test_scenario_02_short_shipment(agent):
    sc = next(s for s in ScenarioRepository.get_all_scenarios() if s.scenario_id == "SCENARIO_02_SHORTAGE")
    record = agent.inspect_shipment(po=sc.po, extracted_features=sc.features, catalog=sc.catalog)
    assert record.verdict == InspectionVerdict.EXCEPTION
    assert record.supplier_dispute_eligible is True
    # 2 units missing * $18.50 = $37.00 claim
    assert record.dispute_claim_amount_usd == 37.00


def test_scenario_04_wrong_sku_rejection(agent):
    sc = next(s for s in ScenarioRepository.get_all_scenarios() if s.scenario_id == "SCENARIO_04_WRONG_SKU")
    record = agent.inspect_shipment(po=sc.po, extracted_features=sc.features, catalog=sc.catalog)
    assert record.verdict == InspectionVerdict.REJECT
    assert record.supplier_dispute_eligible is True


def test_scenario_06_crushed_carton_damage(agent):
    sc = next(s for s in ScenarioRepository.get_all_scenarios() if s.scenario_id == "SCENARIO_06_CRUSHED")
    record = agent.inspect_shipment(po=sc.po, extracted_features=sc.features, catalog=sc.catalog)
    assert record.verdict == InspectionVerdict.EXCEPTION
    assert any("CRUSHED_CARTON" in d.value for d in record.detected_damages)


def test_scenario_10_ambiguous_case_uncertainty(agent):
    sc = next(s for s in ScenarioRepository.get_all_scenarios() if s.scenario_id == "SCENARIO_10_AMBIGUOUS_BLUR")
    record = agent.inspect_shipment(po=sc.po, extracted_features=sc.features, catalog=sc.catalog)
    assert record.verdict == InspectionVerdict.UNCERTAIN
    assert record.operator_action_required is not None
