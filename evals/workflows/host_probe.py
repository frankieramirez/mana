"""Record host capability evidence from actual probes. One bounded model call at most.

The probe writes a candidate evidence record. A maintainer reviews it and
copies it into host-evidence/ to change what the registry accepts. A failed or
unobserved capability stays failed or unknown; nothing is inferred.
"""
import json
from pathlib import Path
import re
import subprocess
import threading
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
# The model probe asks for one child more than agents.max_threads allows and holds every child
# open at a gate that the evaluator releases only after the spawn attempts are over. The run then
# shows either more children open at once than the cap or a refused spawn. Anything else stays unknown.
CAP = 2
PROMPT = '''This is a host capability probe. All files are synthetic fixtures.
1. Run exactly: python3 bin/probe.py parent
2. Spawn %(children)d child agents, one spawn call per child. Issue all %(children)d spawn calls before you wait on any child. Give child N, for N from 1 to %(children)d, these instructions: "Run exactly python3 bin/probe.py child-N. Then run exactly python3 bin/gate.py child-N with a command timeout of at least 120 seconds. It blocks until the evaluator releases it. If it ends without printing MANA-GATE released, run it again. Do not start other agents. Then report both outputs." If the host refuses a spawn, do not retry it.
3. When every spawn call has returned, run exactly: python3 bin/gate.py spawned
4. Wait for every child that started. Then return the response schema with report set to "probe complete" and checks listing each command you ran with its exit code, plus one entry for each refused spawn.
Do not run any other command and do not edit files.'''
GATE = '''import pathlib, re, sys, time
NONCE = %(nonce)r
LIMIT = %(limit)d
label = sys.argv[1] if len(sys.argv) == 2 else ''
if not re.fullmatch(r'[a-z0-9][a-z0-9_-]{0,39}', label):
    sys.exit('usage: python3 bin/gate.py LABEL')
root = pathlib.Path('artifacts')
if label == 'spawned':
    (root / ('gate-spawned-' + NONCE)).write_text('spawned')
    print('MANA-GATE spawned', flush=True)
    sys.exit(0)
beat = root / ('gate-held-' + label + '-' + NONCE)
release = root / ('gate-release-' + NONCE)
deadline = time.time() + LIMIT
count = 0
while time.time() < deadline:
    if release.exists():
        (root / ('gate-left-' + label + '-' + NONCE)).write_text('left')
        print('MANA-GATE released ' + label, flush=True)
        sys.exit(0)
    count += 1
    beat.write_text(str(count))
    time.sleep(0.2)
print('MANA-GATE timeout ' + label, flush=True)
sys.exit(3)
'''
# Rollout outputs count as a refusal only when the host's text names the limit.
REFUSAL_TEXT = re.compile(r'(agent|thread)[^\n]{0,40}limit|limit[^\n]{0,40}(agent|thread)|max_threads', re.I)


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


class Gate:
    """Watch the children's gate heartbeats and release them once the spawn attempts are over.

    A child counts as held while its heartbeat file keeps changing and it has not left.
    Release happens when more children are held than the cap, when the parent signalled that
    every spawn call returned and the held set stayed the same for `settle` seconds, or at
    `deadline` seconds after start.
    """

    def __init__(self, work, nonce, cap, settle=20.0, deadline=75.0, poll=0.2, fresh=1.5):
        self.root = Path(work) / 'artifacts'
        self.nonce, self.cap = nonce, cap
        self.settle, self.deadline, self.poll, self.fresh = settle, deadline, poll, fresh
        self.beats = {}
        self.entered = set()
        self.peak, self.peak_labels = 0, []
        self.result = None
        self.stopping = threading.Event()
        self.thread = threading.Thread(target=self.run, daemon=True)

    def install(self, work, limit):
        path = Path(work) / 'bin' / 'gate.py'
        path.write_text(GATE % {'nonce': self.nonce, 'limit': limit})
        path.chmod(0o555)
        return path

    def held(self, now):
        found = set()
        suffix = '-' + self.nonce
        for path in self.root.glob('gate-held-*' + suffix):
            label = path.name[len('gate-held-'):-len(suffix)]
            try:
                value = path.read_text()
            except OSError:
                continue
            if self.beats.get(label, (None,))[0] != value:
                self.beats[label] = (value, now)
            self.entered.add(label)
            left = (self.root / ('gate-left-' + label + suffix)).exists()
            if not left and now - self.beats[label][1] <= self.fresh:
                found.add(label)
        return found

    def run(self):
        started = time.monotonic()
        previous, since = None, started
        while not self.stopping.is_set():
            now = time.monotonic()
            held = self.held(now)
            if len(held) > self.peak:
                self.peak, self.peak_labels = len(held), sorted(held)
            if held != previous:
                previous, since = held, now
            spawned = (self.root / ('gate-spawned-' + self.nonce)).exists()
            if len(held) > self.cap:
                return self.release('more children held at once than the cap', held, spawned, started)
            if spawned and now - since >= self.settle:
                return self.release('every spawn call returned and the held set settled', held, spawned, started)
            if now - started >= self.deadline:
                return self.release('deadline', held, spawned, started)
            self.stopping.wait(self.poll)

    def release(self, reason, held, spawned, started):
        (self.root / ('gate-release-' + self.nonce)).write_text('release')
        self.result = {'reason': reason, 'released_after_seconds': round(time.monotonic() - started, 1),
                       'held_at_release': sorted(held), 'spawned_signal': spawned}

    def start(self):
        self.thread.start()

    def stop(self):
        self.stopping.set()
        self.thread.join()
        if self.result is None:
            self.release('host exited before release', set(), (self.root / ('gate-spawned-' + self.nonce)).exists(),
                         time.monotonic())
        return dict(self.result, peak_held=self.peak, peak_labels=self.peak_labels, entered=sorted(self.entered))


def rollout_spawns(path):
    """spawn_agent calls and their outputs from the host's own rollout file for the parent thread."""
    calls, outputs = {}, {}
    try:
        lines = Path(path).read_text().splitlines()
    except (OSError, TypeError, ValueError):
        return None
    for line in lines:
        try:
            entry = json.loads(line)
        except ValueError:
            continue
        payload = entry.get('payload') if isinstance(entry, dict) and entry.get('type') == 'response_item' else entry
        if not isinstance(payload, dict):
            continue
        if payload.get('type') == 'function_call' and payload.get('name') == 'spawn_agent':
            calls[payload.get('call_id')] = True
        elif payload.get('type') == 'function_call_output':
            output = payload.get('output')
            if isinstance(output, dict):
                output = output.get('content') if isinstance(output.get('content'), str) else json.dumps(output)
            outputs[payload.get('call_id')] = output if isinstance(output, str) else json.dumps(output)
    return [{'call_id': call, 'output': outputs.get(call)} for call in calls]


def spawn_refusals(events, threads, parent):
    """Count refused spawns from explicit host records only. Returns (count, evidence by source).

    Sources: a failed `collab_tool_call` with tool `spawn_agent` in the CLI stream, a failed
    `collabAgentToolCall` with tool `spawnAgent` in the parent's persisted turns, and a
    `spawn_agent` call in the parent's rollout whose output names an agent or thread limit.
    Other failed items, whatever their type mentions, never count.
    """
    found = {'stream': [], 'history': [], 'rollout': []}
    for event in events:
        item = event.get('item') if isinstance(event, dict) and event.get('type') == 'item.completed' else None
        if (isinstance(item, dict) and item.get('type') == 'collab_tool_call' and item.get('tool') == 'spawn_agent'
                and item.get('status') == 'failed' and not item.get('receiver_thread_ids')):
            found['stream'].append(item.get('id'))
    thread = threads.get(parent, {})
    for turn in thread.get('turns', []):
        for item in turn.get('items', []):
            if (isinstance(item, dict) and item.get('type') == 'collabAgentToolCall'
                    and item.get('tool') in ('spawnAgent', 'spawn_agent') and item.get('status') == 'failed'
                    and not item.get('receiverThreadIds')):
                found['history'].append(item.get('id'))
    spawns = rollout_spawns(thread.get('path')) if thread.get('path') else None
    children = {identity for identity in threads if identity != parent}
    for call in spawns or []:
        output = call['output'] or ''
        if REFUSAL_TEXT.search(output) and not any(identity in output for identity in children):
            found['rollout'].append(call['call_id'])
    # The same refusal can appear in several records, so the largest single source is the count.
    shown = None if spawns is None else [{'call_id': c['call_id'], 'output': (c['output'] or '')[:300]} for c in spawns]
    return max(len(ids) for ids in found.values()), {'by_source': found, 'rollout_spawn_calls': shown}


def thread_cap(peak, held, collected, refused, configured):
    """Judge agents.max_threads only from a decisive gate run. Returns (capability or None, detail)."""
    detail = ('configured agents.max_threads=%d; asked for %d children held open at once; peak children held at '
              'the gate %s; held at release %s; collected %d; explicit spawn refusals %d' % (
                  configured, configured + 1, peak, held, collected, refused))
    if peak is None:
        return None, detail + '; no gate observation'
    if peak > configured:
        return cap('failed', detail + '; children exceeded the configured cap'), detail
    if refused and peak == held == collected == configured:
        return cap('verified', detail + '; the host refused a spawn with the cap full of children, '
                   'so the cap counts child threads only', counts='children'), detail
    if refused and peak == held == collected == configured - 1:
        return cap('verified', detail + '; the host refused a spawn with one child open, '
                   'so the cap also counts the parent', counts='including_parent'), detail
    if collected > peak:
        return None, detail + '; children ran staggered without a recorded refusal, so the cap stays unknown'
    return None, detail + '; the cap was not challenged, so its meaning stays unknown'


def probe(executable, out, model, reasoning='medium', timeout=120, prepare=None, permission_config=None,
          config_args=None, case=None, settle=20.0):
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
        # Children wait at the gate for at most the run's own timeout; the evaluator releases them sooner.
        gate = Gate(work, nonce, CAP, settle=settle, deadline=max(settle + 5, timeout * 0.6))
        gate.install(work, int(timeout))
        record['model_invocations'] = 1
        gate.start()
        try:
            with (out / 'events.jsonl').open('w') as stdout, (out / 'stderr.txt').open('w') as stderr:
                invocation = process_family.run_bounded(command, prompt, stdout, stderr, timeout)
        finally:
            observation = gate.stop()
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
        refused, refusals = spawn_refusals(events, threads, family['parent_thread'])
        held = len(observation['held_at_release'])
        verdict, detail = thread_cap(observation['peak_held'], held, children, refused, CAP)
        if family['failures'] and verdict is not None and verdict['status'] == 'verified':
            verdict, detail = None, detail + '; descendant collection failed, so the run cannot verify the cap'
        record['probes'].append({'name': 'thread-cap', 'detail': detail, 'gate': observation,
                                 'collected_children': children, 'refused_spawns': refused, 'refusals': refusals})
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
