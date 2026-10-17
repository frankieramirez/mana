"""Immutable allocated-slot attempt records for frozen condition studies.

A sealed record is written once beside its slot directory and never rewritten.
It keeps execution status apart from task outcome, inventories every artifact
with its source hash, and is listed in an append-only ledger. Allocated slots
without a record stay visible as unstarted. Nothing here invokes a model.
"""
import hashlib
import json
import os
from pathlib import Path
import re
import stat

EXECUTION_STATUSES = ('setup_failed', 'agent_failed', 'timeout', 'collection_failed', 'completed')
TASK_OUTCOMES = ('passed', 'failed', 'needs_adjudication')
SLOT_DIR = re.compile(r'(\d{3})')
SLOT_FILE = re.compile(r'(\d{3})\.(json\.gz|archive\.json|attempt\.json)')
RESULT_FILES = {'STOP.json', 'attempts.jsonl', '.active', '.seal-lock'}
# Mirrors archive_delegated.archive so the inventory says what the archive omits.
ARCHIVE_EXCLUDED = ('workspace/.git', 'workspace/home', 'workspace/installed')
LEDGER = 'attempts.jsonl'
# Read-only Git commands such as a later offline regrade may refresh stat data in
# the index. It stays inventoried; only this file is exempt from the change check.
VOLATILE = {'workspace/.git/index'}


def encoded(value):
    return (json.dumps(value, sort_keys=True, indent=2) + '\n').encode()


def digest(data):
    return hashlib.sha256(data).hexdigest()


def archived(relative):
    parts = relative.split('/')
    if '__pycache__' in parts:
        return False
    return not any(relative == p or relative.startswith(p + '/') for p in ARCHIVE_EXCLUDED)


def artifact_inventory(root):
    """Hash every entry without following links; agent-made links are evidence, not errors."""
    root = Path(root)
    entries = []
    for path in sorted(root.rglob('*')):
        relative = path.relative_to(root).as_posix()
        info = path.lstat()
        if stat.S_ISDIR(info.st_mode):
            continue
        entry = {'path': relative, 'archived': archived(relative)}
        if stat.S_ISLNK(info.st_mode):
            entry.update(kind='symlink', target=os.readlink(path), archived=False)
        elif not stat.S_ISREG(info.st_mode):
            entry.update(kind='special', archived=False)
        else:
            try:
                data = path.read_bytes()
            except OSError as exc:
                entry.update(kind='unreadable', error=type(exc).__name__, archived=False)
            else:
                entry.update(kind='file', sha256=digest(data), bytes=len(data),
                             executable=bool(info.st_mode & 0o111))
        entries.append(entry)
    return entries


def stable(index):
    return [entry for entry in index if entry['path'] not in VOLATILE]


def _json(path):
    try:
        return json.loads(path.read_bytes())
    except (OSError, ValueError):
        return None


def execution_and_outcome(runner_execution, evaluation):
    """Map the runner's status onto the protocol vocabulary without inventing a pass."""
    if runner_execution in ('setup_failed', 'agent_failed', 'timeout', 'collection_failed'):
        return runner_execution, None
    if runner_execution == 'completed':
        outcome = evaluation.get('task_outcome') if evaluation else None
        return 'completed', outcome if outcome in ('passed', 'failed') else 'needs_adjudication'
    if runner_execution == 'grading_failed':
        # The agent finished; the automatic grader could not decide. A human resolves it.
        return 'completed', 'needs_adjudication'
    return 'collection_failed', None


def build_record(study, slot):
    """Deterministic record for one claimed slot, from the evidence on disk."""
    cell = study.schedule[slot - 1]
    _, case, condition = study.selection(slot)
    results = study.root / 'results'
    out = results / f'{slot:03d}'
    if out.is_symlink() or not out.is_dir():
        raise ValueError(f'slot {slot} has no claimed attempt directory')
    evaluation = _json(out / 'evaluation.json')
    result = _json(out / 'result.json')
    failures = []
    if evaluation is None:
        failures.append('evaluation.json missing or unreadable')
    if result is None:
        failures.append('result.json missing or unreadable: interrupted or unrecorded attempt')
    runner_execution = (result or {}).get('execution') or (evaluation or {}).get('execution_status')
    if result is None:
        runner_execution = 'collection_failed'
    execution_status, task_outcome = execution_and_outcome(runner_execution, evaluation)
    if runner_execution == 'grading_failed':
        failures.append('automatic grader error; outcome needs adjudication')
    failures += [str(f) for f in (evaluation or {}).get('failures') or (result or {}).get('failures') or []]
    archive = None
    archive_record = _json(results / f'{slot:03d}.archive.json')
    archive_path = results / f'{slot:03d}.json.gz'
    if archive_record is not None and archive_path.is_file():
        actual = digest(archive_path.read_bytes())
        if actual != archive_record.get('sha256'):
            raise ValueError(f'slot {slot} archive differs from its archive record')
        archive = {'path': archive_path.name, 'sha256': actual, 'files': archive_record.get('files')}
    else:
        failures.append('portable archive unavailable')
    index = artifact_inventory(out)
    stop = _json(results / 'STOP.json')
    usage = (evaluation or {}).get('usage') or {}
    context = (result or {}).get('context')
    context = context if isinstance(context, dict) else {}
    payload = condition['inventory']
    record = {
        'schema_version': 1, 'record': 'attempt',
        'study': study.controls['study'], 'controls_sha256': study.expected_digest,
        'schedule_slot': slot, 'case_id': cell['case'], 'condition': cell['condition'],
        'repetition': cell['repetition'], 'source_group': case['source_group'], 'split': case['split'],
        'request_sha256': digest(case['definition']['request'].encode()),
        'case_definition_sha256': digest(encoded(case['definition'])),
        'payload_hashes': payload, 'payload_inventory_sha256': digest(encoded(payload)),
        'fixture_sha256': (evaluation or {}).get('fixture_sha256'),
        'frozen_fixture_sha256': digest(encoded(case['initial_fixture_inventory'])),
        'tool_inventory_sha256': digest(encoded(case['tool_inventory'])),
        'runner_hashes': study.controls['runner_inventory'],
        'requested_model': study.controls['model'],
        # Host events have not supplied backend identity; unobserved values stay null.
        'actual_model': (evaluation or {}).get('actual_model'),
        'runner_execution': runner_execution,
        'execution_status': execution_status,
        'task_outcome': task_outcome,
        'counts_as_pass': task_outcome == 'passed',
        'failures': failures,
        'artifact_index': index,
        'artifact_index_sha256': digest(encoded(index)),
        'archive': archive,
        'elapsed_seconds': (evaluation or {}).get('elapsed_seconds'),
        'tool_operations': None,
        'observed_command_operations': (evaluation or {}).get('observed_command_operations'),
        'retry_attempts': 0,
        'usage': {'parent': usage.get('parent'), 'children': usage.get('children'),
                  'family_total': usage.get('family_total')},
        # Complete-content read matches are lower bounds; absent observations stay null.
        'context': {'observed_full_read_bytes': context.get('total_full_read_bytes'),
                    'repeated_read_bytes': context.get('redundant_full_read_bytes')},
        'runner_context': context if isinstance(context, dict) and context else None,
        'human_review': {'active_seconds': None, 'censored': None},
        'stopped_schedule': bool(stop and stop.get('slot') == slot),
        # Judgments and regrades are separate write-once records naming this record's hash.
        'judgments': [], 'regrades': [],
        'sealed_by': {'attempts.py': digest(Path(__file__).read_bytes())},
    }
    if execution_status not in EXECUTION_STATUSES or task_outcome not in TASK_OUTCOMES + (None,):
        raise ValueError('attempt status outside the protocol vocabulary')
    return record


def _ledger(results):
    path = results / LEDGER
    if not path.exists():
        return []
    entries = []
    for number, line in enumerate(path.read_text().splitlines(), 1):
        try:
            entry = json.loads(line)
            if set(entry) != {'slot', 'record', 'sha256'}:
                raise ValueError
        except ValueError:
            raise ValueError(f'attempt ledger line {number} is invalid') from None
        entries.append(entry)
    return entries


def comparable(record):
    """Fields a reseal must reproduce: volatile Git stat data and the sealing tool's hash are excluded."""
    value = {k: v for k, v in record.items() if k not in ('artifact_index', 'artifact_index_sha256', 'sealed_by')}
    value['artifact_index'] = stable(record['artifact_index'])
    return value


def locked(path):
    try:
        path.mkdir()
    except FileExistsError:
        raise ValueError(f'{path.name} exists; confirm no seal or review write is running, '
                         'then remove the stale lock directory') from None


def seal(study, slot):
    """Write the slot's record once. Resealing the same evidence is a no-op; different evidence fails."""
    study.verify()
    if type(slot) is not int or not 1 <= slot <= len(study.schedule):
        raise ValueError('invalid scheduled slot')
    results = study.root / 'results'
    target = results / f'{slot:03d}.attempt.json'
    lock = results / '.seal-lock'
    locked(lock)
    try:
        out = results / f'{slot:03d}'
        stop = results / 'STOP.json'
        if (out.is_dir() and not (out / 'result.json').is_file() and not stop.exists()
                and not target.exists()):
            # An interrupted claim cannot be followed by later slots; record why the schedule ended.
            stop.write_bytes(encoded({'slot': slot, 'execution': 'collection_failed', 'failures': [
                'result.json missing: interrupted or unrecorded attempt'],
                'reason': 'interrupted allocated attempt sealed without a runner result'}))
        record = build_record(study, slot)
        data = encoded(record)
        entries = _ledger(results)
        if target.exists() or target.is_symlink():
            existing = target.read_bytes() if not target.is_symlink() else b''
            if not any(e['slot'] == slot and e['sha256'] == digest(existing) for e in entries):
                raise ValueError(f'slot {slot} record is missing from the attempt ledger')
            if comparable(json.loads(existing)) != comparable(record):
                raise ValueError(f'slot {slot} is already sealed with different evidence')
            return {'slot': slot, 'sha256': digest(existing), 'created': False}
        if any(e['slot'] == slot for e in entries):
            raise ValueError(f'slot {slot} already has a ledger entry')
        descriptor = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o444)
        with os.fdopen(descriptor, 'wb') as file:
            file.write(data)
        with (results / LEDGER).open('a') as file:
            file.write(json.dumps({'slot': slot, 'record': target.name, 'sha256': digest(data)}, sort_keys=True) + '\n')
        return {'slot': slot, 'sha256': digest(data), 'created': True}
    finally:
        lock.rmdir()


def seal_claimed(study):
    """Seal claimed slots without a ledger entry, such as one interrupted before its runner finished.

    Already sealed slots are skipped; verify() reports any later change to their evidence.
    """
    sealed = [e['slot'] for e in _ledger(study.root / 'results')]
    created = []
    for slot in range(1, len(study.schedule) + 1):
        if slot not in sealed and (study.root / 'results' / f'{slot:03d}').is_dir():
            created.append(seal(study, slot))
    return created


def verify(study):
    """Return every sealed record by slot, or raise on tampering, replacement or unsealed attempts."""
    study.verify()
    results = study.root / 'results'
    allocated = len(study.schedule)
    problems = []
    for path in sorted(results.iterdir()):
        name = path.name
        match = SLOT_DIR.fullmatch(name) or SLOT_FILE.fullmatch(name)
        if match:
            if not 1 <= int(match.group(1)) <= allocated:
                problems.append('unallocated attempt entry: ' + name)
            elif SLOT_DIR.fullmatch(name) and (path.is_symlink() or not path.is_dir()):
                problems.append('slot entry is not a directory: ' + name)
        elif name not in RESULT_FILES and not re.fullmatch(r'regrade-[A-Za-z0-9_]+\.json', name):
            problems.append('unexpected entry in results; hidden replacement is not allowed: ' + name)
    entries = _ledger(results)
    seen = set()
    records = {}
    for entry in entries:
        slot = entry['slot']
        if slot in seen:
            problems.append(f'slot {slot} appears twice in the attempt ledger')
            continue
        seen.add(slot)
        path = results / entry['record']
        if entry['record'] != f'{slot:03d}.attempt.json' or path.is_symlink() or not path.is_file():
            problems.append(f'slot {slot} record is missing')
            continue
        data = path.read_bytes()
        if digest(data) != entry['sha256']:
            problems.append(f'slot {slot} record changed after sealing')
            continue
        record = json.loads(data)
        cell = study.schedule[slot - 1] if 1 <= slot <= allocated else None
        if (cell is None or record['schedule_slot'] != slot or record['case_id'] != cell['case']
                or record['condition'] != cell['condition'] or record['repetition'] != cell['repetition']
                or record['controls_sha256'] != study.expected_digest):
            problems.append(f'slot {slot} record does not match the frozen schedule')
            continue
        index = artifact_inventory(results / f'{slot:03d}')
        if stable(index) != stable(record['artifact_index']):
            problems.append(f'slot {slot} evidence changed after sealing')
        if record['archive'] is not None:
            archive = results / record['archive']['path']
            if not archive.is_file() or digest(archive.read_bytes()) != record['archive']['sha256']:
                problems.append(f'slot {slot} archive changed after sealing')
        records[slot] = (record, entry['sha256'])
    for slot in range(1, allocated + 1):
        if (results / f'{slot:03d}').is_dir() and slot not in records and slot not in seen:
            problems.append(f'slot {slot} was claimed but never sealed')
        elif (results / f'{slot:03d}.attempt.json').exists() and slot not in seen:
            problems.append(f'slot {slot} record is missing from the attempt ledger')
    if problems:
        raise ValueError('; '.join(problems))
    return records


def summarize(study, records=None):
    """Denominator is every allocated slot. Unobserved resources stay null; no human savings are inferred."""
    records = verify(study) if records is None else records
    allocated = len(study.schedule)
    statuses = {status: 0 for status in EXECUTION_STATUSES + ('unstarted',)}
    outcomes = {outcome: 0 for outcome in TASK_OUTCOMES}
    unstarted = []
    for slot in range(1, allocated + 1):
        if slot not in records:
            statuses['unstarted'] += 1
            unstarted.append(slot)
            continue
        record = records[slot][0]
        statuses[record['execution_status']] += 1
        if record['task_outcome'] is not None:
            outcomes[record['task_outcome']] += 1
    sealed = [records[s][0] for s in sorted(records)]
    stop = _json(study.root / 'results' / 'STOP.json')
    return {
        'study': study.controls['study'], 'allocated_slots': allocated,
        'sealed_attempts': len(sealed), 'unstarted_slots': unstarted,
        'execution_status_counts': statuses,
        'automatic_task_outcomes': outcomes,
        'passes': outcomes['passed'],
        'not_passed': allocated - outcomes['passed'],
        'stopped_at_slot': stop.get('slot') if stop else None,
        'actual_model_unobserved': sum(r['actual_model'] is None for r in sealed),
        'child_usage_unobserved': sum(r['usage']['children'] is None for r in sealed),
        'family_usage_unobserved': sum(r['usage']['family_total'] is None for r in sealed),
        'tool_operations_unobserved': sum(r['tool_operations'] is None for r in sealed),
        'retry_attempts': sum(r['retry_attempts'] for r in sealed),
    }
