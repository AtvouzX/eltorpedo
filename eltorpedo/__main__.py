"""Package entry point."""

from __future__ import annotations

import argparse
from pathlib import Path

from .app import ElTorpedoApp
from .config import detect_profile, load_config
from .gamepad import list_devices


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="ArduSub ROV control TUI")
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("config.toml"),
        help="path to config.toml (created if missing)",
    )
    parser.add_argument(
        "--endpoint",
        default=None,
        help="override the MAVLink endpoint, e.g. udpout:192.168.1.50:14550",
    )
    parser.add_argument(
        "--sitl",
        action="store_true",
        help="relax claw-config arming checks for SITL testing",
    )
    parser.add_argument(
        "--list-gamepads",
        action="store_true",
        help="list connected controllers and exit",
    )
    args = parser.parse_args(argv)

    if args.list_gamepads:
        devices = list_devices()
        if not devices:
            print("No controllers found.")
        for device in devices:
            print(
                f"{device.index}: {device.name}  "
                f"({device.axes} axes, {device.buttons} buttons, {device.hats} hats)  "
                f"profile={detect_profile(device.name)}"
            )
        return

    config = load_config(args.config, args.endpoint)
    app = ElTorpedoApp(config, sitl=args.sitl)
    # Textual mouse tracking would let the controller touchpad move focus.
    app.run(mouse=False)


if __name__ == "__main__":
    main()
