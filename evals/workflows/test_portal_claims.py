import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('portal_claim_fixture', Path(__file__).with_name('run.py'))
fixture = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fixture)


class ClaimTargets(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='mana portal claims ')
        self.addCleanup(self.temp.cleanup)
        self.out = Path(self.temp.name)
        self.case = next(c for c in fixture.load_cases() if c['id'] == 'portal-go-single-unit')
        self.work, self.baseline = fixture.prepare(self.case, self.out)
        self.env = fixture.clean_env(self.work / 'home')
        self.env['PATH'] = str(self.work / 'bin') + ':/usr/bin:/bin'
        (self.work / 'unit11.txt').write_text('new11\n')

    def transport(self, *args):
        return subprocess.run(['gh', 'issue', *args], cwd=self.work, env=self.env,
                              text=True, capture_output=True)

    def grade(self):
        return fixture.grade_portal_fixture(self.case, self.work, self.baseline,
                                            {'report': 'Prepared unit 11'}, [])

    def test_numeric_and_url_claims_are_both_graded(self):
        for target in ('11', 'https://github.com/fixture/mana/issues/11'):
            with self.subTest(target=target):
                result = self.transport('edit', '--repo', 'fixture/mana', target, '--add-assignee', 'fixture')
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(self.grade(), [])
        data = json.loads((self.work / 'artifacts/tracker.json').read_text())
        self.assertEqual(data['issues']['11']['assignees'], ['fixture'])

    def test_numeric_and_url_comment_close_targets_are_consistent(self):
        for target in ('11', 'https://github.com/fixture/mana/issues/12'):
            with self.subTest(target=target):
                comment = self.transport('comment', target, '--body', '99')
                closed = self.transport('close', '--repo', 'fixture/mana', target)
                self.assertEqual(comment.returncode, 0, comment.stderr)
                self.assertEqual(closed.returncode, 0, closed.stderr)
        data = json.loads((self.work / 'artifacts/tracker.json').read_text())
        for n in ('11', '12'):
            self.assertEqual(data['issues'][n]['comments'], ['99'])
            self.assertEqual(data['issues'][n]['state'], 'CLOSED')

    def test_malformed_and_foreign_claims_fail_explicitly(self):
        for target in (None, 'bogus', 'https://github.com/other/repo/issues/11'):
            with self.subTest(target=target):
                args = ['edit', '--add-assignee', 'fixture', '--body', '99']
                if target is not None:
                    args.insert(1, target)
                result = self.transport(*args)
                self.assertEqual(result.returncode, 97, result.stderr)
                self.assertNotIn('Traceback', result.stderr)
                self.assertTrue(any('invalid claim target' in failure for failure in self.grade()))

    def test_claim_without_any_numeric_argument_fails_explicitly(self):
        result = self.transport('edit', '--add-assignee', 'fixture')
        self.assertEqual(result.returncode, 97, result.stderr)
        self.assertNotIn('Traceback', result.stderr)
        self.assertIn('invalid claim target: expected one issue target', self.grade())

    def test_unknown_numeric_claim_fails_explicitly(self):
        result = self.transport('edit', '200', '--add-assignee', 'fixture')
        self.assertEqual(result.returncode, 97, result.stderr)
        self.assertIn('unsupported claim target: 200', self.grade())

    def test_malformed_comment_and_close_do_not_raise(self):
        for verb in ('comment', 'close'):
            with self.subTest(verb=verb):
                result = self.transport(verb, '--body', '99')
                self.assertEqual(result.returncode, 97, result.stderr)
                self.assertNotIn('Traceback', result.stderr)

    def test_unexpected_grading_exception_writes_failed_result(self):
        class FakeProcess:
            returncode = 0

            def __init__(self, command, **kwargs):
                self.stdout = kwargs['stdout']
                self.response = Path(command[command.index('-o') + 1])

            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def communicate(self, prompt, timeout):
                self.stdout.write(json.dumps({'type': 'item.completed', 'item': {
                    'type': 'command_execution', 'command': 'git status', 'exit_code': 0,
                    'aggregated_output': ''}}) + '\n')
                self.stdout.write(json.dumps({'type': 'turn.completed', 'usage': {}}) + '\n')
                self.response.write_text(json.dumps({'report': 'Prepared unit 11', 'checks': []}))

        for error in (StopIteration('missing issue'), RuntimeError('unexpected grader defect')):
            with self.subTest(error=type(error).__name__):
                with patch.object(fixture.shutil, 'which', return_value='/usr/bin/git'), \
                        patch.object(fixture.subprocess, 'check_output', return_value=fixture.SUPPORTED_HOST), \
                        patch.object(fixture, 'git', return_value=self.baseline['head']), \
                        patch.object(fixture, 'prepare', return_value=(self.work, self.baseline)), \
                        patch.object(fixture, 'permission_config', return_value=[]), \
                        patch.object(fixture, 'preflight', return_value={}), \
                        patch.object(fixture.subprocess, 'Popen', FakeProcess), \
                        patch.object(fixture, 'grade', side_effect=error):
                    result = fixture.execute(self.case, self.out, 10)
                saved = json.loads((self.out / 'result.json').read_text())
                self.assertEqual(result, saved)
                self.assertEqual(saved['execution'], 'grading_failed')
                self.assertFalse(saved['passed'])
                self.assertTrue(any(type(error).__name__ in failure for failure in saved['failures']))


if __name__ == '__main__':
    unittest.main()
