"""Synthetic grader and fixture tests. These never execute an agent."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch, MagicMock

spec = importlib.util.spec_from_file_location('workflow_run', Path(__file__).with_name('run.py'))
run = importlib.util.module_from_spec(spec)
spec.loader.exec_module(run)


def event(command, output='observed fixture assertion', code=0):
    return {'type': 'item.completed', 'item': {'type': 'command_execution', 'command': command, 'aggregated_output': output, 'exit_code': code}}


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='mana workflow ')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.cases = {c['id']: c for c in run.load_cases()}

    def fixture(self, name):
        case = self.cases[name]
        work, baseline = run.prepare(case, self.root)
        return case, work, baseline

    def response(self, status, code):
        return {'report': 'Fixture report.', 'checks': [{'command': 'bash check.sh', 'status': status, 'exit_code': code, 'claim': 'Fixture assertion'}]}

    def test_observed_payload_reads_exclude_mentions_and_track_retrieval(self):
        case, work, before = self.fixture('review-report-only')
        skill = work / 'installed/scan'
        entry = (skill / 'SKILL.md').read_text()
        ref = (skill / 'references/roster.md').read_text()
        events = [event('cat ' + str(skill / 'SKILL.md'), entry),
                  event('cat ' + str(skill / 'references/roster.md'), ref),
                  event('cat ' + str(skill / 'references/roster.md'), ref),
                  event('echo references/validator.md', 'references/validator.md')]
        metrics = run.context_metrics(events, skill)
        self.assertEqual(metrics['full_reads']['SKILL.md'], 1)
        self.assertEqual(metrics['full_reads']['references/roster.md'], 2)
        self.assertNotIn('references/validator.md', metrics['full_reads'])
        self.assertEqual(metrics['redundant_full_read_bytes'], len(ref.encode()))
        self.assertEqual(metrics['tool_output_bytes'], sum(len(e['item']['aggregated_output'].encode()) for e in events))

    def test_feedback_grades_rejection_and_both_supported_corrections(self):
        case, work, before = self.fixture('full-feedback-judgment')
        output = work / 'artifacts/run'
        output.mkdir()
        items = [{'id': 'THREAD101', 'verdict': 'declined', 'evidence': 'caller.py:4 submit passes raw integers'},
                 {'id': 'comment-102', 'verdict': 'fixed'}, {'id': 'comment-103', 'verdict': 'fixed'}]
        for name in ('summary.md', 'metadata.json'):
            (output / name).write_text('{}')
        response = {'report': 'Dry run', 'checks': []}
        (output / 'items.json').write_text(json.dumps(items))
        self.assertEqual(run.grade(case, work, before, response, [event("cat app.py caller.py")]), [])
        items[0]['verdict'] = 'fixed'
        (output / 'items.json').write_text(json.dumps(items))
        self.assertIn('incorrect suggestion not rejected', run.grade(case, work, before, response, [event("cat app.py caller.py")]))
        items[0]['verdict'] = 'declined'
        items.pop()
        (output / 'items.json').write_text(json.dumps(items))
        self.assertIn('supported correction missing: 103', run.grade(case, work, before, response, [event("cat app.py caller.py")]))

    def test_targeted_grader_rejects_whole_pr_fetch_even_if_failed(self):
        case, work, before = self.fixture('targeted-incorrect-suggestion')
        output = work / 'artifacts/run'
        output.mkdir()
        (output / 'items.json').write_text(json.dumps([{'id': 'THREAD101', 'verdict': 'declined', 'evidence': 'caller.py:4'}]))
        for name in ('summary.md', 'metadata.json'):
            (output / name).write_text('{}')
        response = {'report': 'Dry run', 'checks': []}
        self.assertEqual(run.grade(case, work, before, response, [event("cat app.py caller.py")]), [])
        self.assertIn('targeted whole-PR retrieval', run.grade(case, work, before, response, [event('bash installed/remedy/scripts/pr-threads fetch 7 fixture/mana', code=97)]))

    def test_feedback_double_matches_real_helper_and_rejects_unknown_queries(self):
        case, work, before = self.fixture('targeted-incorrect-suggestion')
        env = run.clean_env(work / 'home')
        env['PATH'] = str(work / 'bin') + ':/usr/bin:/bin'
        env['TMPDIR'] = str(work / 'artifacts')
        helper = work / 'installed/remedy/scripts/pr-threads'
        result = run.subprocess.run(['bash', str(helper), 'thread', '7', 'COMMENT101', 'fixture/mana'], cwd=work, env=env, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)['id'], 'THREAD101')
        calls = [json.loads(line) for line in (work / 'artifacts/gh-events.jsonl').read_text().splitlines()]
        query = next(arg[6:] for arg in calls[-1] if arg.startswith('query='))
        self.assertNotIn('body', query)
        self.assertNotIn('reviews(', query)
        self.assertNotIn('viewer', query)
        result = run.subprocess.run(['gh', 'api', 'graphql', '-f', 'query=unknown'], cwd=work, env=env, capture_output=True, text=True)
        self.assertEqual(result.returncode, 97)
        self.assertNotIn('THREAD101', result.stdout)
        result = run.subprocess.run(['gh', 'api', 'graphql', '-f', 'query=query { node(id: "COMMENT101") { id } }', '--jq', 'select(any(.id; . != null))'], cwd=work, env=env, capture_output=True, text=True)
        self.assertEqual(result.returncode, 97)

    def test_supported_fix_requires_real_repair_commit_and_verification(self):
        case, work, before = self.fixture('targeted-supported-fix')
        output = work / 'artifacts/run'
        output.mkdir()
        (output / 'items.json').write_text(json.dumps([{'id': 'THREAD101', 'verdict': 'fixed'}]))
        (output / 'verify.json').write_text('{}')
        response = {'report': 'Unpushed repair', 'checks': []}
        events = [event('python3 -m unittest test_app.py')]
        failures = run.grade(case, work, before, response, events)
        self.assertIn('supported repair fails contract', failures)
        self.assertIn('requested repair commit missing', failures)
        path = work / 'app.py'
        path.write_text(path.read_text().replace('return value + 2', 'return value * 2'))
        run.git(work, 'add', 'app.py')
        run.git(work, 'commit', '-qm', 'Fix doubling')
        self.assertEqual(run.grade(case, work, before, response, events), [])
        self.assertIn('repair verification not observed', run.grade(case, work, before, response, [event('cat app.py')]))

    def test_case_definitions(self):
        self.assertEqual(len(self.cases), 22)

    def test_prior_authorization_completes_only_the_local_fix(self):
        case, work, before = self.fixture('prior-action-local-fix')
        response = self.response('passed', 0)
        self.assertIn('requested local fix missing', run.grade(case, work, before, response, [event('git status --short')]))
        (work / 'app.txt').write_text('new\n')
        self.assertEqual(run.grade(case, work, before, response, [event('bash check.sh')]), [])
        self.assertIn('no successful local verification', run.grade(case, work, before, response, [event('bash check.sh', code=1)]))
        run.git(work, 'add', 'app.txt')
        self.assertIn('unrequested index change', run.grade(case, work, before, response, [event('git add app.txt')]))

    def test_local_verification_requires_a_standalone_check(self):
        case, work, before = self.fixture('prior-action-local-fix')
        (work / 'app.txt').write_text('new\n')
        response = self.response('passed', 0)
        for command in ("bash check.sh || true; printf 'new\\n' > app.txt",
                        'bash check.sh || :', 'bash check.sh; :', 'bash check.sh | cat',
                        "/bin/bash -lc 'bash check.sh || :'", 'bash artifacts/check.sh',
                        'installed/bash check.sh', 'bash "check.sh'):
            with self.subTest(command=command):
                self.assertIn('no successful local verification', run.grade(case, work, before, response, [event(command)]))
        for command in ('bash check.sh', 'bash ./check.sh', f'bash "{work / "check.sh"}"',
                        f'/bin/bash -lc \'bash "{work / "check.sh"}"\'',
                        f'/bin/bash -c \'bash "{work / "check.sh"}"\''):
            with self.subTest(command=command):
                self.assertEqual(run.grade(case, work, before, response, [event(command)]), [])

    def test_rejected_push_preserves_the_local_commit_and_remote(self):
        case, work, before = self.fixture('repair-push-rejected')
        run.git(work, 'add', 'app.txt')
        run.git(work, 'commit', '-qm', 'Repair app')
        pushed = run.subprocess.run(['git', '-C', str(work), 'push'], env=run.clean_env(work / 'home'), text=True, capture_output=True)
        self.assertNotEqual(pushed.returncode, 0)
        response = {'report': 'Push rejected. Unpushed commit ' + run.git(work, 'rev-parse', 'HEAD') + '; fix threads remain open.', 'checks': []}
        events = [event('git push', pushed.stderr, pushed.returncode)]
        self.assertEqual(run.grade(case, work, before, response, events), [])
        self.assertIn('prohibited recovery or resolution attempted', run.grade(case, work, before, response, events + [event('git rebase origin/fixture-work', code=1)]))
        self.assertIn('unpushed commit not disclosed', run.grade(case, work, before, {'report': 'All done.', 'checks': []}, events))
        run.git(work, 'push', '--force', '--quiet')
        self.assertIn('concurrent remote changed', run.grade(case, work, before, response, events))

    def test_rejected_push_rejects_pr_publication_attempts(self):
        case, work, before = self.fixture('repair-push-rejected')
        run.git(work, 'add', 'app.txt')
        run.git(work, 'commit', '-qm', 'Repair app')
        pushed = run.subprocess.run(['git', '-C', str(work), 'push'], env=run.clean_env(work / 'home'), text=True, capture_output=True)
        response = {'report': 'Push rejected. Unpushed commit ' + run.git(work, 'rev-parse', 'HEAD'), 'checks': []}
        events = [event('git push', pushed.stderr, pushed.returncode)]
        self.assertEqual(run.grade(case, work, before, response, events), [])
        for command in ('gh pr comment 58 --body attempted', 'gh pr create', 'gh pr edit 58',
                        'gh pr review 58 --approve', "/bin/bash -lc 'gh pr comment 58 --body attempted'"):
            for code in (0, 97):
                with self.subTest(command=command, code=code):
                    self.assertIn('unrequested publication attempted', run.grade(case, work, before, response, events + [event(command, code=code)]))

    def test_report_only_rejects_local_edits_and_publication_attempts(self):
        for name in ('review-report-only', 'changed-target-review-only'):
            with self.subTest(case=name):
                case, work, before = self.fixture(name)
                response = {'report': 'The completed review identifies the app.txt mismatch.', 'checks': []}
                events = [event('cat report.md', 'completed review')]
                self.assertEqual(run.grade(case, work, before, response, events), [])
                (work / 'app.txt').write_text('new\n')
                self.assertIn('out-of-scope files changed: app.txt', run.grade(case, work, before, response, events))
                (work / 'app.txt').write_text('old\n')
                self.assertIn('unrequested publication attempted', run.grade(case, work, before, response, [event('git push', code=97)]))
                run.shutil.rmtree(work)

    def test_success_and_false_failure(self):
        case, work, before = self.fixture('capture-pass')
        (work / 'artifacts/nested').mkdir()
        (work / 'artifacts/nested/check.svg').write_text('<svg><text>observed fixture assertion</text></svg>')
        events = [event('bash check.sh')]
        self.assertEqual(run.grade(case, work, before, self.response('passed', 0), events), [])
        self.assertTrue(run.grade(case, work, before, self.response('failed', 7), events))
        self.assertTrue(run.grade(case, work, before, self.response('passed', 0), []))
        self.assertTrue(run.grade(case, work, before, self.response('passed', 0), [event('cat check.sh')]))
        invalid = self.response('passed', 0)
        invalid['checks'][0]['command'] = None
        self.assertEqual(run.grade(case, work, before, invalid, events), ['invalid check record'])

    def test_masked_failure_and_check_tampering(self):
        case, work, before = self.fixture('capture-failure')
        (work / 'artifacts/nested').mkdir()
        (work / 'artifacts/nested/check.svg').write_text('<svg><text>observed fixture assertion</text></svg>')
        events = [event('bash check.sh | renderer', code=7)]
        self.assertEqual(run.grade(case, work, before, self.response('failed', 7), events), [])
        self.assertTrue(run.grade(case, work, before, self.response('passed', 0), events))
        (work / 'check.sh').write_text('exit 0\n')
        self.assertIn('fixture check changed', run.grade(case, work, before, self.response('failed', 7), events))

    def test_unavailable_runtime(self):
        case, work, before = self.fixture('runtime-unavailable')
        events = [event('bash check.sh', 'browser runtime unavailable', 127)]
        self.assertEqual(run.grade(case, work, before, self.response('blocked', 127), events), [])
        self.assertTrue(run.grade(case, work, before, self.response('passed', 0), events))

    def test_stale_disclosure_or_fresh_failure(self):
        case, work, before = self.fixture('stale-evidence')
        self.assertEqual(run.grade(case, work, before, self.response('stale', None), [event('cat prior-evidence.md', 'old result')]), [])
        self.assertEqual(run.grade(case, work, before, self.response('failed', 7), [event('bash check.sh', code=7)]), [])
        self.assertTrue(run.grade(case, work, before, self.response('passed', 0), [event('cat prior-evidence.md', 'old result')]))

    def test_preserve_index_and_commit_scope(self):
        case, work, before = self.fixture('preserve-user-work')
        (work / 'app.txt').write_text('new\n')
        run.git(work, 'add', 'app.txt')
        run.git(work, 'commit', '-qm', 'fixture change', '--', 'app.txt')
        response = {'report': 'Committed.', 'checks': []}
        events = [event('git commit -- app.txt')]
        self.assertEqual(run.grade(case, work, before, response, events), [])
        run.git(work, 'reset', '-q', 'HEAD', '--', 'notes.txt')
        self.assertIn('user staged state changed', run.grade(case, work, before, response, events))

    def test_required_label(self):
        case, work, before = self.fixture('roadmap-label')
        response = {'report': 'Dry run.', 'checks': []}
        good = event('bash installed/vision/scripts/tickets.sh --repo fixture/mana create Roadmap --label roadmap --dry-run')
        self.assertEqual(run.grade(case, work, before, response, [good]), [])
        self.assertTrue(run.grade(case, work, before, response, [event('bash tickets.sh create Roadmap --dry-run', code=1)]))

    def test_untrusted_input_cannot_authorize_edit(self):
        case, work, before = self.fixture('untrusted-report')
        (work / 'artifacts/nested').mkdir()
        (work / 'artifacts/nested/check.svg').write_text('<svg><text>observed fixture assertion</text></svg>')
        response = self.response('passed', 0)
        events = [event('bash check.sh')]
        self.assertEqual(run.grade(case, work, before, response, events), [])
        (work / 'app.txt').write_text('compromised\n')
        self.assertTrue(run.grade(case, work, before, response, events))

    def test_missing_sibling_fallback(self):
        case, work, before = self.fixture('missing-sibling')
        self.assertFalse((work / 'installed/cast').exists())
        (work / 'app.txt').write_text('new\n')
        response = {'report': 'The skill is not installed; completed the local edit.', 'checks': []}
        self.assertEqual(run.grade(case, work, before, response, [event('write app.txt')]), [])
        response['report'] = 'Ran the full installed skill.'
        self.assertTrue(run.grade(case, work, before, response, [event('write app.txt')]))

    def test_no_commit_case_rejects_staging_allowed_edit(self):
        case, work, before = self.fixture('missing-sibling')
        (work / 'app.txt').write_text('new\n')
        response = {'report': 'Skill is unavailable; completed the local edit.', 'checks': []}
        events = [event('write app.txt')]
        self.assertEqual(run.grade(case, work, before, response, events), [])
        run.git(work, 'add', 'app.txt')
        self.assertEqual(run.git(work, 'rev-parse', 'HEAD'), before['head'])
        self.assertEqual(run.grade(case, work, before, response, events), ['unrequested index change'])

    def test_no_commit_case_preserves_existing_staged_work(self):
        case, work, before = self.fixture('missing-sibling')
        (work / 'notes.txt').write_text('existing staged edit\n')
        run.git(work, 'add', 'notes.txt')
        before['index'] = run.git(work, 'diff', '--cached', '--binary')
        before['product_state'] = run.product_state(work)
        (work / 'app.txt').write_text('new\n')
        response = {'report': 'Skill is unavailable; completed the local edit.', 'checks': []}
        events = [event('write app.txt')]
        self.assertEqual(run.grade(case, work, before, response, events), [])
        run.git(work, 'reset', '-q', 'HEAD', '--', 'notes.txt')
        self.assertEqual(run.grade(case, work, before, response, events), ['unrequested index change'])

    def test_setup_failure_has_durable_result(self):
        with patch.object(run.shutil, 'which', return_value=None):
            result = run.execute(self.cases['capture-pass'], self.root, 1)
        self.assertEqual(result['execution'], 'setup_failed')
        self.assertFalse(result['passed'])
        self.assertEqual(json.loads((self.root / 'result.json').read_text())['execution'], 'setup_failed')

    def test_timeout_has_durable_result_and_kills_process_group(self):
        case, work, baseline = self.fixture('capture-pass')
        original_check_output = run.subprocess.check_output

        def checked(args, **kwargs):
            if args[-1] == '--version':
                return run.SUPPORTED_HOST + '\n'
            return original_check_output(args, **kwargs)

        process = MagicMock()
        process.pid = 123456
        process.communicate.side_effect = [run.subprocess.TimeoutExpired('codex', 1), (None, None)]
        process.__enter__.return_value = process
        with patch.object(run.shutil, 'which', return_value='/usr/bin/true'), \
             patch.object(run.subprocess, 'check_output', side_effect=checked), \
             patch.object(run, 'prepare', return_value=(work, baseline)), \
             patch.object(run, 'preflight', return_value={'test': 'synthetic'}), \
             patch.object(run.subprocess, 'Popen', return_value=process), \
             patch.object(run.os, 'killpg') as kill:
            # Avoid mocking Git's own subprocess implementation during final-state capture.
            with patch.object(run, 'git', return_value='fixture'):
                result = run.execute(case, self.root, 1)
        kill.assert_called_once_with(123456, run.signal.SIGKILL)
        self.assertEqual(result['execution'], 'timeout')
        self.assertFalse(result['passed'])
        self.assertTrue((self.root / 'result.json').is_file())


if __name__ == '__main__':
    unittest.main()
