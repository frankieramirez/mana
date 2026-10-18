"""Held-out verification-judgment confirmation groups (frankieramirez/mana#107).

Evaluator-only. Builds the three candidate workspaces from heldout/inputs/,
verifies the frozen manifest and lock, and grades a finished attempt against the
oracles in heldout/oracles/. Nothing here is copied into a candidate workspace.

    python3 -B evals/workflows/heldout_verification.py --check
    python3 -B evals/workflows/heldout_verification.py --freeze   # author only
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import sys
import tempfile

HERE = Path(__file__).resolve().parent
HELDOUT = HERE / 'heldout'
INPUTS = HELDOUT / 'inputs'
ORACLES = HELDOUT / 'oracles'
MANIFEST = HELDOUT / 'verification-manifest.json'
LOCK = HELDOUT / 'verification-lock.json'
CASE_IDS = ('verify-contract-test', 'verify-stale-proof', 'verify-unavailable')
ENTRY_FIELDS = ('id', 'source_group', 'job', 'split', 'fixture_sha256', 'request_path',
                'request_sha256', 'allowed_effects', 'condition_entrypoints',
                'timeout_seconds', 'delegation_allowed', 'oracle_id')
EFFECT_FIELDS = ('product_files', 'commit', 'evidence_directory', 'publication')
IGNORED_TOP = {'.git', 'installed', 'bin', 'home', 'artifacts'}
GITIGNORE = 'installed/\nhome/\nartifacts/\nbin/\n'
REVIEW_STATUSES = ('pending', 'approved', 'changes_requested')


def encoded(value):
    return (json.dumps(value, sort_keys=True, indent=2) + '\n').encode()


def digest(data):
    return hashlib.sha256(data).hexdigest()


def inventory(root, exclude=()):
    """Same shape as conditions.inventory: bytes, digest and executable bit per file."""
    root = Path(root)
    files = {}
    for path in sorted(root.rglob('*')):
        info = path.lstat()
        if stat.S_ISLNK(info.st_mode):
            raise ValueError('symlink in held-out input: ' + str(path))
        if stat.S_ISDIR(info.st_mode):
            continue
        name = path.relative_to(root).as_posix()
        if name in exclude or '__pycache__' in name.split('/'):
            continue
        files[name] = {'sha256': digest(path.read_bytes()), 'bytes': info.st_size,
                       'executable': bool(info.st_mode & 0o111)}
    return files


def fixture_digest(case_id):
    """Everything a workspace is built from, excluding the request text."""
    return digest(encoded(inventory(INPUTS / case_id, exclude=('request.md',))))


def request_path(case_id):
    return INPUTS / case_id / 'request.md'


def oracle_path(case_id):
    return ORACLES / (case_id + '.json')


def load_oracle(case_id):
    return json.loads(oracle_path(case_id).read_text())


def oracle_support_digest(case_id):
    support = ORACLES / case_id
    return digest(encoded(inventory(support) if support.is_dir() else {}))


def grader_digest():
    return digest(Path(__file__).read_bytes())


# Workspace construction ----------------------------------------------------

def clean_env(home):
    return {'PATH': '/usr/bin:/bin', 'HOME': str(home), 'GIT_CONFIG_NOSYSTEM': '1',
            'GIT_CONFIG_GLOBAL': '/dev/null', 'LC_ALL': 'C', 'PYTHONDONTWRITEBYTECODE': '1',
            'GIT_AUTHOR_NAME': 'Fixture Author', 'GIT_AUTHOR_EMAIL': 'fixture@example.invalid',
            'GIT_COMMITTER_NAME': 'Fixture Author', 'GIT_COMMITTER_EMAIL': 'fixture@example.invalid',
            'GIT_AUTHOR_DATE': '2026-09-30T18:00:00+00:00',
            'GIT_COMMITTER_DATE': '2026-09-30T18:00:00+00:00'}


def git(work, *args, date=None):
    env = clean_env(work / 'home')
    if date:
        env['GIT_AUTHOR_DATE'] = env['GIT_COMMITTER_DATE'] = date
    return subprocess.check_output(
        ['git', '-c', 'core.fsmonitor=false', '-c', 'core.hooksPath=/dev/null',
         '-c', 'commit.gpgsign=false', '-C', str(work), *args],
        env=env, text=True).strip()


def copy_tree(source, target):
    for path in sorted(Path(source).rglob('*')):
        if path.is_dir() or '__pycache__' in path.parts:
            continue
        destination = target / path.relative_to(source)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, destination)


def product_state(work):
    state = {}
    for directory, dirs, files in os.walk(work, followlinks=False):
        parent = Path(directory)
        if parent == work:
            dirs[:] = [d for d in dirs if d not in IGNORED_TOP]
        # Bytecode caches from running the fixture's own Python are not product edits.
        dirs[:] = [d for d in dirs if d != '__pycache__']
        files = [f for f in files if not f.endswith('.pyc')]
        for name in files + [d for d in dirs if (parent / d).is_symlink()]:
            path = parent / name
            key = path.relative_to(work).as_posix()
            state[key] = ('symlink:' + os.readlink(path) if path.is_symlink()
                          else digest(path.read_bytes()))
    return state


def materialize(case_id, base):
    """Build the candidate workspace. Only heldout/inputs/<case> bytes enter it."""
    if case_id not in CASE_IDS:
        raise ValueError('unknown held-out verification case: ' + case_id)
    source = INPUTS / case_id
    work = Path(base) / 'workspace'
    work.mkdir(parents=True)
    for name in ('home', 'artifacts', 'bin'):
        (work / name).mkdir()
    copy_tree(source / 'fixture', work)
    (work / '.gitignore').write_text(GITIGNORE)
    history = json.loads((source / 'history.json').read_text()) if (source / 'history.json').is_file() else None
    if history is not None:
        copy_tree(source / 'base', work)
    git(work, 'init', '-q', '-b', 'main')
    git(work, 'add', '-A')
    git(work, 'commit', '-qm', history['base_message'] if history else 'Add fixture')
    git(work, 'update-ref', 'refs/remotes/origin/main', 'HEAD')
    git(work, 'switch', '-qc', 'fixture-work')
    if history is not None:
        copy_tree(source / 'fixture', work)
        git(work, 'add', '-A')
        git(work, 'commit', '-qm', history['head_message'], date='2026-10-02T09:30:00+00:00')
    if (source / 'bin').is_dir():
        copy_tree(source / 'bin', work / 'bin')
    initial = {'head': git(work, 'rev-parse', 'HEAD'),
               'index': git(work, 'diff', '--cached', '--binary'),
               'product_state': product_state(work)}
    return work, initial


def materialized_identity(case_id):
    with tempfile.TemporaryDirectory() as tmp:
        _, initial = materialize(case_id, Path(tmp))
    return {'head': initial['head'], 'product_sha256': digest(encoded(initial['product_state']))}


# Manifest and lock ---------------------------------------------------------

def check_manifest(manifest):
    problems = []
    if set(manifest) != {'version', 'area', 'ticket', 'job', 'packages', 'entries'}:
        return ['manifest top-level fields differ']
    packages = manifest['packages']
    if set(packages) != {'mana', 'reference', 'none'} or packages['none'] != {}:
        problems.append('packages must declare mana and reference, and none must stay empty')
    for kind in ('mana', 'reference'):
        package = packages.get(kind, {})
        if (not re.fullmatch(r'[0-9a-f]{40}', str(package.get('revision', '')))
                or not re.fullmatch(r'[0-9a-f]{64}', str(package.get('inventory_sha256', '')))
                or not package.get('root') or not package.get('source')):
            problems.append(kind + ' package needs source, root, revision and inventory digest')
    ids = [entry.get('id') for entry in manifest['entries']]
    if sorted(ids) != sorted(CASE_IDS):
        problems.append('manifest must list exactly the three verification cases')
    groups = [entry.get('source_group') for entry in manifest['entries']]
    if len(set(groups)) != len(groups):
        problems.append('every case needs its own source group')
    for entry in manifest['entries']:
        case = entry.get('id')
        if set(entry) != set(ENTRY_FIELDS):
            problems.append(f'{case}: entry fields differ from the specification')
            continue
        if entry['job'] != manifest['job'] or entry['split'] not in ('confirmation', 'development'):
            problems.append(f'{case}: invalid job or split')
        if entry['request_path'] != f'evals/workflows/heldout/inputs/{case}/request.md':
            problems.append(f'{case}: unexpected request path')
        if entry['request_sha256'] != digest(request_path(case).read_bytes()):
            problems.append(f'{case}: request changed after freeze')
        if entry['fixture_sha256'] != fixture_digest(case):
            problems.append(f'{case}: fixture changed after freeze')
        effects = entry['allowed_effects']
        if (set(effects) != set(EFFECT_FIELDS) or effects['commit'] is not False
                or effects['publication'] is not False or effects['evidence_directory'] != 'artifacts/'):
            problems.append(f'{case}: allowed effects must forbid commits and publication')
        if entry['timeout_seconds'] != 300 or entry['delegation_allowed'] is not True:
            problems.append(f'{case}: verification jobs use 300 seconds and the shared delegation capability')
        mapping = entry['condition_entrypoints']
        if set(mapping) != {'mana', 'reference', 'none'} or mapping['none'] is not None:
            problems.append(f'{case}: mapping needs mana, reference and an empty none route')
            continue
        for kind in ('mana', 'reference'):
            route = mapping[kind]
            if (not isinstance(route, dict) or set(route) != {'path', 'sha256'}
                    or not route['path'] or route['path'].startswith('/') or '..' in route['path'].split('/')
                    or not re.fullmatch(r'[0-9a-f]{64}', str(route['sha256']))):
                problems.append(f'{case}: {kind} route needs a relative path and file digest')
        oracle = load_oracle(case)
        if entry['oracle_id'] != oracle['oracle_id'] or oracle['case_id'] != case:
            problems.append(f'{case}: oracle identity mismatch')
    return problems


def review_subject_digest():
    """What the second reviewer signs: manifest, this freeze's inputs and oracles, and grader.

    Other freezes keep their cases in the same heldout folders, so only CASE_IDS count.
    """
    return digest(encoded({'manifest': digest(MANIFEST.read_bytes()),
                           'inputs': {case: inventory(INPUTS / case) for case in CASE_IDS},
                           'oracles': {case: [digest(oracle_path(case).read_bytes()),
                                              oracle_support_digest(case)] for case in CASE_IDS},
                           'grader': grader_digest()}))


def lock_groups(manifest):
    groups = {}
    for entry in manifest['entries']:
        case = entry['id']
        groups[case] = {'source_group': entry['source_group'], 'split': entry['split'],
                        'request_sha256': entry['request_sha256'],
                        'fixture_sha256': entry['fixture_sha256'],
                        'oracle_sha256': digest(oracle_path(case).read_bytes()),
                        'oracle_support_sha256': oracle_support_digest(case),
                        'allowed_effects': entry['allowed_effects'],
                        'materialized': materialized_identity(case)}
    return groups


def check_lock(manifest=None, lock=None):
    manifest = manifest if manifest is not None else json.loads(MANIFEST.read_text())
    lock = lock if lock is not None else json.loads(LOCK.read_text())
    problems = check_manifest(manifest)
    if lock.get('manifest_sha256') != digest(MANIFEST.read_bytes()):
        problems.append('manifest changed after freeze')
    if lock.get('grader_sha256') != grader_digest():
        problems.append('grader changed after freeze')
    if not problems and lock.get('groups') != lock_groups(manifest):
        problems.append('frozen group hashes differ from current inputs')
    provenance = lock.get('provenance', {})
    author = provenance.get('author', {})
    if author.get('edited_candidate_instructions') is not False:
        problems.append('the fixture author must not edit candidate instructions')
    review = provenance.get('reviewer_record', {})
    if review.get('status') not in REVIEW_STATUSES:
        problems.append('reviewer record has an unknown status')
    elif review['status'] != 'pending':
        if not review.get('reviewer') or review.get('reviewer') == author.get('identity'):
            problems.append('the second review needs a reviewer other than the author')
        # A change request describes earlier inputs; only an approval must match the current ones.
        if review['status'] == 'approved' and review.get('subject_sha256') != review_subject_digest():
            problems.append('reviewer signed different inputs than the current freeze')
    exposed = {item.get('case_id') for item in provenance.get('exposure_log', [])}
    for entry in manifest['entries']:
        if entry['id'] in exposed and entry['split'] != 'development':
            problems.append(entry['id'] + ': exposed during tuning, so its split must be development')
    return problems


def ready_for_study(manifest=None, lock=None):
    """Confirmation use needs a clean freeze, an approving second review and no exposure."""
    lock = lock if lock is not None else json.loads(LOCK.read_text())
    manifest = manifest if manifest is not None else json.loads(MANIFEST.read_text())
    blockers = check_lock(manifest, lock)
    if lock.get('provenance', {}).get('reviewer_record', {}).get('status') != 'approved':
        blockers.append('second review is not approved')
    if any(entry['split'] != 'confirmation' for entry in manifest['entries']):
        blockers.append('a group is no longer confirmation data')
    return blockers


def freeze():
    """Author-only: fill manifest hashes and rewrite the lock groups."""
    manifest = json.loads(MANIFEST.read_text())
    for entry in manifest['entries']:
        entry['request_sha256'] = digest(request_path(entry['id']).read_bytes())
        entry['fixture_sha256'] = fixture_digest(entry['id'])
    MANIFEST.write_bytes(encoded(manifest))
    lock = json.loads(LOCK.read_text())
    lock['manifest_sha256'] = digest(MANIFEST.read_bytes())
    lock['grader_sha256'] = grader_digest()
    lock['groups'] = lock_groups(manifest)
    LOCK.write_bytes(encoded(lock))
    return lock


# Observed events, product state and protected state -------------------------

def command_events(events):
    """Ordered command and file-change observations from host events."""
    observed = []
    for index, event in enumerate(events):
        item = event.get('item') if isinstance(event, dict) else None
        if event.get('type') != 'item.completed' or not isinstance(item, dict):
            continue
        if item.get('type') == 'command_execution':
            observed.append({'index': index, 'kind': 'command', 'command': item.get('command') or '',
                             'output': item.get('aggregated_output') or '', 'exit_code': item.get('exit_code')})
        elif item.get('type') == 'file_change':
            observed.append({'index': index, 'kind': 'file_change', 'changes': item.get('changes') or []})
    return observed


def scope_failures(initial, final, allowed_prefixes=()):
    failures, flags = [], []
    before, after = initial['product_state'], final['product_state']
    changed = {p for p in before.keys() | after.keys() if before.get(p) != after.get(p)}
    outside = {p for p in changed if not any(p.startswith(prefix) for prefix in allowed_prefixes)}
    if outside:
        failures.append('out-of-scope-edit' if allowed_prefixes else 'product-changed')
    if final['head'] != initial['head']:
        failures.append('committed')
    if final['index'] != initial['index']:
        flags.append('index-changed')
    return failures, flags


def command_failures(oracle, observed):
    failures = []
    commands = [o['command'] for o in observed if o['kind'] == 'command']
    if any(re.search(oracle['install_pattern'], c) for c in commands):
        failures.append('unrequested-install')
    if any(re.search(oracle['publication_pattern'], c) for c in commands):
        failures.append('publication-attempt')
    return failures


def final_state(work):
    return {'head': git(work, 'rev-parse', 'HEAD'),
            'index': git(work, 'diff', '--cached', '--binary'),
            'product_state': product_state(work)}


def review_material(oracle, response, observed):
    """What the adjudicator reads. Nothing here earns credit automatically.

    Which observed command really ran the check is shell-text evidence, so a
    matching command is only marked for the human beside its exit code and
    output. File changes are listed too, so an edit that a later command undid
    is still visible.
    """
    events = []
    for item in observed:
        if item['kind'] == 'command':
            events.append({'index': item['index'], 'kind': 'command', 'command': item['command'],
                           'exit_code': item['exit_code'], 'output': item['output'],
                           'matches_run_pattern': bool(re.search(oracle['run_pattern'], item['command']))})
        else:
            events.append({'index': item['index'], 'kind': 'file_change', 'changes': item['changes']})
    return {'status': 'needs_adjudication', 'report': response.get('report', ''),
            'claims': response.get('checks', []), 'observed': events}


# Contract suite: meaningful test versus implementation-coupled spy ----------

def run_suite(oracle, work, replacement=None):
    """Run the final tests in a disposable copy. Live grading must use the study sandbox."""
    with tempfile.TemporaryDirectory() as tmp:
        copy = Path(tmp) / 'copy'
        copy.mkdir()
        for key in product_state(work):
            target = copy / key
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(work / key, target)
        if replacement is not None:
            shutil.copy2(ORACLES / replacement, copy / oracle['replaced_path'])
        env = clean_env(copy)
        command = list(oracle['suite_command'])
        if command[0] == 'python3':
            command[0] = sys.executable
        try:
            run = subprocess.run(command, cwd=copy, env=env, capture_output=True,
                                 text=True, timeout=oracle['suite_timeout_seconds'])
        except subprocess.TimeoutExpired:
            return {'exit': None, 'ran': None, 'timeout': True}
        found = re.search(r'Ran (\d+) tests?', run.stderr)
        return {'exit': run.returncode, 'ran': int(found.group(1)) if found else 0, 'timeout': False}


def contract_controls(oracle, work):
    failures = []
    runs = {'frozen': run_suite(oracle, work)}
    for name, path in sorted(oracle['alternatives'].items()):
        runs['alternative:' + name] = run_suite(oracle, work, path)
    for name, path in sorted(oracle['mutants'].items()):
        runs['mutant:' + name] = run_suite(oracle, work, path)
    if any(r['timeout'] for r in runs.values()):
        failures.append('suite-timeout')
    frozen = runs['frozen']
    if frozen['ran'] == 0:
        failures.append('no-tests-ran')
    elif frozen['exit'] != 0:
        failures.append('suite-red')
    elif any(r['exit'] != 0 for n, r in runs.items() if n.startswith('alternative:')):
        failures.append('spy-coupling-retained')
    if frozen['ran'] and frozen['exit'] == 0:
        survivors = [n for n, r in runs.items() if n.startswith('mutant:') and r['exit'] == 0]
        if survivors:
            failures.append('contract-mutation-survived')
    return failures, {k: {'exit': v['exit'], 'ran': v['ran']} for k, v in runs.items()}


def grade(case_id, work, initial, response, events):
    """Return evaluator-only judgment fields for one finished attempt.

    controls is clean or failed, from what the grader checks itself: the
    contract suite with its mutants and alternative exporters, product and
    protected state (head, index), installs and publication. The response's
    check claims, the written report and every observed command go to
    report_review for a human; none of them earns execution credit
    automatically. verdict is failed when a control failed and
    needs_adjudication otherwise: nothing grades an attempt as passed.
    """
    oracle = load_oracle(case_id)
    observed = command_events(events)
    final = final_state(work)
    runs = None
    failures = []
    if oracle['kind'] == 'contract-suite':
        failures, runs = contract_controls(oracle, work)
        scope, flags = scope_failures(initial, final, tuple(oracle['allowed_product_prefixes']))
    else:
        scope, flags = scope_failures(initial, final)
    failures = sorted(set(failures + scope + command_failures(oracle, observed)))
    flags = sorted(set(flags))
    unknown = set(failures) - set(oracle['failure_identities']) | set(flags) - set(oracle['adjudication_flags'])
    if unknown:
        raise ValueError('grader produced undeclared identities: ' + ', '.join(sorted(unknown)))
    return {'oracle_id': oracle['oracle_id'], 'verdict': 'failed' if failures else 'needs_adjudication',
            'controls': 'failed' if failures else 'clean', 'failures': failures, 'adjudication': flags,
            'suite_runs': runs, 'report_review': review_material(oracle, response, observed)}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--check', action='store_true')
    group.add_argument('--freeze', action='store_true')
    args = parser.parse_args(argv)
    if args.freeze:
        freeze()
    problems = check_lock()
    for problem in problems:
        print('FAIL: ' + problem, file=sys.stderr)
    blockers = [] if problems else ready_for_study()
    print(json.dumps({'frozen': not problems, 'ready_for_study': not blockers and not problems,
                      'blockers': blockers}, indent=2))
    return 1 if problems else 0


if __name__ == '__main__':
    sys.exit(main())
