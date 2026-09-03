#!/usr/bin/env bash
# Regenerates agents/comment-reaper.md from the persona reference so the two never drift.
set -euo pipefail
cd "$(dirname "$0")/.."
SRC=skills/decomment/references/comment-reaper.md
OUT=agents/comment-reaper.md
{
  cat <<'HDR'
---
name: comment-reaper
description: Deletes comments that do not earn their place and flags the code they were covering for. Report-only on code; edits comments only. Generated from skills/decomment/references/comment-reaper.md, do not edit by hand.
---

HDR
  cat "$SRC"
} > "$OUT"
echo "wrote $OUT"
