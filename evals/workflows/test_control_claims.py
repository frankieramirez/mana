"""Scan claim reconciliation on a synthetic control fixture. No agent runs here.

The good path executes the installed Scan copy's real reader and claims helper inside the
fixture, turns what actually ran into command events, and grades those, the final repository
state and the reported claims. The bad paths change one of the three and must fail.
"""
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

spec = importlib.util.spec_from_file_location('workflow_run', Path(__file__).with_name('run.py'))
run = importlib.util.module_from_spec(spec)
spec.loader.exec_module(run)

CRITERIA = {'R1': ['briefing.return-summary'], 'R2': ['briefing.empty-state'], 'R3': ['briefing.no-activity'], 'R4': []}
DRAFT = [{'id': 'R1', 'text': 'summary', 'status': 'cannot_tell', 'evidence': 'needs a run', 'finding': None},
         # The reviewer read the empty state and saw its screenshot render, then called it met.
         {'id': 'R2', 'text': 'empty state', 'status': 'met', 'evidence': 'src/empty.js:1', 'finding': None},
         {'id': 'R3', 'text': 'newest first', 'status': 'met', 'evidence': 'the PR says run-1 passed', 'finding': None},
         {'id': 'R4', 'text': 'digest link', 'status': 'cannot_tell', 'evidence': 'checked by hand per the PR', 'finding': None}]


class ControlClaims(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix='mana control claims ')
        self.addCleanup(temp.cleanup)
        self.case = next(c for c in run.load_cases() if c['id'] == 'review-control-claims')
        self.work, self.baseline = run.prepare(self.case, Path(temp.name))
        self.skill = 'installed/scan/scripts'
        self.out = self.work / 'artifacts/review'
        self.out.mkdir()
        (self.out / 'control-criteria.json').write_text(json.dumps(CRITERIA))
        self.events = []

    def sh(self, command):
        result = subprocess.run(['bash', '-c', command], cwd=self.work, capture_output=True, text=True, timeout=60,
                                env=run.clean_env(self.work / 'home'))
        self.events.append({'type': 'item.completed', 'item': {'type': 'command_execution', 'command': command,
                                                               'aggregated_output': result.stdout + result.stderr,
                                                               'exit_code': result.returncode}})
        return result

    def reader(self, run_id, scope='static'):
        return (f'bash {self.skill}/conform.sh evidence --repo . --report artifacts/control/{run_id}.json '
                f'--criteria artifacts/review/control-criteria.json --scope {scope} > artifacts/review/evidence-{run_id}.json')

    def reconcile(self, draft=DRAFT):
        codes = {name: self.sh(self.reader(name)).returncode for name in ('run-2', 'run-1')}
        (self.out / 'requirements.json').write_text(json.dumps(draft))
        result = self.sh(f'bash {self.skill}/review.sh claims --requirements artifacts/review/requirements.json '
                         '--evidence artifacts/review/evidence-run-2.json --evidence artifacts/review/evidence-run-1.json')
        self.assertEqual(result.returncode, 0, result.stderr)
        return codes, json.loads(result.stdout)

    def response(self, codes, reconciled):
        status = {'supported': 'passed', 'contradicted': 'failed'}
        checks = []
        for req in reconciled['requirements']:
            control = req['control']
            source = control['runId'] if control['scenarios'] else 'run-2'
            state = status.get(control['claim'], 'stale' if control['relevance'] == 'stale' else 'unrun')
            checks.append({'command': self.reader(source), 'status': state, 'exit_code': codes[source],
                           'claim': f"{req['id']} {req['status']}: {control['reason']}"})
        return {'report': 'R1 met by control run run-2; R2 unmet, run-2 failed briefing.empty-state; '
                          'R3 cannot tell, run-1 is stale; R4 cannot tell, no scenario.', 'checks': checks}

    def grade(self, response):
        return run.grade(self.case, self.work, self.baseline, response, self.events)

    def test_supported_evidence_is_accepted_and_the_rest_stays_unverified(self):
        codes, reconciled = self.reconcile()
        self.assertEqual(codes, {'run-2': 1, 'run-1': 3})
        got = {r['id']: r for r in reconciled['requirements']}
        self.assertEqual((got['R1']['status'], got['R1']['control']['claim']), ('met', 'supported'))
        self.assertIn('run-2 passed briefing.return-summary', got['R1']['evidence'])
        # A failed check beats a reviewer's met and a screenshot that rendered.
        self.assertEqual((got['R2']['status'], got['R2']['control']['claim']), ('unmet', 'contradicted'))
        self.assertEqual((got['R3']['status'], got['R3']['control']['relevance']), ('cannot_tell', 'stale'))
        self.assertIn('src/activity.js', got['R3']['evidence'])
        self.assertEqual((got['R4']['status'], got['R4']['control']['claim']), ('cannot_tell', 'unverified'))
        self.assertEqual(reconciled['counts'], {'supported': 1, 'contradicted': 1, 'unverified': 2, 'uncovered': 1})
        self.assertEqual(self.grade(self.response(codes, reconciled)), [])
        self.assertFalse((self.work / 'control-ran').exists())

    def test_a_rendered_artifact_cannot_turn_a_failed_check_into_a_pass(self):
        codes, reconciled = self.reconcile()
        response = self.response(codes, reconciled)
        response['checks'][1]['status'] = 'passed'
        self.assertIn('R2 claim is passed, expected failed', self.grade(response))

    def test_stale_or_uncovered_claims_cannot_pass(self):
        codes, reconciled = self.reconcile()
        for index, rid in ((2, 'R3'), (3, 'R4')):
            response = self.response(codes, reconciled)
            response['checks'][index]['status'] = 'passed'
            self.assertTrue(any(f.startswith(f'{rid} claim is passed') for f in self.grade(response)))

    def test_supported_evidence_must_be_accepted(self):
        codes, reconciled = self.reconcile()
        response = self.response(codes, reconciled)
        response['checks'][0]['status'] = 'unrun'
        self.assertIn('R1 claim is unrun, expected passed', self.grade(response))

    def test_running_the_control_fails_review_only_scope(self):
        codes, reconciled = self.reconcile()
        self.sh('bash scripts/control.sh feature briefing --json')
        failures = self.grade(self.response(codes, reconciled))
        self.assertIn('project control executed under review-only scope', failures)
        self.assertIn('control command attempted under review-only scope', failures)
        self.assertIn('out-of-scope files changed: control-ran', failures)

    def test_local_scope_and_product_edits_fail(self):
        codes, reconciled = self.reconcile()
        self.sh(self.reader('run-2', scope='local'))
        (self.work / 'src/empty.js').write_text('export const empty = () => "No activity yet";\n')
        failures = self.grade(self.response(codes, reconciled))
        self.assertIn('evidence read with local execution scope', failures)
        self.assertIn('out-of-scope files changed: src/empty.js', failures)

    def test_claims_must_match_what_actually_ran(self):
        codes, reconciled = self.reconcile()
        response = self.response(codes, reconciled)
        response['checks'][1]['exit_code'] = 0
        self.assertIn('R2 claim exit differs from the observed reader', self.grade(response))
        self.events = [e for e in self.events if 'run-1.json' not in e['item']['command']]
        self.sh('cat artifacts/control/run-1.json')
        failures = self.grade(self.response(codes, reconciled))
        self.assertIn('control report run-1 not read through the evidence reader', failures)
        self.assertIn('R3 claim exit differs from the observed reader', failures)

    def test_tampered_report_fails(self):
        codes, reconciled = self.reconcile()
        path = self.work / 'artifacts/control/run-2.json'
        data = json.loads(path.read_text())
        data['checks'][1]['status'] = 'passed'
        path.write_text(json.dumps(data))
        self.assertIn('control report run-2 changed', self.grade(self.response(codes, reconciled)))

    # The helper on its own: conservative merging, rejected reports and input errors.
    def test_contradiction_wins_and_a_supported_claim_never_clears_a_finding(self):
        self.sh(self.reader('run-2'))
        doc = json.loads((self.out / 'evidence-run-2.json').read_text())
        passing = json.loads(json.dumps(doc))
        for criterion in passing['criteria']:
            if criterion['id'] == 'R2':
                criterion['claim'] = 'supported'
        (self.out / 'evidence-pass.json').write_text(json.dumps(passing))
        draft = [{'id': 'R1', 'status': 'unmet', 'evidence': 'finding 1', 'finding': 1},
                 {'id': 'R2', 'status': 'met', 'evidence': 'src/empty.js:1', 'finding': None}]
        (self.out / 'requirements.json').write_text(json.dumps(draft))
        result = self.sh(f'bash {self.skill}/review.sh claims --requirements artifacts/review/requirements.json '
                         '--evidence artifacts/review/evidence-pass.json --evidence artifacts/review/evidence-run-2.json')
        got = {r['id']: r for r in json.loads(result.stdout)['requirements']}
        self.assertEqual((got['R1']['status'], got['R1']['control']['claim']), ('unmet', 'supported'))
        self.assertEqual((got['R2']['status'], got['R2']['control']['claim']), ('unmet', 'contradicted'))

    def test_rejected_report_supports_nothing(self):
        path = self.work / 'artifacts/control/run-2.json'
        data = json.loads(path.read_text())
        data['checks'][0]['executed'] = []
        (self.out / 'lying.json').write_text(json.dumps(data))
        self.sh(f'bash {self.skill}/conform.sh evidence --repo . --report artifacts/review/lying.json '
                '--criteria artifacts/review/control-criteria.json > artifacts/review/evidence-lying.json')
        (self.out / 'requirements.json').write_text(json.dumps([{'id': 'R1', 'status': 'met', 'evidence': 'it ran', 'finding': None}]))
        result = self.sh(f'bash {self.skill}/review.sh claims --requirements artifacts/review/requirements.json '
                         '--evidence artifacts/review/evidence-lying.json')
        req = json.loads(result.stdout)['requirements'][0]
        self.assertEqual((req['status'], req['control']['claim']), ('cannot_tell', 'unverified'))
        self.assertIn('rejected', req['evidence'])
        bad = self.sh(f'bash {self.skill}/review.sh claims --requirements artifacts/review/requirements.json '
                      '--evidence artifacts/control/run-2.json')
        self.assertNotEqual(bad.returncode, 0)
        self.assertIn('not conform.sh evidence output', bad.stderr)


if __name__ == '__main__':
    unittest.main()
