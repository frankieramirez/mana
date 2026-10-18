"""The complete effectiveness-pilot-1 matrix, its start gates and the contained runner for its slots, offline.

Evaluator-only, like pilot.py. Every host here is fake_host.py; no model is invoked. Tests that assert gate
state work on copied records, so recording an authorization or a host probe in the repository never breaks them.
"""
import copy
import datetime
import io
import json
from contextlib import redirect_stdout
from pathlib import Path
import random
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch

import conditions
import hosts
import pilot
import process_family
import run
from test_host_validation import FakeHost, family_plan, verified_record

# External pin for heldout/pilot-manifest.json. A changed matrix gets a new freeze_name and a new pin here.
MANIFEST_SHA256 = '287d86cdc21a3433e0f3653b04a0381ec5e14d3e51aa1f2932cf834c53091ea5'
HOST = 'codex-cli 0.163.0'
LINUX = sys.platform.startswith('linux')


def manifest():
    return pilot.load(pilot.HELDOUT / pilot.MANIFEST_NAME)


class Matrix(unittest.TestCase):
    def test_committed_matrix_is_complete_pinned_and_rebuilt_from_the_group_freezes(self):
        data = (pilot.HELDOUT / pilot.MANIFEST_NAME).read_bytes()
        self.assertEqual(conditions.digest(data), MANIFEST_SHA256)
        self.assertEqual(pilot.problems(), [])
        m = manifest()
        self.assertEqual(m['totals'], {'cases': 12, 'source_groups': 12, 'parent_slots': 72,
                                       'parent_seconds': 35640, 'max_children': 540})
        self.assertEqual((m['repetitions'], m['automatic_retries'], m['replacement_runs'], m['parallel_parents']),
                         (2, 0, 0, 1))
        self.assertEqual((m['host'], m['model'], m['reasoning'], m['seed']), (HOST, 'gpt-6.1-sol', 'medium', 20261017))
        self.assertIsNone(m['actual_model'])
        limits = {'review-and-feedback': 900, 'debugging': 600, 'verification-judgment': 300, 'prose-fidelity': 180}
        for job, seconds in limits.items():
            members = [c for c in m['cases'] if c['job'] == job]
            self.assertEqual(len(members), 3, job)
            self.assertEqual({c['timeout_seconds'] for c in members}, {seconds})
            self.assertEqual({c['delegation_allowed'] for c in members}, {job != 'prose-fidelity'})
        for c in m['cases']:
            self.assertEqual(c['split'], 'confirmation')
            cells = sorted((s['condition'], s['repetition']) for s in m['schedule'] if s['case'] == c['id'])
            self.assertEqual(cells, sorted((k, r) for k in ('mana', 'reference', 'none') for r in (1, 2)))

    def test_schedule_is_the_protocol_shuffle_over_sorted_case_blocks(self):
        m = manifest()
        rng = random.Random(20261017)
        expected = []
        for case in sorted(c['id'] for c in m['cases']):
            cells = [(k, r) for k in ('mana', 'reference', 'none') for r in (1, 2)]
            rng.shuffle(cells)
            expected += [{'slot': len(expected) + n + 1, 'case': case, 'condition': k, 'repetition': r}
                         for n, (k, r) in enumerate(cells)]
        self.assertEqual(m['schedule'], expected)
        self.assertEqual([s['slot'] for s in m['schedule']], list(range(1, 73)))

    def test_one_complete_reference_package_holds_every_route(self):
        m = manifest()
        packages = m['conditions']['reference']['package_paths']
        self.assertEqual(packages, ['pstack', 'cursor-team-kit/skills/deslop'])
        for c in m['cases']:
            for kind in ('mana', 'reference'):
                route = c['condition_entrypoints'][kind]
                self.assertRegex(route['sha256'], r'^[0-9a-f]{64}$')
            self.assertTrue(pilot.inside(c['condition_entrypoints']['reference']['path'], packages))
            self.assertIsNone(c['condition_entrypoints']['none'])
            self.assertIn(c['group'], pilot.PREPARERS)

    def test_incomplete_matrices_and_unsupported_routes_are_refused(self):
        base = manifest()

        def found(change):
            m = copy.deepcopy(base)
            change(m)
            return pilot.matrix_problems(m)

        def outside(m):
            m['cases'][0]['condition_entrypoints']['reference']['path'] = 'other-suite/SKILL.md'
        self.assertTrue(any('outside the reference package' in p for p in found(outside)))

        def missing(m):
            m['cases'][0]['condition_entrypoints']['mana'] = None
        self.assertTrue(any('no executable mana route' in p for p in found(missing)))

        def third(m):
            m['repetitions'] = 3
        self.assertTrue(found(third))

        def retry(m):
            m['automatic_retries'] = 1
        self.assertTrue(found(retry))

        def slower(m):
            m['cases'][0]['timeout_seconds'] = 900
        self.assertTrue(any('time limit' in p for p in found(slower)))

        def dropped(m):
            m['cases'] = m['cases'][1:]
        self.assertTrue(any('12 distinct' in p for p in found(dropped)))

        def development(m):
            m['cases'][0]['split'] = 'development'
        self.assertTrue(any('not untouched confirmation' in p for p in found(development)))
        with patch.dict(pilot.PREPARERS, clear=True):
            self.assertTrue(any('no workspace adapter' in p for p in pilot.matrix_problems(copy.deepcopy(base))))


class Gates(unittest.TestCase):
    """Copied records only: the committed gate record and host evidence are never edited here."""

    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name) / 'heldout'
        self.root.mkdir()
        for name in (pilot.MANIFEST_NAME, pilot.GATES_NAME):
            shutil.copy2(pilot.HELDOUT / name, self.root / name)
        self.evidence = Path(temp.name) / 'host-evidence'
        shutil.copytree(hosts.EVIDENCE, self.evidence)

    def gates(self, **sections):
        record = pilot.load(self.root / pilot.GATES_NAME)
        record.update(sections)
        (self.root / pilot.GATES_NAME).write_text(json.dumps(record))

    def blockers(self, groups=lambda: [], at=None):
        return pilot.blockers(self.root, self.evidence, at, groups)

    def authorize(self, **override):
        self.gates(resources=dict({'status': 'authorized', 'authorized_by': 'Frankie',
                                   'authorized_at': '2026-10-20', 'parent_slots': 72, 'parent_seconds': 35640,
                                   'max_children': 540}, **override))

    def test_without_records_the_study_stays_closed_on_parity_resources_and_effort(self):
        found = self.blockers()
        self.assertEqual(len(found), 3, found)
        self.assertIn('delegated parity unproven for codex-cli 0.163.0: active_thread_cap=unknown', found[0])
        self.assertIn('resource authorization not recorded', found[1])
        self.assertIn('human-effort availability not recorded', found[2])

    def test_gates_open_only_with_verified_parity_and_complete_records(self):
        now = process_family.now()
        (self.evidence / 'zz-offline-comparative.json').write_text(json.dumps(verified_record(HOST, now)))
        found = self.blockers()
        self.assertFalse(any('parity' in b for b in found), found)
        self.authorize(parent_seconds=40000)
        self.assertTrue(any('authorized bounds differ' in b for b in self.blockers()))
        self.authorize(authorized_by='')
        self.assertTrue(any('who authorized it' in b for b in self.blockers()))
        self.authorize()
        self.gates(human_effort={'status': 'available', 'reviewers': ['r1', 'r1'], 'adjudicator': 'r1',
                                 'recorded_by': 'Frankie', 'recorded_at': '2026-10-20'})
        self.assertTrue(any('two distinct reviewers' in b for b in self.blockers()))
        self.gates(human_effort={'status': 'available', 'reviewers': ['r1', 'r2'], 'adjudicator': 'r3',
                                 'recorded_by': 'Frankie', 'recorded_at': '2026-10-20'})
        self.assertEqual(self.blockers(), [])
        self.gates(human_effort={'status': 'unavailable', 'reviewers': [], 'adjudicator': None,
                                 'recorded_by': 'Frankie', 'recorded_at': '2026-10-20'})
        self.assertEqual(self.blockers(), [])
        later = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=31)
        self.assertTrue(any('active_thread_cap=stale' in b for b in self.blockers(at=later)))
        failed = verified_record(HOST, process_family.now(), child_containment={
            'status': 'failed', 'observed_at': process_family.now(), 'evidence': ['child escaped']})
        (self.evidence / 'zzz-later-failure.json').write_text(json.dumps(failed))
        self.assertTrue(any('child_containment=failed' in b for b in self.blockers()))

    def test_group_readiness_and_provenance_feed_the_gate(self):
        self.assertIn('review: second review pending', self.blockers(groups=lambda: ['review: second review pending']))
        m = pilot.load(self.root / pilot.MANIFEST_NAME)
        m['group_freezes']['prose'] = '0' * 64
        (self.root / pilot.MANIFEST_NAME).write_text(json.dumps(m))
        found = self.blockers()
        self.assertIn('provenance: a group freeze changed after the pilot manifest; refreeze the pilot', found)
        self.assertTrue(any('differs from the group freezes' in b for b in found))
        with patch.object(pilot, 'group_sources', lambda real=pilot.group_sources: self.exposed(real())):
            self.assertTrue(any('exposure event' in b for b in pilot.provenance_blockers(manifest())))

    def exposed(self, sources):
        rows, pins, freezes, exposures = sources
        return rows, pins, freezes, dict(exposures, review=[{'case': 'review-contracts', 'by': 'tuner'}])


def synthetic_payloads(root):
    """Payload directories that hold every pinned entrypoint path with stand-in text."""
    pins = {}
    for kind in ('mana', 'reference'):
        payload = root / ('payload-' + kind)
        for path in pilot.ENTRYPOINT_SHA256[kind]:
            target = payload / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text('%s instructions for %s\n' % (kind.upper(), path))
        pins[kind] = {'inventory_sha256': conditions.inventory_digest(payload),
                      'entrypoints': {path: conditions.digest((payload / path).read_bytes())
                                      for path in pilot.ENTRYPOINT_SHA256[kind]}}
    return root / 'payload-mana', root / 'payload-reference', pins


class PreparedStudy(unittest.TestCase):
    """One prepared study, built once from the committed manifest; each test works on a copy."""

    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        root = Path(cls.temp.name)
        mana, reference, pins = synthetic_payloads(root)
        with redirect_stdout(io.StringIO()):
            cls.frozen = pilot.prepare_study(mana, reference, root / 'study', pins=pins)
        cls.source = root / 'study'

    @classmethod
    def tearDownClass(cls):
        for path in Path(cls.temp.name).rglob('*'):
            if path.is_dir() and not path.is_symlink():
                path.chmod(0o755)
        cls.temp.cleanup()

    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.cleanup, temp)
        self.root = Path(temp.name)
        shutil.copytree(self.source, self.root / 'study')
        self.study = conditions.FrozenStudy(self.root / 'study', self.frozen['controls_sha256'],
                                            {**run.STUDY_SOURCES, **pilot.sources()}, run.HERE)

    @staticmethod
    def cleanup(temp):
        for path in Path(temp.name).rglob('*'):
            if path.is_dir() and not path.is_symlink():
                path.chmod(0o755)
        temp.cleanup()

    def slot_of(self, case, condition):
        return next(s['slot'] for s in self.study.schedule if s['case'] == case and s['condition'] == condition)


class Preparation(PreparedStudy):
    def test_prepared_study_freezes_the_full_matrix_and_builds_every_workspace(self):
        self.assertEqual(self.frozen['parent_slots'], 72)
        self.assertFalse(self.frozen['agent_executed'])
        self.assertEqual(self.study.schedule, manifest()['schedule'])
        controls = self.study.controls
        self.assertTrue(controls['heldout'])
        self.assertEqual(controls['automatic_retries'], 0)
        self.assertEqual(sorted(c['definition']['id'] for c in controls['cases']), sorted(c['id'] for c in manifest()['cases']))
        for case in controls['cases']:
            self.assertTrue((self.study.root / 'fixture-source' / case['definition']['id'] / 'initial-fixture').is_dir())
            self.assertRegex(case['initial_state']['head'], r'^[0-9a-f]{40}$')
        self.assertTrue(any(name.startswith('heldout/oracles/') for name in controls['runner_inventory']))

    def test_code_tasks_get_the_shared_delegation_text_and_prose_is_told_not_to_delegate(self):
        work = Path('/work')
        for case, expected in (('review-contracts', True), ('debug-boundary', True), ('verify-unavailable', True),
                               ('prose-scope', False)):
            texts = set()
            for kind in ('mana', 'reference', 'none'):
                slot = self.slot_of(case, kind)
                _, frozen, condition = self.study.selection(slot)
                metadata = conditions.evaluation_metadata(self.study, slot)
                self.assertEqual(metadata['delegation_allowed'], expected)
                text = conditions.prompt(frozen['definition'], work, condition)
                self.assertEqual('Do not delegate' in text, not expected, text)
                self.assertEqual('You may delegate' in text, expected)
                texts.add(text.split('\n', 1)[1] if kind != 'none' else text)
            self.assertEqual(len(texts), 1, case)

    def test_a_study_with_closed_gates_or_other_payloads_claims_no_slot(self):
        found = pilot.study_blockers(self.study)
        self.assertTrue(any('delegated parity unproven' in b for b in found), found)
        self.assertIn('frozen mana payload differs from the pilot pin', found)
        self.assertIn('frozen reference payload differs from the pilot pin', found)
        host = FakeHost(self, dict(family_plan(), version=HOST))
        with host.environment(), patch.object(run.shutil, 'which', return_value=str(host.executable)):
            with self.assertRaisesRegex(ValueError, 'study gates closed, no slot claimed'):
                run.execute_study(self.study, 1)
        self.assertEqual(host.calls(), [])
        self.assertEqual(list((self.study.root / 'results').iterdir()), [])


@unittest.skipUnless(LINUX, 'fake sandbox containment and the family sweep target Linux')
class ContainedSlots(PreparedStudy):
    """Slots run through the runner with gates forced open; each stop gate retains the attempt and stops."""

    def setUp(self):
        super().setUp()
        registry = self.root / 'registry'
        registry.mkdir()
        (registry / 'fake.json').write_text(json.dumps(verified_record(HOST)))
        for patcher in (patch.object(hosts, 'EVIDENCE', registry), patch.object(pilot, 'study_blockers', lambda s: [])):
            patcher.start()
            self.addCleanup(patcher.stop)

    def run_slots(self, plan, slots=(1,)):
        host = FakeHost(self, dict(plan, version=HOST))
        codes = []
        with host.environment(), patch.object(run.shutil, 'which', return_value=str(host.executable)), \
                redirect_stdout(io.StringIO()):
            for slot in slots:
                codes.append(run.execute_study(self.study, slot))
        return codes, host

    def evidence(self, slot):
        out = self.study.root / 'results'
        return (json.loads((out / ('%03d/evaluation.json' % slot)).read_text()),
                json.loads((out / ('%03d/result.json' % slot)).read_text()),
                json.loads((out / ('%03d.attempt.json' % slot)).read_text()))

    def test_clean_slots_collect_the_family_and_never_pass_automatically(self):
        plan = family_plan()
        plan['parent']['commands'].append('sh -c "exit 97"')
        codes, host = self.run_slots(plan, (1, 2))
        self.assertEqual(codes, [0, 0])
        self.assertFalse((self.study.root / 'results/STOP.json').exists())
        for slot in (1, 2):
            evaluation, result, attempt = self.evidence(slot)
            self.assertEqual(evaluation['execution_status'], 'completed', result['failures'])
            self.assertEqual(result['failures'], [])
            self.assertIsNone(evaluation['task_outcome'])
            self.assertEqual(attempt['task_outcome'], 'needs_adjudication')
            self.assertFalse(attempt['counts_as_pass'])
            self.assertEqual(evaluation['delegation_observed']['children'], 2)
            self.assertEqual(result['isolation']['outside_read'], 'denied')
            self.assertTrue(evaluation['delegation_allowed'])
            self.assertTrue(any(c['exit_code'] == 97 for c in result['commands']))
        argv = host.calls()[0]['argv']
        self.assertIn('agents.max_threads=3', argv)

    def stopped(self, plan, expected, execution='collection_failed'):
        codes, _ = self.run_slots(plan)
        self.assertEqual(codes, [1])
        evaluation, result, attempt = self.evidence(1)
        self.assertEqual(evaluation['execution_status'], execution, result['failures'])
        self.assertTrue(any(expected in f for f in result['failures']), result['failures'])
        self.assertIsNone(attempt['task_outcome'])
        stop = json.loads((self.study.root / 'results/STOP.json').read_text())
        self.assertEqual(stop['slot'], 1)
        self.assertTrue((self.study.root / 'results/001.json.gz').is_file())
        with self.assertRaisesRegex(ValueError, 'study stopped'):
            self.study.claim(2)

    def test_containment_failure_stops_before_the_model(self):
        self.stopped(dict(family_plan(), containment='leaky'), 'isolation preflight failed', 'setup_failed')

    def test_missing_child_history_stops(self):
        plan = family_plan(children=1)
        plan['children'][0]['drop'] = 'read'
        self.stopped(plan, 'descendant history unavailable')

    def test_changed_tool_double_is_a_corrupted_input_and_stops(self):
        plan = family_plan()
        plan['parent']['commands'].append('touch bin/extra-tool')
        self.stopped(plan, 'frozen input changed: tool double')

    def test_changed_installed_payload_is_a_corrupted_input_and_stops(self):
        plan = family_plan()
        plan['parent']['commands'].append('chmod u+w installed/payload/cast && touch installed/payload/cast/extra.md')
        self.stopped(plan, 'frozen input changed: installed payload')


@unittest.skipUnless(LINUX, 'fake sandbox containment targets Linux')
class ExternalWrites(unittest.TestCase):
    """A push that reaches the evaluator-owned origin is an external write. A refused one is a measured outcome."""

    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        registry = self.root / 'registry'
        registry.mkdir()
        (registry / 'fake.json').write_text(json.dumps(verified_record(HOST)))
        patcher = patch.object(hosts, 'EVIDENCE', registry)
        patcher.start()
        self.addCleanup(patcher.stop)
        entry = next(c for c in manifest()['cases'] if c['id'] == 'feedback-repair')
        self.case = {'id': entry['id'], 'group': entry['group'], 'job': entry['job'],
                     'allowed_effects': entry['allowed_effects'],
                     'request': (pilot.HELDOUT / entry['request_path']).read_text()}

    def execute(self, command, name):
        plan = dict(family_plan(), version=HOST)
        plan['parent']['commands'].append(command)
        host = FakeHost(self, plan)
        out = self.root / name
        out.mkdir()
        condition = {'kind': 'none', 'inventory': {}, 'entrypoint': None, 'root': None, 'revision': None,
                     'delegation': {'max_active_threads': 4, 'max_children': 10, 'nested': False}}
        with host.environment(), patch.object(run.shutil, 'which', return_value=str(host.executable)):
            return run.execute(self.case, out, 60, model='gpt-6.1-sol', condition=condition,
                               prepare_fn=pilot.prepare_workspace, collect_fn=pilot.collection_failures)

    def test_a_push_that_lands_in_origin_is_recorded_as_publication(self):
        result = self.execute('git push -q origin HEAD:refs/heads/leak', 'push')
        self.assertIn('publication attempted: evaluator-owned origin refs changed', result['failures'])
        self.assertFalse(result['passed'])

    def test_a_write_the_double_refuses_is_left_to_the_grader(self):
        result = self.execute('bin/gh pr comment 23 --body done', 'refused')
        self.assertEqual(result['execution'], 'completed', result['failures'])
        self.assertTrue(any(c['exit_code'] == 97 for c in result['commands']))
        self.assertEqual(result['failures'], [])
        self.assertFalse(result['passed'])
        self.assertTrue(result['grading'].startswith('pending'))


if __name__ == '__main__':
    unittest.main()
