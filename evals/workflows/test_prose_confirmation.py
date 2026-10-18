"""Offline confirmation-case freeze, oracle and gate controls; never invoke a model."""
import copy
import json
from pathlib import Path
import re
import shutil
import tempfile
import unittest
from unittest import mock

import conditions
import prose_ablation as pa
import prose_confirmation as pc

SET = pc.CASE_SET


def oracle_for(case):
    return json.loads((SET / 'oracles' / (case['source_group'] + '.json')).read_text())


class Workspace(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        _, self.cases = pc.load_cases()
        self.by_id = {c['id']: c for c in self.cases}

    def copy_set(self):
        target = self.root / 'case-set'
        shutil.copytree(SET, target)
        return target

    def edit_json(self, path, change):
        data = json.loads(path.read_text())
        change(data)
        path.write_bytes(conditions.encoded(data))

    def set_review(self, case_set, **fields):
        """Write the second review this test needs, whatever the committed record holds."""
        review = {'status': 'pending', 'reviewer': None, 'date': None, 'freeze_sha256': None,
                  'contested_groups': [], 'notes': None, **fields}
        self.edit_json(case_set / 'review.json', lambda r: r.update(second_review=review))

    def complete_review(self, case_set, **fields):
        lock = json.loads((case_set / 'freeze.json').read_text())
        self.set_review(case_set, **{'status': 'complete', 'reviewer': 'second-reviewer', 'date': '2026-10-18',
                                     'freeze_sha256': lock['freeze_sha256'], 'notes': 'reviewed', **fields})
        return lock


class LockTests(Workspace):
    def test_committed_lock_verifies(self):
        report = pc.verify()
        self.assertEqual(report['parent_slots'], 36)
        self.assertEqual(sorted(report['groups'].values()), sorted(pc.GROUP_KINDS))
        self.assertEqual(report['exposed_groups'], [])
        self.assertIn(report['second_review'], ('pending', 'complete'))
        self.assertFalse(report['agent_executed'])

    def test_a_pending_second_review_is_the_only_open_gate(self):
        case_set = self.copy_set()
        self.set_review(case_set)
        report = pc.verify(case_set)
        self.assertEqual(report['second_review'], 'pending')
        self.assertEqual(report['open_gates'], ['second review pending'])
        self.assertFalse(report['confirmation_ready'])

    def test_a_completed_uncontested_review_on_this_freeze_makes_the_study_ready(self):
        case_set = self.copy_set()
        self.complete_review(case_set)
        report = pc.verify(case_set)
        self.assertEqual(report['open_gates'], [])
        self.assertTrue(report['confirmation_ready'])

    def test_the_lock_pins_the_screen_code(self):
        lock = json.loads((SET / 'freeze.json').read_text())
        self.assertEqual(lock['screen_source'], 'evals/workflows/prose_confirmation.py')
        self.assertEqual(lock['screen_sha256'], conditions.digest((pc.HERE / 'prose_confirmation.py').read_bytes()))
        case_set = self.copy_set()
        edited = self.root / 'edited'
        edited.mkdir()
        source = (pc.HERE / 'prose_confirmation.py').read_bytes()
        (edited / 'prose_confirmation.py').write_bytes(source.replace(b'|though|while)', b'|though|while|so)'))
        self.assertNotEqual((edited / 'prose_confirmation.py').read_bytes(), source)
        with mock.patch.object(pc, 'HERE', edited):
            with self.assertRaisesRegex(ValueError, 'freeze.json does not match'):
                pc.verify(case_set)

    def test_lock_pins_payloads_sources_requests_oracles_and_schedule(self):
        lock = json.loads((SET / 'freeze.json').read_text())
        record, set_digest = pa.load_payload_set()
        self.assertEqual(lock['payload_set_sha256'], set_digest)
        self.assertEqual(lock['payload_arms'], {arm: record['arms'][arm]['inventory_sha256'] for arm in pa.ARMS})
        self.assertEqual(lock['baseline_revision'], pa.BASELINE_REVISION)
        for entry in lock['cases']:
            case = self.by_id[entry['id']]
            self.assertEqual(entry['split'], 'confirmation')
            self.assertEqual(entry['request_sha256'], pa.text_digest(case['request']))
            self.assertEqual(entry['source_inventory'], conditions.inventory(SET / case['inputs']))
            self.assertEqual(entry['oracle_sha256'], conditions.digest((SET / entry['oracle']).read_bytes()))
            for span, raw in zip(entry['protected_spans'], case['protected_spans']):
                self.assertEqual(span['sha256'], pa.text_digest(raw['text']))
                self.assertEqual(case['sources'][raw['file']][span['offset']:].find(raw['text']), 0)
        body = {k: v for k, v in lock.items() if k != 'freeze_sha256'}
        self.assertEqual(lock['freeze_sha256'], conditions.digest(conditions.encoded(body)))

    def test_schedule_is_six_groups_by_three_arms_by_two_repetitions_with_the_decision_seed(self):
        lock = json.loads((SET / 'freeze.json').read_text())
        schedule = lock['schedule']
        self.assertEqual([cell['slot'] for cell in schedule], list(range(1, 37)))
        self.assertEqual(lock['seed'], 20261017)
        for start in range(0, 36, 6):
            block = schedule[start:start + 6]
            self.assertEqual(len({cell['source_group'] for cell in block}), 1)
            self.assertEqual(sorted((c['condition'], c['repetition']) for c in block),
                             sorted((arm, rep) for arm in pa.ARMS for rep in (1, 2)))
        selected = pa.checked_study(pc.render_manifest())
        self.assertEqual(pa.build_schedule(selected, 20261017, 2), schedule)
        self.assertNotEqual(pa.build_schedule(selected, 20261018, 2), schedule)

    def test_any_changed_input_oracle_request_or_exposure_record_breaks_the_lock(self):
        edits = {
            'source byte': lambda s: (s / 'inputs/pfc-pool-closure/pool-update.md').write_bytes(
                (s / 'inputs/pfc-pool-closure/pool-update.md').read_bytes().replace(b'Thursday', b'Friday')),
            'added source': lambda s: (s / 'inputs/pfc-cfp-checks/extra.md').write_text('more context\n'),
            'oracle label': lambda s: self.edit_json(s / 'oracles/pfc1-absent-cause.json',
                                                     lambda o: o['legitimate_alternatives'].append('anything goes')),
            'request': lambda s: self.edit_json(s / 'cases.json', lambda d: d['cases'][0].update(
                request=d['cases'][0]['request'] + ' Mention the reason.')),
            'exposure record': lambda s: self.edit_json(s / 'exposures.json', lambda d: d.update(rule='none')),
        }
        for name, edit in edits.items():
            with self.subTest(name):
                case_set = self.copy_set()
                edit(case_set)
                with self.assertRaisesRegex(ValueError, 'freeze.json does not match'):
                    pc.verify(case_set)
                shutil.rmtree(case_set)

    def test_refreeze_after_a_change_moves_a_completed_review_into_history(self):
        case_set = self.copy_set()
        lock = self.complete_review(case_set, contested_groups=['pfc1-absent-cause'])
        past = len(json.loads((case_set / 'review.json').read_text())['history'])
        path = case_set / 'inputs/pfc-hold-expiry/branch-notes.md'
        path.write_bytes(path.read_bytes().replace(b'5 to 2', b'6 to 1'))
        new = pc.refreeze(case_set, resolution='vote corrected')
        self.assertNotEqual(new, lock['freeze_sha256'])
        review = json.loads((case_set / 'review.json').read_text())
        self.assertEqual(review['freeze_sha256'], new)
        self.assertEqual(review['second_review']['status'], 'pending')
        self.assertEqual(len(review['history']), past + 1)
        self.assertEqual(review['history'][-1]['resolution'], 'vote corrected')
        self.assertEqual(review['history'][-1]['review']['contested_groups'], ['pfc1-absent-cause'])
        self.assertEqual(review['history'][-1]['review']['freeze_sha256'], lock['freeze_sha256'])
        self.assertIn('second review pending', pc.verify(case_set)['open_gates'])

    def test_review_history_records_the_first_second_review(self):
        history = json.loads((SET / 'review.json').read_text())['history']
        first = history[0]['review']
        self.assertEqual(first['status'], 'complete')
        self.assertEqual(first['reviewer'], 'claude-pr-140-second-reviewer')
        self.assertEqual(first['contested_groups'], ['pfc2-adjacent-config', 'pfc4-conditional-quantity'])
        self.assertTrue(history[0]['resolution'])
        case_set = self.copy_set()
        lock = json.loads((case_set / 'freeze.json').read_text())
        self.edit_json(case_set / 'review.json', lambda r: r['history'][0]['review'].update(
            freeze_sha256=lock['freeze_sha256']))
        with self.assertRaisesRegex(ValueError, 'past review cannot name the current freeze'):
            pc.verify(case_set)


class AdapterTests(Workspace):
    def freeze(self, manifest, name='study'):
        path = self.root / (name + '.json')
        path.write_bytes(conditions.encoded(manifest))
        return pa.freeze_study(path, self.root / name)

    def test_freezes_through_the_prose_adapter_into_exactly_the_locked_study(self):
        result = self.freeze(pc.render_manifest(model='gpt-6.1-sol'))
        self.assertEqual(result['parent_slots'], 36)
        self.assertFalse(result['agent_executed'])
        study = self.root / 'study'
        lock = json.loads((SET / 'freeze.json').read_text())
        self.assertEqual(conditions.digest((study / 'schedule.json').read_bytes()), lock['schedule_sha256'])
        report = pc.check_frozen_study(study)
        self.assertTrue(report['matches_lock'])
        self.assertEqual(report['controls_sha256'], result['controls_sha256'])
        frozen = pa.ProseStudy(study, result['controls_sha256'], pa.LOADED_SOURCES, pa.HERE).verify()
        for case in frozen.controls['cases']:
            self.assertEqual(conditions.inventory(study / 'sources' / case['id']),
                             conditions.inventory(SET / self.by_id[case['id']]['inputs']))

    def test_no_oracle_material_reaches_the_manifest_controls_or_prompt(self):
        manifest = pc.render_manifest()
        text = json.dumps(manifest)
        self.freeze(manifest)
        controls = (self.root / 'study' / 'controls.json').read_text()
        work = self.root / 'work'
        for case in self.cases:
            oracle = oracle_for(case)
            prompt = pa.prose_prompt({'request': case['request']}, work)
            for visible in (text, controls, prompt):
                self.assertNotIn(oracle['canary'], visible)
                self.assertNotIn(oracle['contract'], visible)
                for check in oracle['checks']:
                    self.assertNotIn(check['review_question'], visible)
                for example in oracle['examples']:
                    self.assertNotIn(example['text'], visible)
        for case in manifest['cases']:
            self.assertEqual(set(case), {'id', 'source_group', 'split', 'request', 'sources', 'protected_spans',
                                         'timeout_seconds'})

    def test_a_study_frozen_from_changed_cases_or_seed_is_rejected(self):
        changes = {
            'request': lambda m: m['cases'][2].update(request=m['cases'][2]['request'] + ' Be brief.'),
            'source': lambda m: m['cases'][3]['sources'].update({'pricing-notes.md': 'rides are free\n'}),
            'seed': lambda m: m.update(seed=7),
            'split': lambda m: m['cases'][4].update(split='development'),
        }
        for name, change in changes.items():
            with self.subTest(name):
                manifest = copy.deepcopy(pc.render_manifest())
                change(manifest)
                self.freeze(manifest, 'bad-' + name)
                with self.assertRaisesRegex(ValueError, 'differs from the lock|differ from the lock'):
                    pc.check_frozen_study(self.root / ('bad-' + name))

    def test_manifest_is_refused_while_any_gate_is_open(self):
        out = self.root / 'manifest.json'
        self.assertEqual(pc.main(['--manifest', str(out), '--model', 'gpt-6.1-sol']), 2)
        self.assertFalse(out.exists())


class OracleTests(Workspace):
    def test_every_labeled_example_screens_as_labeled_as_written_and_restyled(self):
        for case in self.cases:
            oracle = pc.checked_oracle(oracle_for(case), case)
            self.assertEqual(pc.grade_examples(oracle, case), [])
            labels = [e['label'] for e in oracle['examples']]
            self.assertGreaterEqual(labels.count('valid'), 2, case['id'])
            self.assertGreaterEqual(labels.count('failing'), 3, case['id'])

    def test_style_never_offsets_an_invented_fact(self):
        for case in self.cases:
            oracle = oracle_for(case)
            polished = [e for e in oracle['examples'] if e['polished'] and e['screen'] == 'screen_fail']
            self.assertTrue(polished, case['id'])
            for example in polished:
                result = pc.screen(oracle, case, example['text'])
                self.assertEqual(result['verdict'], 'screen_fail')
                self.assertFalse(result['style_scored'])
        case = self.by_id['pfc-hold-expiry']
        oracle = oracle_for(case)
        valid = next(e['text'] for e in oracle['examples'] if e['id'] == 'g1-reason-absent-said')
        self.assertEqual(pc.screen(oracle, case, valid)['verdict'], 'screen_pass')
        self.assertEqual(pc.screen(oracle, case, pc.stylize(valid))['verdict'], 'screen_pass')
        invented = valid.replace('instead of 7.', 'instead of 7 to give more patrons a turn.')
        for text in (invented, pc.stylize(invented)):
            result = pc.screen(oracle, case, text)
            self.assertEqual(result['verdict'], 'needs_adjudication')
            self.assertIn('unmapped-clause', result['cues'])

    def test_a_clause_passes_only_when_templates_cover_every_word(self):
        case = self.by_id['pfc-bikeshare-pricing']
        oracle = oracle_for(case)
        valid = next(e['text'] for e in oracle['examples'] if e['id'] == 'g1-plain')
        self.assertEqual(pc.screen(oracle, case, valid)['verdict'], 'screen_pass')
        swaps = {
            'riders swapped': valid.replace('Annual members ride', 'Casual riders ride'),
            'added rider group': valid.replace('for everyone,', 'for everyone except students,'),
            'causal join': valid.replace("; it may change", ", so it may change"),
            'unlock narrowed': valid.replace('unlock any bike', 'unlock a classic bike'),
        }
        for name, text in swaps.items():
            with self.subTest(name):
                self.assertNotEqual(text, valid)
                self.assertNotEqual(pc.screen(oracle, case, text)['verdict'], 'screen_pass')
        self.assertTrue(pc.mapped('annual members ride classic bikes free for the first 30 minutes',
                                  re.compile('|'.join(t for s in oracle['statements'] for t in s['templates']))))

    def test_no_labeled_failing_output_ever_passes_and_no_valid_one_ever_fails(self):
        probes = 0
        for case in self.cases:
            oracle = oracle_for(case)
            for example in oracle['examples']:
                probes += example['id'].startswith('r1-')
                for text in (example['text'], pc.stylize(example['text'], case['protected_spans'])):
                    verdict = pc.screen(oracle, case, text)['verdict']
                    if example['label'] == 'failing':
                        self.assertNotEqual(verdict, 'screen_pass', example['id'])
                    else:
                        self.assertNotEqual(verdict, 'screen_fail', example['id'])
        self.assertEqual(probes, 44)

    def test_quoting_a_directive_name_never_stands_in_for_explaining_it(self):
        case = self.by_id['pfc-kiosk-logrotate']
        oracle = oracle_for(case)
        names = next(e['text'] for e in oracle['examples'] if e['id'] == 'b8-names-only')
        result = pc.screen(oracle, case, names)
        self.assertEqual(result['verdict'], 'needs_adjudication')
        self.assertTrue({'weekly', 'compress', 'delaycompress', 'missingok', 'rotate-8-kept'} <= set(result['unconfirmed']))

    def test_protected_spans_are_conclusive_and_excluded_from_prose_checks(self):
        case = self.by_id['pfc-kiosk-logrotate']
        oracle = oracle_for(case)
        block = case['protected_spans'][0]['text']
        bare = pc.screen(oracle, case, block)
        self.assertTrue(bare['exact_spans']['logrotate-block'])
        self.assertEqual(bare['failures'], [])
        self.assertEqual(bare['verdict'], 'needs_adjudication')
        self.assertTrue({'weekly', 'ask-imran', 'path-scope'} <= set(bare['unconfirmed']))
        case = self.by_id['pfc-dome-autoclose']
        oracle = oracle_for(case)
        valid = next(e['text'] for e in oracle['examples'] if e['id'] == 'g1-plain')
        self.assertEqual(pc.screen(oracle, case, valid)['verdict'], 'screen_pass')
        altered = valid.replace('wind_gust_kmh = 45', 'wind_gust_kmh = 50')
        self.assertIn('protected-span-lost', pc.screen(oracle, case, altered)['failures'])

    def test_oracle_contract_requirements_are_enforced(self):
        case = self.by_id['pfc-cfp-checks']
        base = oracle_for(case)
        broken = {
            'no failure opportunity': lambda o: o.update(checks=[c for c in o['checks'] if c['kind'] == 'preserve']),
            'one legitimate alternative': lambda o: o.update(examples=[
                e for e in o['examples'] if e['label'] == 'failing' or e['id'] == 'g1-including']),
            'no polished failure': lambda o: [e.update(polished=False) for e in o['examples']],
            'valid example screened as failure': lambda o: o['examples'][0].update(screen='screen_fail'),
            'failing example screened as pass': lambda o: next(
                e for e in o['examples'] if e['label'] == 'failing').update(screen='screen_pass'),
            'no statement templates': lambda o: o.update(statements=[]),
            'wildcard template': lambda o: o['statements'][0]['templates'].append('why did the form .*'),
            'gap template': lambda o: o['statements'][0]['templates'].append(r'the form \w+ my proposal'),
            'not evaluator only': lambda o: o.update(evaluator_only=False),
            'wrong group kind': lambda o: o.update(group_kind='anything'),
            'extra field': lambda o: o.update(expected_rewrite='x'),
        }
        for name, change in broken.items():
            with self.subTest(name):
                oracle = copy.deepcopy(base)
                change(oracle)
                with self.assertRaises(ValueError):
                    pc.checked_oracle(oracle, case)


class IndependenceTests(Workspace):
    def test_inputs_share_no_eight_word_run_with_development_material(self):
        self.assertEqual(pc.development_overlap(self.cases), {})
        corpus_files = [p for pattern in pc.DEVELOPMENT_CORPORA for p in pc.ROOT.glob(pattern) if p.is_file()]
        self.assertGreaterEqual(len(corpus_files), 15)

    def test_reused_development_text_is_caught(self):
        reused = copy.deepcopy(self.by_id['pfc-cfp-checks'])
        prompt = (pc.ROOT / 'evals/04-pr-description/prompt.md').read_text().split('---\n')[-1]
        reused['sources'] = {'notes.md': 'Draft notes.\n\n' + prompt.split('\n\n')[1]}
        hits = pc.development_overlap([reused])
        self.assertIn('pfc-cfp-checks:notes.md', hits)
        self.assertEqual(hits['pfc-cfp-checks:notes.md'][0]['development_file'], 'evals/04-pr-description/prompt.md')
        planted = self.root / 'repo'
        (planted / 'evals/workflows/heldout/inputs').mkdir(parents=True)
        (planted / 'evals/workflows/heldout/inputs/new.md').write_text(
            self.by_id['pfc-pool-closure']['sources']['pool-update.md'])
        self.assertIn('pfc-pool-closure:pool-update.md', pc.development_overlap(self.cases, planted))

    def test_canary_in_candidate_text_is_caught(self):
        case = copy.deepcopy(self.by_id['pfc-hold-expiry'])
        oracle = oracle_for(case)
        case['sources']['branch-notes.md'] += oracle['canary']
        self.assertEqual(pc.leaked_canaries(SET, [case], {case['id']: oracle}), [case['id']])


class GateTests(Workspace):
    def test_an_exposed_group_must_leave_confirmation_and_be_replaced(self):
        case_set = self.copy_set()
        exposure = {'group': 'pfc4-conditional-quantity', 'reader': 'candidate tuner', 'date': '2026-10-18',
                    'reason': 'read the oracle while editing the candidate'}
        self.edit_json(case_set / 'exposures.json', lambda d: d['exposures'].append(exposure))
        with self.assertRaisesRegex(ValueError, 'move to the development split'):
            pc.refreeze(case_set)
            pc.verify(case_set)
        self.edit_json(case_set / 'cases.json', lambda d: d['cases'][3].update(split='development'))
        pc.refreeze(case_set)
        report = pc.verify(case_set)
        self.assertEqual(report['exposed_groups'], ['pfc4-conditional-quantity'])
        self.assertFalse(report['confirmation_ready'])
        self.assertTrue(any('conditional-quantity' in gate for gate in report['open_gates']))

    def test_second_review_must_be_a_different_reviewer_on_this_exact_freeze(self):
        case_set = self.copy_set()
        lock = json.loads((case_set / 'freeze.json').read_text())
        attempts = {
            'by the author': dict(status='complete', reviewer='claude-issue-115-case-author', date='2026-10-18',
                                  freeze_sha256=lock['freeze_sha256']),
            'another freeze': dict(status='complete', reviewer='second-reviewer', date='2026-10-18',
                                   freeze_sha256='0' * 64),
            'pending with a reviewer': dict(status='pending', reviewer='second-reviewer'),
        }
        for name, fields in attempts.items():
            with self.subTest(name):
                self.edit_json(case_set / 'review.json', lambda r: r.update(second_review={
                    'status': 'pending', 'reviewer': None, 'date': None, 'freeze_sha256': None,
                    'contested_groups': [], 'notes': None, **fields}))
                with self.assertRaises(ValueError):
                    pc.verify(case_set)
        self.complete_review(case_set, contested_groups=['pfc2-adjacent-config'])
        self.assertEqual(pc.verify(case_set)['open_gates'], ['replace contested groups: pfc2-adjacent-config'])

    def test_contested_groups_must_name_real_groups(self):
        case_set = self.copy_set()
        for contested in (['pfc9-imaginary'], ['pfc-dome-autoclose'], ['pfc2-adjacent-config', 'adjacent-code-config']):
            with self.subTest(contested):
                self.complete_review(case_set, contested_groups=contested)
                with self.assertRaisesRegex(ValueError, 'contests a group that does not exist'):
                    pc.verify(case_set)
        self.edit_json(case_set / 'review.json', lambda r: r['history'][0]['review'].update(
            contested_groups=['pfc7-gone']))
        self.set_review(case_set)
        with self.assertRaisesRegex(ValueError, 'contests a group that does not exist'):
            pc.verify(case_set)


if __name__ == '__main__':
    unittest.main()
