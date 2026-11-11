"""Thin MAVLink wrapper around pymavlink."""

from __future__ import annotations

import glob
import os
import time

from pymavlink import mavutil

from .config import LinkConfig

# ArduSub message ids used by the dashboard.
STREAMS: tuple[tuple[int, float], ...] = (
    (mavutil.mavlink.MAVLINK_MSG_ID_ATTITUDE, 10.0),
    (mavutil.mavlink.MAVLINK_MSG_ID_GLOBAL_POSITION_INT, 5.0),
    (mavutil.mavlink.MAVLINK_MSG_ID_BATTERY_STATUS, 1.0),
    (mavutil.mavlink.MAVLINK_MSG_ID_SYS_STATUS, 1.0),
    (mavutil.mavlink.MAVLINK_MSG_ID_HEARTBEAT, 1.0),
)


class MavLink:
    def __init__(self, cfg: LinkConfig) -> None:
        self.cfg = cfg
        self.conn = None
        self.target_system = 1
        self.target_component = 1
        self.endpoint = ""

    def open(self) -> None:
        self.endpoint = ""
        if self.cfg.autodetect and self.cfg.endpoint == LinkConfig.endpoint:
            # Default endpoint: take the first serial autopilot found, if any.
            device = next(iter(serial_candidates()), "")
            if device:
                self.endpoint = f"serial:{device}:{self.cfg.autodetect_baud}"
        if not self.endpoint:
            self.endpoint = self.cfg.endpoint
        self.conn = mavutil.mavlink_connection(
            self.endpoint,
            source_system=self.cfg.source_system,
            source_component=self.cfg.source_component,
            autoreconnect=True,
        )

    def close(self) -> None:
        if self.conn is not None:
            try:
                self.conn.close()
            except Exception:
                pass
            self.conn = None

    def recv(self):
        if self.conn is None:
            return None
        try:
            return self.conn.recv_match(blocking=False)
        except Exception:
            return None

    def set_target(self, system: int, component: int) -> None:
        if system:
            self.target_system = system
        if component:
            self.target_component = component

    def send_heartbeat(self) -> None:
        if self.conn is None:
            return
        self.conn.mav.heartbeat_send(
            mavutil.mavlink.MAV_TYPE_GCS,
            mavutil.mavlink.MAV_AUTOPILOT_INVALID,
            0,
            0,
            0,
        )

    def send_manual_control(self, x: int, y: int, z: int, r: int, buttons: int = 0) -> None:
        if self.conn is None:
            return
        self.conn.mav.manual_control_send(
            self.target_system,
            _clamp(x),
            _clamp(y),
            _clamp(z),
            _clamp(r),
            buttons & 0xFFFF,
        )

    def arm(self, arm: bool) -> None:
        if self.conn is None:
            return
        self.conn.mav.command_long_send(
            self.target_system,
            self.target_component,
            mavutil.mavlink.MAV_CMD_COMPONENT_ARM_DISARM,
            0,
            1.0 if arm else 0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
        )

    def set_mode(self, mode_id: int) -> None:
        if self.conn is None:
            return
        self.conn.mav.set_mode_send(
            self.target_system,
            mavutil.mavlink.MAV_MODE_FLAG_CUSTOM_MODE_ENABLED,
            mode_id,
        )

    def request_param(self, name: str) -> None:
        if self.conn is None:
            return
        self.conn.mav.param_request_read_send(
            self.target_system,
            self.target_component,
            name.encode("ascii"),
            -1,
        )

    def set_param(self, name: str, value: float) -> None:
        if self.conn is None:
            return
        self.conn.mav.param_set_send(
            self.target_system,
            self.target_component,
            name.encode("ascii"),
            float(value),
            mavutil.mavlink.MAV_PARAM_TYPE_INT32,
        )

    def set_message_interval(self, message_id: int, hz: float) -> None:
        if self.conn is None:
            return
        interval_us = int(1_000_000 / hz) if hz > 0 else -1
        self.conn.mav.command_long_send(
            self.target_system,
            self.target_component,
            mavutil.mavlink.MAV_CMD_SET_MESSAGE_INTERVAL,
            0,
            float(message_id),
            float(interval_us),
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
        )

    def request_streams(self) -> None:
        for message_id, hz in STREAMS:
            self.set_message_interval(message_id, hz)


def serial_candidates(dev_root: str = "/dev", modified_within_s: float = 10.0) -> list[str]:
    """Serial autopilot ports, most recently added first.

    Only devices attached in the last few seconds qualify, so a UART port that
    exists from boot is never picked over a cable that was just plugged in.
    """
    cutoff = time.time() - modified_within_s
    found = []
    for pattern in ("ttyUSB*", "ttyACM*"):
        for path in glob.glob(f"{dev_root}/{pattern}"):
            try:
                if os.stat(path).st_mtime >= cutoff:
                    found.append(path)
            except OSError:
                continue
    return sorted(found, key=lambda p: os.stat(p).st_mtime, reverse=True)


def _clamp(value: int) -> int:
    return max(-1000, min(1000, int(value)))
