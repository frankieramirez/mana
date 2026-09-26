#!/usr/bin/env bash
set -euo pipefail
submit_release --pipeline partner-production --revision "$REVISION"
