#!/usr/bin/env bash
# Exercise synchronization in disposable standalone skill fixtures.
set -euo pipefail
cd "$(dirname "$0")/.."
python3 - <<'PY'
import pathlib
import shutil
import subprocess
import tempfile

repository = pathlib.Path.cwd()
with tempfile.TemporaryDirectory(prefix='mana persona ') as temporary:
    root = pathlib.Path(temporary)
    (root / 'scripts').mkdir()
    shutil.copy2(repository / 'scripts/sync-persona.sh', root / 'scripts/sync-persona.sh')
    source = root / 'skills/attune/references'
    source.mkdir(parents=True)
    for name in ('archmage.md', 'persona-activation.md'):
        shutil.copy2(repository / 'skills/attune/references' / name, source / name)
    original = '---\nname: {name}\ndescription: Test skill\n---\n\n# Test\n\nKeep this body exactly.\n'
    for name in ('attune', 'isolated'):
        folder = root / 'skills' / name
        folder.mkdir(exist_ok=True)
        (folder / 'SKILL.md').write_text(original.format(name=name))

    def run(*arguments, success=True):
        result = subprocess.run(['bash', str(root / 'scripts/sync-persona.sh'), *arguments],
                                cwd='/', capture_output=True, text=True)
        assert (result.returncode == 0) == success, result.stdout + result.stderr
        return result

    def snapshot():
        return {str(path.relative_to(root)): path.read_bytes()
                for path in root.rglob('*') if path.is_file()}

    before = snapshot()
    run('--check', success=False)
    assert snapshot() == before, '--check changed files'
    run()
    run('--check')
    synced = snapshot()
    run()
    assert snapshot() == synced, 'sync is not idempotent'
    for name in ('attune', 'isolated'):
        skill = root / 'skills' / name
        text = (skill / 'SKILL.md').read_text()
        assert text.startswith('---\nname: ' + name + '\n')
        assert text.endswith('# Test\n\nKeep this body exactly.\n')
        assert text.count('<!-- BEGIN MANA PERSONA -->') == 1
        assert text.count('<!-- END MANA PERSONA -->') == 1
        assert '[references/archmage.md](references/archmage.md)' in text
        assert (skill / 'references/archmage.md').read_bytes() == (source / 'archmage.md').read_bytes()

    voice = root / 'skills/isolated/references/archmage.md'
    voice.write_text('stale voice\n')
    before = snapshot()
    run('--check', success=False)
    assert snapshot() == before
    run()
    assert snapshot() == synced

    entry = root / 'skills/isolated/SKILL.md'
    entry.write_text(entry.read_text().replace('## Persona at invocation', '## Stale activation'))
    run('--check', success=False)
    run()
    assert snapshot() == synced

    # A malformed later skill must not leave earlier skills partially rewritten.
    (source / 'archmage.md').write_text((source / 'archmage.md').read_text() + '\nUpdated voice.\n')
    entry.write_text(entry.read_text().replace('<!-- END MANA PERSONA -->', ''))
    before = snapshot()
    run(success=False)
    assert snapshot() == before, 'malformed markers caused partial writes'
    entry.write_bytes(synced['skills/isolated/SKILL.md'])
    run()
    run('--check')

    (root / 'skills/new').mkdir()
    (root / 'skills/new/SKILL.md').write_text(original.format(name='new'))
    run('--check', success=False)
    run()
    run('--check')
    assert (root / 'skills/new/references/archmage.md').read_bytes() == (source / 'archmage.md').read_bytes()
    before = snapshot()
    run('--invalid', success=False)
    run('--check', 'extra', success=False)
    assert snapshot() == before

print('persona synchronization fixtures: ok')
PY
