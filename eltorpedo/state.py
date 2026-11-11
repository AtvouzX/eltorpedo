"""Shared runtime state for the TUI."""

from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass, field

from .claw import ClawStatus


@dataclass
class Message:
    text: str
    severity: int = 6
    at: float = field(default_factory=time.time)


@dataclass
class VehicleState:
    link_ok: bool = False
    link_lost: bool = False
    last_heartbeat: float = 0.0
    system_id: int = 0
    component_id: int = 0
    mode_id: int = -1
    armed: bool = False
    depth_m: float | None = None
    roll_deg: float = 0.0
    pitch_deg: float = 0.0
    yaw_deg: float = 0.0
    battery_voltage: float | None = None
    battery_current: float | None = None
    battery_remaining: int | None = None
    axes: tuple[int, int, int, int] = (0, 0, 0, 0)
    gamepad_ok: bool = False
    gamepad_name: str = ""
    gamepad_seen: bool = False
    messages: deque[Message] = field(default_factory=lambda: deque(maxlen=5))
    claw: ClawStatus = field(default_factory=ClawStatus)
    params: dict[str, float] = field(default_factory=dict)
    claw_errors: list[str] = field(default_factory=list)

    def add_message(self, text: str, severity: int = 6) -> None:
        self.messages.append(Message(text=text, severity=severity))
