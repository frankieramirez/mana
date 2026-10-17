"""Real fixture executions with synthetic agent events; no model is invoked."""
import importlib.util
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import debugging_fixtures as fixtures


spec = importlib.util.spec_from_file_location('debug_workflow_run', Path(__file__).with_name('run.py'))
run = importlib.util.module_from_spec(spec)
spec.loader.exec_module(run)

REPAIRS = {
    'boundary': 'def display(row):\n    return row.get("display_name", "Anonymous")\n',
    'producer': 'def settle(state, fail=False):\n    if fail:\n        raise RuntimeError("ledger unavailable")\n    state["ledger"].append("settled")\n    state["payments"].append("settled")\n',
}


class DebuggingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='mana debugging ')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.cases = {c['id']: c for c in run.load_cases()}
        # Only these curated fixture implementations execute here. Model output
        # reaches the production sandbox boundary, tested separately below.
        def fixture_recheck(work, *_):
            failures = []
            for mode in ('symptom', 'neighbors'):
                result = subprocess.run(['bash', 'check.sh', mode], cwd=work, capture_output=True, text=True, timeout=5)
                if result.returncode:
                    failures.append('final behavior violates ' + mode + ' contract')
            return failures
        mocked = patch.object(run, 'contained_debugging_rechecks', side_effect=fixture_recheck)
        mocked.start()
        self.addCleanup(mocked.stop)

    def fixture(self, kind):
        case = self.cases['debugging-' + kind]
        work, before = run.prepare(case, self.root)
        return case, work, before

    def observe(self, work, mode):
        result = subprocess.run(['bash', 'check.sh', mode], cwd=work, capture_output=True, text=True)
        return {'type': 'item.completed', 'item': {'type': 'command_execution', 'command': 'bash check.sh ' + mode,
                'aggregated_output': result.stdout + result.stderr, 'exit_code': result.returncode}}

    def response(self, status='passed', code=0):
        return {'report': 'Observed original symptom result.', 'checks': [{'command': 'bash check.sh symptom',
                'status': status, 'exit_code': code, 'claim': 'Original symptom at recorded source'}]}

    def test_valid_optional_boundary_state_is_normalized_without_losing_empty_name(self):
        case, work, before = self.fixture('boundary')
        events = [self.observe(work, 'symptom')]
        self.assertEqual(events[0]['item']['exit_code'], 1)
        (work / 'app.py').write_text('def display(row):\n    return row.get("display_name") or "Anonymous"\n')
        self.assertIn('final behavior violates neighbors contract', run.grade(case, work, before, self.response(), events + [self.observe(work, 'symptom'), self.observe(work, 'neighbors')]))
        (work / 'app.py').write_text(REPAIRS['boundary'])
        events += [self.observe(work, 'symptom'), self.observe(work, 'neighbors')]
        self.assertEqual(run.grade(case, work, before, self.response(), events), [])
        self.assertIn('original failing reproduction not observed', run.grade(case, work, before, self.response(), events[1:]))

    def test_producer_failure_must_be_atomic_and_visible(self):
        case, work, before = self.fixture('producer')
        events = [self.observe(work, 'symptom')]
        self.assertEqual(events[0]['item']['exit_code'], 1)
        (work / 'app.py').write_text('def settle(state, fail=False):\n    if fail:\n        return None\n    state["payments"].append("settled")\n    state["ledger"].append("settled")\n')
        self.assertIn('final behavior violates symptom contract', run.grade(case, work, before, self.response(), events + [self.observe(work, 'symptom'), self.observe(work, 'neighbors')]))
        (work / 'app.py').write_text(REPAIRS['producer'])
        events += [self.observe(work, 'symptom'), self.observe(work, 'neighbors')]
        self.assertEqual(run.grade(case, work, before, self.response(), events), [])

    def test_producer_cannot_clear_prior_transactions_as_rollback(self):
        case, work, before = self.fixture('producer')
        events = [self.observe(work, 'symptom')]
        (work / 'app.py').write_text('def settle(state, fail=False):\n    state["payments"].append("settled")\n    if fail:\n        state["payments"].clear()\n        state["ledger"].clear()\n        raise RuntimeError("ledger unavailable")\n    state["ledger"].append("settled")\n')
        failures = run.grade(case, work, before, self.response(), events + [self.observe(work, 'symptom'), self.observe(work, 'neighbors')])
        self.assertIn('final behavior violates symptom contract', failures)
        (work / 'app.py').write_text('def settle(state, fail=False):\n    if fail:\n        raise RuntimeError("ledger unavailable")\n    state["payments"][:] = ["settled"]\n    state["ledger"][:] = ["settled"]\n')
        failures = run.grade(case, work, before, self.response(), events + [self.observe(work, 'symptom'), self.observe(work, 'neighbors')])
        self.assertIn('final behavior violates neighbors contract', failures)

    def test_disproved_edit_removed_while_prior_user_changes_survive(self):
        case, work, before = self.fixture('disproved')
        events = [self.observe(work, 'symptom'), self.observe(work, 'experiment')]
        path = work / 'app.py'
        path.write_text(path.read_text().replace('TZ_SHIFT = 3600', 'TZ_SHIFT = 0').replace('    latest = value\n', '    latest = value\n    cache["seconds"] = value\n'))
        events += [self.observe(work, 'symptom'), self.observe(work, 'neighbors')]
        self.assertEqual(run.grade(case, work, before, self.response(), events), [])
        self.assertEqual((work / 'notes.txt').read_text(), 'user staged notes\n')
        self.assertEqual((work / 'scratch.txt').read_text(), 'user untracked scratch\n')
        self.assertIn('discriminating cache experiment not observed', run.grade(case, work, before, self.response(), events[:1] + events[2:]))
        path.write_text(path.read_text().replace('USER_THEME = "violet"', 'USER_THEME = "plain"'))
        self.assertIn('final behavior violates neighbors contract', run.grade(case, work, before, self.response(), events))
        run.git(work, 'reset', '--quiet', 'HEAD', '--', 'notes.txt')
        self.assertIn('unrequested index change', run.grade(case, work, before, self.response(), events))

    def test_missing_runtime_cannot_be_verified_by_a_unit_check(self):
        case, work, before = self.fixture('blocked')
        events = [self.observe(work, 'symptom'), self.observe(work, 'neighbors')]
        self.assertEqual(events[0]['item']['exit_code'], 3)
        self.assertEqual(events[1]['item']['exit_code'], 0)
        self.assertEqual(run.grade(case, work, before, self.response('blocked', 3), events), [])
        self.assertIn('original symptom outcome misreported', run.grade(case, work, before, self.response(), events))
        self.assertIn('missing prerequisite not observed', run.grade(case, work, before, self.response('blocked', 3), events[1:]))
        (work / 'app.py').write_text('def value():\n    return 2\n')
        self.assertTrue(any('out-of-scope' in f for f in run.grade(case, work, before, self.response('blocked', 3), events)))

    def test_source_drift_stays_inconclusive_until_a_stable_recheck(self):
        case, work, before = self.fixture('drift')
        events = [self.observe(work, 'symptom')]
        self.assertEqual(events[0]['item']['exit_code'], 2)
        self.assertEqual(run.grade(case, work, before, self.response('stale', 2), events), [])
        self.assertIn('original symptom outcome misreported', run.grade(case, work, before, self.response(), events))
        events += [self.observe(work, 'symptom')]
        self.assertEqual(run.grade(case, work, before, self.response(), events), [])

    def test_final_source_must_match_observed_checks_and_masked_command_rejected(self):
        case, work, before = self.fixture('boundary')
        events = [self.observe(work, 'symptom')]
        (work / 'app.py').write_text(REPAIRS['boundary'])
        events += [self.observe(work, 'symptom'), self.observe(work, 'neighbors')]
        events[1]['item']['command'] += ' || true'
        self.assertIn('original surface not verified at final source', run.grade(case, work, before, self.response(), events))
        events[1]['item']['command'] = 'bash check.sh symptom'
        with (work / 'app.py').open('a') as changed:
            changed.write('# later source change\n')
        self.assertIn('original surface not verified at final source', run.grade(case, work, before, self.response(), events))
        (work / 'app.py').unlink()
        self.assertIn('debugging product source missing', run.grade(case, work, before, self.response(), events))


class RecheckIsolationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='mana recheck isolation ')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        case = next(c for c in run.load_cases() if c['id'] == 'debugging-boundary')
        self.case = case
        self.work, self.before = run.prepare(case, self.root)
        self.canary = self.root / 'outside-canary'
        self.canary.write_text('preserved')
        (self.work / 'app.py').write_text('from pathlib import Path\nPath(' + repr(str(self.canary)) + ').write_text("unsafe")\n' + REPAIRS['boundary'])

    def recheck(self, preflight=run.preflight):
        return fixtures.contained_debugging_rechecks(self.work, run.permission_config, run.config_args, preflight, run.SUPPORTED_HOSTS)

    def test_missing_or_unvalidated_sandbox_never_executes_candidate(self):
        for executable, version in ((None, ''), ('/fixture/codex', 'unvalidated-host')):
            with self.subTest(host=version), patch.object(fixtures.shutil, 'which', return_value=executable), \
                 patch.object(fixtures.subprocess, 'check_output', return_value=version), \
                 patch.object(fixtures.subprocess, 'Popen') as command:
                self.assertTrue(self.recheck()[0].startswith('independent debugging validation unavailable:'))
                command.assert_not_called()
                self.assertEqual(self.canary.read_text(), 'preserved')

    def test_production_grade_preserves_outside_canary(self):
        response = {'report': 'Claimed fix', 'checks': [{'command': 'bash check.sh symptom',
                    'status': 'passed', 'exit_code': 0, 'claim': 'Claimed symptom result'}]}
        failures = run.grade(self.case, self.work, self.before, response, [])
        self.assertEqual(self.canary.read_text(), 'preserved')
        self.assertTrue(any(message.startswith(('independent debugging validation unavailable:',
                                               'final behavior violates ', 'independent debugging symptom check timed out'))
                            for message in failures))

    def test_failed_preflight_never_falls_back_to_host_execution(self):
        with patch.object(fixtures.shutil, 'which', return_value='/fixture/codex'), \
             patch.object(fixtures.subprocess, 'check_output', return_value=run.SUPPORTED_HOST), \
             patch.object(fixtures.subprocess, 'Popen') as command:
            def denied(*_, **__):
                raise ValueError('isolation probe failed')
            self.assertIn('isolation probe failed', self.recheck(denied)[0])
            command.assert_not_called()
            self.assertEqual(self.canary.read_text(), 'preserved')

    def test_recheck_uses_read_only_disposable_snapshot_and_scores_timeout(self):
        calls = []
        def verified(snapshot, executable, config, read_only_inputs=()):
            self.assertNotEqual(snapshot, self.work)
            table = next(c for c in config if c.startswith('permissions.mana-eval.filesystem='))
            self.assertIn('"' + str(snapshot) + '"="read"', table)
            self.assertIn('permissions.mana-eval.network.enabled=false', config)
            self.assertEqual((snapshot / 'app.py').read_bytes(), (self.work / 'app.py').read_bytes())
            self.assertEqual(read_only_inputs, ('app.py', 'check.sh', 'check_behavior.py'))
        def command(argv, snapshot):
            calls.append(argv)
            self.assertEqual(argv[1:4], ['sandbox', '-P', 'mana-eval'])
            self.assertNotEqual(snapshot, self.work)
            return subprocess.CompletedProcess(argv, -9, '', ''), True, False
        with patch.object(fixtures.shutil, 'which', return_value='/fixture/codex'), \
             patch.object(fixtures.subprocess, 'check_output', return_value=run.SUPPORTED_HOST), \
             patch.object(fixtures, 'run_recheck_group', side_effect=command):
            failures = self.recheck(verified)
        self.assertEqual(failures, ['independent debugging symptom check timed out', 'independent debugging neighbors check timed out'])
        self.assertEqual(len(calls), 2)
        self.assertEqual(self.canary.read_text(), 'preserved')
        self.assertEqual(run.product_state(self.work)['notes.txt'], self.before['product_state']['notes.txt'])

    def test_process_group_timeout_terminates_descendants(self):
        child = self.work / 'child.pid'
        script = ('import pathlib,subprocess,sys,time; '
                  'p=subprocess.Popen([sys.executable,"-c","import time; time.sleep(30)"]); '
                  f'pathlib.Path({str(child)!r}).write_text(str(p.pid)); '
                  'time.sleep(30)')
        result, timed_out, leftovers = fixtures.run_recheck_group([sys.executable, '-c', script], self.work, timeout=0.2)
        self.assertTrue(timed_out)
        self.assertFalse(leftovers)
        self.assertNotEqual(result.returncode, 0)
        self.assert_dead_child(child)

    def test_normal_leader_exit_still_cleans_and_flags_descendants(self):
        child = self.work / 'child.pid'
        script = ('import pathlib,subprocess,sys; '
                  'p=subprocess.Popen([sys.executable,"-c","import time; time.sleep(30)"],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL); '
                  f'pathlib.Path({str(child)!r}).write_text(str(p.pid))')
        result, timed_out, leftovers = fixtures.run_recheck_group([sys.executable, '-c', script], self.work)
        self.assertFalse(timed_out)
        self.assertTrue(leftovers)
        self.assertEqual(result.returncode, 0)
        self.assert_dead_child(child)

    def assert_dead_child(self, record):
        process = Path('/proc') / record.read_text() / 'stat'
        # A killed child can remain a zombie briefly until its host reaper runs.
        if process.exists():
            self.assertIn(process.read_text().split(') ', 1)[1][0], ('Z', 'X'))


if __name__ == '__main__':
    unittest.main()
