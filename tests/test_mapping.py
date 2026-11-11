from eltorpedo.config import AxisSpec, GamepadConfig, apply_profile, detect_profile
from eltorpedo.gamepad import DeviceInfo, RawInput, choose_device, map_axes, shape_axis


def test_deadzone_returns_zero():
    assert shape_axis(0.04, AxisSpec(0), 0.08) == 0.0
    assert shape_axis(-0.04, AxisSpec(0), 0.08) == 0.0


def test_deadzone_rescales_to_full_range():
    assert shape_axis(0.54, AxisSpec(0), 0.08) == 0.5
    assert shape_axis(1.0, AxisSpec(0), 0.08) == 1.0


def test_invert_flips_sign():
    assert shape_axis(-0.5, AxisSpec(0, True), 0.0) == 0.5
    assert shape_axis(0.5, AxisSpec(0, False), 0.0) == 0.5


def test_map_axes_xbox_layout():
    cfg = GamepadConfig(deadzone=0.0)
    # axes: left x, left y, right x, right y
    raw = RawInput(axes=(0.0, -0.5, 0.25, -1.0), connected=True)
    x, y, z, r = map_axes(raw, cfg)
    assert x == 1000  # right stick up = forward
    assert y == 250  # right stick right = lateral
    assert z == 500  # left stick up = throttle
    assert r == 0


def test_map_axes_missing_axis_is_zero():
    cfg = GamepadConfig()
    raw = RawInput(axes=(), connected=True)
    assert map_axes(raw, cfg) == (0, 0, 0, 0)


def test_detect_profile_by_name():
    assert detect_profile("Xbox 360 Controller") == "xbox"
    assert detect_profile("PS4 Controller") == "playstation"
    assert detect_profile("Wireless Controller") == "playstation"


def test_apply_profile_switches_playstation_buttons():
    cfg = GamepadConfig()
    assert apply_profile(cfg, "PS4 Controller") == "playstation"
    assert cfg.buttons["arm"] == 9
    assert cfg.labels["claw_close"] == "Cross"


def test_custom_button_survives_profile_switch():
    cfg = GamepadConfig(custom_buttons={"arm"})
    cfg.buttons["arm"] = 4
    apply_profile(cfg, "PS4 Controller")
    assert cfg.buttons["arm"] == 4


def test_choose_device_prefers_name_over_index():
    devices = [
        DeviceInfo(0, "PS4 Controller", 6, 16, 0),
        DeviceInfo(1, "Xbox 360 Controller", 6, 11, 1),
    ]
    cfg = GamepadConfig(preferred_name="Xbox", index=0)
    assert choose_device(cfg, devices) == 1


def test_choose_device_falls_back_to_index():
    devices = [DeviceInfo(0, "PS4 Controller", 6, 16, 0)]
    cfg = GamepadConfig(preferred_name="Xbox", index=0)
    assert choose_device(cfg, devices) == 0
