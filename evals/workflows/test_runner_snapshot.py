"""Frozen runner copies must remain executable without the original checkout."""
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import run


class RunnerSnapshotTests(unittest.TestCase):
    def test_focused_and_delegated_snapshots_import_and_validate_offline(self):
        for delegated in (False, True):
            with self.subTest(delegated=delegated), tempfile.TemporaryDirectory() as temp:
                source = Path(temp) / 'runner-source'
                run.snapshot_runner_source(source, delegated=delegated)
                check = subprocess.run([sys.executable, '-B', str(source / 'run.py'), '--check'],
                                       cwd=source, capture_output=True, text=True)
                self.assertEqual(check.returncode, 0, check.stderr)
                self.assertIn('33 valid; no agent executed', check.stdout)
                if delegated:
                    check = subprocess.run([sys.executable, '-B', '-c', 'import delegated_review'],
                                           cwd=source, capture_output=True, text=True)
                    self.assertEqual(check.returncode, 0, check.stderr)


if __name__ == '__main__':
    unittest.main()
