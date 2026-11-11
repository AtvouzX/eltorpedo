# Deploying eltorpedo

## Raspberry Pi 4B (MAVLink router)

1. Install the router package:

   ```bash
   sudo apt install mavlink-router
   ```

2. Copy the config:

   ```bash
   sudo cp deploy/mavlink-router.conf /etc/mavlink-router/main.conf
   ```

3. Check the Pixhawk device. With a USB cable it is normally
   `/dev/ttyACM0`. Confirm with `ls /dev/ttyACM*` before starting.

4. Start and enable the router:

   ```bash
   sudo cp deploy/mavlink-router.service /etc/systemd/system/
   sudo systemctl daemon-reload
   sudo systemctl enable --now mavlink-router
   ```

5. Verify:

   ```bash
   systemctl status mavlink-router
   ss -lunp | grep 14550
   ```

The router exposes UDP 14550 for the TUI and UDP 14551 for QGroundControl.
Both can run at the same time. Do not enable QGroundControl's joystick while
the TUI is flying: two `MANUAL_CONTROL` streams fight over the vehicle.

## Jetson (TUI)

1. Install `uv`:

   ```bash
   curl -LsSf https://astral.sh/uv/install.sh | sh
   ```

2. Copy this repository to `/opt/eltorpedo` and install. JetPack 5 ships
   Python 3.8, so let `uv` provide 3.12:

   ```bash
   cd /opt/eltorpedo
   uv python install 3.12
   uv sync --python 3.12
   ```

3. Run:

   ```bash
   uv run --python 3.12 eltorpedo --config config.toml
   ```

   The default endpoint is `udpin:0.0.0.0:14550`, so the TUI listens for
   the router.

4. Optional autostart on the local console:

   ```bash
   sudo cp deploy/eltorpedo.service /etc/systemd/system/
   sudo systemctl daemon-reload
   sudo systemctl enable --now eltorpedo
   ```

   The unit takes over `/dev/tty1` and is shipped disabled. It does not work
   over SSH; run the TUI manually from an SSH session instead.

## Gamepad

Connect the controller over USB. Xbox and PlayStation pads both work; the TUI
picks the one matching `preferred_name` in `config.toml` (default `"Xbox"`).
Check what SDL sees:

```bash
uv run eltorpedo --list-gamepads
```

On Linux the user needs read access to the joystick device:

```bash
sudo usermod -aG input "$USER"
```

Log out and back in after changing groups. If the pad is not listed, check
`ls /dev/input/js*` and `dmesg | tail`.

## First connect checklist

- `GRIP_ENABLE=1`, `GRIP_TYPE=3`
- `BTN0_FUNCTION=140` (close), `BTN1_FUNCTION=139` (open),
  `BTN2_FUNCTION=141` (stop)
- The claw panel shows `CONFIG OK`. If it shows `MISMATCH`, press `F` and
  confirm the write.

## Windows development

Use WSL for SITL:

```powershell
.\scripts\run_sitl.ps1
```

Then run the TUI in another terminal:

```powershell
uv run eltorpedo --sitl
```

`--sitl` skips the claw-configuration arming check. The claw panel stays
disabled when the firmware does not expose `GRIP_*` parameters.
