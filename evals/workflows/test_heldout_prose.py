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


def reset_review(root):
    """Put the copied review slot back to pending, so a recorded review of the committed freeze cannot
    block a test that refreezes the copy."""
    def pending(manifest, review):
        review['second_review'] = {'status': 'pending', 'reviewer': None, 'reviewed_freeze_sha256': None,
                                   'date': None, 'checked': {k: None for k in sorted(hp.REVIEW_CHECKS)},
                                   'notes': None}
    rewrite(root, pending)


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
        reset_review(self.root)
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
        reset_review(self.root)
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
    def test_labeled_examples_match_their_expected_grades(self):
        for case in hp.CASES:
            for example in hp.examples(hp.HELDOUT, case):
                with self.subTest(case=case, example=example['id']):
                    result = hp.grade(case, observation(case, example))
                    self.assertEqual(result['outcome'], example['expected_outcome'])
                    self.assertEqual(result['failures'], sorted(example['expected_failures']))

    def test_every_prose_output_goes_to_an_adjudicator(self):
        """Exact checks pass or fail; a prose output that clears them always needs adjudication, and the
        result hands the adjudicator the fact list."""
        for case in ('prose-exempt', 'prose-scope'):
            oracle = hp.load_oracle(hp.HELDOUT, case)
            for example in hp.examples(hp.HELDOUT, case):
                with self.subTest(case=case, example=example['id']):
                    result = hp.grade(case, observation(case, example))
                    self.assertNotEqual(result['outcome'], 'passed')
                    self.assertEqual(result['facts'], oracle['facts'])

    def test_fact_lists_serve_an_adjudicator(self):
        for case in ('prose-exempt', 'prose-scope'):
            oracle = hp.load_oracle(hp.HELDOUT, case)
            kinds = {f['kind'] for f in oracle['facts']}
            self.assertLessEqual({'must-survive', 'condition', 'must-not-add'}, kinds, case)
            for fact in oracle['facts']:
                self.assertEqual(tuple(fact), hp.FACT_FIELDS, (case, fact))
                self.assertTrue(fact['statement'] and fact['review_question'].endswith('?'), (case, fact['id']))
        self.assertEqual(hp.load_oracle(hp.HELDOUT, 'prose-verbatim')['facts'], [])

    def test_malformed_fact_list_is_detected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            copy_tree(root)
            path = root / 'oracles/prose-scope.json'
            oracle = json.loads(path.read_text())
            oracle['facts'][0]['topics'] = ['valid']
            path.write_text(json.dumps(oracle, indent=2) + '\n')
            self.assertTrue(any('oracle facts need' in p for p in hp.verify(root)))

    def test_examples_cover_good_bad_and_alternatives(self):
        """Every group has known-good, valid-alternative and known-bad outputs. A known-bad output fails an exact
        check or is unfaithful; --check verifies that `shows` names a known fact."""
        for case in hp.CASES:
            labels = [e['label'] for e in hp.examples(hp.HELDOUT, case)]
            self.assertGreaterEqual(labels.count('known-good'), 1, case)
            self.assertGreaterEqual(labels.count('valid-alternative'), 1, case)
            self.assertGreaterEqual(labels.count('known-bad'), 3, case)
            for example in hp.examples(hp.HELDOUT, case):
                bad = example['expected_failures'] or example.get('expected_adjudication') == 'unfaithful'
                self.assertEqual(bool(bad), example['label'] == 'known-bad', (case, example['id']))
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            copy_tree(root)
            path = root / 'oracles/prose-scope/examples/index.json'
            rows = json.loads(path.read_text())
            rows[3]['shows'] = 'not-a-fact'
            path.write_text(json.dumps(rows, indent=2) + '\n')
            self.assertTrue(any('shows a known fact' in p for p in hp.verify(root)))

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

    def test_exact_checks_ignore_style(self):
        """Dash, filler and opener edits outside protected bytes never add an exact failure and never make a
        prose output pass."""
        for case in ('prose-exempt', 'prose-scope'):
            oracle = hp.load_oracle(hp.HELDOUT, case)
            protected = None
            if case == 'prose-exempt':
                manifest, _ = hp.load()
                spec = oracle['exact'][0]['span']
                protected = hp.span(hp.fixture_files(hp.HELDOUT, manifest['cases'][0])[spec['path']], spec)
            for example in hp.examples(hp.HELDOUT, case):
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
                        self.assertEqual(set(result['failures']) - set(expected['failures']), set())
                        self.assertNotEqual(result['outcome'], 'passed')

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
