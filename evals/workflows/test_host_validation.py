"""Host registry, isolation probes, family termination and delegated collection, offline.

Every host here is fake_host.py. No model is invoked.
"""
import copy
import datetime
import hashlib
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

import conditions
import delegation
import host_probe
import hosts
import probes
import process_family
import run

LINUX = sys.platform.startswith('linux')
FAKE = 'codex-cli 9.9.9-fake'
MODEL = 'gpt-6.1-sol'
LIMITS = {'max_active_threads': 4, 'max_children': 10, 'nested': False}


def alive(pid):
    try:
        state = Path('/proc/%d/stat' % pid).read_text()
    except OSError:
        return False
    return state[state.rindex(')') + 2:].split()[0] != 'Z'


def wait_for(path, seconds=10):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if path.is_file() and path.read_text().strip():
            return int(path.read_text())
        time.sleep(0.05)
    raise AssertionError('missing ' + str(path))


def verified_record(host=FAKE, at=None, **overrides):
    at = at or process_family.now()
    caps = {key: {'status': 'verified', 'observed_at': at, 'evidence': ['offline fixture probe']}
            for key in hosts.MODES['comparative-delegated']}
    caps['active_thread_cap']['counts'] = 'children'
    caps.update(overrides)
    return {'schema_version': 1, 'host': host, 'platform': 'linux', 'recorded_at': at,
            'source': 'offline test', 'capabilities': caps}


class FakeHost:
    """A temporary fake `codex` outside every workspace's readable roots."""

    def __init__(self, test, plan):
        self.dir = Path(tempfile.mkdtemp(prefix='mana-fake-host-'))
        test.addCleanup(shutil.rmtree, self.dir, True)
        (self.dir / 'bin').mkdir()
        self.executable = self.dir / 'bin' / 'codex'
        shutil.copy2(Path(run.HERE) / 'fake_host.py', self.executable)
        self.executable.chmod(0o755)
        self.state = self.dir / 'state'
        self.plan_path = self.dir / 'plan.json'
        self.write(plan)

    def write(self, plan):
        plan = dict({'version': FAKE, 'containment': 'enforced', 'reported_model': MODEL}, **plan)
        plan['state'] = str(self.state)
        self.plan_path.write_text(json.dumps(plan))

    def environment(self):
        return patch.dict(os.environ, {'MANA_FAKE_HOST_PLAN': str(self.plan_path)})

    def calls(self):
        return [json.loads(p.read_text()) for p in sorted(self.state.glob('exec-*.json'))]


class Registry(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.dir = Path(temp.name)

    def write(self, name, record):
        (self.dir / name).write_text(json.dumps(record))

    def test_accepted_hosts_are_derived_from_committed_evidence(self):
        # Recompute acceptance from the raw committed records, independently of hosts.assess.
        raw = [json.loads(path.read_text()) for path in sorted(hosts.EVIDENCE.glob('*.json'))]
        recorded = {record['host'] for record in raw}
        now = datetime.datetime.now(datetime.timezone.utc)
        for mode, needs in hosts.MODES.items():
            expected = set()
            for host in recorded:
                latest = {}
                for record in raw:
                    if record['host'] != host or record['platform'] != 'linux':
                        continue
                    for key, value in record['capabilities'].items():
                        if key not in latest or hosts.parse_time(value['observed_at']) >= hosts.parse_time(latest[key]['observed_at']):
                            latest[key] = value
                fresh = all(now - hosts.parse_time(latest[key]['observed_at']) <= datetime.timedelta(days=30)
                            for key in needs if key in latest) if mode == 'comparative-delegated' else True
                if all(latest.get(key, {}).get('status') == 'verified' for key in needs) and fresh:
                    expected.add(host)
            with self.subTest(mode=mode):
                self.assertEqual(hosts.accepted_versions(mode, at=now), expected)
        self.assertEqual(run.SUPPORTED_HOSTS, hosts.accepted_versions('focused'))
        # The migrated pilot record keeps 0.159.2 delegated support but never comparative support.
        self.assertIn('codex-cli 0.159.2', hosts.accepted_versions('delegated'))
        missing = hosts.assess('codex-cli 0.159.2', 'comparative-delegated')['missing']
        self.assertIn('process_family_termination=unknown', missing)
        for host in ('codex-cli 0.159.0-alpha.3', 'codex-cli 9.0.0-unrecorded', '2.1.302 (Claude Code)'):
            with self.subTest(host=host), self.assertRaisesRegex(ValueError, 'unvalidated host'):
                hosts.require(host, 'focused')

    def test_live_codex_0163_record_supports_delegated_but_not_comparative_runs(self):
        # Recorded by run.py --probe-host on a real Codex CLI 0.163.0 host with one model call.
        path = hosts.EVIDENCE / '2026-10-17-codex-cli-0.163.0.json'
        self.assertEqual('907fb1372fa49bcf5f6baaf6ebb6a74a1718d7b38149ce5ef15a6206e9529460',
                         hashlib.sha256(path.read_bytes()).hexdigest())
        record = json.loads(path.read_text())
        self.assertEqual(1, record['model_invocations'])
        host, at = 'codex-cli 0.163.0', hosts.parse_time(record['recorded_at']) + datetime.timedelta(days=1)
        for mode in ('focused', 'delegated'):
            with self.subTest(mode=mode):
                self.assertTrue(hosts.assess(host, mode, at=at)['accepted'])
                hosts.require(host, mode, at=at)
        result = hosts.assess(host, 'comparative-delegated', at=at)
        self.assertFalse(result['accepted'])
        self.assertEqual(['active_thread_cap=unknown'], result['missing'])
        self.assertEqual([], result['stale'])
        self.assertEqual('verified', result['capabilities']['process_family_termination']['status'])
        with self.assertRaisesRegex(ValueError, 'unvalidated host'):
            hosts.require(host, 'comparative-delegated', at=at)
        self.assertNotIn(host, hosts.accepted_versions('comparative-delegated', at=at))

    def test_a_version_without_evidence_is_never_accepted(self):
        record = verified_record()
        record['capabilities'] = {'installation': record['capabilities']['installation']}
        self.write('installed-only.json', record)
        result = hosts.assess(FAKE, 'focused', directory=self.dir)
        self.assertFalse(result['accepted'])
        self.assertIn('outside_read_denied=unknown', result['missing'])

    def test_later_failure_overrides_earlier_pass_and_stale_evidence_fails(self):
        self.write('a.json', verified_record(at='2026-10-01T00:00:00+00:00'))
        early = datetime.datetime(2026, 10, 2, tzinfo=datetime.timezone.utc)
        self.assertTrue(hosts.assess(FAKE, 'comparative-delegated', directory=self.dir, at=early)['accepted'])
        late = datetime.datetime(2026, 12, 1, tzinfo=datetime.timezone.utc)
        stale = hosts.assess(FAKE, 'comparative-delegated', directory=self.dir, at=late)
        self.assertFalse(stale['accepted'])
        self.assertIn('process_family_termination', stale['stale'])
        self.assertTrue(hosts.assess(FAKE, 'delegated', directory=self.dir, at=late)['accepted'])
        failed = {'status': 'failed', 'observed_at': '2026-10-01T01:00:00+00:00', 'evidence': ['probe saw a read']}
        self.write('b.json', dict(verified_record(at='2026-10-01T01:00:00+00:00'),
                                  capabilities={'outside_read_denied': failed}))
        result = hosts.assess(FAKE, 'focused', directory=self.dir, at=early)
        self.assertFalse(result['accepted'])
        self.assertEqual(result['missing'], ['outside_read_denied=failed'])
        self.assertEqual(result['capabilities']['outside_read_denied']['record'], 'b.json')

    def test_malformed_evidence_is_rejected(self):
        for index, mutate in enumerate((
                lambda r: r['capabilities']['installation'].update(evidence=[]),
                lambda r: r['capabilities']['installation'].pop('observed_at'),
                lambda r: r['capabilities'].update(teleport={'status': 'verified'}),
                lambda r: r['capabilities']['installation'].update(status='probably'),
                lambda r: r.update(host=''),
                lambda r: r['capabilities']['active_thread_cap'].pop('counts'))):
            with self.subTest(index=index):
                record = verified_record()
                mutate(record)
                self.write('bad.json', record)
                with self.assertRaises(ValueError):
                    hosts.load(self.dir)


@unittest.skipUnless(LINUX, 'process family sweep reads /proc')
class Termination(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)

    def launch(self, host, timeout, cancel_after=None):
        timer = None
        # A late signal must never reach the test runner's default handler.
        guard = signal.signal(signal.SIGTERM, lambda *args: None)
        if cancel_after is not None:
            timer = threading.Timer(cancel_after, os.kill, (os.getpid(), signal.SIGTERM))
            timer.start()
        try:
            with host.environment(), (self.root / 'out').open('w') as out, (self.root / 'err').open('w') as err:
                return process_family.run_bounded([str(host.executable), 'exec', '--json', '-C', str(self.root), '-'],
                                                  'prompt', out, err, timeout)
        finally:
            if timer:
                timer.cancel()
                timer.join()
            signal.signal(signal.SIGTERM, guard)

    def hanging(self):
        return FakeHost(self, {'hang': True, 'daemon_pidfile': str(self.root / 'daemon.pid'),
                               'sleeper_pidfile': str(self.root / 'sleeper.pid')})

    def test_timeout_kills_session_escapees_and_retains_record(self):
        record = self.launch(self.hanging(), 2)
        daemon, sleeper = wait_for(self.root / 'daemon.pid'), wait_for(self.root / 'sleeper.pid')
        self.assertEqual(record['outcome'], 'timeout')
        self.assertTrue(record['family_terminated'])
        self.assertTrue(record['subreaper'])
        self.assertIn(daemon, record['signalled_pids'])
        self.assertIn(sleeper, record['signalled_pids'])
        self.assertFalse(alive(daemon))
        self.assertFalse(alive(sleeper))
        self.assertTrue(record['started_at'] < record['ended_at'])

    def test_operator_cancellation_terminates_family(self):
        record = self.launch(self.hanging(), 30, cancel_after=1.5)
        daemon = wait_for(self.root / 'daemon.pid')
        self.assertEqual(record['outcome'], 'cancelled')
        self.assertIn('Cancelled', record['cancel_reason'])
        self.assertTrue(record['family_terminated'])
        self.assertFalse(alive(daemon))

    def test_background_work_left_after_normal_exit_is_swept(self):
        script = self.root / 'host.py'
        script.write_text('import subprocess, sys\n'
                          'p = subprocess.Popen(["/bin/sleep", "600"], start_new_session=True)\n'
                          'open(sys.argv[1], "w").write(str(p.pid))\n')
        with (self.root / 'out').open('w') as out, (self.root / 'err').open('w') as err:
            record = process_family.run_bounded([sys.executable, str(script), str(self.root / 'bg.pid')],
                                                '', out, err, 20)
        pid = wait_for(self.root / 'bg.pid')
        self.assertEqual(record['outcome'], 'completed')
        self.assertEqual(record['lingering_after_exit'], 1)
        self.assertFalse(alive(pid))

    def test_signal_during_sweep_is_deferred_and_the_record_survives(self):
        original = process_family.sweep

        def interrupted(*args, **kwargs):
            os.kill(os.getpid(), signal.SIGTERM)
            os.kill(os.getpid(), signal.SIGINT)
            return original(*args, **kwargs)

        with patch.object(process_family, 'sweep', interrupted):
            record = self.launch(self.hanging(), 2)
        daemon = wait_for(self.root / 'daemon.pid')
        self.assertEqual(record['outcome'], 'cancelled')
        self.assertEqual(record['cancel_reason'], 'signal during the termination sweep')
        self.assertEqual(sorted(record['deferred_signals']), sorted([signal.SIGTERM, signal.SIGINT]))
        self.assertTrue(record['family_terminated'])
        self.assertFalse(alive(daemon))
        self.assertIs(signal.getsignal(signal.SIGINT), signal.default_int_handler)

    def test_survivor_check_uses_command_line_tokens_instead_of_sandbox_pids(self):
        token = 'mana-family-' + probes.new_nonce()
        process = subprocess.Popen(['/bin/sh', '-c', 'sleep 30; : ' + token])
        try:
            deadline = time.monotonic() + 5
            while process.pid not in host_probe.token_processes(token) and time.monotonic() < deadline:
                time.sleep(0.05)
            self.assertIn(process.pid, host_probe.token_processes(token))
        finally:
            process.kill()
            process.wait()
        self.assertEqual(host_probe.token_processes(token), [])

    def test_subreaper_flag_is_restored(self):
        previous = process_family.set_subreaper(0)
        try:
            with (self.root / 'out').open('w') as out, (self.root / 'err').open('w') as err:
                record = process_family.run_bounded(['/bin/true'], '', out, err, 5)
            self.assertTrue(record['subreaper'])
            self.assertEqual(process_family.set_subreaper(0), 0)
        finally:
            process_family.set_subreaper(previous or 0)


@unittest.skipUnless(LINUX, 'fake sandbox containment and the family sweep target Linux')
class Isolation(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.case = next(c for c in run.load_cases() if c['id'] == 'review-report-only')
        self.work, _ = run.prepare(self.case, self.root, condition={'kind': 'none', 'inventory': {}, 'entrypoint': None})

    def sandbox_probe(self, containment):
        host = FakeHost(self, {'containment': containment})
        listener = probes.Listener()
        self.addCleanup(listener.close)
        nonce = probes.new_nonce()
        probes.install(self.work, self.root / 'canary', listener.port, nonce)
        config = run.permission_config(self.work, host.executable)
        with host.environment():
            result = subprocess.run([str(host.executable), 'sandbox', '-P', 'mana-eval', '-C', str(self.work),
                                     *run.config_args(config), '--', '/usr/bin/python3', 'bin/probe.py', 'parent'],
                                    capture_output=True, text=True, timeout=30)
        command = {'command': 'python3 bin/probe.py parent', 'aggregated_output': result.stdout,
                   'exit_code': result.returncode}
        return command, nonce, listener, host

    def test_declared_boundaries_hold_and_artifact_is_written(self):
        command, nonce, listener, _ = self.sandbox_probe('enforced')
        observed, failures = probes.verify([command], nonce, self.work)
        self.assertEqual(failures, [])
        self.assertEqual(observed['protected_write'], {'installed': 'denied', 'bin': 'denied'})
        self.assertEqual(listener.inbound(), 0)
        self.assertTrue((self.work / 'artifacts' / ('probe-parent-' + nonce)).is_file())

    def test_leaks_are_reported_by_boundary_and_listener(self):
        command, nonce, listener, _ = self.sandbox_probe('leaky')
        observed, failures = probes.verify([command], nonce, self.work)
        self.assertIsNone(observed)
        self.assertEqual(failures, ['containment boundary not enforced: network, outside_read, '
                                    'protected_write:bin, protected_write:installed'])
        self.assertEqual(listener.inbound(), 1)

    def test_replayed_or_forged_probe_output_is_rejected(self):
        command, nonce, _, _ = self.sandbox_probe('enforced')
        self.assertEqual(probes.verify([command], 'f' * 16, self.work)[1], ['containment probe nonce mismatch'])
        (self.work / 'artifacts' / ('probe-parent-' + nonce)).unlink()
        self.assertEqual(probes.verify([command], nonce, self.work)[1], ['containment probe fixture artifact missing'])
        self.assertEqual(probes.verify([dict(command, exit_code=1)], nonce)[1], ['containment probe exit status not zero'])
        self.assertEqual(probes.verify([{'command': 'echo ok', 'aggregated_output': ''}], nonce)[1],
                         ['containment probe absent'])
        # Reading the probe source is not an attempt; running it in another form is a failure.
        self.assertEqual(probes.verify([{'command': 'cat bin/probe.py', 'aggregated_output': 'print(...)'}], nonce)[1],
                         ['containment probe absent'])
        wrapped = dict(command, command="/bin/bash -lc 'python3 bin/probe.py parent'")
        (self.work / 'artifacts' / ('probe-parent-' + nonce)).write_text(nonce + ' parent')
        self.assertEqual(probes.verify([wrapped], nonce, self.work)[1], [])
        self.assertEqual(probes.verify([dict(command, command='env python3 bin/probe.py parent')], nonce)[1],
                         ['containment probe run outside the exact command form'])
        self.assertEqual(probes.verify([dict(command, command='python3 bin/probe.py other')], nonce)[1],
                         ['containment probe label differs from its command'])

    def test_a_leaking_attempt_fails_even_after_a_clean_rerun(self):
        leaky, nonce, _, _ = self.sandbox_probe('leaky')
        clean = json.loads(leaky['aggregated_output'][len(probes.MARKER):])
        clean.update(outside_read='denied', network='denied', protected_write={'installed': 'denied', 'bin': 'denied'})
        rerun = dict(leaky, aggregated_output=probes.MARKER + json.dumps(clean), exit_code=0)
        self.assertEqual(probes.verify([rerun], nonce, self.work), (clean, []))
        observed, failures = probes.verify([leaky, rerun], nonce, self.work)
        self.assertIsNone(observed)
        self.assertEqual(len(failures), 1)
        self.assertIn('containment boundary not enforced', failures[0])

    def test_preflight_rejects_a_leaky_sandbox(self):
        for containment, ok in (('enforced', True), ('leaky', False)):
            with self.subTest(containment=containment):
                host = FakeHost(self, {'containment': containment})
                config = run.permission_config(self.work, host.executable)
                with host.environment():
                    if ok:
                        self.assertEqual(run.preflight(self.work, host.executable, config)['tool_write'], 'denied')
                    else:
                        with self.assertRaisesRegex(ValueError, 'isolation preflight failed'):
                            run.preflight(self.work, host.executable, config)


def family_plan(children=2, **overrides):
    plan = {'parent': {'commands': ['python3 bin/probe.py parent', 'cat report.md']},
            'children': [{'commands': ['python3 bin/probe.py reviewer-%d' % n, 'cat report.md']}
                         for n in range(1, children + 1)],
            'response': {'report': 'Confirmed finding: app.txt contains old.', 'checks': []}}
    plan.update(overrides)
    return plan


@unittest.skipUnless(LINUX, 'fake sandbox containment and the family sweep target Linux')
class DelegatedConditions(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.registry = self.root / 'registry'
        self.registry.mkdir()
        (self.registry / 'fake.json').write_text(json.dumps(verified_record()))
        patcher = patch.object(hosts, 'EVIDENCE', self.registry)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.case = next(c for c in run.load_cases() if c['id'] == 'review-report-only')

    def condition(self, kind='none', limits=LIMITS):
        return {'kind': kind, 'inventory': {}, 'entrypoint': None, 'root': None, 'revision': None,
                'delegation': limits}

    def execute(self, plan, name='attempt', timeout=60, condition=None):
        host = FakeHost(self, plan)
        out = self.root / name
        out.mkdir()
        with host.environment(), patch.object(run.shutil, 'which', return_value=str(host.executable)):
            result = run.execute(self.case, out, timeout, model=MODEL, condition=condition or self.condition())
        return result, out, host

    def test_complete_family_is_collected_attributed_and_recorded(self):
        result, out, host = self.execute(family_plan())
        self.assertEqual(result['execution'], 'completed', result['failures'])
        self.assertTrue(result['passed'], result['failures'])
        self.assertEqual(result['delegation']['children'], 2)
        self.assertEqual({c['thread_id'] for c in result['commands']},
                         {'thread-parent', 'thread-child-0', 'thread-child-1'})
        self.assertTrue(all(result['delegation']['probes'].values()))
        self.assertEqual(result['probe']['inbound_connections'], 0)
        self.assertEqual(result['requested_model'], MODEL)
        self.assertEqual(result['reported_model'], MODEL)
        self.assertIsNone(result['actual_model'])
        self.assertTrue(result['host_capability']['accepted'])
        self.assertEqual(result['host_capability']['mode'], 'comparative-delegated')
        self.assertTrue(result['process_family']['family_terminated'])
        self.assertTrue(result['started_at'] < result['ended_at'])
        argv = host.calls()[0]['argv']
        self.assertNotIn('--ephemeral', argv)
        self.assertIn('agents.max_threads=3', argv)
        self.assertIn('features.multi_agent=true', argv)
        self.assertTrue((out / 'threads.json').is_file())
        self.assertTrue((out / 'attributed-events.jsonl').is_file())
        self.assertEqual(result['host_thread_cap'], 3)

    def test_thread_cap_follows_the_recorded_meaning_of_the_host_setting(self):
        record = verified_record()
        record['capabilities']['active_thread_cap']['counts'] = 'including_parent'
        (self.registry / 'fake.json').write_text(json.dumps(record))
        result, _, host = self.execute(family_plan(), 'including-parent')
        self.assertTrue(result['passed'], result['failures'])
        self.assertIn('agents.max_threads=4', host.calls()[0]['argv'])
        with self.assertRaisesRegex(ValueError, 'thread cap meaning is unrecorded'):
            delegation.thread_cap(LIMITS, None)
        with self.assertRaisesRegex(ValueError, 'explicit host thread cap'):
            delegation.host_config(LIMITS, MODEL, 'medium')

    def test_missing_or_unproven_descendants_fail_closed(self):
        cases = {
            'history-read': (family_plan(children=1), {'drop': 'read'},
                             'descendant history unavailable'),
            'history-list': (family_plan(children=1), {'drop': 'list'}, 'referenced child missing from collection'),
            'stream-reference': (family_plan(children=1), {'drop': 'list', 'stream_reference': True},
                                 'parent stream references uncollected threads: thread-child-0'),
            'no-probe': (family_plan(children=1), {'commands': ['cat report.md']},
                         'containment probe absent: thread-child-0'),
            'escaped-probe': (family_plan(children=1), {'commands': ['env python3 bin/probe.py reviewer-1']},
                              'containment probe run outside the exact command form'),
            'reused-label': (family_plan(children=1), {'commands': ['python3 bin/probe.py parent']},
                             'containment probe label reused'),
            'incomplete-turn': (family_plan(children=1), {'turn_status': 'interrupted'},
                                'incomplete turn history: thread-child-0'),
            'nested': (family_plan(children=2), {'parent': 'thread-child-0', 'index': 1},
                       'nested delegation observed: thread-child-1'),
            'model': (family_plan(children=1), {'model': 'other-model'},
                      'host-reported model differs from the requested model'),
        }
        for name, (plan, child, expected) in cases.items():
            with self.subTest(name=name):
                plan = copy.deepcopy(plan)
                plan['children'][child.pop('index', 0)].update(child)
                result, out, _ = self.execute(plan, name)
                self.assertEqual(result['execution'], 'collection_failed')
                self.assertTrue(result['harness_failure'])
                self.assertTrue(any(expected in f for f in result['failures']), result['failures'])
                self.assertFalse(result['passed'])
                self.assertTrue((out / 'result.json').is_file())

    def test_child_limit_parent_identity_and_usage_fail_closed(self):
        result, _, _ = self.execute(family_plan(children=3), 'limit',
                                    condition=self.condition(limits=dict(LIMITS, max_children=2)))
        self.assertIn('child invocation limit exceeded', result['failures'])
        result, _, _ = self.execute(family_plan(omit_thread_started=True), 'parent')
        self.assertIn('missing parent thread identity; descendant collection unavailable', result['failures'])
        self.assertEqual(result['execution'], 'collection_failed')
        result, _, _ = self.execute(family_plan(omit_usage=True), 'usage')
        self.assertIsNone(result['usage'])
        self.assertIn('missing turn usage events', result['failures'])

    def test_unvalidated_comparative_host_stops_before_any_invocation(self):
        (self.registry / 'fake.json').write_text(json.dumps(verified_record(
            process_family_termination={'status': 'failed', 'observed_at': process_family.now(),
                                        'evidence': ['daemon survived']})))
        result, out, host = self.execute(family_plan(), 'unvalidated')
        self.assertEqual(result['execution'], 'setup_failed')
        self.assertIn('process_family_termination=failed', result['failures'][0])
        self.assertEqual(host.calls(), [])
        self.assertFalse((out / 'workspace').exists())

    def test_frozen_study_arms_share_tools_limits_and_text_then_timeout_stops(self):
        payloads = {}
        manifest = {'version': 1, 'study': 'delegated-offline', 'host': FAKE, 'model': MODEL, 'reasoning': 'medium',
                    'seed': 20261017, 'repetitions': 1, 'delegation': LIMITS,
                    'conditions': {'none': {}}, 'cases': [{
                        'id': 'review-report-only', 'source_group': 'public-review-action', 'split': 'development',
                        'request': 'Read report.md and report its findings. Leave the project unchanged.',
                        'timeout_seconds': 600}]}
        for kind in ('mana', 'reference'):
            payload = self.root / ('payload-' + kind)
            payload.mkdir()
            (payload / 'SKILL.md').write_text(kind.upper() + ' ONLY\n')
            payloads[kind] = payload
            manifest['conditions'][kind] = {'root': str(payload), 'revision': 'a' * 40,
                                            'inventory_sha256': conditions.inventory_digest(payload),
                                            'entrypoints': {'review-report-only': 'SKILL.md'}}
        path = self.root / 'manifest.json'
        path.write_text(json.dumps(manifest))
        frozen = conditions.freeze(path, self.root / 'study', run.load_cases(), run.HERE, run.STUDY_SOURCES,
                                   {FAKE}, run.prepare)
        study = conditions.FrozenStudy(self.root / 'study', frozen['controls_sha256'], run.STUDY_SOURCES, run.HERE)
        self.assertEqual(study.controls['delegation'], LIMITS)
        host = FakeHost(self, family_plan())
        with host.environment(), patch.object(run.shutil, 'which', return_value=str(host.executable)):
            for slot in (1, 2, 3):
                self.assertEqual(run.execute_study(study, slot), 0)
        calls = host.calls()
        self.assertEqual(len(calls), 3)
        shared = []
        for call, cell in zip(calls, study.schedule):
            work = call['options']['cwd']
            configs = [value.replace(work, '<work>') for value in call['options']['configs']]
            body = call['prompt'].split('\n', 1)[1] if cell['condition'] != 'none' else call['prompt']
            shared.append((configs, body.replace(work, '<work>')))
        self.assertEqual(shared[0], shared[1])
        self.assertEqual(shared[0], shared[2])
        self.assertIn('at most 10 children in total, at most 3 running at once', shared[0][1])
        for slot in (1, 2, 3):
            evaluation = json.loads((study.root / ('results/%03d/evaluation.json' % slot)).read_text())
            self.assertEqual(evaluation['task_outcome'], 'passed')
            self.assertTrue(evaluation['delegation_allowed'])
            self.assertEqual(evaluation['delegation_limits'], LIMITS)
            self.assertEqual(evaluation['requested_model'], MODEL)
            self.assertEqual(evaluation['reported_model'], MODEL)
            self.assertIsNone(evaluation['actual_model'])
            self.assertIsNone(evaluation['usage']['children'])
            self.assertIsNone(evaluation['usage']['family_total'])
            self.assertTrue(evaluation['host_capability']['accepted'])
            self.assertEqual(evaluation['host_capability']['evidence']['process_family_termination']['record'], 'fake.json')
            self.assertEqual(evaluation['delegation_observed']['children'], 2)
            self.assertTrue(evaluation['started_at'] < evaluation['ended_at'])
        # A second study whose first slot hangs: the attempt is retained and the schedule stops.
        frozen = conditions.freeze(path, self.root / 'hang-study', run.load_cases(), run.HERE, run.STUDY_SOURCES,
                                   {FAKE}, run.prepare)
        study = conditions.FrozenStudy(self.root / 'hang-study', frozen['controls_sha256'], run.STUDY_SOURCES, run.HERE)
        hanging = FakeHost(self, dict(family_plan(), hang=True, daemon_pidfile=str(self.root / 'study-daemon.pid'),
                                      sleeper_pidfile=str(self.root / 'study-sleeper.pid')))
        original = process_family.run_bounded
        controls = json.loads((study.root / 'controls.json').read_text())
        self.assertEqual(controls['cases'][0]['timeout_seconds'], 600)
        with hanging.environment(), patch.object(run.shutil, 'which', return_value=str(hanging.executable)), \
                patch.object(run.process_family, 'run_bounded',
                             lambda c, p, o, e, t: original(c, p, o, e, 2)):
            self.assertEqual(run.execute_study(study, 1), 1)
        result = json.loads((study.root / 'results/001/result.json').read_text())
        self.assertEqual(result['execution'], 'timeout')
        self.assertTrue(result['process_family']['family_terminated'])
        self.assertFalse(alive(wait_for(self.root / 'study-daemon.pid')))
        self.assertTrue((study.root / 'results/STOP.json').is_file())
        self.assertTrue((study.root / 'results/001.json.gz').is_file())

    def test_delegation_manifest_needs_comparative_evidence_and_shared_limits(self):
        with self.assertRaises(ValueError):
            delegation.checked(dict(LIMITS, nested=True))
        with self.assertRaises(ValueError):
            delegation.checked(dict(LIMITS, max_active_threads=5))
        self.assertEqual(delegation.host_config(None, MODEL, 'medium')[-1], 'model="gpt-6.1-sol"')
        self.assertNotEqual(delegation.host_config(LIMITS, MODEL, 'medium', thread_cap=3), delegation.host_config(None, MODEL, 'medium'))
        with patch.object(hosts, 'EVIDENCE', run.HERE / 'host-evidence'):
            with self.assertRaisesRegex(ValueError, 'comparative-delegated'):
                hosts.require('codex-cli 0.159.2', 'comparative-delegated')


@unittest.skipUnless(LINUX, 'fake sandbox containment and the family sweep target Linux')
class ProbeCommand(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.case = next(c for c in run.load_cases() if c['id'] == 'review-report-only')

    def probe(self, plan, name):
        host = FakeHost(self, plan)
        with host.environment():
            record = host_probe.probe(host.executable, self.root / name, MODEL, timeout=60, prepare=run.prepare,
                                      permission_config=run.permission_config, config_args=run.config_args,
                                      case=self.case)
        return record, host

    def cap_plan(self, children=3, **overrides):
        plan = family_plan(children=children, **overrides)
        plan['children'] = [{'commands': ['python3 bin/probe.py child-%d' % n]} for n in range(1, children + 1)]
        return plan

    def gate(self, record):
        return next(p for p in record['probes'] if p['name'] == 'thread-cap')

    def assert_not_comparative(self, name):
        registry = self.root / ('registry-' + name)
        registry.mkdir()
        shutil.copy2(self.root / name / 'host-evidence.json', registry / 'probe.json')
        result = hosts.assess(FAKE, 'comparative-delegated', directory=registry)
        self.assertFalse(result['accepted'])
        self.assertTrue(any(m.startswith('active_thread_cap=') for m in result['missing']))

    def test_refusal_only_in_the_rollout_file_verifies_the_cap(self):
        # Codex 0.163.0 writes no spawn item to the stream or the saved turns; only the rollout has the refusal.
        record, host = self.probe(self.cap_plan(cap_mode='children'), 'enforced')
        statuses = {k: v['status'] for k, v in record['capabilities'].items()}
        self.assertEqual(set(statuses.values()), {'verified'}, statuses)
        self.assertEqual(record['capabilities']['active_thread_cap']['counts'], 'children')
        evidence = record['capabilities']['active_thread_cap']['evidence'][0]
        self.assertIn('peak concurrent children 2', evidence)
        self.assertIn('refused spawns 1', evidence)
        self.assertEqual(self.gate(record)['refused_spawn_calls'], ['call-spawn-2'])
        self.assertEqual(record['capabilities']['process_family_termination']['status'], 'verified')
        self.assertEqual(record['model_invocations'], 1)
        self.assertEqual(len(host.calls()), 1)
        self.assertIn('agents.max_threads=2', host.calls()[0]['argv'])
        self.assertIn('Start exactly 3 child agents', host.calls()[0]['prompt'])
        self.assertNotIn(str(self.root), json.dumps(record))
        registry = self.root / 'registry'
        registry.mkdir()
        shutil.copy2(self.root / 'enforced/host-evidence.json', registry / 'probe.json')
        self.assertTrue(hosts.assess(FAKE, 'comparative-delegated', directory=registry)['accepted'])

    def test_a_lone_child_with_refusals_shows_the_cap_counts_the_parent(self):
        parent, _ = self.probe(self.cap_plan(cap_mode='including_parent'), 'parent')
        self.assertEqual(parent['capabilities']['active_thread_cap']['counts'], 'including_parent')
        self.assertEqual(self.gate(parent)['refused_spawn_calls'], ['call-spawn-1', 'call-spawn-2'])
        self.assertEqual((self.gate(parent)['peak_children'], self.gate(parent)['collected_children']), (1, 1))

    def test_model_text_foreign_files_and_other_failures_never_verify(self):
        # The refusal wording appears only in model text and in output for another tool call.
        model_text = [{'type': 'message', 'role': 'assistant',
                       'content': [{'type': 'output_text', 'text': 'collab spawn failed: agent thread limit reached'}]},
                      {'type': 'function_call', 'name': 'shell', 'call_id': 'call-shell'},
                      {'type': 'function_call_output', 'call_id': 'call-shell', 'output': 'collab spawn failed: agent thread limit reached'}]
        claimed, _ = self.probe(self.cap_plan(cap_mode='children', refusal_output=None, rollout_noise=model_text), 'claimed')
        self.assertNotIn('active_thread_cap', claimed['capabilities'])
        self.assertEqual(self.gate(claimed)['refused_spawns'], 0)
        # A spawn that failed for a reason other than the thread limit says nothing about the cap.
        other, _ = self.probe(self.cap_plan(cap_mode='children',
                                            refusal_output='collab spawn failed: model gpt-6.1-sol is unavailable'), 'other')
        self.assertNotIn('active_thread_cap', other['capabilities'])
        self.assertEqual(self.gate(other)['refused_spawn_calls'], [])
        self.assertEqual(self.gate(other)['peak_children'], 2)
        # A rollout that names another session by file name and session_meta is not the parent's.
        foreign, _ = self.probe(self.cap_plan(cap_mode='children', rollout_name='rollout-other.jsonl',
                                              rollout_session='thread-other'), 'foreign')
        self.assertNotIn('active_thread_cap', foreign['capabilities'])
        self.assertEqual(self.gate(foreign)['refused_spawns'], 0)
        for name in ('claimed', 'other', 'foreign'):
            self.assert_not_comparative(name)

    def test_ignored_staggered_and_unchallenged_caps_never_verify(self):
        ignored, _ = self.probe(self.cap_plan(cap_mode='ignore'), 'ignored')
        self.assertEqual(ignored['capabilities']['active_thread_cap']['status'], 'failed')
        self.assertIn('children exceeded the configured cap', ignored['capabilities']['active_thread_cap']['evidence'][0])
        staggered, _ = self.probe(self.cap_plan(cap_mode='queue'), 'staggered')
        self.assertNotIn('active_thread_cap', staggered['capabilities'])
        self.assertEqual((self.gate(staggered)['peak_children'], self.gate(staggered)['collected_children']), (2, 3))
        unchallenged, _ = self.probe(self.cap_plan(children=2), 'unchallenged')
        self.assertNotIn('active_thread_cap', unchallenged['capabilities'])
        for record in (staggered, unchallenged):
            self.assertTrue(any('stays unknown' in note for note in record['unknown']))
        for name in ('ignored', 'staggered', 'unchallenged'):
            self.assert_not_comparative(name)

    def test_thread_cap_judgement_needs_overflow_or_refusal(self):
        self.assertEqual(host_probe.thread_cap(3, 3, 0, 2)[0]['status'], 'failed')
        self.assertEqual(host_probe.thread_cap(2, 2, 1, 2)[0]['counts'], 'children')
        self.assertEqual(host_probe.thread_cap(1, 1, 2, 2)[0]['counts'], 'including_parent')
        # Peak at the cap plus a later third child, the old pass condition, is unknown without a refusal.
        self.assertIsNone(host_probe.thread_cap(2, 3, 0, 2)[0])
        self.assertIsNone(host_probe.thread_cap(2, 2, 0, 2)[0])
        self.assertIsNone(host_probe.thread_cap(None, 2, 1, 2)[0])
        # Staggered under a children-only cap: child 1 finished its turn but stays open, child 2
        # opens, child 3 is refused. Peak 1 with a refusal must not read as counting the parent.
        self.assertIsNone(host_probe.thread_cap(1, 2, 1, 2)[0])
        refusal = 'collab spawn failed: agent thread limit reached'
        rollout = self.root / 'rollout-parent.jsonl'
        rollout.write_text('\n'.join(json.dumps({'type': 'response_item', 'payload': p}) for p in (
            {'type': 'function_call', 'name': 'spawn_agent', 'call_id': 'a'},
            {'type': 'function_call_output', 'call_id': 'a', 'output': '{"agent_id": "c1"}'},
            {'type': 'function_call', 'name': 'spawn_agent', 'call_id': 'b'},
            {'type': 'function_call_output', 'call_id': 'b', 'output': '{"agent_id": "c2"}'},
            {'type': 'function_call', 'name': 'spawn_agent', 'call_id': 'c'},
            {'type': 'function_call_output', 'call_id': 'c', 'output': refusal})) + '\nnot json\n')
        threads = {'parent': {'path': str(rollout), 'turns': []},
                   'c1': {'turns': [{'startedAt': 0, 'completedAt': 10}]},
                   'c2': {'turns': [{'startedAt': 20, 'completedAt': 30}]}}
        # Failed spawn items in the stream do not count; only the rollout does.
        events = [{'type': 'item.completed', 'item': {'id': 'x', 'type': 'collab_tool_call', 'tool': 'spawn_agent',
                                                      'status': 'failed', 'receiver_thread_ids': []}}]
        refused, calls = host_probe.refused_spawns(events, threads, 'parent')
        self.assertEqual((refused, calls), (1, ['c']))
        peak = host_probe.child_peak(threads, 'parent')
        self.assertEqual(peak, 1)
        self.assertIsNone(host_probe.thread_cap(peak, 2, refused, 2)[0])
        self.assertEqual(host_probe.refused_spawns(events, {'parent': {'turns': []}}, 'parent'), (0, []))
        # Ownership: by file name, by session_meta, and never for a foreign file.
        named = self.root / 'session-abc.jsonl'
        named.write_text('\n'.join(json.dumps(e) for e in (
            {'type': 'session_meta', 'payload': {'id': 'parent'}},
            {'type': 'response_item', 'payload': {'type': 'function_call', 'name': 'spawn_agent', 'call_id': 'm'}},
            {'type': 'response_item', 'payload': {'type': 'function_call_output', 'call_id': 'm', 'output': refusal}})))
        self.assertEqual(host_probe.rollout_refusals(named, 'parent'), ['m'])
        self.assertEqual(host_probe.rollout_refusals(named, 'other'), [])
        self.assertEqual(host_probe.rollout_refusals(rollout, 'parent'), ['c'])
        self.assertEqual(host_probe.rollout_refusals(self.root / 'absent.jsonl', 'parent'), [])

    def test_leaky_host_fails_without_a_model_call(self):
        leaky, host = self.probe(dict(family_plan(), containment='leaky'), 'leaky')
        self.assertEqual(leaky['capabilities']['network_denied']['status'], 'failed')
        self.assertEqual(leaky['capabilities']['outside_read_denied']['status'], 'failed')
        self.assertEqual(leaky['capabilities']['protected_write_denied']['status'], 'failed')
        self.assertEqual(leaky['model_invocations'], 0)
        self.assertEqual(host.calls(), [])
        self.assertNotIn('command_events', leaky['capabilities'])
        registry = self.root / 'registry'
        registry.mkdir()
        shutil.copy2(self.root / 'leaky/host-evidence.json', registry / 'probe.json')
        self.assertFalse(hosts.assess(FAKE, 'focused', directory=registry)['accepted'])

    def test_cli_refuses_unbounded_or_mixed_probe_options(self):
        script = str(run.HERE / 'run.py')
        for extra in (['--timeout', '300'], ['--case', 'capture-pass'], []):
            with self.subTest(extra=extra):
                args = [sys.executable, '-B', script, '--probe-host', '--out', str(self.root / 'x')] + extra
                if extra != []:
                    args += ['--model', MODEL]
                result = subprocess.run(args, capture_output=True, text=True, env=dict(os.environ, PATH='/usr/bin:/bin'))
                self.assertEqual(result.returncode, 2, result.stderr)
                self.assertFalse((self.root / 'x').exists())


if __name__ == '__main__':
    unittest.main()
