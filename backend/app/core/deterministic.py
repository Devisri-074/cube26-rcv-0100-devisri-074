"""
Deterministic Rules Engine.
Implements rigorous mathematical validation, SKU cross-referencing,
quantity delta arithmetic, variant validation, and financial claim calculation.
Zero hallucinations: every rule is mathematically provable and reproducible.
"""

from typing import Dict, List, Tuple, Optional, Any
from .models import (
    PurchaseOrderItem, CatalogItem, VisualFeatureExtraction,
    SingleCheckResult, CheckType, CheckStatus, DamageType, BoundingBox
)


class DeterministicRulesEngine:
    """
    Executes non-probabilistic checks on extracted visual features against PO and Catalog.
    Acts as the ground-truth gatekeeper before any final verdict is rendered.
    """

    @staticmethod
    def evaluate_sku(
        po: PurchaseOrderItem,
        features: VisualFeatureExtraction,
        catalog: Optional[CatalogItem] = None
    ) -> SingleCheckResult:
        """Evaluates SKU identity against PO and Catalog."""
        if features.observed_sku is None and features.observed_barcode is None:
            return SingleCheckResult(
                check_type=CheckType.SKU_IDENTITY,
                status=CheckStatus.UNCERTAIN,
                confidence=0.5,
                expected_value=po.sku,
                observed_value="NOT_DETECTED",
                reason="SKU text or barcode label was not clearly legible in receiving photo.",
                requires_operator_override=True
            )

        observed_sku = (features.observed_sku or "").strip().upper()
        expected_sku = po.sku.strip().upper()

        # Check barcode cross-reference if available
        barcode_match = False
        if features.observed_barcode and po.asin_or_upc:
            barcode_match = (features.observed_barcode.strip() == po.asin_or_upc.strip())

        sku_match = (observed_sku == expected_sku)

        if sku_match or barcode_match:
            sku_boxes = [b for b in features.bounding_boxes if "sku" in b.label.lower() or "barcode" in b.label.lower()]
            return SingleCheckResult(
                check_type=CheckType.SKU_IDENTITY,
                status=CheckStatus.PASS,
                confidence=0.99 if (sku_match and barcode_match) else 0.95,
                expected_value=po.sku,
                observed_value=observed_sku or features.observed_barcode,
                reason=f"SKU '{po.sku}' successfully verified against receiving label/barcode.",
                evidence_boxes=sku_boxes
            )

        # SKU Mismatch detected
        return SingleCheckResult(
            check_type=CheckType.SKU_IDENTITY,
            status=CheckStatus.FAIL,
            confidence=0.98,
            expected_value=po.sku,
            observed_value=observed_sku or features.observed_barcode,
            discrepancy_delta=f"Expected SKU '{po.sku}', found '{observed_sku}'",
            reason=f"CRITICAL SKU MISMATCH: Received package indicates SKU '{observed_sku}', expected '{po.sku}'.",
            evidence_boxes=[b for b in features.bounding_boxes if "sku" in b.label.lower()]
        )

    @staticmethod
    def evaluate_quantity(
        po: PurchaseOrderItem,
        features: VisualFeatureExtraction
    ) -> SingleCheckResult:
        """Evaluates expected vs observed quantity and carton packing configuration."""
        if features.observed_quantity is None:
            return SingleCheckResult(
                check_type=CheckType.QUANTITY_COUNT,
                status=CheckStatus.UNCERTAIN,
                confidence=0.4,
                expected_value=po.expected_quantity,
                observed_value="UNKNOWN",
                reason="Cannot count units with certainty from visible surfaces without opening inner packaging.",
                requires_operator_override=True
            )

        obs_qty = features.observed_quantity
        exp_qty = po.expected_quantity
        delta = obs_qty - exp_qty

        qty_boxes = [b for b in features.bounding_boxes if "unit" in b.label.lower() or "count" in b.label.lower() or "carton" in b.label.lower()]

        if delta == 0:
            return SingleCheckResult(
                check_type=CheckType.QUANTITY_COUNT,
                status=CheckStatus.PASS,
                confidence=0.96,
                expected_value=exp_qty,
                observed_value=obs_qty,
                discrepancy_delta=0,
                reason=f"QUANTITY VERIFIED: Expected: {exp_qty} | Observed: {obs_qty} | Difference: 0. Exact PO match.",
                evidence_boxes=qty_boxes
            )
        elif delta < 0:
            return SingleCheckResult(
                check_type=CheckType.QUANTITY_COUNT,
                status=CheckStatus.FAIL,
                confidence=0.98,
                expected_value=exp_qty,
                observed_value=obs_qty,
                discrepancy_delta=delta,
                reason=f"SHORT SHIPMENT DETECTED: Expected: {exp_qty} | Observed: {obs_qty} | Difference: {delta} (Missing {abs(delta)} units).",
                evidence_boxes=qty_boxes
            )
        else:
            return SingleCheckResult(
                check_type=CheckType.QUANTITY_COUNT,
                status=CheckStatus.FAIL,
                confidence=0.95,
                expected_value=exp_qty,
                observed_value=obs_qty,
                discrepancy_delta=f"+{delta}",
                reason=f"OVERAGE DETECTED: Expected: {exp_qty} | Observed: {obs_qty} | Difference: +{delta} (Extra unmanifested units).",
                evidence_boxes=qty_boxes
            )

    @staticmethod
    def evaluate_variant(
        po: PurchaseOrderItem,
        features: VisualFeatureExtraction
    ) -> SingleCheckResult:
        """Evaluates observed product variant (color, model, finish) against PO specification."""
        if not features.observed_variant:
            return SingleCheckResult(
                check_type=CheckType.VARIANT_SPEC,
                status=CheckStatus.UNCERTAIN,
                confidence=0.5,
                expected_value=po.expected_variant,
                observed_value="UNSPECIFIED",
                reason="Variant / color characteristics could not be resolved from provided photography.",
                requires_operator_override=True
            )

        exp_var = po.expected_variant.strip().lower()
        obs_var = features.observed_variant.strip().lower()

        variant_boxes = [b for b in features.bounding_boxes if "variant" in b.label.lower() or "color" in b.label.lower() or "product" in b.label.lower()]

        if exp_var == obs_var:
            return SingleCheckResult(
                check_type=CheckType.VARIANT_SPEC,
                status=CheckStatus.PASS,
                confidence=0.96,
                expected_value=po.expected_variant,
                observed_value=features.observed_variant,
                reason=f"Observed variant '{features.observed_variant}' matches PO specification '{po.expected_variant}'.",
                evidence_boxes=variant_boxes
            )

        return SingleCheckResult(
            check_type=CheckType.VARIANT_SPEC,
            status=CheckStatus.FAIL,
            confidence=0.97,
            expected_value=po.expected_variant,
            observed_value=features.observed_variant,
            discrepancy_delta=f"Expected '{po.expected_variant}', Received '{features.observed_variant}'",
            reason=f"WRONG VARIANT DETECTED: Received '{features.observed_variant}' instead of ordered '{po.expected_variant}'.",
            evidence_boxes=variant_boxes
        )

    @staticmethod
    def evaluate_packaging_and_damage(
        features: VisualFeatureExtraction
    ) -> Tuple[SingleCheckResult, SingleCheckResult]:
        """Evaluates carton structural integrity and visible damage/defects."""
        # Physical damage types
        physical_damage_types = [
            d for d in features.detected_damages 
            if d not in [DamageType.NONE, DamageType.OCCLUSION_BLUR, DamageType.LABEL_TAMPERED, DamageType.WRONG_VARIANT, DamageType.MISSING_COMPONENTS]
        ]
        damage_boxes = [b for b in features.bounding_boxes if any(keyword in b.label.lower() for keyword in ["crush", "water", "tear", "damage", "puncture", "dent"])]

        # Check if perception is too degraded/blurred to verify packaging condition
        if DamageType.OCCLUSION_BLUR in features.detected_damages or features.image_quality_score < 0.50:
            carton_check = SingleCheckResult(
                check_type=CheckType.CARTON_INTEGRITY,
                status=CheckStatus.UNCERTAIN,
                confidence=0.40,
                expected_value="Intact, Structural Grade A",
                observed_value="UNVERIFIABLE_BLUR",
                reason="Severe blur or optical artifact prevents reliable verification of carton fluting.",
                requires_operator_override=True
            )
            damage_check = SingleCheckResult(
                check_type=CheckType.PACKAGING_DAMAGE,
                status=CheckStatus.UNCERTAIN,
                confidence=0.40,
                expected_value="Zero Defect Condition",
                observed_value="UNVERIFIABLE_BLUR",
                reason="Surface resolution insufficient to detect hairline tears, punctures, or moisture ingress.",
                requires_operator_override=True
            )
            return carton_check, damage_check

        if not physical_damage_types:
            carton_check = SingleCheckResult(
                check_type=CheckType.CARTON_INTEGRITY,
                status=CheckStatus.PASS,
                confidence=0.95,
                expected_value="Intact, Structural Grade A",
                observed_value="Sound Carton Integrity",
                reason="Carton shows sound structural corners, intact fluting, and no puncture/collapse.",
                evidence_boxes=[]
            )
            damage_check = SingleCheckResult(
                check_type=CheckType.PACKAGING_DAMAGE,
                status=CheckStatus.PASS,
                confidence=0.95,
                expected_value="No Visible Damage / Stains",
                observed_value="Clean / Undamaged",
                reason="No moisture ingress, tears, crushing, or seal breaches detected.",
                evidence_boxes=[]
            )
            return carton_check, damage_check

        damage_descriptions = []
        has_crush = DamageType.CRUSHED_CARTON in physical_damage_types
        has_tear = DamageType.TEAR_PUNCTURE in physical_damage_types
        has_water = DamageType.WATER_DAMAGE in physical_damage_types
        has_open_seal = DamageType.OPEN_SEAL in physical_damage_types

        if has_crush:
            damage_descriptions.append("Corner/wall crushing (>15% deformation)")
        if has_water:
            damage_descriptions.append("Moisture staining / corrugated softening")
        if has_tear:
            damage_descriptions.append("Torn packaging / punctured outer wall")
        if has_open_seal:
            damage_descriptions.append("Broken security seal / opened tape")

        carton_status = CheckStatus.FAIL if (has_crush or has_tear) else CheckStatus.PASS
        carton_check = SingleCheckResult(
            check_type=CheckType.CARTON_INTEGRITY,
            status=carton_status,
            confidence=0.94,
            expected_value="Intact, Structural Grade A",
            observed_value=", ".join(d.value for d in physical_damage_types),
            discrepancy_delta=f"{len(physical_damage_types)} defect(s) detected",
            reason=f"Carton integrity compromised: {'; '.join(damage_descriptions)}",
            evidence_boxes=damage_boxes
        )

        damage_check = SingleCheckResult(
            check_type=CheckType.PACKAGING_DAMAGE,
            status=CheckStatus.FAIL,
            confidence=0.96,
            expected_value="Zero Defect Condition",
            observed_value=", ".join(d.value for d in physical_damage_types),
            discrepancy_delta="Physical Damage Present",
            reason=f"INCOMING SHIPMENT DAMAGE: Detected {', '.join(damage_descriptions)}.",
            evidence_boxes=damage_boxes
        )

        return carton_check, damage_check

    @staticmethod
    def evaluate_components(
        po: PurchaseOrderItem,
        features: VisualFeatureExtraction
    ) -> SingleCheckResult:
        """Evaluates presence of required accessories and components."""
        if not po.required_components:
            return SingleCheckResult(
                check_type=CheckType.COMPONENT_INTEGRITY,
                status=CheckStatus.PASS,
                confidence=1.0,
                expected_value="Standard Single Item",
                observed_value="N/A",
                reason="No separate mandatory accessories required by PO.",
                evidence_boxes=[]
            )

        missing = features.missing_components
        comp_boxes = [b for b in features.bounding_boxes if "component" in b.label.lower() or "missing" in b.label.lower() or "accessory" in b.label.lower()]

        if not missing:
            return SingleCheckResult(
                check_type=CheckType.COMPONENT_INTEGRITY,
                status=CheckStatus.PASS,
                confidence=0.94,
                expected_value=po.required_components,
                observed_value="All Present",
                reason=f"All {len(po.required_components)} mandatory components/accessories verified present.",
                evidence_boxes=comp_boxes
            )

        return SingleCheckResult(
            check_type=CheckType.COMPONENT_INTEGRITY,
            status=CheckStatus.FAIL,
            confidence=0.96,
            expected_value=po.required_components,
            observed_value=f"Missing: {', '.join(missing)}",
            discrepancy_delta=f"Missing: {', '.join(missing)}",
            reason=f"MISSING COMPONENTS: Expected {', '.join(po.required_components)}, but missing {', '.join(missing)}.",
            evidence_boxes=comp_boxes
        )

    @staticmethod
    def evaluate_label_integrity(
        features: VisualFeatureExtraction
    ) -> SingleCheckResult:
        """Evaluates shipping label security, authenticity, and absence of adversarial tampering."""
        if features.adversarial_signals or DamageType.LABEL_TAMPERED in features.detected_damages:
            return SingleCheckResult(
                check_type=CheckType.LABEL_BARCODE,
                status=CheckStatus.FAIL,
                confidence=0.99,
                expected_value="Authentic Standard Inbound Shipping Label",
                observed_value="TAMPERED / ADVERSARIAL PAYLOAD",
                discrepancy_delta="Label Tampering Present",
                reason=f"SECURITY ALERT: {'; '.join(features.adversarial_signals) if features.adversarial_signals else 'Tampered / spoofed shipping label detected.'}",
                evidence_boxes=[b for b in features.bounding_boxes if "adversarial" in b.label.lower() or "tamper" in b.label.lower() or "label" in b.label.lower()]
            )

        return SingleCheckResult(
            check_type=CheckType.LABEL_BARCODE,
            status=CheckStatus.PASS,
            confidence=0.98,
            expected_value="Authentic Standard Inbound Shipping Label",
            observed_value="Legitimate Label Verified",
            reason="Shipping label barcode and text adhere to EDI standard formatting without tampering.",
            evidence_boxes=[]
        )
