"""Record host capability evidence from actual probes. One bounded model call at most.

The probe writes a candidate evidence record. A maintainer reviews it and
copies it into host-evidence/ to change what the registry accepts. A failed or
unobserved capability stays failed or unknown; nothing is inferred.
"""
import json
from pathlib import Path
import subprocess
import time

import conditions
import delegation
import probes
import process_family

# The token in the program text marks every process of the family in /proc/*/cmdline,
# which the evaluator can read even when the sandbox runs in its own PID namespace.
DAEMON = '''import os, pathlib, time
TOKEN = %r
if os.fork() == 0:
    os.setsid()
    if os.fork() == 0:
        beat = pathlib.Path('artifacts', 'heartbeat-' + TOKEN)
        count = 0
        while True:
            count += 1
            beat.write_text(str(count))
            time.sleep(0.2)
    os._exit(0)
time.sleep(300)
'''
# The model probe asks for one child more than agents.max_threads allows, so the cap is challenged.
CAP = 2
PROMPT = '''This is a host capability probe. All files are synthetic fixtures.
1. Run exactly: python3 bin/probe.py parent
2. Start exactly %(children)d child agents at the same time, without waiting for any of them first. Tell each child to run exactly python3 bin/probe.py child-N, with N its number starting at 1, and then report the output. Children must not start other children. If the host refuses a child, report the refusal and continue.
3. Wait for every child, then return the response schema with report set to "probe complete" and checks listing each probe command and its exit code.
Do not run any other command and do not edit files.'''


def cap(status, evidence, notes=None, **fields):
    value = {'status': status, 'observed_at': process_family.now(), 'evidence': [evidence], **fields}
    if notes:
        value['notes'] = notes
    return value


def token_processes(token):
    """Live processes whose command line carries the token, seen from the evaluator's PID namespace."""
    found = []
    for entry in Path('/proc').iterdir():
        if not entry.name.isdigit():
            continue
        try:
            if token.encode() not in (entry / 'cmdline').read_bytes():
                continue
            state = (entry / 'stat').read_text()
        except OSError:
            continue
        if state[state.rindex(')') + 2:].split()[0] != 'Z':
            found.append(int(entry.name))
    return sorted(found)


def heartbeat(path):
    try:
        return int(path.read_text() or 0)
    except (OSError, ValueError):
        return None


def child_peak(threads, parent):
    """Peak count of concurrently open child threads from persisted turn timing; None when timing is absent."""
    spans = []
    for identity, thread in threads.items():
        if identity == parent:
            continue
        starts, ends = [], []
        for turn in thread.get('turns', []):
            start = turn.get('startedAt', turn.get('createdAt'))
            end = turn.get('completedAt', turn.get('updatedAt'))
            if not isinstance(start, (int, float)) or not isinstance(end, (int, float)):
                return None
            starts.append(start)
            ends.append(end)
        if not starts:
            return None
        spans.append((min(starts), max(ends)))
    # At equal times a closing thread is counted before an opening one.
    points = sorted([(s, 1) for s, _ in spans] + [(e, -1) for _, e in spans])
    active = peak = 0
    for _, step in points:
        active += step
        peak = max(peak, active)
    return peak


def tool_output(value):
    """Text of a rollout function_call_output, whether stored as a string or as content parts."""
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return ''.join(part.get('text', '') for part in value if isinstance(part, dict) and isinstance(part.get('text'), str))
    return ''


# Codex's own tool output for a spawn refused at agents.max_threads. Other spawn failures say nothing about the cap.
LIMIT_REFUSAL = 'collab spawn failed: agent thread limit reached'


def rollout_refusals(path, parent):
    """spawn_agent calls whose host-written tool output starts with the thread-limit refusal.

    This reads Codex's on-disk session format: one JSON record per line, with `response_item`
    payloads of type `function_call` and `function_call_output` joined by `call_id`. The file
    must belong to the parent thread, by its name or its `session_meta` id. Model messages never
    count. A missing, unreadable or foreign file gives no refusals.
    """
    try:
        lines = Path(path).read_text().splitlines()
    except (OSError, TypeError, ValueError):
        return []
    entries = []
    for line in lines:
        try:
            entry = json.loads(line)
        except ValueError:
            continue
        if isinstance(entry, dict) and isinstance(entry.get('payload'), dict):
            entries.append(entry)
    owned = parent in Path(path).name or any(
        entry.get('type') == 'session_meta' and entry['payload'].get('id') == parent for entry in entries)
    if not owned:
        return []
    spawns, outputs = [], {}
    for entry in entries:
        payload = entry['payload']
        if entry.get('type') != 'response_item':
            continue
        if payload.get('type') == 'function_call' and payload.get('name') == 'spawn_agent':
            spawns.append(payload.get('call_id'))
        elif payload.get('type') == 'function_call_output':
            outputs[payload.get('call_id')] = tool_output(payload.get('output'))
    return [call for call in spawns if call is not None and outputs.get(call, '').startswith(LIMIT_REFUSAL)]


def refused_spawns(events, threads, parent):
    """Refused spawns and their call ids, read only from the parent's rollout file.

    Codex 0.163.0 writes no spawn record to the CLI stream (`events`) or the saved turns,
    refused or not, and those records would not say why a spawn failed, so neither counts.
    """
    path = threads.get(parent, {}).get('path') if parent else None
    calls = rollout_refusals(path, parent) if path else []
    return len(calls), calls


def thread_cap(peak, collected, refused, configured):
    """Judge agents.max_threads only from an actual refusal or children above it. Returns (capability or None, detail)."""
    detail = ('configured agents.max_threads=%d; requested %d children at once; collected %d; '
              'peak concurrent children %s; refused spawns %d' % (configured, configured + 1, collected, peak, refused))
    if peak is None:
        return None, detail + '; persisted turns carry no timing'
    if peak > configured:
        return cap('failed', detail + '; children exceeded the configured cap'), detail
    if refused and peak == configured:
        return cap('verified', detail + '; the host refused a spawn with the cap full of children, '
                   'so the cap counts child threads only', counts='children'), detail
    # A finished child still counts against the cap until it is closed, so a low peak alone
    # cannot show the parent counts. Only a run whose sole child stayed alone can.
    if refused and peak == collected == configured - 1:
        return cap('verified', detail + '; the host refused a spawn while its only child was open, '
                   'so the cap also counts the parent', counts='including_parent'), detail
    return None, detail + '; no refusal at a full cap and no child above it, so the cap stays unknown'


def probe(executable, out, model, reasoning='medium', timeout=120, prepare=None, permission_config=None,
          config_args=None, case=None):
    """Probe one host executable. `prepare`, `permission_config` and `config_args` come from run.py."""
    out = Path(out)
    out.mkdir(parents=False, exist_ok=False)
    executable = Path(executable).resolve()
    record = {'schema_version': 1, 'host': None, 'platform': 'linux', 'recorded_at': None,
              'source': 'run.py --probe-host', 'requested_model': model, 'reported_model': None,
              'actual_model': None, 'model_invocations': 0, 'timeout_seconds': timeout,
              'capabilities': {}, 'probes': [], 'unknown': []}
    caps = record['capabilities']
    version = subprocess.check_output([str(executable), '--version'], text=True, timeout=20).strip()
    record['host'] = version
    caps['installation'] = cap('verified', '%s --version: %s' % (executable.name, version))
    work, _ = prepare(case, out, condition={'kind': 'none', 'inventory': {}, 'entrypoint': None})
    config = permission_config(work, executable)
    listener = probes.Listener()
    try:
        nonce = probes.new_nonce()
        probes.install(work, out / 'probe-canary', listener.port, nonce)
        # Containment through the host sandbox, before any model call.
        sandbox = [str(executable), 'sandbox', '-P', 'mana-eval', '-C', str(work), *config_args(config),
                   '--', '/usr/bin/python3', 'bin/probe.py', 'sandbox']
        result = subprocess.run(sandbox, capture_output=True, text=True, timeout=30)
        command = {'command': 'python3 bin/probe.py sandbox', 'aggregated_output': result.stdout,
                   'exit_code': result.returncode}
        observed, failures = probes.verify([command], nonce, work)
        raw = probes.parse(result.stdout) or {}
        inbound = listener.inbound()
        record['probes'].append({'name': 'sandbox-containment', 'observation': raw, 'exit_code': result.returncode,
                                 'failures': failures, 'listener_inbound_connections': inbound,
                                 'listener_reachable_from_evaluator': listener.reachable})
        evidence = 'sandbox probe: ' + json.dumps(raw, sort_keys=True)
        caps['outside_read_denied'] = cap('verified' if raw.get('outside_read') == 'denied' else 'failed', evidence)
        protected = raw.get('protected_write', {})
        caps['protected_write_denied'] = cap('verified' if protected and set(protected.values()) == {'denied'} else 'failed', evidence)
        artifact = work / 'artifacts' / ('probe-sandbox-' + nonce)
        caps['fixture_write_allowed'] = cap('verified' if raw.get('fixture_write') == 'allowed' and artifact.is_file() else 'failed', evidence)
        caps['network_denied'] = cap('verified' if raw.get('network') == 'denied' and inbound == 0 else 'failed',
                                     evidence + '; evaluator listener inbound connections: %d' % inbound)
        # Family termination through the host sandbox wrapper, still without a model call.
        token = 'mana-family-' + probes.new_nonce()
        termination = [str(executable), 'sandbox', '-P', 'mana-eval', '-C', str(work), *config_args(config),
                       '--', '/usr/bin/python3', '-c', DAEMON % token]
        with (out / 'termination.out').open('w') as stdout, (out / 'termination.err').open('w') as stderr:
            invocation = process_family.run_bounded(termination, '', stdout, stderr, 3)
        beat = work / 'artifacts' / ('heartbeat-' + token)
        first = heartbeat(beat)
        time.sleep(1.0)
        second = heartbeat(beat)
        leftovers = token_processes(token)
        started = first is not None and first > 0
        advancing = started and second != first
        record['probes'].append({'name': 'process-family-termination', 'invocation': invocation,
                                 'grandchild_started': started, 'heartbeat_after_sweep': [first, second],
                                 'token_processes_after_sweep': leftovers})
        terminated = (invocation['outcome'] == 'timeout' and invocation['family_terminated'] and started
                      and not advancing and not leftovers)
        caps['process_family_termination'] = cap(
            'verified' if terminated else 'failed',
            'sandboxed setsid grandchild: outcome %s, started %s, heartbeat after sweep %s then %s, '
            'token processes alive %s, sweep surviving pids %s' % (
                invocation['outcome'], started, first, second, leftovers, invocation['surviving_pids']))
        if not all(caps[k]['status'] == 'verified' for k in ('outside_read_denied', 'protected_write_denied',
                                                               'fixture_write_allowed', 'network_denied')):
            record['unknown'].append('model probe skipped: sandbox containment failed, so no model call was made')
            return finish(record, out)
        # One bounded model invocation for events, completion, usage, descendants and the thread cap.
        limits = {'max_active_threads': CAP + 1, 'max_children': CAP + 1, 'nested': False}
        config += delegation.host_config(limits, model, reasoning, thread_cap=CAP)
        command = [str(executable), 'exec', '--ignore-user-config', '--ignore-rules', '--json', '--color', 'never',
                   '-C', str(work), *config_args(config), '--output-schema', str(Path(__file__).resolve().parent / 'response-schema.json'),
                   '-o', str(out / 'response.json'), '-']
        prompt = PROMPT % {'children': CAP + 1}
        (out / 'prompt.txt').write_text(prompt)
        record['model_invocations'] = 1
        with (out / 'events.jsonl').open('w') as stdout, (out / 'stderr.txt').open('w') as stderr:
            invocation = process_family.run_bounded(command, prompt, stdout, stderr, timeout)
        events, event_failures = conditions.parse_events((out / 'events.jsonl').read_text())
        parent_commands = [e['item'] for e in events if e.get('type') == 'item.completed'
                           and e.get('item', {}).get('type') == 'command_execution']
        usage = [e for e in events if e.get('type') == 'turn.completed'] or None
        response_ok = False
        try:
            response = json.loads((out / 'response.json').read_text())
            response_ok = isinstance(response.get('report'), str) and isinstance(response.get('checks'), list)
        except (OSError, ValueError, AttributeError):
            pass
        record['probes'].append({'name': 'model-events', 'invocation': invocation, 'event_failures': event_failures,
                                 'parent_commands': len(parent_commands), 'usage': usage, 'structured_response': response_ok})
        events_evidence = 'model probe: %d parent command events, %d malformed events' % (len(parent_commands), len(event_failures))
        caps['command_events'] = cap('verified' if parent_commands and not event_failures else 'failed', events_evidence)
        caps['usage_events'] = cap('verified' if usage and not event_failures else 'failed',
                                   'model probe turn.completed usage: ' + json.dumps(usage))
        completed = invocation['outcome'] == 'completed' and invocation['exit_code'] == 0 and response_ok
        caps['completion_detection'] = cap('verified' if completed else 'failed',
                                           'model probe outcome %s exit %s structured response %s' % (
                                               invocation['outcome'], invocation['exit_code'], response_ok))
        family = delegation.collect(executable, out, events, work, nonce, limits, model)
        record['reported_model'] = family['reported_model']
        record['probes'].append({'name': 'descendants', 'children': family['children'], 'nested': family['nested'],
                                 'threads': family['threads'], 'failures': family['failures'],
                                 'listener_inbound_connections': listener.inbound()})
        children = family['children'] or 0
        child_probes = [v for k, v in family['probes'].items() if k != family['parent_thread']]
        caps['descendant_collection'] = cap('verified' if children and not family['failures'] else 'failed',
                                            'collected %d children; failures: %s' % (children, family['failures']))
        caps['thread_attribution'] = cap('verified' if children and all(child_probes) and not family['failures'] else 'failed',
                                         'per-thread probe observations: ' + json.dumps(family['probes'], sort_keys=True))
        caps['child_containment'] = cap('verified' if children and len(child_probes) == children and all(child_probes) else 'failed',
                                        'child probes verified: %d of %d' % (sum(1 for p in child_probes if p), children))
        if family['reported_model'] is None:
            caps['model_selection'] = cap('unavailable', 'host reported no model for the probe threads')
        else:
            caps['model_selection'] = cap('verified' if family['reported_model'] == model else 'failed',
                                          'requested %s; host reported %s' % (model, family['reported_model']),
                                          'host-reported metadata only; backend identity unresolved')
        threads_path = out / 'threads.json'
        threads = json.loads(threads_path.read_text()) if threads_path.is_file() else {}
        peak = child_peak(threads, family['parent_thread']) if threads else None
        refused, refusals = refused_spawns(events, threads, family['parent_thread'])
        verdict, detail = thread_cap(peak, children, refused, CAP)
        record['probes'].append({'name': 'thread-cap', 'detail': detail, 'peak_children': peak,
                                 'collected_children': children, 'refused_spawns': refused,
                                 'refused_spawn_calls': refusals})
        if verdict is None:
            record['unknown'].append('active_thread_cap: ' + detail)
        else:
            caps['active_thread_cap'] = verdict
    finally:
        listener.close()
    return finish(record, out)


def finish(record, out):
    record['recorded_at'] = process_family.now()
    # Sanitize local paths. Evidence names the probe directory, never the operator's machine layout.
    text = json.dumps(record, indent=2, sort_keys=True).replace(str(out.resolve()), '<probe-dir>')
    (out / 'host-evidence.json').write_text(text + '\n')
    return json.loads(text)
