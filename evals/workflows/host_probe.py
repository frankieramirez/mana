"""Record host capability evidence from actual probes. One bounded model call at most.

The probe writes a candidate evidence record. A maintainer reviews it and
copies it into host-evidence/ to change what the registry accepts. A failed or
unobserved capability stays failed or unknown; nothing is inferred.
"""
import json
from pathlib import Path
import subprocess

import conditions
import delegation
import probes
import process_family

DAEMON = '''import os, pathlib, time
if os.fork() == 0:
    os.setsid()
    if os.fork() == 0:
        pathlib.Path('artifacts/daemon.pid').write_text(str(os.getpid()))
        time.sleep(300)
        os._exit(0)
    os._exit(0)
time.sleep(300)
'''
PROMPT = '''This is a host capability probe. All files are synthetic fixtures.
1. Run exactly: python3 bin/probe.py parent
2. Start exactly %(children)d child agents at the same time. Tell each child to run exactly python3 bin/probe.py child-N, with N its number starting at 1, and then report the output. Children must not start other children.
3. Wait for every child, then return the response schema with report set to "probe complete" and checks listing each probe command and its exit code.
Do not run any other command and do not edit files.'''


def cap(status, evidence, notes=None):
    value = {'status': status, 'observed_at': process_family.now(), 'evidence': [evidence]}
    if notes:
        value['notes'] = notes
    return value


def alive(pid):
    try:
        stat = Path('/proc/%d/stat' % pid).read_text()
    except OSError:
        return False
    return stat[stat.rindex(')') + 2:].split()[0] != 'Z'


def overlap(threads, cap_value):
    """Maximum concurrently active threads from persisted turn timing, or None when absent."""
    spans = []
    for thread in threads.values():
        for turn in thread.get('turns', []):
            start = turn.get('startedAt', turn.get('createdAt'))
            end = turn.get('completedAt', turn.get('updatedAt'))
            if not isinstance(start, (int, float)) or not isinstance(end, (int, float)):
                return None
            spans.append((start, end))
    points = sorted([(s, 1) for s, _ in spans] + [(e, -1) for _, e in spans])
    active = peak = 0
    for _, step in points:
        active += step
        peak = max(peak, active)
    return peak


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
        termination = [str(executable), 'sandbox', '-P', 'mana-eval', '-C', str(work), *config_args(config),
                       '--', '/usr/bin/python3', '-c', DAEMON]
        with (out / 'termination.out').open('w') as stdout, (out / 'termination.err').open('w') as stderr:
            invocation = process_family.run_bounded(termination, '', stdout, stderr, 3)
        pidfile = work / 'artifacts' / 'daemon.pid'
        daemon = int(pidfile.read_text()) if pidfile.is_file() else None
        survived = daemon is not None and alive(daemon)
        record['probes'].append({'name': 'process-family-termination', 'invocation': invocation,
                                 'daemon_pid_recorded': daemon is not None, 'daemon_survived': survived})
        terminated = invocation['outcome'] == 'timeout' and invocation['family_terminated'] and daemon is not None and not survived
        caps['process_family_termination'] = cap('verified' if terminated else 'failed',
            'sandboxed setsid grandchild: outcome %s, recorded %s, survived %s, surviving pids %s' % (
                invocation['outcome'], daemon is not None, survived, invocation['surviving_pids']))
        if not all(caps[k]['status'] == 'verified' for k in ('outside_read_denied', 'protected_write_denied',
                                                               'fixture_write_allowed', 'network_denied')):
            record['unknown'].append('model probe skipped: sandbox containment failed, so no model call was made')
            return finish(record, out)
        # One bounded model invocation for events, completion, usage and descendants.
        limits = {'max_active_threads': 2, 'max_children': 2, 'nested': False}
        config += delegation.host_config(limits, model, reasoning)
        command = [str(executable), 'exec', '--ignore-user-config', '--ignore-rules', '--json', '--color', 'never',
                   '-C', str(work), *config_args(config), '--output-schema', str(Path(__file__).resolve().parent / 'response-schema.json'),
                   '-o', str(out / 'response.json'), '-']
        prompt = PROMPT % {'children': limits['max_children']}
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
        peak = overlap(json.loads(threads_path.read_text()), limits['max_active_threads']) if threads_path.is_file() else None
        if peak is None:
            record['unknown'].append('active_thread_cap: persisted turns carry no timing, so concurrency was not observed')
        else:
            caps['active_thread_cap'] = cap('verified' if peak <= limits['max_active_threads'] and children >= 1 else 'failed',
                                            'configured %d active threads; observed peak %d with %d children requested' % (
                                                limits['max_active_threads'], peak, limits['max_children']))
    finally:
        listener.close()
    return finish(record, out)


def finish(record, out):
    record['recorded_at'] = process_family.now()
    # Sanitize local paths. Evidence names the probe directory, never the operator's machine layout.
    text = json.dumps(record, indent=2, sort_keys=True).replace(str(out.resolve()), '<probe-dir>')
    (out / 'host-evidence.json').write_text(text + '\n')
    return json.loads(text)
