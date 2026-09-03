#!/usr/bin/env bash
# Regenerates agents/*.md from their persona references so the two never drift.
# Usage: sync-agent.sh          write the agent files
#        sync-agent.sh --check  exit 1 when any agent file is out of date
set -euo pipefail
cd "$(dirname "$0")/.."

# name | source reference | description
AGENTS='
comment-reaper|skills/scrap/references/comment-reaper.md|Deletes comments that do not earn their place and flags the code they were covering for. Report-only on code; edits comments only.
ghost|skills/be-me/references/ghost.md|Builds a voice profile from the user'"'"'s own writing (session messages, PR comments, PR descriptions, commits) and returns a filled-in draft with the evidence. Read-only; never writes the profile.
'

render() {
  local name=$1 src=$2 desc=$3
  printf -- '---\nname: %s\ndescription: %s Generated from %s, do not edit by hand.\n' "$name" "$desc" "$src"
  case $name in
    ghost) printf 'tools: Read, Bash, Grep, Glob\n' ;;
  esac
  printf -- '---\n\n'
  cat "$src"
}

check=${1:-}
status=0
while IFS='|' read -r name src desc; do
  [ -n "$name" ] || continue
  out=agents/$name.md
  if [ "$check" = "--check" ]; then
    if ! diff -q <(render "$name" "$src" "$desc") "$out" >/dev/null 2>&1; then
      echo "$out is out of sync; run scripts/sync-agent.sh" >&2
      status=1
    fi
  else
    render "$name" "$src" "$desc" > "$out"
    echo "wrote $out"
  fi
done <<< "$AGENTS"
exit $status
