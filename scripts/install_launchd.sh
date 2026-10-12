#!/bin/sh
set -eu
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
PLIST="$HOME/Library/LaunchAgents/com.korgan.intelligence.plist"
mkdir -p "$HOME/Library/LaunchAgents" "$ROOT/data/logs"
python3 - "$ROOT" "$PLIST" <<'PY'
import plistlib, sys
root, path = sys.argv[1:]
data = {"Label":"com.korgan.intelligence", "ProgramArguments":[root+"/.venv/bin/python", "-m", "app"], "WorkingDirectory":root, "RunAtLoad":True, "KeepAlive":False, "ThrottleInterval":60, "StartInterval":1800, "StandardOutPath":root+"/data/logs/launchd.out", "StandardErrorPath":root+"/data/logs/launchd.err", "EnvironmentVariables":{"PYTHONUNBUFFERED":"1"}}
with open(path, "wb") as fh: plistlib.dump(data, fh)
PY
DOMAIN="gui/$(id -u)"
launchctl bootout "$DOMAIN/com.korgan.intelligence" 2>/dev/null || true
launchctl bootstrap "$DOMAIN" "$PLIST"
echo "Installed $PLIST"
