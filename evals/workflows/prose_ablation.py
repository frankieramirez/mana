#!/usr/bin/env python3
"""Frozen prose instruction-ablation payloads and their execution adapter.

Builds the current, narrowed and section-removed dispel payloads from one source,
verifies the committed copies, freezes a prose study and runs one allocated slot.
Every path except --live is offline and never invokes a model."""
import argparse
import difflib
import json
import os
from pathlib import Path, PurePosixPath
import random
import re
import shutil
import signal
import subprocess
import sys
import time

import conditions
import run

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
PAYLOAD_SET = HERE / 'prose-ablation'
BASELINE_REVISION = '9d1aa521974bc7c72bf9cdd676de18c09a036468'
SOURCE_PATH = 'skills/dispel'
# Byte identity of the audit baseline, so a shallow checkout still pins the current arm.
BASELINE_SHA256 = {'SKILL.md': '5af33a677f43a9874ba0ed9928cec49ea3f2afe81ac0f13d938493ba3a005ac7',
                   'references/archmage.md': '337e7dec905ac43d1fba6085fbdae67d3b02a2201bd18e99169433472efbeed6'}
ENTRYPOINT = 'SKILL.md'
ARMS = ('current-fidelity', 'scope-fidelity', 'section-removed')
CHANGED_ARMS = ARMS[1:]
EXPERIMENT = 'prose-fidelity-1'
SPLITS = ('development', 'confirmation')
# The exact candidate from docs/specs/instruction-ablations.md, one paragraph.
CANDIDATE = (
    "Preserve the source's task-relevant facts, conditions, quantifiers and uncertainty. "
    "Make the wording concrete only with details the source prose states. "
    "Preserve exempt text exactly; derive new claims from it only when the user explicitly requests interpretation. "
    "A missing reason or measurement stays missing. "
    "Removing filler must preserve a qualified claim that matters to the task. "
    "Before returning, compare every changed claim with its source and restore any lost condition or unsupported addition.")
SECTION_START = '## Fidelity\n'
SECTION_END = '## Positive rules\n'
SELF_CHECK = '## Self-check before returning\n'
NUMBERED = re.compile(r'\d+\. ')
RESERVED_NAMES = {'.git', '.gitignore', 'installed', 'artifacts', 'home', 'bin', 'AGENTS.md', 'CLAUDE.md',
                  ENTRYPOINT, 'references'}
# The same host surface the focused runner freezes; identical for every arm.
DISABLED_FEATURES = ('apps', 'plugins', 'remote_plugin', 'hooks', 'memories', 'multi_agent', 'multi_agent_v2',
                     'browser_use', 'browser_use_external', 'computer_use', 'image_generation', 'in_app_browser',
                     'workspace_dependencies', 'shell_snapshot', 'skill_mcp_dependency_install', 'goals')
PROMPT_TEMPLATE = ('Use the instructions at {entrypoint}.\n{request}\n\n'
                   'All workspace files are synthetic fixtures. Do not delegate. '
                   "Return only the finished prose in the response schema's rewrite field. "
                   'Leave workspace files and installed instructions unchanged. Use artifacts/ for temporary notes.')
DETERMINISTIC_CHECKS = ('protected-spans-exact', 'source-files-unchanged', 'workspace-unchanged', 'head-unchanged')
RESPONSE_SCHEMA = 'prose-response-schema.json'
SOURCE_NAMES = sorted(set(run.STUDY_SOURCES) | {'prose_ablation.py', RESPONSE_SCHEMA})


def text_digest(text):
    return conditions.digest(text.encode())


def read_text(path):
    return Path(path).read_bytes().decode('utf-8')


def write_text(path, text):
    Path(path).write_bytes(text.encode('utf-8'))


# Payload construction ------------------------------------------------------

def selected_regions(text):
    """Zero-based, half-open line ranges of the two blocks this experiment may change."""
    if not text.endswith('\n'):
        raise ValueError('source entrypoint must end with a newline')
    lines = text.splitlines(keepends=True)
    starts = [i for i, line in enumerate(lines) if line == SECTION_START]
    ends = [i for i, line in enumerate(lines) if line == SECTION_END]
    checks = [i for i, line in enumerate(lines) if line == SELF_CHECK]
    if len(starts) != 1 or len(ends) != 1 or len(checks) != 1 or not starts[0] < ends[0] < checks[0]:
        raise ValueError('source needs exactly one Fidelity section before Positive rules and Self-check')
    items = [i for i in range(checks[0], len(lines)) if lines[i].startswith('9. ')]
    if len(items) != 1 or any(NUMBERED.match(line) for line in lines[items[0] + 1:]):
        raise ValueError('source needs exactly one final self-check item 9')
    return {'fidelity_section': (starts[0], ends[0]), 'self_check_item_9': (items[0], items[0] + 1)}


def derive(text):
    """Return each arm's entrypoint text; everything outside the two blocks is copied."""
    lines = text.splitlines(keepends=True)
    regions = selected_regions(text)
    start, end = regions['fidelity_section']
    item, _ = regions['self_check_item_9']
    sections = {'current-fidelity': lines[start:end],
                'scope-fidelity': [SECTION_START, '\n', CANDIDATE + '\n', '\n'],
                'section-removed': []}
    items = {'current-fidelity': [lines[item]], 'scope-fidelity': [], 'section-removed': []}
    return {arm: ''.join(lines[:start] + sections[arm] + lines[end:item] + items[arm] + lines[item + 1:])
            for arm in ARMS}


def patch_text(current, changed):
    return ''.join(difflib.unified_diff(current.splitlines(keepends=True), changed.splitlines(keepends=True),
                                        'a/' + ENTRYPOINT, 'b/' + ENTRYPOINT))


def payload_record(source_dir, revision, arm_roots, patches):
    current = read_text(source_dir / ENTRYPOINT)
    regions = selected_regions(current)
    record = {'version': 1, 'experiment': EXPERIMENT, 'evaluation_only': True,
              'baseline_revision': revision, 'source_path': SOURCE_PATH, 'entrypoint': ENTRYPOINT,
              'source_inventory': conditions.inventory(source_dir),
              'candidate_text': CANDIDATE,
              'selected_regions': {name: {'first_line': a + 1, 'last_line': b}
                                   for name, (a, b) in regions.items()},
              'arms': {}}
    record['source_inventory_sha256'] = conditions.digest(conditions.encoded(record['source_inventory']))
    for arm in ARMS:
        files = conditions.inventory(arm_roots[arm])
        record['arms'][arm] = {'directory': 'payloads/' + arm, 'inventory': files,
                               'inventory_sha256': conditions.digest(conditions.encoded(files)),
                               'patch': None, 'patch_sha256': None}
        if arm in patches:
            record['arms'][arm].update(patch='patches/' + arm + '.patch',
                                       patch_sha256=text_digest(patches[arm]))
    return record


def outside_production(path):
    path = Path(path).resolve()
    for protected in (ROOT / 'skills', ROOT / 'agents', ROOT / 'output-styles'):
        if path == protected.resolve() or path.is_relative_to(protected.resolve()):
            raise ValueError('experimental payloads cannot be written under ' + str(protected))
    return path


def build_payloads(source_dir, destination, revision=BASELINE_REVISION):
    """Create a new payload set from a dispel source; the source is only read."""
    source_dir = Path(source_dir)
    destination = outside_production(destination)
    if not re.fullmatch(r'[0-9a-f]{40}', revision):
        raise ValueError('baseline revision must be a 40-hex commit')
    conditions.inventory(source_dir)
    current = read_text(source_dir / ENTRYPOINT)
    texts = derive(current)
    destination.mkdir(parents=False, exist_ok=False)
    roots = {}
    for arm in ARMS:
        roots[arm] = destination / 'payloads' / arm
        shutil.copytree(source_dir, roots[arm])
        write_text(roots[arm] / ENTRYPOINT, texts[arm])
    patches = {arm: patch_text(current, texts[arm]) for arm in CHANGED_ARMS}
    (destination / 'patches').mkdir()
    for arm, text in patches.items():
        write_text(destination / 'patches' / (arm + '.patch'), text)
    record = payload_record(source_dir, revision, roots, patches)
    (destination / 'payloads.json').write_bytes(conditions.encoded(record))
    return record


def load_payload_set(set_dir=PAYLOAD_SET):
    set_dir = Path(set_dir)
    raw = (set_dir / 'payloads.json').read_bytes()
    record = json.loads(raw)
    if (record.get('version') != 1 or record.get('experiment') != EXPERIMENT
            or record.get('evaluation_only') is not True or tuple(record.get('arms', ())) != ARMS
            or record.get('entrypoint') != ENTRYPOINT or record.get('candidate_text') != CANDIDATE):
        raise ValueError('invalid prose payload set')
    return record, conditions.digest(raw)


def verify_payload_set(set_dir=PAYLOAD_SET):
    """Recompute every inventory, arm and patch from the frozen current payload."""
    set_dir = Path(set_dir)
    record, set_digest = load_payload_set(set_dir)
    roots = {arm: set_dir / record['arms'][arm]['directory'] for arm in ARMS}
    for arm in ARMS:
        files = conditions.inventory(roots[arm])
        entry = record['arms'][arm]
        if files != entry['inventory'] or conditions.digest(conditions.encoded(files)) != entry['inventory_sha256']:
            raise ValueError('frozen payload changed: ' + arm)
    if record['arms']['current-fidelity']['inventory'] != record['source_inventory']:
        raise ValueError('current payload differs from the recorded source')
    if conditions.digest(conditions.encoded(record['source_inventory'])) != record['source_inventory_sha256']:
        raise ValueError('recorded source inventory digest is wrong')
    if {k: v['sha256'] for k, v in record['source_inventory'].items()} != BASELINE_SHA256:
        raise ValueError('current payload is not the audit baseline')
    current = read_text(roots['current-fidelity'] / ENTRYPOINT)
    texts = derive(current)
    regions = selected_regions(current)
    if record['selected_regions'] != {name: {'first_line': a + 1, 'last_line': b} for name, (a, b) in regions.items()}:
        raise ValueError('recorded selected regions are wrong')
    for arm in ARMS:
        if read_text(roots[arm] / ENTRYPOINT) != texts[arm]:
            raise ValueError('arm is not the exact derived payload: ' + arm)
        others = {k: v for k, v in record['arms'][arm]['inventory'].items() if k != ENTRYPOINT}
        if others != {k: v for k, v in record['source_inventory'].items() if k != ENTRYPOINT}:
            raise ValueError('supporting files differ between arms: ' + arm)
    for arm in ARMS:
        entry = record['arms'][arm]
        if arm == 'current-fidelity':
            if entry['patch'] is not None or entry['patch_sha256'] is not None:
                raise ValueError('current payload carries a patch')
            continue
        stored = read_text(set_dir / entry['patch'])
        if stored != patch_text(current, texts[arm]) or text_digest(stored) != entry['patch_sha256']:
            raise ValueError('stored patch is not the exact change: ' + arm)
    production = ROOT / record['source_path']
    drift = None
    if production.is_dir():
        drift = conditions.inventory(production) != record['source_inventory']
    return {'payload_set_sha256': set_digest, 'baseline_revision': record['baseline_revision'],
            'arms': {arm: record['arms'][arm]['inventory_sha256'] for arm in ARMS},
            'patches': {arm: record['arms'][arm]['patch_sha256'] for arm in CHANGED_ARMS},
            'production_differs_from_frozen_current': drift, 'agent_executed': False}


# Study manifest and freeze --------------------------------------------------

def safe_source_name(name):
    if (not isinstance(name, str) or not name or '\\' in name or PurePosixPath(name).is_absolute()
            or any(p in ('', '.', '..') or p.startswith('.') for p in name.split('/'))
            or name.split('/')[0] in RESERVED_NAMES):
        raise ValueError('invalid source file name: ' + repr(name))
    return name


def checked_study(data):
    conditions.keys(data, ('version', 'study', 'host', 'model', 'reasoning', 'seed', 'repetitions',
                           'payload_set', 'payload_set_sha256', 'cases'), 'prose study manifest')
    if data['version'] != 1 or not isinstance(data['study'], str) or not conditions.IDENTIFIER.fullmatch(data['study']):
        raise ValueError('invalid study identity')
    if data['host'] not in run.SUPPORTED_HOSTS:
        raise ValueError('unvalidated study host')
    if (not isinstance(data['model'], str) or not data['model'].strip()
            or data['reasoning'] != 'medium'):
        raise ValueError('model must be explicit and reasoning must be medium')
    if type(data['seed']) is not int or type(data['repetitions']) is not int or not 1 <= data['repetitions'] <= 3:
        raise ValueError('invalid schedule controls')
    if not isinstance(data['payload_set'], str) or not Path(data['payload_set']).is_absolute():
        raise ValueError('payload set needs an absolute path')
    verify_payload_set(data['payload_set'])
    _, set_digest = load_payload_set(data['payload_set'])
    if data['payload_set_sha256'] != set_digest:
        raise ValueError('wrong or changed payload set')
    if not isinstance(data['cases'], list) or not 1 <= len(data['cases']) <= 12:
        raise ValueError('study needs 1..12 prose cases')
    if len(data['cases']) * len(ARMS) * data['repetitions'] > 72:
        raise ValueError('study exceeds 72 allocated parent invocations')
    selected, seen = [], set()
    for item in data['cases']:
        conditions.keys(item, ('id', 'source_group', 'split', 'request', 'sources', 'protected_spans',
                               'timeout_seconds'), 'prose case')
        if not isinstance(item['id'], str) or not conditions.IDENTIFIER.fullmatch(item['id']) or item['id'] in seen:
            raise ValueError('invalid or duplicate prose case id')
        if not isinstance(item['source_group'], str) or not conditions.IDENTIFIER.fullmatch(item['source_group']):
            raise ValueError('invalid source group')
        if item['split'] not in SPLITS:
            raise ValueError('split must be development or confirmation')
        if not isinstance(item['request'], str) or not item['request'].strip():
            raise ValueError('ordinary request is required')
        sources = item['sources']
        if not isinstance(sources, dict) or not 1 <= len(sources) <= 8:
            raise ValueError('prose case needs 1..8 raw source files')
        for name, text in sources.items():
            safe_source_name(name)
            if not isinstance(text, str) or not text:
                raise ValueError('raw source must be non-empty text: ' + name)
        spans, span_ids = [], set()
        if not isinstance(item['protected_spans'], list):
            raise ValueError('protected spans must be a list')
        for span in item['protected_spans']:
            conditions.keys(span, ('id', 'file', 'text'), 'protected span')
            if (not isinstance(span['id'], str) or not conditions.IDENTIFIER.fullmatch(span['id'])
                    or span['id'] in span_ids):
                raise ValueError('invalid or duplicate protected span id')
            if span['file'] not in sources or not isinstance(span['text'], str) or not span['text']:
                raise ValueError('protected span must name a source file and text')
            offset = sources[span['file']].find(span['text'])
            if offset < 0:
                raise ValueError('protected span is not verbatim source text: ' + span['id'])
            spans.append({**span, 'offset': offset, 'sha256': text_digest(span['text'])})
            span_ids.add(span['id'])
        if type(item['timeout_seconds']) is not int or not 1 <= item['timeout_seconds'] <= 300:
            raise ValueError('prose timeout must be 1..300 seconds')
        selected.append({'id': item['id'], 'source_group': item['source_group'], 'split': item['split'],
                         'request': item['request'], 'request_sha256': text_digest(item['request']),
                         'protected_spans': spans, 'timeout_seconds': item['timeout_seconds'],
                         'source_files': sorted(sources)})
        seen.add(item['id'])
    return selected


def build_schedule(selected, seed, repetitions):
    """Shuffle case, arm and repetition cells within each source group, groups in sorted order."""
    rng = random.Random(seed)
    groups = {}
    for case in selected:
        groups.setdefault(case['source_group'], []).append(case['id'])
    schedule = []
    for group in sorted(groups):
        cells = [(case_id, arm, repetition) for case_id in sorted(groups[group])
                 for arm in ARMS for repetition in range(1, repetitions + 1)]
        rng.shuffle(cells)
        for case_id, arm, repetition in cells:
            schedule.append({'slot': len(schedule) + 1, 'case': case_id, 'source_group': group,
                             'condition': arm, 'repetition': repetition})
    return schedule


def shared_controls():
    """Everything an arm could differ by except its payload; one record covers all arms."""
    return {'prompt_template': PROMPT_TEMPLATE, 'entrypoint': ENTRYPOINT,
            'installed_location': 'installed/payload',
            'response_schema_sha256': run.file_hash(HERE / RESPONSE_SCHEMA),
            'deterministic_checks': list(DETERMINISTIC_CHECKS),
            'disabled_features': list(DISABLED_FEATURES), 'writable_workspace': False,
            'delegation': False, 'children': 0, 'retries': 0}


def lock_tree(root):
    for path in root.rglob('*'):
        if path.is_file():
            path.chmod(0o555 if path.stat().st_mode & 0o111 else 0o444)
    for path in sorted((p for p in root.rglob('*') if p.is_dir()), reverse=True):
        path.chmod(0o555)
    root.chmod(0o555)


def freeze_study(manifest_path, destination, loaded_sources=None):
    data = json.loads(read_text(manifest_path))
    selected = checked_study(data)
    payload_set = Path(data['payload_set'])
    destination = outside_production(destination)
    if destination.is_relative_to(payload_set.resolve()):
        raise ValueError('frozen output cannot be inside the payload set')
    record, set_digest = load_payload_set(payload_set)
    destination.mkdir(parents=False, exist_ok=False)
    (destination / 'results').mkdir()
    sources = destination / 'sources'
    sources.mkdir()
    raw_cases = {item['id']: item for item in data['cases']}
    for case in selected:
        for name, text in raw_cases[case['id']]['sources'].items():
            target = sources / case['id'] / name
            target.parent.mkdir(parents=True, exist_ok=True)
            write_text(target, text)
        case['source_inventory'] = conditions.inventory(sources / case['id'])
    payloads = destination / 'payloads'
    payloads.mkdir()
    arms = {}
    for arm in ARMS:
        shutil.copytree(payload_set / record['arms'][arm]['directory'], payloads / arm)
        files = conditions.inventory(payloads / arm)
        if files != record['arms'][arm]['inventory']:
            raise ValueError('payload changed during freeze: ' + arm)
        arms[arm] = {'inventory': files, 'inventory_sha256': record['arms'][arm]['inventory_sha256'],
                     'patch_sha256': record['arms'][arm]['patch_sha256'], 'entrypoint': ENTRYPOINT}
    shutil.copytree(payload_set / 'patches', destination / 'patches')
    runner = destination / 'runner-source'
    runner.mkdir()
    loaded = loaded_sources or LOADED_SOURCES
    for name in SOURCE_NAMES:
        (runner / name).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(HERE / name, runner / name)
        if name in loaded and conditions.digest((runner / name).read_bytes()) != loaded[name]:
            raise ValueError('evaluator source changed during freeze: ' + name)
    schedule = build_schedule(selected, data['seed'], data['repetitions'])
    (destination / 'schedule.json').write_bytes(conditions.encoded(schedule))
    controls = {k: data[k] for k in ('version', 'study', 'host', 'model', 'reasoning', 'seed', 'repetitions')}
    controls.update({'experiment': EXPERIMENT, 'baseline_revision': record['baseline_revision'],
                     'payload_set_sha256': set_digest, 'candidate_text': CANDIDATE,
                     'selected_regions': record['selected_regions'], 'conditions': arms,
                     'shared_controls': shared_controls(), 'cases': selected,
                     'schedule_sha256': conditions.digest(conditions.encoded(schedule)),
                     'sources_inventory': conditions.inventory(sources),
                     'patches_inventory': conditions.inventory(destination / 'patches'),
                     'runner_inventory': conditions.inventory(runner)})
    control_bytes = conditions.encoded(controls)
    (destination / 'controls.json').write_bytes(control_bytes)
    for root in (payloads, runner, sources, destination / 'patches'):
        lock_tree(root)
    for name in ('controls.json', 'schedule.json'):
        (destination / name).chmod(0o444)
    return {'study': str(destination), 'controls_sha256': conditions.digest(control_bytes),
            'parent_slots': len(schedule), 'agent_executed': False}


class ProseStudy(conditions.FrozenStudy):
    """Reuses the serial claim/release lock; verification covers prose inputs."""

    def verify(self):
        if not isinstance(self.expected_digest, str) or not conditions.DIGEST.fullmatch(self.expected_digest):
            raise ValueError('an external controls SHA-256 pin is required')
        for name in ('controls.json', 'schedule.json'):
            if self.root.is_symlink() or (self.root / name).is_symlink():
                raise ValueError('frozen ' + name + ' changed')
        control_bytes = (self.root / 'controls.json').read_bytes()
        if conditions.digest(control_bytes) != self.expected_digest:
            raise ValueError('frozen controls changed')
        self.controls = json.loads(control_bytes)
        schedule_bytes = (self.root / 'schedule.json').read_bytes()
        if conditions.digest(schedule_bytes) != self.controls['schedule_sha256']:
            raise ValueError('frozen schedule changed')
        self.schedule = json.loads(schedule_bytes)
        for arm in ARMS:
            if conditions.inventory(self.root / 'payloads' / arm) != self.controls['conditions'][arm]['inventory']:
                raise ValueError('frozen payload changed: ' + arm)
        for name, key in (('sources', 'sources_inventory'), ('patches', 'patches_inventory'),
                          ('runner-source', 'runner_inventory')):
            if conditions.inventory(self.root / name) != self.controls[key]:
                raise ValueError('frozen ' + name + ' changed')
        if self.loaded_sources is not None:
            for name, value in self.loaded_sources.items():
                if self.controls['runner_inventory'].get(name, {}).get('sha256') != value:
                    raise ValueError('running evaluator differs from frozen sources: ' + name)
                if self.source_dir is not None and conditions.digest((self.source_dir / name).read_bytes()) != value:
                    raise ValueError('active evaluator source changed: ' + name)
        return self

    def selection(self, slot):
        if type(slot) is not int or not 1 <= slot <= len(self.schedule):
            raise ValueError('invalid scheduled slot')
        cell = self.schedule[slot - 1]
        case = next(c for c in self.controls['cases'] if c['id'] == cell['case'])
        payload = self.controls['conditions'][cell['condition']]
        condition = {'kind': cell['condition'], 'root': self.root / 'payloads' / cell['condition'],
                     'inventory': payload['inventory'], 'entrypoint': ENTRYPOINT,
                     'patch_sha256': payload['patch_sha256']}
        return cell, case, condition

    def snapshot(self, out, case, condition):
        """Evaluator-only copies: raw source, protected spans, controls and actual payload bytes."""
        self.verify()
        for name in ('controls.json', 'schedule.json'):
            shutil.copy2(self.root / name, out / name)
        shutil.copytree(self.root / 'runner-source', out / 'runner-source')
        shutil.copytree(self.root / 'sources' / case['id'], out / 'raw-source')
        shutil.copytree(condition['root'], out / 'payload-source')
        (out / 'protected-spans.json').write_bytes(conditions.encoded(case['protected_spans']))
        if conditions.inventory(out / 'raw-source') != case['source_inventory']:
            raise ValueError('attempt raw source differs from frozen input')
        if conditions.inventory(out / 'payload-source') != condition['inventory']:
            raise ValueError('attempt payload snapshot differs from frozen input')


# Fixture, prompt and deterministic checks -----------------------------------

def prepare_workspace(raw_source, out, condition):
    """A Git workspace holding only the raw source; the payload installs read-only beside it."""
    work = out / 'workspace'
    work.mkdir()
    for name in ('home', 'artifacts', 'bin'):
        (work / name).mkdir()
    for path in sorted(raw_source.rglob('*')):
        if path.is_file():
            target = work / path.relative_to(raw_source)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(path.read_bytes())
    (work / '.gitignore').write_text('installed/\nhome/\nartifacts/\nbin/\n')
    run.git(work, 'init', '-q', '-b', 'main')
    run.git(work, 'config', 'user.name', 'Mana Fixture')
    run.git(work, 'config', 'user.email', 'fixture@example.invalid')
    run.git(work, 'add', '.')
    run.git(work, 'commit', '-qm', 'prose fixture base', deterministic=True)
    if conditions.inventory(condition['root']) != condition['inventory']:
        raise ValueError('payload changed before installation')
    conditions.relative_file(condition['root'], condition['entrypoint'])
    (work / 'installed').mkdir()
    shutil.copytree(condition['root'], work / 'installed' / 'payload')
    if conditions.inventory(work / 'installed' / 'payload') != condition['inventory']:
        raise ValueError('installed payload does not match frozen inventory')
    baseline = {'head': run.git(work, 'rev-parse', 'HEAD'), 'product_state': run.product_state(work)}
    return work, baseline


def prose_prompt(case, work):
    entry = work / 'installed' / 'payload' / ENTRYPOINT
    return PROMPT_TEMPLATE.format(entrypoint=entry, request=case['request'])


def protected_span_checks(case, rewrite):
    return [{'id': span['id'], 'file': span['file'], 'sha256': span['sha256'],
             'preserved': isinstance(rewrite, str) and span['text'] in rewrite}
            for span in case['protected_spans']]


def instruction_reads(events, payload_root):
    """Observed reads: exact complete retrievals plus every command that names a payload file."""
    metrics = run.context_metrics(events, payload_root, ENTRYPOINT)
    commands = run.command_events(events)
    named = {}
    for relative in conditions.inventory(payload_root):
        hits = [index for index, command in enumerate(commands, 1) if relative in command.get('command', '')]
        if hits:
            named[relative] = hits
    files = sorted(conditions.inventory(payload_root))
    return {'payload_files': files, 'full_reads': metrics['full_reads'],
            'commands_naming_file': named,
            'unobserved_files': [f for f in files if f not in metrics['full_reads'] and f not in named],
            'entry_bytes': metrics['entry_bytes'], 'unique_full_read_bytes': metrics['unique_full_read_bytes'],
            'total_full_read_bytes': metrics['total_full_read_bytes'],
            'limits': metrics['limits'] + ' A command naming a file is not proof that its output reached the model.'}


def scope_checks(work, baseline, raw_source):
    failures = []
    for path in sorted(raw_source.rglob('*')):
        if path.is_file():
            target = work / path.relative_to(raw_source)
            if not target.is_file() or target.read_bytes() != path.read_bytes():
                failures.append('source file changed: ' + path.relative_to(raw_source).as_posix())
    if run.product_state(work) != baseline['product_state']:
        failures.append('workspace changed outside artifacts/')
    if run.git(work, 'rev-parse', 'HEAD') != baseline['head']:
        failures.append('workspace HEAD changed')
    return failures


def evaluation_metadata(study, slot):
    cell, case, condition = study.selection(slot)
    return {'schema_version': 1, 'experiment': EXPERIMENT, 'study': study.controls['study'],
            'schedule_slot': slot, 'case_id': cell['case'], 'condition': cell['condition'],
            'repetition': cell['repetition'], 'source_group': case['source_group'], 'split': case['split'],
            'controls_sha256': study.expected_digest, 'request_sha256': case['request_sha256'],
            'source_inventory': case['source_inventory'],
            'protected_span_hashes': {s['id']: s['sha256'] for s in case['protected_spans']},
            'payload_set_sha256': study.controls['payload_set_sha256'],
            'payload_hashes': condition['inventory'], 'patch_sha256': condition['patch_sha256'],
            'runner_hashes': study.controls['runner_inventory'],
            'requested_model': study.controls['model'], 'actual_model': None,
            'timeout_seconds': case['timeout_seconds'], 'delegation_allowed': False, 'retry_attempts': 0,
            'fidelity_review': {'reviewers': [], 'adjudication': None, 'active_seconds': None},
            'judgments': [], 'regrades': []}


# Execution ------------------------------------------------------------------

def run_attempt(study, case, condition, out):
    result = {'case': case['id'], 'condition': condition['kind'], 'execution': 'setup_failed',
              'failures': [], 'deterministic_failures': [], 'live': True}
    started = time.monotonic()
    work = baseline = None
    try:
        executable = Path(shutil.which('codex') or '')
        if not executable.is_file():
            raise ValueError('Codex CLI is unavailable')
        executable = executable.resolve()
        version = subprocess.check_output([str(executable), '--version'], text=True).strip()
        result['host'] = version
        if version not in run.SUPPORTED_HOSTS or version != study.controls['host']:
            raise ValueError('unvalidated host or host differs from frozen controls: ' + version)
        work, baseline = prepare_workspace(out / 'raw-source', out, condition)
        result['baseline'] = baseline
        config = run.permission_config(work, executable, writable_workspace=False)
        result['isolation'] = run.preflight(work, executable, config, read_only_inputs=case['source_files'])
        config += [f'features.{feature}=false' for feature in DISABLED_FEATURES]
        config += ['features.skip_host_skill_discovery=true', 'web_search="disabled"',
                   'project_doc_max_bytes=0', 'mcp_servers={}',
                   f'model_reasoning_effort="{study.controls["reasoning"]}"',
                   'model=' + json.dumps(study.controls['model'])]
        command = [str(executable), 'exec', '--ignore-user-config', '--ignore-rules', '--ephemeral', '--json',
                   '--color', 'never', '-C', str(work), *run.config_args(config),
                   '--output-schema', str(HERE / RESPONSE_SCHEMA), '-o', str(out / 'response.json'), '-']
        result['command'] = command
        prompt = prose_prompt(case, work)
        write_text(out / 'prompt.txt', prompt)
        study.verify()
        with (out / 'events.jsonl').open('w') as stdout, (out / 'stderr.txt').open('w') as stderr:
            with subprocess.Popen(command, stdin=subprocess.PIPE, stdout=stdout, stderr=stderr, text=True,
                                  start_new_session=True) as process:
                try:
                    process.communicate(prompt, timeout=case['timeout_seconds'])
                    result['exit_code'] = process.returncode
                    result['execution'] = 'completed' if process.returncode == 0 else 'agent_failed'
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL)
                    process.communicate()
                    result['execution'] = 'timeout'
        events, event_failures = conditions.parse_events(read_text(out / 'events.jsonl'))
        if event_failures:
            result['failures'] += event_failures
            result['execution'] = 'collection_failed'
        result['commands'] = run.command_events(events)
        result['usage'] = [e for e in events if e.get('type') == 'turn.completed']
        reads = instruction_reads(events, work / 'installed' / 'payload')
        (out / 'instruction-reads.json').write_bytes(conditions.encoded(reads))
        result['instruction_reads'] = reads
        if result['execution'] == 'completed':
            if not result['usage']:
                result['failures'].append('missing turn usage events')
            response = json.loads(read_text(out / 'response.json'))
            if not isinstance(response, dict) or set(response) != {'rewrite'} or not isinstance(response['rewrite'], str):
                raise ValueError('response does not match the prose schema')
            write_text(out / 'final-output.md', response['rewrite'])
            result['protected_spans'] = protected_span_checks(case, response['rewrite'])
            result['deterministic_failures'] += ['protected span lost: ' + s['id']
                                                 for s in result['protected_spans'] if not s['preserved']]
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        result['failures'].append(str(exc))
        if result['execution'] == 'completed':
            result['execution'] = 'collection_failed'
    finally:
        try:
            study.verify()
        except (OSError, ValueError) as exc:
            result['failures'].append('frozen study invalid after invocation: ' + str(exc))
        if work is not None and baseline is not None:
            try:
                result['deterministic_failures'] += scope_checks(work, baseline, out / 'raw-source')
                result['final_status'] = run.git(work, 'status', '--porcelain')
            except (OSError, subprocess.SubprocessError) as exc:
                result['failures'].append('final state unavailable: ' + str(exc))
        result['seconds'] = round(time.monotonic() - started, 2)
    return result


def execute_slot(study, slot):
    """One explicit allocated slot; infrastructure failures stop the schedule, outcomes do not."""
    import archive_delegated
    out = study.claim(slot)
    cell, case, condition = study.selection(slot)
    metadata = evaluation_metadata(study, slot)
    result = {'case': cell['case'], 'condition': cell['condition'], 'execution': 'setup_failed',
              'failures': [], 'deterministic_failures': [], 'live': True}
    try:
        (out / 'evaluation.json').write_bytes(conditions.encoded(metadata))
        study.snapshot(out, case, condition)
        result = run_attempt(study, case, condition, out)
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        result['failures'].append('study attempt failed: ' + str(exc))
    finally:
        if result['failures'] and result['execution'] == 'completed':
            result['execution'] = 'collection_failed'
        completed = result['execution'] == 'completed'
        metadata.update({
            'execution_status': result['execution'],
            'task_outcome': (('failed' if result['deterministic_failures'] else 'passed-deterministic')
                             if completed else None),
            'deterministic_checks': {'protected_spans': result.get('protected_spans'),
                                     'failures': result['deterministic_failures'] if completed else None},
            'instruction_reads': result.get('instruction_reads'),
            'final_output_sha256': (conditions.digest((out / 'final-output.md').read_bytes())
                                    if (out / 'final-output.md').is_file() else None),
            'elapsed_seconds': result.get('seconds'),
            'observed_command_operations': len(result['commands']) if 'commands' in result else None,
            'usage': {'parent': result.get('usage'), 'children': None},
            'failures': result['failures']})
        stop = not completed or bool(result['failures'])
        try:
            (out / 'evaluation.json').write_bytes(conditions.encoded(metadata))
            (out / 'result.json').write_bytes(conditions.encoded(result))
            (out / 'artifact-index.json').write_bytes(conditions.encoded(conditions.inventory(out)))
            archive = archive_delegated.archive(out, out.with_suffix('.json.gz'))
            out.with_suffix('.archive.json').write_bytes(conditions.encoded(archive))
        except (OSError, ValueError) as exc:
            stop = True
            result['execution'] = 'collection_failed'
            result['failures'].append('archive failed: ' + str(exc))
            metadata.update({'execution_status': 'collection_failed', 'task_outcome': None,
                             'failures': result['failures']})
            metadata['deterministic_checks']['failures'] = None
            (out / 'evaluation.json').write_bytes(conditions.encoded(metadata))
            (out / 'result.json').write_bytes(conditions.encoded(result))
        if stop:
            (study.root / 'results' / 'STOP.json').write_bytes(conditions.encoded({
                'slot': slot, 'execution': result['execution'], 'failures': result['failures'],
                'reason': 'incomplete execution or containment, input or collection failure'}))
        study.release()
    passed = result['execution'] == 'completed' and not result['failures'] and not result['deterministic_failures']
    print(out)
    print(json.dumps({'execution': result['execution'], 'deterministic_passed': passed,
                      'failures': result['failures'] + result['deterministic_failures']}))
    return 0 if passed else 1


LOADED_SOURCES = {name: run.file_hash(HERE / name) for name in SOURCE_NAMES}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check-payloads', action='store_true', help='verify the frozen payload set; no agent')
    parser.add_argument('--build-payloads', type=Path, help='derive a new payload set from a dispel source; no agent')
    parser.add_argument('--revision', default=BASELINE_REVISION, help='source revision label for --build-payloads')
    parser.add_argument('--freeze-study', type=Path, help='validate and freeze a prose study manifest; no agent')
    parser.add_argument('--out', type=Path, help='new directory for --build-payloads or --freeze-study')
    parser.add_argument('--study', type=Path, help='frozen prose study')
    parser.add_argument('--controls-sha256', help='external digest printed by --freeze-study')
    parser.add_argument('--check', action='store_true', help='verify a frozen study; no agent')
    parser.add_argument('--live', action='store_true', help='invoke the frozen host for one slot')
    parser.add_argument('--slot', type=int, help='one allocated slot in the frozen schedule')
    args = parser.parse_args(argv)
    try:
        if args.build_payloads:
            if not args.out:
                raise ValueError('--build-payloads needs --out')
            record = build_payloads(args.build_payloads, args.out, args.revision)
            print(json.dumps({'arms': {a: record['arms'][a]['inventory_sha256'] for a in ARMS},
                              'agent_executed': False}, indent=2))
            return 0
        if args.freeze_study:
            if not args.out:
                raise ValueError('--freeze-study needs --out')
            print(json.dumps(freeze_study(args.freeze_study, args.out), indent=2))
            return 0
        if args.study:
            study = ProseStudy(args.study, args.controls_sha256, LOADED_SOURCES, HERE)
            if args.check and not args.live and args.slot is None:
                print(json.dumps({'study': study.controls['study'], 'parent_slots': len(study.schedule),
                                  'agent_executed': False}))
                return 0
            if not args.live or args.check or args.slot is None:
                raise ValueError('a frozen study needs either --check or --live with one --slot')
            return execute_slot(study, args.slot)
        if not args.check_payloads:
            raise ValueError('choose --check-payloads, --build-payloads, --freeze-study or --study')
        print(json.dumps(verify_payload_set(), indent=2))
        return 0
    except (OSError, ValueError) as exc:
        print('prose ablation: ' + str(exc), file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
