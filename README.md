# eltorpedo

Terminal UI for the custom ArduSub Pixhawk ROV (SimpleROV-4 frame) with an
Xbox gamepad. Runs on the Jetson and reaches the Pixhawk through a Raspberry
Pi 4B running `mavlink-router`.

## Quick start

```bash
uv sync
uv run eltorpedo
```

Windows SITL:

```powershell
.\scripts\run_sitl.ps1
uv run eltorpedo --sitl
```

Deployment: `deploy/README.md`. Bench test: `BENCH.md`.

## Controls

| Input | Action |
| --- | --- |
| Left stick | throttle + yaw |
| Right stick | forward + lateral |
| A / B / X (Xbox) | claw close / open / stop |
| Cross / Circle / Square (PS) | claw close / open / stop |
| D-pad up/down | cycle mode |
| Start (Menu) | arm |
| Back (View) | disarm |
| Options (PS) | arm |
| Share (PS) | disarm |
| H or ? | in-app help overlay |
| Q | quit |
| K | keybind settings (rebind and save to config.toml) |
| F | fix claw parameters after confirmation |
| 1 / 2 / 3 | select mode (bench) |
| Z / C / O / X | arm, claw close/open/stop (bench) |

Keyboard bindings are configurable. Press `K` at runtime, or edit the
`[ui.keybinds]` table in `config.toml`. Alternative keys are comma-separated,
for example `show_help = "h,question_mark"`.

## Controllers

Any SDL/pygame gamepad works. Xbox and PlayStation layouts have built-in
profiles. List what SDL sees:

```bash
uv run eltorpedo --list-gamepads
# 0: PS4 Controller  (6 axes, 16 buttons, 0 hats)  profile=playstation
# 1: Xbox 360 Controller  (6 axes, 11 buttons, 1 hats)  profile=xbox
```

The TUI picks the controller whose name contains `preferred_name` from
`config.toml` (`"Xbox"` by default), then falls back to `index`. The profile
comes from the device name unless `profile` is set to `xbox` or `playstation`.

Most other pads (8BitDo, Logitech, generic XInput) report the Xbox layout and
work through the xbox profile. Override `[gamepad.axes.*]` or
`[gamepad.buttons]` in `config.toml` if a pad maps differently.

Textual mouse tracking is off, and the TUI prefers the named controller. This
keeps a PlayStation touchpad from moving the desktop cursor or focus out of the
terminal.

If the pointer still moves or a terminal/tmux tab bar changes while flying, the
controller touchpad is acting as a mouse outside the TUI. Disconnect that pad,
disable its touchpad in the OS, or turn off tmux mouse handling:

```bash
tmux set -g mouse off
```

Check the pad name in the center panel. `PlayStation pad: touchpad can move the
desktop cursor` in the log means the PS pad is selected.

The TUI streams `MANUAL_CONTROL` at 20 Hz and a GCS heartbeat at 1 Hz. If the
gamepad disappears, axes go to zero and the vehicle disarms after 1 s. The
firmware pilot-input and GCS failsafes remain the backstop.

`config.toml` is generated on first run. Axis indices, buttons, endpoint and
rates are all configurable.
