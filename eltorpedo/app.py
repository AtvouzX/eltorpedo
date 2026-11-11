"""Textual dashboard for the ROV."""

from __future__ import annotations

import asyncio
import math
import time
from collections import deque
from collections.abc import Callable

from pymavlink import mavutil
from rich.text import Text
from textual import events
from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, OptionList, Static
from textual.widgets.option_list import Option

from .claw import ClawStatus, config_errors, parse_statustext
from .config import Config, Mode, detect_profile, save_keybinds
from .gamepad import Gamepad, RawInput, list_devices, map_axes
from .mav import MavLink, serial_candidates
from .state import VehicleState

KEYBIND_LABELS = {
    "request_quit": "Quit",
    "show_help": "Help",
    "show_keybinds": "Keybind settings",
    "fix_claw": "Fix claw parameters",
    "toggle_arm": "Arm / disarm",
    "claw_close": "Claw close",
    "claw_open": "Claw open",
    "claw_stop": "Claw stop",
    "mode_1": "Mode 1",
    "mode_2": "Mode 2",
    "mode_3": "Mode 3",
}

KEY_NAME_DISPLAY = {
    "question_mark": "?",
    "escape": "Esc",
    "space": "Space",
    "enter": "Enter",
    "backspace": "Backspace",
}


def _display_keys(keys: str) -> str:
    """Render a config key list (``"h,question_mark"``) for humans."""
    shown = [
        KEY_NAME_DISPLAY.get(key.strip(), key.strip().upper())
        for key in keys.split(",")
        if key.strip()
    ]
    return " or ".join(shown) or "unbound"


class ConfirmDisarmScreen(ModalScreen[bool]):
    def __init__(self, title: str, body: str) -> None:
        super().__init__()
        self.title_text = title
        self.body_text = body

    def compose(self) -> ComposeResult:
        yield Vertical(
            Static(Text(self.title_text, style="bold"), id="modal-title"),
            Static(self.body_text, id="modal-body"),
            Horizontal(
                Button("Disarm and exit", variant="error", id="yes"),
                Button("Cancel", variant="primary", id="no"),
                id="modal-buttons",
            ),
            id="modal",
        )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(event.button.id == "yes")

    def action_cancel(self) -> None:
        self.dismiss(False)

    BINDINGS = [
        ("escape", "cancel", "Cancel"),
        ("q", "cancel", "Cancel"),
        ("n", "cancel", "Cancel"),
    ]


class ClawFixScreen(ModalScreen[bool]):
    def __init__(self, errors: list[str], required: dict[str, int]) -> None:
        super().__init__()
        self.errors = errors
        self.required = required

    def compose(self) -> ComposeResult:
        lines = Text()
        lines.append("The claw is not configured for this TUI.\n\n", style="bold")
        for error in self.errors:
            lines.append(f"  {error}\n", style="red")
        lines.append("\nWrite these values?\n\n", style="bold")
        for name, value in self.required.items():
            lines.append(f"  {name} = {value}\n")
        yield Vertical(
            Static(lines, id="modal-body"),
            Horizontal(
                Button("Write params", variant="warning", id="yes"),
                Button("Cancel", variant="primary", id="no"),
                id="modal-buttons",
            ),
            id="modal",
        )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(event.button.id == "yes")

    def action_cancel(self) -> None:
        self.dismiss(False)

    BINDINGS = [
        ("escape", "cancel", "Cancel"),
        ("q", "cancel", "Cancel"),
        ("n", "cancel", "Cancel"),
    ]


class HelpScreen(ModalScreen[None]):
    def __init__(
        self,
        profile: str,
        device_name: str,
        labels: dict[str, str],
        keybinds: dict[str, str],
    ) -> None:
        super().__init__()
        self.profile = profile
        self.device_name = device_name
        self.labels = labels
        self.keybinds = keybinds

    def compose(self) -> ComposeResult:
        lines = Text()
        lines.append(f"GAMEPAD  {self.device_name or 'not connected'}\n", style="bold")
        lines.append(f"profile: {self.profile}\n\n", style="dim")
        for keys, action in (
            ("Left stick", "throttle up/down, yaw left/right"),
            ("Right stick", "forward up/down, lateral left/right"),
            (
                f"{self.labels['claw_close']} / {self.labels['claw_open']} / {self.labels['claw_stop']}",
                "claw close / open / stop",
            ),
            ("D-pad up/down", "cycle flight mode"),
            (self.labels["arm"], "arm"),
            (self.labels["disarm"], "disarm"),
        ):
            lines.append(f"  {keys:<18}", style="cyan")
            lines.append(f"{action}\n")

        lines.append("\nKEYBOARD\n\n", style="bold")
        for action, label in KEYBIND_LABELS.items():
            shown = _display_keys(self.keybinds.get(action, ""))
            lines.append(f"  {shown:<18}", style="cyan")
            lines.append(f"{label}\n")

        lines.append(
            "\nForward motors are one-way: negative forward is ignored.\n",
            style="dim",
        )
        yield Vertical(
            Static(lines, id="modal-body"),
            Horizontal(Button("Close", variant="primary", id="no"), id="modal-buttons"),
            id="modal",
        )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(None)

    def action_cancel(self) -> None:
        self.dismiss(None)

    BINDINGS = [
        ("escape", "cancel", "Close"),
        ("q", "cancel", "Close"),
        ("h", "cancel", "Close"),
        ("question_mark", "cancel", "Close"),
    ]


class KeybindScreen(ModalScreen[None]):
    """View and rebind keyboard keys, persisted to config.toml."""

    RESERVED = {
        "escape",
        "up",
        "down",
        "left",
        "right",
        "enter",
        "tab",
        "shift+tab",
        "pageup",
        "pagedown",
        "home",
        "end",
        "ctrl+c",
    }

    def __init__(
        self,
        keybinds: dict[str, str],
        save: Callable[[dict[str, str]], str | None],
    ) -> None:
        super().__init__()
        self.keybinds = dict(keybinds)
        self.save = save
        self._capturing: str | None = None
        self._list = OptionList(id="keybind-list")
        self._status = Static("", id="keybind-status")

    def compose(self) -> ComposeResult:
        yield Vertical(
            Static(Text("KEYBINDS", style="bold"), id="modal-title"),
            Static(
                "Arrow keys select, Enter rebinds, then press the new key.\n"
                "Escape cancels; Escape again closes.",
                id="keybind-help",
            ),
            self._list,
            self._status,
            id="modal",
        )

    def on_mount(self) -> None:
        self._sync()
        self.set_focus(self._list)

    def _sync(self, highlight: int | None = None) -> None:
        if highlight is None:
            highlight = self._list.highlighted or 0
        self._list.clear_options()
        for action, label in KEYBIND_LABELS.items():
            shown = _display_keys(self.keybinds.get(action, ""))
            self._list.add_option(Option(f"{label:<22}{shown}", id=action))
        self._list.highlighted = min(highlight, len(KEYBIND_LABELS) - 1)

    def _set_status(self, message: str) -> None:
        self._status.update(Text(message))

    def on_option_list_option_selected(
        self, event: OptionList.OptionSelected
    ) -> None:
        event.stop()
        self._capturing = event.option.id
        self._set_status(f"Press the new key for {KEYBIND_LABELS[self._capturing]}")
        self.set_focus(None)

    def on_key(self, event: events.Key) -> None:
        if self._capturing is None:
            if event.key == "escape":
                event.stop()
                self.dismiss(None)
            return
        event.stop()
        event.prevent_default()
        if event.key == "escape":
            self._capturing = None
            self._set_status("Cancelled")
            self.set_focus(self._list)
            return
        self._assign(self._capturing, event.key)

    def _assign(self, action: str, key: str) -> None:
        self._capturing = None
        if key in self.RESERVED:
            self._set_status(f"{key} is reserved; choose another key")
            self.set_focus(self._list)
            return
        for other, keys in self.keybinds.items():
            if other != action and key in [item.strip() for item in keys.split(",")]:
                self._set_status(f"{key} is already bound to {KEYBIND_LABELS[other]}")
                self.set_focus(self._list)
                return
        self.keybinds[action] = key
        error = self.save(self.keybinds)
        if error:
            self._set_status(f"Not saved: {error}")
        else:
            self._set_status(f"{KEYBIND_LABELS[action]} = {_display_keys(key)} (saved)")
        self._sync(list(KEYBIND_LABELS).index(action))
        self.set_focus(self._list)


class ElTorpedoApp(App[None]):
    CSS = """
    Screen { background: $surface; color: $text; }
    #topbar { height: 1; padding: 0 1; background: $panel; }
    #middle { height: 1fr; }
    .panel { border: round $primary; padding: 0 1; }
    #telemetry { width: 1fr; }
    #center { width: 1fr; }
    #claw { width: 1fr; }
    #log { height: 7; border: round $secondary; padding: 0 1; }
    #hints { height: 1; padding: 0 1; color: $text; }
    ConfirmDisarmScreen, ClawFixScreen, HelpScreen, KeybindScreen { align: center middle; }
    #modal { width: 76; height: auto; border: round $warning; background: $surface; padding: 1 2; }
    #modal-title { height: auto; margin-bottom: 1; }
    #modal-body { height: auto; }
    #modal-buttons { height: 3; align: center middle; }
    #modal-buttons Button { margin: 0 1; }
    #keybind-help { height: auto; color: $text-muted; }
    #keybind-list { height: 13; border: none; background: $surface; padding: 0; }
    #keybind-status { height: 1; color: $text; }
    """

    def __init__(self, config: Config, sitl: bool = False) -> None:
        super().__init__()
        self.cfg = config
        self.sitl = sitl
        self.state = VehicleState()
        self.state.messages = deque(maxlen=config.ui.messages)
        self.mav = MavLink(config.link)
        self.gamepad = Gamepad(config.gamepad)
        self._alive = True
        self._tasks: list[asyncio.Task] = []
        self._raw = RawInput()
        self._prev_buttons: tuple[bool, ...] = ()
        self._prev_hat_y = 0
        self._gamepad_lost_since: float | None = None
        self._gamepad_disarmed = False
        self._pending_claw: dict[int, float] = {}

    def on_key(self, event: events.Key) -> None:
        if isinstance(self.screen, KeybindScreen):
            return
        action = self.cfg.ui.action_for(event.key)
        if action is None:
            return
        event.stop()
        handler = getattr(self, f"action_{action}", None)
        if handler is not None:
            handler()

    def compose(self) -> ComposeResult:
        yield Static(id="topbar")
        with Horizontal(id="middle"):
            with Vertical(id="telemetry", classes="panel"):
                yield Static(id="telemetry-body")
            with Vertical(id="center", classes="panel"):
                yield Static(id="center-body")
            with Vertical(id="claw", classes="panel"):
                yield Static(id="claw-body")
        yield Static(id="log")
        yield Static(id="hints")

    def on_mount(self) -> None:
        try:
            self.mav.open()
        except Exception as exc:
            self.state.add_message(f"Link open failed: {exc}", 3)

        playstation = [
            device.name
            for device in list_devices()
            if detect_profile(device.name) == "playstation"
        ]
        if playstation:
            self.state.add_message(
                "PS touchpad can move the desktop cursor: " + ", ".join(playstation), 4
            )

        self._tasks = [
            asyncio.create_task(self._reader_loop()),
            asyncio.create_task(self._gamepad_loop()),
            asyncio.create_task(self._control_loop()),
            asyncio.create_task(self._heartbeat_loop()),
            asyncio.create_task(self._param_loop()),
        ]
        self.set_interval(1.0 / max(1.0, self.cfg.ui.refresh_hz), self._refresh_view)
        self._refresh_view()

    def on_unmount(self) -> None:
        self._alive = False
        for task in self._tasks:
            task.cancel()
        self.mav.close()
        self.gamepad.close()

    # ---------------------------------------------------------------- loops

    async def _reader_loop(self) -> None:
        while self._alive:
            if self.mav.conn is None:
                try:
                    self.mav.open()
                    self.state.add_message(f"MAVLink open: {self.mav.endpoint}", 6)
                except Exception as exc:
                    self.state.add_message(f"MAVLink open failed: {exc}", 3)
                    await asyncio.sleep(2.0)
                    continue
            elif self._serial_appeared():
                self.mav.close()
                continue
            got = False
            for _ in range(64):
                msg = self.mav.recv()
                if msg is None:
                    break
                got = True
                self._handle_message(msg)
            await asyncio.sleep(0.005 if got else 0.01)

    def _serial_appeared(self) -> bool:
        """True when a serial autopilot port exists but the link is still UDP."""
        if not self.cfg.link.autodetect or not self.mav.endpoint.startswith("udp"):
            return False
        return bool(serial_candidates())

    async def _gamepad_loop(self) -> None:
        announced = ""
        while self._alive:
            raw = self.gamepad.poll()
            self.state.gamepad_ok = raw.connected
            self.state.gamepad_name = raw.name
            if raw.connected:
                self.state.gamepad_seen = True
                if raw.name != announced:
                    announced = raw.name
                    if self.cfg.gamepad.resolved_profile == "playstation":
                        self.state.add_message(
                            "PlayStation pad: touchpad can move the desktop cursor", 4
                        )
                    elif not self.gamepad.matched_preferred:
                        self.state.add_message(
                            f"Preferred pad not found, using {raw.name}", 4
                        )
                if self._gamepad_lost_since is not None:
                    self.state.add_message("Gamepad reconnected", 6)
                    self._gamepad_lost_since = None
                    self._gamepad_disarmed = False
                self._handle_gamepad_edges(raw)
                self._raw = raw
            else:
                if self.state.gamepad_seen and self._gamepad_lost_since is None:
                    self._gamepad_lost_since = time.monotonic()
                    self.state.add_message("Gamepad lost", 3)
                self._raw = RawInput()
            await asyncio.sleep(1.0 / 60.0)

    async def _control_loop(self) -> None:
        period = 1.0 / max(1.0, self.cfg.link.control_hz)
        while self._alive:
            now = time.monotonic()
            self._check_link(now)

            if self._gamepad_lost_since is not None and not self._gamepad_disarmed:
                if self.state.armed and now - self._gamepad_lost_since >= self.cfg.link.gamepad_disarm_s:
                    self._disarm("gamepad lost")
                    self._gamepad_disarmed = True

            axes = (0, 0, 0, 0)
            if self.state.link_ok and self.state.gamepad_ok:
                axes = map_axes(self._raw, self.cfg.gamepad)
            self.state.axes = axes
            buttons = self._claw_mask(now)
            if self.state.link_ok:
                self.mav.send_manual_control(*axes, buttons)
            await asyncio.sleep(period)

    async def _heartbeat_loop(self) -> None:
        while self._alive:
            self.mav.send_heartbeat()
            await asyncio.sleep(1.0 / max(0.2, self.cfg.link.heartbeat_hz))

    async def _param_loop(self) -> None:
        while self._alive:
            if self.state.link_ok:
                self.mav.request_param("GRIP_DC_CURR")
                for name in self.cfg.claw.required:
                    if name not in self.state.params:
                        self.mav.request_param(name)
            await asyncio.sleep(1.0)

    # ------------------------------------------------------------- messages

    def _handle_message(self, msg) -> None:
        mtype = msg.get_type()
        if mtype == "BAD_DATA":
            return

        if mtype == "HEARTBEAT":
            if msg.type == mavutil.mavlink.MAV_TYPE_GCS:
                return
            if msg.autopilot == mavutil.mavlink.MAV_AUTOPILOT_INVALID:
                return
            self.mav.set_target(msg.get_srcSystem(), msg.get_srcComponent())
            was_up = self.state.link_ok
            self.state.link_ok = True
            self.state.link_lost = False
            self.state.last_heartbeat = time.monotonic()
            self.state.system_id = msg.get_srcSystem()
            self.state.component_id = msg.get_srcComponent()
            self.state.armed = bool(
                msg.base_mode & mavutil.mavlink.MAV_MODE_FLAG_SAFETY_ARMED
            )
            self.state.mode_id = msg.custom_mode
            if not was_up:
                self._on_link_up()

        elif mtype == "ATTITUDE":
            self.state.roll_deg = math.degrees(msg.roll)
            self.state.pitch_deg = math.degrees(msg.pitch)
            self.state.yaw_deg = math.degrees(msg.yaw) % 360.0

        elif mtype == "GLOBAL_POSITION_INT":
            self.state.depth_m = -msg.relative_alt / 1000.0

        elif mtype == "BATTERY_STATUS":
            voltage = msg.voltages[0] if msg.voltages else 65535
            if voltage not in (0, 65535):
                self.state.battery_voltage = voltage / 1000.0
            if msg.current_battery >= 0:
                self.state.battery_current = msg.current_battery / 100.0
            if msg.battery_remaining >= 0:
                self.state.battery_remaining = msg.battery_remaining

        elif mtype == "SYS_STATUS":
            if self.state.battery_voltage is None and msg.voltage_battery not in (0, 65535):
                self.state.battery_voltage = msg.voltage_battery / 1000.0
            if self.state.battery_current is None and msg.current_battery >= 0:
                self.state.battery_current = msg.current_battery / 100.0
            if self.state.battery_remaining is None and msg.battery_remaining >= 0:
                self.state.battery_remaining = msg.battery_remaining

        elif mtype == "STATUSTEXT":
            text = msg.text
            if isinstance(text, bytes):
                text = text.decode(errors="replace")
            text = text.rstrip("\x00")
            self.state.add_message(text, msg.severity)
            parse_statustext(text, self.state.claw)

        elif mtype == "PARAM_VALUE":
            name = msg.param_id
            if isinstance(name, bytes):
                name = name.decode(errors="replace")
            name = name.rstrip("\x00")
            self.state.params[name] = msg.param_value
            if name == "GRIP_DC_CURR":
                self.state.claw.current_ma = int(msg.param_value)
            self.state.claw_errors = config_errors(
                self.state.params, self.cfg.claw.required
            )

        elif mtype == "COMMAND_ACK":
            if msg.command == mavutil.mavlink.MAV_CMD_COMPONENT_ARM_DISARM:
                if msg.result == mavutil.mavlink.MAV_RESULT_ACCEPTED:
                    self.state.add_message("Arm command accepted", 6)
                else:
                    self.state.add_message(f"Arm command rejected ({msg.result})", 3)

    def _on_link_up(self) -> None:
        self.state.add_message("Link up", 6)
        self.mav.request_streams()
        for name in self.cfg.claw.required:
            self.mav.request_param(name)

    def _check_link(self, now: float) -> None:
        if (
            self.state.link_ok
            and now - self.state.last_heartbeat > self.cfg.link.link_timeout_s
        ):
            self.state.link_ok = False
            self.state.link_lost = True
            self.state.axes = (0, 0, 0, 0)
            self.state.params.clear()
            self.state.claw_errors = []
            self.state.claw = ClawStatus(detail="link lost")
            self.state.add_message("LINK LOST", 2)

    # ------------------------------------------------------------- commands

    def _arm(self, reason: str) -> None:
        if self.state.armed:
            return
        if not self.state.link_ok:
            self.state.add_message("Cannot arm: no link", 3)
            return
        errors = config_errors(self.state.params, self.cfg.claw.required)
        if not self.sitl and self.cfg.claw.enabled and errors:
            self.state.add_message("Cannot arm: claw not configured (F)", 3)
            return
        self.mav.arm(True)
        self.state.add_message(f"Arm requested ({reason})", 6)

    def _disarm(self, reason: str) -> None:
        if not self.state.link_ok:
            return
        self.mav.arm(False)
        self.state.add_message(f"Disarm requested ({reason})", 4)

    def _set_mode(self, mode: Mode) -> None:
        if not self.state.link_ok:
            self.state.add_message("Cannot change mode: no link", 3)
            return
        self.mav.set_mode(mode.id)
        self.state.add_message(f"Mode request: {mode.name}", 6)

    def _cycle_mode(self, direction: int) -> None:
        modes = self.cfg.vehicle.modes
        ids = [mode.id for mode in modes]
        try:
            index = ids.index(self.state.mode_id)
        except ValueError:
            index = -1 if direction > 0 else 0
        index = (index + direction) % len(modes)
        self._set_mode(modes[index])

    def _set_mode_index(self, index: int) -> None:
        if 0 <= index < len(self.cfg.vehicle.modes):
            self._set_mode(self.cfg.vehicle.modes[index])

    def _press_claw(self, action: str) -> None:
        if not self.state.link_ok:
            self.state.add_message("Claw: no link", 3)
            return
        bit = {
            "close": self.cfg.claw.close_bit,
            "open": self.cfg.claw.open_bit,
            "stop": self.cfg.claw.stop_bit,
        }[action]
        self._pending_claw[bit] = time.monotonic() + self.cfg.claw.press_ms / 1000.0

    def _claw_mask(self, now: float) -> int:
        mask = 0
        for bit, expiry in list(self._pending_claw.items()):
            if expiry <= now:
                del self._pending_claw[bit]
            else:
                mask |= 1 << bit
        return mask

    def _handle_gamepad_edges(self, raw: RawInput) -> None:
        buttons = raw.buttons
        previous = self._prev_buttons
        for index, pressed in enumerate(buttons):
            was = previous[index] if index < len(previous) else False
            if not pressed or was:
                continue
            if index == self.cfg.gamepad.buttons["claw_close"]:
                self._press_claw("close")
            elif index == self.cfg.gamepad.buttons["claw_open"]:
                self._press_claw("open")
            elif index == self.cfg.gamepad.buttons["claw_stop"]:
                self._press_claw("stop")

        arm_button = self.cfg.gamepad.buttons["arm"]
        disarm_button = self.cfg.gamepad.buttons["disarm"]
        if (
            arm_button < len(buttons)
            and buttons[arm_button]
            and not (arm_button < len(previous) and previous[arm_button])
        ):
            self._arm("gamepad Start")
        if (
            disarm_button < len(buttons)
            and buttons[disarm_button]
            and not (disarm_button < len(previous) and previous[disarm_button])
        ):
            self._disarm("gamepad Back")

        hat_y = raw.hat[1] if len(raw.hat) > 1 else 0
        if hat_y != self._prev_hat_y:
            if hat_y > 0:
                self._cycle_mode(1)
            elif hat_y < 0:
                self._cycle_mode(-1)
        self._prev_hat_y = hat_y
        self._prev_buttons = buttons

    # -------------------------------------------------------------- actions

    def action_toggle_arm(self) -> None:
        if self.state.armed:
            self._disarm("keyboard")
        else:
            self._arm("keyboard")

    def action_claw_close(self) -> None:
        self._press_claw("close")

    def action_claw_open(self) -> None:
        self._press_claw("open")

    def action_claw_stop(self) -> None:
        self._press_claw("stop")

    def action_mode_1(self) -> None:
        self._set_mode_index(0)

    def action_mode_2(self) -> None:
        self._set_mode_index(1)

    def action_mode_3(self) -> None:
        self._set_mode_index(2)

    def action_request_quit(self) -> None:
        if self.state.armed:
            self.push_screen(
                ConfirmDisarmScreen(
                    "Vehicle is armed",
                    "Disarm the vehicle and exit?\n\n"
                    "The TUI will send neutral axes and a disarm command.",
                ),
                self._on_quit_result,
            )
        else:
            asyncio.create_task(self._shutdown_and_exit(disarm=False))

    def _on_quit_result(self, confirmed: bool | None) -> None:
        if confirmed:
            asyncio.create_task(self._shutdown_and_exit(disarm=True))

    async def _shutdown_and_exit(self, disarm: bool) -> None:
        self._alive = False
        if self.mav.conn is not None:
            for _ in range(3):
                if self.state.link_ok:
                    self.mav.send_manual_control(0, 0, 0, 0, 0)
                await asyncio.sleep(0.05)
            if disarm and self.state.armed:
                self.mav.arm(False)
                await asyncio.sleep(0.25)
        self.exit()

    def action_show_help(self) -> None:
        self.push_screen(
            HelpScreen(
                self.cfg.gamepad.resolved_profile,
                self.state.gamepad_name,
                self.cfg.gamepad.labels,
                self.cfg.ui.keybinds,
            )
        )

    def action_show_keybinds(self) -> None:
        self.push_screen(
            KeybindScreen(dict(self.cfg.ui.keybinds), self._save_keybinds)
        )

    def _save_keybinds(self, keybinds: dict[str, str]) -> str | None:
        self.cfg.ui.keybinds = dict(keybinds)
        try:
            save_keybinds(self.cfg.path, keybinds)
        except OSError as exc:
            return str(exc)
        return None

    def action_fix_claw(self) -> None:
        if not self.cfg.claw.enabled:
            self.state.add_message("Claw disabled in config", 4)
            return
        errors = config_errors(self.state.params, self.cfg.claw.required)
        if not errors:
            self.state.add_message("Claw configuration OK", 6)
            return
        if any("not read" in error for error in errors):
            self.state.add_message("Claw params still loading", 4)
            return
        self.push_screen(
            ClawFixScreen(errors, self.cfg.claw.required),
            self._on_fix_result,
        )

    def _on_fix_result(self, confirmed: bool | None) -> None:
        if confirmed:
            asyncio.create_task(self._write_claw_params())

    async def _write_claw_params(self) -> None:
        for name, value in self.cfg.claw.required.items():
            self.mav.set_param(name, value)
            await asyncio.sleep(0.08)
        self.state.add_message("Claw params written; reboot if GRIP_TYPE changed", 4)
        await asyncio.sleep(0.5)
        for name in self.cfg.claw.required:
            self.mav.request_param(name)

    # --------------------------------------------------------------- render

    def _mode_name(self, mode_id: int) -> str:
        for mode in self.cfg.vehicle.modes:
            if mode.id == mode_id:
                return mode.name
        return f"UNKNOWN ({mode_id})"

    def _refresh_view(self) -> None:
        if not self._alive:
            return
        self.query_one("#topbar", Static).update(self._render_top())
        self.query_one("#telemetry-body", Static).update(self._render_telemetry())
        self.query_one("#center-body", Static).update(self._render_center())
        self.query_one("#claw-body", Static).update(self._render_claw())
        self.query_one("#log", Static).update(self._render_log())
        self.query_one("#hints", Static).update(self._render_hints())

    def _render_top(self) -> Text:
        now = time.monotonic()
        age_ms = (
            (now - self.state.last_heartbeat) * 1000.0
            if self.state.last_heartbeat
            else 999999.0
        )
        text = Text()
        if self.state.link_ok:
            text.append(" LINK OK ", style="bold black on green")
        else:
            text.append(" LINK LOST ", style="bold white on red")
        text.append(f" {age_ms:.0f} ms  ")
        text.append("MODE ", style="dim")
        text.append(f"{self._mode_name(self.state.mode_id)}  ")
        if self.state.armed:
            text.append(" ARMED ", style="bold white on red")
        else:
            text.append(" DISARMED ", style="bold black on green")
        text.append("  BAT ", style="dim")
        if self.state.battery_voltage is not None:
            text.append(f"{self.state.battery_voltage:.1f} V")
            if self.state.battery_current is not None:
                text.append(f"  {self.state.battery_current:.1f} A")
            if self.state.battery_remaining is not None and self.state.battery_remaining >= 0:
                text.append(f"  {self.state.battery_remaining}%")
        else:
            text.append("--")
        return text

    def _render_telemetry(self) -> Text:
        text = Text()
        depth = f"{self.state.depth_m:+.2f} m" if self.state.depth_m is not None else "--"
        text.append("DEPTH     ", style="dim")
        text.append(f"{depth}\n")
        text.append("HEADING   ", style="dim")
        text.append(f"{self.state.yaw_deg:6.1f} deg\n")
        text.append("ATTITUDE  ", style="dim")
        text.append(
            f"roll {self.state.roll_deg:+6.1f}  "
            f"pitch {self.state.pitch_deg:+6.1f}\n"
        )
        text.append("\nCOMMAND\n", style="dim")
        x, y, z, r = self.state.axes
        for label, value in (
            ("FORWARD ", x),
            ("LATERAL ", y),
            ("THROTTLE", z),
            ("YAW     ", r),
        ):
            text.append(f"{label} ", style="dim")
            text.append(f"{_bar(value)} {value:+5d}\n")
        return text

    def _render_center(self) -> Text:
        x, y, z, r = self.state.axes
        labels = self.cfg.gamepad.labels
        text = Text()
        text.append("RIGHT STICK  ", style="dim")
        text.append(f"forward {x:+5d}   lateral {y:+5d}\n")
        text.append("LEFT STICK   ", style="dim")
        text.append(f"throttle {z:+5d}  yaw     {r:+5d}\n")
        text.append("\n")
        text.append("GAMEPAD      ", style="dim")
        if self.state.gamepad_ok:
            text.append(f"{self.state.gamepad_name}\n")
        else:
            text.append("not connected\n", style="red")
        text.append("PROFILE      ", style="dim")
        text.append(f"{self.cfg.gamepad.resolved_profile}\n")
        text.append("DEADMAN      ", style="dim")
        text.append("disabled (QGC-style)\n")
        text.append("MODE         ", style="dim")
        text.append(f"{self._mode_name(self.state.mode_id)}\n")
        text.append("\n")
        text.append("CLAW         ", style="dim")
        text.append(
            f"{labels['claw_close']} close  "
            f"{labels['claw_open']} open  "
            f"{labels['claw_stop']} stop\n"
        )
        text.append("ARM          ", style="dim")
        text.append(f"{labels['arm']} arm  {labels['disarm']} disarm\n")
        text.append("HELP         ", style="dim")
        text.append("H for all controls\n")
        if self.cfg.vehicle.unidirectional_forward and x < -50:
            text.append("\nREVERSE UNAVAILABLE\n", style="bold yellow")
            text.append("forward motors idle below zero", style="yellow")
        return text

    def _render_claw(self) -> Text:
        status = self.state.claw
        text = Text()
        text.append("STATE    ", style="dim")
        text.append(f"{status.state}\n", style=_claw_style(status))
        text.append("CURRENT  ", style="dim")
        text.append(
            f"{status.current_ma} mA\n" if status.current_ma is not None else "--\n"
        )
        if status.detail:
            text.append("DETAIL   ", style="dim")
            text.append(f"{status.detail}\n")
        text.append("\n")
        if not self.cfg.claw.enabled:
            text.append("CONFIG   disabled in config\n", style="dim")
        elif not self.state.params:
            text.append("CONFIG   reading params...\n", style="dim")
        elif self.state.claw_errors:
            text.append("CONFIG   MISMATCH (F to fix)\n", style="bold red")
            for error in self.state.claw_errors:
                text.append(f"  {error}\n", style="red")
        else:
            text.append("CONFIG   OK\n", style="green")
        return text

    def _render_log(self) -> Text:
        text = Text()
        for message in list(self.state.messages)[-self.cfg.ui.messages :]:
            text.append(time.strftime("%H:%M:%S ", time.localtime(message.at)), style="dim")
            text.append(f"{message.text}\n", style=_severity_style(message.severity))
        return text

    def _render_hints(self) -> Text:
        keys = self.cfg.ui.keybinds
        modes = "/".join(
            keys.get(f"mode_{index + 1}", "")
            for index in range(len(self.cfg.vehicle.modes))
            if f"mode_{index + 1}" in keys
        )
        text = Text()
        text.append(
            f"{_display_keys(keys['request_quit'])} quit  "
            f"{_display_keys(keys['show_help'])} help  "
            f"{_display_keys(keys['show_keybinds'])} keybinds  "
            f"{_display_keys(keys['toggle_arm'])} arm  "
            f"{_display_keys(keys['claw_close'])}/"
            f"{_display_keys(keys['claw_open'])}/"
            f"{_display_keys(keys['claw_stop'])} claw  "
            f"{modes} mode",
            style="dim",
        )
        if self.sitl:
            text.append("   [SITL]", style="yellow")
        return text


def _bar(value: int, width: int = 10) -> str:
    filled = int(round(abs(value) / 1000.0 * width))
    return "█" * filled + "░" * (width - filled)


def _claw_style(status: ClawStatus) -> str:
    if status.fault:
        return "bold red"
    if status.unavailable:
        return "yellow"
    if status.state in ("HOLDING", "CLOSED", "OPEN"):
        return "green"
    if status.state in ("CLOSING", "OPENING"):
        return "cyan"
    return "dim"


def _severity_style(severity: int) -> str:
    if severity <= 3:
        return "red"
    if severity == 4:
        return "yellow"
    if severity == 5:
        return "cyan"
    if severity >= 7:
        return "dim"
    return ""
