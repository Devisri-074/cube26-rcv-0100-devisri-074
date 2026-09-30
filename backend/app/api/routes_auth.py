"""
Authentication & Role-Based Access Control API Routes.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional
import uuid

router = APIRouter(prefix="/api/auth", tags=["Auth"])


class UserProfile(BaseModel):
    user_id: str
    username: str
    full_name: str
    role: str
    role_title: str
    dock_station: str
    badge_id: str
    permissions: List[str]
    avatar_initials: str


class LoginRequest(BaseModel):
    username: str
    password: Optional[str] = "admin123"


# Enterprise Personas Database
USERS_DB = {
    "devis": UserProfile(
        user_id="USR-8801",
        username="devis",
        full_name="Devis Patel",
        role="RECEIVING_OPERATOR",
        role_title="Inbound Receiving Specialist",
        dock_station="Dock Bay #04 (North)",
        badge_id="BADGE-RCV-8801",
        permissions=["ingest_po", "upload_photos", "view_inspections", "request_override"],
        avatar_initials="DP"
    ),
    "elena": UserProfile(
        user_id="USR-9022",
        username="elena",
        full_name="Dr. Elena Vance",
        role="QA_LEAD",
        role_title="Lead Quality Assurance Officer",
        dock_station="QA Inspection Lab A",
        badge_id="BADGE-QA-9022",
        permissions=["ingest_po", "upload_photos", "view_inspections", "calibrate_thresholds", "approve_exceptions", "sign_dossier"],
        avatar_initials="EV"
    ),
    "marcus": UserProfile(
        user_id="USR-1044",
        username="marcus",
        full_name="Marcus Sterling",
        role="OPERATIONS_DIRECTOR",
        role_title="Warehouse Operations Director",
        dock_station="Central Terminal Operations",
        badge_id="BADGE-DIR-1044",
        permissions=["all", "view_analytics", "export_claims", "sign_dossier", "manage_system"],
        avatar_initials="MS"
    )
}

CURRENT_SESSION = {"user": USERS_DB["devis"]}


@router.get("/users", response_model=List[UserProfile])
def list_available_personas():
    """Returns list of pre-configured demo user personas."""
    return list(USERS_DB.values())


@router.get("/me", response_model=UserProfile)
def get_current_user():
    """Returns currently authenticated user profile."""
    return CURRENT_SESSION["user"]


@router.post("/login", response_model=UserProfile)
def login_user(payload: LoginRequest):
    """Logs in or switches to a user persona."""
    username = payload.username.lower().strip()
    if username in USERS_DB:
        user = USERS_DB[username]
        CURRENT_SESSION["user"] = user
        return user
    
    # Custom write-in user
    custom_user = UserProfile(
        user_id=f"USR-{uuid.uuid4().hex[:4].upper()}",
        username=username,
        full_name=username.capitalize(),
        role="RECEIVING_OPERATOR",
        role_title="Receiving Operator",
        dock_station="Dock Station 1",
        badge_id=f"BADGE-{uuid.uuid4().hex[:4].upper()}",
        permissions=["ingest_po", "upload_photos", "view_inspections"],
        avatar_initials=username[:2].upper()
    )
    CURRENT_SESSION["user"] = custom_user
    return custom_user
