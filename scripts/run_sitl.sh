#!/usr/bin/env bash
# Build the custom ArduSub SITL and send MAVLink to the TUI on UDP 14550.
# Set ARDUPILOT_DIR to the ardupilot checkout, e.g. ../torpedosub/ardupilot.
set -euo pipefail

ARDUPILOT_DIR="${ARDUPILOT_DIR:-$HOME/ardupilot}"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [ ! -d "$ARDUPILOT_DIR" ]; then
    echo "ArduPilot checkout not found: $ARDUPILOT_DIR" >&2
    echo "Set ARDUPILOT_DIR to the ardupilot directory." >&2
    exit 1
fi

cd "$ARDUPILOT_DIR"

if [ "${SKIP_BUILD:-0}" != "1" ]; then
    ./waf configure --board sitl
    ./waf sub
fi

exec python3 Tools/autotest/sim_vehicle.py \
    -v ArduSub \
    -f vectored \
    --add-param-file="$HERE/simplerov4.parm" \
    --console \
    --map \
    --out=udp:127.0.0.1:14550
