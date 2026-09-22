"""Offline regressions for shared assets and documented evidence capture."""
import contextlib
import io
import json
from pathlib import Path
import shlex
import subprocess
import tempfile
import unittest

import shared_assets
import verify_packages

ROOT = Path(__file__).resolve().parent.parent


class SharedAssets(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="mana assets ")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / "source").write_text("canonical\n")
        (self.root / "source").chmod(0o755)
        self.manifest = {"version": 1, "copies": [{"source": "source", "destinations": ["nested/copy"]}], "agents": [], "persona": None}

    def snapshot(self):
        return {str(p.relative_to(self.root)): (p.read_bytes(), p.stat().st_mode)
                for p in self.root.rglob("*") if p.is_file()}

    def sync(self, check=False):
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            return shared_assets.sync(self.root, self.manifest, check)

    def test_copy_check_and_idempotence(self):
        before = self.snapshot()
        self.assertEqual(self.sync(True), 1)
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(self.sync(), 0)
        self.assertEqual((self.root / "nested/copy").stat().st_mode & 0o777, 0o755)
        before = self.snapshot()
        self.assertEqual(self.sync(True), 0)
        self.sync()
        self.assertEqual(self.snapshot(), before)
        (self.root / "nested/copy").write_text("drift")
        before = self.snapshot()
        self.assertEqual(self.sync(True), 1)
        self.assertEqual(self.snapshot(), before)

    def test_invalid_declarations_leave_every_file_unchanged(self):
        invalid = [
            {"source": "missing", "destinations": ["later"]},
            {"source": "source", "destinations": ["nested/copy"]},
            {"source": "source", "destinations": ["../escaped"]},
            {"source": "source", "destinations": ["/absolute"]},
            {"source": "source", "destinations": ["source"]},
            {"source": "source", "destinations": "wrong-type"},
            {"source": "source", "destinations": ["source/child"]},
        ]
        for declaration in invalid:
            with self.subTest(declaration=declaration):
                self.manifest["copies"] = self.manifest["copies"][:1] + [declaration]
                before = self.snapshot()
                with self.assertRaises((ValueError, OSError)):
                    self.sync()
                self.assertEqual(self.snapshot(), before)

    def test_symlink_destination_and_parent(self):
        for value in ("link", "link/child"):
            (self.root / "link").symlink_to(self.root / "source")
            self.manifest["copies"][0]["destinations"] = ["first", value]
            before = self.snapshot()
            with self.assertRaises(ValueError):
                self.sync()
            self.assertEqual(self.snapshot(), before)
            (self.root / "link").unlink()

    def test_agent_and_copy_cannot_own_same_destination(self):
        self.manifest["agents"] = [{"name": "test", "source": "source", "destination": "nested/copy", "description": "Test agent."}]
        with self.assertRaisesRegex(ValueError, "duplicate destination"):
            self.sync()
        self.assertFalse((self.root / "nested").exists())

    def test_existing_generated_bytes(self):
        manifest = json.loads((ROOT / "scripts/shared-assets.json").read_text())
        for path, (data, _) in shared_assets.plan(ROOT, manifest).items():
            self.assertEqual(path.read_bytes(), data, str(path))


class Capture(unittest.TestCase):
    def run_capture(self, check_exit, renderer_failure=False, broken=False):
        guide = (ROOT / "skills/reveal/references/capture.md").read_text()
        block = guide.split("```bash\n", 1)[1].split("```", 1)[0]
        block = block.replace("<the proving command>", f"bash -c 'echo observed-check; exit {check_exit}'")
        block = block.replace("<SKILL_DIR>", str(ROOT / "skills/reveal"))
        if broken:
            # The original defect: the renderer alone determines pipeline success.
            block = f"bash -c 'echo observed-check; exit {check_exit}' | bash {shlex.quote(str(ROOT / 'skills/reveal/scripts/text-frame.sh'))} \"$DIR/tests.svg\""
        with tempfile.TemporaryDirectory(prefix="mana capture ") as temp:
            path = Path(temp)
            if renderer_failure:
                (path / "tests.svg").mkdir()
            result = subprocess.run(["bash", "-e", "-c", 'DIR="$1"\n' + block, "fixture", temp], capture_output=True, text=True)
            status = (path / "status.txt").read_text() if (path / "status.txt").exists() else ""
            rendered = (path / "tests.svg").is_file()
            return result.returncode, status, rendered

    def test_actual_check_exit_survives_successful_renderer(self):
        self.assertEqual(self.run_capture(7), (7, "check_exit=7 render_exit=0\n", True))
        self.assertEqual(self.run_capture(0), (0, "check_exit=0 render_exit=0\n", True))
        self.assertEqual(self.run_capture(7, broken=True)[0], 0, "seed must reproduce the original masking defect")

    def test_renderer_failure_is_not_success(self):
        code, status, _ = self.run_capture(0, renderer_failure=True)
        self.assertNotEqual(code, 0)
        self.assertIn("check_exit=0", status)
        self.assertNotIn("render_exit=0", status)
        self.assertEqual(self.run_capture(7, renderer_failure=True)[0], 7)


class Packages(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="mana package ")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "example"
        (self.root / "references").mkdir(parents=True)
        (self.root / "SKILL.md").write_text("Read `references/check.md`. Project input: `docs/agents/issue-tracker.md`.\n")
        (self.root / "references/check.md").write_text("Check the fixture.\n")
        self.contract = {"required": ["SKILL.md", "references/check.md"], "smoke": [], "project_links": {}}

    def test_missing_required_asset_fails_without_a_link(self):
        verify_packages.inspect_package(self.root, self.contract)
        (self.root / "SKILL.md").write_text("No links.\n")
        (self.root / "references/check.md").unlink()
        with self.assertRaisesRegex(ValueError, "example: missing bundled asset references/check.md"):
            verify_packages.inspect_package(self.root, self.contract)

    def test_link_escape_fails(self):
        (self.root / "SKILL.md").write_text("[sibling](../other/SKILL.md)\n")
        with self.assertRaisesRegex(ValueError, "escapes package"):
            verify_packages.inspect_package(self.root, self.contract)

    def test_new_bundled_reference_is_checked(self):
        (self.root / "SKILL.md").write_text("Read `scripts/missing.sh`.\n")
        with self.assertRaisesRegex(ValueError, "missing bundled asset scripts/missing.sh"):
            verify_packages.inspect_package(self.root, self.contract)

    def test_project_template_link_is_explicit(self):
        (self.root / "references/check.md").write_text("Build parent: [parent](../build.md)\n")
        self.contract["project_links"] = {"references/check.md": ["../build.md"]}
        verify_packages.inspect_package(self.root, self.contract)


class TrackerArguments(unittest.TestCase):
    def test_create_requires_label_and_dry_run_preserves_it(self):
        with tempfile.TemporaryDirectory(prefix="mana tracker ") as temp:
            root = Path(temp)
            gh = root / "gh"
            gh.write_text('#!/bin/bash\necho "unexpected live call" >&2\nexit 97\n')
            gh.chmod(0o755)
            env = {"PATH": str(root) + ":/usr/bin:/bin", "HOME": str(root), "TMPDIR": str(root), "LC_ALL": "C"}
            command = ["bash", str(ROOT / "skills/sift/scripts/tickets.sh"), "--repo", "fixture/mana", "create", "Fixture roadmap", "--dry-run"]
            broken = subprocess.run(command, input="Destination: verify packaging\n", capture_output=True, text=True, env=env, cwd=root)
            self.assertNotEqual(broken.returncode, 0)
            self.assertIn("create needs at least one --label", broken.stderr)
            fixed = subprocess.run(command + ["--label", "roadmap"], input="Destination: verify packaging\n", capture_output=True, text=True, env=env, cwd=root)
            self.assertEqual(fixed.returncode, 0, fixed.stderr)
            argv = shlex.split(fixed.stdout.removeprefix("command\t").strip())
            self.assertEqual(argv[argv.index("--label") + 1], "roadmap")
            self.assertEqual(Path(argv[argv.index("--body-file") + 1]).read_text(), "Destination: verify packaging\n")


if __name__ == "__main__":
    unittest.main()
