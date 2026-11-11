"""Autodetect of a serial autopilot port."""

import os
from pathlib import Path

from eltorpedo.mav import serial_candidates


def test_recent_serial_port_wins_and_tty_acm_ignored(tmp_path: Path):
    root = tmp_path
    old = root / "ttyUSB0"
    new = root / "ttyACM0"
    uart = root / "ttyTHS1"
    for path in (old, new, uart):
        path.write_text("")
    now = os.stat(new).st_mtime
    os.utime(old, (now - 3600, now - 3600))
    os.utime(uart, (now - 3600, now - 3600))
    assert serial_candidates(str(root)) == [str(new)]


def test_boot_uart_never_picked(tmp_path: Path):
    uart = tmp_path / "ttyTHS1"
    uart.write_text("")
    os.utime(uart, (0, 0))
    assert serial_candidates(str(tmp_path)) == []