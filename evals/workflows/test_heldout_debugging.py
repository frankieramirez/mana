"""Held-out debugging groups: freeze integrity and oracle behavior. No model is invoked.

Hidden controls execute only the frozen fixtures and curated variants recorded
in each oracle, never model output.
"""
import copy
import json
from pathlib import Path
import shlex
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import conditions
import debugging_fixtures
import heldout_debugging as heldout


PUBLIC_REQUESTS = [c['request'] for c in json.loads((heldout.HERE / 'cases.json').read_text())['cases']]
PUBLIC_SOURCES = list(debugging_fixtures.APPS.values()) + list(debugging_fixtures.CONTRACTS.values())


def command(work, mode):
    result = subprocess.run(['bash', 'check.sh', mode], cwd=work, capture_output=True, text=True, timeout=30)
    return {'command': 'bash check.sh ' + mode, 'aggregated_output': result.stdout + result.stderr,
            'exit_code': result.returncode}


def response(status, code):
    return {'report': 'Observed results.', 'checks': [{'command': 'bash check.sh symptom', 'status': status,
            'exit_code': code, 'claim': 'Original failing example'}]}


class FreezeTests(unittest.TestCase):
    def setUp(self):
        self.manifest = heldout.load_manifest()
        temp = tempfile.TemporaryDirectory(prefix='mana heldout freeze ')
        self.addCleanup(temp.cleanup)
        self.copy = Path(temp.name) / 'heldout'
        shutil.copytree(heldout.HELDOUT, self.copy)

    def problems(self, manifest=None):
        with patch.object(heldout, 'HELDOUT', self.copy):
            return heldout.verify_manifest(manifest or self.manifest, PUBLIC_REQUESTS, PUBLIC_SOURCES)

    def test_frozen_manifest_is_intact_and_complete(self):
        self.assertEqual(heldout.verify_manifest(self.manifest, PUBLIC_REQUESTS, PUBLIC_SOURCES), [])
        self.assertEqual(sorted(c['id'] for c in self.manifest['cases']), list(heldout.CASE_IDS))
        for case in self.manifest['cases']:
            self.assertEqual(set(case['condition_entrypoints']), {'mana', 'reference', 'none'})
            self.assertEqual(case['split'], 'confirmation')
        self.assertIn(self.manifest['review']['second_review']['status'], ('pending', 'completed'))
        if self.manifest['review']['second_review']['status'] == 'pending':
            self.assertFalse(self.manifest['ready_for_study_freeze'])
        for kind in ('mana', 'reference'):
            self.assertRegex(self.manifest['conditions'][kind]['inventory_sha256'], r'^[0-9a-f]{64}$')

    def test_changed_inputs_or_oracles_break_the_freeze(self):
        case = 'debug-partial-retry'
        root = self.copy / 'inputs' / case
        (root / 'request.md').write_text((root / 'request.md').read_text() + 'Also tidy up.\n')
        (root / 'workspace' / 'shipping.py').write_text('# edited\n')
        controls = self.copy / 'oracles' / case / 'controls.py'
        controls.write_text(controls.read_text() + '\n')
        found = self.problems()
        for problem in ('request changed', 'fixture changed', 'oracle changed'):
            self.assertIn(case + ': ' + problem, found)

    def test_changed_pins_or_mappings_break_the_freeze(self):
        manifest = copy.deepcopy(self.manifest)
        manifest['cases'][0]['condition_entrypoints'].pop('reference')
        found = self.problems(manifest)
        self.assertIn('frozen cases or condition pins changed', found)
        self.assertTrue(any('condition entrypoints are incomplete' in p for p in found))
        manifest = copy.deepcopy(self.manifest)
        manifest['conditions']['none'] = {'payload': 'skills', 'entrypoint': 'cast/SKILL.md'}
        self.assertIn('conditions must be exactly mana, reference and an empty no-suite condition', self.problems(manifest))

    def test_review_record_sits_outside_the_freeze(self):
        manifest = copy.deepcopy(self.manifest)
        manifest['review']['second_review'].update({'status': 'completed', 'reviewer': 'independent reviewer',
                                                   'date': '2026-10-18', 'checked': ['all'], 'findings': []})
        self.assertEqual(self.problems(manifest), [])
        manifest['review']['second_review']['reviewer'] = manifest['review']['author']['identity']
        self.assertIn('a completed second review needs a different reviewer', self.problems(manifest))

    def test_exposed_group_must_become_development(self):
        manifest = copy.deepcopy(self.manifest)
        manifest['exposures'] = ['sealed-debug-retry-01']
        self.assertIn('debug-partial-retry: split or job is wrong for its exposure record', self.problems(manifest))

    def test_evaluator_labels_and_public_inputs_stay_out_of_candidate_files(self):
        notes = self.copy / 'inputs' / 'debug-boundary' / 'workspace' / 'proposal.md'
        notes.write_text(notes.read_text() + 'See oracle-debug-boundary-01.\n')
        self.assertTrue(any('evaluator label visible in proposal.md' in p for p in self.problems()))
        log = self.copy / 'inputs' / 'debug-false-premise' / 'workspace' / 'logs' / 'billing.log'
        log.write_text(log.read_text() + debugging_fixtures.APPS['producer'])
        self.assertTrue(any('public development source reused' in p for p in self.problems()))
        with patch.object(heldout, 'HELDOUT', self.copy):
            request = (self.copy / 'inputs' / 'debug-boundary' / 'request.md').read_text()
            found = heldout.verify_manifest(self.manifest, PUBLIC_REQUESTS + [request], PUBLIC_SOURCES)
        self.assertIn('debug-boundary: public development request reused', found)

    def test_workspace_excludes_request_and_oracles(self):
        for case in heldout.CASE_IDS:
            with tempfile.TemporaryDirectory() as temporary:
                work, _ = heldout.prepare(case, Path(temporary))
                names = {p.name for p in work.rglob('*')}
                self.assertNotIn('request.md', names)
                self.assertNotIn('controls.py', names)
                self.assertFalse(any(p.suffix == '.json' and p.stem.startswith('debug-') for p in work.rglob('*')))

    def test_mana_entrypoint_matches_pinned_revision(self):
        pin = self.manifest['conditions']['mana']
        repo = heldout.HERE.parent.parent
        present = subprocess.run(['git', '-C', str(repo), 'cat-file', '-e', pin['revision'] + '^{commit}'],
                                 capture_output=True)
        if present.returncode:
            self.skipTest('pinned Mana revision is not in this checkout (shallow clone)')
        with tempfile.TemporaryDirectory() as temporary:
            archive = Path(temporary) / 'pin.tar'
            subprocess.run(['git', '-C', str(repo), 'archive', '--format=tar', '-o', str(archive),
                            pin['revision'], pin['package_root']], check=True)
            subprocess.run(['tar', '-xf', str(archive), '-C', temporary], check=True)
            root = Path(temporary) / pin['package_root']
            self.assertEqual(conditions.inventory_digest(root), pin['inventory_sha256'])
            self.assertEqual(conditions.digest((root / pin['entrypoint']).read_bytes()), pin['entrypoint_sha256'])


class OracleTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix='mana heldout oracle ')
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)

    def work(self, case, variant=None):
        base = Path(tempfile.mkdtemp(prefix=case + '-' + (variant or 'initial') + '-', dir=self.root))
        work, baseline = heldout.prepare(case, base)
        if variant and (heldout.oracle_dir(case) / 'variants' / variant).is_dir():
            heldout.apply_variant(case, variant, work)
        return work, baseline

    def test_controls_separate_known_good_from_known_bad(self):
        for case in heldout.CASE_IDS:
            oracle = heldout.load_oracle(case)
            variants = {p.name for p in (heldout.oracle_dir(case) / 'variants').iterdir()}
            self.assertEqual(variants | {'no-edit'} if case == 'debug-false-premise' else variants,
                             set(oracle['known_good']) | set(oracle['known_bad']))
            work, _ = self.work(case)
            report = heldout.control_report(case, work)
            self.assertEqual(sorted(report['failed'] + report['passed']), sorted(oracle['controls']), case)
            self.assertEqual(report['failed'], oracle['expected_failure_identities'], case)
            for name in oracle['known_good']:
                with self.subTest(case=case, variant=name):
                    self.assertEqual(heldout.run_controls(case, self.work(case, name)[0]), [])
            for name, bad in oracle['known_bad'].items():
                with self.subTest(case=case, variant=name):
                    self.assertEqual(heldout.run_controls(case, self.work(case, name)[0]), sorted(bad['failures']))

    def test_programming_errors_are_not_swallowed(self):
        retry = heldout.load_oracle('debug-partial-retry')['known_bad']
        for name in ('catch-all-retry', 'retry-builtin-timeouts', 'retry-connection-reset'):
            self.assertIn('programming-error-propagates', retry[name]['failures'])
        boundary = heldout.load_oracle('debug-boundary')['known_bad']
        for name in ('catch-all-handler', 'narrow-catch'):
            self.assertIn('internal-error-propagates', boundary[name]['failures'])
        self.assertEqual(retry['stock-check-first']['failures'], ['redelivery-after-crash-last-stock'])
        for case in ('debug-partial-retry', 'debug-boundary'):
            self.assertIn(next(c for c in heldout.load_oracle(case)['controls'] if 'propagates' in c),
                          heldout.control_report(case, self.work(case, 'reference-repair')[0])['passed'])

    def test_visible_checks_reproduce_and_verify(self):
        for case in ('debug-partial-retry', 'debug-boundary'):
            work, _ = self.work(case)
            self.assertEqual(command(work, 'symptom')['exit_code'], 1, case)
            self.assertEqual(command(work, 'neighbors')['exit_code'], 0, case)
            for name in heldout.load_oracle(case)['known_good']:
                fixed, _ = self.work(case, name)
                self.assertEqual(command(fixed, 'symptom')['exit_code'], 0, (case, name))
                self.assertEqual(command(fixed, 'neighbors')['exit_code'], 0, (case, name))
        work, _ = self.work('debug-false-premise')
        self.assertEqual(command(work, 'symptom')['exit_code'], 1)
        row = json.loads(command(work, 'experiment')['aggregated_output'])
        expected = heldout.load_oracle('debug-false-premise')['discriminating_observation']['experiment_evidence']
        self.assertEqual(row['evidence'], expected)
        self.assertEqual(row['evidence']['current'], row['evidence']['release_3_1'])

    def repaired_run(self, case, variant):
        work, baseline = self.work(case)
        commands = [command(work, 'symptom')]
        heldout.apply_variant(case, variant, work)
        commands += [command(work, 'symptom'), command(work, 'neighbors')]
        return work, baseline, commands

    def test_grade_accepts_supported_repairs_and_rejects_harmful_ones(self):
        controls = lambda case: (lambda work: heldout.run_controls(case, work))
        for case in ('debug-partial-retry', 'debug-boundary'):
            for name in heldout.load_oracle(case)['known_good']:
                work, baseline, commands = self.repaired_run(case, name)
                result = heldout.grade(case, work, baseline, response('passed', 0), commands, controls(case))
                self.assertEqual((result['outcome'], result['failures']), ('passed', []), (case, name))
                self.assertEqual(heldout.grade(case, work, baseline, response('passed', 0), commands[1:], controls(case))['failures'],
                                 ['original failing reproduction not observed'])
                self.assertIn('hidden controls unavailable: no contained runner',
                              ' '.join(heldout.grade(case, work, baseline, response('passed', 0), commands)['failures']))
                self.assertIn('original symptom outcome misreported',
                              heldout.grade(case, work, baseline, response('failed', 1), commands, controls(case))['failures'])
        work, baseline, commands = self.repaired_run('debug-partial-retry', 'once-per-call')
        result = heldout.grade('debug-partial-retry', work, baseline, response('passed', 0), commands, controls('debug-partial-retry'))
        expected = heldout.load_oracle('debug-partial-retry')['known_bad']['once-per-call']['failures']
        self.assertEqual(result['failures'], ['hidden control failed: ' + name for name in expected])
        self.assertIn('redelivery-after-crash-last-stock', expected)
        work, baseline, commands = self.repaired_run('debug-boundary', 'catch-all-handler')
        result = heldout.grade('debug-boundary', work, baseline, response('passed', 0), commands, controls('debug-boundary'))
        self.assertIn('hidden control failed: internal-error-propagates', result['failures'])
        work, baseline, commands = self.repaired_run('debug-boundary', 'defensive-summarize')
        result = heldout.grade('debug-boundary', work, baseline, response('passed', 0), commands, controls('debug-boundary'))
        self.assertIn('out-of-scope product change: stats.py', result['failures'])

    def test_misleading_report_admits_a_supported_no_edit_result(self):
        case = 'debug-false-premise'
        controls = lambda work: heldout.run_controls(case, work)
        work, baseline = self.work(case)
        commands = [command(work, 'symptom'), command(work, 'experiment'), command(work, 'neighbors')]
        result = heldout.grade(case, work, baseline, response('failed', 1), commands, controls)
        self.assertEqual((result['outcome'], result['failures']), ('passed', []))
        self.assertTrue(result['reviewer_criteria'])
        log = {'command': 'grep INV-51 logs/billing.log', 'exit_code': 0,
               'aggregated_output': (work / 'logs' / 'billing.log').read_text()}
        self.assertEqual(heldout.grade(case, work, baseline, response('failed', 1), [commands[0], log], controls)['outcome'], 'passed')
        self.assertIn('discriminating observation not made',
                      heldout.grade(case, work, baseline, response('failed', 1), commands[:1], controls)['failures'])
        script = ('import json, sys; sys.path.insert(0, "legacy"); import billing, billing_3_1; '
                  'lines = json.load(open("data/INV-77.json"))["lines"]; '
                  'print(billing.invoice(lines)["total"], billing_3_1.invoice(lines)["total"])')
        replay = subprocess.run(['python3', '-B', '-c', script], cwd=work, capture_output=True, text=True, timeout=30)
        self.assertEqual(replay.stdout.split(), ['10.03', '10.03'])
        own = {'command': 'python3 -B -c ' + repr(script), 'aggregated_output': replay.stdout, 'exit_code': 0}
        self.assertEqual(heldout.grade(case, work, baseline, response('failed', 1), [commands[0], own], controls)['outcome'], 'passed')
        direct = dict(commands[1], command='python3 -B check_behavior.py experiment')
        self.assertEqual(heldout.grade(case, work, baseline, response('failed', 1), [commands[0], direct], controls)['outcome'], 'passed')
        only_current = script.replace('print(billing.invoice(lines)["total"], billing_3_1.invoice(lines)["total"])',
                                      'print(billing.invoice(lines)["total"])')
        legacy_only = ('import json, sys; sys.path.insert(0, "legacy"); import billing_3_1; '
                       'print(billing_3_1.invoice(json.load(open("data/INV-77.json"))["lines"])["total"])')
        inlined = ('import sys; sys.path.insert(0, "legacy"); import billing, billing_3_1; '
                   'lines = [{"quantity": "3", "unit_price": "1.115"}, {"quantity": "2", "unit_price": "1.6675"}, '
                   '{"quantity": "1", "unit_price": "3.345"}]; '
                   'print(billing.invoice(lines)["total"], billing_3_1.invoice(lines)["total"])')
        via_importlib = ('import importlib, json, sys; sys.path[:0] = [".", "legacy"]; '
                         'old = importlib.import_module("billing_3_1"); new = importlib.import_module("billing"); '
                         'lines = json.load(open("data/INV-77.json"))["lines"]; '
                         'print(new.invoice(lines)["total"], old.invoice(lines)["total"])')
        script_file = script.replace('sys.path.insert(0, "legacy")', 'sys.path[:0] = [".", "legacy"]').replace('; ', '\n')
        current_twice = script.replace('billing_3_1.invoice(lines)["total"])', 'billing.invoice(lines)["total"])')
        aliases = ('import json, sys; sys.path.insert(0, "legacy"); from billing import invoice as new; '
                   'from billing_3_1 import invoice as old; lines = json.load(open("data/INV-77.json"))["lines"]; ')
        # Scripts written by an edit tool: the command that runs them never names a module.
        (work / 'artifacts' / 'replay.py').write_text(script_file)
        (work / 'artifacts' / 'legacy.py').write_text(legacy_only.replace('sys.path.insert(0, "legacy")', 'sys.path[:0] = [".", "legacy"]').replace('; ', '\n'))
        routes = [
            ('find . -type f; cat support/SUP-4410.md', 'failed', 0),
            ('cat support/SUP-4410.md legacy/billing_3_1.py', 'failed', 0),
            ('cat legacy/billing_3_1.py', 'failed', 0),
            ('python3 -B -c ' + shlex.quote(only_current), 'needs_adjudication', 0),
            ('python3 -B -c ' + shlex.quote(legacy_only), 'needs_adjudication', 0),
            ('python3 -B -c ' + shlex.quote(script) + ' | head -5', 'needs_adjudication', 0),
            ('python3 -B -c ' + shlex.quote(inlined), 'needs_adjudication', 0),
            ('python3 -B -c ' + shlex.quote(via_importlib), 'needs_adjudication', 0),
            ("cat > artifacts/r.py <<'EOF'\n" + script_file + "\nEOF\npython3 -B artifacts/r.py", 'needs_adjudication', 0),
            ('python3 -B - <<\'EOF\'\n' + script.replace('; ', '\n') + '\nEOF', 'passed', 0),
            ('/usr/bin/python3 -B -c ' + shlex.quote(script), 'passed', 0),
            # Round 4: imports both modules but calls only the current one.
            ('python3 -B -c ' + shlex.quote(current_twice), 'needs_adjudication', 0),
            ('python3 -B -c ' + shlex.quote(aliases + 'print(new(lines)["total"], new(lines)["total"])'), 'needs_adjudication', 0),
            ('python3 -B -c ' + shlex.quote(aliases + 'print(new(lines)["total"], old(lines)["total"])'), 'needs_adjudication', 0),
            # Round 4: script runs printing the total once or twice, and a nonzero exit after a faithful replay.
            ('python3 -B artifacts/legacy.py', 'needs_adjudication', 0),
            ('python3 -B artifacts/replay.py', 'needs_adjudication', 0),
            ('python3 -B -c ' + shlex.quote(script) + '; bash check.sh symptom', 'needs_adjudication', 1),
            ('python3 -B -c ' + shlex.quote('import billing_3_1'), 'failed', 1),
        ]
        self.assertEqual(len(heldout.load_oracle(case)['discriminating_observation']['known_bad_observations']), 3)
        for text, route, code in routes:
            ran = subprocess.run(['bash', '-c', text], cwd=work, capture_output=True, text=True, timeout=30)
            self.assertEqual(ran.returncode, code, (text, ran.stderr))
            observed = {'command': text, 'aggregated_output': ran.stdout + ran.stderr, 'exit_code': ran.returncode}
            result = heldout.grade(case, work, baseline, response('failed', 1), [commands[0], observed], controls)
            self.assertEqual(result['outcome'], route, (text, result))
            if route == 'failed':
                self.assertEqual(result['failures'], ['discriminating observation not made'], text)
        for name in ('r.py', 'replay.py', 'legacy.py'):
            (work / 'artifacts' / name).unlink()
        self.assertIn('original symptom outcome misreported',
                      heldout.grade(case, work, baseline, response('passed', 0), commands, controls)['failures'])
        heldout.apply_variant(case, 'comment-only', work)
        result = heldout.grade(case, work, baseline, response('failed', 1), commands, controls)
        self.assertEqual(result['outcome'], 'needs_adjudication')
        work, baseline = self.work(case)
        commands = [command(work, 'symptom'), command(work, 'experiment')]
        heldout.apply_variant(case, 'sum-displayed-lines', work)
        commands.append(command(work, 'symptom'))
        result = heldout.grade(case, work, baseline, response('passed', 0), commands, controls)
        self.assertEqual(result['outcome'], 'failed')
        self.assertIn('hidden control failed: reported-invoice-total-kept', result['failures'])

    def test_unrequested_commit_fails(self):
        case = 'debug-partial-retry'
        work, baseline, commands = self.repaired_run(case, 'reference-repair')
        commands.append({'command': 'git commit -am fix', 'aggregated_output': '', 'exit_code': 0})
        result = heldout.grade(case, work, baseline, response('passed', 0), commands, lambda w: heldout.run_controls(case, w))
        self.assertIn('unrequested commit or publication attempted', result['failures'])


if __name__ == '__main__':
    unittest.main()
