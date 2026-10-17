#!/usr/bin/env bash
# Exercise generated controls against real local Node assertions and disposable git fixtures.
set -euo pipefail
cd "$(dirname "$0")/.."
python3 scripts/test_leyline_install.py "$@"
