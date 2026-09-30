"""
Receiving Inspection API Routes.
Provides endpoints for custom image uploads, interactive visual inspection,
and persistent manual inspection intake history.
"""

from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from typing import Optional, List, Dict, Any
from PIL import Image
import io
import os
import json
import uuid
import time
from datetime import datetime, timezone
from ..core.models import PurchaseOrderItem, EvidenceRecord, VisualFeatureExtraction, DamageType, BoundingBox
from ..core.vision_agent import ReceivingInspectionAgent
from ..core.image_analysis import ImageAnalysisPipeline

router = APIRouter(prefix="/api/inspect", tags=["Inspection"])
agent = ReceivingInspectionAgent()

UPLOADS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "data", "uploads"))
HISTORY_FILE = os.path.join(UPLOADS_DIR, "manual_inspections.json")
os.makedirs(UPLOADS_DIR, exist_ok=True)


def _load_history() -> List[Dict[str, Any]]:
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []
    return []


def _save_history(history: List[Dict[str, Any]]) -> None:
    try:
        with open(HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(history, f, indent=2)
    except Exception as e:
        print(f"Error saving manual inspection history: {e}")


# In-memory cached history
_manual_history: List[Dict[str, Any]] = _load_history()


@router.post("/custom", response_model=Dict[str, Any])
async def inspect_custom_shipment(
    file: UploadFile = File(...),
    po_number: str = Form("PO-2026-LIVE-8801"),
    sku: str = Form("BLUE-BOTTLE-001"),
    asin_or_upc: Optional[str] = Form("810092345001"),
    expected_quantity: int = Form(24),
    units_per_carton: int = Form(12),
    expected_variant: str = Form("Blue"),
    supplier_name: str = Form("Apex Hydration Mfg Ltd"),
    unit_price: float = Form(18.50),
    required_components: str = Form("Bottle Body, Insulated Cap")
):
    """
    Accepts an uploaded image and Purchase Order parameters, runs full agentic inspection,
    persists the image and inspection results to manual intake history.
    """
    try:
        contents = await file.read()
        image = Image.open(io.BytesIO(contents))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid image file: {str(e)}")

    # Generate a unique filename and save image to uploads directory
    timestamp_str = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    unique_id = uuid.uuid4().hex[:6]
    image_filename = f"upload_{timestamp_str}_{unique_id}.png"
    saved_image_path = os.path.join(UPLOADS_DIR, image_filename)
    
    try:
        image.save(saved_image_path, format="PNG")
        image_url = f"/static/uploads/{image_filename}"
    except Exception as e:
        image_url = ""

    components_list = [c.strip() for c in required_components.split(",") if c.strip()]

    po = PurchaseOrderItem(
        po_number=po_number,
        sku=sku,
        asin_or_upc=asin_or_upc or "810092345001",
        expected_quantity=expected_quantity,
        units_per_carton=units_per_carton,
        expected_variant=expected_variant,
        supplier_name=supplier_name,
        unit_price=unit_price,
        required_components=components_list
    )

    # Perform comprehensive visual analysis and defect detection
    features = ImageAnalysisPipeline.extract_comprehensive_features(
        image=image,
        po=po
    )

    # Execute vision agent inspection pipeline
    raw_meta = {
        "source": "manual_upload",
        "original_filename": file.filename or "uploaded_photo.png",
        "image_url": image_url,
        "width": image.width,
        "height": image.height,
        "uploaded_at": datetime.now(timezone.utc).isoformat()
    }

    record = agent.inspect_shipment(
        po=po,
        image=image,
        extracted_features=features,
        raw_metadata=raw_meta
    )

    # Construct complete response payload
    record_dict = record.model_dump()
    po_dict = po.model_dump()

    history_entry = {
        "record_id": record.record_id,
        "po_number": po.po_number,
        "sku": po.sku,
        "expected_quantity": po.expected_quantity,
        "expected_variant": po.expected_variant,
        "supplier_name": po.supplier_name,
        "unit_price": po.unit_price,
        "verdict": record.verdict.value,
        "overall_confidence": record.overall_confidence,
        "summary": record.summary,
        "detected_damages": [d.value for d in record.detected_damages],
        "discrepancies": record.discrepancies,
        "image_url": image_url,
        "created_at": record.created_at,
        "immutable_sha256": record.immutable_sha256,
        "po": po_dict,
        "evidence_record": record_dict
    }

    # Prepend to manual history and persist to disk
    _manual_history.insert(0, history_entry)
    _save_history(_manual_history)

    # Return combined dictionary with all record fields and metadata
    result = dict(record_dict)
    result["image_url"] = image_url
    result["po"] = po_dict
    result["evidence_record"] = record_dict

    return result


@router.get("/history", response_model=List[Dict[str, Any]])
def get_manual_inspection_history():
    """
    Returns list of all manually checked receiving images and their inspection records.
    """
    return _manual_history


@router.get("/history/{record_id}", response_model=Dict[str, Any])
def get_manual_inspection_record(record_id: str):
    """
    Retrieves a specific manually inspected record by record_id.
    """
    for entry in _manual_history:
        if entry.get("record_id") == record_id:
            return entry
    raise HTTPException(status_code=404, detail=f"Manual inspection record '{record_id}' not found.")


@router.delete("/history/{record_id}")
def delete_manual_inspection_record(record_id: str):
    """
    Deletes a specific manual inspection record from history.
    """
    global _manual_history
    _manual_history = [e for e in _manual_history if e.get("record_id") != record_id]
    _save_history(_manual_history)
    return {"message": f"Record '{record_id}' deleted successfully."}


@router.delete("/history")
def clear_manual_inspection_history():
    """
    Clears all manual inspection history.
    """
    global _manual_history
    _manual_history = []
    _save_history(_manual_history)
    return {"message": "All manual inspection history cleared successfully."}

