"""Host adapter capability registry backed by recorded probe evidence.

A host version is accepted for a mode only when every capability that mode
needs has a recorded `verified` observation with evidence and a timestamp.
Unknown stays unknown and fails closed. A later failed or unavailable
observation for the same host and capability overrides an earlier pass.
"""
import datetime
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
EVIDENCE = HERE / 'host-evidence'
STATUSES = ('verified', 'failed', 'unavailable')
CAPABILITIES = (
    'installation', 'outside_read_denied', 'protected_write_denied', 'fixture_write_allowed',
    'network_denied', 'command_events', 'usage_events', 'completion_detection', 'model_selection',
    'descendant_collection', 'thread_attribution', 'active_thread_cap', 'child_containment',
    'process_family_termination', 'question_support', 'skill_discovery', 'explicit_only_honored',
    'children_disabled',
)
FOCUSED = ('installation', 'outside_read_denied', 'protected_write_denied', 'fixture_write_allowed',
           'network_denied', 'command_events', 'completion_detection')
DELEGATED = FOCUSED + ('descendant_collection', 'thread_attribution', 'child_containment')
MODES = {
    'focused': FOCUSED,
    'delegated': DELEGATED,
    # Comparative arms share one thread cap, so the cap itself must be observed,
    # along with family termination and fresh evidence.
    'comparative-delegated': DELEGATED + ('usage_events', 'active_thread_cap', 'process_family_termination'),
    # Natural selection needs focused containment plus a probe that saw the host expose the
    # installed catalog and record the entrypoint load as an event. explicit_only_honored is
    # recorded beside it and changes how loads are judged, not whether the host is accepted. So is
    # children_disabled: a selection-only slot that tries to spawn is judged on its own.
    'discovery': FOCUSED + ('skill_discovery',),
}
FRESHNESS_DAYS = {'comparative-delegated': 30}


def parse_time(value):
    if not isinstance(value, str):
        raise ValueError('capability timestamp required')
    if len(value) == 10:
        value += 'T00:00:00+00:00'
    moment = datetime.datetime.fromisoformat(value.replace('Z', '+00:00'))
    if moment.tzinfo is None:
        raise ValueError('capability timestamp needs a timezone')
    return moment


def check_record(record, name='record'):
    if not isinstance(record, dict) or record.get('schema_version') != 1:
        raise ValueError('invalid host evidence schema: ' + name)
    for field in ('host', 'platform', 'recorded_at', 'source', 'capabilities'):
        if field not in record:
            raise ValueError('host evidence missing %s: %s' % (field, name))
    if not isinstance(record['host'], str) or not record['host'].strip():
        raise ValueError('host evidence needs the exact reported version string: ' + name)
    parse_time(record['recorded_at'])
    capabilities = record['capabilities']
    if not isinstance(capabilities, dict) or set(capabilities) - set(CAPABILITIES):
        raise ValueError('unknown host capability: ' + name)
    for key, value in capabilities.items():
        if (not isinstance(value, dict) or value.get('status') not in STATUSES
                or not isinstance(value.get('evidence'), list) or not value['evidence']
                or not all(isinstance(item, str) and item for item in value['evidence'])):
            raise ValueError('capability %s needs a status and evidence: %s' % (key, name))
        parse_time(value.get('observed_at'))
    cap = capabilities.get('active_thread_cap')
    if cap and cap['status'] == 'verified' and cap.get('counts') not in ('children', 'including_parent'):
        raise ValueError('a verified thread cap must record whether it counts the parent: ' + name)
    return record


def load(directory=None):
    records = []
    directory = Path(directory or EVIDENCE)
    for path in sorted(directory.glob('*.json')):
        data = path.read_bytes()
        record = check_record(json.loads(data), path.name)
        records.append({'path': path.name, 'sha256': hashlib.sha256(data).hexdigest(), 'record': record})
    return records


def capabilities(host, platform='linux', directory=None):
    """Latest observation per capability for one exact host string; absent means unknown."""
    merged = {key: None for key in CAPABILITIES}
    for entry in load(directory):
        record = entry['record']
        if record['host'] != host or record['platform'] != platform:
            continue
        for key, value in record['capabilities'].items():
            current = merged[key]
            if current is None or parse_time(value['observed_at']) >= parse_time(current['observed_at']):
                merged[key] = dict(value, record=entry['path'], record_sha256=entry['sha256'])
    return merged


def assess(host, mode, platform='linux', directory=None, at=None):
    """Return a durable acceptance record. `accepted` is false unless every need is verified."""
    if mode not in MODES:
        raise ValueError('unknown host mode: ' + str(mode))
    at = at or datetime.datetime.now(datetime.timezone.utc)
    found = capabilities(host, platform, directory)
    missing, stale = [], []
    for key in MODES[mode]:
        value = found[key]
        if value is None or value['status'] != 'verified':
            missing.append(key + '=' + ('unknown' if value is None else value['status']))
            continue
        limit = FRESHNESS_DAYS.get(mode)
        if limit is not None and at - parse_time(value['observed_at']) > datetime.timedelta(days=limit):
            stale.append(key)
    return {'host': host, 'platform': platform, 'mode': mode, 'assessed_at': at.isoformat(timespec='seconds'),
            'accepted': not missing and not stale, 'missing': missing, 'stale': stale,
            'capabilities': {key: found[key] for key in MODES[mode]}}


def require(host, mode, platform='linux', directory=None, at=None):
    result = assess(host, mode, platform, directory, at)
    if not result['accepted']:
        detail = ', '.join(result['missing'] + [key + '=stale' for key in result['stale']])
        raise ValueError('unvalidated host %s for %s: %s' % (host, mode, detail))
    return result


def accepted_versions(mode, platform='linux', directory=None, at=None):
    hosts = {entry['record']['host'] for entry in load(directory)}
    return {host for host in hosts if assess(host, mode, platform, directory, at)['accepted']}
