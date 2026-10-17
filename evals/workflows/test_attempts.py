"""Offline attempt records, blinded packets, judgments and regrades; never invoke a model."""
import contextlib
import io
import json
from pathlib import Path
import random
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import adjudication
import attempts
import conditions
import run


def fake_execution(status='completed', passed=True, extra=None):
    """Stand in for the host: a real prepared workspace with observed evidence, no model."""
    def execute(case, out, timeout, condition=None, **kwargs):
        work, baseline = run.prepare(case, out, condition=condition)
        initial = out / 'initial-fixture'
        for name in baseline['product_state']:
            target = initial / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(work / name, target)
        commands = []
        if condition['kind'] != 'none':
            entry = work / 'installed/payload' / condition['entrypoint']
            commands.append({'id': 'c1', 'type': 'command_execution', 'command': 'cat ' + str(entry),
                             'aggregated_output': entry.read_text(), 'exit_code': 0})
        commands.append({'id': 'c2', 'type': 'command_execution', 'command': 'bash check.sh',
                         'aggregated_output': '', 'exit_code': 1})
        commands.append({'id': 'c3', 'type': 'command_execution', 'command': 'cat report.md',
                         'aggregated_output': (work / 'report.md').read_text(), 'exit_code': 0})
        (out / 'prompt.txt').write_text(conditions.prompt(case, work, condition))
        suffix = {'mana': ' Following MANA ONLY INSTRUCTIONS, per Mana scan.',
                  'reference': ' Following REFERENCE ONLY INSTRUCTIONS, per Cursor review.'}.get(condition['kind'], '')
        response = {'report': 'The confirmed finding is app.txt contains old.' + suffix,
                    'checks': [{'command': 'bash check.sh', 'status': 'failed', 'exit_code': 1,
                                'claim': 'app.txt still contains old'}]}
        (out / 'response.json').write_text(json.dumps(response))
        (out / 'events.jsonl').write_text(''.join(json.dumps({'type': 'item.completed', 'item': c}) + '\n'
                                                  for c in commands))
        (out / 'final.diff').write_text(run.git(work, 'diff', baseline['head']))
        if extra:
            extra(out, work, condition)
        return {'case': case['id'], 'execution': status, 'passed': passed and status == 'completed',
                'failures': [] if passed else ['out-of-scope product change'], 'live': False,
                'commands': commands, 'actual_model': None, 'seconds': 1.5, 'baseline': baseline,
                'usage': [{'type': 'turn.completed', 'usage': {'input_tokens': 4, 'output_tokens': 2}}],
                'context': {'full_reads': {}, 'unique_full_read_bytes': 0},
                'initial_fixture_sha256': conditions.digest(conditions.encoded(conditions.inventory(initial)))}
    return execute


class AttemptTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.addCleanup(self.unlock)
        self.root = Path(self.temp.name)
        self.manifest = {
            'version': 1, 'study': 'offline-attempts', 'host': run.SUPPORTED_HOST,
            'model': 'gpt-6.1-sol', 'reasoning': 'medium', 'seed': 20261017,
            'repetitions': 2, 'conditions': {'none': {}}, 'cases': [{
                'id': 'review-report-only', 'source_group': 'public-review-action',
                'split': 'development', 'request': 'Read report.md and report its findings. Leave the project unchanged.',
                'timeout_seconds': 120}]}
        for kind in ('mana', 'reference'):
            payload = self.root / kind
            payload.mkdir()
            entry = 'SKILL.md' if kind == 'mana' else 'workflows/review.md'
            (payload / entry).parent.mkdir(exist_ok=True)
            (payload / entry).write_text(kind.upper() + ' ONLY INSTRUCTIONS\nShort line\n')
            (payload / 'asset.bin').write_bytes(b'\x00\xff\xfe' + kind.encode())
            self.manifest['conditions'][kind] = {
                'root': str(payload), 'revision': ('a' if kind == 'mana' else 'b') * 40,
                'inventory_sha256': conditions.inventory_digest(payload),
                'entrypoints': {'review-report-only': entry}}

    def unlock(self):
        for path in self.root.rglob('*'):
            if path.is_dir() and not path.is_symlink():
                path.chmod(0o755)

    def freeze(self, name='study'):
        path = self.root / (name + '.json')
        path.write_text(json.dumps(self.manifest))
        result = conditions.freeze(path, self.root / name, run.load_cases(), run.HERE,
                                   run.STUDY_SOURCES, run.SUPPORTED_HOSTS, run.prepare)
        return conditions.FrozenStudy(self.root / name, result['controls_sha256'], run.STUDY_SOURCES, run.HERE)

    def execute(self, study, slot, **fake):
        with patch.object(run, 'execute', side_effect=fake_execution(**fake)), \
                contextlib.redirect_stdout(io.StringIO()):
            return run.execute_study(study, slot)

    def completed_study(self, name='study', extra=None):
        study = self.freeze(name)
        for slot in range(1, 7):
            self.assertEqual(self.execute(study, slot, extra=extra), 0)
        return study

    def test_execution_status_stays_separate_from_task_outcome_and_every_slot_persists(self):
        study = self.freeze()
        self.assertEqual(self.execute(study, 1), 0)
        self.assertEqual(self.execute(study, 2, passed=False), 1)
        self.assertEqual(self.execute(study, 3, status='timeout'), 1)
        with self.assertRaises(ValueError):
            study.claim(4)
        records = attempts.verify(study)
        self.assertEqual(sorted(records), [1, 2, 3])
        first, second, third = (records[s][0] for s in (1, 2, 3))
        self.assertEqual((first['execution_status'], first['task_outcome'], first['counts_as_pass']), ('completed', 'passed', True))
        self.assertEqual((second['execution_status'], second['task_outcome']), ('completed', 'failed'))
        self.assertEqual((third['execution_status'], third['task_outcome'], third['counts_as_pass']), ('timeout', None, False))
        self.assertTrue(third['stopped_schedule'])
        for record in (first, second, third):
            self.assertEqual(record['retry_attempts'], 0)
            self.assertTrue(record['archive']['sha256'])
            paths = {e['path']: e for e in record['artifact_index']}
            self.assertIn('workspace/app.txt', paths)
            self.assertTrue(paths['evaluation.json']['sha256'])
            self.assertFalse(any(e['archived'] for p, e in paths.items() if p.startswith('workspace/.git/')))
            self.assertEqual(record['frozen_fixture_sha256'], record['fixture_sha256'])
            self.assertEqual(record['controls_sha256'], study.expected_digest)
        summary = attempts.summarize(study)
        self.assertEqual(summary['allocated_slots'], 6)
        self.assertEqual(summary['unstarted_slots'], [4, 5, 6])
        self.assertEqual(summary['execution_status_counts'],
                         {'setup_failed': 0, 'agent_failed': 0, 'timeout': 1, 'collection_failed': 0,
                          'completed': 2, 'unstarted': 3})
        self.assertEqual((summary['passes'], summary['not_passed'], summary['stopped_at_slot']), (1, 5, 3))

    def test_each_infrastructure_status_is_preserved_without_replacement(self):
        for index, status in enumerate(('agent_failed', 'timeout', 'collection_failed', 'grading_failed')):
            with self.subTest(status=status):
                study = self.freeze('status-' + str(index))
                self.execute(study, 1, status=status)
                record = attempts.verify(study)[1][0]
                expected = ('completed', 'needs_adjudication') if status == 'grading_failed' else (status, None)
                self.assertEqual((record['execution_status'], record['task_outcome']), expected)
                self.assertEqual(record['runner_execution'], status)
                self.assertFalse(record['counts_as_pass'])
                with self.assertRaises(ValueError):
                    study.claim(2)
        study = self.freeze('setup')
        with patch.object(run.shutil, 'which', return_value='/usr/bin/true'), \
                patch.object(run.subprocess, 'check_output', return_value='codex-cli unvalidated\n'), \
                patch.object(run.subprocess, 'Popen') as model:
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(run.execute_study(study, 1), 1)
            model.assert_not_called()
        record = attempts.verify(study)[1][0]
        self.assertEqual((record['execution_status'], record['task_outcome']), ('setup_failed', None))
        self.assertIsNone(record['fixture_sha256'])
        self.assertTrue(record['frozen_fixture_sha256'])

    def test_interrupted_claim_is_sealed_as_an_incomplete_attempt(self):
        study = self.freeze()
        study.claim(1)
        study.release()
        with self.assertRaisesRegex(ValueError, 'claimed but never sealed'):
            attempts.verify(study)
        self.assertTrue(attempts.seal_claimed(study)[0]['created'])
        record = attempts.verify(study)[1][0]
        self.assertEqual((record['execution_status'], record['task_outcome']), ('collection_failed', None))
        self.assertIn('result.json missing or unreadable: interrupted or unrecorded attempt', record['failures'])

    def test_sealed_records_are_immutable_and_hidden_replacement_is_detected(self):
        study = self.freeze()
        self.execute(study, 1)
        results = study.root / 'results'
        record_path = results / '001.attempt.json'
        self.assertEqual(attempts.seal(study, 1)['created'], False)
        with contextlib.redirect_stdout(io.StringIO()):
            run.regrade(results)
        self.assertTrue(list(results.glob('regrade-*.json')))
        attempts.verify(study)
        self.assertEqual(record_path.stat().st_mode & 0o777, 0o444)
        (results / '001' / 'notes.txt').write_text('changed after sealing\n')
        with self.assertRaisesRegex(ValueError, 'already sealed with different evidence'):
            attempts.seal(study, 1)
        with self.assertRaisesRegex(ValueError, 'evidence changed after sealing'):
            attempts.verify(study)
        (results / '001' / 'notes.txt').unlink()
        attempts.verify(study)
        (results / '001-retry').mkdir()
        with self.assertRaisesRegex(ValueError, 'hidden replacement'):
            attempts.verify(study)
        (results / '001-retry').rmdir()
        (results / '007').mkdir()
        with self.assertRaisesRegex(ValueError, 'unallocated attempt entry'):
            attempts.verify(study)
        (results / '007').rmdir()
        original = record_path.read_bytes()
        record_path.chmod(0o644)
        record_path.write_bytes(original.replace(b'"completed"', b'"timeout"', 1))
        with self.assertRaisesRegex(ValueError, 'record changed after sealing'):
            attempts.verify(study)
        record_path.write_bytes(original)
        ledger = results / 'attempts.jsonl'
        ledger.write_text(ledger.read_text() * 2)
        with self.assertRaisesRegex(ValueError, 'appears twice'):
            attempts.verify(study)

    def test_packets_carry_evidence_and_withhold_condition_identity(self):
        def extra(out, work, condition):
            (work / 'artifacts' / 'shot.bin').write_bytes(b'\x89PNG\x00\xff')
            (work / 'artifacts' / 'copied.bin').write_bytes(b'\x00\xff\xfe' + b'mana')
            if condition['kind'] == 'reference':
                (out / 'threads.json').write_text(json.dumps({'child-1': {'model': 'gpt-6.1-sol'}}))
                (out / 'children').mkdir()
                (out / 'children' / 'child-1.txt').write_text('Child read REFERENCE ONLY INSTRUCTIONS and confirmed app.txt.\n')
        study = self.completed_study(extra=extra)
        review_root = self.root / 'review'
        result = adjudication.export(study, review_root, ['cursor'])
        self.assertEqual((result['packets'], result['not_exported'], result['agent_executed']), (6, 0, False))
        self.assertEqual((review_root / 'restricted').stat().st_mode & 0o777, 0o700)
        key = json.loads((review_root / 'restricted/key.json').read_text())
        layouts = {}
        for packet_id, entry in key['packets'].items():
            self.assertRegex(packet_id, r'p[0-9a-f]{12}')
            directory = review_root / 'packets' / packet_id
            manifest = json.loads((directory / 'manifest.json').read_text())
            self.assertNotIn('condition', manifest)
            self.assertNotIn('schedule_slot', json.dumps(manifest))
            for required in ('contract.json', 'source/app.txt', 'source/report.md', 'final/app.txt',
                             'final.diff', 'commands.json', 'checks.json', 'final-message.json',
                             'artifacts/shot.bin'):
                self.assertIn(required, manifest['files'])
            self.assertNotIn('artifacts/copied.bin', manifest['files'])
            self.assertFalse((directory / 'prompt.txt').exists())
            text = '\n'.join(p.read_bytes().decode('utf-8', 'replace') for p in directory.rglob('*') if p.is_file())
            for forbidden in ('MANA ONLY', 'REFERENCE ONLY', 'a' * 40, 'b' * 40, 'Use the instructions at',
                              'installed/payload', 'workflows/review.md', 'public-review-action', str(study.root)):
                self.assertNotIn(forbidden, text)
            self.assertNotRegex(text, r'(?i)\b(mana|cursor)\b')
            checks = json.loads((directory / 'checks.json').read_text())
            self.assertEqual([c['command'] for c in checks['observed']], ['bash check.sh'])
            self.assertEqual(checks['claimed'][0]['status'], 'failed')
            commands = json.loads((directory / 'commands.json').read_text())
            limits = entry['masking']['limits']
            self.assertTrue(any('binary file copied without masking: artifacts/shot.bin' == l for l in limits))
            self.assertTrue(any('artifacts/copied.bin' in l for l in limits))
            loading = any('Instruction loading remains visible' in l for l in limits)
            self.assertEqual(loading, entry['condition'] != 'none')
            if entry['condition'] != 'none':
                self.assertIn('[instruction text withheld]', commands[0]['output'])
                self.assertIn('<instructions>/<instruction-file>', commands[0]['command'])
            if entry['condition'] == 'reference':
                self.assertTrue(manifest['children']['collected'])
                child = (directory / 'children/children/child-1.txt').read_text()
                self.assertIn('[instruction text withheld]', child)
                self.assertIn('children/threads.json', manifest['files'])
            else:
                self.assertEqual(manifest['children'], {'collected': False, 'reason': 'delegation was disabled for this study'})
            layouts[packet_id] = {p for p in manifest['files'] if not p.startswith('children/')}
        self.assertEqual(len({frozenset(v) for v in layouts.values()}), 1)
        with self.assertRaises(FileExistsError):
            adjudication.export(study, review_root)

    def judged_review(self, name='study'):
        study = self.completed_study(name)
        review_root = self.root / (name + '-review')
        adjudication.export(study, review_root)
        return study, adjudication.Review(study, review_root)

    def test_two_initial_judgments_and_adjudication_preserve_evidence_hashes(self):
        study, review = self.judged_review()
        packet = sorted(review.key['packets'])[0]
        slot = review.key['packets'][packet]['slot']
        record, attempt_sha = attempts.verify(study)[slot]
        first = adjudication.judge(review, packet, 'alice', 'human', 'initial', 'passed', 'Report matches the contract.',
                                   active_seconds=240, censored=False)
        with self.assertRaisesRegex(ValueError, 'adjudication needs both'):
            adjudication.judge(review, packet, 'carol', 'human', 'adjudication', 'failed', 'Too early.')
        with self.assertRaisesRegex(ValueError, 'different reviewers'):
            adjudication.judge(review, packet, 'alice', 'human', 'initial', 'failed', 'Second look.')
        with self.assertRaisesRegex(ValueError, 'capped at 600'):
            adjudication.judge(review, packet, 'bob', 'human', 'initial', 'failed', 'Long review.', active_seconds=700)
        with self.assertRaisesRegex(ValueError, 'censored review is unresolved'):
            adjudication.judge(review, packet, 'bob', 'human', 'initial', 'failed', 'Ran out of time.', 600, True)
        second = adjudication.judge(review, packet, 'bob', 'human', 'initial', 'failed', 'Check failure was not reported as blocking.',
                                    active_seconds=600, censored=False)
        with self.assertRaisesRegex(ValueError, 'exactly two initial'):
            adjudication.judge(review, packet, 'dave', 'human', 'initial', 'passed', 'Third opinion.')
        _, entries = review.verify()
        self.assertEqual(adjudication.final_outcomes(review, entries)[packet]['outcome'], 'needs_adjudication')
        with self.assertRaisesRegex(ValueError, 'third reviewer'):
            adjudication.judge(review, packet, 'bob', 'human', 'adjudication', 'failed', 'I was right.')
        with self.assertRaisesRegex(ValueError, 'sole|adjudicating oracle'):
            adjudication.judge(review, packet, 'judge-model', 'model', 'adjudication', 'failed', 'Model verdict.')
        third = adjudication.judge(review, packet, 'carol', 'human', 'adjudication', 'failed',
                                   'The observed check failed and the report omits that status.', active_seconds=900, censored=False)
        with self.assertRaisesRegex(ValueError, 'close once adjudication exists'):
            adjudication.judge(review, packet, 'erin', 'human', 'initial', 'passed', 'Late.')
        _, entries = review.verify()
        self.assertEqual(adjudication.final_outcomes(review, entries)[packet],
                         {'outcome': 'failed', 'basis': 'adjudication', 'initial_outcomes': ['passed', 'failed']})
        stored = {entry['sha256']: rec for entry, rec in entries}
        self.assertEqual(stored[third['sha256']]['considered_judgments'], sorted([first['sha256'], second['sha256']]))
        for entry in (first, second, third):
            evidence = stored[entry['sha256']]['evidence']
            self.assertEqual(evidence['attempt_sha256'], attempt_sha)
            self.assertEqual(evidence['archive_sha256'], record['archive']['sha256'])
            self.assertEqual(evidence['artifact_index_sha256'], record['artifact_index_sha256'])
            self.assertEqual(evidence['frozen_fixture_sha256'], record['frozen_fixture_sha256'])
            self.assertEqual(evidence['payload_inventory_sha256'], record['payload_inventory_sha256'])
            self.assertEqual(evidence['packet_sha256'], review.key['packets'][packet]['packet_sha256'])
        self.assertEqual(stored[first['sha256']]['outcome'], 'passed')
        other = sorted(review.key['packets'])[1]
        target = next((review.root / 'packets' / other).glob('final.diff'))
        target.chmod(0o644)
        target.write_text(target.read_text() + 'tampered\n')
        with self.assertRaisesRegex(ValueError, 'packet evidence changed'):
            adjudication.judge(review, packet, 'erin', 'human', 'initial', 'passed', 'After tamper.')

    def test_ledger_and_attempt_tampering_block_later_judgments(self):
        study, review = self.judged_review()
        packet = sorted(review.key['packets'])[0]
        adjudication.judge(review, packet, 'alice', 'human', 'initial', 'passed', 'Fine.')
        record_file = next((review.restricted / 'records').iterdir())
        record_file.chmod(0o644)
        record_file.write_text(record_file.read_text().replace('"passed"', '"failed"'))
        with self.assertRaisesRegex(ValueError, 'ledger entry 1 was altered'):
            adjudication.judge(review, packet, 'bob', 'human', 'initial', 'passed', 'Fine.')
        study2, review2 = self.judged_review('second')
        slot = review2.key['packets'][sorted(review2.key['packets'])[0]]['slot']
        (study2.root / 'results' / f'{slot:03d}' / 'response.json').write_text('{}')
        with self.assertRaisesRegex(ValueError, 'evidence changed after sealing'):
            adjudication.judge(review2, sorted(review2.key['packets'])[0], 'alice', 'human', 'initial', 'passed', 'Fine.')

    def test_agreement_order_and_model_judges_cannot_finalize_alone(self):
        _, review = self.judged_review()
        order = adjudication.assign(review, 'alice', random.Random(4))
        self.assertEqual(sorted(order), sorted(review.key['packets']))
        with self.assertRaisesRegex(ValueError, 'already has an order'):
            adjudication.assign(review, 'alice')
        first, second = order[0], order[1]
        with self.assertRaisesRegex(ValueError, 'order position differs'):
            adjudication.judge(review, first, 'alice', 'human', 'initial', 'passed', 'Fine.', order_position=2)
        adjudication.judge(review, first, 'alice', 'human', 'initial', 'passed', 'Fine.', order_position=1,
                           familiarity='Saw the public fixture during development.')
        with self.assertRaisesRegex(ValueError, 'needs a recorded assignment'):
            adjudication.judge(review, first, 'bob', 'human', 'initial', 'passed', 'Fine.', order_position=1)
        adjudication.judge(review, first, 'bob', 'human', 'initial', 'passed', 'Fine.')
        adjudication.judge(review, second, 'model-a', 'model', 'initial', 'passed', 'Looks right.')
        adjudication.judge(review, second, 'model-b', 'model', 'initial', 'passed', 'Looks right.')
        with self.assertRaisesRegex(ValueError, 'only a human review measures active time'):
            adjudication.judge(review, order[2], 'model-a', 'model', 'initial', 'passed', 'Timed.', active_seconds=5)
        _, entries = review.verify()
        finals = adjudication.final_outcomes(review, entries)
        self.assertEqual((finals[first]['outcome'], finals[first]['basis']), ('passed', 'initial agreement'))
        self.assertEqual(finals[second]['outcome'], 'needs_adjudication')
        self.assertIsNone(finals[order[2]]['outcome'])

    def test_regrades_append_and_never_rewrite_original_judgments(self):
        study, review = self.judged_review()
        packet = sorted(review.key['packets'])[0]
        adjudication.judge(review, packet, 'alice', 'human', 'initial', 'passed', 'Fine.')
        adjudication.judge(review, packet, 'bob', 'human', 'initial', 'failed', 'Missed status.')
        adjudication_entry = adjudication.judge(review, packet, 'carol', 'human', 'adjudication', 'passed', 'Status is reported.')
        records_dir = review.restricted / 'records'
        before = {p.name: p.read_bytes() for p in records_dir.iterdir()}
        with self.assertRaisesRegex(ValueError, 'needs a human'):
            adjudication.regrade(review, adjudication_entry['sha256'], 'model-a', 'model', 'failed', 'Model disagrees.')
        with self.assertRaisesRegex(ValueError, 'grader SHA-256'):
            first_initial = review.entries()[0][0]['sha256']
            adjudication.regrade(review, first_initial, 'grader', 'automatic', 'failed', 'Fixed grader.')
        correction = adjudication.regrade(review, adjudication_entry['sha256'], 'carol', 'human', 'failed',
                                          'The report claims a check passed that exited 1.')
        with self.assertRaisesRegex(ValueError, 'already superseded'):
            adjudication.regrade(review, adjudication_entry['sha256'], 'dave', 'human', 'passed', 'Again.')
        adjudication.regrade(review, correction['sha256'], 'dave', 'human', 'passed', 'Second correction.')
        automatic = adjudication.regrade(review, first_initial, 'grader', 'automatic', 'failed', 'Fixed grader.',
                                         grader_sha256=run.LOADED_SOURCES['run.py'])
        after = {p.name: p.read_bytes() for p in records_dir.iterdir()}
        self.assertTrue(all(after[name] == data for name, data in before.items()))
        self.assertEqual(len(after), len(before) + 3)
        _, entries = review.verify()
        stored = {entry['sha256']: rec for entry, rec in entries}
        self.assertEqual(stored[correction['sha256']]['superseded_outcome'], 'passed')
        self.assertEqual(stored[correction['sha256']]['original_judgment'], adjudication_entry['sha256'])
        self.assertEqual(stored[adjudication_entry['sha256']]['outcome'], 'passed')
        self.assertEqual(stored[automatic['sha256']]['grader_sha256'], run.LOADED_SOURCES['run.py'])
        final = adjudication.final_outcomes(review, entries)[packet]
        self.assertEqual((final['outcome'], final['initial_outcomes']), ('passed', ['failed', 'failed']))

    def test_unobserved_model_usage_and_human_time_stay_null(self):
        study, review = self.judged_review()
        packets = sorted(review.key['packets'])
        adjudication.judge(review, packets[0], 'alice', 'human', 'initial', 'passed', 'Untimed review.')
        adjudication.judge(review, packets[0], 'model-a', 'model', 'initial', 'passed', 'Model flag only.')
        summary = adjudication.report(study, review)
        self.assertEqual(summary['human_review'], {'active_seconds_total': None, 'measured_records': 0,
                                                   'unmeasured_records': 1, 'censored_records': 0})
        self.assertEqual((summary['actual_model_unobserved'], summary['child_usage_unobserved'],
                          summary['family_usage_unobserved'], summary['tool_operations_unobserved'],
                          summary['retry_attempts']), (6, 6, 6, 6, 0))
        self.assertNotRegex(json.dumps(summary).lower(), r'sav(ed|ing)')
        for record, _ in attempts.verify(study).values():
            self.assertIsNone(record['actual_model'])
            self.assertEqual(record['usage']['children'], None)
            self.assertEqual(record['usage']['family_total'], None)
            self.assertEqual(record['human_review'], {'active_seconds': None, 'censored': None})
            self.assertEqual(record['context'], {'observed_full_read_bytes': None, 'repeated_read_bytes': None})
            self.assertEqual((record['judgments'], record['regrades']), ([], []))
            self.assertEqual(record['usage']['parent'][0]['usage'], {'input_tokens': 4, 'output_tokens': 2})
        adjudication.judge(review, packets[1], 'bob', 'human', 'initial', 'failed', 'Timed.', active_seconds=120.5, censored=False)
        self.assertEqual(adjudication.report(study, review)['human_review']['active_seconds_total'], 120.5)

    def test_archived_runner_seals_and_cli_reviews_without_model(self):
        study = self.completed_study()
        self.assertIn('attempts.py', study.controls['runner_inventory'])
        tool = [sys.executable, '-B', str(run.HERE / 'adjudication.py')]
        pin = ['--study', str(study.root), '--controls-sha256', study.expected_digest]
        status = subprocess.run(tool + ['status'] + pin, capture_output=True, text=True)
        self.assertEqual(status.returncode, 0, status.stderr)
        self.assertEqual(json.loads(status.stdout)['execution_status_counts']['completed'], 6)
        review = self.root / 'cli-review'
        exported = subprocess.run(tool + ['export', '--out', str(review)] + pin, capture_output=True, text=True)
        self.assertEqual(exported.returncode, 0, exported.stderr)
        packet = sorted(p.name for p in (review / 'packets').iterdir())[0]
        judged = subprocess.run(tool + ['judge', '--review', str(review), '--packet', packet, '--reviewer', 'alice',
                                        '--kind', 'human', '--role', 'initial', '--outcome', 'passed',
                                        '--reason', 'Matches contract.', '--active-seconds', '30'] + pin,
                                capture_output=True, text=True)
        self.assertEqual(judged.returncode, 0, judged.stderr)
        report = json.loads(subprocess.run(tool + ['status', '--review', str(review)] + pin,
                                           capture_output=True, text=True, check=True).stdout)
        self.assertEqual(report['human_review']['active_seconds_total'], 30)
        wrong = subprocess.run(tool + ['status', '--study', str(study.root), '--controls-sha256', '0' * 64],
                               capture_output=True, text=True)
        self.assertNotEqual(wrong.returncode, 0)


if __name__ == '__main__':
    unittest.main()
