"""Frozen, opt-in conditions for the existing focused workflow runner."""
import hashlib
import json
from pathlib import Path, PurePosixPath
import random
import re
import shutil
import stat


KINDS = ('mana', 'reference', 'none')
GENERIC_FIXTURES = {'check', 'stale', 'dirty', 'injection', 'action'}
GENERIC_SKILLS = {'reveal', 'cast', 'scan'}
IDENTIFIER = re.compile(r'[a-z0-9][a-z0-9-]*')
DIGEST = re.compile(r'[0-9a-f]{64}')
INITIAL_FIELDS = ('head', 'index', 'check_hash', 'product_state')


def encoded(value):
    return (json.dumps(value, sort_keys=True, indent=2) + '\n').encode()


def digest(data):
    return hashlib.sha256(data).hexdigest()


def inventory(root):
    """Reject links/special files and retain every file byte and executable bit."""
    root = Path(root)
    if root.is_symlink() or not root.is_dir():
        raise ValueError('payload root must be a real directory')
    files = {}
    for path in sorted(root.rglob('*')):
        info = path.lstat()
        if stat.S_ISLNK(info.st_mode):
            raise ValueError('symlink in frozen input: ' + str(path))
        if stat.S_ISDIR(info.st_mode):
            continue
        if not stat.S_ISREG(info.st_mode):
            raise ValueError('special file in frozen input: ' + str(path))
        files[path.relative_to(root).as_posix()] = {
            'sha256': digest(path.read_bytes()), 'bytes': info.st_size,
            'executable': bool(info.st_mode & 0o111),
        }
    return files


def inventory_digest(root):
    return digest(encoded(inventory(root)))


def relative_file(root, name):
    if (not isinstance(name, str) or not name or '\\' in name
            or PurePosixPath(name).is_absolute()
            or any(p in ('', '.', '..') for p in name.split('/'))):
        raise ValueError('invalid relative entrypoint')
    path = root / name
    if not path.is_file() or path.is_symlink():
        raise ValueError('missing entrypoint: ' + name)
    return path


def keys(value, required, label):
    if not isinstance(value, dict) or set(value) != set(required):
        raise ValueError('invalid ' + label + ' fields')


def checked_manifest(data, cases, supported_hosts):
    keys(data, ('version', 'study', 'host', 'model', 'reasoning', 'seed',
                'repetitions', 'conditions', 'cases'), 'study manifest')
    if data['version'] != 1 or not isinstance(data['study'], str) or not IDENTIFIER.fullmatch(data['study']):
        raise ValueError('invalid study identity')
    if data['host'] not in supported_hosts:
        raise ValueError('unvalidated study host')
    if (not isinstance(data['model'], str) or not data['model'].strip()
            or data['reasoning'] not in ('low', 'medium', 'high')):
        raise ValueError('model and reasoning must be explicit')
    if type(data['seed']) is not int or type(data['repetitions']) is not int or not 1 <= data['repetitions'] <= 3:
        raise ValueError('invalid schedule controls')
    keys(data['conditions'], KINDS, 'conditions')
    if data['conditions']['none'] != {}:
        raise ValueError('no-suite condition cannot carry a payload')
    if not isinstance(data['cases'], list) or not 1 <= len(data['cases']) <= 12:
        raise ValueError('study needs 1..12 focused cases')
    if len(data['cases']) * len(KINDS) * data['repetitions'] > 72:
        raise ValueError('study exceeds 72 allocated parent invocations')
    by_id = {c['id']: c for c in cases}
    selected = []
    seen = set()
    for item in data['cases']:
        keys(item, ('id', 'source_group', 'split', 'request', 'timeout_seconds'), 'study case')
        case = by_id.get(item['id'])
        if case is None or item['id'] in seen:
            raise ValueError('unknown or duplicate focused case')
        if case['fixture'] not in GENERIC_FIXTURES or case['skill'] not in GENERIC_SKILLS:
            raise ValueError('case requires a suite-specific fixture or grader: ' + item['id'])
        if (not isinstance(item['source_group'], str) or not IDENTIFIER.fullmatch(item['source_group'])
                or item['split'] != 'development'):
            raise ValueError('existing cases are development sources only')
        if not isinstance(item['request'], str) or not item['request'].strip():
            raise ValueError('ordinary request is required for every condition')
        if type(item['timeout_seconds']) is not int or not 1 <= item['timeout_seconds'] <= 300:
            raise ValueError('focused condition timeout must be 1..300 seconds')
        frozen = dict(case)
        frozen['request'] = item['request']
        selected.append({'definition': frozen, 'source_group': item['source_group'],
                         'split': item['split'], 'timeout_seconds': item['timeout_seconds']})
        seen.add(item['id'])
    for kind in ('mana', 'reference'):
        condition = data['conditions'][kind]
        keys(condition, ('root', 'revision', 'inventory_sha256', 'entrypoints'), 'payload')
        if (not isinstance(condition['root'], str) or not Path(condition['root']).is_absolute()
                or not isinstance(condition['revision'], str) or not re.fullmatch(r'[0-9a-f]{40}', condition['revision'])
                or not isinstance(condition['inventory_sha256'], str)
                or not DIGEST.fullmatch(condition['inventory_sha256'])):
            raise ValueError('payload needs an absolute root, revision and expected inventory digest')
        keys(condition['entrypoints'], seen, 'condition entrypoints')
        root = Path(condition['root'])
        if inventory_digest(root) != condition['inventory_sha256']:
            raise ValueError('wrong or changed payload: ' + kind)
        for path in condition['entrypoints'].values():
            relative_file(root, path)
    return selected


def freeze(manifest_path, destination, cases, source_dir, source_names, supported_hosts, prepare_fixture):
    """Create once; controls are externally pinned and input content is rechecked."""
    data = json.loads(Path(manifest_path).read_text())
    selected = checked_manifest(data, cases, supported_hosts)
    destination = Path(destination)
    for condition in ('mana', 'reference'):
        if destination.resolve().is_relative_to(Path(data['conditions'][condition]['root']).resolve()):
            raise ValueError('frozen output cannot be inside a source payload')
    destination.mkdir(parents=False, exist_ok=False)
    (destination / 'results').mkdir()
    fixture_source = destination / 'fixture-source'
    fixture_source.mkdir()
    for item in selected:
        case_root = fixture_source / item['definition']['id']
        case_root.mkdir()
        empty_condition = {'kind': 'none', 'inventory': {}, 'entrypoint': None}
        work, baseline = prepare_fixture(item['definition'], case_root, condition=empty_condition)
        initial = case_root / 'initial-fixture'
        initial.mkdir()
        for name in baseline['product_state']:
            target = initial / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(work / name, target)
        shutil.copytree(work / 'bin', case_root / 'tool-source')
        shutil.rmtree(work)
        item['initial_state'] = {key: baseline[key] for key in INITIAL_FIELDS}
        item['initial_fixture_inventory'] = inventory(initial)
        item['tool_inventory'] = inventory(case_root / 'tool-source')
    payloads = destination / 'payloads'
    payloads.mkdir()
    conditions = {'none': {'inventory': {}, 'entrypoints': {}, 'revision': None}}
    for kind in ('mana', 'reference'):
        raw = data['conditions'][kind]
        target = payloads / kind
        shutil.copytree(raw['root'], target)
        files = inventory(target)
        if digest(encoded(files)) != raw['inventory_sha256']:
            raise ValueError('payload changed during freeze: ' + kind)
        conditions[kind] = {'inventory': files, 'entrypoints': raw['entrypoints'],
                            'revision': raw['revision']}
    source = destination / 'runner-source'
    source.mkdir()
    for name in sorted(set(source_names) | {'cases.json', 'response-schema.json', 'archive_delegated.py'}):
        shutil.copy2(source_dir / name, source / name)
        if name in source_names and digest((source / name).read_bytes()) != source_names[name]:
            raise ValueError('evaluator source changed during freeze: ' + name)
    rng = random.Random(data['seed'])
    schedule = []
    for item in sorted(selected, key=lambda c: c['definition']['id']):
        cells = [(kind, repetition) for kind in KINDS for repetition in range(1, data['repetitions'] + 1)]
        rng.shuffle(cells)
        for kind, repetition in cells:
            schedule.append({'slot': len(schedule) + 1, 'case': item['definition']['id'],
                             'condition': kind, 'repetition': repetition})
    (destination / 'schedule.json').write_bytes(encoded(schedule))
    controls = {k: data[k] for k in ('version', 'study', 'host', 'model', 'reasoning', 'seed', 'repetitions')}
    controls.update({'cases': selected, 'conditions': conditions, 'delegation': False,
                     'schedule_sha256': digest(encoded(schedule)),
                     'fixture_inventory': inventory(fixture_source),
                     'runner_inventory': inventory(source)})
    control_bytes = encoded(controls)
    (destination / 'controls.json').write_bytes(control_bytes)
    # Permissions discourage accidental edits; the external digest supplies the pin.
    for root in (payloads, source, fixture_source):
        for path in root.rglob('*'):
            if path.is_file():
                path.chmod(0o555 if path.stat().st_mode & 0o111 else 0o444)
        for path in sorted((p for p in root.rglob('*') if p.is_dir()), reverse=True):
            path.chmod(0o555)
        root.chmod(0o555)
    for name in ('controls.json', 'schedule.json'):
        (destination / name).chmod(0o444)
    return {'study': str(destination.resolve()), 'controls_sha256': digest(control_bytes),
            'parent_slots': len(schedule), 'agent_executed': False}


class FrozenStudy:
    def __init__(self, root, expected_digest, loaded_sources=None, source_dir=None):
        if Path(root).is_symlink():
            raise ValueError('study root cannot be a symlink')
        self.root = Path(root).resolve()
        self.expected_digest = expected_digest
        self.loaded_sources = loaded_sources
        self.source_dir = source_dir
        self.verify()

    def verify(self):
        if not isinstance(self.expected_digest, str) or not DIGEST.fullmatch(self.expected_digest):
            raise ValueError('an external controls SHA-256 pin is required')
        if self.root.is_symlink():
            raise ValueError('study root cannot be a symlink')
        control_path = self.root / 'controls.json'
        if control_path.is_symlink():
            raise ValueError('frozen controls changed')
        control_bytes = control_path.read_bytes()
        if digest(control_bytes) != self.expected_digest:
            raise ValueError('frozen controls changed')
        self.controls = json.loads(control_bytes)
        schedule_path = self.root / 'schedule.json'
        if schedule_path.is_symlink():
            raise ValueError('frozen schedule changed')
        schedule_bytes = schedule_path.read_bytes()
        if digest(schedule_bytes) != self.controls['schedule_sha256']:
            raise ValueError('frozen schedule changed')
        self.schedule = json.loads(schedule_bytes)
        for kind in ('mana', 'reference'):
            if inventory(self.root / 'payloads' / kind) != self.controls['conditions'][kind]['inventory']:
                raise ValueError('frozen payload changed: ' + kind)
        if inventory(self.root / 'runner-source') != self.controls['runner_inventory']:
            raise ValueError('frozen runner changed')
        if inventory(self.root / 'fixture-source') != self.controls['fixture_inventory']:
            raise ValueError('frozen fixtures changed')
        if self.loaded_sources is not None:
            for name, value in self.loaded_sources.items():
                if self.controls['runner_inventory'].get(name, {}).get('sha256') != value:
                    raise ValueError('running evaluator differs from frozen sources: ' + name)
                if self.source_dir is not None and digest((self.source_dir / name).read_bytes()) != value:
                    raise ValueError('active evaluator source changed: ' + name)
        return self

    def selection(self, slot):
        if type(slot) is not int or not 1 <= slot <= len(self.schedule):
            raise ValueError('invalid scheduled slot')
        cell = self.schedule[slot - 1]
        case = next(c for c in self.controls['cases'] if c['definition']['id'] == cell['case'])
        payload = self.controls['conditions'][cell['condition']]
        condition = {'kind': cell['condition'], 'root': self.root / 'payloads' / cell['condition'],
                     'inventory': payload['inventory'], 'revision': payload['revision'],
                     'entrypoint': payload['entrypoints'].get(cell['case'])}
        return cell, case, condition

    def claim(self, slot):
        self.verify()
        self.selection(slot)
        results = self.root / 'results'
        if results.is_symlink() or not results.is_dir():
            raise ValueError('invalid study results directory')
        lock = results / '.active'
        lock.mkdir()
        try:
            if (results / 'STOP.json').exists():
                raise ValueError('study stopped; record a separate follow-up study')
            for earlier in range(1, slot):
                if not (results / f'{earlier:03d}' / 'result.json').is_file():
                    raise ValueError('run the frozen schedule in order')
            out = results / f'{slot:03d}'
            out.mkdir()
            return out
        except Exception:
            lock.rmdir()
            raise

    def release(self):
        (self.root / 'results' / '.active').rmdir()

    def snapshot(self, out, condition):
        """Evaluator-only copies retain actual payload bytes, including binary files."""
        self.verify()
        for name in ('controls.json', 'schedule.json'):
            shutil.copy2(self.root / name, out / name)
        shutil.copytree(self.root / 'runner-source', out / 'runner-source')
        shutil.copytree(self.root / 'fixture-source', out / 'fixture-source')
        if condition['kind'] == 'none':
            (out / 'payload-source').mkdir()
        else:
            shutil.copytree(condition['root'], out / 'payload-source')
        if inventory(out / 'payload-source') != condition['inventory']:
            raise ValueError('attempt payload snapshot differs from frozen input')


def evaluation_metadata(study, slot):
    cell, case, condition = study.selection(slot)
    return {'schema_version': 1, 'study': study.controls['study'],
            'schedule_slot': slot, 'case_id': cell['case'], 'condition': cell['condition'],
            'repetition': cell['repetition'], 'source_group': case['source_group'],
            'split': case['split'], 'controls_sha256': study.expected_digest,
            'request_sha256': digest(case['definition']['request'].encode()),
            'case_definition_sha256': digest(encoded(case['definition'])),
            'payload_hashes': condition['inventory'],
            'runner_hashes': study.controls['runner_inventory'],
            'allowed_effects': case['definition']['allowed_effects'],
            'requested_model': study.controls['model'], 'actual_model': None,
            'timeout_seconds': case['timeout_seconds'], 'delegation_allowed': False,
            'retry_attempts': 0, 'human_review': {'active_seconds': None, 'censored': None},
            'judgments': [], 'regrades': []}


def parse_events(text):
    """A lost or malformed observation makes this attempt ungradeable."""
    events, failures = [], []
    for index, line in enumerate(text.splitlines(), 1):
        try:
            event = json.loads(line)
            if not isinstance(event, dict) or not isinstance(event.get('type'), str) or not event['type']:
                raise ValueError('missing event type')
            if event['type'].startswith('item.'):
                item = event.get('item')
                if not isinstance(item, dict) or not isinstance(item.get('type'), str):
                    raise ValueError('missing item type')
                if event['type'] == 'item.completed' and item['type'] == 'command_execution':
                    if (not isinstance(item.get('command'), str)
                            or not isinstance(item.get('aggregated_output'), str)
                            or type(item.get('exit_code')) is not int):
                        raise ValueError('incomplete command observation')
            if event['type'] == 'turn.completed':
                usage = event.get('usage')
                if (not isinstance(usage, dict)
                        or any(type(usage.get(key)) is not int or usage[key] < 0
                               for key in ('input_tokens', 'output_tokens'))):
                    raise ValueError('incomplete usage observation')
            events.append(event)
        except (ValueError, TypeError) as exc:
            failures.append(f'invalid event at line {index}: {exc}')
    return events, failures


def install(condition, destination):
    destination.mkdir(parents=True)
    if condition['kind'] == 'none':
        if condition['inventory'] or condition['entrypoint'] is not None:
            raise ValueError('no-suite condition carries instructions')
        return
    if condition['kind'] not in ('mana', 'reference'):
        raise ValueError('unknown execution condition')
    if inventory(condition['root']) != condition['inventory']:
        raise ValueError('payload changed before installation')
    relative_file(condition['root'], condition['entrypoint'])
    shutil.copytree(condition['root'], destination / 'payload')
    if inventory(destination / 'payload') != condition['inventory']:
        raise ValueError('installed payload does not match frozen inventory')


def prompt(case, work, condition):
    prefix = ''
    if condition['kind'] != 'none':
        prefix = 'Use the instructions at ' + str(work / 'installed' / 'payload' / condition['entrypoint']) + '.\n'
    return (prefix + case['request'] + '\n\nAll workspace files are synthetic fixtures. '
            'Do not delegate. Keep the normal report inside the response schema\'s report field. '
            'List checks actually attempted or left unverified in checks. '
            'Do not change fixture checks or installed instructions. Use artifacts/ for temporary evidence.')
