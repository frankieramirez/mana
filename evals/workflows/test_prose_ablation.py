"""Offline prose-ablation payload, freeze and archive controls; never invoke a model."""
import difflib
import gzip
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import archive_delegated
import conditions
import prose_ablation as pa
import run

SET = pa.PAYLOAD_SET
FAKE_HOST = r'''#!/usr/bin/env python3
import json, os, pathlib, sys
args = sys.argv[1:]
if args == ['--version']:
    print(os.environ['FAKE_HOST_VERSION']); sys.exit(0)
if args[0] == 'sandbox':
    print('isolation verified'); sys.exit(0)
work = pathlib.Path(args[args.index('-C') + 1])
response = pathlib.Path(args[args.index('-o') + 1])
prompt = sys.stdin.read()
mode = os.environ['FAKE_PROSE_MODE']
skill = work / 'installed/payload/SKILL.md'
source = (work / 'notes.md').read_text()
print(json.dumps({'type': 'thread.started'}))
print(json.dumps({'type': 'item.completed', 'item': {'type': 'command_execution',
      'command': 'cat ' + str(skill), 'aggregated_output': skill.read_text(), 'exit_code': 0}}))
print(json.dumps({'type': 'item.completed', 'item': {'type': 'command_execution',
      'command': 'sed -n 1,5p installed/payload/references/archmage.md', 'aggregated_output': 'partial', 'exit_code': 0}}))
if mode == 'malformed':
    print('{not json')
print(json.dumps({'type': 'turn.completed', 'usage': {'input_tokens': 10, 'output_tokens': 4}}))
if mode == 'edit':
    (work / 'notes.md').write_text('candidate overwrote the source\n')
rewrite = source if mode != 'drop' else 'The import retries, then stops.'
response.write_text(json.dumps({'rewrite': rewrite}))
'''

SOURCE = ('So basically the importer will retry, which is honestly pretty great.\n\n'
          '```ini\nretry_limit = 3\n```\n\nIt stops after that. Nobody wrote down why.\n')
SPAN = '```ini\nretry_limit = 3\n```'


def entry(arm, root=SET):
    return pa.read_text(root / 'payloads' / arm / pa.ENTRYPOINT)


def base_manifest():
    _, set_digest = pa.load_payload_set()
    return {
        'version': 1, 'study': 'offline-prose', 'host': run.SUPPORTED_HOST, 'model': 'gpt-6.1-sol',
        'reasoning': 'medium', 'seed': 20261017, 'repetitions': 2,
        'payload_set': str(SET), 'payload_set_sha256': set_digest,
        'cases': [{'id': 'synthetic-retry-note', 'source_group': 'synthetic-retry', 'split': 'development',
                   'request': 'Rewrite notes.md as a short Slack update.',
                   'sources': {'notes.md': SOURCE},
                   'protected_spans': [{'id': 'retry-config', 'file': 'notes.md', 'text': SPAN}],
                   'timeout_seconds': 60}]}


class PayloadTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.record = json.loads((SET / 'payloads.json').read_text())

    def test_frozen_set_verifies_and_is_evaluation_only(self):
        report = pa.verify_payload_set()
        self.assertEqual(tuple(report['arms']), pa.ARMS)
        self.assertEqual(report['baseline_revision'], pa.BASELINE_REVISION)
        self.assertFalse(report['agent_executed'])
        self.assertTrue(self.record['evaluation_only'])
        for arm in pa.ARMS:
            files = conditions.inventory(SET / 'payloads' / arm)
            self.assertEqual(set(files), {'SKILL.md', 'references/archmage.md'})
            self.assertEqual(conditions.digest(conditions.encoded(files)), self.record['arms'][arm]['inventory_sha256'])

    def test_only_the_selected_blocks_differ(self):
        current = entry('current-fidelity')
        regions = pa.selected_regions(current)
        allowed = set(range(*regions['fidelity_section'])) | set(range(*regions['self_check_item_9']))
        lines = current.splitlines(keepends=True)
        for arm in pa.CHANGED_ARMS:
            changed = entry(arm).splitlines(keepends=True)
            matcher = difflib.SequenceMatcher(a=lines, b=changed, autojunk=False)
            touched = set()
            for tag, a1, a2, _, _ in matcher.get_opcodes():
                if tag != 'equal':
                    touched |= set(range(a1, a2))
            self.assertTrue(touched)
            self.assertLessEqual(touched, allowed, arm)
            start, end = regions['fidelity_section']
            item = regions['self_check_item_9'][0]
            middle, tail = lines[end:item], lines[item + 1:]
            self.assertEqual(changed[:start], lines[:start], arm)
            self.assertEqual(changed[len(changed) - len(tail):], tail, arm)
            self.assertEqual(changed[len(changed) - len(tail) - len(middle):len(changed) - len(tail)], middle, arm)
            self.assertEqual((SET / 'payloads' / arm / 'references/archmage.md').read_bytes(),
                             (SET / 'payloads/current-fidelity/references/archmage.md').read_bytes())
        # Unrelated restrictions and self-check items 1..8 stay fixed in every arm.
        fixed = [line for line in lines if line.startswith(('1. ', '2. ', '3. ', '4. ', '5. ', '6. ', '7. ', '8. '))]
        self.assertEqual(len(fixed), 8)
        for arm in pa.ARMS:
            text = entry(arm)
            for line in fixed + ['Preserve exempt text exactly.', 'Name the mechanism or the number when the source gives you one.',
                                 'Fix what you find, then return the prose.', '<!-- BEGIN MANA PERSONA -->',
                                 'Honor explicit user instructions']:
                self.assertIn(line, text, arm)
        self.assertEqual(entry('scope-fidelity').count(pa.CANDIDATE), 1)
        self.assertIn('## Fidelity\n\n' + pa.CANDIDATE + '\n\n## Positive rules', entry('scope-fidelity'))
        self.assertNotIn('## Fidelity', entry('section-removed'))
        for arm in pa.CHANGED_ARMS:
            self.assertNotIn('\n9. ', entry(arm))
            self.assertNotIn('A missing reason stays missing.', entry(arm))
        self.assertNotIn(pa.CANDIDATE, entry('current-fidelity'))
        self.assertNotIn(pa.CANDIDATE, entry('section-removed'))

    def test_stored_patches_apply_exactly_to_the_current_payload(self):
        for arm in pa.CHANGED_ARMS:
            work = self.root / arm
            shutil.copytree(SET / 'payloads/current-fidelity', work)
            subprocess.run(['git', 'apply', str(SET / 'patches' / (arm + '.patch'))],
                           cwd=work, check=True, capture_output=True)
            self.assertEqual(conditions.inventory(work), self.record['arms'][arm]['inventory'])
            self.assertEqual(conditions.digest((SET / 'patches' / (arm + '.patch')).read_bytes()),
                             self.record['arms'][arm]['patch_sha256'])
        self.assertIsNone(self.record['arms']['current-fidelity']['patch'])

    def test_current_payload_is_the_audit_baseline(self):
        self.assertEqual(self.record['arms']['current-fidelity']['inventory'], self.record['source_inventory'])
        self.assertEqual(self.record['source_path'], 'skills/dispel')
        probe = subprocess.run(['git', '-C', str(run.ROOT), 'cat-file', '-e', pa.BASELINE_REVISION + ':skills/dispel/SKILL.md'],
                               capture_output=True)
        if probe.returncode:
            self.skipTest('audit baseline object is unavailable in this shallow checkout')
        for name in ('SKILL.md', 'references/archmage.md'):
            blob = subprocess.check_output(['git', '-C', str(run.ROOT), 'show', pa.BASELINE_REVISION + ':skills/dispel/' + name])
            self.assertEqual(blob, (SET / 'payloads/current-fidelity' / name).read_bytes(), name)

    def test_builder_reproduces_the_frozen_set_and_never_writes_production(self):
        before = conditions.inventory(run.ROOT / 'skills')
        rebuilt = self.root / 'rebuilt'
        pa.build_payloads(SET / 'payloads/current-fidelity', rebuilt)
        self.assertEqual(conditions.inventory(rebuilt), conditions.inventory(SET))
        for target in (run.ROOT / 'skills' / 'dispel-experiment', run.ROOT / 'agents' / 'x'):
            with self.assertRaisesRegex(ValueError, 'cannot be written under'):
                pa.build_payloads(SET / 'payloads/current-fidelity', target)
            self.assertFalse(target.exists())
        self.assertEqual(conditions.inventory(run.ROOT / 'skills'), before)

    def test_production_instructions_do_not_reference_experimental_payloads(self):
        markers = ('prose-ablation', 'scope-fidelity', 'section-removed', 'Removing filler must preserve a qualified claim')
        for base in ('skills', 'agents', 'output-styles'):
            for path in (run.ROOT / base).rglob('*'):
                if path.is_file():
                    text = path.read_bytes().decode('utf-8', 'replace')
                    for marker in markers:
                        self.assertNotIn(marker, text, str(path))

    def test_ambiguous_sources_and_tampering_fail_closed(self):
        current = entry('current-fidelity')
        for broken in (current.replace('## Fidelity\n', ''), current + '## Fidelity\n',
                       current.replace('\n9. ', '\n10. '), current + '10. Extra item.\n', current.rstrip('\n')):
            with self.assertRaises(ValueError):
                pa.derive(broken)
        for relative, data in (('payloads/scope-fidelity/SKILL.md', b'tampered\n'),
                               ('payloads/section-removed/references/archmage.md', b'tampered\n'),
                               ('patches/section-removed.patch', b'--- a/SKILL.md\n')):
            copy = self.root / ('set-' + relative.replace('/', '-'))
            shutil.copytree(SET, copy)
            (copy / relative).write_bytes(data)
            with self.assertRaises(ValueError):
                pa.verify_payload_set(copy)
        # A consistent re-hash of a wrong arm still fails because the arm is rederived.
        copy = self.root / 'rehashed'
        shutil.copytree(SET, copy)
        target = copy / 'payloads/scope-fidelity/SKILL.md'
        target.write_bytes(target.read_bytes().replace(b'Before returning, compare', b'Afterwards, compare'))
        record = json.loads((copy / 'payloads.json').read_text())
        record['arms']['scope-fidelity']['inventory'] = conditions.inventory(target.parent)
        record['arms']['scope-fidelity']['inventory_sha256'] = conditions.inventory_digest(target.parent)
        (copy / 'payloads.json').write_bytes(conditions.encoded(record))
        with self.assertRaisesRegex(ValueError, 'exact derived payload'):
            pa.verify_payload_set(copy)


class StudyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.manifest = base_manifest()

    def freeze(self, name='study', manifest=None):
        path = self.root / (name + '.json')
        path.write_text(json.dumps(manifest or self.manifest))
        result = pa.freeze_study(path, self.root / name)
        return pa.ProseStudy(self.root / name, result['controls_sha256'], pa.LOADED_SOURCES, pa.HERE), result

    def test_freeze_pins_three_arms_and_a_seeded_schedule(self):
        study, result = self.freeze()
        self.assertEqual(result['parent_slots'], 6)
        self.assertFalse(result['agent_executed'])
        self.assertEqual(sorted((c['condition'], c['repetition']) for c in study.schedule),
                         sorted((a, r) for a in pa.ARMS for r in (1, 2)))
        again, _ = self.freeze('again')
        self.assertEqual(study.schedule, again.schedule)
        self.assertEqual(study.controls['payload_set_sha256'], self.manifest['payload_set_sha256'])
        for arm in pa.ARMS:
            self.assertEqual(study.controls['conditions'][arm]['inventory'],
                             json.loads((SET / 'payloads.json').read_text())['arms'][arm]['inventory'])
        case = study.controls['cases'][0]
        self.assertEqual(case['protected_spans'][0]['sha256'], conditions.digest(SPAN.encode()))
        self.assertNotIn('expected', json.dumps(case))
        shifted = json.loads(json.dumps(self.manifest))
        shifted['seed'] = 7
        other, _ = self.freeze('seeded', shifted)
        self.assertEqual(len(other.schedule), 6)

    def test_arms_share_every_control_except_the_payload(self):
        study, _ = self.freeze()
        prompts, states = {}, []
        for arm in pa.ARMS:
            slot = next(c['slot'] for c in study.schedule if c['condition'] == arm)
            cell, case, condition = study.selection(slot)
            out = self.root / f'{slot:03d}'
            out.mkdir()
            study.snapshot(out, case, condition)
            work, baseline = pa.prepare_workspace(out / 'raw-source', out, condition)
            states.append((baseline['product_state'], baseline['head']))
            self.assertEqual(conditions.inventory(work / 'installed/payload'), condition['inventory'])
            self.assertEqual((out / 'raw-source/notes.md').read_text(), SOURCE)
            self.assertEqual(json.loads((out / 'protected-spans.json').read_text())[0]['text'], SPAN)
            prompt = pa.prose_prompt(case, work)
            self.assertNotIn('synthetic-retry', prompt)
            self.assertNotIn('retry-config', prompt)
            self.assertNotIn(arm, prompt)
            prompts[arm] = prompt.replace(str(work), '<work>')
        self.assertEqual(len(set(prompts.values())), 1)
        self.assertEqual(len({json.dumps(s, sort_keys=True) for s in states}), 1)
        self.assertNotIn('conditions', study.controls['shared_controls'])
        self.assertEqual(study.controls['shared_controls']['deterministic_checks'], list(pa.DETERMINISTIC_CHECKS))

    def test_invalid_manifests_fail_closed(self):
        mutations = [
            lambda m: m.update(payload_set_sha256='0' * 64),
            lambda m: m.update(host='codex-cli unvalidated'),
            lambda m: m.update(repetitions=4),
            lambda m: m.update(payload_set='relative/path'),
            lambda m: m['cases'][0].update(split='heldout'),
            lambda m: m['cases'][0].update(sources={'../escape.md': 'x'}),
            lambda m: m['cases'][0].update(sources={'installed/SKILL.md': 'x'}),
            lambda m: m['cases'][0]['protected_spans'][0].update(text='retry_limit = 4'),
            lambda m: m['cases'][0]['protected_spans'][0].update(file='other.md'),
            lambda m: m['cases'][0].update(timeout_seconds=301),
            lambda m: m['cases'][0].update(expected='invented'),
            lambda m: m.update(cases=[dict(m['cases'][0], id=f'case-{i}') for i in range(13)]),
        ]
        for index, mutate in enumerate(mutations):
            manifest = json.loads(json.dumps(self.manifest))
            mutate(manifest)
            path = self.root / f'bad-{index}.json'
            path.write_text(json.dumps(manifest))
            with self.assertRaises(ValueError, msg=str(index)):
                pa.freeze_study(path, self.root / f'bad-{index}')
            self.assertFalse((self.root / f'bad-{index}').exists())

    def test_external_pin_detects_changed_inputs(self):
        study, result = self.freeze()
        with self.assertRaises(ValueError):
            pa.ProseStudy(study.root, '0' * 64)
        for relative in ('payloads/section-removed/SKILL.md', 'sources/synthetic-retry-note/notes.md',
                         'patches/scope-fidelity.patch'):
            target = study.root / relative
            target.parent.chmod(0o755)
            target.chmod(0o644)
            original = target.read_bytes()
            target.write_bytes(original + b'changed\n')
            with self.assertRaisesRegex(ValueError, 'changed'):
                pa.ProseStudy(study.root, result['controls_sha256'])
            target.write_bytes(original)
        pa.ProseStudy(study.root, result['controls_sha256'])

    def test_cli_check_never_runs_a_model_and_rejects_ambiguous_modes(self):
        study, result = self.freeze()
        with patch.object(pa, 'execute_slot', side_effect=AssertionError('model path')), \
                patch('builtins.print'), patch.object(pa.sys, 'stderr'):
            self.assertEqual(pa.main(['--study', str(study.root), '--controls-sha256', result['controls_sha256'], '--check']), 0)
            self.assertEqual(pa.main(['--study', str(study.root), '--controls-sha256', result['controls_sha256'],
                                      '--check', '--live', '--slot', '1']), 2)
            self.assertEqual(pa.main(['--study', str(study.root), '--controls-sha256', result['controls_sha256'], '--live']), 2)
        self.assertEqual(pa.main(['--check-payloads']), 0)


class ExecutionTests(unittest.TestCase):
    """A fake host stands in for Codex so the archive path runs with no model."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        bindir = self.root / 'fake-bin'
        bindir.mkdir()
        (bindir / 'codex').write_text(FAKE_HOST)
        (bindir / 'codex').chmod(0o755)
        self.env = {'PATH': str(bindir) + os.pathsep + os.environ.get('PATH', '/usr/bin:/bin'),
                    'FAKE_HOST_VERSION': run.SUPPORTED_HOST}
        self.manifest = base_manifest()
        path = self.root / 'manifest.json'
        path.write_text(json.dumps(self.manifest))
        result = pa.freeze_study(path, self.root / 'study')
        self.study = pa.ProseStudy(self.root / 'study', result['controls_sha256'], pa.LOADED_SOURCES, pa.HERE)

    def execute(self, slot, mode):
        with patch.dict(os.environ, dict(self.env, FAKE_PROSE_MODE=mode)), \
                patch('builtins.print'):
            code = pa.execute_slot(self.study, slot)
        out = self.study.root / 'results' / f'{slot:03d}'
        return code, out, json.loads((out / 'evaluation.json').read_text()), json.loads((out / 'result.json').read_text())

    def test_archive_keeps_raw_source_spans_final_output_and_instruction_reads(self):
        code, out, evaluation, result = self.execute(1, 'keep')
        self.assertEqual(code, 0, result)
        self.assertEqual(evaluation['execution_status'], 'completed')
        self.assertEqual(evaluation['task_outcome'], 'passed-deterministic')
        self.assertEqual((out / 'raw-source/notes.md').read_text(), SOURCE)
        self.assertEqual((out / 'final-output.md').read_text(), SOURCE)
        self.assertEqual(json.loads((out / 'protected-spans.json').read_text())[0]['text'], SPAN)
        reads = json.loads((out / 'instruction-reads.json').read_text())
        self.assertEqual(reads['full_reads'], {'SKILL.md': 1})
        self.assertEqual(reads['commands_naming_file'], {'SKILL.md': [1], 'references/archmage.md': [2]})
        self.assertEqual(reads['unobserved_files'], [])
        self.assertEqual(evaluation['condition'], self.study.schedule[0]['condition'])
        self.assertEqual(conditions.inventory(out / 'payload-source'), self.study.controls['conditions'][evaluation['condition']]['inventory'])
        self.assertIsNone(evaluation['actual_model'])
        self.assertEqual(evaluation['fidelity_review'], {'reviewers': [], 'adjudication': None, 'active_seconds': None})
        archive = gzip.decompress((out.with_suffix('.json.gz')).read_bytes())
        files = json.loads(archive)['files']
        for name in ('raw-source/notes.md', 'protected-spans.json', 'final-output.md', 'instruction-reads.json',
                     'events.jsonl', 'prompt.txt', 'response.json', 'payload-source/SKILL.md', 'evaluation.json'):
            self.assertIn(name, files)
        self.assertFalse(any(name.startswith('workspace/installed') for name in files))
        self.assertEqual(archive_delegated.verify(out.with_suffix('.json.gz'))['verified_files'], len(files))
        self.assertFalse((self.study.root / 'results/STOP.json').exists())

    def test_lost_span_and_edited_source_are_outcomes_not_harness_stops(self):
        _, _, first, _ = self.execute(1, 'drop')
        self.assertEqual(first['execution_status'], 'completed')
        self.assertEqual(first['task_outcome'], 'failed')
        self.assertEqual(first['deterministic_checks']['failures'], ['protected span lost: retry-config'])
        self.assertFalse((self.study.root / 'results/STOP.json').exists())
        _, _, second, _ = self.execute(2, 'edit')
        self.assertIn('source file changed: notes.md', second['deterministic_checks']['failures'])
        self.assertIn('workspace changed outside artifacts/', second['deterministic_checks']['failures'])
        with self.assertRaises(FileExistsError):
            self.study.claim(2)

    def test_malformed_events_and_wrong_host_stop_the_schedule(self):
        _, out, evaluation, result = self.execute(1, 'malformed')
        self.assertEqual(evaluation['execution_status'], 'collection_failed')
        self.assertIsNone(evaluation['task_outcome'])
        self.assertTrue((out / 'events.jsonl').read_text())
        self.assertTrue((self.study.root / 'results/STOP.json').exists())
        with self.assertRaisesRegex(ValueError, 'study stopped'):
            self.study.claim(2)

    def test_unvalidated_host_preserves_attempt_without_launch(self):
        self.env['FAKE_HOST_VERSION'] = 'codex-cli unvalidated'
        _, out, evaluation, result = self.execute(1, 'keep')
        self.assertEqual(evaluation['execution_status'], 'setup_failed')
        self.assertFalse((out / 'events.jsonl').exists())
        self.assertTrue((out / 'raw-source/notes.md').is_file())
        self.assertTrue((self.study.root / 'results/STOP.json').exists())


if __name__ == '__main__':
    unittest.main()
