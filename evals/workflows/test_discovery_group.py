"""The frozen discovery group driver, offline against fake_host.py. No model is invoked."""
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

import discovery
import discovery_group
import run
from test_discovery import RESPONSE, empty_host_folders, evidence
from test_host_validation import MODEL, FakeHost

LINUX = sys.platform.startswith('linux')
FAILED_SPAWN = ('ERROR codex_core::tools::router: error=collab spawn failed: Fatal error: failed to load model context '
                'for thread parent: invalid thread-store request: no rollout found for thread id parent')


def git(root, *args):
    subprocess.run(['git', '-C', str(root), '-c', 'user.name=Mana Fixture', '-c', 'user.email=fixture@example.invalid', *args],
                   check=True, capture_output=True, text=True)


def source_repo(base):
    """A clean copy of the evaluator and catalog, pushed to a local origin so the fetch check runs offline."""
    root = Path(base) / 'source'
    shutil.copytree(run.ROOT / 'skills', root / 'skills')
    workflows = run.ROOT / 'evals/workflows'
    for name in [p.name for p in workflows.glob('*.py')] + ['discovery-cases.json', 'response-schema.json']:
        (root / 'evals/workflows').mkdir(parents=True, exist_ok=True)
        shutil.copy2(workflows / name, root / 'evals/workflows' / name)
    (root / 'evals/workflows/host-evidence').mkdir()
    git(base, 'init', '-q', '--bare', '-b', 'main', str(Path(base) / 'origin.git'))
    git(root, 'init', '-q', '-b', 'main')
    git(root, 'add', '.')
    git(root, 'commit', '-qm', 'source')
    git(root, 'remote', 'add', 'origin', str(Path(base) / 'origin.git'))
    git(root, 'push', '-q', 'origin', 'main')
    return root


@unittest.skipUnless(LINUX, 'fake sandbox containment and the family sweep target Linux')
class Group(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.base = Path(temp.name)
        self.root = source_repo(self.base)
        self.registry = evidence(self.base / 'registry')
        patcher, _ = empty_host_folders(self.base)
        patcher.start()
        self.addCleanup(patcher.stop)

    def group(self, plan, name):
        host = FakeHost(self, dict({'response': RESPONSE}, **plan))
        out = self.base / 'results' / name
        with host.environment():
            manifest = discovery_group.freeze(out, host.executable, MODEL, root=self.root, evidence_dir=self.registry)
            completion = discovery_group.run(out, host.executable, root=self.root, evidence_dir=self.registry, live=False)
        return manifest, completion, json.loads((out / 'allocation.json').read_text()), host

    def test_failed_spawns_mark_their_slots_and_the_group_runs_every_slot(self):
        wait = {'tool': 'wait', 'receiver_thread_ids': []}
        manifest, completion, rows, host = self.group({'collab_items': [wait], 'stderr_lines': [FAILED_SPAWN],
                                                       'parent': {'commands': ['cat README.md']}}, 'attempted')
        self.assertIsNone(completion['stop_reason'])
        self.assertEqual(len(rows), 24)
        self.assertEqual(len(host.calls()), 24)
        self.assertEqual({row['children'] for row in rows}, {'attempted'})
        self.assertEqual(completion['children_attempted_slots'], list(range(24)))
        self.assertEqual([row['slot'] for row in rows], [cell['slot'] for cell in manifest['schedule']])
        self.assertEqual(manifest['source']['upstream_ref'], 'origin/main')
        self.assertEqual(manifest['source']['head'], manifest['source']['upstream'])
        self.assertEqual(manifest['resources']['parent_slots'], 24)

    def test_a_created_child_stops_the_group_and_keeps_every_allocation(self):
        _, completion, rows, host = self.group({'collab_items': [{'tool': 'spawn_agent', 'receiver_thread_ids': ['child-1']}]},
                                               'created')
        self.assertIn('a child thread was created', completion['stop_reason'])
        self.assertEqual(len(host.calls()), 1)
        self.assertEqual(rows[0]['children'], 'created')
        self.assertEqual({row['status'] for row in rows[1:]}, {'not_started'})
        self.assertEqual(len(rows), 24)

    def test_a_host_that_exits_nonzero_stops_the_group(self):
        _, completion, rows, host = self.group({'exit_code': 1}, 'exited')
        self.assertIn('host failed or cancelled', completion['stop_reason'])
        self.assertEqual(len(host.calls()), 1)
        self.assertEqual({row['status'] for row in rows[1:]}, {'not_started'})

    def test_a_group_never_freezes_a_stale_or_dirty_checkout(self):
        host = FakeHost(self, {'response': RESPONSE})
        (self.root / 'notes.txt').write_text('uncommitted')
        with host.environment(), self.assertRaisesRegex(ValueError, 'uncommitted changes'):
            discovery_group.freeze(self.base / 'dirty', host.executable, MODEL, root=self.root, evidence_dir=self.registry)
        (self.root / 'notes.txt').unlink()
        # Someone else lands a commit on main; this checkout has not pulled it.
        other = self.base / 'other'
        git(self.base, 'clone', '-q', str(self.base / 'origin.git'), str(other))
        (other / 'later.txt').write_text('later')
        git(other, 'add', '.')
        git(other, 'commit', '-qm', 'later')
        git(other, 'push', '-q', 'origin', 'main')
        with host.environment(), self.assertRaisesRegex(ValueError, 'does not contain origin/main'):
            discovery_group.freeze(self.base / 'stale', host.executable, MODEL, root=self.root, evidence_dir=self.registry)
        self.assertFalse((self.base / 'stale').exists())
        self.assertEqual(host.calls(), [])

    def test_a_group_refuses_an_unaccepted_host_and_a_second_run(self):
        host = FakeHost(self, {'response': RESPONSE})
        with host.environment(), self.assertRaisesRegex(ValueError, 'unvalidated host'):
            discovery_group.freeze(self.base / 'unaccepted', host.executable, MODEL, root=self.root,
                                   evidence_dir=evidence(self.base / 'no-discovery', discovery_status=None))
        _, _, _, host = self.group({}, 'once')
        with host.environment(), self.assertRaisesRegex(ValueError, 'already ran'):
            discovery_group.run(self.base / 'results/once', host.executable, root=self.root, evidence_dir=self.registry, live=False)

    def test_a_changed_source_stops_before_the_next_slot(self):
        host = FakeHost(self, {'response': RESPONSE})
        out = self.base / 'results' / 'changed'
        with host.environment():
            discovery_group.freeze(out, host.executable, MODEL, root=self.root, evidence_dir=self.registry)
            (self.root / 'evals/workflows/discovery-cases.json').write_text('{}')
            completion = discovery_group.run(out, host.executable, root=self.root, evidence_dir=self.registry, live=False)
        rows = json.loads((out / 'allocation.json').read_text())
        self.assertIn('changed', completion['stop_reason'])
        self.assertEqual((rows[0]['status'], host.calls()), ('setup_failed', []))

    def test_cli_needs_live_out_and_model(self):
        script = str(run.HERE / 'run.py')
        for extra in (['--discover-group', '--out', str(self.base / 'x'), '--model', MODEL],
                      ['--discover-group', '--live', '--model', MODEL],
                      ['--discover-group', '--live', '--out', str(self.base / 'x'), '--model', MODEL, '--case', 'scan-positive']):
            with self.subTest(extra=extra):
                result = subprocess.run([sys.executable, '-B', script] + extra, capture_output=True, text=True,
                                        env={'PATH': '/usr/bin:/bin'})
                self.assertEqual(result.returncode, 2, result.stderr)
                self.assertFalse((self.base / 'x').exists())


if __name__ == '__main__':
    unittest.main()
