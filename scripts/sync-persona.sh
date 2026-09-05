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

repo = pathlib.Path.cwd().resolve()
root = repo / 'skills'
source = root / 'attune/references'
begin, end = '<!-- BEGIN MANA PERSONA -->', '<!-- END MANA PERSONA -->'

def reject_symlink_components(path):
    try:
        relative = path.relative_to(repo)
    except ValueError:
        sys.exit(f'{path}: target is outside repository')
    current = repo
    for component in relative.parts:
        current /= component
        if current.is_symlink():
            sys.exit(f'{path}: symlink destination is not allowed')
    try:
        path.resolve(strict=False).relative_to(repo)
    except ValueError:
        sys.exit(f'{path}: target resolves outside repository')

if root.is_symlink():
    sys.exit(f'{root}: symlink destination is not allowed')
reject_symlink_components(source)
for path in (source / 'archmage.md', source / 'persona-activation.md'):
    reject_symlink_components(path)

voice = (source / 'archmage.md').read_bytes()
block = (source / 'persona-activation.md').read_bytes().decode('utf-8').strip()
if block.count(begin) != 1 or block.count(end) != 1 or not block.startswith(begin) or not block.endswith(end):
    sys.exit('invalid canonical persona activation block')
pattern = re.compile(re.escape(begin) + r'.*?' + re.escape(end), re.S)
updates = []
for directory in sorted(root.iterdir()):
    if not directory.is_dir():
        continue
    reject_symlink_components(directory)
    entry = directory / 'SKILL.md'
    references = directory / 'references'
    reject_symlink_components(entry)
    reject_symlink_components(references)
    reject_symlink_components(references / 'archmage.md')
    original = entry.read_bytes().decode('utf-8')
    text = original
    counts = text.count(begin), text.count(end)
    if counts not in ((0, 0), (1, 1)) or (counts == (1, 1) and text.index(begin) > text.index(end)):
        sys.exit(f'{entry}: malformed persona markers; repair before syncing')
    had_block = begin in text
    text = pattern.sub('', text)
    frontmatter = re.match(r'\A---\r?\n.*?\r?\n---\r?\n', text, re.S)
    if not frontmatter:
        sys.exit(f'{entry}: missing frontmatter')
    if had_block:
        expected = pattern.sub(lambda _: block, original, count=1)
    else:
        newline = '\r\n' if '\r\n' in text[:frontmatter.end()] else '\n'
        expected = text[:frontmatter.end()] + newline + block + newline + text[frontmatter.end():]
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
