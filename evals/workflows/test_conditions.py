"""Offline condition isolation, freeze and oracle controls; never invoke a model."""
import base64
import copy
import gzip
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import archive_delegated
import conditions
import run


def event(command='cat report.md', output='Completed review.', code=0):
    return {'type': 'item.completed', 'item': {'type': 'command_execution',
            'command': command, 'aggregated_output': output, 'exit_code': code}}


class ConditionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.cases = run.load_cases()
        self.manifest = {
            'version': 1, 'study': 'offline-controls', 'host': run.SUPPORTED_HOST,
            'model': 'gpt-6.1-sol', 'reasoning': 'medium', 'seed': 20261017,
            'repetitions': 2, 'conditions': {'none': {}}, 'cases': [{
                'id': 'review-report-only', 'source_group': 'public-review-action',
                'split': 'development', 'request': 'Read report.md and report its findings. Leave the project unchanged.',
                'timeout_seconds': 120}]}
        for kind in ('mana', 'reference'):
            payload = self.root / kind
            payload.mkdir()
            entry = 'SKILL.md' if kind == 'mana' else 'workflows/review.md'
            path = payload / entry
            path.parent.mkdir(exist_ok=True)
            path.write_text(kind.upper() + ' ONLY INSTRUCTIONS\n')
            (payload / 'asset.bin').write_bytes(b'\x00\xff\xfe')
            (payload / 'helper').write_text('#!/bin/sh\nexit 0\n')
            (payload / 'helper').chmod(0o755)
            self.manifest['conditions'][kind] = {
                'root': str(payload), 'revision': ('a' if kind == 'mana' else 'b') * 40,
                'inventory_sha256': conditions.inventory_digest(payload),
                'entrypoints': {'review-report-only': entry}}

    def freeze(self, name='study', manifest=None):
        path = self.root / (name + '.json')
        path.write_text(json.dumps(manifest or self.manifest))
        result = conditions.freeze(path, self.root / name, self.cases, run.HERE,
                                   run.STUDY_SOURCES, run.SUPPORTED_HOSTS, run.prepare)
        study = conditions.FrozenStudy(self.root / name, result['controls_sha256'], run.STUDY_SOURCES, run.HERE)
        return study, result

    def test_separate_payloads_and_none_receive_only_ordinary_request(self):
        study, _ = self.freeze()
        prompts = {}
        product_states = []
        for kind in conditions.KINDS:
            cell = next(c for c in study.schedule if c['condition'] == kind)
            _, frozen, condition = study.selection(cell['slot'])
            out = self.root / ('run-' + kind)
            out.mkdir()
            work, baseline = run.prepare(frozen['definition'], out, condition=condition)
            product_states.append(baseline['product_state'])
            installed = conditions.inventory(work / 'installed')
            self.assertEqual(installed, baseline['installed_inventory'])
            self.assertFalse((work / 'installed/scan').exists())
            self.assertFalse((work / 'controls.json').exists())
            self.assertFalse((work / 'runner-source').exists())
            prompt = conditions.prompt(frozen['definition'], work, condition)
            self.assertNotIn('Stage 6', prompt)
            self.assertNotIn('public-review-action', prompt)
            self.assertNotIn('expected_status', prompt)
            if kind == 'none':
                self.assertEqual(installed, {})
                self.assertNotIn('Use the instructions at', prompt)
                prompts[kind] = prompt
            else:
                self.assertEqual(conditions.inventory(work / 'installed/payload'), condition['inventory'])
                self.assertEqual((work / 'installed/payload' / condition['entrypoint']).read_text(), kind.upper() + ' ONLY INSTRUCTIONS\n')
                self.assertNotIn(('REFERENCE' if kind == 'mana' else 'MANA') + ' ONLY', '\n'.join(
                    p.read_text(errors='replace') for p in (work / 'installed').rglob('*') if p.is_file()))
                prompts[kind] = prompt.split('\n', 1)[1]
        self.assertEqual(prompts['mana'], prompts['reference'])
        self.assertEqual(prompts['mana'], prompts['none'])
        self.assertEqual(product_states[0], product_states[1])
        self.assertEqual(product_states[0], product_states[2])

    def test_known_good_and_harmful_edit_oracles_work_in_every_condition(self):
        study, _ = self.freeze()
        for kind in conditions.KINDS:
            cell = next(c for c in study.schedule if c['condition'] == kind)
            _, frozen, condition = study.selection(cell['slot'])
            out = self.root / ('oracle-' + kind)
            out.mkdir()
            case = frozen['definition']
            work, baseline = run.prepare(case, out, condition=condition)
            response = {'report': 'The confirmed finding is app.txt contains old.', 'checks': []}
            self.assertEqual(run.grade(case, work, baseline, response, [event()]), [])
            (work / 'app.txt').write_text('harmful change\n')
            self.assertTrue(any('out-of-scope' in f for f in run.grade(case, work, baseline, response, [event()])))
            (work / 'app.txt').write_text('old\n')
            (work / 'installed').chmod(0o755)
            (work / 'installed/hidden.md').write_text('unexpected instructions')
            self.assertIn('installed condition payload changed', run.grade(case, work, baseline, response, [event()]))

    def test_invalid_payload_and_unavailable_case_fail_closed(self):
        mutations = [
            lambda m: m['conditions']['mana'].update(inventory_sha256='0' * 64),
            lambda m: m['conditions']['reference']['entrypoints'].update({'review-report-only': 'missing.md'}),
            lambda m: m['conditions']['none'].update(root='/tmp/hidden'),
            lambda m: m.update(host='codex-cli unvalidated'),
            lambda m: m['cases'][0].update(id='full-feedback-judgment'),
            lambda m: m['cases'][0].update(split='heldout'),
        ]
        for index, mutate in enumerate(mutations):
            with self.subTest(index=index):
                manifest = copy.deepcopy(self.manifest)
                mutate(manifest)
                with self.assertRaises(ValueError):
                    self.freeze('invalid-' + str(index), manifest)
                self.assertFalse((self.root / ('invalid-' + str(index))).exists())
        (self.root / 'mana/link').symlink_to(self.root / 'reference/SKILL.md')
        with self.assertRaises(ValueError):
            conditions.inventory(self.root / 'mana')

    def test_deterministic_schedule_and_external_pin_detect_mutation(self):
        first, result = self.freeze()
        second, second_result = self.freeze('second')
        self.assertEqual(first.schedule, second.schedule)
        self.assertEqual(result['controls_sha256'], second_result['controls_sha256'])
        self.assertEqual(result['parent_slots'], 6)
        with self.assertRaises(ValueError):
            conditions.FrozenStudy(first.root, '0' * 64)
        for index, relative in enumerate(('schedule.json', 'controls.json', 'payloads/mana/SKILL.md', 'runner-source/run.py')):
            study, _ = self.freeze('mutation-' + str(index))
            path = study.root / relative
            path.chmod(0o644)
            path.write_bytes(path.read_bytes() + b'\n')
            with self.assertRaises(ValueError):
                study.verify()
        (second.root / 'payloads/reference').chmod(0o755)
        (second.root / 'payloads/reference/added').write_text('unexpected')
        with self.assertRaises(ValueError):
            second.verify()

    def test_schedule_rejects_parallel_out_of_order_and_repeat_slots(self):
        study, _ = self.freeze()
        with self.assertRaises(ValueError):
            study.claim(2)
        out = study.claim(1)
        with self.assertRaises(FileExistsError):
            study.claim(1)
        (out / 'result.json').write_text('{}')
        study.release()
        with self.assertRaises(FileExistsError):
            study.claim(1)
        study.claim(2)
        study.release()

    def test_verification_parses_the_pinned_bytes_when_file_changes_after_read(self):
        for name, error in (('controls.json', 'frozen controls changed'),
                            ('schedule.json', 'frozen schedule changed')):
            with self.subTest(name=name):
                study, _ = self.freeze('read-race-' + name.split('.')[0])
                expected_cell, expected_case, _ = copy.deepcopy(study.selection(1))
                target = study.root / name
                replacement = json.loads(target.read_bytes())
                if name == 'controls.json':
                    replacement['cases'][0]['definition']['request'] = 'Unpinned replacement request.'
                else:
                    replacement[0]['condition'] = 'none' if expected_cell['condition'] != 'none' else 'mana'
                target.chmod(0o644)
                original_read_bytes = Path.read_bytes
                changed = False

                def read_then_change(path):
                    nonlocal changed
                    data = original_read_bytes(path)
                    if path == target and not changed:
                        target.write_bytes(conditions.encoded(replacement))
                        changed = True
                    return data

                with patch.object(Path, 'read_bytes', read_then_change):
                    study.verify()
                self.assertTrue(changed)
                cell, case, _ = study.selection(1)
                self.assertEqual(cell, expected_cell)
                self.assertEqual(case, expected_case)
                with self.assertRaisesRegex(ValueError, error):
                    study.verify()

    def test_verification_rejects_symlinked_controls_and_schedule(self):
        for name, error in (('controls.json', 'frozen controls changed'),
                            ('schedule.json', 'frozen schedule changed')):
            with self.subTest(name=name):
                study, _ = self.freeze('symlink-' + name.split('.')[0])
                target = study.root / name
                replacement = self.root / name
                replacement.write_bytes(target.read_bytes())
                target.unlink()
                target.symlink_to(replacement)
                with self.assertRaisesRegex(ValueError, error):
                    study.verify()

    def test_stale_fixture_bytes_and_git_identity_are_frozen_across_conditions(self):
        manifest = copy.deepcopy(self.manifest)
        manifest['cases'][0].update(id='stale-evidence', source_group='public-stale',
                                    request='Assess prior-evidence.md against the current app.txt and check.sh.')
        for kind in ('mana', 'reference'):
            entry = manifest['conditions'][kind]['entrypoints'].pop('review-report-only')
            manifest['conditions'][kind]['entrypoints']['stale-evidence'] = entry
        study, _ = self.freeze(manifest=manifest)
        expected = study.controls['cases'][0]
        for kind in conditions.KINDS:
            slot = next(c['slot'] for c in study.schedule if c['condition'] == kind)
            _, frozen, condition = study.selection(slot)
            out = self.root / ('stale-' + kind)
            out.mkdir()
            work, baseline = run.prepare(frozen['definition'], out, condition=condition)
            self.assertEqual({k: baseline[k] for k in conditions.INITIAL_FIELDS}, expected['initial_state'])
            self.assertEqual(run.git(work, 'show', '-s', '--format=%at'), '946684800')
            self.assertEqual((work / 'prior-evidence.md').read_bytes(),
                             (study.root / 'fixture-source/stale-evidence/initial-fixture/prior-evidence.md').read_bytes())

    def test_prepared_fixture_drift_stops_before_containment_or_model(self):
        study, _ = self.freeze()
        _, frozen, condition = study.selection(1)
        original_check_output = run.subprocess.check_output
        original_prepare = run.prepare
        def host_or_git(command, *args, **kwargs):
            if command[-1] == '--version':
                return run.SUPPORTED_HOST + '\n'
            return original_check_output(command, *args, **kwargs)
        def wrong_fixture(*args, **kwargs):
            work, baseline = original_prepare(*args, **kwargs)
            (work / 'app.txt').write_text('unexpected fixture drift\n')
            return work, baseline
        out = self.root / 'drift'
        out.mkdir()
        with patch.object(run.shutil, 'which', return_value='/usr/bin/true'), \
                patch.object(run.subprocess, 'check_output', side_effect=host_or_git), \
                patch.object(run, 'prepare', side_effect=wrong_fixture), \
                patch.object(run, 'preflight') as preflight:
            result = run.execute(frozen['definition'], out, 120, condition=condition, frozen_study=study)
        preflight.assert_not_called()
        self.assertEqual(result['execution'], 'setup_failed')
        self.assertIn('prepared fixture differs from frozen inputs', result['failures'])

    def test_active_sources_and_copy_races_rejected(self):
        study, _ = self.freeze()
        sources = self.root / 'sources'
        shutil.copytree(study.root / 'runner-source', sources)
        (sources / 'response-schema.json').chmod(0o644)
        (sources / 'response-schema.json').write_text('{}')
        with self.assertRaises(ValueError):
            conditions.FrozenStudy(study.root, study.expected_digest, run.STUDY_SOURCES, sources)
        path = self.root / 'manifest.json'
        path.write_text(json.dumps(self.manifest))
        with self.assertRaises(ValueError):
            conditions.freeze(path, self.root / 'race', self.cases, sources, run.STUDY_SOURCES, run.SUPPORTED_HOSTS, run.prepare)

    def test_archive_retains_actual_binary_payload_and_original_text_format(self):
        study, _ = self.freeze()
        _, _, condition = study.selection(next(c['slot'] for c in study.schedule if c['condition'] == 'reference'))
        out = self.root / 'archived'
        out.mkdir()
        study.snapshot(out, condition)
        target = self.root / 'archive.json.gz'
        record = archive_delegated.archive(out, target)
        self.assertEqual(archive_delegated.verify(target)['verified_files'], record['files'])
        content = json.loads(gzip.decompress(target.read_bytes()))['files']
        self.assertEqual(base64.b64decode(content['payload-source/asset.bin']['base64']), b'\x00\xff\xfe')
        self.assertEqual(content['payload-source/workflows/review.md']['text'], 'REFERENCE ONLY INSTRUCTIONS\n')
        self.assertIn('runner-source/conditions.py', content)
        self.assertIn('schedule.json', content)

    def test_frozen_cli_check_and_override_rejection_never_run_model(self):
        study, _ = self.freeze()
        command = [sys.executable, '-B', str(study.root / 'runner-source/run.py'), '--study', str(study.root),
                   '--controls-sha256', study.expected_digest, '--check']
        result = subprocess.run(command, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(json.loads(result.stdout)['agent_executed'])
        result = subprocess.run(command + ['--model=other-model'], capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('cannot combine', result.stderr)

    def test_unsupported_host_preserves_attempt_and_stops_without_model(self):
        study, _ = self.freeze()
        with patch.object(run.shutil, 'which', return_value='/usr/bin/true'), \
                patch.object(run.subprocess, 'check_output', return_value='codex-cli unvalidated\n'), \
                patch.object(run.subprocess, 'Popen') as model:
            self.assertEqual(run.execute_study(study, 1), 1)
            model.assert_not_called()
        out = study.root / 'results/001'
        result = json.loads((out / 'result.json').read_text())
        self.assertEqual(result['execution'], 'setup_failed')
        self.assertIsNone(json.loads((out / 'evaluation.json').read_text())['task_outcome'])
        self.assertTrue(out.with_suffix('.json.gz').is_file())
        with self.assertRaises(ValueError):
            study.claim(2)

    def test_malformed_events_cannot_be_hidden_by_valid_command_and_usage(self):
        valid = [event(), {'type': 'turn.completed', 'usage': {'input_tokens': 4, 'output_tokens': 2}}]
        for invalid in ('{}', 'null', '{broken', '{"type":"item.completed","item":null}',
                        '{"type":"turn.completed","usage":null}'):
            with self.subTest(invalid=invalid):
                parsed, failures = conditions.parse_events(invalid + '\n' + '\n'.join(map(json.dumps, valid)))
                self.assertEqual(parsed, valid)
                self.assertTrue(failures)
        self.assertEqual(conditions.parse_events('\n'.join(map(json.dumps, valid))), (valid, []))

    def test_collection_failure_stops_schedule_and_preserves_raw_events(self):
        study, _ = self.freeze()
        def fake_execute(case, out, *args, **kwargs):
            (out / 'events.jsonl').write_text('null\n')
            return {'case': case['id'], 'execution': 'collection_failed', 'passed': False,
                    'failures': ['invalid event at line 1'], 'live': False}
        with patch.object(run, 'execute', side_effect=fake_execute):
            self.assertEqual(run.execute_study(study, 1), 1)
        self.assertTrue((study.root / 'results/STOP.json').is_file())
        self.assertEqual((study.root / 'results/001/events.jsonl').read_text(), 'null\n')
        self.assertIsNone(json.loads((study.root / 'results/001/evaluation.json').read_text())['task_outcome'])


if __name__ == '__main__':
    unittest.main()
