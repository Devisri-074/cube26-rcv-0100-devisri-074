"""
Core Domain Data Models for InspectIQ™ Inspection Agent.
Defines schemas for Purchase Orders, Receiving Evidence, Inspection Verdicts,
Check Results, and Cryptographic Evidence Records.
"""

from __future__ import annotations
from enum import Enum
from typing import List, Dict, Optional, Any, Union
from datetime import datetime
import hashlib
import json
from pydantic import BaseModel, Field


class InspectionVerdict(str, Enum):
    ACCEPT = "ACCEPT"                          # All checks PASS with high confidence
    EXCEPTION = "EXCEPTION"                    # One or more non-conformances detected (damage, short, wrong variant)
    UNCERTAIN = "UNCERTAIN"                    # Insufficient, occluded, or ambiguous visual evidence; operator intervention needed
    REJECT = "REJECT"                          # Critical violation (e.g. counterfeit, unmanifested wrong SKU, hazardous defect)


class CheckStatus(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    UNCERTAIN = "UNCERTAIN"
    SKIPPED = "SKIPPED"


class CheckType(str, Enum):
    SKU_IDENTITY = "SKU_IDENTITY"
    QUANTITY_COUNT = "QUANTITY_COUNT"
    VARIANT_SPEC = "VARIANT_SPEC"
    CARTON_INTEGRITY = "CARTON_INTEGRITY"
    PACKAGING_DAMAGE = "PACKAGING_DAMAGE"
    COMPONENT_INTEGRITY = "COMPONENT_INTEGRITY"
    LABEL_BARCODE = "LABEL_BARCODE"


class DamageType(str, Enum):
    NONE = "NONE"
    CRUSHED_CARTON = "CRUSHED_CARTON"
    WATER_DAMAGE = "WATER_DAMAGE"
    TEAR_PUNCTURE = "TEAR_PUNCTURE"
    OPEN_SEAL = "OPEN_SEAL"
    DENTED_PRODUCT = "DENTED_PRODUCT"
    WRONG_VARIANT = "WRONG_VARIANT"
    MISSING_COMPONENTS = "MISSING_COMPONENTS"
    LABEL_TAMPERED = "LABEL_TAMPERED"
    OCCLUSION_BLUR = "OCCLUSION_BLUR"


class BoundingBox(BaseModel):
    x: float = Field(..., description="Top-left X coordinate normalized (0.0 to 1.0) or pixel")
    y: float = Field(..., description="Top-left Y coordinate normalized (0.0 to 1.0) or pixel")
    width: float = Field(..., description="Width normalized or pixel")
    height: float = Field(..., description="Height normalized or pixel")
    label: str = Field(default="", description="Annotation label (e.g., 'crushed_corner', 'sku_barcode')")
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    color: str = Field(default="#00ffcc", description="HEX color for visualization overlay")
    details: Optional[Dict[str, Any]] = Field(default_factory=dict)


class PurchaseOrderItem(BaseModel):
    po_number: str = Field(..., description="Purchase Order Number (e.g. 'PO-2026-8891')")
    sku: str = Field(..., description="SKU identifier (e.g. 'BLUE-BOTTLE-001')")
    asin_or_upc: Optional[str] = Field(default="", description="UPC, EAN or ASIN barcode")
    expected_quantity: int = Field(..., ge=0, description="Total expected units ordered")
    units_per_carton: int = Field(default=1, ge=1, description="Expected unit pack size per master carton")
    expected_cartons: Optional[int] = Field(default=None, description="Expected master cartons count")
    expected_variant: str = Field(..., description="Expected variant description (e.g. 'Blue', 'Matte Black')")
    supplier_name: str = Field(default="Standard Logistics Mfg", description="Supplier / Vendor name")
    unit_price: float = Field(default=0.0, description="Unit cost in USD for discrepancy calculation")
    required_components: List[str] = Field(default_factory=list, description="List of required parts/accessories")

    def model_post_init(self, __context: Any) -> None:
        if self.expected_cartons is None and self.units_per_carton > 0:
            self.expected_cartons = (self.expected_quantity + self.units_per_carton - 1) // self.units_per_carton


class CatalogItem(BaseModel):
    sku: str
    product_name: str
    category: str
    allowed_variants: List[str]
    standard_upc: str
    dimensions_cm: Optional[Dict[str, float]] = None
    weight_kg: Optional[float] = None
    primary_color_hex: Optional[str] = None
    standard_components: List[str] = Field(default_factory=list)


class VisualFeatureExtraction(BaseModel):
    observed_sku: Optional[str] = None
    observed_barcode: Optional[str] = None
    observed_quantity: Optional[int] = None
    observed_cartons: Optional[int] = None
    observed_variant: Optional[str] = None
    detected_damages: List[DamageType] = Field(default_factory=list)
    missing_components: List[str] = Field(default_factory=list)
    image_quality_score: float = Field(default=1.0, ge=0.0, le=1.0, description="Laplacian sharpness + contrast")
    occlusion_ratio: float = Field(default=0.0, ge=0.0, le=1.0, description="Fraction of carton/label obscured")
    ocr_raw_text: List[str] = Field(default_factory=list)
    bounding_boxes: List[BoundingBox] = Field(default_factory=list)
    visual_heatmaps: Optional[Dict[str, Any]] = None
    adversarial_signals: List[str] = Field(default_factory=list)


class SingleCheckResult(BaseModel):
    check_type: CheckType
    status: CheckStatus
    confidence: float = Field(..., ge=0.0, le=1.0)
    expected_value: Any
    observed_value: Any
    discrepancy_delta: Optional[Any] = None
    reason: str
    evidence_boxes: List[BoundingBox] = Field(default_factory=list)
    requires_operator_override: bool = False


class AuditLogEntry(BaseModel):
    step_id: str
    timestamp: str
    actor: str = "ReceivingInspectionAgent"
    action: str
    details: Dict[str, Any]


class EvidenceRecord(BaseModel):
    record_id: str
    po_number: str
    sku: str
    created_at: str
    verdict: InspectionVerdict
    overall_confidence: float = Field(..., ge=0.0, le=1.0)
    summary: str
    checks: Dict[str, SingleCheckResult]
    detected_damages: List[DamageType]
    discrepancies: List[str]
    missing_components: List[str]
    bounding_boxes: List[BoundingBox]
    image_metadata: Dict[str, Any]
    uncertainty_reasons: List[str] = Field(default_factory=list)
    operator_action_required: Optional[str] = None
    supplier_dispute_eligible: bool = False
    dispute_claim_amount_usd: float = 0.0
    audit_trail: List[AuditLogEntry] = Field(default_factory=list)
    immutable_sha256: str = ""

    def calculate_hash(self) -> str:
        """Computes a SHA-256 tamper-evident seal of the inspection findings."""
        hash_payload = {
            "record_id": self.record_id,
            "po_number": self.po_number,
            "sku": self.sku,
            "created_at": self.created_at,
            "verdict": self.verdict.value,
            "overall_confidence": round(self.overall_confidence, 4),
            "discrepancies": sorted(self.discrepancies),
            "damages": [d.value for d in self.detected_damages],
            "checks": {
                k: {
                    "status": v.status.value,
                    "expected": str(v.expected_value),
                    "observed": str(v.observed_value)
                } for k, v in self.checks.items()
            }
        }
        raw = json.dumps(hash_payload, sort_keys=True)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def seal_record(self) -> None:
        self.immutable_sha256 = self.calculate_hash()
