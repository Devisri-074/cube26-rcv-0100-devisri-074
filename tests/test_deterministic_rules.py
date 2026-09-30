"""
Unit & Property-based Tests for Deterministic Rules Engine.
Validates exact mathematical arithmetic, SKU logic, and variant verification.
"""

import pytest
from backend.app.core.models import (
    PurchaseOrderItem, CatalogItem, VisualFeatureExtraction,
    CheckType, CheckStatus, DamageType
)
from backend.app.core.deterministic import DeterministicRulesEngine


@pytest.fixture
def sample_po():
    return PurchaseOrderItem(
        po_number="PO-TEST-001",
        sku="BLUE-BOTTLE-001",
        asin_or_upc="810092345001",
        expected_quantity=24,
        units_per_carton=12,
        expected_variant="Blue",
        unit_price=18.50,
        required_components=["Bottle Body", "Insulated Cap"]
    )


def test_sku_evaluation_exact_match(sample_po):
    features = VisualFeatureExtraction(
        observed_sku="BLUE-BOTTLE-001",
        observed_barcode="810092345001"
    )
    res = DeterministicRulesEngine.evaluate_sku(sample_po, features)
    assert res.status == CheckStatus.PASS
    assert res.confidence >= 0.95
    assert "BLUE-BOTTLE-001" in res.reason


def test_sku_evaluation_mismatch(sample_po):
    features = VisualFeatureExtraction(
        observed_sku="RED-TUMBLER-999",
        observed_barcode="899999999999"
    )
    res = DeterministicRulesEngine.evaluate_sku(sample_po, features)
    assert res.status == CheckStatus.FAIL
    assert "MISMATCH" in res.reason
    assert res.discrepancy_delta is not None


def test_sku_evaluation_uncertain_when_absent(sample_po):
    features = VisualFeatureExtraction(
        observed_sku=None,
        observed_barcode=None
    )
    res = DeterministicRulesEngine.evaluate_sku(sample_po, features)
    assert res.status == CheckStatus.UNCERTAIN
    assert res.requires_operator_override is True


def test_quantity_evaluation_exact(sample_po):
    features = VisualFeatureExtraction(observed_quantity=24)
    res = DeterministicRulesEngine.evaluate_quantity(sample_po, features)
    assert res.status == CheckStatus.PASS
    assert res.discrepancy_delta == 0


def test_quantity_evaluation_shortage(sample_po):
    features = VisualFeatureExtraction(observed_quantity=22)
    res = DeterministicRulesEngine.evaluate_quantity(sample_po, features)
    assert res.status == CheckStatus.FAIL
    assert res.discrepancy_delta == -2
    assert "SHORT SHIPMENT" in res.reason


def test_quantity_evaluation_overage(sample_po):
    features = VisualFeatureExtraction(observed_quantity=28)
    res = DeterministicRulesEngine.evaluate_quantity(sample_po, features)
    assert res.status == CheckStatus.FAIL
    assert res.discrepancy_delta == "+4"
    assert "OVERAGE DETECTED" in res.reason


def test_variant_evaluation_matching(sample_po):
    features = VisualFeatureExtraction(observed_variant="Blue")
    res = DeterministicRulesEngine.evaluate_variant(sample_po, features)
    assert res.status == CheckStatus.PASS


def test_variant_evaluation_mismatch(sample_po):
    features = VisualFeatureExtraction(observed_variant="Matte Black")
    res = DeterministicRulesEngine.evaluate_variant(sample_po, features)
    assert res.status == CheckStatus.FAIL
    assert "WRONG VARIANT" in res.reason


def test_packaging_damage_clean():
    features = VisualFeatureExtraction(detected_damages=[])
    carton_chk, damage_chk = DeterministicRulesEngine.evaluate_packaging_and_damage(features)
    assert carton_chk.status == CheckStatus.PASS
    assert damage_chk.status == CheckStatus.PASS


def test_packaging_damage_crushed():
    features = VisualFeatureExtraction(detected_damages=[DamageType.CRUSHED_CARTON])
    carton_chk, damage_chk = DeterministicRulesEngine.evaluate_packaging_and_damage(features)
    assert carton_chk.status == CheckStatus.FAIL
    assert damage_chk.status == CheckStatus.FAIL
    assert "crushing" in carton_chk.reason.lower()


def test_components_evaluation(sample_po):
    features = VisualFeatureExtraction(missing_components=["Insulated Cap"])
    res = DeterministicRulesEngine.evaluate_components(sample_po, features)
    assert res.status == CheckStatus.FAIL
    assert "Insulated Cap" in res.reason
