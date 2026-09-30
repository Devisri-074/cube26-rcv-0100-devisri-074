"""
Unit and Integration tests for Custom Manual Inbound Inspection & History Archive.
"""

import pytest
from fastapi.testclient import TestClient
from PIL import Image
import io
import os
from backend.app.main import app
from backend.app.core.models import DamageType, InspectionVerdict

client = TestClient(app)


def create_test_image(color=(30, 110, 220), size=(640, 480)) -> bytes:
    img = Image.new("RGB", size, color=color)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def test_custom_inspection_conforming():
    # Load canonical correct image
    img_path = os.path.join("data", "images", "scenario_01_correct.png")
    with open(img_path, "rb") as f:
        img_bytes = f.read()

    response = client.post(
        "/api/inspect/custom",
        files={"file": ("test_conforming.png", img_bytes, "image/png")},
        data={
            "po_number": "PO-2026-TEST-001",
            "sku": "BLUE-BOTTLE-001",
            "expected_quantity": 24,
            "units_per_carton": 12,
            "expected_variant": "Blue",
            "supplier_name": "Apex Hydration Mfg Ltd",
            "unit_price": 18.50,
            "required_components": "Bottle Body, Insulated Cap"
        }
    )

    assert response.status_code == 200
    data = response.json()
    assert data["verdict"] == "ACCEPT"
    assert data["overall_confidence"] >= 0.90
    assert len(data["bounding_boxes"]) > 0
    assert "image_url" in data
    assert data["image_url"].startswith("/static/uploads/")


def test_custom_inspection_crushed_carton_defect():
    # Upload crushed carton image
    img_path = os.path.join("data", "images", "scenario_06_crushed.png")
    with open(img_path, "rb") as f:
        img_bytes = f.read()

    response = client.post(
        "/api/inspect/custom",
        files={"file": ("test_crushed.png", img_bytes, "image/png")},
        data={
            "po_number": "PO-2026-TEST-CRUSH",
            "sku": "BLUE-BOTTLE-001",
            "expected_quantity": 24,
            "units_per_carton": 12,
            "expected_variant": "Blue",
            "supplier_name": "Apex Hydration Mfg Ltd",
            "unit_price": 18.50
        }
    )

    assert response.status_code == 200
    data = response.json()
    assert data["verdict"] == "EXCEPTION"
    assert "CRUSHED_CARTON" in data["detected_damages"]
    assert any("DAMAGE" in d or "Carton integrity" in d for d in data["discrepancies"])
    assert data["dispute_claim_amount_usd"] > 0


def test_custom_inspection_shortage():
    # Upload shortage image (22 units instead of 24)
    img_path = os.path.join("data", "images", "scenario_02_shortage.png")
    with open(img_path, "rb") as f:
        img_bytes = f.read()

    response = client.post(
        "/api/inspect/custom",
        files={"file": ("test_shortage.png", img_bytes, "image/png")},
        data={
            "po_number": "PO-2026-TEST-SHORT",
            "sku": "BLUE-BOTTLE-001",
            "expected_quantity": 24,
            "units_per_carton": 12,
            "expected_variant": "Blue",
            "supplier_name": "Apex Hydration Mfg Ltd",
            "unit_price": 18.50
        }
    )

    assert response.status_code == 200
    data = response.json()
    assert data["verdict"] == "EXCEPTION"
    qty_check = data["checks"]["QUANTITY_COUNT"]
    assert qty_check["status"] == "FAIL"
    assert qty_check["observed_value"] == 22
    assert qty_check["discrepancy_delta"] == -2


def test_manual_history_api():
    # Retrieve history
    response = client.get("/api/inspect/history")
    assert response.status_code == 200
    history = response.json()
    assert isinstance(history, list)
    assert len(history) >= 3

    # Check first record structure
    first = history[0]
    assert "record_id" in first
    assert "po_number" in first
    assert "verdict" in first
    assert "image_url" in first
    assert "evidence_record" in first

    # Retrieve specific record
    rec_id = first["record_id"]
    rec_res = client.get(f"/api/inspect/history/{rec_id}")
    assert rec_res.status_code == 200
    assert rec_res.json()["record_id"] == rec_id
