#!/usr/bin/env bash
set -euo pipefail
build_image --tag "$REVISION"
apply_migration migrations/002_drop_legacy.sql
rollout_image "$REVISION"
