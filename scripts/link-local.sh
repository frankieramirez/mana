#!/usr/bin/env bash
# Dev loop: symlink this checkout's skills and agents into ~/.claude so edits are live.
# Do not use this while the `fr` plugin is installed, or every skill shows up twice.
set -euo pipefail
cd "$(dirname "$0")/.."
root=$(pwd)
mkdir -p ~/.claude/skills ~/.claude/agents
for dir in "$root"/skills/*/; do
  name=$(basename "$dir")
  ln -sfn "$dir" ~/.claude/skills/"$name"
  echo "~/.claude/skills/$name -> $dir"
done
for f in "$root"/agents/*.md; do
  ln -sfn "$f" ~/.claude/agents/"$(basename "$f")"
  echo "~/.claude/agents/$(basename "$f") -> $f"
done
