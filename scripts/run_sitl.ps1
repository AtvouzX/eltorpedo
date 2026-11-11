param(
    [string]$ArduPilotDir = ""
)

$ErrorActionPreference = "Stop"

if (-not $ArduPilotDir) {
    $ArduPilotDir = Join-Path (Split-Path $PSScriptRoot -Parent) "..\torpedosub\ardupilot"
}
$ArduPilotDir = (Resolve-Path $ArduPilotDir).Path

$wslArduPilot = (wsl wslpath -a $ArduPilotDir).Trim()
$wslScript = (wsl wslpath -a (Join-Path $PSScriptRoot "run_sitl.sh")).Trim()

Write-Host "Starting custom ArduSub SITL from $ArduPilotDir"
wsl bash -lc "ARDUPILOT_DIR='$wslArduPilot' bash '$wslScript'"
