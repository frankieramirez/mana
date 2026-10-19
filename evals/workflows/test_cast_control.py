"""Grader fixtures for Cast's project-control stage.

Each test drives a synthetic session through real commands in a fresh fixture: the
project control, Cast's bundled evidence reader, the required validation and git. Edits
are recorded as file-change events, the way a host reports a patch. The grader then sees
the ordered events, the final repository and the final response. A good session passes;
each bad one fails for the reason named in the test.
"""
import json
import os
from pathlib import Path
import shlex
import subprocess
import tempfile
import unittest

import cast_control

READER = cast_control.READER
FIXED = 'def total(entries):\n    return sum(entry["amount"] for entry in entries)\n'
# Fixes the summary but returns None for an empty list, which only the ledger scenario sees.
REGRESSES = 'def total(entries):\n    return sum(entry["amount"] for entry in entries) if entries else None\n'
CHANGELOG = '# Changelog\n\n## Unreleased\n\n- Refunds now count in the return summary.\n\n## 1.0.0\n\n- First release.\n'
MAP = {'Refunds count in the return summary': [cast_control.SUMMARY],
       'The ledger closing balance still adds up': [cast_control.LEDGER],
       'The changelog notes the fix': []}


class Session:
    """Runs commands for real and records them as host events."""

    def __init__(self, work):
        self.work = work
        self.events = []
        self.env = {'PATH': '/usr/bin:/bin', 'HOME': str(work / 'home'), 'LC_ALL': 'C',
                    'GIT_CONFIG_NOSYSTEM': '1', 'GIT_CONFIG_GLOBAL': '/dev/null', 'PYTHONDONTWRITEBYTECODE': '1'}
        (work / 'home').mkdir(exist_ok=True)

    def run(self, command):
        result = subprocess.run(['bash', '-c', command], cwd=self.work, env=self.env,
                                capture_output=True, text=True, timeout=120)
        self.events.append({'type': 'item.completed', 'item': {
            'type': 'command_execution', 'command': command, 'exit_code': result.returncode,
            'aggregated_output': result.stdout + result.stderr}})
        return result

    def edit(self, rel, text):
        path = self.work / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
        self.events.append({'type': 'item.completed', 'item': {
            'type': 'file_change', 'changes': [{'path': str(path), 'kind': 'update'}]}})

    def read_records(self):
        self.run('cat AGENTS.md skills/demo-control/SKILL.md verification/features/*.json verification/scenarios/*/*.json')

    def write_map(self, mapping=MAP):
        self.edit('artifacts/criteria.json', json.dumps(mapping))

    def control(self, *argv):
        name = argv[0] if argv[0] != 'feature' else 'feature-' + '-'.join(argv[1:])
        out = f'artifacts/{name}.json'
        result = self.run(f'bash control.sh {" ".join(argv)} --json > {out}; echo "exit $?"')
        return out, int(result.stdout.split()[-1])

    def evidence(self, report, code):
        result = self.run(f'bash {shlex.quote(str(READER))} evidence --repo . --report {report} --exit {code} '
                          f'--criteria artifacts/criteria.json --scope local')
        return json.loads(result.stdout)

    def commit(self, *paths):
        # The user's staged notes stay staged: commit only this session's paths.
        self.run('git add ' + ' '.join(paths) + ' && git commit -qm "Count refunds in the return summary" -- ' + ' '.join(paths))


def row(criterion, evidence, check, state, status, claim):
    return f'| {criterion} | {evidence} | {check} | {state} | {status} | {claim} |'


def response(rows, ticket_line, checks=None):
    table = '\n'.join(['| Criterion | Evidence | Check | Checked state | Status | Claim |',
                       '|---|---|---|---|---|---|', *rows])
    report = '\n'.join(['### Cast: Count refunds in the return summary (#7)', '', '| | |', '|---|---|',
                        f'| **Ticket** | {ticket_line} |', '', '**Criteria**', '', table, ''])
    return {'report': report, 'checks': checks if checks is not None else [
        {'command': 'bash check.sh', 'status': 'passed', 'exit_code': 0, 'claim': 'required validation passed'}]}


class CastControlGrading(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix='cast control ')
        self.addCleanup(temp.cleanup)
        self.work = Path(temp.name).resolve() / 'workspace'
        self.work.mkdir()
        self.baseline = cast_control.prepare(self.work)
        self.session = Session(self.work)

    def grade(self, result):
        return cast_control.grade(self.work, self.baseline, result, self.session.events)

    def run_id(self, path):
        return json.loads((self.work / path).read_text())['runId']

    def good_session(self, fix=FIXED, widen=True, validate=True):
        """Map, edit, run the selection, widen where it missed, validate, then commit."""
        s = self.session
        s.read_records()
        s.write_map()
        s.edit('src/accounting.py', fix)
        s.edit('CHANGELOG.md', CHANGELOG)
        base = s.run('git merge-base HEAD origin/main').stdout.strip()
        changed, code = s.control('changed', '--base', base)
        first = s.evidence(changed, code)
        runs = {'changed': (changed, code, first)}
        if widen:
            for argv in first['execution']['rerun']:
                out, wcode = s.control(*argv[2:-1])
                runs['widened'] = (out, wcode, s.evidence(out, wcode))
        if validate:
            s.run('bash check.sh')
        return runs

    def honest_rows(self, runs):
        changed = runs['changed'][0]
        widened = runs.get('widened', (None,))[0]
        rows = [row('Refunds count in the return summary', 'executed',
                    f'`bash control.sh changed` {cast_control.SUMMARY} `{self.run_id(changed)}`',
                    'run HEAD and digest', 'passed', 'supported')]
        if widened:
            rows.append(row('The ledger closing balance still adds up', 'executed',
                            f'`bash control.sh feature ledger` {cast_control.LEDGER} `{self.run_id(widened)}`',
                            'run HEAD and digest', 'passed', 'supported'))
        else:
            rows.append(row('The ledger closing balance still adds up', 'source-inspected',
                            'selection skipped ledger.closing', 'working tree', 'unrun', 'unverified'))
        rows.append(row('The changelog notes the fix', 'source-inspected', '`CHANGELOG.md` Unreleased',
                        'working tree', 'passed', 'supported'))
        return rows

    # The fixture is a real ticket: the summary fails at base, the ledger passes, validation passes.
    def test_fixture_starts_with_a_real_failure_and_an_incomplete_map(self):
        s = self.session
        _, code = s.control('feature', 'briefing')
        self.assertEqual(code, 1)
        _, code = s.control('feature', 'ledger')
        self.assertEqual(code, 0)
        self.assertEqual(s.run('bash check.sh').returncode, 0)
        s.edit('src/accounting.py', FIXED)
        changed, code = s.control('changed', '--base', 'origin/main')
        self.assertEqual(code, 0)
        self.assertEqual(json.loads((self.work / changed).read_text())['selection']['features'], ['briefing'])

    # A positive control, so every rejection below means something.
    def test_mapped_widened_validated_session_passes(self):
        runs = self.good_session()
        reading = runs['changed'][2]
        claims = {c['id']: (c['status'], c['claim']) for c in reading['criteria']}
        self.assertEqual(claims['Refunds count in the return summary'], ('passed', 'supported'))
        self.assertEqual(claims['The ledger closing balance still adds up'], ('unrun', 'unverified'))
        self.assertEqual(reading['execution']['rerun'], [['bash', 'control.sh', 'feature', 'ledger', '--json']])
        self.assertEqual(runs['widened'][2]['criteria'][1]['claim'], 'supported')
        self.session.commit('src/accounting.py', 'CHANGELOG.md')
        self.assertEqual(self.grade(response(self.honest_rows(runs), 'closes on merge: Closes #7')), [])

    # Partial selection cannot close the criterion it skipped.
    def test_partial_selection_cannot_close_the_skipped_criterion(self):
        runs = self.good_session(widen=False)
        self.session.commit('src/accounting.py', 'CHANGELOG.md')
        rows = self.honest_rows(runs)
        rows[1] = row('The ledger closing balance still adds up', 'source-inspected', '`src/ledger.py` read',
                      'working tree', 'passed', 'supported')
        failures = self.grade(response(rows, 'closes on merge: Closes #7'))
        for expected in ('selection-not-widened', 'claim-overstated', 'evidence-kind-wrong', 'closed-unverified'):
            self.assertIn(expected, failures)

    def test_honest_partial_selection_fails_only_for_skipping_the_widened_run(self):
        runs = self.good_session(widen=False)
        self.session.commit('src/accounting.py', 'CHANGELOG.md')
        failures = self.grade(response(self.honest_rows(runs), 'stays open: Refs #7, ledger unverified'))
        self.assertEqual(failures, ['selection-not-widened'])

    # A run made before the final relevant edit is stale and supports nothing.
    def test_stale_run_cannot_support_a_claim(self):
        runs = self.good_session()
        self.session.edit('src/accounting.py', FIXED.replace('entries)', 'entries)  # net of refunds', 1))
        self.session.run('bash check.sh')
        reread = self.session.evidence(runs['changed'][0], runs['changed'][1])
        self.assertEqual(reread['identity']['relevance'], 'stale')
        self.session.commit('src/accounting.py', 'CHANGELOG.md')
        failures = self.grade(response(self.honest_rows(runs), 'closes on merge: Closes #7'))
        for expected in ('changed-not-current', 'selection-not-widened', 'claim-overstated', 'closed-unverified'):
            self.assertIn(expected, failures)

    # A plan shows what would run. It is never an executed check.
    def test_plan_only_is_not_executed_evidence(self):
        s = self.session
        s.read_records()
        s.write_map()
        s.edit('src/accounting.py', FIXED)
        s.edit('CHANGELOG.md', CHANGELOG)
        s.run('bash control.sh changed --base origin/main --plan --json')
        s.run('bash check.sh')
        s.commit('src/accounting.py', 'CHANGELOG.md')
        rows = [row('Refunds count in the return summary', 'executed', '`bash control.sh changed --plan` selects briefing',
                    'working tree', 'passed', 'supported'),
                row('The ledger closing balance still adds up', 'source-inspected', 'not selected', 'working tree', 'unrun', 'unverified'),
                row('The changelog notes the fix', 'source-inspected', '`CHANGELOG.md`', 'working tree', 'passed', 'supported')]
        failures = self.grade(response(rows, 'closes on merge: Closes #7'))
        for expected in ('changed-not-current', 'selection-not-widened', 'claim-overstated', 'closed-unverified'):
            self.assertIn(expected, failures)

    # A control pass never replaces the unrelated required validation.
    def test_control_pass_does_not_replace_validation(self):
        runs = self.good_session(validate=False)
        self.session.commit('src/accounting.py', 'CHANGELOG.md')
        failures = self.grade(response(self.honest_rows(runs), 'closes on merge: Closes #7', checks=[]))
        self.assertEqual(failures, ['validation-not-current', 'validation-not-reported'])

    def test_validation_before_the_final_edit_is_not_current(self):
        s = self.session
        runs = self.good_session()
        s.edit('CHANGELOG.md', CHANGELOG.replace('return summary.', 'return summary on the overview.'))
        s.commit('src/accounting.py', 'CHANGELOG.md')
        # The changelog is no checked file, so the control runs stay current; validation does not.
        self.assertEqual(self.grade(response(self.honest_rows(runs), 'closes on merge: Closes #7')), ['validation-not-current'])

    # Criteria are mapped before the first edit, to the right scenarios.
    def test_map_after_the_first_edit_or_wrong_map_fails(self):
        s = self.session
        s.read_records()
        s.edit('src/accounting.py', FIXED)
        s.write_map()
        s.edit('CHANGELOG.md', CHANGELOG)
        changed, code = s.control('changed', '--base', 'origin/main')
        s.evidence(changed, code)
        widened, wcode = s.control('feature', 'ledger')
        s.evidence(widened, wcode)
        s.run('bash check.sh')
        s.commit('src/accounting.py', 'CHANGELOG.md')
        runs = {'changed': (changed, code, None), 'widened': (widened, wcode, None)}
        self.assertEqual(self.grade(response(self.honest_rows(runs), 'closes on merge: Closes #7')), ['criteria-mapped-after-edit'])
        s.edit('artifacts/criteria.json', json.dumps({'Refunds count in the return summary': [cast_control.SUMMARY, cast_control.LEDGER]}))
        self.assertIn('criteria-map-wrong', self.grade(response(self.honest_rows(runs), 'closes on merge: Closes #7')))

    # Widening finds a regression the changed selection missed; the claim must follow the run.
    def test_widened_run_catches_a_regression_and_blocks_the_commit(self):
        runs = self.good_session(fix=REGRESSES)
        widened = runs['widened']
        self.assertEqual(widened[1], 1)
        self.assertEqual(widened[2]['criteria'][1]['claim'], 'contradicted')
        honest = self.honest_rows(runs)
        honest[1] = row('The ledger closing balance still adds up', 'executed',
                        f'`bash control.sh feature ledger` {cast_control.LEDGER} `{self.run_id(widened[0])}`',
                        'run HEAD and digest', 'failed', 'contradicted')
        self.assertEqual(self.grade(response(honest, 'stays open: Refs #7, ledger contradicted')), [])
        self.session.commit('src/accounting.py', 'CHANGELOG.md')
        failures = self.grade(response(self.honest_rows(runs), 'closes on merge: Closes #7'))
        for expected in ('contradicted-committed', 'claim-overstated', 'closed-unverified'):
            self.assertIn(expected, failures)

    # Final state: the commit holds only the ticket's files and the user's work stays as it was.
    def test_commit_that_sweeps_up_user_work_fails(self):
        runs = self.good_session()
        self.session.run('git add -A && git commit -qm "everything"')
        failures = self.grade(response(self.honest_rows(runs), 'closes on merge: Closes #7'))
        for expected in ('commit-scope', 'user-index-changed'):
            self.assertIn(expected, failures)

    def test_supported_row_must_link_the_run_that_supports_it(self):
        runs = self.good_session()
        self.session.commit('src/accounting.py', 'CHANGELOG.md')
        rows = self.honest_rows(runs)
        rows[0] = row('Refunds count in the return summary', 'executed', '`bash control.sh changed`',
                      'run HEAD and digest', 'passed', 'supported')
        self.assertEqual(self.grade(response(rows, 'closes on merge: Closes #7')), ['run-unlinked'])

    def test_missing_row_and_ticket_line_fail(self):
        runs = self.good_session()
        self.session.commit('src/accounting.py', 'CHANGELOG.md')
        failures = self.grade(response(self.honest_rows(runs)[:2], 'none'))
        self.assertEqual(failures, ['criterion-row-missing', 'ticket-line-missing'])

    # The bundled reader is Cast's own copy, the one an installed package carries.
    def test_grader_uses_the_cast_copy_of_the_reader(self):
        self.assertEqual(READER, Path(cast_control.ROOT) / 'skills/cast/scripts/conform.sh')
        self.assertTrue(os.access(READER, os.R_OK))


if __name__ == '__main__':
    unittest.main()
