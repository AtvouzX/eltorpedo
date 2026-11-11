"""Claw state parsing and parameter checks.

The BTS7960 backend reports through STATUSTEXT only. There is no structured
state message in the custom firmware, so the TUI keeps the last reported state
and the live GRIP_DC_CURR value.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ClawStatus:
    state: str = "UNKNOWN"
    detail: str = ""
    fault: bool = False
    current_ma: int | None = None
    unavailable: bool = False


def parse_statustext(text: str, status: ClawStatus) -> bool:
    """Update *status* from a firmware message. Return True when it was a claw message."""
    if not text.lower().startswith("claw:"):
        return False

    body = text.split(":", 1)[1].strip()
    lowered = body.lower()

    if lowered.startswith("fault"):
        status.state = "FAULT"
        status.fault = True
        status.unavailable = False
        status.detail = body.split("-", 1)[1].strip() if "-" in body else body
        return True

    if lowered in ("outputs not assigned", "gripperdcfwd/rev outputs not assigned"):
        status.state = "UNAVAILABLE"
        status.fault = False
        status.unavailable = True
        status.detail = body
        return True

    if lowered == "ina219 not found":
        status.state = "UNAVAILABLE"
        status.fault = False
        status.unavailable = True
        status.detail = body
        return True

    if lowered.startswith("no enable output"):
        status.state = "UNAVAILABLE"
        status.fault = False
        status.unavailable = True
        status.detail = body
        return True

    mapping = {
        "closing": "CLOSING",
        "opening": "OPENING",
        "stopped": "IDLE",
        "object grasped, holding": "HOLDING",
        "object grasped": "HOLDING",
        "fully closed": "CLOSED",
        "fully open": "OPEN",
        "already closed": "CLOSED",
        "already open": "OPEN",
        "fault active, stop to reset": "FAULT",
    }
    state = mapping.get(lowered)
    if state is None:
        status.detail = body
        return True

    status.state = state
    status.detail = body
    status.fault = state == "FAULT"
    status.unavailable = False
    return True


def config_errors(params: dict[str, float], required: dict[str, int]) -> list[str]:
    """Return human-readable mismatches between current and required params."""
    errors: list[str] = []
    for name, wanted in required.items():
        if name not in params:
            errors.append(f"{name} not read")
            continue
        actual = int(round(params[name]))
        if actual != wanted:
            errors.append(f"{name}={actual}, need {wanted}")
    return errors
