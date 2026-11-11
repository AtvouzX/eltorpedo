"""Gamepad discovery, polling and axis shaping."""

from __future__ import annotations

import math
import os
import time
from dataclasses import dataclass

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame  # noqa: E402

from .config import AxisSpec, GamepadConfig, apply_profile  # noqa: E402


@dataclass(frozen=True)
class DeviceInfo:
    index: int
    name: str
    axes: int
    buttons: int
    hats: int


@dataclass
class RawInput:
    axes: tuple[float, ...] = ()
    buttons: tuple[bool, ...] = ()
    hat: tuple[int, int] = (0, 0)
    connected: bool = False
    name: str = ""


def _init_pygame() -> None:
    # Joystick events need an initialised video subsystem even on a headless host.
    if not pygame.display.get_init():
        pygame.display.init()
    if not pygame.joystick.get_init():
        pygame.joystick.init()


def list_devices() -> list[DeviceInfo]:
    """Return every connected controller. Re-scans so hot-plug is visible."""
    try:
        _init_pygame()
        try:
            pygame.event.pump()
        except pygame.error:
            pass
        devices: list[DeviceInfo] = []
        for index in range(pygame.joystick.get_count()):
            joystick = pygame.joystick.Joystick(index)
            joystick.init()
            devices.append(
                DeviceInfo(
                    index=index,
                    name=joystick.get_name(),
                    axes=joystick.get_numaxes(),
                    buttons=joystick.get_numbuttons(),
                    hats=joystick.get_numhats(),
                )
            )
            joystick.quit()
        return devices
    except Exception:
        return []


def choose_device(cfg: GamepadConfig, devices: list[DeviceInfo] | None = None) -> int | None:
    """Prefer a name match, then the configured index, then the first device."""
    devices = list_devices() if devices is None else devices
    if not devices:
        return None
    wanted = cfg.preferred_name.strip().lower()
    if wanted:
        for device in devices:
            if wanted in device.name.lower():
                return device.index
    if 0 <= cfg.index < len(devices):
        return cfg.index
    return devices[0].index


def shape_axis(value: float, spec: AxisSpec, deadzone: float) -> float:
    """Apply inversion, deadzone and rescale to -1..1."""
    if spec.invert:
        value = -value
    magnitude = abs(value)
    if magnitude < deadzone:
        return 0.0
    scaled = (magnitude - deadzone) / (1.0 - deadzone)
    return math.copysign(min(1.0, scaled), value)


def _read_axis(raw: RawInput, spec: AxisSpec) -> float:
    if 0 <= spec.index < len(raw.axes):
        return float(raw.axes[spec.index])
    return 0.0


def map_axes(raw: RawInput, cfg: GamepadConfig) -> tuple[int, int, int, int]:
    """Return MANUAL_CONTROL (x, y, z, r) in -1000..1000.

    x = forward, y = lateral, z = throttle, r = yaw.
    """
    forward = shape_axis(_read_axis(raw, cfg.axes["forward"]), cfg.axes["forward"], cfg.deadzone)
    lateral = shape_axis(_read_axis(raw, cfg.axes["lateral"]), cfg.axes["lateral"], cfg.deadzone)
    throttle = shape_axis(_read_axis(raw, cfg.axes["throttle"]), cfg.axes["throttle"], cfg.deadzone)
    yaw = shape_axis(_read_axis(raw, cfg.axes["yaw"]), cfg.axes["yaw"], cfg.deadzone)
    return (
        int(round(forward * 1000)),
        int(round(lateral * 1000)),
        int(round(throttle * 1000)),
        int(round(yaw * 1000)),
    )


class Gamepad:
    def __init__(self, cfg: GamepadConfig) -> None:
        self.cfg = cfg
        self._joystick: pygame.joystick.JoystickType | None = None
        self._next_scan = 0.0
        self.matched_preferred = True
        self.name = ""

    def open(self) -> bool:
        try:
            _init_pygame()
            index = choose_device(self.cfg)
            if index is None:
                return False
            joystick = pygame.joystick.Joystick(index)
            joystick.init()
            self._joystick = joystick
            self.name = joystick.get_name()
            wanted = self.cfg.preferred_name.strip().lower()
            self.matched_preferred = not wanted or wanted in self.name.lower()
            apply_profile(self.cfg, self.name)
            return True
        except Exception:
            self._joystick = None
            return False

    def poll(self) -> RawInput:
        if self._joystick is None:
            now = time.monotonic()
            if now < self._next_scan or not self.open():
                self._next_scan = now + 1.0
                return RawInput()
        assert self._joystick is not None
        try:
            try:
                pygame.event.pump()
            except pygame.error:
                pass
            axes = tuple(self._joystick.get_axis(i) for i in range(self._joystick.get_numaxes()))
            buttons = tuple(
                bool(self._joystick.get_button(i))
                for i in range(self._joystick.get_numbuttons())
            )
            hat = (
                self._joystick.get_hat(self.cfg.hat)
                if self._joystick.get_numhats() > 0
                else (0, 0)
            )
            return RawInput(axes=axes, buttons=buttons, hat=hat, connected=True, name=self.name)
        except Exception:
            self.close()
            return RawInput()

    def close(self) -> None:
        if self._joystick is not None:
            try:
                self._joystick.quit()
            except Exception:
                pass
        self._joystick = None
        self.name = ""
