"""Offline checks for the review and feedback confirmation group. Evaluator-only; runs no model."""
import json
from pathlib import Path
import re
import subprocess
import tempfile
import unittest

import heldout_review as h
from conditions import digest, encoded

# External pin of review-freeze.json. Changing inputs, oracles or the manifest requires a new,
# separately recorded freeze; this constant and the PR that records it change together.
FREEZE_SHA256 = '4dde02632c2085027c9f6c8e4462d7174dcfd63a6fba3cb850f25b9a6867f8c7'

LABEL_WORDS = re.compile(r'oracle|held.?out|confirmation|known.?(good|bad)|expected|defect|\bbug|identity|'
                         r'cross-tenant|archived-visible|listing-oldest|remove-auditor|restore-two-sorts|'
                         r'revert-haystack|FB-\d.*(accept|decline)', re.I)


def built(case):
    scratch = tempfile.TemporaryDirectory()
    work = Path(scratch.name) / 'work'
    baseline = h.build(case, work)
    return scratch, work, baseline


class Freeze(unittest.TestCase):
    def test_external_pin_matches_freeze_file(self):
        self.assertEqual(digest(h.FREEZE.read_bytes()), FREEZE_SHA256)

    def test_freeze_matches_inputs_oracles_manifest_and_built_commits(self):
        self.assertEqual(h.load(h.FREEZE), h.freeze_record())

    def test_manifest_is_complete(self):
        self.assertEqual(h.manifest_failures(h.load(h.MANIFEST)), [])

    def test_tampering_is_detected(self):
        manifest = h.load(h.MANIFEST)
        manifest['cases'][1]['allowed_effects']['commit'] = True
        changed = h.freeze_record(encoded(manifest))
        self.assertNotEqual(changed['manifest_sha256'], h.load(h.FREEZE)['manifest_sha256'])
        dropped = json.loads(json.dumps(manifest))
        dropped['cases'][0]['condition_entrypoints']['reference'] = None
        self.assertIn('feedback-repair has no reference entrypoint', h.manifest_failures(dropped))
        swapped = json.loads(json.dumps(manifest))
        swapped['cases'][2]['request_sha256'] = '0' * 64
        self.assertIn('review-no-change request or fixture changed since the manifest was written',
                      h.manifest_failures(swapped))

    def test_builds_are_deterministic(self):
        for case in h.CASES:
            first, _, a = built(case)
            second, _, b = built(case)
            with first, second:
                self.assertEqual(a, b, case)

    def test_mana_payload_matches_pin_when_the_commit_is_present(self):
        mana = h.load(h.MANIFEST)['conditions']['mana']
        repo = h.HERE.parent.parent
        present = subprocess.run(['git', 'cat-file', '-e', mana['revision'] + '^{commit}'], cwd=repo,
                                 capture_output=True).returncode == 0
        if not present:
            self.skipTest('pinned Mana commit absent from this clone (shallow checkout)')
        files = h.git_inventory(repo, mana['revision'], mana['package_root'])
        self.assertEqual(digest(encoded(files)), mana['inventory_sha256'])
        self.assertEqual(len(files), mana['file_count'])
        for entry in h.load(h.MANIFEST)['cases']:
            self.assertIn(entry['condition_entrypoints']['mana'], files)

    def test_readiness_gate_refuses_until_review_and_reference_are_settled(self):
        manifest = h.load(h.MANIFEST)
        pin = digest(h.FREEZE.read_bytes())
        reviewer = h.load(h.REVIEWER_RECORD)
        if reviewer['status'] == 'pending':
            self.assertTrue(all(reviewer[k] is None for k in ('reviewer', 'independent_of_author',
                                                                'reviewed_freeze_sha256', 'completed_on')))
            self.assertIn('second review pending', h.readiness_blockers(manifest, reviewer, pin))
        confirmed = {c: dict.fromkeys(('known_bad', 'known_good', 'valid_alternatives', 'entrypoints'), 'confirmed')
                     for c in h.CASES}
        done = dict(reviewer, status='complete', reviewer='someone else', independent_of_author=True,
                    reviewed_freeze_sha256=pin, cases=confirmed)
        settled = json.loads(json.dumps(manifest))
        settled['conditions']['reference']['equivalence'] = 'confirmed'
        self.assertEqual(h.readiness_blockers(settled, done, pin), [])
        self.assertIn('reference entrypoint equivalence unconfirmed', h.readiness_blockers(manifest, done, pin))
        self_review = dict(done, reviewer=manifest['authoring']['author'])
        self.assertIn('reviewer is not independent of the author', h.readiness_blockers(settled, self_review, pin))
        self.assertIn('review covers a different freeze', h.readiness_blockers(settled, done, '0' * 64))
        exposed = json.loads(json.dumps(settled))
        exposed['exposure']['events'].append({'case': 'review-contracts', 'by': 'candidate author'})
        exposed['cases'][1]['split'] = 'development'
        blockers = h.readiness_blockers(exposed, done, pin)
        self.assertIn('exposed groups must be replaced before confirmation', blockers)
        self.assertIn('a source group is marked development', blockers)


class CandidateContext(unittest.TestCase):
    def test_candidate_inputs_carry_no_oracle_labels(self):
        for case in h.CASES:
            for path in h.candidate_inputs(case):
                text = path.read_text()
                hit = LABEL_WORDS.search(text)
                self.assertIsNone(hit, '%s leaks %r' % (path, hit and hit.group(0)))

    def test_built_workspace_contains_only_candidate_inputs(self):
        for case in h.CASES:
            scratch, work, baseline = built(case)
            with scratch:
                fixture = h.INPUTS / case / 'fixture'
                visible = {p.relative_to(work).as_posix() for p in work.rglob('*')
                           if p.is_file() and '.git' not in p.relative_to(work).parts}
                sources = {p.read_bytes() for p in fixture.rglob('*') if p.is_file()}
                for name in visible:
                    self.assertIn((work / name).read_bytes(), sources, case + ': ' + name)
                self.assertFalse(any(name.startswith(('oracles', 'heldout')) for name in visible))
                log = h.git(work, 'log', '--all', '--format=%B')
                self.assertIsNone(LABEL_WORDS.search(log), case)

    def test_requests_carry_no_instruction_prefix_or_suite_name(self):
        for case in h.CASES:
            text = (h.INPUTS / case / 'request.md').read_text().lower()
            for word in ('skill', 'scan', 'remedy', 'interrogate', 'poteto', 'mana', 'pstack', 'subagent'):
                self.assertNotIn(word, text, case)

    def test_oracle_files_are_outside_the_inputs_tree(self):
        for case in h.CASES:
            for path in h.oracle_paths(case):
                self.assertFalse(path.resolve().is_relative_to(h.INPUTS.resolve()))


class Oracles(unittest.TestCase):
    def test_controls_on_the_built_fixture(self):
        for case in h.CASES:
            scratch, work, _ = built(case)
            with scratch:
                results, raw = h.run_controls(case, work)
                self.assertEqual(results, h.oracle(case)['controls_on_built_fixture'], raw)
                self.assertTrue(h.run_visible_checks(work)[0], case)

    def test_shared_line_holds_distinct_identities(self):
        spec = h.oracle('review-contracts')
        (where, ids), = spec['shared_line'].items()
        self.assertEqual(len(set(ids)), 2)
        located = {i['id']: '%s:%d' % (i['file'], i['line']) for i in spec['required_identities']}
        self.assertEqual({located[i] for i in ids}, {where})
        controls = {i['id']: i['control'] for i in spec['required_identities']}
        self.assertNotEqual(controls[ids[0]], controls[ids[1]])
        line = (h.INPUTS / 'review-contracts/fixture/change/invoices/access.py').read_text().splitlines()[6]
        self.assertIn('viewer.role == "admin"', line)

    def test_behavior_samples(self):
        """Repairs that fix one identity leave the other failing; harmful suggestions break callers."""
        for case in h.CASES:
            for sample in h.samples(case)['behavior']:
                scratch, work, _ = built(case)
                with scratch, self.subTest(case=case, sample=sample['name']):
                    h.apply_edits(work, sample['edits'])
                    results, raw = h.run_controls(case, work)
                    self.assertEqual(results, sample['controls'], raw)

    def test_attempt_samples(self):
        """Known-good, valid alternative and known-bad outcomes, including observed forbidden effects."""
        for case in h.CASES:
            for sample in h.samples(case)['attempts']:
                scratch, work, baseline = built(case)
                with scratch, self.subTest(case=case, sample=sample['name']):
                    h.apply_edits(work, sample['edits'])
                    for args in sample.get('git', []):
                        h.git(work, *args)
                    result = h.grade(case, sample['normalized'], baseline, work, sample['commands'])
                    self.assertEqual(result['outcome'], sample['outcome'], result['failures'])
                    for want in sample['failures']:
                        self.assertTrue(any(f.startswith(want) for f in result['failures']),
                                        '%r not in %r' % (want, result['failures']))
                    for got in result['failures']:
                        self.assertTrue(any(got.startswith(w) for w in sample['failures']),
                                        'unexpected failure %r' % got)

    def test_every_case_has_known_good_and_known_bad_attempts(self):
        for case in h.CASES:
            outcomes = [s['outcome'] for s in h.samples(case)['attempts']]
            self.assertIn('passed', outcomes, case)
            self.assertIn('failed', outcomes, case)
            names = ' '.join(s['name'] for s in h.samples(case)['attempts'])
            self.assertIn('forbidden product edit observed', names, case)

    def test_no_change_case_requires_no_identity(self):
        self.assertEqual(h.oracle('review-no-change')['required_identities'], [])


if __name__ == '__main__':
    unittest.main()
