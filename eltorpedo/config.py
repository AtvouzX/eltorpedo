"""Configuration loading and defaults."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path

DEFAULT_CONFIG = """\
# eltorpedo configuration.
# Regenerated with comments if deleted. Override the path with --config.

[link]
# udpin listens for mavlink-router or SITL. Use udpout:192.168.1.50:14550
# when the TUI should push to a remote router. A serial: endpoint is used as
# given; mavlink-router is not required.
endpoint = "udpin:0.0.0.0:14550"
# While the endpoint above is unchanged, a serial autopilot plugged in during
# the run is used instead: ttyUSB*, ttyACM* at autodetect_baud.
autodetect = true
autodetect_baud = 115200
source_system = 255
source_component = 191
control_hz = 20
heartbeat_hz = 1
link_timeout_s = 3.0
gamepad_timeout_s = 0.25
gamepad_disarm_s = 1.0

[gamepad]
# Pick a controller by name (case-insensitive substring). index is the fallback.
preferred_name = "Xbox"
# auto | xbox | playstation
profile = "auto"
index = 0
deadzone = 0.08
hat = 0

# Optional overrides. Anything omitted comes from the detected profile.
# [gamepad.axes.throttle]
# index = 1
# invert = true
#
# [gamepad.buttons]
# claw_close = 0

[claw]
enabled = true
close_bit = 0
open_bit = 1
stop_bit = 2
press_ms = 150

[claw.required]
GRIP_ENABLE = 1
GRIP_TYPE = 3
BTN0_FUNCTION = 140
BTN1_FUNCTION = 139
BTN2_FUNCTION = 141

[vehicle]
unidirectional_forward = true

[[vehicle.modes]]
name = "MANUAL"
id = 19

[[vehicle.modes]]
name = "STABILIZE"
id = 0

[[vehicle.modes]]
name = "DEPTH HOLD"
id = 2

[ui]
refresh_hz = 10
messages = 5

# Keyboard bindings. Changed in the in-app settings screen (K by default)
# and written back here. Separate alternative keys with a comma.
# [ui.keybinds]
# request_quit = "q"
# show_help = "h,question_mark"
"""

DEFAULT_KEYBINDS = {
    "request_quit": "q",
    "show_help": "h,question_mark",
    "show_keybinds": "k",
    "fix_claw": "f",
    "toggle_arm": "z",
    "claw_close": "c",
    "claw_open": "o",
    "claw_stop": "x",
    "mode_1": "1",
    "mode_2": "2",
    "mode_3": "3",
}


@dataclass(frozen=True)
class AxisSpec:
    index: int
    invert: bool = False


# Both Xbox and PlayStation pads report the same SDL axis order.
XBOX_AXES = {
    "throttle": AxisSpec(1, True),
    "yaw": AxisSpec(0, False),
    "forward": AxisSpec(3, True),
    "lateral": AxisSpec(2, False),
    "camera": AxisSpec(5, True),
}
PLAYSTATION_AXES = dict(XBOX_AXES)

XBOX_BUTTONS = {
    "claw_close": 0,  # A
    "claw_open": 1,  # B
    "claw_stop": 2,  # X
    "arm": 7,  # Start (Menu)
    "disarm": 6,  # Back (View)
}
PLAYSTATION_BUTTONS = {
    "claw_close": 0,  # Cross
    "claw_open": 1,  # Circle
    "claw_stop": 2,  # Square
    "arm": 9,  # Options (Start)
    "disarm": 8,  # Share (Back)
}

XBOX_LABELS = {
    "claw_close": "A",
    "claw_open": "B",
    "claw_stop": "X",
    "arm": "Start",
    "disarm": "Back",
}
PLAYSTATION_LABELS = {
    "claw_close": "Cross",
    "claw_open": "Circle",
    "claw_stop": "Square",
    "arm": "Options",
    "disarm": "Share",
}

PROFILES = {
    "xbox": {"axes": XBOX_AXES, "buttons": XBOX_BUTTONS, "labels": XBOX_LABELS},
    "playstation": {
        "axes": PLAYSTATION_AXES,
        "buttons": PLAYSTATION_BUTTONS,
        "labels": PLAYSTATION_LABELS,
    },
}

PLAYSTATION_HINTS = ("playstation", "ps4", "ps5", "dualshock", "dualsense", "wireless controller")


def detect_profile(name: str) -> str:
    lowered = name.lower()
    return "playstation" if any(hint in lowered for hint in PLAYSTATION_HINTS) else "xbox"


def apply_profile(cfg: "GamepadConfig", name: str) -> str:
    """Fill axes, buttons and labels from the detected (or configured) profile."""
    if cfg.profile in PROFILES:
        chosen = cfg.profile
    else:
        chosen = detect_profile(name)
    table = PROFILES[chosen]
    for key, spec in table["axes"].items():
        if key not in cfg.custom_axes:
            cfg.axes[key] = spec
    for key, value in table["buttons"].items():
        if key not in cfg.custom_buttons:
            cfg.buttons[key] = value
    cfg.labels = dict(table["labels"])
    cfg.resolved_profile = chosen
    return chosen


@dataclass
class LinkConfig:
    endpoint: str = "udpin:0.0.0.0:14550"
    autodetect: bool = True
    autodetect_baud: int = 115200
    source_system: int = 255
    source_component: int = 191
    control_hz: float = 20.0
    heartbeat_hz: float = 1.0
    link_timeout_s: float = 3.0
    gamepad_timeout_s: float = 0.25
    gamepad_disarm_s: float = 1.0


@dataclass
class GamepadConfig:
    preferred_name: str = "Xbox"
    profile: str = "auto"
    index: int = 0
    deadzone: float = 0.08
    hat: int = 0
    axes: dict[str, AxisSpec] = field(default_factory=lambda: dict(XBOX_AXES))
    buttons: dict[str, int] = field(default_factory=lambda: dict(XBOX_BUTTONS))
    labels: dict[str, str] = field(default_factory=lambda: dict(XBOX_LABELS))
    custom_axes: set[str] = field(default_factory=set)
    custom_buttons: set[str] = field(default_factory=set)
    resolved_profile: str = "xbox"


@dataclass
class ClawConfig:
    enabled: bool = True
    close_bit: int = 0
    open_bit: int = 1
    stop_bit: int = 2
    press_ms: int = 150
    required: dict[str, int] = field(
        default_factory=lambda: {
            "GRIP_ENABLE": 1,
            "GRIP_TYPE": 3,
            "BTN0_FUNCTION": 140,
            "BTN1_FUNCTION": 139,
            "BTN2_FUNCTION": 141,
        }
    )


@dataclass(frozen=True)
class Mode:
    name: str
    id: int


@dataclass
class VehicleConfig:
    unidirectional_forward: bool = True
    modes: list[Mode] = field(
        default_factory=lambda: [
            Mode("MANUAL", 19),
            Mode("STABILIZE", 0),
            Mode("DEPTH HOLD", 2),
        ]
    )


@dataclass
class UiConfig:
    refresh_hz: float = 10.0
    messages: int = 5
    keybinds: dict[str, str] = field(
        default_factory=lambda: dict(DEFAULT_KEYBINDS)
    )

    def action_for(self, key: str) -> str | None:
        """Return the action bound to a Textual key name, if any."""
        for action, keys in self.keybinds.items():
            if key in (item.strip() for item in keys.split(",")):
                return action
        return None


@dataclass
class Config:
    link: LinkConfig = field(default_factory=LinkConfig)
    gamepad: GamepadConfig = field(default_factory=GamepadConfig)
    claw: ClawConfig = field(default_factory=ClawConfig)
    vehicle: VehicleConfig = field(default_factory=VehicleConfig)
    ui: UiConfig = field(default_factory=UiConfig)
    path: Path = field(default=Path("config.toml"), repr=False)


def _axis(table: dict, key: str, default_index: int, default_invert: bool) -> AxisSpec:
    raw = table.get(key)
    if raw is None:
        return AxisSpec(default_index, default_invert)
    if isinstance(raw, int):
        return AxisSpec(raw, default_invert)
    return AxisSpec(int(raw.get("index", default_index)), bool(raw.get("invert", default_invert)))


def _section(data: dict, key: str) -> dict:
    value = data.get(key)
    return value if isinstance(value, dict) else {}


def load_config(path: Path | None = None, endpoint: str | None = None) -> Config:
    """Load config, writing a commented default when the file is missing."""
    path = path or Path("config.toml")
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(DEFAULT_CONFIG, encoding="utf-8")

    with path.open("rb") as handle:
        data = tomllib.load(handle)

    link_raw = _section(data, "link")
    link = LinkConfig(
        endpoint=str(link_raw.get("endpoint", LinkConfig.endpoint)),
        autodetect=bool(link_raw.get("autodetect", True)),
        autodetect_baud=int(link_raw.get("autodetect_baud", 115200)),
        source_system=int(link_raw.get("source_system", 255)),
        source_component=int(link_raw.get("source_component", 191)),
        control_hz=float(link_raw.get("control_hz", 20)),
        heartbeat_hz=float(link_raw.get("heartbeat_hz", 1)),
        link_timeout_s=float(link_raw.get("link_timeout_s", 3.0)),
        gamepad_timeout_s=float(link_raw.get("gamepad_timeout_s", 0.25)),
        gamepad_disarm_s=float(link_raw.get("gamepad_disarm_s", 1.0)),
    )
    if endpoint:
        link.endpoint = endpoint

    gamepad_raw = _section(data, "gamepad")
    axes_raw = _section(gamepad_raw, "axes")
    buttons_raw = _section(gamepad_raw, "buttons")
    profile = str(gamepad_raw.get("profile", "auto")).strip().lower()
    axes = dict(XBOX_AXES)
    for key, spec in XBOX_AXES.items():
        axes[key] = _axis(axes_raw, key, spec.index, spec.invert)
    buttons = dict(XBOX_BUTTONS)
    for key in XBOX_BUTTONS:
        if key in buttons_raw:
            buttons[key] = int(buttons_raw[key])
    gamepad = GamepadConfig(
        preferred_name=str(gamepad_raw.get("preferred_name", "Xbox")),
        profile=profile,
        index=int(gamepad_raw.get("index", 0)),
        deadzone=float(gamepad_raw.get("deadzone", 0.08)),
        hat=int(gamepad_raw.get("hat", 0)),
        axes=axes,
        buttons=buttons,
        custom_axes={key for key in axes_raw if key in XBOX_AXES},
        custom_buttons={key for key in buttons_raw if key in XBOX_BUTTONS},
    )

    claw_raw = _section(data, "claw")
    required_raw = _section(claw_raw, "required")
    claw = ClawConfig(
        enabled=bool(claw_raw.get("enabled", True)),
        close_bit=int(claw_raw.get("close_bit", 0)),
        open_bit=int(claw_raw.get("open_bit", 1)),
        stop_bit=int(claw_raw.get("stop_bit", 2)),
        press_ms=int(claw_raw.get("press_ms", 150)),
        required={str(k): int(v) for k, v in required_raw.items()}
        or ClawConfig().required,
    )

    vehicle_raw = _section(data, "vehicle")
    modes_raw = vehicle_raw.get("modes")
    modes = [
        Mode(str(item.get("name", f"MODE {item.get('id')}")), int(item["id"]))
        for item in modes_raw
        if isinstance(item, dict) and "id" in item
    ] if isinstance(modes_raw, list) else VehicleConfig().modes
    vehicle = VehicleConfig(
        unidirectional_forward=bool(vehicle_raw.get("unidirectional_forward", True)),
        modes=modes or VehicleConfig().modes,
    )

    ui_raw = _section(data, "ui")
    keybinds_raw = _section(ui_raw, "keybinds")
    keybinds = dict(DEFAULT_KEYBINDS)
    for action, value in keybinds_raw.items():
        if action in keybinds and isinstance(value, str) and value.strip():
            keybinds[action] = value.strip()
    ui = UiConfig(
        refresh_hz=float(ui_raw.get("refresh_hz", 10)),
        messages=int(ui_raw.get("messages", 5)),
        keybinds=keybinds,
    )

    return Config(
        link=link,
        gamepad=gamepad,
        claw=claw,
        vehicle=vehicle,
        ui=ui,
        path=path,
    )


def save_keybinds(path: Path, keybinds: dict[str, str]) -> None:
    """Write the keybind table into config.toml, leaving other sections intact."""
    text = path.read_text(encoding="utf-8") if path.exists() else DEFAULT_CONFIG
    block = "[ui.keybinds]\n" + "".join(
        f'{action} = "{value}"\n' for action, value in keybinds.items()
    )
    lines = text.splitlines(keepends=True)
    start = next(
        (index for index, line in enumerate(lines) if line.strip() == "[ui.keybinds]"),
        None,
    )
    if start is None:
        text = text.rstrip("\n") + "\n\n" + block
    else:
        end = len(lines)
        for index in range(start + 1, len(lines)):
            stripped = lines[index].strip()
            if stripped.startswith("[") and stripped.endswith("]"):
                end = index
                break
        text = "".join(lines[:start] + [block] + lines[end:])
    path.write_text(text, encoding="utf-8")
