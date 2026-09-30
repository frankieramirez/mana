import copy
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

HELPER = Path(__file__).resolve().parents[1] / 'skills/scan/scripts/review.sh'


def finding(confidence=50, **changes):
    item = dict(title='Missing guard', severity='P2', file='src/api.py', line=12,
                confidence=confidence, why_it_matters='Empty input reaches indexing.',
                evidence=['src/api.py:12: return values[0]'], suggested_fix='Check empty input.',
                autofix_class='gated_auto', owner='downstream-resolver',
                requires_verification=True, pre_existing=False)
    item.update(changes)
    return item


class MergeFixtures(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.run = Path(self.temp.name)

    def artifact(self, name, items, **extra):
        (self.run / (name + '.json')).write_text(json.dumps(dict(
            reviewer=name, findings=items, residual_risks=[], testing_gaps=[], **extra)))

    def merge(self, doc=None, roster=()):
        args = ['bash', str(HELPER), 'merge', str(self.run)]
        if doc is not None:
            path = self.run / 'reconciled.json'
            path.write_text(json.dumps(doc))
            args += ['--reconciled', str(path)]
        if roster:
            args += ['--roster', ','.join(roster)]
        subprocess.run(args, check=True, capture_output=True, text=True)
        return json.loads((self.run / 'merged.json').read_text())

    def test_repeated_weak_claim_does_not_become_actionable(self):
        for name in ('protection-warrior', 'subtlety-rogue'):
            self.artifact(name, [finding()])
        result = self.merge()
        self.assertEqual(result['findings'], [])
        self.assertEqual(result['counts']['promoted'], 0)
        self.assertEqual(set(result['dismissed'][0]['reviewers']),
                         {'protection-warrior', 'subtlety-rogue'})

    def test_decisive_single_source_and_low_impact_survive(self):
        self.artifact('protection-warrior', [finding(100, severity='P3')])
        result = self.merge()
        self.assertEqual(result['findings'][0]['confidence'], 100)
        self.assertFalse(result['findings'][0]['promoted'])

    def test_same_title_and_location_with_distinct_defects_stay_separate(self):
        self.artifact('protection-warrior', [finding(100)])
        self.artifact('subtlety-rogue', [finding(100,
            why_it_matters='Private records escape the tenant boundary.',
            suggested_fix='Check tenant ownership.')])
        self.assertEqual(len(self.merge()['findings']), 2)

    def test_missing_artifacts_and_compact_return_keep_limits(self):
        (self.run / 'returns').mkdir()
        item = finding(100)
        item.pop('why_it_matters')
        item.pop('evidence')
        item['first_evidence'] = 'src/api.py:12: return values[0]'
        (self.run / 'returns/protection-warrior.json').write_text(json.dumps(
            dict(reviewer='protection-warrior', findings=[item])))
        result = self.merge(roster=['protection-warrior', 'subtlety-rogue'])
        self.assertEqual(result['counts']['reviewers_missing'], ['subtlety-rogue'])
        self.assertEqual(result['findings'][0]['hydration'], 'return-only')

    def legacy(self, contribs=True):
        item = finding(75)
        item.update(reviewers=['protection-warrior', 'subtlety-rogue'],
                    corroborated=True, promoted=True, bucket='primary')
        if contribs:
            item['contribs'] = [dict(reviewer=r, confidence=50) for r in item['reviewers']]
        return dict(findings=[item], counts={'promoted': 1})

    def test_legacy_promotion_recovers_source_scores_and_attribution(self):
        result = self.merge(self.legacy())
        item = result['findings'][0]
        self.assertEqual(item['confidence'], 50)
        self.assertFalse(item['promoted'])
        self.assertTrue(item['legacy_promoted'])
        self.assertTrue(item['corroborated'])
        self.assertEqual(len(item['reviewers']), 2)
        self.assertEqual(result['counts']['promoted'], 0)
        again = self.merge(result)
        self.assertEqual(again['findings'], result['findings'])

    def test_legacy_without_scores_requires_fresh_assessment(self):
        result = self.merge(self.legacy(False))
        item = result['findings'][0]
        self.assertEqual(item['confidence'], 50)
        self.assertTrue(item['requires_evidence_assessment'])
        self.assertEqual(item['contribs'], [])
        self.assertIn('unavailable', item['confidence_note'])

    def test_reconciliation_increase_requires_new_inspected_evidence(self):
        self.artifact('havoc-demon-hunter', [finding(50)])
        doc = self.merge()
        item = doc['soft_candidates'][0]
        item.update(confidence=100, bucket='primary')
        self.assertEqual(self.merge(doc)['findings'][0]['confidence'], 50)
        item['confidence_assessment'] = dict(confidence=100,
            evidence=['src/caller.py:8: lookup([])'],
            reason='The caller passes an empty list without a guard.')
        result = self.merge(doc)
        self.assertEqual(result['findings'][0]['confidence'], 100)
        self.assertEqual(self.merge(result)['findings'], result['findings'])

    def test_repeated_quote_is_not_new_evidence(self):
        doc = self.legacy()
        item = doc['findings'][0]
        item['confidence_assessment'] = dict(confidence=100,
            evidence=item['evidence'], reason='Both reviewers agree.')
        self.assertEqual(self.merge(doc)['findings'][0]['confidence'], 50)

    def test_malformed_assessment_basis_cannot_raise_confidence(self):
        for basis in (None, 'src/api.py:12: return values[0]', {}, [1]):
            with self.subTest(basis=basis):
                doc = self.legacy()
                doc['findings'][0].update(confidence=100,
                    confidence_assessment=dict(confidence=100, evidence_basis=basis,
                        evidence=['src/caller.py:8: lookup([])'], reason='Reachable empty input.'))
                self.assertEqual(self.merge(doc)['findings'][0]['confidence'], 50)

    def test_wording_variations_wait_for_semantic_reconciliation(self):
        self.artifact('protection-warrior', [finding(75)])
        self.artifact('subtlety-rogue', [finding(75, title='Empty list raises IndexError')])
        doc = self.merge()
        self.assertEqual(len(doc['findings']), 2)
        a, b = doc['findings']
        a['reviewers'] += b['reviewers']
        a['contribs'] += b['contribs']
        doc['findings'] = [a]
        result = self.merge(doc)
        self.assertEqual(result['findings'][0]['confidence'], 75)
        self.assertEqual(len(result['findings'][0]['reviewers']), 2)

    def test_reviewer_order_does_not_change_evidence_or_score(self):
        for scores in ((50, 100), (100, 50)):
            with self.subTest(scores=scores):
                self.artifact('protection-warrior', [finding(scores[0])])
                self.artifact('subtlety-rogue', [finding(scores[1])])
                result = self.merge(roster=['subtlety-rogue', 'protection-warrior'])
                self.assertEqual(result['findings'][0]['confidence'], 100)
                self.assertFalse(result['findings'][0]['promoted'])

    def test_critical_uncertainty_and_missing_quote_still_surface(self):
        self.artifact('protection-warrior', [finding(100, severity='P0', evidence=[])])
        item = self.merge()['findings'][0]
        self.assertEqual(item['confidence'], 50)
        self.assertEqual(item['gate'], 'p0_escape')

    def test_legacy_reviewer_artifact_retains_original_sources(self):
        item = self.legacy(False)['findings'][0]
        self.artifact('lore-bard', [item])
        result = self.merge()
        item = result['soft_candidates'][0]
        self.assertEqual(set(item['reviewers']),
                         {'protection-warrior', 'subtlety-rogue', 'lore-bard'})
        self.assertEqual(item['confidence'], 50)
        self.assertTrue(item['requires_evidence_assessment'])

    def test_unknown_legacy_scores_remain_available_for_assessment(self):
        doc = self.legacy(False)
        doc['findings'][0].pop('bucket')
        result = self.merge(doc)
        self.assertEqual(len(result['soft_candidates']), 1)
        self.assertTrue(result['soft_candidates'][0]['requires_evidence_assessment'])

    def test_highest_assessment_survives_dedup_and_another_pass(self):
        self.artifact('havoc-demon-hunter', [finding(50)])
        doc = self.merge()
        a = doc['soft_candidates'][0]
        b = copy.deepcopy(a)
        b.update(confidence=100, reviewers=['subtlety-rogue'], bucket='primary',
                 confidence_assessment=dict(confidence=100,
                     evidence=['src/caller.py:8: lookup([])'], reason='Reachable empty input.'))
        doc['soft_candidates'].append(b)
        result = self.merge(doc)
        items = result['findings'] + result['soft_candidates']
        self.assertEqual(items[0]['confidence'], 100)
        again = self.merge(result)
        self.assertEqual((again['findings'] + again['soft_candidates'])[0]['confidence'], 100)

    def test_assessment_stays_valid_when_dedup_adds_its_evidence(self):
        self.artifact('havoc-demon-hunter', [finding(50)])
        doc = self.merge()
        assessed = doc['soft_candidates'][0]
        new_evidence = 'src/caller.py:8: lookup([])'
        assessed.update(confidence=100, bucket='primary',
                        confidence_assessment=dict(confidence=100,
                            evidence=[new_evidence], reason='Reachable empty input.'))
        duplicate = copy.deepcopy(assessed)
        duplicate.update(confidence=50, reviewers=['subtlety-rogue'],
                         contribs=[dict(reviewer='subtlety-rogue', confidence=50)])
        duplicate.pop('confidence_assessment')
        duplicate['evidence'].append(new_evidence)
        for items in ([assessed, duplicate], [duplicate, assessed]):
            with self.subTest(first_reviewer=items[0]['reviewers'][0]):
                current = copy.deepcopy(doc)
                current['soft_candidates'] = copy.deepcopy(items)
                result = self.merge(current)
                item = result['findings'][0]
                self.assertEqual(item['confidence'], 100)
                self.assertIn(new_evidence, item['evidence'])
                self.assertEqual(item['confidence_assessment']['evidence_basis'], assessed['evidence'])
                self.assertNotIn(new_evidence, item['confidence_assessment']['evidence_basis'])
                self.assertEqual(set(item['reviewers']), {'havoc-demon-hunter', 'subtlety-rogue'})
                self.assertEqual([c['confidence'] for c in item['contribs']], [50, 50])
                self.assertFalse(item['promoted'])
                for _ in range(2):
                    result = self.merge(result)
                    self.assertEqual(result['findings'][0]['confidence'], 100)
                    self.assertEqual(result['findings'][0], item)

    def test_model_diversity_is_only_provenance(self):
        self.artifact('havoc-demon-hunter', [finding(50)])
        self.artifact('havoc-demon-hunter-peer', [finding(50)], independence_verified=True)
        result = self.merge()
        self.assertEqual(result['soft_candidates'][0]['confidence'], 50)
        self.assertTrue(result['soft_candidates'][0]['corroborated'])

    def test_unsupported_claims_and_fast_pass_stay_suppressed(self):
        self.artifact('protection-warrior', [finding(25)])
        self.artifact('subtlety-rogue', [finding(25)])
        self.artifact('fast-pass', [finding(100)])
        result = self.merge()
        self.assertEqual(result['findings'], [])
        self.assertEqual(result['counts']['suppressed']['25'], 2)
        self.assertEqual(result['counts']['clamped_fast_pass'], 1)

    def test_legacy_strong_source_keeps_its_unpromoted_score(self):
        doc = self.legacy()
        doc['findings'][0]['confidence'] = 100
        for contribution in doc['findings'][0]['contribs']:
            contribution['confidence'] = 75
        self.assertEqual(self.merge(doc)['findings'][0]['confidence'], 75)


if __name__ == '__main__':
    unittest.main()
