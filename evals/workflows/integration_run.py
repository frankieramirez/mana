"""Live attempts and the no-model sandbox preflight for a frozen paired integration study, ticket 112.

Every attempt and every preflight check runs inside one host sandbox profile, the same in both arms.
The consumer checkout, its home and temporary directories are writable; attachments, the Node install,
the browser builds and the host's own files are read-only; everything else is denied. The app's tests
start local servers, so loopback binding is allowed, while all other traffic goes through the host's
network proxy with no allowed domain. Dependencies install offline from the frozen npm cache before the
agent starts, outside the sandbox, identically for both arms.

`--sandbox-preflight` makes no model call: it builds one workspace per family and arm, runs the
containment probe and the family's declared checks, and compares their exits with the frozen
expectations. `--live` runs the schedule serially, one model invocation per slot, with no retries.
The study directory, and everything an attempt retains, stays outside the Mana checkout.
"""
import argparse
import json
import os
from pathlib import Path
import re
import shutil
import socket
import subprocess
import sys
import time

import conditions
import delegation
import integration
import process_family

HERE = Path(__file__).resolve().parent
SPAWN_FAILURE = re.compile(r'collab spawn failed')
SUFFIX = ('\n\nKeep the normal report inside the response schema\'s report field. '
          'List checks actually attempted or left unverified in checks. Do not delegate.')
# Execution states that end the group. A timeout is a measured outcome and the next slot still runs.
STOP_EXECUTIONS = ('setup_failed', 'collection_failed', 'agent_failed', 'cancelled')


def agent_env(work, runtime):
    env = {'PATH': runtime['node'] + '/bin:/usr/bin:/bin', 'HOME': str(work / 'home'), 'TMPDIR': str(work / 'tmp'),
           'LC_ALL': 'C.UTF-8', 'GIT_CONFIG_NOSYSTEM': '1', 'GIT_CONFIG_GLOBAL': '/dev/null',
           'PLAYWRIGHT_BROWSERS_PATH': runtime['browsers'], 'npm_config_cache': str(work / 'home' / '.npm'),
           'npm_config_prefer_offline': 'true', 'npm_config_update_notifier': 'false'}
    env.update(runtime['env'])
    return env


def toml_table(values):
    return '{ ' + ', '.join(json.dumps(k) + '=' + json.dumps(v) for k, v in values.items()) + ' }'


def sandbox_config(work, runtime):
    """One permission profile for every attempt and check in both arms."""
    filesystem = {':root': 'deny', ':minimal': 'read', str(work): 'write', str(work / 'attachments'): 'read',
                  runtime['node']: 'read', runtime['browsers']: 'read', str(Path(runtime['codex']).parent.parent): 'read'}
    return ['default_permissions="mana-eval"', 'approval_policy="never"',
            'permissions.mana-eval.filesystem=' + toml_table(filesystem),
            'permissions.mana-eval.network.enabled=true', 'permissions.mana-eval.network.allow_local_binding=true',
            'permissions.mana-eval.network.domains={}', 'features.network_proxy=true',
            'shell_environment_policy.inherit="none"',
            'shell_environment_policy.set=' + toml_table(agent_env(work, runtime))]


def host_config(model, reasoning):
    """The focused host settings, except that project docs load: the Control pointer lives in AGENTS.md."""
    return [value for value in delegation.host_config(None, model, reasoning) if value != 'project_doc_max_bytes=0']


def config_args(values):
    return [part for value in values for part in ('-c', value)]


def git(work, *args):
    return subprocess.run(['git', '-C', str(work), *args], capture_output=True, text=True,
                          env=integration.git_env(), timeout=120)


def state(consumer):
    """HEAD, the index and the status, including untracked files and ignored dependencies left out."""
    status = git(consumer, 'status', '--porcelain=v1', '-z', '--untracked-files=all')
    index = consumer / '.git' / 'index'
    return {'head': git(consumer, 'rev-parse', 'HEAD').stdout.strip(),
            'status_sha256': conditions.digest(status.stdout.encode()),
            'index_sha256': conditions.digest(index.read_bytes()) if index.is_file() else None}


def workspace(study, slot, out, runtime):
    """Rebuild the slot's fixture, place attachments and the npm cache, and install dependencies offline."""
    work = out / 'work'
    cell, built = study.fixture(slot, work / 'consumer')
    for name in ('home', 'tmp', 'attachments'):
        (work / name).mkdir(parents=True, exist_ok=True)
    subprocess.run(['cp', '-a', '--reflink=auto', runtime['npm_cache'], str(work / 'home' / '.npm')], check=True, timeout=600)
    family = study.controls['families'][cell['family']]
    for attachment in family['attachments']:
        target = work / 'attachments' / Path(attachment['path']).name
        shutil.copy2(study.root / 'families' / family['id'] / attachment['path'], target)
        target.chmod(0o444)
    with (out / 'install.log').open('w') as log:
        installed = subprocess.run(study.controls['consumer']['install'], cwd=work / 'consumer', stdout=log,
                                   stderr=subprocess.STDOUT, env=agent_env(work, runtime), timeout=900)
    if installed.returncode:
        raise ValueError('offline dependency install exited %d' % installed.returncode)
    after = git(work / 'consumer', 'status', '--porcelain=v1', '-z', '--untracked-files=all').stdout.encode()
    if conditions.digest(after) != built['status_sha256']:
        raise ValueError('dependency install changed the fixture status')
    return cell, work


PROBE = r'''
import json, pathlib, socket, sys
canary, outside_port = sys.argv[1], int(sys.argv[2])
result = {}
result['outside_read'] = 'visible' if pathlib.Path(canary).exists() else 'denied'
pathlib.Path('../tmp/probe').write_text('allowed'); pathlib.Path('../tmp/probe').unlink(); result['workspace_write'] = 'allowed'
try:
    pathlib.Path('../attachments/probe').write_text('forbidden'); result['attachment_write'] = 'allowed'
except OSError:
    result['attachment_write'] = 'denied'
own = socket.socket(); own.bind(('127.0.0.1', 0)); own.listen(1)
client = socket.socket(); client.settimeout(3); client.connect(own.getsockname()); result['loopback'] = 'allowed'
for name, address in (('outside_listener', ('127.0.0.1', outside_port)), ('external', ('192.0.2.1', 443))):
    try:
        probe = socket.socket(); probe.settimeout(3); probe.connect(address); result[name] = 'connected'
    except OSError:
        result[name] = 'refused'
print(json.dumps(result))
'''
EXPECTED_PROBE = {'outside_read': 'denied', 'workspace_write': 'allowed', 'attachment_write': 'denied',
                  'loopback': 'allowed', 'outside_listener': 'refused', 'external': 'refused'}


def sandboxed(executable, work, runtime, argv, timeout, **kwargs):
    command = [str(executable), 'sandbox', '-P', 'mana-eval', '-C', str(work / 'consumer'),
               *config_args(sandbox_config(work, runtime)), '--', *argv]
    return subprocess.run(command, capture_output=True, text=True, timeout=timeout, **kwargs)


def probe(executable, work, runtime):
    """Containment through the same profile: denied outside reads, writes and network, allowed loopback."""
    canary = work.parent / 'outside-canary'
    canary.write_text('evaluator only, never visible to the agent')
    listener = socket.socket()
    listener.bind(('127.0.0.1', 0))
    listener.listen(4)
    listener.settimeout(0.2)
    try:
        result = sandboxed(executable, work, runtime, ['/usr/bin/python3', '-c', PROBE, str(canary),
                                                       str(listener.getsockname()[1])], 60)
        try:
            listener.accept()
            reached = True
        except OSError:
            reached = False
    finally:
        listener.close()
    try:
        observed = json.loads(result.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError):
        raise ValueError('containment probe failed: ' + (result.stderr or result.stdout)[-800:])
    if reached:
        observed['outside_listener'] = 'connected'
    if result.returncode or observed != EXPECTED_PROBE:
        raise ValueError('containment probe failed: ' + json.dumps(observed, sort_keys=True))
    return dict(observed, checked_at=process_family.now())


def executable_for(study):
    runtime = study.runtime()
    executable = Path(runtime['codex'])
    version = subprocess.run([str(executable), '--version'], capture_output=True, text=True, timeout=20).stdout.strip()
    if version != study.controls['host']:
        raise ValueError('host reports %r, not the frozen %r' % (version, study.controls['host']))
    return executable, runtime


def preflight(study, out):
    """No model call. One workspace per family and arm, the probe, then each declared check in the sandbox."""
    out = Path(out)
    integration.outside(out, integration.ROOT, 'sandbox preflight')
    out.mkdir(parents=False, exist_ok=False)
    executable, runtime = executable_for(study)
    rows = []
    for family_id, family in sorted(study.controls['families'].items()):
        for arm in integration.ARMS:
            slot = next(c['slot'] for c in study.schedule if (c['family'], c['arm']) == (family_id, arm))
            cell_dir = out / ('%s-%s' % (family_id, arm))
            cell_dir.mkdir()
            row = {'family': family_id, 'arm': arm, 'checks': [], 'failures': []}
            try:
                _, work = workspace(study, slot, cell_dir, runtime)
                row['probe'] = probe(executable, work, runtime)
                before = state(work / 'consumer')
                row['head'] = before['head']
                for index, check in enumerate(c for c in family['checks'] if arm in c['arms']):
                    started = time.monotonic()
                    result = sandboxed(executable, work, runtime, check['argv'], study.controls['timeout_seconds'])
                    (cell_dir / ('check-%02d.out' % index)).write_text(result.stdout)
                    (cell_dir / ('check-%02d.err' % index)).write_text(result.stderr)
                    row['checks'].append({'index': index, 'expected_exit': check['exit'], 'exit': result.returncode,
                                          'seconds': round(time.monotonic() - started, 1)})
                    if result.returncode != check['exit']:
                        row['failures'].append('check %d exited %d, expected %d' % (index, result.returncode, check['exit']))
                if state(work / 'consumer') != before:
                    row['failures'].append('a check changed the checkout')
            except (OSError, ValueError, subprocess.SubprocessError) as exc:
                row['failures'].append(str(exc))
            rows.append(row)
    record = {'schema_version': 1, 'study': study.controls['study'], 'controls_sha256': study.expected_digest,
              'kind': 'no-model sandbox preflight', 'model_invocations': 0, 'host': study.controls['host'],
              'ran_at': process_family.now(), 'passed': all(not r['failures'] for r in rows), 'cells': rows}
    (out / 'preflight.json').write_text(json.dumps(record, indent=2, sort_keys=True) + '\n')
    return record


def children(events, stderr):
    """A failed spawn is an attempted delegation; a collaboration call that names a thread is a created child."""
    created, empty_waits = [], 0
    for event in events:
        item = event.get('item') or {}
        if event.get('type') != 'item.completed' or item.get('type') != 'collab_tool_call':
            continue
        receivers = item.get('receiver_thread_ids') or []
        if item.get('tool') == 'wait' and not receivers:
            empty_waits += 1
        created += [r for r in receivers if r not in created]
    failed = [line.strip()[-300:] for line in stderr.splitlines() if SPAWN_FAILURE.search(line)]
    return {'judgment': 'created' if created else 'attempted' if failed else 'none',
            'created': created, 'failed_spawns': failed, 'empty_waits': empty_waits}


def prompt(study, cell, work):
    family = study.controls['families'][cell['family']]
    request = (study.root / 'families' / family['id'] / 'request.txt').read_text()
    return 'Use the instructions at %s.\n%s%s' % (work / 'consumer' / family['entrypoint'], request.rstrip('\n'), SUFFIX)


def run_slot(study, slot):
    """One model invocation for one allocated slot. The task outcome is graded later by a person."""
    out = study.claim(slot)
    cell = study.schedule[slot - 1]
    family = study.controls['families'][cell['family']]
    result = {'schema_version': 1, 'study': study.controls['study'], 'controls_sha256': study.expected_digest,
              'schedule_slot': slot, **{k: cell[k] for k in ('family', 'arm', 'repetition')},
              'source_group': family['source_group'], 'request_sha256': family['request_sha256'],
              'host': study.controls['host'], 'requested_model': study.controls['model'],
              'reasoning': study.controls['reasoning'], 'reported_model': None, 'actual_model': None,
              'timeout_seconds': study.controls['timeout_seconds'], 'retry_attempts': 0,
              'execution': 'setup_failed', 'task_outcome': None, 'failures': [],
              'human_review': {'active_seconds': None, 'censored': None}, 'started_at': process_family.now()}
    started = time.monotonic()
    work = initial = None
    try:
        executable, runtime = executable_for(study)
        cell, work = workspace(study, slot, out, runtime)
        initial = state(work / 'consumer')
        result['initial_state'] = initial
        result['isolation'] = probe(executable, work, runtime)
        text = prompt(study, cell, work)
        (out / 'prompt.txt').write_text(text)
        command = [str(executable), 'exec', '--ignore-user-config', '--ignore-rules', '--ephemeral', '--json',
                   '--color', 'never', '-C', str(work / 'consumer'),
                   *config_args(sandbox_config(work, runtime) + host_config(study.controls['model'], study.controls['reasoning'])),
                   '--output-schema', str(study.root / 'runner-source' / 'response-schema.json'),
                   '-o', str(out / 'response.json'), '-']
        result['command'] = command
        study.verify()
        with (out / 'events.jsonl').open('w') as stdout, (out / 'stderr.txt').open('w') as stderr:
            invocation = process_family.run_bounded(command, text, stdout, stderr, study.controls['timeout_seconds'])
        result['process_family'] = invocation
        result['model_invocations'] = 1
        if invocation['outcome'] == 'completed':
            result['execution'] = 'completed' if invocation['exit_code'] == 0 else 'agent_failed'
        else:
            result['execution'] = 'timeout' if invocation['outcome'] == 'timeout' else 'cancelled'
        if not invocation['family_terminated']:
            result['failures'].append('process family survived termination')
        events, event_failures = conditions.parse_events((out / 'events.jsonl').read_text())
        if event_failures:
            result['failures'] += event_failures
            if result['execution'] == 'completed':
                result['execution'] = 'collection_failed'
        result['children'] = children(events, (out / 'stderr.txt').read_text())
        result['reported_model'] = next((e['model'] for e in events if isinstance(e.get('model'), str)), None)
        result['usage'] = [e['usage'] for e in events if e.get('type') == 'turn.completed'] or None
        result['commands'] = sum(1 for e in events if e.get('type') == 'item.completed'
                                 and (e.get('item') or {}).get('type') == 'command_execution')
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        result['failures'].append(str(exc))
        result.setdefault('model_invocations', 0)
    finally:
        if work is not None and initial is not None:
            consumer = work / 'consumer'
            result['final_state'] = state(consumer)
            result['new_commits'] = git(consumer, 'log', '--format=%H %s', initial['head'] + '..HEAD').stdout.splitlines()
            (out / 'final.diff').write_text(git(consumer, 'diff', initial['head']).stdout)
        try:
            study.verify()
        except (OSError, ValueError) as exc:
            result['failures'].append('frozen study invalid after the attempt: %s' % exc)
        result['seconds'] = round(time.monotonic() - started, 2)
        result['ended_at'] = process_family.now()
        result['stop_reason'] = stop_reason(result)
        (out / 'result.json').write_text(json.dumps(result, indent=2, sort_keys=True) + '\n')
        if result['stop_reason']:
            (study.root / 'results' / 'STOP.json').write_text(json.dumps({'slot': slot, 'reason': result['stop_reason']}) + '\n')
        study.release()
    return result


def stop_reason(result):
    if result['failures']:
        return 'slot %d: %s' % (result['schedule_slot'], '; '.join(result['failures'])[:600])
    if result['execution'] in STOP_EXECUTIONS:
        return 'slot %d: %s' % (result['schedule_slot'], result['execution'])
    if (result.get('children') or {}).get('judgment') == 'created':
        return 'slot %d: a child thread was created, so the zero-child bound no longer holds' % result['schedule_slot']
    return None


def run_all(study):
    """Every remaining slot in order until the schedule ends or a stop. Never retries a slot."""
    rows = []
    for cell in study.schedule:
        if (study.root / 'results' / 'STOP.json').exists():
            break
        if (study.root / 'results' / ('%03d' % cell['slot']) / 'result.json').is_file():
            continue
        result = run_slot(study, cell['slot'])
        rows.append({k: result.get(k) for k in ('schedule_slot', 'family', 'arm', 'repetition', 'execution', 'stop_reason')})
    return rows


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--study', type=Path, required=True)
    parser.add_argument('--controls-sha256', required=True)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument('--sandbox-preflight', type=Path, metavar='OUT', help='no-model checks in a new directory')
    action.add_argument('--live', action='store_true', help='run the remaining slots serially; calls the model')
    parser.add_argument('--slot', type=int, help='with --live, run only this slot')
    args = parser.parse_args(argv)
    try:
        study = integration.FrozenIntegration(args.study, args.controls_sha256)
        if args.sandbox_preflight:
            result = preflight(study, args.sandbox_preflight)
            code = 0 if result['passed'] else 1
        else:
            result = run_slot(study, args.slot) if args.slot else run_all(study)
            code = 0
    except (OSError, ValueError, KeyError) as exc:
        print('integration_run: ' + str(exc), file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2, sort_keys=True))
    return code


if __name__ == '__main__':
    sys.exit(main())
