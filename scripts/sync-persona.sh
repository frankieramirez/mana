#!/usr/bin/env bash
# Synchronize the standalone persona references and skill entrypoint blocks.
set -euo pipefail
cd "$(dirname "$0")/.."
case "${1:-}" in
  ''|--check) ;;
  *) echo "usage: scripts/sync-persona.sh [--check]" >&2; exit 2 ;;
esac
[ "$#" -le 1 ] || { echo "usage: scripts/sync-persona.sh [--check]" >&2; exit 2; }
python3 - "${1:-}" <<'PY'
import pathlib
import re
import sys

root = pathlib.Path('skills')
source = root / 'attune/references'
voice = (source / 'archmage.md').read_bytes()
block = (source / 'persona-activation.md').read_text().strip()
begin, end = '<!-- BEGIN MANA PERSONA -->', '<!-- END MANA PERSONA -->'
if block.count(begin) != 1 or block.count(end) != 1 or not block.startswith(begin) or not block.endswith(end):
    sys.exit('invalid canonical persona activation block')
pattern = re.compile(re.escape(begin) + r'.*?' + re.escape(end) + r'\n*', re.S)
updates = []
for directory in sorted(root.iterdir()):
    if not directory.is_dir():
        continue
    entry = directory / 'SKILL.md'
    text = entry.read_text()
    counts = text.count(begin), text.count(end)
    if counts not in ((0, 0), (1, 1)) or (counts == (1, 1) and text.index(begin) > text.index(end)):
        sys.exit(f'{entry}: malformed persona markers; repair before syncing')
    text = pattern.sub('', text)
    frontmatter = re.match(r'\A---\n.*?\n---\n', text, re.S)
    if not frontmatter:
        sys.exit(f'{entry}: missing frontmatter')
    expected = text[:frontmatter.end()] + '\n' + block + '\n\n' + text[frontmatter.end():].lstrip('\n')
    updates.append((entry, expected.encode()))
    updates.append((directory / 'references/archmage.md', voice))

stale = [(path, data) for path, data in updates if not path.exists() or path.read_bytes() != data]
if sys.argv[1] == '--check':
    for path, _ in stale:
        print(f'{path} is out of sync; run scripts/sync-persona.sh', file=sys.stderr)
    sys.exit(bool(stale))
for path, data in stale:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    print(f'wrote {path}')
PY
