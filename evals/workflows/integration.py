"""Frozen controls for the paired project-control integration pilot, ticket 112.

Both arms install the same Mana payload and get the same request, host, model, reasoning,
tools, authority, prerequisites and timeout. Only the consumer fixture differs. Arm `control`
is the pinned consumer revision as committed. Arm `baseline` is the same tree with the declared
control paths removed and the declared baseline edits applied, which drop the root Control pointer
line and any other reference to the control. Three task families, two arms and two repetitions give
exactly 12 parent invocations, with no retries.

Both arms install the payload where the consumer installs its skills, replacing whatever copy the
pinned revision holds there, so an older installed copy cannot answer for the payload.

Fixtures carry no history from the consumer: each is one commit of the arm's tree plus the family's
setup, so the baseline arm cannot recover the control from an earlier commit.

The runtime is pinned too: the host binary, the Node install, the browser builds and a seeded npm
cache. `integration_run.py` installs dependencies offline from that cache and runs every attempt and
every no-model check inside the same host sandbox.

The consumer is private and Mana is public. The frozen study therefore lives outside this
checkout, and so does every request, oracle and setup patch. Only `summary()` output, which
holds counts, digests and the schedule, may be committed here. Freezing runs no agent.
"""
import argparse
import io
import json
import os
from pathlib import Path, PurePosixPath
import random
import re
import shutil
import stat
import subprocess
import sys
import tarfile
import tempfile

import conditions
import hosts

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
# Each family's owning workflow. The same entrypoint loads in both arms.
FAMILIES = {'vague-report': 'sift', 'feature-change': 'cast', 'review-claims': 'scan'}
ARMS = ('control', 'baseline')
REPETITIONS = 2
INVOCATIONS = len(FAMILIES) * len(ARMS) * REPETITIONS
MAX_TIMEOUT = 900
POINTER = re.compile(r'^Control:')
REVISION = re.compile(r'[0-9a-f]{40}')
FIXTURE_DATE = '2000-01-01T00:00:00+00:00'
# fold: amend into the pinned commit; commit: a commit of its own; worktree: an uncommitted edit, applied last.
SETUP_MODES = ('fold', 'commit', 'worktree')
RUNNER_SOURCES = ('integration.py', 'integration_run.py', 'conditions.py', 'hosts.py', 'delegation.py',
                  'process_family.py', 'archive_delegated.py', 'response-schema.json')
KEYS = ('version', 'study', 'host', 'model', 'reasoning', 'seed', 'repetitions', 'timeout_seconds',
        'budget', 'payload', 'consumer', 'runtime', 'families')
ENV_NAME = re.compile(r'[A-Za-z_][A-Za-z0-9_]*')
# The agent environment never carries a credential or a session handle.
FORBIDDEN_ENV = re.compile(r'^(GH_|GITHUB_|AWS_|CLOUDSDK_|GOOGLE_|OPENAI_|ANTHROPIC_|CODEX_|CLAUDE_)|TOKEN|SECRET|PASSWORD|KEY$', re.I)


def git_env():
    """Fixture Git ignores the operator's configuration, so prefixes and identities match on every machine."""
    env = {k: v for k, v in os.environ.items() if not k.startswith('GIT_')}
    env.update(GIT_CONFIG_NOSYSTEM='1', GIT_CONFIG_GLOBAL=os.devnull, LC_ALL='C',
               GIT_AUTHOR_NAME='Fixture', GIT_AUTHOR_EMAIL='fixture@example.invalid',
               GIT_COMMITTER_NAME='Fixture', GIT_COMMITTER_EMAIL='fixture@example.invalid',
               GIT_AUTHOR_DATE=FIXTURE_DATE, GIT_COMMITTER_DATE=FIXTURE_DATE)
    return env


def git(root, *args, binary=False):
    result = subprocess.run(['git', '-c', 'core.hooksPath=/dev/null', '-c', 'core.fsmonitor=false',
                             '-C', str(root), *args], capture_output=True, env=git_env(), timeout=300)
    if result.returncode:
        raise ValueError('git %s failed: %s' % (args[0], result.stderr.decode(errors='replace').strip()[-400:]))
    return result.stdout if binary else result.stdout.decode().strip()


def tree_inventory(root):
    """Like conditions.inventory, but a consumer tree may track relative symlinks that stay inside it."""
    root = Path(root)
    files = {}
    for path in sorted(root.rglob('*')):
        info = path.lstat()
        name = path.relative_to(root).as_posix()
        if stat.S_ISLNK(info.st_mode):
            target = os.readlink(path)
            if Path(target).is_absolute() or not (path.parent / target).resolve().is_relative_to(root.resolve()):
                raise ValueError('symlink leaves the tree: ' + name)
            files[name] = {'link': target}
        elif stat.S_ISREG(info.st_mode):
            files[name] = {'sha256': conditions.digest(path.read_bytes()), 'bytes': info.st_size,
                           'executable': bool(info.st_mode & 0o111)}
        elif not stat.S_ISDIR(info.st_mode):
            raise ValueError('special file in consumer tree: ' + name)
    return files


def writable(root):
    """Disposable copies keep only the executable bit Git records."""
    for path in [root, *root.rglob('*')]:
        if not path.is_symlink():
            path.chmod(0o755 if path.is_dir() or path.stat().st_mode & 0o111 else 0o644)


def outside(path, root, label):
    """Private inputs and outputs never sit inside the public checkout."""
    if Path(path).resolve().is_relative_to(Path(root).resolve()):
        raise ValueError(label + ' must be outside the Mana checkout')


def absolute_file(value, label):
    if not isinstance(value, str) or not Path(value).is_absolute() or not Path(value).is_file():
        raise ValueError(label + ' must be an absolute path to an existing file')
    return Path(value)


def relative_path(value, label):
    if (not isinstance(value, str) or not value or '\\' in value or PurePosixPath(value).is_absolute()
            or any(p in ('', '.', '..') for p in value.split('/'))):
        raise ValueError('invalid relative path in ' + label)
    return value


def checked_manifest(data, root=ROOT, evidence_dir=None):
    conditions.keys(data, KEYS, 'integration manifest')
    if data['version'] != 1 or not isinstance(data['study'], str) or not conditions.IDENTIFIER.fullmatch(data['study']):
        raise ValueError('invalid study identity')
    hosts.require(data['host'], 'focused', directory=evidence_dir)
    if (not isinstance(data['model'], str) or not data['model'].strip()
            or data['reasoning'] not in ('low', 'medium', 'high')):
        raise ValueError('model and reasoning must be explicit')
    if type(data['seed']) is not int or data['repetitions'] != REPETITIONS:
        raise ValueError('the pilot runs two repetitions with an explicit seed')
    if type(data['timeout_seconds']) is not int or not 1 <= data['timeout_seconds'] <= MAX_TIMEOUT:
        raise ValueError('timeout must be 1..%d seconds per invocation' % MAX_TIMEOUT)
    budget = data['budget']
    conditions.keys(budget, ('invocations', 'retries'), 'budget')
    if budget != {'invocations': INVOCATIONS, 'retries': 0}:
        raise ValueError('the budget is exactly %d invocations and no retries' % INVOCATIONS)
    payload = data['payload']
    conditions.keys(payload, ('root', 'revision', 'inventory_sha256'), 'payload')
    if (not isinstance(payload['root'], str) or not Path(payload['root']).is_absolute()
            or not isinstance(payload['revision'], str) or not REVISION.fullmatch(payload['revision'])
            or not isinstance(payload['inventory_sha256'], str)
            or not conditions.DIGEST.fullmatch(payload['inventory_sha256'])):
        raise ValueError('payload needs an absolute root, revision and expected inventory digest')
    if conditions.inventory_digest(payload['root']) != payload['inventory_sha256']:
        raise ValueError('wrong or changed payload')
    for skill in FAMILIES.values():
        conditions.relative_file(Path(payload['root']), skill + '/SKILL.md')
    consumer = data['consumer']
    conditions.keys(consumer, ('repository', 'revision', 'skills_dir', 'control_paths', 'pointer', 'baseline_edits',
                               'install', 'prerequisites'), 'consumer')
    relative_path(consumer['skills_dir'], 'skills_dir')
    if not isinstance(consumer['repository'], str) or not Path(consumer['repository']).is_absolute():
        raise ValueError('consumer repository must be an absolute path')
    outside(consumer['repository'], root, 'consumer repository')
    if not isinstance(consumer['revision'], str) or not REVISION.fullmatch(consumer['revision']):
        raise ValueError('consumer revision must be a full commit id')
    git(consumer['repository'], 'cat-file', '-e', consumer['revision'] + '^{commit}')
    if not isinstance(consumer['control_paths'], list) or not consumer['control_paths']:
        raise ValueError('declare the control paths the baseline arm removes')
    for path in consumer['control_paths']:
        relative_path(path, 'control_paths')
        if path == consumer['skills_dir'] or path.startswith(consumer['skills_dir'] + '/'):
            raise ValueError('the installed payload is the same in both arms; it cannot be a control path')
    if len(set(consumer['control_paths'])) != len(consumer['control_paths']):
        raise ValueError('duplicate control path')
    relative_path(consumer['pointer'], 'pointer')
    if consumer['pointer'] in consumer['control_paths']:
        raise ValueError('the pointer file stays in both arms; only its Control line is dropped')
    edits = consumer['baseline_edits']
    if not isinstance(edits, list) or not edits:
        raise ValueError('baseline edits must at least drop the Control pointer line')
    for edit in edits:
        conditions.keys(edit, ('path', 'old', 'new'), 'baseline edit')
        relative_path(edit['path'], 'baseline_edits')
        if (not isinstance(edit['old'], str) or not edit['old'] or not isinstance(edit['new'], str)
                or edit['old'] == edit['new'] or edit['path'] in consumer['control_paths']):
            raise ValueError('a baseline edit replaces text in a file both arms keep')
        if edit['path'] == consumer['skills_dir'] or edit['path'].startswith(consumer['skills_dir'] + '/'):
            raise ValueError('the installed payload is the same in both arms; a baseline edit cannot touch it')
    argv(consumer['install'], 'install')
    if (not isinstance(consumer['prerequisites'], list)
            or any(not isinstance(p, str) or not p.strip() for p in consumer['prerequisites'])):
        raise ValueError('prerequisites are a list of descriptions, identical for both arms')
    checked_runtime(data['runtime'], data['host'])
    families = data['families']
    if not isinstance(families, list) or sorted(f.get('id') for f in families if isinstance(f, dict)) != sorted(FAMILIES):
        raise ValueError('the pilot has exactly the families ' + ', '.join(sorted(FAMILIES)))
    for family in families:
        conditions.keys(family, ('id', 'source_group', 'request', 'attachments', 'oracle', 'commits', 'checks'), 'family')
        if not isinstance(family['checks'], list) or not family['checks']:
            raise ValueError('each family declares its no-model sandbox checks')
        for check in family['checks']:
            conditions.keys(check, ('arms', 'argv', 'exit'), 'sandbox check')
            argv(check['argv'], 'sandbox check')
            if (not isinstance(check['arms'], list) or not check['arms'] or not set(check['arms']) <= set(ARMS)
                    or type(check['exit']) is not int):
                raise ValueError('a sandbox check names its arms and expected exit')
        if not isinstance(family['source_group'], str) or not conditions.IDENTIFIER.fullmatch(family['source_group']):
            raise ValueError('invalid source group')
        for name in [family['request'], family['oracle']] + list(family['attachments'] or []):
            outside(absolute_file(name, family['id'] + ' input'), root, family['id'] + ' input')
        if not isinstance(family['attachments'], list) or not isinstance(family['commits'], list):
            raise ValueError('attachments and commits are lists')
        modes = []
        for commit in family['commits']:
            conditions.keys(commit, ('patch', 'mode', 'message'), 'setup step')
            outside(absolute_file(commit['patch'], 'setup patch'), root, 'setup patch')
            if commit['mode'] not in SETUP_MODES:
                raise ValueError('setup mode is one of ' + ', '.join(SETUP_MODES))
            if (commit['mode'] == 'commit') != (isinstance(commit['message'], str) and bool(commit['message'].strip())):
                raise ValueError('a setup commit needs a message, and only a commit has one')
            modes.append(SETUP_MODES.index(commit['mode']))
        if modes != sorted(modes):
            raise ValueError('setup steps run fold, then commit, then worktree')
    if len({f['source_group'] for f in families}) != len(families):
        raise ValueError('each family is its own source group')
    return data


def argv(value, label):
    if not isinstance(value, list) or not value or any(not isinstance(a, str) or not a for a in value):
        raise ValueError(label + ' is a non-empty argument list')
    return value


def checked_runtime(runtime, host):
    """The pinned host binary, Node install, browser builds and npm cache, the same for both arms."""
    conditions.keys(runtime, ('codex', 'node', 'browsers', 'npm_cache', 'env'), 'runtime')
    codex = Path(runtime['codex']) if isinstance(runtime['codex'], str) else None
    if codex is None or not codex.is_absolute() or not codex.is_file() or not os.access(codex, os.X_OK):
        raise ValueError('runtime codex must be an absolute path to the host executable')
    reported = subprocess.run([str(codex), '--version'], capture_output=True, text=True, timeout=20).stdout.strip()
    if reported != host:
        raise ValueError('runtime codex reports %r, not the study host' % reported)
    for key in ('node', 'browsers', 'npm_cache'):
        if not isinstance(runtime[key], str) or not Path(runtime[key]).is_absolute() or not Path(runtime[key]).is_dir():
            raise ValueError('runtime %s must be an absolute directory' % key)
    if not (Path(runtime['node']) / 'bin' / 'node').is_file():
        raise ValueError('runtime node must hold bin/node')
    if (not isinstance(runtime['env'], dict)
            or any(not ENV_NAME.fullmatch(k) or FORBIDDEN_ENV.search(k) or not isinstance(v, str)
                   for k, v in runtime['env'].items())):
        raise ValueError('runtime env holds plain names and string values and no credential')


def runtime_pins(runtime):
    """Byte identity of the runtime, checked again before every attempt."""
    node = Path(runtime['node']) / 'bin' / 'node'
    return {'codex_sha256': conditions.digest(Path(runtime['codex']).read_bytes()),
            'node_version': subprocess.run([str(node), '--version'], capture_output=True, text=True, timeout=20).stdout.strip(),
            'node_sha256': conditions.digest(node.read_bytes()),
            'browsers_sha256': conditions.digest(conditions.encoded(tree_inventory(runtime['browsers']))),
            'npm_cache_sha256': conditions.digest(conditions.encoded(tree_inventory(runtime['npm_cache'])))}


def schedule(seed):
    """Sorted family blocks; each block's arm/repetition cells are shuffled with one seeded generator."""
    rng = random.Random(seed)
    slots = []
    for family in sorted(FAMILIES):
        cells = [(arm, repetition) for arm in ARMS for repetition in range(1, REPETITIONS + 1)]
        rng.shuffle(cells)
        for arm, repetition in cells:
            slots.append({'slot': len(slots) + 1, 'family': family, 'arm': arm, 'repetition': repetition})
    return slots


def export(repository, revision, destination):
    """The committed tree at the pinned revision, never the operator's working copy."""
    archive = git(repository, 'archive', '--format=tar', revision, binary=True)
    destination.mkdir(parents=True)
    try:
        with tarfile.open(fileobj=io.BytesIO(archive)) as tar:
            tar.extractall(destination, filter='data')
    except tarfile.FilterError as exc:
        raise ValueError('symlink leaves the tree: %s' % exc.tarinfo.name)


def pointer_lines(text):
    return [i for i, line in enumerate(text.splitlines(True)) if POINTER.match(line)]


def derive_baseline(control, baseline, consumer):
    """Copy the control tree, drop the declared control paths and apply the baseline edits."""
    pointer = control / consumer['pointer']
    if not pointer.is_file():
        raise ValueError('pointer file is missing from the pinned revision')
    found = pointer_lines(pointer.read_text())
    if len(found) != 1:
        raise ValueError('the pinned pointer file must hold exactly one Control line, found %d' % len(found))
    for path in consumer['control_paths']:
        if not (control / path).exists():
            raise ValueError('declared control path is absent from the pinned revision: ' + path)
    shutil.copytree(control, baseline, symlinks=True)
    for path in consumer['control_paths']:
        target = baseline / path
        shutil.rmtree(target) if target.is_dir() else target.unlink()
    for edit in consumer['baseline_edits']:
        target = baseline / edit['path']
        text = target.read_text() if target.is_file() else ''
        if text.count(edit['old']) != 1:
            raise ValueError('a baseline edit must match exactly once in ' + edit['path'])
        target.write_text(text.replace(edit['old'], edit['new']))
    if pointer_lines((baseline / consumer['pointer']).read_text()):
        raise ValueError('the baseline pointer file still holds a Control line')


def arm_difference(control_inventory, baseline_inventory, consumer):
    """The arms may differ only in the declared paths and the pointer file."""
    removed = set(control_inventory) - set(baseline_inventory)
    declared = {name for name in control_inventory
                if any(name == p or name.startswith(p.rstrip('/') + '/') for p in consumer['control_paths'])}
    changed = {name for name in baseline_inventory if baseline_inventory[name] != control_inventory.get(name)}
    if removed != declared or changed != {edit['path'] for edit in consumer['baseline_edits']}:
        raise ValueError('arms differ beyond the declared control paths and baseline edits')
    return {'removed_files': len(removed), 'changed_files': len(changed)}


def build_fixture(tree, commits, destination):
    """A disposable Git checkout of one arm with the family's setup commits. Deterministic, so HEAD is reproducible."""
    shutil.copytree(tree, destination, symlinks=True)
    writable(destination)
    git(destination, 'init', '-q', '-b', 'main')
    git(destination, 'add', '-A')
    for commit in [c for c in commits if c['mode'] == 'fold']:
        git(destination, 'apply', '--index', '--whitespace=nowarn', str(commit['patch']))
    git(destination, 'commit', '-q', '--no-verify', '-m', 'Pinned consumer revision')
    for commit in commits:
        if commit['mode'] == 'commit':
            git(destination, 'apply', '--index', '--whitespace=nowarn', str(commit['patch']))
            git(destination, 'commit', '-q', '--no-verify', '-m', commit['message'])
        elif commit['mode'] == 'worktree':
            git(destination, 'apply', '--whitespace=nowarn', str(commit['patch']))
    status = git(destination, 'status', '--porcelain=v1', '-z', '--untracked-files=all', binary=True)
    return {'head': git(destination, 'rev-parse', 'HEAD'), 'commits': 1 + sum(c['mode'] == 'commit' for c in commits),
            'status_sha256': conditions.digest(status)}


def copy_input(source, destination):
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)
    return conditions.digest(destination.read_bytes())


def freeze(manifest_path, destination, root=ROOT, evidence_dir=None, source_dir=HERE):
    """Create once. Prints nothing private; the caller keeps the returned controls pin outside the study."""
    data = checked_manifest(json.loads(Path(manifest_path).read_text()), root, evidence_dir)
    final = Path(destination)
    outside(final, root, 'frozen study')
    outside(manifest_path, root, 'study manifest')
    if final.resolve().is_relative_to(Path(data['consumer']['repository']).resolve()):
        raise ValueError('frozen study cannot be inside the consumer checkout')
    if final.exists() or not final.parent.is_dir():
        raise ValueError('the frozen study needs a new directory in an existing parent')
    # Everything is built in a private sibling and renamed into place only when every check passed,
    # so a refused freeze leaves nothing behind and can be retried with the same destination.
    destination = Path(tempfile.mkdtemp(prefix='.' + final.name + '.partial-', dir=final.parent))
    try:
        result = build_study(data, destination, evidence_dir, source_dir)
        os.rename(destination, final)
        return result
    except BaseException:
        writable(destination)
        shutil.rmtree(destination, ignore_errors=True)
        raise


def build_study(data, destination, evidence_dir, source_dir):
    (destination / 'results').mkdir()
    consumer = data['consumer']
    arms = destination / 'arms'
    export(consumer['repository'], consumer['revision'], arms / 'control')
    installed = arms / 'control' / consumer['skills_dir']
    if installed.is_symlink() or (installed.exists() and not installed.is_dir()):
        raise ValueError('the skills directory must be a real directory or absent')
    replaced = len(tree_inventory(installed)) if installed.is_dir() else 0
    if installed.is_dir():
        shutil.rmtree(installed)
    shutil.copytree(data['payload']['root'], installed)
    derive_baseline(arms / 'control', arms / 'baseline', consumer)
    arm_inventory = {arm: tree_inventory(arms / arm) for arm in ARMS}
    difference = arm_difference(arm_inventory['control'], arm_inventory['baseline'], consumer)
    shutil.copytree(data['payload']['root'], destination / 'payload')
    payload_inventory = conditions.inventory(destination / 'payload')
    if conditions.digest(conditions.encoded(payload_inventory)) != data['payload']['inventory_sha256']:
        raise ValueError('payload changed during freeze')
    families = {}
    scratch = destination / 'scratch'
    for family in sorted(data['families'], key=lambda f: f['id']):
        base = destination / 'families' / family['id']
        frozen = {'id': family['id'], 'skill': FAMILIES[family['id']],
                  'entrypoint': consumer['skills_dir'] + '/' + FAMILIES[family['id']] + '/SKILL.md',
                  'source_group': family['source_group'],
                  'request_sha256': copy_input(family['request'], base / 'request.txt'),
                  'attachments': [], 'commits': []}
        for index, name in enumerate(family['attachments'], 1):
            target = 'attachments/%02d%s' % (index, Path(name).suffix.lower())
            frozen['attachments'].append({'path': target, 'sha256': copy_input(name, base / target)})
        frozen['oracle_sha256'] = copy_input(family['oracle'], destination / 'oracles' / (family['id'] + Path(family['oracle']).suffix.lower()))
        commits = []
        for index, commit in enumerate(family['commits'], 1):
            target = base / ('setup-%02d.patch' % index)
            frozen['commits'].append({'patch': target.name, 'mode': commit['mode'], 'message': commit['message'],
                                      'sha256': copy_input(commit['patch'], target)})
            commits.append({'patch': target, 'mode': commit['mode'], 'message': commit['message']})
        frozen['checks'] = family['checks']
        frozen['fixtures'] = {}
        for arm in ARMS:
            work = scratch / family['id'] / arm
            try:
                built = build_fixture(arms / arm, commits, work)
            except ValueError as exc:
                raise ValueError('%s setup does not apply to the %s arm: %s' % (family['id'], arm, exc))
            built['tree_inventory_sha256'] = conditions.digest(conditions.encoded(
                {k: v for k, v in tree_inventory(work).items() if not k.startswith('.git/')}))
            frozen['fixtures'][arm] = built
        families[family['id']] = frozen
    shutil.rmtree(scratch)
    source = destination / 'runner-source'
    source.mkdir()
    for name in RUNNER_SOURCES:
        shutil.copy2(Path(source_dir) / name, source / name)
    runtime = dict(data['runtime'], pins=runtime_pins(data['runtime']))
    shutil.copytree(Path(evidence_dir or source_dir / 'host-evidence'), source / 'host-evidence')
    slots = schedule(data['seed'])
    (destination / 'schedule.json').write_bytes(conditions.encoded(slots))
    controls = {key: data[key] for key in ('version', 'study', 'host', 'model', 'reasoning', 'seed', 'repetitions',
                                           'timeout_seconds', 'budget')}
    controls.update({
        'kind': 'paired-integration', 'children': 0, 'actual_model': None,
        'payload': {'revision': data['payload']['revision'], 'inventory': payload_inventory},
        'consumer': {'revision': consumer['revision'], 'pointer': consumer['pointer'],
                     'skills_dir': consumer['skills_dir'], 'replaced_skill_files': replaced,
                     'control_paths': consumer['control_paths'], 'baseline_edits': consumer['baseline_edits'],
                     'install': consumer['install'], 'prerequisites': consumer['prerequisites'],
                     'arm_difference': difference},
        'runtime': runtime,
        'arms': {arm: {'inventory': arm_inventory[arm]} for arm in ARMS},
        'families': families, 'schedule_sha256': conditions.digest(conditions.encoded(slots)),
        'family_inventory': conditions.inventory(destination / 'families'),
        'oracle_inventory': conditions.inventory(destination / 'oracles'),
        'runner_inventory': conditions.inventory(source),
    })
    control_bytes = conditions.encoded(controls)
    (destination / 'controls.json').write_bytes(control_bytes)
    for tree in (arms, destination / 'payload', destination / 'families', destination / 'oracles', source):
        for path in tree.rglob('*'):
            if path.is_file() and not path.is_symlink():
                path.chmod(0o555 if path.stat().st_mode & 0o111 else 0o444)
        for path in sorted((p for p in tree.rglob('*') if p.is_dir() and not p.is_symlink()), reverse=True):
            path.chmod(0o555)
        tree.chmod(0o555)
    for name in ('controls.json', 'schedule.json'):
        (destination / name).chmod(0o444)
    return {'study': data['study'], 'controls_sha256': conditions.digest(control_bytes),
            'parent_slots': len(slots), 'agent_executed': False}


class FrozenIntegration:
    def __init__(self, root, expected_digest):
        self.root = Path(root).resolve()
        self.expected_digest = expected_digest
        self.verify()

    def verify(self):
        if not isinstance(self.expected_digest, str) or not conditions.DIGEST.fullmatch(self.expected_digest):
            raise ValueError('an external controls SHA-256 pin is required')
        control_bytes = (self.root / 'controls.json').read_bytes()
        if conditions.digest(control_bytes) != self.expected_digest:
            raise ValueError('frozen controls changed')
        self.controls = json.loads(control_bytes)
        schedule_bytes = (self.root / 'schedule.json').read_bytes()
        if conditions.digest(schedule_bytes) != self.controls['schedule_sha256']:
            raise ValueError('frozen schedule changed')
        self.schedule = json.loads(schedule_bytes)
        for arm in ARMS:
            if tree_inventory(self.root / 'arms' / arm) != self.controls['arms'][arm]['inventory']:
                raise ValueError('frozen arm changed: ' + arm)
        checks = (('payload', self.controls['payload']['inventory']), ('families', self.controls['family_inventory']),
                  ('oracles', self.controls['oracle_inventory']), ('runner-source', self.controls['runner_inventory']))
        for name, expected in checks:
            if conditions.inventory(self.root / name) != expected:
                raise ValueError('frozen %s changed' % name)
        return self

    def runtime(self):
        """Fail when the host binary, Node, the browsers or the npm cache changed since the freeze."""
        runtime = self.controls['runtime']
        if runtime_pins(runtime) != runtime['pins']:
            raise ValueError('pinned runtime changed since the freeze')
        return runtime

    def claim(self, slot):
        """Serial, in schedule order, once per slot, and never after a stop."""
        self.verify()
        if type(slot) is not int or not 1 <= slot <= len(self.schedule):
            raise ValueError('invalid scheduled slot')
        results = self.root / 'results'
        lock = results / '.active'
        lock.mkdir()
        try:
            if (results / 'STOP.json').exists():
                raise ValueError('study stopped; a follow-up needs its own freeze')
            for earlier in range(1, slot):
                if not (results / ('%03d' % earlier) / 'result.json').is_file():
                    raise ValueError('run the frozen schedule in order')
            out = results / ('%03d' % slot)
            out.mkdir()
            return out
        except BaseException:
            lock.rmdir()
            raise

    def release(self):
        (self.root / 'results' / '.active').rmdir()

    def fixture(self, slot, destination):
        """Rebuild one slot's disposable checkout and prove it matches the frozen HEAD and tree."""
        self.verify()
        cell = self.schedule[slot - 1]
        family = self.controls['families'][cell['family']]
        base = self.root / 'families' / family['id']
        commits = [{'patch': base / c['patch'], 'mode': c['mode'], 'message': c['message']} for c in family['commits']]
        built = build_fixture(self.root / 'arms' / cell['arm'], commits, Path(destination))
        expected = family['fixtures'][cell['arm']]
        if (built['head'], built['status_sha256']) != (expected['head'], expected['status_sha256']):
            raise ValueError('rebuilt fixture differs from the frozen fixture')
        return cell, built


def summary(study):
    """Counts, digests and the schedule only: no paths, names, request text or consumer bytes."""
    c = study.controls
    arms = {arm: {'files': len(c['arms'][arm]['inventory']),
                  'inventory_sha256': conditions.digest(conditions.encoded(c['arms'][arm]['inventory']))} for arm in ARMS}
    families = {}
    for family_id, family in sorted(c['families'].items()):
        families[family_id] = {
            'skill': family['skill'], 'request_sha256': family['request_sha256'],
            'oracle_sha256': family['oracle_sha256'],
            'attachments_sha256': [a['sha256'] for a in family['attachments']],
            'setup_patches_sha256': [s['sha256'] for s in family['commits']],
            'setup_modes': [s['mode'] for s in family['commits']],
            'sandbox_checks': [{'arms': k['arms'], 'exit': k['exit']} for k in family['checks']],
            'fixtures': {arm: {'head': f['head'], 'commits': f['commits'], 'status_sha256': f['status_sha256'],
                               'tree_inventory_sha256': f['tree_inventory_sha256']}
                         for arm, f in family['fixtures'].items()}}
    return {'schema_version': 1, 'study': c['study'], 'kind': c['kind'], 'controls_sha256': study.expected_digest,
            'host': c['host'], 'requested_model': c['model'], 'actual_model': None, 'reasoning': c['reasoning'],
            'seed': c['seed'], 'repetitions': c['repetitions'], 'timeout_seconds': c['timeout_seconds'],
            'budget': c['budget'], 'children': c['children'], 'schedule': study.schedule,
            'payload': {'revision': c['payload']['revision'],
                        'inventory_sha256': conditions.digest(conditions.encoded(c['payload']['inventory']))},
            'runtime': {'codex_sha256': c['runtime']['pins']['codex_sha256'], 'node_version': c['runtime']['pins']['node_version'],
                        'browsers_sha256': c['runtime']['pins']['browsers_sha256'],
                        'npm_cache_sha256': c['runtime']['pins']['npm_cache_sha256'],
                        'network': 'host proxy, loopback binding only, no allowed domains'},
            'consumer': {'revision': c['consumer']['revision'], 'control_paths': len(c['consumer']['control_paths']),
                         'replaced_skill_files': c['consumer']['replaced_skill_files'],
                         'baseline_edits': len(c['consumer']['baseline_edits']),
                         'prerequisites': len(c['consumer']['prerequisites']),
                         'arm_difference': c['consumer']['arm_difference']},
            'arms': arms, 'families': families,
            'runner_inventory_sha256': conditions.digest(conditions.encoded(c['runner_inventory'])),
            'agent_executed': False}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument('--freeze', type=Path, metavar='MANIFEST', help='freeze a private manifest into --out; no agent')
    action.add_argument('--check', type=Path, metavar='STUDY', help='verify a frozen study against --controls-sha256')
    action.add_argument('--summary', type=Path, metavar='STUDY', help='print the public summary of a verified study')
    parser.add_argument('--out', type=Path)
    parser.add_argument('--controls-sha256')
    args = parser.parse_args(argv)
    try:
        if args.freeze:
            if not args.out:
                parser.error('--freeze needs --out outside the Mana checkout')
            result = freeze(args.freeze, args.out)
        else:
            study = FrozenIntegration(args.check or args.summary, args.controls_sha256)
            result = summary(study) if args.summary else {'study': study.controls['study'], 'verified': True,
                                                           'parent_slots': len(study.schedule)}
    except (OSError, ValueError, KeyError) as exc:
        print('integration: ' + str(exc), file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == '__main__':
    sys.exit(main())
