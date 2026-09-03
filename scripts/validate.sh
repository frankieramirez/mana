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
scripts/sync-agent.sh --check || err "generated agents are out of sync"

# 2b. The plugin prefix agrees across both manifests and every /prefix:skill in the README exists.
python3 - <<'PY' || err "plugin naming is inconsistent"
import json, pathlib, re, sys
plugin = json.load(open(".claude-plugin/plugin.json"))
market = json.load(open(".claude-plugin/marketplace.json"))
names = [e["name"] for e in market["plugins"]]
bad = []
if plugin["name"] not in names:
    bad.append(f"plugin.json name {plugin['name']!r} is not in marketplace.json plugins {names}")
prefix = plugin["name"]
dirs = {d.name for d in pathlib.Path("skills").iterdir() if d.is_dir()}
readme = pathlib.Path("README.md").read_text()
for used_prefix, skill in sorted(set(re.findall(r"/([a-z0-9-]+):([a-z0-9-]+)", readme))):
    if used_prefix != prefix:
        bad.append(f"README uses /{used_prefix}:{skill} but the plugin prefix is {prefix}")
    elif skill not in dirs:
        bad.append(f"README uses /{used_prefix}:{skill} but skills/{skill} does not exist")
for name in sorted(dirs):
    if f"/{prefix}:{name}" not in readme:
        bad.append(f"skills/{name} is never shown as /{prefix}:{name} in README.md")
for line in bad:
    print(line, file=sys.stderr)
sys.exit(1 if bad else 0)
PY

# 3. Manifests parse.
for j in .claude-plugin/plugin.json .claude-plugin/marketplace.json skills/scan/references/findings-schema.json; do
  python3 -c "import json,sys;json.load(open('$j'))" 2>/dev/null || err "$j is not valid JSON"
done

# 4. No residue from the repos these skills were originally forked from, no em dashes in prose.
banned='EveryInc|compound-engineering|\bce-[a-z]|\blfg\b|babysit|julik|\bcora\b|pr-comment-resolver|Comment Sicko|Sicko|pr-feedback|MUST KILL|pstack|safe_auto|/how\b|/why\b|/architect\b'
hits=$(grep -rnE "$banned" skills agents CLAUDE.md 2>/dev/null || true)   # README names the origins on purpose
[ -z "$hits" ] || { err "origin residue found:"; echo "$hits" >&2; }
# dispel/SKILL.md and scan voice.md quote dashes as examples of what not to write.
dashes=$(grep -rn --include='*.md' -e '—' -e '–' skills agents README.md CLAUDE.md 2>/dev/null \
  | grep -v -e 'skills/dispel/SKILL.md' -e 'skills/scan/references/voice.md' || true)
[ -z "$dashes" ] || { err "em/en dashes found:"; echo "$dashes" >&2; }

# 5. Scripts are executable and parse.
for s in skills/*/scripts/* scripts/*.sh; do
  [ -e "$s" ] || continue
  [ -x "$s" ] || err "$s is not executable"
  head -1 "$s" | grep -q bash && { bash -n "$s" || err "$s does not parse"; }
done

# 5b. Ship files shared by reveal and cast stay identical. Edit skills/reveal/ and copy.
while read -r a b; do
  [ -n "${a:-}" ] || continue
  cmp -s "$a" "$b" || err "$a and $b differ; edit skills/reveal/ and copy to skills/cast/"
done <<'EOF'
skills/reveal/references/capture.md skills/cast/references/capture.md
skills/reveal/references/body.md skills/cast/references/body.md
skills/reveal/references/attach.md skills/cast/references/attach.md
skills/reveal/scripts/open-pr.sh skills/cast/scripts/open-pr.sh
skills/reveal/scripts/text-frame.sh skills/cast/scripts/text-frame.sh
EOF

# 6. Claude Code's own validator, when available.
if command -v claude >/dev/null 2>&1; then
  claude plugin validate . >/dev/null 2>&1 || { claude plugin validate . >&2; err "claude plugin validate failed"; }
fi

[ $fail -eq 0 ] && echo "ok" || exit 1
