from pathlib import Path

from eltorpedo.app import ElTorpedoApp
from eltorpedo.config import Config, load_config
from eltorpedo.gamepad import RawInput
from eltorpedo.mav import _clamp


def test_load_config_writes_default(tmp_path: Path):
    path = tmp_path / "config.toml"
    cfg = load_config(path)
    assert path.exists()
    assert cfg.link.endpoint == "udpin:0.0.0.0:14550"
    assert cfg.gamepad.buttons["claw_close"] == 0
    assert [mode.id for mode in cfg.vehicle.modes] == [19, 0, 2]
    assert cfg.claw.required["GRIP_TYPE"] == 3


def test_endpoint_override(tmp_path: Path):
    path = tmp_path / "config.toml"
    path.write_text(
        '[link]\nendpoint = "udpin:0.0.0.0:14550"\n',
        encoding="utf-8",
    )
    cfg = load_config(path, endpoint="udpout:192.168.1.50:14550")
    assert cfg.link.endpoint == "udpout:192.168.1.50:14550"


def test_clamp_axes():
    assert _clamp(-2000) == -1000
    assert _clamp(0) == 0
    assert _clamp(2000) == 1000


def test_arm_blocked_until_claw_is_configured():
    app = ElTorpedoApp(Config(), sitl=False)
    app.state.link_ok = True
    calls = []
    app.mav.arm = lambda value: calls.append(value)

    app._arm("test")

    assert calls == []
    assert "claw not configured" in app.state.messages[-1].text


def test_sitl_allows_arm_without_claw_params():
    app = ElTorpedoApp(Config(), sitl=True)
    app.state.link_ok = True
    calls = []
    app.mav.arm = lambda value: calls.append(value)

    app._arm("test")

    assert calls == [True]


def test_gamepad_start_arms_once_and_back_disarms():
    app = ElTorpedoApp(Config(), sitl=True)
    app.state.link_ok = True
    calls = []
    app.mav.arm = lambda value: calls.append(value)

    start = app.cfg.gamepad.buttons["arm"]
    back = app.cfg.gamepad.buttons["disarm"]
    buttons = [False] * 11
    buttons[start] = True
    held = RawInput(buttons=tuple(buttons), connected=True)

    app._handle_gamepad_edges(held)
    assert calls == [True]

    app._handle_gamepad_edges(held)
    assert calls == [True]

    buttons[start] = False
    app._handle_gamepad_edges(RawInput(buttons=tuple(buttons), connected=True))
    buttons[back] = True
    app._handle_gamepad_edges(RawInput(buttons=tuple(buttons), connected=True))
    assert calls == [True, False]
