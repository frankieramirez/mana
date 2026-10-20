"""Paired integration freeze, offline against a synthetic consumer. No model is invoked."""
import contextlib
import io
import json
import os
from pathlib import Path
import stat
import subprocess
import tempfile
import unittest

import conditions
import integration

HOST = 'codex-cli 0.163.0'
CONTROL_LINE = 'Control: .agents/skills/briefing-control/SKILL.md\n'
SOURCE = "export function briefing(workers) {\n  return workers.length ? 'Welcome back' : 'No activity';\n}\n"
SECRET_REQUEST = 'came back and the briefing is empty ??? zz-private-marker'


def git(root, *args):
    return subprocess.run(['git', '-C', str(root), *args], check=True, capture_output=True, text=True,
                          env=integration.git_env()).stdout.strip()


def write(root, name, text):
    path = Path(root) / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    return path


def patch(tree, name, old, new):
    """A unified diff produced the way a person would, with the operator's Git config ignored."""
    work = Path(tempfile.mkdtemp(dir=tree.parent))
    write(work, name, old)
    git(work, 'init', '-q')
    git(work, 'add', '-A')
    write(work, name, new)
    return git(work, 'diff') + '\n'


class Freeze(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix='mana-integration-')
        self.addCleanup(temp.cleanup)
        self.base = Path(temp.name)
        self.consumer = self.base / 'consumer'
        files = {
            'AGENTS.md': '# Agents\n\nRead the docs first.\n' + CONTROL_LINE + 'Keep the hosted product current.\n',
            '.agents/skills/briefing-control/SKILL.md': '---\nname: briefing-control\n---\nCommand: node verify.mjs\n',
            'verification/features/briefing.json': '{"id": "briefing"}\n',
            'verify.mjs': 'process.exit(0)\n',
            'src/briefing.mjs': SOURCE,
            'package.json': '{"name": "consumer"}\n',
        }
        for name, text in files.items():
            write(self.consumer, name, text)
        (self.consumer / 'verify.mjs').chmod(0o755)
        git(self.consumer, 'init', '-q', '-b', 'main')
        git(self.consumer, 'add', '-A')
        git(self.consumer, 'commit', '-qm', 'pinned')
        self.revision = git(self.consumer, 'rev-parse', 'HEAD')
        write(self.consumer, 'src/briefing.mjs', SOURCE + '// uncommitted operator work\n')
        self.payload = self.base / 'payload'
        for skill in ('sift', 'cast', 'scan'):
            write(self.payload, skill + '/SKILL.md', '---\nname: %s\n---\nBody.\n' % skill)
        self.inputs = self.base / 'inputs'
        defect = write(self.inputs, 'defect.patch', patch(self.base, 'src/briefing.mjs', SOURCE,
                                                          SOURCE.replace("'Welcome back'", "''")))
        claim = write(self.inputs, 'claim.patch', patch(self.base, 'src/briefing.mjs', SOURCE,
                                                        SOURCE.replace('Welcome back', 'Welcome home')))
        self.families = []
        for family, commits in (('vague-report', [defect]), ('feature-change', []), ('review-claims', [claim])):
            request = write(self.inputs, family + '/request.txt', SECRET_REQUEST + ' ' + family)
            oracle = write(self.inputs, family + '/oracle.json', '{"expected": "%s"}' % family)
            attachments = [str(write(self.inputs, family + '/crop.PNG', 'png-bytes'))] if family == 'vague-report' else []
            self.families.append({'id': family, 'source_group': 'consumer-' + family, 'request': str(request),
                                  'attachments': attachments, 'oracle': str(oracle),
                                  'commits': [{'patch': str(p), 'message': 'Setup ' + family} for p in commits]})

    def manifest(self, **changes):
        data = {'version': 1, 'study': 'integration-pilot-test', 'host': HOST, 'model': 'gpt-6.1-sol',
                'reasoning': 'medium', 'seed': 20261017, 'repetitions': 2, 'timeout_seconds': 600,
                'budget': {'invocations': 12, 'retries': 0},
                'payload': {'root': str(self.payload), 'revision': '1' * 40,
                            'inventory_sha256': conditions.inventory_digest(self.payload)},
                'consumer': {'repository': str(self.consumer), 'revision': self.revision,
                             'control_paths': ['.agents/skills/briefing-control', 'verification', 'verify.mjs'],
                             'pointer': 'AGENTS.md', 'prerequisites': ['node 22 on PATH', 'dependencies installed offline']},
                'families': self.families}
        for key, value in changes.items():
            data[key] = value
        path = self.base / ('manifest-%d.json' % len(list(self.base.glob('manifest-*.json'))))
        path.write_text(json.dumps(data))
        return path

    def freeze(self, manifest=None, name='study'):
        return integration.freeze(manifest or self.manifest(), self.base / name)

    def refused(self, message, **changes):
        with self.assertRaisesRegex(ValueError, message):
            self.freeze(self.manifest(**changes), name='refused-%d' % len(list(self.base.glob('refused-*'))))

    def test_freeze_allocates_twelve_paired_slots_without_an_agent(self):
        result = self.freeze()
        self.assertEqual(result['parent_slots'], 12)
        self.assertFalse(result['agent_executed'])
        study = integration.FrozenIntegration(self.base / 'study', result['controls_sha256'])
        cells = [(s['family'], s['arm'], s['repetition']) for s in study.schedule]
        self.assertEqual(len(set(cells)), 12)
        for family in integration.FAMILIES:
            block = [c for c in cells if c[0] == family]
            self.assertEqual(sorted(block), sorted((family, a, r) for a in integration.ARMS for r in (1, 2)))
        self.assertEqual([s['family'] for s in study.schedule], [f for f in sorted(integration.FAMILIES) for _ in range(4)])
        again = self.freeze(name='again')
        self.assertEqual(json.loads((self.base / 'again/schedule.json').read_text()), study.schedule)
        self.assertEqual(again['controls_sha256'], result['controls_sha256'])

    def test_arms_differ_only_in_control_paths_and_pointer_line(self):
        result = self.freeze()
        control, baseline = self.base / 'study/arms/control', self.base / 'study/arms/baseline'
        self.assertIn(CONTROL_LINE, (control / 'AGENTS.md').read_text())
        self.assertNotIn('Control:', (baseline / 'AGENTS.md').read_text())
        self.assertEqual((baseline / 'AGENTS.md').read_text(), (control / 'AGENTS.md').read_text().replace(CONTROL_LINE, ''))
        for path in ('verification', '.agents/skills/briefing-control', 'verify.mjs'):
            self.assertTrue((control / path).exists())
            self.assertFalse((baseline / path).exists())
        self.assertEqual((control / 'src/briefing.mjs').read_text(), SOURCE, 'froze the working copy, not the revision')
        self.assertTrue((control / 'verify.mjs').stat().st_mode & stat.S_IXUSR)
        controls = json.loads((self.base / 'study/controls.json').read_text())
        self.assertEqual(controls['consumer']['arm_difference'], {'removed_files': 3, 'changed_files': 1})
        self.assertEqual(controls['budget'], {'invocations': 12, 'retries': 0})
        self.assertEqual(controls['children'], 0)
        self.assertIsNone(controls['actual_model'])
        self.assertTrue(result['controls_sha256'])

    def test_every_slot_rebuilds_its_frozen_fixture(self):
        result = self.freeze()
        study = integration.FrozenIntegration(self.base / 'study', result['controls_sha256'])
        heads = {}
        for slot in range(1, 13):
            cell, built = study.fixture(slot, self.base / 'work' / str(slot))
            heads.setdefault((cell['family'], cell['arm']), set()).add(built['head'])
            if cell['family'] == 'vague-report':
                self.assertIn("? '' :", (self.base / 'work' / str(slot) / 'src/briefing.mjs').read_text())
        self.assertTrue(all(len(v) == 1 for v in heads.values()), 'repetitions of one cell must share HEAD')
        self.assertNotEqual(heads[('vague-report', 'control')], heads[('vague-report', 'baseline')])

    def test_summary_carries_digests_and_counts_only(self):
        result = self.freeze()
        study = integration.FrozenIntegration(self.base / 'study', result['controls_sha256'])
        text = json.dumps(integration.summary(study))
        for private in (str(self.base), 'zz-private-marker', 'briefing-control', 'verification', 'AGENTS.md',
                        'node 22', 'Setup vague-report', 'consumer-'):
            self.assertNotIn(private, text)
        data = json.loads(text)
        self.assertEqual(data['consumer']['revision'], self.revision)
        self.assertEqual(len(data['schedule']), 12)
        self.assertEqual(data['families']['vague-report']['fixtures']['control']['commits'], 2)
        with contextlib.redirect_stdout(io.StringIO()) as printed:
            code = integration.main(['--summary', str(self.base / 'study'), '--controls-sha256', result['controls_sha256']])
        self.assertEqual((code, json.loads(printed.getvalue())), (0, data))

    def test_changed_inputs_fail_verification(self):
        result = self.freeze()
        study_root = self.base / 'study'
        with self.assertRaisesRegex(ValueError, 'pin'):
            integration.FrozenIntegration(study_root, None)
        with self.assertRaisesRegex(ValueError, 'controls changed'):
            integration.FrozenIntegration(study_root, '0' * 64)
        target = study_root / 'arms/baseline/src/briefing.mjs'
        target.parent.chmod(0o755)
        target.chmod(0o644)
        target.write_text(SOURCE + '// edited\n')
        with self.assertRaisesRegex(ValueError, 'arm changed: baseline'):
            integration.FrozenIntegration(study_root, result['controls_sha256'])

    def test_private_material_stays_outside_the_mana_checkout(self):
        with self.assertRaisesRegex(ValueError, 'outside the Mana checkout'):
            integration.freeze(self.manifest(), integration.ROOT / 'evals/results/never-here')
        self.assertFalse((integration.ROOT / 'evals/results/never-here').exists())
        inside = dict(self.families[0], request=str(integration.ROOT / 'README.md'))
        self.refused('outside the Mana checkout', families=[inside] + self.families[1:])
        with self.assertRaisesRegex(ValueError, 'inside the consumer'):
            integration.freeze(self.manifest(), self.consumer / 'frozen')

    def test_manifest_controls_are_refused(self):
        self.refused('exactly 12 invocations', budget={'invocations': 13, 'retries': 0})
        self.refused('exactly 12 invocations', budget={'invocations': 12, 'retries': 1})
        self.refused('two repetitions', repetitions=3)
        self.refused('timeout', timeout_seconds=901)
        self.refused('unvalidated|not accepted|no evidence|unknown', host='codex-cli 0.159.0-alpha.3')
        self.refused('exactly the families', families=self.families[:2])
        self.refused('wrong or changed payload', payload={'root': str(self.payload), 'revision': '1' * 40,
                                                          'inventory_sha256': '0' * 64})
        consumer = self.manifest_data()['consumer']
        self.refused('full commit id', consumer=dict(consumer, revision='HEAD'))
        self.refused('absent from the pinned revision', consumer=dict(consumer, control_paths=['missing']))
        self.refused('pointer file stays', consumer=dict(consumer, control_paths=['AGENTS.md']))
        self.refused('invalid relative path', consumer=dict(consumer, control_paths=['../escape']))
        shared = [dict(f, source_group='shared') for f in self.families]
        self.refused('own source group', families=shared)

    def test_pointer_must_name_one_control_line(self):
        consumer = self.manifest_data()['consumer']
        write(self.consumer, 'NOTES.md', 'no pointer here\n')
        write(self.consumer, 'TWO.md', CONTROL_LINE + CONTROL_LINE)
        git(self.consumer, 'add', 'NOTES.md', 'TWO.md')
        git(self.consumer, 'commit', '-qm', 'notes')
        revision = git(self.consumer, 'rev-parse', 'HEAD')
        self.refused('exactly one Control line, found 0', consumer=dict(consumer, revision=revision, pointer='NOTES.md'))
        self.refused('exactly one Control line, found 2', consumer=dict(consumer, revision=revision, pointer='TWO.md'))

    def test_setup_that_needs_the_control_fails_on_the_baseline(self):
        control_edit = write(self.inputs, 'control.patch', patch(self.base, 'verify.mjs', 'process.exit(0)\n',
                                                                 'process.exit(1)\n'))
        families = [dict(f, commits=[{'patch': str(control_edit), 'message': 'break the control'}])
                    if f['id'] == 'review-claims' else f for f in self.families]
        self.refused('review-claims setup does not apply to the baseline arm', families=families)

    def test_operator_git_config_cannot_change_fixture_heads(self):
        first = self.freeze()
        home = self.base / 'home'
        write(home, '.gitconfig', '[diff]\n\tmnemonicPrefix = true\n[user]\n\tname = Someone Else\n')
        saved = os.environ.get('HOME')
        os.environ['HOME'] = str(home)
        try:
            second = self.freeze(name='other-home')
        finally:
            os.environ['HOME'] = saved
        self.assertEqual(first['controls_sha256'], second['controls_sha256'])

    def manifest_data(self):
        return json.loads(self.manifest().read_text())


if __name__ == '__main__':
    unittest.main()
