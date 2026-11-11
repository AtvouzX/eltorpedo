# Bench checklist

Props off, ROV restrained, battery disconnect within reach. Run every item
before the first water test.

## Link and telemetry

- [ ] `mavlink-router` is running and `ss -lunp` shows 14550.
- [ ] TUI shows `LINK OK` and a heartbeat age below 200 ms.
- [ ] Mode matches QGroundControl.
- [ ] Depth, heading and attitude change when the Pixhawk is moved.
- [ ] Battery voltage and current match QGroundControl.

## Arm and modes

- [ ] `uv run eltorpedo --list-gamepads` shows the expected controller and profile.
- [ ] The center panel shows the right gamepad name and profile.
- [ ] `H` opens the help overlay and lists the correct button names.
- [ ] Start (Menu) arms on one press.
- [ ] Holding Start does not send a second arm.
- [ ] Back (View) disarms immediately.
- [ ] QGroundControl shows the same armed state.
- [ ] D-pad up/down cycles MANUAL, STABILIZE, DEPTH HOLD.
- [ ] QGroundControl shows the same mode.
- [ ] Keyboard `Z` arms and disarms (bench testing only).

## Axes

- [ ] Right stick up commands positive forward.
- [ ] Right stick right commands positive lateral.
- [ ] Left stick up commands positive throttle.
- [ ] Left stick right commands positive yaw.
- [ ] The `REVERSE UNAVAILABLE` warning appears when forward is negative.
- [ ] Motors 1 and 2 go to `FWD_IDLE`, not reverse.

## Claw

- [ ] Claw panel shows `CONFIG OK`.
- [ ] `A` closes, `B` opens, `X` stops.
- [ ] `Claw: closing` then `Claw: object grasped` or `Claw: fully closed`.
- [ ] `GRIP_DC_CURR` updates while the motor runs.
- [ ] Blocking the claw produces a fault with the firmware reason.
- [ ] Only `X` clears the fault. It does not auto-retry.
- [ ] `F` with a deliberate mismatch writes the params after confirmation.

## Failure behavior

- [ ] Unplug the gamepad: axes go to zero, then the vehicle disarms.
- [ ] Reconnect the gamepad: controls work again, the vehicle stays disarmed.
- [ ] Quit while armed: the confirmation appears; confirm sends disarm.
- [ ] Unplug the Pixhawk USB: `LINK LOST` appears, controls are disabled.
- [ ] Reconnect: `Link up`, streams and params return, no auto-arm.
- [ ] Reboot the Pixhawk: TUI recovers, mode and armed state refresh.
- [ ] Start the TUI while the vehicle is armed: it does not arm, and it
      shows the armed state from the first heartbeat.

## SITL

- [ ] `scripts/run_sitl.sh` builds and starts the custom firmware.
- [ ] `uv run eltorpedo --sitl` connects and shows telemetry.
- [ ] Arm, mode changes and claw button messages appear in the log.
