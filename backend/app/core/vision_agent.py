"""
InspectIQ™ Autonomous Receiving Inspection Agent.
Orchestrates perception, deterministic rule validation, uncertainty arbitration,
and immutable dossier sealing.
"""

from typing import Dict, Any, List, Optional, Tuple
from PIL import Image
import uuid
import time
from .models import (
    PurchaseOrderItem, CatalogItem, VisualFeatureExtraction, EvidenceRecord,
    InspectionVerdict, CheckType, CheckStatus, DamageType, BoundingBox
)
from .state import InspectionStateContext, AgentState
from .deterministic import DeterministicRulesEngine
from .uncertainty import UncertaintyEvaluator
from .image_analysis import ImageAnalysisPipeline
from .evidence_dossier import EvidenceDossierBuilder


class ReceivingInspectionAgent:
    """
    Autonomous Principal Agent for Inbound Visual Receiving.
    Processes receiving photography + Purchase Order manifests to yield
    deterministic, evidence-backed inspection records.
    """

    def __init__(self, name: str = "ReceivingManager-AI-v2.6"):
        self.name = name

    def inspect_shipment(
        self,
        po: PurchaseOrderItem,
        image: Optional[Image.Image] = None,
        extracted_features: Optional[VisualFeatureExtraction] = None,
        catalog: Optional[CatalogItem] = None,
        raw_metadata: Optional[Dict[str, Any]] = None
    ) -> EvidenceRecord:
        """
        Executes end-to-end multi-stage inspection pipeline.
        """
        start_time = time.time()
        ctx = InspectionStateContext(
            inspection_id=f"INSP-{uuid.uuid4().hex[:6].upper()}",
            po_number=po.po_number
        )

        ctx.transition_to(AgentState.INGESTING, "Ingesting PO manifest and receiving image", {
            "po_number": po.po_number,
            "sku": po.sku,
            "expected_quantity": po.expected_quantity,
            "expected_variant": po.expected_variant
        })

        # Phase 1: Visual Perception
        ctx.transition_to(AgentState.PERCEIVING, "Running low-level image processing & feature extraction")
        
        image_meta = raw_metadata or {}
        if image:
            sharpness = ImageAnalysisPipeline.calculate_laplacian_sharpness(image)
            contrast, mean_lum = ImageAnalysisPipeline.calculate_contrast_and_exposure(image)
            image_meta.update({
                "width": image.width,
                "height": image.height,
                "laplacian_sharpness": round(sharpness, 4),
                "contrast": round(contrast, 4),
                "mean_luminance": round(mean_lum, 4)
            })
            if extracted_features is None:
                # If features were not pre-extracted, initialize from image analysis
                dom_color, hex_val = ImageAnalysisPipeline.analyze_dominant_color(image)
                extracted_features = VisualFeatureExtraction(
                    observed_sku=po.sku,
                    observed_quantity=po.expected_quantity,
                    observed_variant=dom_color,
                    image_quality_score=sharpness,
                    occlusion_ratio=0.0
                )
            else:
                # Update image quality score from actual image
                extracted_features.image_quality_score = sharpness

        if extracted_features is None:
            extracted_features = VisualFeatureExtraction()

        # Sanitize OCR lines against prompt injection attacks
        if extracted_features.ocr_raw_text:
            sanitized_ocr, threats = ImageAnalysisPipeline.sanitize_adversarial_text(extracted_features.ocr_raw_text)
            if threats:
                extracted_features.adversarial_signals.extend(threats)
                extracted_features.detected_damages.append(DamageType.LABEL_TAMPERED)
                ctx.transition_to(AgentState.EXTRACTING_FEATURES, "Security Threat Detected: Adversarial Prompt Injection", {
                    "threats": threats
                })

        # Phase 2: Deterministic Rule Evaluation
        ctx.transition_to(AgentState.DETERMINISTIC_RULES, "Executing deterministic validation matrix")

        checks: Dict[str, Any] = {}
        
        # Check 1: SKU Identity
        checks[CheckType.SKU_IDENTITY.value] = DeterministicRulesEngine.evaluate_sku(
            po=po, features=extracted_features, catalog=catalog
        )

        # Check 2: Quantity & Packing Count
        checks[CheckType.QUANTITY_COUNT.value] = DeterministicRulesEngine.evaluate_quantity(
            po=po, features=extracted_features
        )

        # Check 3: Variant & Attribute Specification
        checks[CheckType.VARIANT_SPEC.value] = DeterministicRulesEngine.evaluate_variant(
            po=po, features=extracted_features
        )

        # Check 4 & 5: Carton Integrity & Physical Damage
        carton_chk, damage_chk = DeterministicRulesEngine.evaluate_packaging_and_damage(
            features=extracted_features
        )
        checks[CheckType.CARTON_INTEGRITY.value] = carton_chk
        checks[CheckType.PACKAGING_DAMAGE.value] = damage_chk

        # Check 6: Component & Accessory Integrity
        checks[CheckType.COMPONENT_INTEGRITY.value] = DeterministicRulesEngine.evaluate_components(
            po=po, features=extracted_features
        )

        # Check 7: Label Integrity & Barcode Security
        checks[CheckType.LABEL_BARCODE.value] = DeterministicRulesEngine.evaluate_label_integrity(
            features=extracted_features
        )

        # Phase 3: Epistemic Uncertainty & Quality Gate
        ctx.transition_to(AgentState.UNCERTAINTY_GATE, "Assessing evidence ambiguity and image fidelity")

        is_uncertain, uncertainty_reasons, operator_action = UncertaintyEvaluator.evaluate_perception_uncertainty(
            extracted_features
        )

        # If adversarial signal present, flag immediate exception
        if extracted_features.adversarial_signals:
            discrepancies = extracted_features.adversarial_signals
        else:
            discrepancies = []

        # Phase 4: Verdict Arbitration
        ctx.transition_to(AgentState.ARBITRATING_VERDICT, "Synthesizing checks into final inspection verdict")

        verdict, confidence, check_discrepancies, summary = UncertaintyEvaluator.arbitrate_final_verdict(
            checks=checks,
            is_uncertain=is_uncertain,
            uncertainty_reasons=uncertainty_reasons
        )
        discrepancies.extend(check_discrepancies)

        # Phase 5: Dossier Assembly & Sealing
        ctx.transition_to(AgentState.SEALING_DOSSIER, "Building immutable dispute dossier with SHA-256 seal")

        elapsed_ms = (time.time() - start_time) * 1000.0
        image_meta["processing_time_ms"] = round(elapsed_ms, 2)

        record = EvidenceDossierBuilder.create_evidence_record(
            po=po,
            verdict=verdict,
            overall_confidence=confidence,
            summary=summary,
            checks=checks,
            damages=extracted_features.detected_damages,
            discrepancies=discrepancies,
            missing_components=extracted_features.missing_components,
            bounding_boxes=extracted_features.bounding_boxes,
            image_metadata=image_meta,
            uncertainty_reasons=uncertainty_reasons,
            operator_action=operator_action,
            audit_trail=ctx.audit_trail
        )

        ctx.transition_to(AgentState.COMPLETED, f"Inspection completed in {elapsed_ms:.1f}ms. Sealed hash: {record.immutable_sha256[:12]}")
        return record
