"""
Unit Tests for Uncertainty Evaluation and Epistemic Calibration.
Validates the critical constraint: UNCERTAIN is a valid outcome and hallucinations are prohibited.
"""

from backend.app.core.models import (
    VisualFeatureExtraction, PurchaseOrderItem, InspectionVerdict,
    SingleCheckResult, CheckType, CheckStatus
)
from backend.app.core.uncertainty import UncertaintyEvaluator
from backend.app.core.vision_agent import ReceivingInspectionAgent


def test_uncertainty_triggered_on_severe_blur():
    features = VisualFeatureExtraction(
        image_quality_score=0.25, # Below 0.55 threshold
        occlusion_ratio=0.0
    )
    is_uncertain, reasons, action = UncertaintyEvaluator.evaluate_perception_uncertainty(features)
    assert is_uncertain is True
    assert any("sharpness" in r.lower() for r in reasons)
    assert action is not None
    assert "Retake" in action


def test_uncertainty_triggered_on_excessive_occlusion():
    features = VisualFeatureExtraction(
        image_quality_score=0.85,
        occlusion_ratio=0.60 # Exceeds 0.40 threshold
    )
    is_uncertain, reasons, action = UncertaintyEvaluator.evaluate_perception_uncertainty(features)
    assert is_uncertain is True
    assert any("occlusion" in r.lower() for r in reasons)
    assert "wrap" in action.lower() or "orient" in action.lower()


def test_uncertainty_triggered_on_missing_sku_and_barcode():
    features = VisualFeatureExtraction(
        observed_sku=None,
        observed_barcode=None,
        image_quality_score=0.90
    )
    is_uncertain, reasons, action = UncertaintyEvaluator.evaluate_perception_uncertainty(features)
    assert is_uncertain is True
    assert any("neither" in r.lower() for r in reasons)


def test_agent_refuses_to_guess_quantity_in_sealed_box():
    po = PurchaseOrderItem(
        po_number="PO-2026-SEALED",
        sku="BLUE-BOTTLE-001",
        expected_quantity=24,
        expected_variant="Blue"
    )
    # Sealed box: inner quantity unknown
    features = VisualFeatureExtraction(
        observed_sku="BLUE-BOTTLE-001",
        observed_barcode="810092345001",
        observed_quantity=None, # Missing inner count
        observed_cartons=2,
        observed_variant="Blue",
        image_quality_score=0.92
    )
    agent = ReceivingInspectionAgent()
    record = agent.inspect_shipment(po=po, extracted_features=features)

    assert record.verdict == InspectionVerdict.UNCERTAIN
    assert record.checks[CheckType.QUANTITY_COUNT.value].status == CheckStatus.UNCERTAIN
    assert "spot-check unboxing" in record.operator_action_required.lower() or "unboxing" in record.operator_action_required.lower()
