"""
FastAPI Application Entry Point for InspectIQ™ Visual Inspection System.
"""

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
import os
import uvicorn

from .api.routes_scenarios import router as scenarios_router
from .api.routes_inspect import router as inspect_router
from .api.routes_dossier import router as dossier_router
from .api.routes_auth import router as auth_router

app = FastAPI(
    title="InspectIQ™ — Autonomous Inbound PO Verification & Vision Agent",
    description="Production-grade AI Vision agent for warehouse receiving quality control and PO verification.",
    version="2.6.0"
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include Routers
app.include_router(auth_router)
app.include_router(scenarios_router)
app.include_router(inspect_router)
app.include_router(dossier_router)

# Mount Static Directories
images_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "data", "images"))
os.makedirs(images_dir, exist_ok=True)
app.mount("/static/images", StaticFiles(directory=images_dir), name="images")

uploads_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "data", "uploads"))
os.makedirs(uploads_dir, exist_ok=True)
app.mount("/static/uploads", StaticFiles(directory=uploads_dir), name="uploads")

frontend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "frontend"))
os.makedirs(frontend_dir, exist_ok=True)
app.mount("/static/ui", StaticFiles(directory=frontend_dir), name="ui")


@app.get("/")
def serve_index():
    """Serves the main inspection dashboard web interface."""
    index_file = os.path.join(frontend_dir, "index.html")
    if os.path.exists(index_file):
        return FileResponse(index_file)
    return {"message": "Receiving Inspection Agent API is running.", "docs": "/docs"}


@app.get("/healthz")
def health_check():
    return {
        "status": "HEALTHY",
        "service": "InspectIQ",
        "version": "2.6.0",
        "state_machine": "ONLINE",
        "uncertainty_calibrator": "ACTIVE",
        "deterministic_engine": "ACTIVE"
    }


if __name__ == "__main__":
    uvicorn.run("backend.app.main:app", host="127.0.0.1", port=5173, reload=True)
