#!/usr/bin/env bash
# Checks the repo is a valid plugin + skills.sh source and that no origin residue is left.
set -uo pipefail
cd "$(dirname "$0")/.."
fail=0
err() { echo "FAIL: $*" >&2; fail=1; }

# 1. Every skill dir has a SKILL.md whose name matches the directory and has a description.
for dir in skills/*/; do
  name=$(basename "$dir")
  f="$dir/SKILL.md"
  [ -f "$f" ] || { err "$dir has no SKILL.md"; continue; }
  fm_name=$(sed -n '2,20p' "$f" | grep -m1 '^name:' | sed 's/^name:[[:space:]]*//; s/^"//; s/"$//')
  [ "$fm_name" = "$name" ] || err "$f frontmatter name '$fm_name' != dir '$name'"
  sed -n '2,20p' "$f" | grep -q '^description:[[:space:]]*.\+' || err "$f has no description"
  # skills.sh drops a skill whose frontmatter is not valid YAML (an unquoted ": " inside a value does it).
  python3 - "$f" <<'PY' || err "$f frontmatter does not parse as YAML"
import sys, re
text = open(sys.argv[1]).read().split('\n---', 2)[0].split('\n', 1)[1]
try:
    import yaml; yaml.safe_load(text)
except ImportError:
    for line in text.split('\n'):
        m = re.match(r'^([\w-]+):\s*(.*)$', line)
        if m and not m.group(2).startswith(('"', "'")) and ': ' in m.group(2):
            sys.exit(1)
PY
done

# 2. Agent paths in plugin.json exist and the generated agent matches its source.
for p in $(python3 -c 'import json;print(" ".join(json.load(open(".claude-plugin/plugin.json")).get("agents",[])))'); do
  [ -f "$p" ] || err "plugin.json agent path missing: $p"
done
if [ -f agents/comment-reaper.md ]; then
  tmp=$(mktemp)
  awk 'f>=2{print} /^---$/{f++}' agents/comment-reaper.md | sed '1{/^$/d;}' > "$tmp"
  diff -q "$tmp" skills/decomment/references/comment-reaper.md >/dev/null \
    || err "agents/comment-reaper.md is out of sync; run scripts/sync-agent.sh"
  rm -f "$tmp"
fi

# 3. Manifests parse.
for j in .claude-plugin/plugin.json .claude-plugin/marketplace.json skills/deep-review/references/findings-schema.json; do
  python3 -c "import json,sys;json.load(open('$j'))" 2>/dev/null || err "$j is not valid JSON"
done

# 4. No residue from the repos these skills were originally forked from, no em dashes in prose.
banned='EveryInc|compound-engineering|\bce-[a-z]|\blfg\b|babysit|julik|\bcora\b|pr-comment-resolver|Comment Sicko|Sicko|pr-feedback|MUST KILL|pstack|safe_auto|/how\b|/why\b|/architect\b'
hits=$(grep -rnE "$banned" skills agents CLAUDE.md 2>/dev/null || true)   # README names the origins on purpose
[ -z "$hits" ] || { err "origin residue found:"; echo "$hits" >&2; }
# spit/SKILL.md and deep-review voice.md quote dashes as examples of what not to write.
dashes=$(grep -rn --include='*.md' -e '—' -e '–' skills agents README.md CLAUDE.md 2>/dev/null \
  | grep -v -e 'skills/spit/SKILL.md' -e 'skills/deep-review/references/voice.md' || true)
[ -z "$dashes" ] || { err "em/en dashes found:"; echo "$dashes" >&2; }

# 5. Scripts are executable and parse.
for s in skills/*/scripts/* scripts/*.sh; do
  [ -e "$s" ] || continue
  [ -x "$s" ] || err "$s is not executable"
  head -1 "$s" | grep -q bash && { bash -n "$s" || err "$s does not parse"; }
done

# 6. Claude Code's own validator, when available.
if command -v claude >/dev/null 2>&1; then
  claude plugin validate . >/dev/null 2>&1 || { claude plugin validate . >&2; err "claude plugin validate failed"; }
fi

[ $fail -eq 0 ] && echo "ok" || exit 1
