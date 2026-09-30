"""
Evidence Dossier and Dispute Claim Export API Routes.
"""

from fastapi import APIRouter, HTTPException, Response
from typing import Dict, Any
from ..core.models import EvidenceRecord, PurchaseOrderItem
from ..core.evidence_dossier import EvidenceDossierBuilder
from ..scenarios.dataset import ScenarioRepository

router = APIRouter(prefix="/api/dossier", tags=["Dossier"])


@router.post("/render-markdown")
def render_dossier_markdown(payload: Dict[str, Any]):
    """Renders formatted Markdown for an EvidenceRecord and PO."""
    try:
        record_data = payload.get("evidence_record")
        po_data = payload.get("po")
        if not record_data or not po_data:
            raise HTTPException(status_code=400, detail="Both 'evidence_record' and 'po' required.")

        record = EvidenceRecord.model_validate(record_data)
        po = PurchaseOrderItem.model_validate(po_data)
        markdown_text = EvidenceDossierBuilder.generate_dispute_markdown(record, po)
        return {"markdown": markdown_text, "record_id": record.record_id}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
