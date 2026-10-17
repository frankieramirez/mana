#!/usr/bin/env python3
"""Blinded review packets, independent judgments and append-only regrades for sealed attempts.

Reviewer packets carry the task contract, source, diff, observed commands, check
outcomes, child artifacts and final message. Condition names, instruction
contents and evaluator metadata stay in a restricted directory, together with a
record of what masking could not hide. Judgments and regrades are separate
write-once records in a hash-chained ledger; originals are never rewritten.
Nothing here invokes a model or infers human time.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import random
import re
import secrets
import sys

import attempts
import conditions

INITIAL_CAP_SECONDS = 600
MIN_SEGMENT = 16
ANCHOR = 8
REVIEWER = re.compile(r'[A-Za-z0-9][A-Za-z0-9._-]{0,63}')
PRODUCT_IGNORED = {'.git', 'installed', 'bin', 'home', 'artifacts'}
CHILD_SOURCES = ('threads.json', 'attributed-events.jsonl', 'children')
WITHHELD = [
    'condition name and installed instruction payload',
    'instruction file contents and paths, replaced by placeholders',
    'invocation prompt, which names the instruction entrypoint',
    'schedule slot, repetition and source group',
    'automatic grader verdict and failures',
    'payload inventories, revisions and evaluator metadata',
]
GENERIC_LIMITS = [
    'Report wording, structure and workflow-specific artifact formats can still identify a suite; they are not rewritten.',
    'The ordinary words "reference" and "none" are left as written.',
    'Instruction lines shorter than 16 characters are not masked.',
]


def digest(data):
    return hashlib.sha256(data).hexdigest()


def encoded(value):
    return attempts.encoded(value)


def source_hash():
    return digest(Path(__file__).read_bytes())


class Masker:
    """Replace instruction text, instruction paths and suite identifiers from every condition."""

    def __init__(self, study, extra_terms=()):
        self.segments = {}
        self.binary = set()
        self.paths = []
        revisions = []
        root_names = set()
        # Bare names also used by a fixture stay readable; the fixture file is identical across conditions.
        fixture_names = {p.name for p in (study.root / 'fixture-source').rglob('*')}
        for kind in ('mana', 'reference'):
            root = study.root / 'payloads' / kind
            payload = study.controls['conditions'][kind]
            if payload.get('revision'):
                revisions.append(payload['revision'])
            revisions.append(digest(encoded(payload['inventory'])))
            self.paths.append((str(root), '<instructions>'))
            for relative, info in payload['inventory'].items():
                self.binary.add(info['sha256'])
                if '/' in relative:
                    self.paths.append((relative, '<instruction-file>'))
                elif relative not in fixture_names:
                    root_names.add(relative)
                try:
                    text = (root / relative).read_text(encoding='utf-8')
                except UnicodeError:
                    continue
                for line in text.splitlines():
                    for part in [line.strip()] + [p.strip() for p in line.split('. ')]:
                        if len(part) >= MIN_SEGMENT:
                            self.segments.setdefault(part[:ANCHOR], set()).add(part)
        self.paths.append((str(study.root), '<study>'))
        terms = ['mana'] + [t for t in extra_terms if t.strip()]
        self.terms = re.compile(r'(?i)(?<![A-Za-z0-9])(' + '|'.join(re.escape(t) for t in terms) + r')(?![A-Za-z0-9])')
        self.binary_terms = re.compile(b'(?i)' + b'|'.join(re.escape(t.encode()) for t in terms))
        self.root_names = (re.compile(r'(?<![\w./-])(' + '|'.join(re.escape(n) for n in sorted(root_names, key=len, reverse=True))
                                      + r')(?![\w-])') if root_names else None)
        self.revisions = re.compile('|'.join(re.escape(r) for r in revisions)) if revisions else None

    def instruction_spans(self, text):
        spans = []
        index = 0
        while index <= len(text) - MIN_SEGMENT:
            best = None
            for segment in self.segments.get(text[index:index + ANCHOR], ()):
                if text.startswith(segment, index) and (best is None or len(segment) > len(best)):
                    best = segment
            if best:
                spans.append((index, index + len(best)))
                index += len(best)
            else:
                index += 1
        return spans

    def mask(self, text, attempt_paths=()):
        hits = set()
        spans = self.instruction_spans(text)
        if spans:
            hits.add('instruction_content')
            pieces, last = [], 0
            for start, end in spans:
                pieces += [text[last:start], '[instruction text withheld]']
                last = end
            text = ''.join(pieces + [text[last:]])
        replacements = list(attempt_paths) + self.paths + [('installed/payload', '<instructions>')]
        for old, new in sorted(replacements, key=lambda pair: -len(pair[0])):
            if old and old in text:
                if new in ('<instructions>', '<instruction-file>'):
                    hits.add('instruction_path')
                text = text.replace(old, new)
        # A file name under an instruction root can name the suite's workflow.
        text = re.sub(r'<instructions>/[^\s\'"`)\]]+', '<instructions>/<instruction-file>', text)
        if self.root_names is not None and self.root_names.search(text):
            hits.add('instruction_path')
            text = self.root_names.sub('<instruction-file>', text)
        if self.revisions is not None and self.revisions.search(text):
            hits.add('revision')
            text = self.revisions.sub('<revision>', text)
        if self.terms.search(text):
            hits.add('suite_term')
            text = self.terms.sub('<suite>', text)
        return text, hits

    def residual(self, text):
        return bool(self.instruction_spans(text) or self.terms.search(text)
                    or (self.revisions is not None and self.revisions.search(text)))


def _mask_value(value, mask):
    if isinstance(value, str):
        return mask(value)
    if isinstance(value, list):
        return [_mask_value(v, mask) for v in value]
    if isinstance(value, dict):
        return {mask(k): _mask_value(v, mask) for k, v in value.items()}
    return value


def _walk(root, top_ignored=()):
    files = []
    if not root.is_dir() or root.is_symlink():
        return files
    for directory, dirs, names in os.walk(root, followlinks=False):
        parent = Path(directory)
        if parent == root:
            dirs[:] = [d for d in dirs if d not in top_ignored]
        dirs.sort()
        for name in sorted(names) + [d for d in dirs if (parent / d).is_symlink()]:
            files.append(parent / name)
    return files


def _read_json(path):
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError, UnicodeError):
        return None


class PacketWriter:
    def __init__(self, directory, masker, attempt_paths):
        self.directory = directory
        self.masker = masker
        self.attempt_paths = attempt_paths
        self.files = {}
        self.hits = set()
        self.limits = []
        self.withheld = []

    def text(self, value):
        masked, hits = self.masker.mask(value, self.attempt_paths)
        self.hits |= hits
        return masked

    def put_bytes(self, relative, data):
        target = self.directory / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        self.files[relative] = digest(data)

    def put_json(self, relative, value):
        self.put_bytes(relative, encoded(_mask_value(value, self.text)))

    def put_file(self, relative, source):
        if source.is_symlink():
            self.put_bytes(relative + '.symlink.txt', ('symbolic link to ' + self.text(os.readlink(source)) + '\n').encode())
            return
        try:
            data = source.read_bytes()
        except OSError:
            self.withheld.append(relative + ' (unreadable)')
            return
        try:
            self.put_bytes(relative, self.text(data.decode('utf-8')).encode())
        except UnicodeError:
            if digest(data) in self.masker.binary or self.masker.binary_terms.search(data):
                self.withheld.append(relative + ' (binary instruction bytes or suite term)')
                self.limits.append('binary file withheld because it matches instruction bytes or a suite term: ' + relative)
            else:
                self.put_bytes(relative, data)
                self.limits.append('binary file copied without masking: ' + relative)


def build_packet(study, record, slot_dir, directory, packet_id, masker):
    """Write one reviewer packet and return its manifest plus restricted masking notes."""
    _, case, _ = study.selection(record['schedule_slot'])
    definition = case['definition']
    attempt_paths = [(str(slot_dir / 'workspace' / 'installed' / 'payload'), '<instructions>'),
                     (str(slot_dir / 'workspace' / 'installed'), '<installed>'),
                     (str(slot_dir / 'workspace'), '<workspace>'), (str(slot_dir), '<attempt>')]
    writer = PacketWriter(directory, masker, attempt_paths)
    writer.put_json('contract.json', {'case_id': definition['id'], 'request': definition['request'],
                                      'allowed_effects': definition['allowed_effects']})
    initial = study.root / 'fixture-source' / definition['id'] / 'initial-fixture'
    fixture_names = []
    for path in _walk(initial):
        relative = path.relative_to(initial).as_posix()
        fixture_names.append(relative)
        writer.put_file('source/' + relative, path)
    workspace = slot_dir / 'workspace'
    for path in _walk(workspace, PRODUCT_IGNORED):
        writer.put_file('final/' + path.relative_to(workspace).as_posix(), path)
    for path in _walk(workspace / 'artifacts'):
        writer.put_file('artifacts/' + path.relative_to(workspace / 'artifacts').as_posix(), path)
    if (slot_dir / 'final.diff').is_file():
        writer.put_file('final.diff', slot_dir / 'final.diff')
    else:
        writer.withheld.append('final.diff (not produced)')
    response = _read_json(slot_dir / 'response.json')
    if response is not None:
        writer.put_json('final-message.json', response)
    else:
        writer.withheld.append('final-message.json (missing or invalid response)')
    result = _read_json(slot_dir / 'result.json') or {}
    commands = [{'command': c.get('command'), 'exit_code': c.get('exit_code'),
                 'output': c.get('aggregated_output'), 'thread': c.get('thread_id')}
                for c in result.get('commands') or [] if isinstance(c, dict)]
    writer.put_json('commands.json', commands)
    check_names = [n for n in fixture_names
                   if Path(n).name.startswith(('check', 'test')) or n.endswith('.sh')]
    observed = [c for c in commands if isinstance(c['command'], str)
                and any(name in c['command'] for name in check_names)]
    writer.put_json('checks.json', {
        'claimed': response.get('checks') if isinstance(response, dict) else None,
        'observed': observed,
        'selection': 'observed commands that name a fixture check or test file: ' + ', '.join(check_names),
    })
    children = []
    for name in CHILD_SOURCES:
        source = slot_dir / name
        if source.is_dir() and not source.is_symlink():
            for path in _walk(source):
                writer.put_file('children/' + path.relative_to(slot_dir).as_posix(), path)
                children.append(path.relative_to(slot_dir).as_posix())
        elif source.exists() or source.is_symlink():
            writer.put_file('children/' + name, source)
            children.append(name)
    if children:
        child_status = {'collected': True, 'files': len(children)}
    elif study.controls.get('delegation') is False:
        child_status = {'collected': False, 'reason': 'delegation was disabled for this study'}
    else:
        child_status = {'collected': False, 'reason': 'no child records were collected'}
    for relative in writer.files:
        data = (directory / relative).read_bytes()
        try:
            text = data.decode('utf-8')
        except UnicodeError:
            continue
        if masker.residual(text):
            raise ValueError('masking left identifying text in ' + relative)
    limits = list(GENERIC_LIMITS) + writer.limits
    if writer.hits & {'instruction_content', 'instruction_path'}:
        limits.append('Instruction loading remains visible as placeholders; packets from the no-suite condition never contain them.')
    words = {}
    for relative in writer.files:
        try:
            text = (directory / relative).read_text()
        except UnicodeError:
            continue
        for word in ('reference', 'none'):
            words[word] = words.get(word, 0) + len(re.findall(r'(?i)\b' + word + r'\b', text))
    manifest = {'schema_version': 1, 'record': 'review-packet', 'packet_id': packet_id,
                'files': dict(sorted(writer.files.items())), 'children': child_status,
                'withheld': WITHHELD + sorted(writer.withheld),
                'notes': 'Judge the contract against the observed commands, checks, diff and final state. '
                         'A narrated check without an observed command earns no execution credit.'}
    data = encoded(manifest)
    (directory / 'manifest.json').write_bytes(data)
    masking = {'categories_masked': sorted(writer.hits), 'limits': limits,
               'unmasked_common_word_counts': words, 'withheld_files': sorted(writer.withheld)}
    return digest(data), masking


def _lock_down(root):
    # A fixed timestamp keeps file times from revealing the export order.
    for path in sorted(root.rglob('*'), reverse=True):
        os.utime(path, (0, 0), follow_symlinks=False)
        path.chmod(0o555 if path.is_dir() else 0o444)
    os.utime(root, (0, 0))
    root.chmod(0o555)


def export(study, destination, extra_terms=()):
    """Create a new review directory once; a later export is a separate review with new identifiers."""
    records = attempts.verify(study)
    destination = Path(destination)
    if destination.resolve().is_relative_to(study.root.resolve() / 'results'):
        raise ValueError('review directory cannot be inside study results')
    destination.mkdir(parents=False, exist_ok=False)
    packets = destination / 'packets'
    packets.mkdir()
    restricted = destination / 'restricted'
    restricted.mkdir(mode=0o700)
    (restricted / 'records').mkdir()
    masker = Masker(study, extra_terms)
    key = {'schema_version': 1, 'record': 'review-key', 'study': study.controls['study'],
           'controls_sha256': study.expected_digest, 'exporter_sha256': source_hash(),
           'attempts_sha256': digest(Path(attempts.__file__).read_bytes()),
           'mask_terms': ['mana'] + list(extra_terms), 'packets': {}, 'not_exported': []}
    used = set()
    order = list(range(1, len(study.schedule) + 1))
    random.SystemRandom().shuffle(order)
    for slot in order:
        if slot not in records:
            key['not_exported'].append({'slot': slot, 'reason': 'unstarted or unsealed allocated slot'})
            continue
        record, sha = records[slot]
        if record['execution_status'] != 'completed':
            key['not_exported'].append({'slot': slot, 'attempt_sha256': sha,
                                        'execution_status': record['execution_status'],
                                        'reason': 'execution did not complete; no task outcome to judge'})
            continue
        packet_id = 'p' + secrets.token_hex(6)
        while packet_id in used:
            packet_id = 'p' + secrets.token_hex(6)
        used.add(packet_id)
        directory = packets / packet_id
        directory.mkdir()
        packet_sha, masking = build_packet(study, record, study.root / 'results' / f'{slot:03d}',
                                           directory, packet_id, masker)
        key['packets'][packet_id] = {
            'slot': slot, 'case_id': record['case_id'], 'condition': record['condition'],
            'repetition': record['repetition'], 'attempt_sha256': sha, 'packet_sha256': packet_sha,
            'automatic_task_outcome': record['task_outcome'], 'masking': masking}
    key['not_exported'].sort(key=lambda item: item['slot'])
    descriptor = os.open(restricted / 'key.json', os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o400)
    with os.fdopen(descriptor, 'wb') as file:
        file.write(encoded(key))
    _lock_down(packets)
    return {'review': str(destination.resolve()), 'packets': len(key['packets']),
            'not_exported': len(key['not_exported']), 'agent_executed': False}


class Review:
    def __init__(self, study, root):
        self.study = study
        self.root = Path(root).resolve()
        self.restricted = self.root / 'restricted'
        self.key = json.loads((self.restricted / 'key.json').read_bytes())
        if self.key['controls_sha256'] != study.expected_digest:
            raise ValueError('review belongs to a different frozen study')

    def verify_packet(self, packet_id):
        entry = self.key['packets'].get(packet_id)
        if entry is None:
            raise ValueError('unknown packet: ' + packet_id)
        directory = self.root / 'packets' / packet_id
        manifest_bytes = (directory / 'manifest.json').read_bytes()
        if digest(manifest_bytes) != entry['packet_sha256']:
            raise ValueError('packet manifest changed: ' + packet_id)
        manifest = json.loads(manifest_bytes)
        actual = {p.relative_to(directory).as_posix(): digest(p.read_bytes())
                  for p in directory.rglob('*') if p.is_file() or p.is_symlink()}
        actual.pop('manifest.json')
        if actual != manifest['files']:
            raise ValueError('packet evidence changed: ' + packet_id)
        return entry

    def entries(self):
        path = self.restricted / 'ledger.jsonl'
        if not path.exists():
            return []
        out, chain = [], ''
        for number, line in enumerate(path.read_text().splitlines(), 1):
            entry = json.loads(line)
            record_path = self.restricted / 'records' / entry['record']
            data = record_path.read_bytes()
            if (entry['seq'] != number or digest(data) != entry['sha256']
                    or entry['chain'] != digest((chain + entry['sha256']).encode())):
                raise ValueError(f'review ledger entry {number} was altered')
            chain = entry['chain']
            out.append((entry, json.loads(data)))
        return out

    def verify(self):
        """Packets, attempts and ledger still match the hashes recorded when they were created."""
        records = attempts.verify(self.study)
        slots = set()
        for packet_id, entry in self.key['packets'].items():
            self.verify_packet(packet_id)
            if entry['slot'] in slots:
                raise ValueError('two packets for one allocated slot')
            slots.add(entry['slot'])
            sealed = records.get(entry['slot'])
            if sealed is None or sealed[1] != entry['attempt_sha256']:
                raise ValueError('packet attempt no longer matches its sealed record: ' + packet_id)
        withheld = [item['slot'] for item in self.key['not_exported']]
        if (len(withheld) != len(set(withheld)) or slots & set(withheld)
                or slots | set(withheld) != set(range(1, len(self.study.schedule) + 1))):
            raise ValueError('review key must account for every allocated slot exactly once')
        return records, self.entries()

    def append(self, kind, record):
        lock = self.restricted / '.lock'
        attempts.locked(lock)
        try:
            entries = self.entries()
            seq = len(entries) + 1
            data = encoded(record)
            name = f'{seq:04d}-{kind}.json'
            descriptor = os.open(self.restricted / 'records' / name, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o444)
            with os.fdopen(descriptor, 'wb') as file:
                file.write(data)
            previous = entries[-1][0]['chain'] if entries else ''
            entry = {'seq': seq, 'kind': kind, 'record': name, 'sha256': digest(data),
                     'chain': digest((previous + digest(data)).encode())}
            with (self.restricted / 'ledger.jsonl').open('a') as file:
                file.write(json.dumps(entry, sort_keys=True) + '\n')
            return entry
        finally:
            lock.rmdir()


def _evidence(review, packet_id, records):
    entry = review.verify_packet(packet_id)
    record, sha = records[entry['slot']]
    return {'packet_id': packet_id, 'packet_sha256': entry['packet_sha256'], 'attempt_sha256': sha,
            'archive_sha256': (record['archive'] or {}).get('sha256'),
            'artifact_index_sha256': record['artifact_index_sha256'],
            'controls_sha256': record['controls_sha256'],
            'frozen_fixture_sha256': record['frozen_fixture_sha256'],
            'payload_inventory_sha256': record['payload_inventory_sha256'],
            'request_sha256': record['request_sha256'],
            'case_definition_sha256': record['case_definition_sha256']}


def _check_fields(reviewer, kind, outcome, reasons, active_seconds, censored, initial):
    if not isinstance(reviewer, str) or not REVIEWER.fullmatch(reviewer):
        raise ValueError('reviewer needs a stable identifier')
    if kind not in ('human', 'model', 'automatic'):
        raise ValueError('reviewer kind must be human, model or automatic')
    if outcome not in attempts.TASK_OUTCOMES:
        raise ValueError('outcome must be passed, failed or needs_adjudication')
    if not isinstance(reasons, str) or not reasons.strip():
        raise ValueError('a judgment records its reasons')
    if kind != 'human':
        if active_seconds is not None or censored is not None:
            raise ValueError('only a human review measures active time')
        return
    if active_seconds is not None and (isinstance(active_seconds, bool)
                                       or not isinstance(active_seconds, (int, float)) or active_seconds < 0):
        raise ValueError('active seconds must be a non-negative number or null')
    if censored is not None and not isinstance(censored, bool):
        raise ValueError('censored must be true, false or null')
    if initial and active_seconds is not None and active_seconds > INITIAL_CAP_SECONDS:
        raise ValueError('initial review is capped at 600 active seconds; record it as censored at the cap')
    if censored and outcome != 'needs_adjudication':
        raise ValueError('a censored review is unresolved and needs adjudication')


def _state(entries):
    """Original judgments, their supersession chains and effective versions."""
    originals, root_of, effective, superseded = {}, {}, {}, set()
    for entry, record in entries:
        if entry['kind'] == 'judgment':
            originals[entry['sha256']] = record
            root_of[entry['sha256']] = entry['sha256']
            effective[entry['sha256']] = record
        elif entry['kind'] == 'regrade':
            root = root_of[record['supersedes']]
            superseded.add(record['supersedes'])
            root_of[entry['sha256']] = root
            effective[root] = record
    return originals, root_of, effective, superseded


def _assignment(entries, reviewer):
    for entry, record in entries:
        if entry['kind'] == 'assignment' and record['reviewer'] == reviewer:
            return record
    return None


def assign(review, reviewer, rng=None):
    """Fix one reviewer's randomized packet order before they open any packet."""
    if not isinstance(reviewer, str) or not REVIEWER.fullmatch(reviewer):
        raise ValueError('reviewer needs a stable identifier')
    _, entries = review.verify()
    if _assignment(entries, reviewer) is not None:
        raise ValueError('reviewer already has an order')
    order = sorted(review.key['packets'])
    (rng or random.SystemRandom()).shuffle(order)
    record = {'schema_version': 1, 'record': 'assignment', 'reviewer': reviewer, 'order': order,
              'recorded_by': source_hash()}
    review.append('assignment', record)
    return order


def judge(review, packet_id, reviewer, kind, role, outcome, reasons, active_seconds=None,
          censored=None, order_position=None, familiarity=None, dimensions=None):
    records, entries = review.verify()
    evidence = _evidence(review, packet_id, records)
    if role not in ('initial', 'adjudication'):
        raise ValueError('role must be initial or adjudication')
    _check_fields(reviewer, kind, outcome, reasons, active_seconds, censored, role == 'initial')
    originals, _, _, _ = _state(entries)
    mine = [(sha, r) for sha, r in originals.items() if r['packet_id'] == packet_id]
    initials = [(sha, r) for sha, r in mine if r['role'] == 'initial']
    adjudicated = [r for _, r in mine if r['role'] == 'adjudication']
    considered = []
    if role == 'initial':
        if adjudicated:
            raise ValueError('initial judgments close once adjudication exists; use a regrade')
        if len(initials) >= 2:
            raise ValueError('a packet takes exactly two initial judgments')
        if any(r['reviewer'] == reviewer for _, r in initials):
            raise ValueError('the two initial judgments need different reviewers')
    else:
        if len(initials) != 2:
            raise ValueError('adjudication needs both initial judgments')
        if kind != 'human':
            raise ValueError('a model or automatic grader cannot be the adjudicating oracle')
        if any(r['reviewer'] == reviewer for _, r in initials):
            raise ValueError('the adjudicator must be a third reviewer')
        if adjudicated:
            raise ValueError('a packet takes one adjudication; corrections are regrades')
        if outcome == 'needs_adjudication':
            raise ValueError('adjudication resolves to passed or failed')
        considered = sorted(sha for sha, _ in initials)
    assignment = _assignment(entries, reviewer)
    if assignment is not None:
        order = assignment['order']
        if packet_id not in order or order_position != order.index(packet_id) + 1:
            raise ValueError('order position differs from the reviewer\'s assigned order')
    elif order_position is not None:
        raise ValueError('order position needs a recorded assignment')
    if familiarity is not None and not isinstance(familiarity, str):
        raise ValueError('familiarity is a disclosure string or null')
    record = {'schema_version': 1, 'record': 'judgment', 'role': role, 'evidence': evidence,
              'packet_id': packet_id, 'reviewer': reviewer, 'reviewer_kind': kind, 'outcome': outcome,
              'reasons': reasons, 'dimensions': dimensions or {}, 'order_position': order_position,
              'familiarity': familiarity, 'considered_judgments': considered,
              'human_review': {'active_seconds': active_seconds, 'censored': censored},
              'recorded_by': source_hash()}
    return review.append('judgment', record)


def regrade(review, supersedes, reviewer, kind, outcome, reasons, active_seconds=None,
            censored=None, grader_sha256=None):
    """Append a correction; the superseded judgment and its evidence hashes stay in the ledger."""
    records, entries = review.verify()
    by_sha = {entry['sha256']: (entry, record) for entry, record in entries}
    if supersedes not in by_sha or by_sha[supersedes][0]['kind'] not in ('judgment', 'regrade'):
        raise ValueError('regrade must supersede a recorded judgment or regrade')
    _, root_of, _, superseded = _state(entries)
    if supersedes in superseded:
        raise ValueError('that record is already superseded; regrade its latest version')
    previous = by_sha[supersedes][1]
    role = previous['role']
    _check_fields(reviewer, kind, outcome, reasons, active_seconds, censored, role == 'initial')
    if role == 'adjudication' and (kind != 'human' or outcome == 'needs_adjudication'):
        raise ValueError('an adjudication correction needs a human and a resolved outcome')
    if kind == 'automatic' and (not isinstance(grader_sha256, str) or not conditions.DIGEST.fullmatch(grader_sha256)):
        raise ValueError('an automatic regrade records its grader SHA-256')
    record = {'schema_version': 1, 'record': 'regrade', 'role': role, 'supersedes': supersedes,
              'original_judgment': root_of[supersedes],
              'superseded_outcome': previous['outcome'],
              'evidence': _evidence(review, previous['packet_id'], records),
              'packet_id': previous['packet_id'], 'reviewer': reviewer, 'reviewer_kind': kind,
              'outcome': outcome, 'reasons': reasons, 'grader_sha256': grader_sha256,
              'human_review': {'active_seconds': active_seconds, 'censored': censored},
              'recorded_by': source_hash()}
    if record['evidence'] != previous['evidence']:
        raise ValueError('evidence changed since the superseded judgment')
    return review.append('regrade', record)


def final_outcomes(review, entries):
    originals, _, effective, _ = _state(entries)
    by_packet = {packet_id: {'initial': [], 'adjudication': None} for packet_id in review.key['packets']}
    for sha, record in originals.items():
        current = effective[sha]
        slot = by_packet[record['packet_id']]
        if record['role'] == 'initial':
            slot['initial'].append(current)
        else:
            slot['adjudication'] = current
    results = {}
    for packet_id, slot in by_packet.items():
        initials = slot['initial']
        if slot['adjudication'] is not None:
            outcome, basis = slot['adjudication']['outcome'], 'adjudication'
        elif len(initials) < 2:
            outcome, basis = None, 'awaiting two initial judgments'
        elif not any(r['reviewer_kind'] == 'human' for r in initials):
            outcome, basis = 'needs_adjudication', 'no human judgment; a model cannot be the sole oracle'
        elif initials[0]['outcome'] == initials[1]['outcome'] != 'needs_adjudication':
            outcome, basis = initials[0]['outcome'], 'initial agreement'
        else:
            outcome, basis = 'needs_adjudication', 'initial judgments disagree or are unresolved'
        results[packet_id] = {'outcome': outcome, 'basis': basis,
                              'initial_outcomes': [r['outcome'] for r in initials]}
    return results


def report(study, review=None):
    """Evaluator-only summary. Unmeasured human time stays null; nothing estimates time saved."""
    records = attempts.verify(study)
    summary = attempts.summarize(study, records)
    if review is None:
        return summary
    _, entries = review.verify()
    finals = final_outcomes(review, entries)
    seconds, measured, unmeasured, censored = 0, 0, 0, 0
    for entry, record in entries:
        if entry['kind'] not in ('judgment', 'regrade') or record['reviewer_kind'] != 'human':
            continue
        value = record['human_review']['active_seconds']
        if value is None:
            unmeasured += 1
        else:
            measured += 1
            seconds += value
        censored += bool(record['human_review']['censored'])
    counts = {outcome: 0 for outcome in attempts.TASK_OUTCOMES}
    counts['unjudged'] = 0
    packets = []
    for packet_id, entry in sorted(review.key['packets'].items(), key=lambda item: item[1]['slot']):
        final = finals[packet_id]
        counts[final['outcome'] or 'unjudged'] += 1
        packets.append({'packet_id': packet_id, 'slot': entry['slot'], 'condition': entry['condition'],
                        'case_id': entry['case_id'], 'automatic_task_outcome': entry['automatic_task_outcome'],
                        **final, 'masking_limits': entry['masking']['limits']})
    summary.update({
        'review_packets': packets, 'reviewed_final_outcomes': counts,
        'reviewed_passes': counts['passed'],
        'not_exported': review.key['not_exported'],
        'human_review': {'active_seconds_total': seconds if measured else None,
                         'measured_records': measured, 'unmeasured_records': unmeasured,
                         'censored_records': censored},
    })
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('seal', 'status', 'export', 'assign', 'judge', 'regrade'))
    parser.add_argument('--study', type=Path, required=True)
    parser.add_argument('--controls-sha256', required=True)
    parser.add_argument('--review', type=Path)
    parser.add_argument('--out', type=Path)
    parser.add_argument('--mask-term', action='append', default=[])
    parser.add_argument('--packet')
    parser.add_argument('--reviewer')
    parser.add_argument('--kind', choices=('human', 'model', 'automatic'))
    parser.add_argument('--role', choices=('initial', 'adjudication'))
    parser.add_argument('--outcome', choices=attempts.TASK_OUTCOMES)
    parser.add_argument('--reason')
    parser.add_argument('--active-seconds', type=float)
    parser.add_argument('--censored', action='store_true')
    parser.add_argument('--order-position', type=int)
    parser.add_argument('--familiarity')
    parser.add_argument('--supersedes')
    parser.add_argument('--grader-sha256')
    args = parser.parse_args()
    try:
        # Only the archived runner-source copies of these modules may seal or review the study.
        here = Path(__file__).resolve().parent
        loaded = {'attempts.py': digest(Path(attempts.__file__).read_bytes()), 'adjudication.py': source_hash()}
        if Path(attempts.__file__).resolve().parent != here:
            raise ValueError('attempts.py must load from beside adjudication.py')
        study = conditions.FrozenStudy(args.study, args.controls_sha256, loaded, here)
        if args.command == 'seal':
            result = attempts.seal_claimed(study)
        elif args.command == 'export':
            if not args.out:
                raise ValueError('export needs --out for a new review directory')
            result = export(study, args.out, args.mask_term)
        else:
            review = Review(study, args.review) if args.review else None
            if args.command == 'status':
                result = report(study, review)
            elif review is None:
                raise ValueError(args.command + ' needs --review')
            elif args.command == 'assign':
                result = assign(review, args.reviewer)
            elif args.command == 'judge':
                censored = True if args.censored else (False if args.kind == 'human' and args.active_seconds is not None else None)
                result = judge(review, args.packet, args.reviewer, args.kind, args.role, args.outcome,
                               args.reason, args.active_seconds, censored, args.order_position, args.familiarity)
            else:
                censored = True if args.censored else None
                result = regrade(review, args.supersedes, args.reviewer, args.kind, args.outcome,
                                 args.reason, args.active_seconds, censored, args.grader_sha256)
    except (OSError, ValueError, KeyError) as exc:
        parser.error(str(exc))
    print(json.dumps(result, indent=2))
    return 0


if __name__ == '__main__':
    sys.exit(main())
