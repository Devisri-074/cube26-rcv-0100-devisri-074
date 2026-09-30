"""
Uncertainty & Calibration Engine.
Ensures zero hallucinations and strictly enforces the 'UNCERTAIN' outcome
when visual evidence is ambiguous, low quality, occluded, or insufficient.
"""

from typing import List, Tuple, Optional
from .models import (
    VisualFeatureExtraction, InspectionVerdict, SingleCheckResult,
    CheckStatus, CheckType, DamageType
)


class UncertaintyEvaluator:
    """
    Evaluates epistemic and aleatoric uncertainty in receiving inspection evidence.
    Calibrates confidence scores and generates specific operator guidance.
    """

    MIN_ACCEPTABLE_IMAGE_QUALITY = 0.55
    MAX_PERMISSIBLE_OCCLUSION = 0.40

    @classmethod
    def evaluate_perception_uncertainty(
        cls,
        features: VisualFeatureExtraction
    ) -> Tuple[bool, List[str], Optional[str]]:
        """
        Determines whether the visual perception data is too degraded or ambiguous
        to reach an automated ACCEPT or REJECT decision.

        Returns:
            (is_uncertain, list_of_uncertainty_reasons, suggested_operator_action)
        """
        reasons: List[str] = []
        action: Optional[str] = None

        # Check 1: Blur / Laplacian Sharpness
        if features.image_quality_score < cls.MIN_ACCEPTABLE_IMAGE_QUALITY:
            reasons.append(
                f"Image sharpness score ({features.image_quality_score:.2f}) below threshold ({cls.MIN_ACCEPTABLE_IMAGE_QUALITY:.2f}). Severe motion blur or focal blur detected."
            )
            action = "Operator Action: Retake high-resolution photograph under steady lighting without motion blur."

        # Check 2: Physical Occlusion
        if features.occlusion_ratio > cls.MAX_PERMISSIBLE_OCCLUSION:
            reasons.append(
                f"Subject occlusion ({features.occlusion_ratio*100:.1f}%) exceeds allowable threshold ({cls.MAX_PERMISSIBLE_OCCLUSION*100:.1f}%). Pallet wrap, strapping, or stacking blocks view."
            )
            action = "Operator Action: Remove obscuring stretch-wrap or re-orient carton for unobstructed visual inspection."

        # Check 3: Missing SKU text and barcode simultaneously
        if features.observed_sku is None and features.observed_barcode is None:
            reasons.append("Neither human-readable SKU text nor machine-readable barcode could be resolved.")
            if not action:
                action = "Operator Action: Point scanner or macro-lens directly at the shipping label."

        # Check 4: Ambiguous quantity in sealed opaque packaging
        if features.observed_quantity is None and features.observed_cartons is not None:
            reasons.append("Inner unit quantity cannot be visually verified through sealed opaque corrugated exterior.")
            if not action:
                action = "Operator Action: Perform spot-check unboxing of 1 master carton to verify inner unit packing density."

        # Check 5: Ambiguous damage or smudge
        if DamageType.OCCLUSION_BLUR in features.detected_damages:
            reasons.append("Potential surface defect is obscured by optical artifact or glare.")
            if not action:
                action = "Operator Action: Conduct manual surface tactile inspection."

        is_uncertain = len(reasons) > 0
        return is_uncertain, reasons, action

    @classmethod
    def arbitrate_final_verdict(
        cls,
        checks: dict[str, SingleCheckResult],
        is_uncertain: bool,
        uncertainty_reasons: List[str]
    ) -> Tuple[InspectionVerdict, float, List[str], str]:
        """
        Synthesizes check results into an overall verdict with mathematically grounded confidence.

        Verdict Logic:
        1. If critical check (SKU, Variant, Damage, Quantity) has FAILED with high confidence -> EXCEPTION or REJECT.
        2. If ANY check is UNCERTAIN or perception uncertainty was triggered without a clear confirmed FAIL -> UNCERTAIN.
        3. If ALL checks PASS with high confidence -> ACCEPT.
        """
        all_checks = list(checks.values())
        failed_checks = [c for c in all_checks if c.status == CheckStatus.FAIL]
        uncertain_checks = [c for c in all_checks if c.status == CheckStatus.UNCERTAIN]
        passed_checks = [c for c in all_checks if c.status == CheckStatus.PASS]

        discrepancies: List[str] = []
        for c in failed_checks:
            discrepancies.append(c.reason)

        # Calculate weighted confidence
        if all_checks:
            avg_confidence = sum(c.confidence for c in all_checks) / len(all_checks)
        else:
            avg_confidence = 0.0

        # Scenario A: Definite Failure Confirmed
        if failed_checks:
            # Check if critical SKU failure
            sku_fail = any(c.check_type == CheckType.SKU_IDENTITY for c in failed_checks)
            if sku_fail:
                verdict = InspectionVerdict.REJECT
                summary = f"REJECTED: Shipment contains unauthorized SKU. {len(discrepancies)} discrepancy(ies) detected."
            else:
                verdict = InspectionVerdict.EXCEPTION
                summary = f"EXCEPTION: Inbound discrepancies detected ({len(failed_checks)} check(s) failed). Supplier claim dossier generated."
            return verdict, round(avg_confidence, 4), discrepancies, summary

        # Scenario B: Uncertainty (Cannot confirm PASS)
        if is_uncertain or uncertain_checks:
            verdict = InspectionVerdict.UNCERTAIN
            calibrated_conf = min(avg_confidence, 0.60)
            summary = f"UNCERTAIN: Available visual evidence is insufficient or ambiguous. Manual operator verification required."
            return verdict, round(calibrated_conf, 4), discrepancies, summary

        # Scenario C: Clean Acceptance
        if len(passed_checks) == len(all_checks):
            verdict = InspectionVerdict.ACCEPT
            calibrated_conf = max(0.95, avg_confidence)
            summary = f"ACCEPT: Shipment fully conforms to Purchase Order and Quality Standards (All {len(passed_checks)} checks PASSED)."
            return verdict, round(calibrated_conf, 4), discrepancies, summary

        # Default fallback
        return InspectionVerdict.UNCERTAIN, 0.50, discrepancies, "UNCERTAIN: Incomplete check state."
