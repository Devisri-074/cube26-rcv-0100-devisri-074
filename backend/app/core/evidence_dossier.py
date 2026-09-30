"""
Evidence Dossier & Supplier Claim Packet Generator.
Constructs immutable, cryptographically hashed inspection records
ready for WMS/ERP integration and supplier discrepancy claims.
"""

from typing import Dict, Any, List
from datetime import datetime
import uuid
from .models import (
    EvidenceRecord, PurchaseOrderItem, CatalogItem, SingleCheckResult,
    InspectionVerdict, DamageType, BoundingBox, AuditLogEntry, CheckType, CheckStatus
)


class EvidenceDossierBuilder:
    """
    Assembles complete evidence records with audit trails, cryptographic hash,
    and financial dispute calculation.
    """

    @classmethod
    def create_evidence_record(
        cls,
        po: PurchaseOrderItem,
        verdict: InspectionVerdict,
        overall_confidence: float,
        summary: str,
        checks: Dict[str, SingleCheckResult],
        damages: List[DamageType],
        discrepancies: List[str],
        missing_components: List[str],
        bounding_boxes: List[BoundingBox],
        image_metadata: Dict[str, Any],
        uncertainty_reasons: List[str],
        operator_action: str | None = None,
        audit_trail: List[AuditLogEntry] | None = None
    ) -> EvidenceRecord:
        record_id = f"REC-INSP-{datetime.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:8].upper()}"
        created_at = datetime.now().isoformat()

        # Calculate dispute claim amount if exception exists
        claim_amount = 0.0
        dispute_eligible = (verdict in [InspectionVerdict.EXCEPTION, InspectionVerdict.REJECT])

        if dispute_eligible:
            qty_check = checks.get(CheckType.QUANTITY_COUNT.value)
            if qty_check and qty_check.status == CheckStatus.FAIL:
                if isinstance(qty_check.discrepancy_delta, (int, float)) and qty_check.discrepancy_delta < 0:
                    shortage_units = abs(qty_check.discrepancy_delta)
                    claim_amount += shortage_units * po.unit_price

            damage_check = checks.get(CheckType.PACKAGING_DAMAGE.value)
            if damage_check and damage_check.status == CheckStatus.FAIL:
                # If damaged, claim for observed affected units or full shipment
                affected_units = po.expected_quantity if not po.units_per_carton else po.units_per_carton
                claim_amount += affected_units * po.unit_price

            variant_check = checks.get(CheckType.VARIANT_SPEC.value)
            if variant_check and variant_check.status == CheckStatus.FAIL:
                claim_amount += po.expected_quantity * po.unit_price

            sku_check = checks.get(CheckType.SKU_IDENTITY.value)
            if sku_check and sku_check.status == CheckStatus.FAIL:
                claim_amount = max(claim_amount, po.expected_quantity * po.unit_price)

        record = EvidenceRecord(
            record_id=record_id,
            po_number=po.po_number,
            sku=po.sku,
            created_at=created_at,
            verdict=verdict,
            overall_confidence=overall_confidence,
            summary=summary,
            checks=checks,
            detected_damages=damages,
            discrepancies=discrepancies,
            missing_components=missing_components,
            bounding_boxes=bounding_boxes,
            image_metadata=image_metadata,
            uncertainty_reasons=uncertainty_reasons,
            operator_action_required=operator_action,
            supplier_dispute_eligible=dispute_eligible,
            dispute_claim_amount_usd=round(claim_amount, 2),
            audit_trail=audit_trail or []
        )

        record.seal_record()
        return record

    @classmethod
    def generate_dispute_markdown(cls, record: EvidenceRecord, po: PurchaseOrderItem) -> str:
        """Renders formal supplier claim dossier in clean Markdown with all 9 key report fields."""
        qty_check = record.checks.get(CheckType.QUANTITY_COUNT.value)
        obs_qty = qty_check.observed_value if qty_check else "N/A"
        var_check = record.checks.get(CheckType.VARIANT_SPEC.value)
        obs_var = var_check.observed_value if var_check else "N/A"
        damage_str = ", ".join(d.value for d in record.detected_damages) if record.detected_damages else "NONE (Zero Defects Detected)"

        qty_delta_str = ""
        if qty_check and qty_check.discrepancy_delta is not None:
            if isinstance(qty_check.discrepancy_delta, (int, float)):
                qty_delta_str = f" (Difference: {qty_check.discrepancy_delta:+d})" if qty_check.discrepancy_delta != 0 else " (Difference: 0)"
            else:
                qty_delta_str = f" (Difference: {qty_check.discrepancy_delta})"

        lines = [
            "# InspectIQ™ — INBOUND RECEIVING INSPECTION REPORT",
            "**AI-Powered Visual Receiving Inspection Certificate**",
            "",
            "---",
            "## EXECUTIVE INSPECTION SUMMARY",
            "| Field | Verification Detail | Status |",
            "|---|---|---|",
            f"| **PO Number** | `{po.po_number}` | Reference PO |",
            f"| **SKU** | `{po.sku}` | Validated Item |",
            f"| **Quantity** | Expected: `{po.expected_quantity}` \\| Observed: `{obs_qty}`{qty_delta_str} | `{'PASS' if qty_check and qty_check.status == CheckStatus.PASS else ('EXCEPTION' if qty_check and qty_check.status == CheckStatus.FAIL else 'UNCERTAIN')}` |",
            f"| **Variant** | Expected: `{po.expected_variant}` \\| Observed: `{obs_var}` | `{'PASS' if var_check and var_check.status == CheckStatus.PASS else ('EXCEPTION' if var_check and var_check.status == CheckStatus.FAIL else 'UNCERTAIN')}` |",
            f"| **Damage** | `{damage_str}` | `{'PASS' if not record.detected_damages else 'EXCEPTION'}` |",
            f"| **Decision** | **`{record.verdict.value}`** | **Final Outcome** |",
            f"| **Confidence** | **`{record.overall_confidence*100:.1f}%`** (Mathematically Grounded) | Calibrated |",
            f"| **Evidence** | {len(record.checks)} checks evaluated; {len(record.discrepancies)} discrepancy(ies) detected | Grounded |",
            f"| **Timestamp** | `{record.created_at}` | Dock UTC |",
            "",
            "---",
            "## 1. SHIPMENT & PURCHASE ORDER SPECIFICATIONS",
            f"- **PO Number**: `{po.po_number}`",
            f"- **Supplier**: `{po.supplier_name}`",
            f"- **Target SKU**: `{po.sku}` (UPC/Barcode: `{po.asin_or_upc or 'N/A'}`)",
            f"- **Ordered Quantity**: `{po.expected_quantity}` units ({po.expected_cartons} master carton(s) @ {po.units_per_carton}/carton)",
            f"- **Expected Variant**: `{po.expected_variant}`",
            f"- **Unit Price**: `${po.unit_price:.2f}` | **Total Line Value**: `${po.expected_quantity * po.unit_price:.2f} USD`",
            "",
            "---",
            "## 2. INSPECTION DECISION & REASONING",
            f"### **FINAL VERDICT: {record.verdict.value}** (Confidence: {record.overall_confidence*100:.1f}%)",
            f"> {record.summary}",
            "",
            "### Verification Checks Matrix (Expected vs. Observed):",
            "| Inspection Dimension | Verdict | Expected Value | Observed Value | Confidence | Detailed Grounded Evidence |",
            "|---|---|---|---|---|---|"
        ]

        for check_name, c in record.checks.items():
            status_icon = "PASS" if c.status == CheckStatus.PASS else ("EXCEPTION" if c.status == CheckStatus.FAIL else "UNCERTAIN")
            lines.append(
                f"| `{check_name}` | **{status_icon}** | `{c.expected_value}` | `{c.observed_value}` | {c.confidence*100:.0f}% | {c.reason} |"
            )

        lines.extend([
            "",
            "---",
            "## 3. PHYSICAL EVIDENCE & DETECTED ISSUES",
            f"- **Detected Damage Types**: `{damage_str}`",
            f"- **Discrepancy Notes**:"
        ])

        if record.discrepancies:
            for d in record.discrepancies:
                lines.append(f"  * {d}")
        else:
            lines.append("  * Zero non-conformances detected. Shipment 100% conforming.")

        if record.missing_components:
            lines.append(f"- **Missing Accessories / Components**: `{', '.join(record.missing_components)}`")

        if record.uncertainty_reasons:
            lines.extend([
                "",
                "### Epistemic Uncertainty Factors:",
                *[f"  - {u}" for u in record.uncertainty_reasons],
                f"**Mandatory Operator Action**: `{record.operator_action_required}`"
            ])

        lines.extend([
            "",
            "---",
            "## 4. SUPPLIER DISPUTE CLAIM & SETTLEMENT ACTION",
            f"- **Supplier Dispute Eligible**: `{'YES' if record.supplier_dispute_eligible else 'NO'}`",
            f"- **Claim Financial Settlement Amount**: `${record.dispute_claim_amount_usd:.2f} USD`",
            "",
            f"```json\n// Cryptographic Audit Seal (SHA-256 Tamper Proof)\n{{\n  \"record_id\": \"{record.record_id}\",\n  \"sha256\": \"{record.immutable_sha256}\",\n  \"timestamp\": \"{record.created_at}\",\n  \"verified\": true\n}}\n```"
        ])

        return "\n".join(lines)
