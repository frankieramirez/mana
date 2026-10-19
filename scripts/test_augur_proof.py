"""Offline helper regressions, not live-agent effectiveness evidence."""
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
import tempfile
import time
import unittest

ROOT = Path(__file__).resolve().parent.parent
HELPER = ROOT / "skills/augur/scripts/prove.sh"


class SourceBoundProof(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="augur fixture ")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.repo = self.root / "repo"
        self.repo.mkdir()
        self.git("init", "-q")
        self.git("config", "user.email", "fixture@example.invalid")
        self.git("config", "user.name", "Fixture")
        self.write("app.py", "VALUE = 'reviewed-failure'\n")
        self.write(".gitignore", "ignored.py\n")
        self.write(".gitattributes", "app.py export-ignore\n")
        self.commit("reviewed source")
        self.reviewed = self.git("rev-parse", "HEAD").strip()
        self.write("app.py", "VALUE = 'local-pass'\n")
        self.commit("current source")
        self.context = self.root / "context.json"
        self.context.write_text(json.dumps({"runtime": sys.version, "dependencies": "Python standard library only"}))
        self.script = self.root / "fact.sh"

    def git(self, *argv):
        return subprocess.check_output(["git", "-C", str(self.repo), *argv], text=True)

    def write(self, name, text):
        (self.repo / name).write_text(text)

    def commit(self, message):
        self.git("add", ".")
        self.git("commit", "-qm", message)

    def run_proof(self, code, *extra, revision=None, setup=None, environment=None):
        self.script.write_text("#!/usr/bin/env bash\nset -euo pipefail\n" + code + "\n")
        args = ["bash", str(HELPER), "--repo", str(self.repo), "--proof", str(self.script), "--context", str(self.context)]
        args += ["--revision", revision] if revision else ["--working-tree"]
        if setup:
            setup_file = self.root / "setup.sh"
            setup_file.write_text("set -euo pipefail\n" + setup + "\n")
            args += ["--setup", str(setup_file)]
        result = subprocess.run(args + list(extra), capture_output=True, text=True, env=environment)
        report = json.loads(result.stdout)
        directory = Path(report["runDirectory"])
        self.addCleanup(shutil.rmtree, directory)
        return result, report, directory

    def checkout_state(self):
        return self.git("rev-parse", "HEAD"), self.git("status", "--porcelain=v1", "-uall"), (self.repo / "app.py").read_bytes(), (self.repo / ".git/index").read_bytes()

    def test_reviewed_failure_cannot_be_replaced_by_passing_checkout(self):
        code = "python3 -c \"import app; print(app.VALUE); assert app.VALUE == 'local-pass'\""
        before = self.checkout_state()
        local, local_report, _ = self.run_proof(code)
        self.assertEqual(local.returncode, 0)
        self.assertEqual(local_report["status"], "passed")
        remote, report, directory = self.run_proof(code, revision=self.reviewed)
        self.assertEqual(remote.returncode, 1)
        self.assertEqual(report["status"], "failed")
        self.assertEqual(report["source"]["revision"], self.reviewed)
        self.assertEqual((directory / "proof.stdout.txt").read_text().strip(), "reviewed-failure")
        self.assertIn("AssertionError", (directory / "proof.stderr.txt").read_text())
        self.assertEqual(self.checkout_state(), before)
        self.assertEqual((directory / "source/app.py").read_text(), "VALUE = 'reviewed-failure'\n")
        self.assertEqual((directory / "proof.sh").read_bytes(), self.script.read_bytes())
        self.assertTrue(report["proof"]["scriptSha256"])
        self.assertTrue(report["source"]["sourceDigest"])

    def test_dirty_untracked_deleted_and_explicit_ignored_source(self):
        self.write("app.py", "VALUE = 'dirty'\n")
        self.write("new.py", "VALUE = 'untracked'\n")
        self.write("ignored.py", "VALUE = 'included'\n")
        (self.repo / ".gitattributes").unlink()
        before = self.checkout_state()
        code = "python3 -c \"import app, new, ignored; from pathlib import Path; assert (app.VALUE, new.VALUE, ignored.VALUE) == ('dirty', 'untracked', 'included'); assert not Path('.gitattributes').exists()\""
        result, report, directory = self.run_proof(code, "--include", "ignored.py")
        self.assertEqual(result.returncode, 0, report)
        self.assertEqual(report["status"], "passed")
        paths = {row["path"] for row in json.loads((directory / "source-manifest.json").read_text())}
        self.assertTrue({"app.py", "new.py", "ignored.py"} <= paths)
        self.assertNotIn(".gitattributes", paths)
        self.assertEqual(self.checkout_state(), before)

    def test_source_change_during_run_is_unproven(self):
        # Deliberately simulate an editor changing the user's source while the proof runs.
        command = "printf '%s\\n' \"VALUE = 'edited-concurrently'\" > " + shlex.quote(str(self.repo / "app.py"))
        result, report, _ = self.run_proof(command)
        self.assertEqual(result.returncode, 3)
        self.assertEqual(report["proof"]["exitCode"], 0)
        self.assertEqual(report["status"], "unproven")
        self.assertTrue(report["source"]["changedDuringRun"])
        self.assertIn("source changed", report["reason"])

    def test_snapshot_changes_and_new_source_invalidate_execution(self):
        for command in ("printf 'changed' > app.py", "printf 'new source' > injected.py"):
            with self.subTest(command=command):
                before = self.checkout_state()
                result, report, _ = self.run_proof(command)
                self.assertEqual(result.returncode, 3)
                self.assertEqual(report["status"], "unproven")
                self.assertTrue(report["source"]["snapshotChanged"])
                self.assertEqual(self.checkout_state(), before)

    def test_setup_can_add_dependencies_but_cannot_rewrite_selected_source(self):
        result, report, _ = self.run_proof("test -f dependency.txt", setup="printf pinned > dependency.txt")
        self.assertEqual(result.returncode, 0, report)
        self.assertEqual(report["setup"]["exitCode"], 0)
        result, report, _ = self.run_proof("exit 0", setup="printf changed > app.py")
        self.assertEqual(result.returncode, 3)
        self.assertIsNone(report["proof"])
        self.assertIn("changed selected source", report["reason"])
        result, report, _ = self.run_proof("exit 0", setup="echo missing prerequisite >&2; exit 7")
        self.assertEqual(result.returncode, 3)
        self.assertEqual(report["setup"]["exitCode"], 7)
        self.assertIsNone(report["proof"])

    def test_missing_revision_and_escaping_link_fail_without_running_proof(self):
        result, report, _ = self.run_proof("exit 0", revision="missing-commit")
        self.assertEqual(result.returncode, 3)
        self.assertEqual(report["status"], "unproven")
        self.assertIsNone(report["proof"])
        (self.repo / "external").symlink_to(self.context)
        result, report, _ = self.run_proof("exit 0")
        self.assertEqual(result.returncode, 3)
        self.assertIn("symlink escapes", report["reason"])
        self.assertIsNone(report["proof"])

    def test_ambient_pythonpath_does_not_import_current_checkout(self):
        environment = dict(os.environ, PYTHONPATH=str(self.repo))
        result, report, _ = self.run_proof("python3 -c \"import app; assert app.VALUE == 'reviewed-failure'\"", revision=self.reviewed, environment=environment)
        self.assertEqual(result.returncode, 0, report)

    def test_required_origin_assertion_rejects_an_ambient_editable_install(self):
        (self.repo / "src").mkdir()
        self.write("src/implementation.py", "VALUE = 'reviewed-failure'\n")
        self.commit("reviewed src layout")
        revision = self.git("rev-parse", "HEAD").strip()
        self.write("src/implementation.py", "VALUE = 'local-pass'\n")
        self.commit("local src layout")
        # Reproduce an editable installation: the selected interpreter's .pth file
        # redirects src-layout imports into the current checkout despite cleared PYTHONPATH.
        setup = "python3 -m venv --without-pip --copies .venv\n.venv/bin/python - <<'CODE'\nimport site\nfrom pathlib import Path\n(Path(site.getsitepackages()[0]) / 'editable.pth').write_text(" + repr(str(self.repo / "src") + "\n") + ")\nCODE"
        unchecked = ".venv/bin/python -c \"import implementation; assert implementation.VALUE == 'local-pass'\""
        result, report, _ = self.run_proof(unchecked, revision=revision, setup=setup)
        self.assertEqual(result.returncode, 0, report)
        checked = ".venv/bin/python - <<'CODE'\nimport os\nfrom pathlib import Path\nimport implementation\nsnapshot = Path(os.environ['AUGUR_SOURCE']).resolve()\nloaded = Path(implementation.__file__).resolve()\nassert loaded.is_relative_to(snapshot), f'unproven: implementation loaded outside snapshot: {loaded}'\nassert implementation.VALUE == 'local-pass'\nCODE"
        result, report, directory = self.run_proof(checked, revision=revision, setup=setup)
        self.assertEqual(result.returncode, 1, report)
        self.assertEqual(report["status"], "failed")
        self.assertIn("implementation loaded outside snapshot", (directory / "proof.stderr.txt").read_text())

    def test_manifest_binding_rejects_stale_first_party_code_added_by_setup(self):
        (self.repo / "src").mkdir()
        self.write("src/implementation.py", "VALUE = 'reviewed-failure'\n")
        self.commit("reviewed src implementation")
        revision = self.git("rev-parse", "HEAD").strip()
        setup = "mkdir installed\nprintf \"VALUE = 'unrelated-pass'\\n\" > installed/implementation.py"
        prefix = "python3 - <<'CODE'\nimport hashlib, json, os, sys\nfrom pathlib import Path\nsys.path.insert(0, str(Path.cwd() / 'installed'))\nimport implementation\nsnapshot = Path(os.environ['AUGUR_SOURCE']).resolve()\nloaded = Path(implementation.__file__).resolve()\n"
        weak_check = "assert loaded.is_relative_to(snapshot)\nassert implementation.VALUE == 'unrelated-pass'\nCODE"
        result, report, _ = self.run_proof(prefix + weak_check, revision=revision, setup=setup)
        self.assertEqual(result.returncode, 0, report)
        strong_check = "selected = json.loads(Path(os.environ['AUGUR_MANIFEST']).read_text())\nexpected_path = 'src/implementation.py'\nexpected = next(item for item in selected if item['path'] == expected_path)\nassert loaded == snapshot / expected_path, f'unproven: unexpected implementation path: {loaded}'\nassert hashlib.sha256(loaded.read_bytes()).hexdigest() == expected['sha256']\nassert implementation.VALUE == 'unrelated-pass'\nCODE"
        result, report, directory = self.run_proof(prefix + strong_check, revision=revision, setup=setup)
        self.assertEqual(result.returncode, 1, report)
        self.assertEqual(report["status"], "failed")
        self.assertIn("unexpected implementation path", (directory / "proof.stderr.txt").read_text())
        correct_source = (prefix + strong_check).replace("'installed'", "'src'").replace("unrelated-pass", "reviewed-failure")
        result, report, _ = self.run_proof(correct_source, revision=revision, setup=setup)
        self.assertEqual(result.returncode, 0, report)

    def test_background_work_is_terminated_and_cannot_later_change_retained_source(self):
        result, report, directory = self.run_proof("(sleep 0.2; printf changed > app.py; echo late-output) & echo proof-returned")
        self.assertEqual(result.returncode, 3, report)
        self.assertEqual(report["status"], "unproven")
        self.assertEqual(report["proof"]["exitCode"], 0)
        self.assertTrue(report["proof"]["backgroundProcesses"])
        self.assertIn("left background processes", report["reason"])
        time.sleep(0.3)
        self.assertEqual((directory / "source/app.py").read_text(), "VALUE = 'local-pass'\n")
        self.assertEqual((directory / "proof.stdout.txt").read_text().strip(), "proof-returned")
        result, report, _ = self.run_proof('(printf ready > "$AUGUR_ARTIFACTS/ready") & wait')
        self.assertEqual(result.returncode, 0, report)
        self.assertFalse(report["proof"]["backgroundProcesses"])

    def test_unusual_paths_and_internal_symlinks_preserve_bytes_without_shell_expansion(self):
        name = "quoted'$(touch PWNED);\ninput.txt"
        self.write(name, "exact source bytes\n")
        (self.repo / "internal-link").symlink_to(name)
        code = "python3 - <<'CODE'\nfrom pathlib import Path\nassert Path(" + repr(name) + ").read_text() == 'exact source bytes\\n'\nassert Path('internal-link').read_text() == 'exact source bytes\\n'\nCODE"
        result, report, directory = self.run_proof(code)
        self.assertEqual(result.returncode, 0, report)
        self.assertFalse((directory / "source/PWNED").exists())
        self.assertFalse((self.repo / "PWNED").exists())
        self.assertTrue((directory / "source/internal-link").is_symlink())

    def test_included_path_cannot_escape_repository(self):
        result, report, _ = self.run_proof("exit 0", "--include", "../context.json")
        self.assertEqual(result.returncode, 3)
        self.assertEqual(report["status"], "unproven")
        self.assertIn("unsafe source path", report["reason"])
        self.assertIsNone(report["proof"])

    def write_break(self, old, new, name="break.patch"):
        patch = self.root / name
        patch.write_text("--- a/app.py\n+++ b/app.py\n@@ -1 +1 @@\n-" + old + "\n+" + new + "\n")
        return patch

    def test_break_must_make_a_passing_proof_fail(self):
        patch = self.write_break("VALUE = 'local-pass'", "VALUE = 'broken'")
        before = self.checkout_state()
        code = "python3 - <<'CODE'\nimport app\nprint('coverage: one value, 1 reached the check')\nassert app.VALUE == 'local-pass', app.VALUE\nCODE"
        result, report, directory = self.run_proof(code, "--break", str(patch))
        self.assertEqual(result.returncode, 0, report)
        self.assertEqual(report["status"], "passed")
        self.assertEqual(report["challenge"], "detected")
        self.assertEqual(report["coverage"], "one value, 1 reached the check")
        self.assertTrue(report["breaks"][0]["detected"])
        self.assertIn("broken", (directory / "break-1.stderr.txt").read_text())
        self.assertEqual((directory / "source/app.py").read_text(), "VALUE = 'local-pass'\n")
        self.assertEqual(self.checkout_state(), before)

    def test_proof_that_passes_on_the_break_is_unproven(self):
        patch = self.write_break("VALUE = 'local-pass'", "VALUE = 'broken'")
        result, report, _ = self.run_proof("python3 -c \"import app; print(app.VALUE)\"", "--break", str(patch))
        self.assertEqual(result.returncode, 3, report)
        self.assertEqual(report["status"], "unproven")
        self.assertEqual(report["challenge"], "missed")
        self.assertIn("cannot tell", report["reason"])

    def test_pass_without_a_break_is_reported_as_unchallenged(self):
        result, report, _ = self.run_proof("python3 -c \"import app; assert app.VALUE == 'local-pass'\"")
        self.assertEqual(result.returncode, 0, report)
        self.assertEqual(report["challenge"], "not-run")
        self.assertIsNone(report["coverage"])

    def test_break_runs_against_its_own_manifest(self):
        patch = self.write_break("VALUE = 'local-pass'", "VALUE = 'broken'")
        code = "python3 - <<'CODE'\nimport hashlib, json, os\nfrom pathlib import Path\nimport app\nsnapshot = Path(os.environ['AUGUR_SOURCE']).resolve()\nloaded = Path(app.__file__).resolve()\nexpected = next(i for i in json.loads(Path(os.environ['AUGUR_MANIFEST']).read_text()) if i['path'] == 'app.py')\nassert loaded == snapshot / 'app.py', 'unproven: wrong path'\nassert hashlib.sha256(loaded.read_bytes()).hexdigest() == expected['sha256'], 'unproven: wrong source'\nassert app.VALUE == 'local-pass', 'fact false: ' + app.VALUE\nCODE"
        result, report, directory = self.run_proof(code, "--break", str(patch))
        self.assertEqual(result.returncode, 0, report)
        errors = (directory / "break-1.stderr.txt").read_text()
        self.assertIn("fact false: broken", errors)
        self.assertNotIn("unproven", errors)

    def test_break_that_does_not_apply_is_unproven(self):
        patch = self.write_break("VALUE = 'something else'", "VALUE = 'broken'")
        result, report, _ = self.run_proof("exit 0", "--break", str(patch))
        self.assertEqual(result.returncode, 3, report)
        self.assertEqual(report["status"], "unproven")
        self.assertIn("does not apply", report["reason"])

    def test_failing_proof_skips_the_break(self):
        patch = self.write_break("VALUE = 'local-pass'", "VALUE = 'broken'")
        result, report, _ = self.run_proof("exit 1", "--break", str(patch))
        self.assertEqual(result.returncode, 1, report)
        self.assertEqual(report["status"], "failed")
        self.assertEqual(report["challenge"], "not-run")
        self.assertEqual(report["breaks"], [])

    def test_timeout_retains_output_and_is_unproven(self):
        result, report, directory = self.run_proof("echo started; sleep 10", "--timeout-seconds", "0.1")
        self.assertEqual(result.returncode, 3)
        self.assertEqual(report["status"], "unproven")
        self.assertIn("execution budget", report["reason"])
        self.assertTrue(report["proof"]["timedOut"])
        self.assertEqual(report["proof"]["exitCode"], -9)
        self.assertEqual((directory / "proof.stdout.txt").read_text().strip(), "started")


if __name__ == "__main__":
    unittest.main()
