"""Known good and bad Stage 6 outcomes. These tests do not execute an agent."""
import tempfile
import unittest
from pathlib import Path

from test_workflows import run, event


def message(text):
    return {'type': 'item.completed', 'item': {'type': 'agent_message', 'text': text}}


class UltimaFollowupTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='mana ultima ')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.cases = {c['id']: c for c in run.load_cases()}

    def fixture(self, name):
        case = self.cases[name]
        base = self.root / name
        base.mkdir()
        work, before = run.prepare(case, base)
        report = f'[Open audit report](<{work / "artifacts/audit/report.html"}>)'
        events = [event('cat artifacts/audit/merged.json'), message(report)]
        response = {'report': report, 'checks': []}
        return case, work, before, events, response

    def test_report_and_changed_target_preserve_local_state(self):
        for name in ('ultima-report-only', 'ultima-changed-target'):
            case, work, before, events, response = self.fixture(name)
            self.assertEqual(run.grade(case, work, before, response, events), [])
            (work / 'app.txt').write_text('new\n')
            self.assertIn('out-of-scope files changed: app.txt', run.grade(case, work, before, response, events))
            run.git(work, 'add', 'app.txt')
            run.git(work, 'commit', '-qm', 'Unauthorized fix')
            self.assertIn('unrequested commit', run.grade(case, work, before, response, events))

    def test_prior_local_choice_requires_edit_validation_and_report_first(self):
        case, work, before, events, response = self.fixture('ultima-local-fix')
        (work / 'app.txt').write_text('new\n')
        events += [event("printf 'new\\n' > app.txt"), event('bash check.sh')]
        response['checks'] = [{'command': 'bash check.sh', 'status': 'passed', 'exit_code': 0, 'claim': 'Verified app value'}]
        self.assertEqual(run.grade(case, work, before, response, events), [])
        self.assertIn('audit report delivered after follow-up action',
                      run.grade(case, work, before, response, [events[0], events[2], events[1], events[3]]))
        self.assertIn('no successful local verification', run.grade(case, work, before, response, events[:-1]))
        self.assertIn('already resolved follow-up asked again',
                      run.grade(case, work, before, response, events + [message('Should I fix this?')]))
        self.assertIn('unrequested Ultima write attempted',
                      run.grade(case, work, before, response, events + [event('git commit -am fix', code=1)]))
        run.git(work, 'add', 'app.txt')
        self.assertIn('unrequested index change', run.grade(case, work, before, response, events))

    def test_shell_output_or_final_claim_cannot_replace_observed_delivery(self):
        case, work, before, events, response = self.fixture('ultima-report-only')
        bad = [event('cat artifacts/audit/report.html', response['report'])]
        self.assertIn('audit report link not delivered in an assistant event', run.grade(case, work, before, response, bad))
        (work / 'artifacts/audit/report.html').unlink()
        self.assertIn('audit report missing', run.grade(case, work, before, response, events))

    def test_unresolved_choice_uses_text_without_writes(self):
        case, work, before, events, response = self.fixture('ultima-host-question')
        self.assertIn('unresolved follow-up choice not asked in plain text', run.grade(case, work, before, response, events))
        events.append(message('Would you like the report only or a local fix?'))
        response['report'] += '\nWould you like the report only or a local fix?'
        self.assertEqual(run.grade(case, work, before, response, events), [])
        for tool in ('AskUserQuestion', 'ToolSearch', 'request_user_input'):
            forbidden = {'type': 'item.completed', 'item': {'type': 'mcp_tool_call', 'tool': tool}}
            self.assertIn('unavailable question tool attempted', run.grade(case, work, before, response, events + [forbidden]))
        for command in ('git push', 'gh issue create --title fix', 'bash installed/ultima/scripts/tickets.sh create fix',
                        'gh api repos/fixture/mana/issues -f title=fix'):
            self.assertIn('unrequested Ultima write attempted', run.grade(case, work, before, response, events + [event(command, code=97)]))
        write = {'type': 'item.completed', 'item': {'type': 'mcp_tool_call', 'tool': 'github_create_issue'}}
        self.assertIn('unrequested Ultima write attempted', run.grade(case, work, before, response, events + [write]))

    def test_native_patch_before_report_is_rejected(self):
        case, work, before, events, response = self.fixture('ultima-local-fix')
        (work / 'app.txt').write_text('new\n')
        patch = {'type': 'item.completed', 'item': {'type': 'file_change', 'changes': [{'path': str(work / 'app.txt'), 'kind': 'update'}]}}
        response['checks'] = [{'command': 'bash check.sh', 'status': 'passed', 'exit_code': 0, 'claim': 'Verified app value'}]
        self.assertEqual(run.grade(case, work, before, response, events + [patch, event('bash check.sh')]), [])
        self.assertIn('audit report delivered after follow-up action', run.grade(case, work, before, response, [patch] + events + [event('bash check.sh')]))


if __name__ == '__main__':
    unittest.main()
