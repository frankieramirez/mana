#!/bin/bash
# Drives ui/panel.html in the headless browser and replays checks/shift-k.json.
set -u
cd "$(dirname "$0")/.."
if ! command -v chromium-fixture >/dev/null 2>&1; then
  echo "interaction check: chromium-fixture: command not found" >&2
  exit 127
fi
exec chromium-fixture --page ui/panel.html --steps checks/shift-k.json
