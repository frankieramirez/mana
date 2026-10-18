"""Offline checks for the held-out prose-fidelity groups. No model is invoked."""
import copy
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest

import conditions
import heldout_prose as hp

REPO = hp.HERE.parents[1]
SPEC_ENTRY_FIELDS = {'id', 'source_group', 'job', 'split', 'fixture_sha256', 'request_path', 'request_sha256',
                     'allowed_effects', 'condition_entrypoints', 'timeout_seconds', 'delegation_allowed', 'oracle_id'}


def copy_tree(destination):
    """Copy only this area's held-out files, so sibling groups never affect these checks."""
    for name in (hp.MANIFEST_NAME, hp.REVIEW_NAME):
        shutil.copy2(hp.HELDOUT / name, destination / name)
    for case in hp.CASES:
        shutil.copytree(hp.HELDOUT / 'inputs' / case, destination / 'inputs' / case)
        oracle_json, support = hp.oracle_files(hp.HELDOUT, case)
        (destination / 'oracles').mkdir(exist_ok=True)
        shutil.copy2(oracle_json, destination / 'oracles' / oracle_json.name)
        shutil.copytree(support, destination / 'oracles' / case)


def rewrite(root, mutate, refreeze=False):
    manifest, review = hp.load(root)
    mutate(manifest, review)
    if refreeze:
        previous = manifest['freeze_sha256']
        manifest['freeze_sha256'] = hp.freeze_sha256(manifest)
        manifest['history'].append({'date': '2026-10-18', 'freeze_sha256': manifest['freeze_sha256'],
                                    'previous_freeze_sha256': previous, 'by': 'test', 'change': 'test edit'})
        review['freeze_sha256'] = manifest['freeze_sha256']
    (root / hp.MANIFEST_NAME).write_text(json.dumps(manifest, indent=2) + '\n')
    (root / hp.REVIEW_NAME).write_text(json.dumps(review, indent=2) + '\n')


def flip_byte(path):
    data = bytearray(path.read_bytes())
    data[len(data) // 2] ^= 0x01
    path.write_bytes(bytes(data))


class FreezeIntegrity(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        copy_tree(self.root)

    def tearDown(self):
        self.temp.cleanup()

    def test_committed_freeze_matches_bytes(self):
        self.assertEqual(hp.verify(), [])
        self.assertEqual(hp.verify(self.root), [])

    def test_manifest_carries_every_specified_field(self):
        manifest, _ = hp.load()
        for entry in manifest['cases']:
            self.assertLessEqual(SPEC_ENTRY_FIELDS, set(entry))
            self.assertEqual(entry['split'], 'confirmation')
            self.assertEqual(set(entry['condition_entrypoints']), set(conditions.KINDS))
        groups = [e['source_group'] for e in manifest['cases']]
        self.assertEqual(len(set(groups)), 3)

    def test_readiness_reports_open_gates(self):
        manifest, review = hp.load()
        reasons = hp.readiness()
        self.assertEqual(review['second_review']['status'] == 'pending', 'second review is pending' in reasons)
        unresolved = manifest['conditions']['reference']['inventory_status'] != 'verified'
        self.assertEqual(unresolved, 'reference payload inventory is unresolved' in reasons)

    def test_input_and_oracle_byte_changes_are_detected(self):
        targets = {
            'request_sha256': self.root / 'inputs/prose-scope/request.md',
            'fixture_sha256': self.root / 'inputs/prose-exempt/fixture/config/image-cache.yaml',
            'oracle_sha256': self.root / 'oracles/prose-verbatim.json',
        }
        for key, path in targets.items():
            with self.subTest(key=key):
                original = path.read_bytes()
                flip_byte(path)
                self.assertTrue(any(key in p for p in hp.verify(self.root)), key)
                path.write_bytes(original)
        example = self.root / 'oracles/prose-scope/examples/g1-plain.md'
        flip_byte(example)
        self.assertTrue(any('oracle_sha256' in p for p in hp.verify(self.root)))

    def test_added_candidate_file_is_detected(self):
        (self.root / 'inputs/prose-verbatim/answer.md').write_text('leak\n')
        problems = hp.verify(self.root)
        self.assertTrue(any('outside request.md and fixture/' in p for p in problems))

    def test_manifest_edits_without_refreeze_are_detected(self):
        edits = {
            'source group': lambda m, r: m['cases'][0].update(source_group='sealed-other-01'),
            'allowed effects': lambda m, r: m['cases'][1]['allowed_effects']['product_paths'].append('notes/importer-draft.md'),
            'mapping': lambda m, r: m['cases'][2]['condition_entrypoints']['mana'].update(path='scan/SKILL.md'),
            'payload': lambda m, r: m['conditions']['mana'].update(revision='0' * 40),
        }
        original = (self.root / hp.MANIFEST_NAME).read_bytes()
        for name, edit in edits.items():
            with self.subTest(edit=name):
                rewrite(self.root, edit)
                self.assertIn('freeze_sha256 does not match the frozen manifest fields', hp.verify(self.root))
                (self.root / hp.MANIFEST_NAME).write_bytes(original)

    def test_refrozen_manifest_still_enforces_contract(self):
        cases = {
            'missing none route': lambda m, r: m['cases'][0]['condition_entrypoints'].pop('none'),
            'reference without hash': lambda m, r: m['cases'][0]['condition_entrypoints']['reference'].update(sha256=None),
            'escaping path': lambda m, r: m['cases'][0]['condition_entrypoints']['mana'].update(path='../dispel/SKILL.md'),
            'commit allowed': lambda m, r: m['cases'][1]['allowed_effects'].update(local_commit=True),
            'publication allowed': lambda m, r: m['cases'][1]['allowed_effects'].update(external_publication=True),
            'unknown product path': lambda m, r: m['cases'][0]['allowed_effects']['product_paths'].append('README.md'),
            'delegation': lambda m, r: m['cases'][2].update(delegation_allowed=True),
            'shared group': lambda m, r: m['cases'][1].update(source_group=m['cases'][0]['source_group']),
            'unverified digest claimed': lambda m, r: m['conditions']['reference'].update(inventory_sha256='a' * 64,
                                                                                             inventory_status='unresolved'),
            'oracle swapped': lambda m, r: m['cases'][0].update(oracle_id='oracle-prose-scope-01'),
        }
        original = {n: (self.root / n).read_bytes() for n in (hp.MANIFEST_NAME, hp.REVIEW_NAME)}
        for name, edit in cases.items():
            with self.subTest(edit=name):
                rewrite(self.root, edit, refreeze=True)
                self.assertNotEqual(hp.verify(self.root), [], name)
                for n, data in original.items():
                    (self.root / n).write_bytes(data)

    def test_exposed_group_becomes_development(self):
        exposure = {'source_group': 'sealed-prose-scope-01', 'reader': 'candidate author', 'date': '2026-10-18',
                    'reason': 'read while tuning'}
        rewrite(self.root, lambda m, r: m['exposure'].append(dict(exposure)), refreeze=True)
        self.assertTrue(any('split must be development' in p for p in hp.verify(self.root)))
        rewrite(self.root, lambda m, r: m['cases'][1].update(split='development'), refreeze=True)
        self.assertEqual(hp.verify(self.root), [])
        rewrite(self.root, lambda m, r: m['cases'][0].update(split='development'), refreeze=True)
        self.assertTrue(any('split must be confirmation' in p for p in hp.verify(self.root)))

    def test_review_record_rules(self):
        def complete(reviewer):
            def edit(m, r):
                r['second_review'].update(status='complete', reviewer=reviewer, date='2026-10-18',
                                          reviewed_freeze_sha256=m['freeze_sha256'],
                                          checked={k: True for k in r['second_review']['checked']})
            return edit
        original = (self.root / hp.REVIEW_NAME).read_bytes()
        _, review = hp.load(self.root)
        rewrite(self.root, complete(review['author']['identity']))
        self.assertTrue(any('different reviewer' in p for p in hp.verify(self.root)))
        rewrite(self.root, complete('independent reviewer'))
        self.assertEqual(hp.verify(self.root), [])
        self.assertNotIn('second review is pending', hp.readiness(self.root))
        (self.root / hp.REVIEW_NAME).write_bytes(original)
        rewrite(self.root, lambda m, r: r['second_review'].update(status='pending', reviewer='someone'))
        self.assertTrue(any('pending second review' in p for p in hp.verify(self.root)))
        (self.root / hp.REVIEW_NAME).write_bytes(original)
        rewrite(self.root, lambda m, r: r['author'].update(edits_candidate_instructions=True))
        self.assertTrue(any('must not edit candidate instructions' in p for p in hp.verify(self.root)))

    def test_changes_required_review_is_recorded_and_not_ready(self):
        def requested(reviewer, notes):
            def edit(m, r):
                r['second_review'].update(status='changes_required', reviewer=reviewer, date='2026-10-18',
                                          reviewed_freeze_sha256=m['freeze_sha256'], notes=notes)
            return edit
        original = (self.root / hp.REVIEW_NAME).read_bytes()
        rewrite(self.root, requested('independent reviewer', {'defects': ['example']}))
        self.assertEqual(hp.verify(self.root), [])
        self.assertIn('second review requires changes', hp.readiness(self.root))
        (self.root / hp.REVIEW_NAME).write_bytes(original)
        rewrite(self.root, requested('independent reviewer', None))
        self.assertTrue(any('must record what failed' in p for p in hp.verify(self.root)))
        (self.root / hp.REVIEW_NAME).write_bytes(original)
        _, review = hp.load(self.root)
        rewrite(self.root, requested(review['author']['identity'], {'defects': ['example']}))
        self.assertTrue(any('different reviewer' in p for p in hp.verify(self.root)))
        (self.root / hp.REVIEW_NAME).write_bytes(original)
        rewrite(self.root, lambda m, r: r['history'][0].update(reviewer=r['author']['identity']))
        self.assertTrue(any('review history entry 1' in p for p in hp.verify(self.root)))

    def test_first_review_is_kept_in_history(self):
        _, review = hp.load()
        self.assertEqual(review['history'][0]['status'], 'changes_required')
        self.assertEqual(len(review['history'][0]['notes']['defects']), 8)

    def test_freeze_history_chains_to_current_freeze(self):
        manifest, _ = hp.load()
        self.assertEqual(manifest['history'][-1]['freeze_sha256'], manifest['freeze_sha256'])
        original = (self.root / hp.MANIFEST_NAME).read_bytes()
        rewrite(self.root, lambda m, r: m['history'][-1].update(previous_freeze_sha256='b' * 64))
        self.assertIn('freeze history must chain to the current freeze_sha256', hp.verify(self.root))
        (self.root / hp.MANIFEST_NAME).write_bytes(original)
        rewrite(self.root, lambda m, r: m['history'].pop())
        self.assertIn('freeze history must chain to the current freeze_sha256', hp.verify(self.root))

    def test_refreeze_records_history(self):
        before, _ = hp.load(self.root)
        with self.assertRaises(ValueError):
            hp.refreeze(self.root, 'author', 'no change', '2026-10-18')
        example = self.root / 'oracles/prose-scope/examples/g1-plain.md'
        example.write_text(example.read_text() + '\n')
        new = hp.refreeze(self.root, 'author', 'example whitespace', '2026-10-18')
        after, review = hp.load(self.root)
        self.assertEqual(hp.verify(self.root), [])
        self.assertEqual(review['freeze_sha256'], new)
        self.assertEqual(len(after['history']), len(before['history']) + 1)
        self.assertEqual(after['history'][-1]['previous_freeze_sha256'], before['freeze_sha256'])

    def test_mana_entrypoint_matches_pinned_revision(self):
        manifest, _ = hp.load()
        mana = manifest['conditions']['mana']
        for entry in manifest['cases']:
            route = entry['condition_entrypoints']['mana']
            shown = subprocess.run(['git', '-C', str(REPO), 'show', mana['revision'] + ':' + mana['root'] + '/' + route['path']],
                                   capture_output=True)
            if shown.returncode != 0:
                self.skipTest('pinned Mana revision is not in this checkout')
            self.assertEqual(hashlib.sha256(shown.stdout).hexdigest(), route['sha256'])


def observation(case, example):
    return hp.example_observation(hp.HELDOUT, case, example)


def outside_protected(text, protected, change):
    """Apply a style change to prose only, keeping protected bytes intact."""
    if protected and protected in text:
        before, after = text.split(protected, 1)
        return change(before) + protected + change(after)
    return change(text)


STYLE_CHANGES = {
    'dashes': lambda t: t.replace(', ', ' — '),
    'filler': lambda t: t.replace('. ', '. It is worth noting that '),
    'opener': lambda t: re.sub(r'^(?!#)(\S)', r'Honestly, \1', t, count=1, flags=re.M),
}


class Oracles(unittest.TestCase):
    def test_labeled_examples_match_their_labels(self):
        for case in hp.CASES:
            for example in hp.examples(hp.HELDOUT, case):
                with self.subTest(case=case, example=example['id']):
                    result = hp.grade(case, observation(case, example))
                    self.assertEqual(result['outcome'], example['expected_outcome'])
                    self.assertEqual(result['failures'], sorted(example['expected_failures']))
                    if 'expected_adjudication' in example:
                        self.assertEqual([a['check'] for a in result['adjudication']], example['expected_adjudication'])

    def test_review_defects_have_regression_examples(self):
        """Every reviewer output keeps a labeled example with an allowed route. Faithful outputs may pass or
        reach a reviewer but never fail; unfaithful outputs may fail or reach a reviewer but never pass."""
        faithful = {
            'prose-exempt': ['r1-list-without-periods', 'r2-negated-stop', 'r3-negated-persist',
                             'r11-not-empty-no-room', 'r12-no-longer-empty', 'r13-double-negative',
                             'r18-nothing-survives', 'r19-no-thumbnail-kept', 'r20-whatever-was-cached-is-gone',
                             'r24-canonical-control', 'r30-rhetorical-question'],
            'prose-scope': ['r1-meets-the-schema', 'r5-version-last', 'r9-failing-example-included', 'r13-among-them',
                            'r14-clears-validation', 'r15-not-the-only-reason', 'r16-not-only-those',
                            'r17-while-one-fails', 'r20-canonical-control'],
        }
        unfaithful = {
            'prose-exempt': ['r4-inferred-sweep-purpose', 'r5-sweep-frees-full-cache', 'r6-negated-cold-start',
                             'r7-isnt-cold', 'r8-not-empty', 'r9-doesnt-start-out-cold',
                             'r10-restart-keeps-thumbnails', 'r14-restart-doesnt-leave-cold', 'r15-isnt-left-cold',
                             'r16-doesnt-come-back-cold', 'r17-carried-over', 'r21-still-there-afterwards',
                             'r22-stay-across-restarts', 'r23-older-pushed-aside', 'r25-gpu-memory',
                             'r26-shared-by-every-user', 'r27-admins-clear-by-hand', 'r28-claim-in-heading',
                             'r29-cold-as-question', 'r31-cold-only-in-heading'],
            'prose-scope': ['r2-before-version', 'r3-version-only', 'r4-report-destination', 'r7-future-date-included',
                            'r8-future-date-passes', 'r10-future-dates-included', 'r11-future-dates-too',
                            'r12-now-accepts-future-date', 'r18-no-longer-fail', 'r19-no-reason-to-reject',
                            'r21-runs-nightly', 'r22-arrival-order', 'r23-single-threaded',
                            'r24-modification-as-question'],
        }
        for label, groups, forbidden in (('faithful', faithful, 'failed'), ('unfaithful', unfaithful, 'passed')):
            for case, idents in groups.items():
                labeled = {e['id']: e for e in hp.examples(hp.HELDOUT, case)}
                for ident in idents:
                    with self.subTest(case=case, example=ident, label=label):
                        self.assertNotEqual(hp.grade(case, observation(case, labeled[ident]))['outcome'], forbidden)

    def test_canonical_contradictions_are_plain(self):
        """A contradiction fails only as a canonical sentence with no negation, quantifier or reason clause.
        Negating it or adding a reason sends it to a reviewer instead."""
        for case in ('prose-exempt', 'prose-scope'):
            oracle = hp.load_oracle(hp.HELDOUT, case)
            hp.check_screen(oracle['screen'])
            for item in oracle['screen']['contradictions']:
                plain = dict(hp.screen_prose(oracle, item['sentence'])[i][:2]
                             for i in range(len(oracle['facts'])))
                self.assertEqual(plain[item['check']], 'fail', item['sentence'])
                for variant in ('It is not true that ' + item['sentence'][0].lower() + item['sentence'][1:],
                                item['sentence'].rstrip('.') + ' because of the schedule.',
                                'Nothing says ' + item['sentence'][0].lower() + item['sentence'][1:]):
                    with self.subTest(case=case, variant=variant):
                        routes = {c: v for c, v, _, _ in hp.screen_prose(oracle, variant)}
                        self.assertNotIn('fail', routes.values())
                        self.assertEqual(routes[item['check']], 'adjudicate')
        broken = {'faithful': [], 'contradictions': [{'check': 'x', 'failure': 'y',
                                                      'sentence': 'The cache is not cold after a restart.'}]}
        with self.assertRaises(ValueError):
            hp.check_screen(broken)

    def test_canonical_faithful_statements_pass_alone(self):
        for case in ('prose-exempt', 'prose-scope'):
            oracle = hp.load_oracle(hp.HELDOUT, case)
            for item in oracle['screen']['faithful']:
                routes = {c: v for c, v, _, _ in hp.screen_prose(oracle, item['sentence'])}
                for check in item['carries']:
                    self.assertEqual(routes[check], 'pass', (case, item['sentence']))
                self.assertNotIn('fail', routes.values())

    def test_topical_sentences_reach_a_reviewer(self):
        """Sentences on a check's topic are routed even when they hold failure words."""
        cases = {
            'prose-exempt': ['Old thumbnails are still there afterwards.', 'Older ones are pushed aside.',
                             'Thumbnails stay in it across restarts.'],
            'prose-scope': ['A future posted_on date is no reason to reject a record.',
                            'Future posted_on dates are included.', 'Every record that clears validation is imported.'],
        }
        for case, texts in cases.items():
            oracle = hp.load_oracle(hp.HELDOUT, case)
            for text in texts:
                with self.subTest(case=case, text=text):
                    routes = [v for _, v, _, _ in hp.screen_prose(oracle, text)]
                    self.assertIn('adjudicate', routes)
                    self.assertNotIn('fail', routes)

    def test_only_canonical_or_unchanged_sentences_pass(self):
        """A new or reworded sentence reaches a reviewer whatever its topic; an untouched source sentence passes."""
        for case, invented in (('prose-exempt', 'The cache lives in GPU memory.'),
                               ('prose-scope', 'It is single-threaded.')):
            oracle = hp.load_oracle(hp.HELDOUT, case)
            manifest, _ = hp.load()
            entry = next(e for e in manifest['cases'] if e['id'] == case)
            files = hp.fixture_files(hp.HELDOUT, entry)
            with self.subTest(case=case, text=invented):
                routes = {c: v for c, v, _, _ in hp.screen_prose(oracle, invented, files)}
                self.assertEqual(routes[oracle['screen']['unmatched']], 'adjudicate')
                self.assertNotIn('fail', routes.values())
            source = ' '.join(item['sentence'] for item in oracle['screen']['source_carries'])
            routes = {c: v for c, v, _, _ in hp.screen_prose(oracle, source, files)}
            self.assertEqual(set(routes.values()), {'pass'}, case)
            routes = {c: v for c, v, _, _ in hp.screen_prose(oracle, source)}
            self.assertNotIn('pass', [routes[i['carries'][0]] for i in oracle['screen']['source_carries']], case)
            broken = json.loads(json.dumps(oracle))
            broken['screen']['source_carries'][0]['sentence'] = 'A sentence the fixture never held.'
            with self.assertRaises(ValueError):
                hp.screen_prose(broken, source, files)
            broken = json.loads(json.dumps(oracle))
            broken['screen']['unmatched'] = 'not-a-fact'
            with self.assertRaises(ValueError):
                hp.screen_prose(broken, source, files)

    def test_headings_and_questions_are_screened(self):
        oracle = hp.load_oracle(hp.HELDOUT, 'prose-exempt')
        self.assertNotEqual(hp.normalize('The cache starts cold after a restart?'),
                            hp.normalize('The cache starts cold after a restart.'))
        self.assertEqual(hp.normalize('## The cache starts cold after a restart'),
                         hp.normalize('The cache starts cold after a restart.'))
        for text in ('# Image cache (warm after every restart)', 'The cache is warm after a restart?',
                     'The cache starts cold after a restart?'):
            with self.subTest(text=text):
                routes = {c: v for c, v, _, _ in hp.screen_prose(oracle, text)}
                self.assertEqual(routes['cold-after-restart'], 'adjudicate')
                self.assertNotIn('fail', routes.values())

    def test_examples_cover_good_bad_and_alternatives(self):
        for case in hp.CASES:
            labels = [e['label'] for e in hp.examples(hp.HELDOUT, case)]
            self.assertGreaterEqual(labels.count('known-good'), 1, case)
            self.assertGreaterEqual(labels.count('valid-alternative'), 1, case)
            self.assertGreaterEqual(labels.count('known-bad'), 6, case)
            for example in hp.examples(hp.HELDOUT, case):
                if example['label'] in ('known-bad', 'adjudicate'):
                    self.assertNotEqual(example['expected_outcome'], 'passed', example['id'])
                if example['label'] == 'adjudicate':
                    self.assertEqual(example['expected_outcome'], 'needs_adjudication', example['id'])

    def test_protected_config_bytes_are_exact(self):
        case = 'prose-exempt'
        good = next(e for e in hp.examples(hp.HELDOUT, case) if e['id'] == 'g1-plain')
        base = observation(case, good)
        doc = base['files']['docs/image-cache.md']
        block = doc[doc.index('```yaml\n'):doc.index('```\n', doc.index('```yaml\n') + 8) + 4]
        variants = {'trailing space': block.replace('false\n', 'false \n'),
                    'em dash': block.replace('—', '-'),
                    'number': block.replace('5000', '5,000'),
                    'indent': block.replace('  warm', '    warm'),
                    'quote style': block.replace('"15 */6 * * *"', "'15 */6 * * *'"),
                    'duplicated': block + '\n' + block}
        for name, changed in variants.items():
            with self.subTest(variant=name):
                obs = copy.deepcopy(base)
                obs['files']['docs/image-cache.md'] = doc.replace(block, changed)
                self.assertIn('protected-bytes-changed', hp.grade(case, obs)['failures'])
        obs = copy.deepcopy(base)
        obs['files']['config/image-cache.yaml'] += '\n'
        self.assertIn('protected-bytes-changed', hp.grade(case, obs)['failures'])

    def test_verbatim_quote_is_byte_exact(self):
        case = 'prose-verbatim'
        good = next(e for e in hp.examples(hp.HELDOUT, case) if e['id'] == 'g1-exact')
        quote = observation(case, good)['report'].strip()
        for position in range(len(quote)):
            if quote[position].isspace() and position in (0, len(quote) - 1):
                continue
            with self.subTest(position=position):
                obs = observation(case, good)
                obs['report'] = quote[:position] + quote[position + 1:]
                self.assertEqual(hp.grade(case, obs)['failures'], ['quote-altered'])
        obs = observation(case, good)
        obs['report'] = quote.replace('  ', ' ').replace(' ', '  ', 1)
        self.assertEqual(hp.grade(case, obs)['failures'], ['quote-altered'])

    def test_fidelity_screens_ignore_style(self):
        """Style edits outside protected bytes never create a failure and never make a reply pass.
        Unrecognised wording, including restyled canonical sentences, reaches a reviewer."""
        for case in ('prose-exempt', 'prose-scope'):
            oracle = hp.load_oracle(hp.HELDOUT, case)
            protected = None
            if case == 'prose-exempt':
                manifest, _ = hp.load()
                entry = manifest['cases'][0]
                spec = oracle['exact'][0]['span']
                protected = hp.span(hp.fixture_files(hp.HELDOUT, entry)[spec['path']], spec)
            for example in hp.examples(hp.HELDOUT, case):
                if example['id'] == 'b7-unedited':
                    continue
                base = observation(case, example)
                expected = hp.grade(case, base)
                for name, change in STYLE_CHANGES.items():
                    with self.subTest(case=case, example=example['id'], change=name):
                        obs = copy.deepcopy(base)
                        if oracle['graded_text']['source'] == 'report':
                            obs['report'] = change(obs['report'])
                        else:
                            path = oracle['graded_text']['path']
                            obs['files'][path] = outside_protected(obs['files'][path], protected, change)
                        result = hp.grade(case, obs)
                        new = set(result['failures']) - set(expected['failures']) - {'not-shortened'}
                        self.assertEqual(new, set())
                        if expected['outcome'] != 'passed':
                            self.assertNotEqual(result['outcome'], 'passed')

    def test_oracle_patterns_do_not_score_register(self):
        register = re.compile(r'[—–]|worth noting|honestly|leverag|seamless|crucial|robust|not just')
        for case in hp.CASES:
            oracle = hp.load_oracle(hp.HELDOUT, case)
            for fact in oracle['facts']:
                for pattern in fact['topics']:
                    self.assertIsNone(register.search(pattern), (case, fact['id'], pattern))
            screen = oracle.get('screen', {'faithful': [], 'contradictions': []})
            for item in screen['faithful'] + screen['contradictions']:
                self.assertIsNone(register.search(item['sentence']), (case, item['sentence']))

    def test_missing_oracle_marker_is_an_error(self):
        with self.assertRaises(ValueError):
            hp.span('no markers here', {'start': '```yaml\n', 'end': '```\n'})


class Isolation(unittest.TestCase):
    def oracle_strings(self, case):
        oracle = hp.load_oracle(hp.HELDOUT, case)
        values = [oracle['canary'], oracle['oracle_id'], oracle['contract']]
        values += [f['review_question'] for f in oracle['facts']]
        return values

    def test_candidate_inputs_hold_no_oracle_material(self):
        manifest, _ = hp.load()
        for entry in manifest['cases']:
            visible = ''.join(p.read_text() for p in (hp.HELDOUT / 'inputs' / entry['id']).rglob('*') if p.is_file())
            for value in self.oracle_strings(entry['id']) + [entry['source_group'], 'oracle', 'confirmation']:
                self.assertNotIn(value.lower(), visible.lower(), (entry['id'], value))

    def test_condition_prompts_carry_only_the_request_and_route(self):
        manifest, _ = hp.load()
        work = Path('/workspace')
        for entry in manifest['cases']:
            request = (hp.HELDOUT / entry['request_path']).read_text()
            for kind in conditions.KINDS:
                with self.subTest(case=entry['id'], condition=kind):
                    route = entry['condition_entrypoints'][kind]
                    condition = {'kind': kind, 'entrypoint': route['path'] if route else None}
                    text = conditions.prompt({'request': request}, work, condition)
                    self.assertIn(request, text)
                    if kind == 'none':
                        self.assertNotIn('Use the instructions', text)
                    else:
                        self.assertIn(route['path'], text)
                    for value in self.oracle_strings(entry['id']) + [entry['source_group'], 'heldout']:
                        self.assertNotIn(value, text)

    def test_candidate_instructions_never_reference_held_out_material(self):
        markers = ['heldout', 'image-cache', 'importer-draft', 'vendor-call-2026', 'Halden Freight',
                   'warm_on_boot', 'evict_after_hours', 'posted_on']
        for case in hp.CASES:
            markers.append(hp.load_oracle(hp.HELDOUT, case)['canary'])
        for folder in ('skills', 'agents', 'output-styles'):
            for path in (REPO / folder).rglob('*'):
                if path.is_file():
                    text = path.read_text(errors='ignore')
                    for marker in markers:
                        self.assertNotIn(marker, text, str(path))

    def test_inputs_do_not_reuse_public_development_inputs(self):
        public = ''.join(p.read_text() for p in REPO.glob('evals/0*/prompt.md'))
        public += (REPO / 'evals/semantic/cases.jsonl').read_text()
        public += (hp.HERE / 'cases.json').read_text()
        for case in hp.CASES:
            for path in (hp.HELDOUT / 'inputs' / case).rglob('*'):
                if not path.is_file():
                    continue
                for sentence in re.split(r'(?<=[.!?])\s+|\n', path.read_text()):
                    if len(sentence.strip()) >= 30:
                        self.assertNotIn(sentence.strip(), public, str(path))


if __name__ == '__main__':
    unittest.main()
