"""
Inspection Workflow State Machine.
Tracks execution transitions, timing, tool actions, and state invariants.
"""

from enum import Enum
from typing import Dict, Any, List
from datetime import datetime
from .models import AuditLogEntry


class AgentState(str, Enum):
    IDLE = "IDLE"
    INGESTING = "INGESTING"
    PERCEIVING = "PERCEIVING"
    EXTRACTING_FEATURES = "EXTRACTING_FEATURES"
    DETERMINISTIC_RULES = "DETERMINISTIC_RULES"
    UNCERTAINTY_GATE = "UNCERTAINTY_GATE"
    ARBITRATING_VERDICT = "ARBITRATING_VERDICT"
    SEALING_DOSSIER = "SEALING_DOSSIER"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class InspectionStateContext:
    def __init__(self, inspection_id: str, po_number: str):
        self.inspection_id = inspection_id
        self.po_number = po_number
        self.current_state = AgentState.IDLE
        self.audit_trail: List[AuditLogEntry] = []
        self.step_counter = 0

    def transition_to(self, new_state: AgentState, action_desc: str, details: Dict[str, Any] | None = None) -> None:
        self.step_counter += 1
        self.current_state = new_state
        entry = AuditLogEntry(
            step_id=f"STEP-{self.step_counter:03d}",
            timestamp=datetime.now().isoformat(),
            action=action_desc,
            details=details or {}
        )
        self.audit_trail.append(entry)
