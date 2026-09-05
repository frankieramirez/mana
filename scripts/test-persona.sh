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

    activation = source / 'persona-activation.md'
    activation.write_bytes(activation.read_bytes().replace(
        b'<!-- END MANA PERSONA -->',
        b'Literal path: C:' + bytes((92,)) + b'temp' + bytes((92,)) + b'wizard' + bytes((92,)) + b'1\n<!-- END MANA PERSONA -->'))
    run()
    run('--check')

    (root / 'skills/new').mkdir()
    (root / 'skills/new/SKILL.md').write_text(original.format(name='new'))
    run('--check', success=False)
    run()
    run('--check')
    assert (root / 'skills/new/references/archmage.md').read_bytes() == (source / 'archmage.md').read_bytes()

    blank_skill = root / 'skills/blank-lines'
    blank_skill.mkdir()
    blank_suffix = b'\n\n\n# Blank lines\n\nKeep every blank line.\n'
    (blank_skill / 'SKILL.md').write_bytes(
        b'---\nname: blank-lines\ndescription: Test skill\n---\n' + blank_suffix)
    run()
    blank_entry = blank_skill / 'SKILL.md'
    blank_text = blank_entry.read_bytes()
    assert blank_text.endswith(blank_suffix), 'insertion changed the original suffix'
    marker_end = b'<!-- END MANA PERSONA -->'
    preserved_suffix = b'\n\n\n\n# Replaced body\n'
    blank_entry.write_bytes(blank_text.split(marker_end, 1)[0] + marker_end + preserved_suffix)
    run()
    assert blank_entry.read_bytes().endswith(preserved_suffix), 'replacement changed the original suffix'

    crlf_skill = root / 'skills/crlf'
    crlf_skill.mkdir()
    crlf_suffix = b'\r\n\r\n# CRLF body\r\n\r\nKeep CRLF bytes.\r\n'
    (crlf_skill / 'SKILL.md').write_bytes(
        b'---\r\nname: crlf\r\ndescription: Test skill\r\n---\r\n' + crlf_suffix)
    run()
    crlf_entry = crlf_skill / 'SKILL.md'
    assert crlf_entry.read_bytes().endswith(crlf_suffix), 'insertion changed CRLF suffix'
    crlf_before = crlf_entry.read_bytes()
    run()
    assert crlf_entry.read_bytes() == crlf_before, 'CRLF sync is not idempotent'

    before = snapshot()
    run('--invalid', success=False)
    run('--check', 'extra', success=False)
    assert snapshot() == before

    # Symlink destinations, including parents and skill directories, are rejected
    # before any existing destination is changed.
    external = root / 'external'
    external.mkdir()
    outside_root = pathlib.Path(tempfile.mkdtemp(prefix='mana persona external '))
    outside_voice = outside_root / 'archmage.md'
    outside_voice.write_bytes(b'external voice\n')
    isolated_references = root / 'skills/isolated/references'
    isolated_voice = isolated_references / 'archmage.md'
    isolated_voice.unlink()
    isolated_voice.symlink_to(outside_voice)
    before = snapshot()
    run(success=False)
    assert outside_voice.read_bytes() == b'external voice\n'
    assert snapshot() == before, 'file symlink caused partial writes'
    isolated_voice.unlink()
    isolated_voice.write_bytes((source / 'archmage.md').read_bytes())

    linked_parent = root / 'skills/linked-parent'
    linked_parent.mkdir()
    (linked_parent / 'SKILL.md').write_text(original.format(name='linked-parent'))
    (linked_parent / 'references').symlink_to(external, target_is_directory=True)
    before = snapshot()
    run(success=False)
    assert snapshot() == before, 'parent symlink caused partial writes'
    shutil.rmtree(linked_parent)

    linked_skill = root / 'skills/linked-skill'
    linked_skill.symlink_to(root / 'skills/isolated', target_is_directory=True)
    before = snapshot()
    run(success=False)
    assert snapshot() == before, 'skill directory symlink caused partial writes'
    linked_skill.unlink()

    # A symlinked skills root is rejected before its contents are inspected.
    root_fixture = root / 'root-symlink-fixture'
    (root_fixture / 'scripts').mkdir(parents=True)
    shutil.copy2(root / 'scripts/sync-persona.sh', root_fixture / 'scripts/sync-persona.sh')
    (root_fixture / 'skills').symlink_to(external, target_is_directory=True)
    result = subprocess.run(['bash', str(root_fixture / 'scripts/sync-persona.sh')],
                            cwd=root_fixture, capture_output=True, text=True)
    assert result.returncode != 0
    assert outside_voice.read_bytes() == b'external voice\n'
    shutil.rmtree(outside_root)

print('persona synchronization fixtures: ok')
PY
