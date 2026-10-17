#!/usr/bin/env python3
"""End-to-end installation checks using a local app and its existing test runner.

The runner emits the public Vitest JSON shape, but its results come from actual
Node assertions over an in-process request fixture. No package install, socket,
browser, or remote service is used; hosted network/browser trials remain separate.
"""

import concurrent.futures
import hashlib
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import tempfile
import time
import unittest


ROOT = Path(__file__).resolve().parents[1]
GENERATOR = ROOT / "skills/leyline/scripts/generate.sh"
CONFORM = ROOT / "skills/leyline/scripts/conform.sh"
SCENARIOS = {"briefing.return-summary", "briefing.no-activity"}
SOURCE = '''export function briefing(workers) {
  return {
    produced: workers.reduce((sum, worker) => sum + worker.produced, 0),
    workers: workers.map(worker => worker.name),
    message: workers.length ? 'Welcome back' : 'No activity',
  };
}
'''
RUNNER = r'''import assert from 'node:assert/strict';
import {mkdtemp, readFile, writeFile, appendFile, rm} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {briefing} from '../../src/hosted/briefing.mjs';

const destination = process.argv[2];
assert.ok(destination, 'runner report destination is required');
const mode = process.env.LEYLINE_FIXTURE_MODE || 'normal';
const assertions = [];
const lifecycle = {pid: process.pid, kind: 'in-process', tempPath: null, cleaned: false};
const tests = [];
function scenario(id, _kind, run) { tests.push({id, run}); }
scenario('briefing.return-summary', 'local', async () => {
  const response = await request('/briefing');
  assert.equal(response.path, '/kingdom');
  const actual = response.body;
  assert.equal(actual.produced, 5);
  assert.deepEqual(actual.workers, ['mill', 'mine']);
  assert.equal(actual.message, 'Welcome back');
});
scenario('briefing.no-activity', 'local', async () => {
  const actual = (await request('/kingdom?empty=1')).body;
  assert.equal(actual.produced, 0);
  assert.deepEqual(actual.workers, []);
  assert.equal(actual.message, 'No activity');
});

const started = Date.now();
const fixture = await mkdtemp(join(tmpdir(), 'briefing-fixture-'));
lifecycle.tempPath = fixture;
const seed = JSON.parse(await readFile('fixtures/ready.txt', 'utf8'));
await writeFile(join(fixture, 'workers.json'), JSON.stringify(seed));
await writeFile('runner-invoked.marker', 'executed in a disposable snapshot\n');
async function request(path) {
  if (path === '/briefing') return request('/kingdom');
  const workers = path.includes('empty=1') ? [] :
    JSON.parse(await readFile(join(fixture, 'workers.json'), 'utf8'));
  return {path, body: briefing(workers)};
}
try {
  if (mode === 'wait') {
    const sync = process.env.LEYLINE_FIXTURE_SYNC_DIR;
    assert.ok(sync, 'external source-mutation handshake is required');
    await writeFile(join(sync, 'ready'), 'ready');
    const deadline = Date.now() + 10000;
    while (true) {
      try { await readFile(join(sync, 'release')); break; } catch {}
      assert.ok(Date.now() < deadline, 'test handshake timed out');
      await new Promise(resolve => setTimeout(resolve, 10));
    }
  }
  if (mode === 'overlap') await new Promise(resolve => setTimeout(resolve, 300));
  if (mode === 'mutate') await appendFile('src/hosted/briefing.mjs', '\n// changed during execution\n');
  if (mode !== 'zero') {
    for (const test of tests) {
      const assertion = {title: test.id, fullName: `briefing ${test.id}`,
        ancestorTitles: ['briefing'], status: 'passed', duration: 0, failureMessages: []};
      const begin = Date.now();
      try { await test.run(); }
      catch (error) { assertion.status = 'failed'; assertion.failureMessages = [String(error)]; }
      assertion.duration = Date.now() - begin;
      assertions.push(assertion);
    }
  }
} finally {
  await rm(fixture, {recursive: true, force: true});
  lifecycle.cleaned = true;
}
const failed = assertions.filter(item => item.status === 'failed').length;
const report = {
  success: failed === 0, startTime: started, numTotalTestSuites: 1,
  numPassedTestSuites: failed ? 0 : 1, numFailedTestSuites: failed ? 1 : 0,
  numTotalTests: assertions.length, numPassedTests: assertions.length - failed,
  numFailedTests: failed, numPendingTests: 0, numTodoTests: 0,
  testResults: [{name: 'tests/hosted/briefing.test.mjs', status: failed ? 'failed' : 'passed',
    startTime: started, endTime: Date.now(), message: '', assertionResults: assertions}],
  fixtureLifecycle: lifecycle,
};
await writeFile(destination, JSON.stringify(report));
console.log(JSON.stringify({fixtureLifecycle: lifecycle}));
process.exitCode = failed ? 1 : 0;
'''


def write(root, relative, content):
    target = root / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    return target


class InstallationTests(unittest.TestCase):
    maxDiff = 4000

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="li-")
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.repo = self.base / "app"
        self.repo.mkdir()
        (self.base / "tmp").mkdir()
        self.env = dict(os.environ, GIT_AUTHOR_NAME="Fixture", GIT_AUTHOR_EMAIL="fixture@example.test",
                        GIT_COMMITTER_NAME="Fixture", GIT_COMMITTER_EMAIL="fixture@example.test",
                        GIT_OPTIONAL_LOCKS="0", TMPDIR=str(self.base / "tmp"))
        self.env.pop("LEYLINE_FIXTURE_MODE", None)
        self.env.pop("LEYLINE_FIXTURE_SYNC_DIR", None)
        self.original_agent = "# Hosted app\n\nKeep this human-owned paragraph.\n\n## Agent skills\n\nValidation: `node tests/hosted/briefing.test.mjs`\n\n## Notes\n\nPreserve this exact final section.\n"
        write(self.repo, "AGENTS.md", self.original_agent)
        write(self.repo, "package.json", json.dumps({"name": "hosted-fixture", "type": "module", "private": True}))
        write(self.repo, "src/hosted/briefing.mjs", SOURCE)
        write(self.repo, "tests/hosted/briefing.test.mjs", RUNNER)
        write(self.repo, "fixtures/ready.txt", '[{"name":"mill","produced":2},{"name":"mine","produced":3}]\n')
        write(self.repo, "human.txt", "original human bytes\n")
        self.git("init", "-q")
        self.git("add", ".")
        self.git("commit", "-qm", "local fixture")
        write(self.repo, "src/hosted/briefing.mjs", SOURCE.replace("'Welcome back'", "'Old summary'"))
        self.patch = write(self.repo, "supplied/briefing.return-summary.patch", self.git("diff", "--", "src/hosted/briefing.mjs").stdout)
        write(self.repo, "src/hosted/briefing.mjs", SOURCE)
        self.git("add", "supplied/briefing.return-summary.patch")
        self.git("commit", "-qm", "declared behavior break")
        self.spec = {
            "project": "hosted-fixture",
            "feature": {"id": "briefing", "summary": "Read a return summary in the kingdom overview",
                        "aliases": ["welcome back", "came back", "empty briefing"],
                        "sourceRoots": ["src/hosted/briefing.mjs", "fixtures/ready.txt"],
                        "knowledge": "proposed",
                        "reach": [{"route": "/kingdom", "steps": ["Open /briefing and follow its redirect."]}]},
            "scenarios": [
                {"id": "briefing.return-summary", "steps": [{"action": "Return after two workers produced resources.",
                                                              "expect": "The kingdom overview shows their total and welcome message."}]},
                {"id": "briefing.no-activity", "steps": [{"action": "Open an account with no workers.",
                                                          "expect": "The overview reports zero production and no workers."}]},
            ],
            "bindings": ["tests/hosted/briefing.test.mjs"],
            "runner": {"argv": ["node", "tests/hosted/briefing.test.mjs", "{report}"], "format": "vitest-json"},
            "prerequisites": [{"need": "fixture-assets", "path": "fixtures/ready.txt"}],
            "timeoutSeconds": 15,
            "release": None,
            "break": {"scenario": "briefing.return-summary", "path": str(self.patch.relative_to(self.repo))},
        }
        self.spec_path = write(self.base, "spec.json", json.dumps(self.spec))
        self.map_path = self.base / "map.json"

    def command(self, argv, *, code=0, env=None, timeout=40, cwd=None):
        result = subprocess.run([str(arg) for arg in argv], cwd=cwd or self.repo, text=True,
                                capture_output=True, env=dict(self.env, **(env or {})), timeout=timeout)
        self.assertEqual(result.returncode, code, (argv, result.returncode, result.stdout[-6000:], result.stderr[-3000:]))
        return result

    def git(self, *args):
        return self.command(["git", *args])

    def generate(self, verb, *args, code=0):
        return self.command(["bash", GENERATOR, verb, self.repo, *args], code=code)

    def conform(self, verb, *args, code=0, env=None):
        return json.loads(self.command(["bash", CONFORM, verb, *args], code=code, env=env, timeout=90).stdout)

    def draft(self):
        self.spec_path.write_text(json.dumps(self.spec), encoding="utf-8")
        self.generate("map", "--spec", self.spec_path, "--out", self.map_path)
        self.assertTrue(self.map_path.is_file())

    def install(self):
        self.draft()
        self.generate("install", "--map", self.map_path)
        static = self.conform("static", self.repo)
        self.assertTrue(static["conformant"], static)
        self.control = shlex.split(static["control"]["keys"]["Command"])
        return static

    def run_control(self, *args, code=0, env=None):
        result = self.command([*self.control, *args, "--json"], code=code, env=env)
        report = json.loads(result.stdout)
        path = write(self.base, "checked-report.json", result.stdout)
        checked = self.conform("report", path, "--exit", str(code))
        self.assertTrue(checked["valid"], checked)
        return report

    def bytes_state(self):
        state = {str(path.relative_to(self.repo)): path.read_bytes()
                 for path in self.repo.rglob("*") if path.is_file() and ".git" not in path.relative_to(self.repo).parts}
        state[".git/index"] = (self.repo / ".git/index").read_bytes()
        state[".git/HEAD"] = (self.repo / ".git/HEAD").read_bytes()
        state["resolved-head"] = self.git("rev-parse", "HEAD").stdout
        return state

    def dirty_user_files(self):
        write(self.repo, "human.txt", "a staged human change\n")
        self.git("add", "human.txt")
        write(self.repo, "human.txt", "a staged human change\nplus an unstaged change\n")
        write(self.repo, "notes/untracked.txt", "untracked human bytes\n")

    def assert_retained(self, report, *, expect_runner=True):
        evidence = Path(report["evidenceDir"])
        self.addCleanup(shutil.rmtree, evidence, True)
        self.assertTrue(evidence.is_dir(), report)
        self.assertFalse(evidence.is_relative_to(self.repo), evidence)
        self.assertEqual(json.loads((evidence / "report.json").read_text()), report)
        self.assertFalse(Path(report["snapshot"]["path"]).exists(), report["snapshot"])
        self.assertTrue(report["artifacts"], report)
        if expect_runner:
            raw = []
            for path in evidence.rglob("*.json"):
                data = json.loads(path.read_text())
                if isinstance(data, dict) and "fixtureLifecycle" in data:
                    raw.append(data)
            self.assertTrue(raw, f"runner observations were not retained in {evidence}")
            for item in raw:
                lifecycle = item["fixtureLifecycle"]
                self.assertTrue(lifecycle["cleaned"], lifecycle)
                self.assertFalse(Path(lifecycle["tempPath"]).exists(), lifecycle)
                self.assertEqual(lifecycle["kind"], "in-process")
            return raw[0]["fixtureLifecycle"]

    def test_install_discovery_and_human_content(self):
        before = self.bytes_state()
        inspection = self.generate("inspect")
        self.assertIsInstance(json.loads(inspection.stdout), dict)
        self.assertEqual(self.bytes_state(), before, "inspection wrote to the project")
        self.draft()
        self.assertEqual(self.bytes_state(), before, "mapping wrote to the project")
        static = self.install()
        self.assertEqual(static["counts"], {"features": 1, "scenarios": 2, "bindings": 2, "breaks": 1})
        updated = (self.repo / "AGENTS.md").read_text()
        self.assertIn("Keep this human-owned paragraph.", updated)
        self.assertTrue(updated.endswith("## Notes\n\nPreserve this exact final section.\n"))
        self.assertIn("Control:", updated)
        self.assertEqual((self.repo / "src/hosted/briefing.mjs").read_text(), SOURCE)
        self.assertEqual((self.repo / "tests/hosted/briefing.test.mjs").read_text(), RUNNER)
        self.assertTrue((self.repo / "docs/agents/readiness.md").is_file())
        feature = json.loads((self.repo / "verification/features/briefing.json").read_text())
        self.assertEqual(feature["knowledge"], "proposed")
        self.assertEqual(feature, self.spec["feature"])
        listed = json.loads(self.command([*self.control, "list", "--search", "welcome back", "--json"]).stdout)
        self.assertIn("briefing", json.dumps(listed))
        self.command([*self.control, "feature", "missing", "--json"], code=2)

    def test_identical_install_changes_no_bytes(self):
        self.install()
        before = self.bytes_state()
        self.generate("install", "--map", self.map_path)
        self.assertEqual(self.bytes_state(), before)

    def test_stale_map_refuses_without_writes(self):
        self.draft()
        write(self.repo, "src/hosted/briefing.mjs", SOURCE + "\n// source changed after mapping\n")
        before = self.bytes_state()
        self.generate("install", "--map", self.map_path, code=1)
        self.assertEqual(self.bytes_state(), before)

    def test_preexisting_control_refuses_without_writes(self):
        write(self.repo, "skills/existing/SKILL.md", "Human-owned control skill.\n")
        write(self.repo, "AGENTS.md", self.original_agent.replace("Validation:", "Control: skills/existing/SKILL.md\nValidation:"))
        before = self.bytes_state()
        self.generate("map", "--spec", self.spec_path, "--out", self.map_path, code=1)
        self.assertEqual(self.bytes_state(), before)

    def test_generated_path_conflict_refuses_without_writes(self):
        write(self.repo, "scripts/control.ts", "// Human-owned existing command.\n")
        before = self.bytes_state()
        self.generate("map", "--spec", self.spec_path, "--out", self.map_path, code=1)
        self.assertEqual(self.bytes_state(), before)

    def test_recomputed_digest_cannot_install_forged_recipe(self):
        self.draft()
        plan = json.loads(self.map_path.read_text())
        output = plan["outputs"]["scripts/control.ts"]
        output["text"] += "\n// A map checksum does not authorize arbitrary generated code.\n"
        output["digest"] = hashlib.sha256(output["text"].encode()).hexdigest()
        plan.pop("mapDigest")
        plan["mapDigest"] = hashlib.sha256(json.dumps(plan, sort_keys=True, separators=(",", ":"),
                                                     ensure_ascii=False).encode()).hexdigest()
        self.map_path.write_text(json.dumps(plan))
        before = self.bytes_state()
        result = self.generate("install", "--map", self.map_path, code=1)
        self.assertIn("recipe", result.stderr)
        self.assertEqual(self.bytes_state(), before)

    def test_signals_after_actual_install_write_restore_all_user_bytes(self):
        self.dirty_user_files()
        self.draft()
        injection = self.base / "injection"
        injection.mkdir()
        # Inject only through Python's standard startup hook in this subprocess.
        # The real atomic publication occurs before a signal reaches the installer.
        write(injection, "sitecustomize.py", '''import json, os, pathlib, signal
root = pathlib.Path(os.environ["LEYLINE_TEST_TARGET"]).resolve()
marker = pathlib.Path(os.environ["LEYLINE_TEST_WRITE_MARKER"])
def interrupt_after_write(original):
    def publish(source, destination, *args, **kwargs):
        result = original(source, destination, *args, **kwargs)
        target = pathlib.Path(destination).resolve()
        if target.is_relative_to(root) and not marker.exists():
            marker.write_text(json.dumps({"path": str(target), "exists": target.is_file(),
                                          "bytes": target.read_bytes().hex()}))
            os.kill(os.getpid(), getattr(signal, os.environ["LEYLINE_TEST_SIGNAL"]))
        return result
    return publish
os.link = interrupt_after_write(os.link)
''')
        before = self.bytes_state()
        before_dirs = {str(path.relative_to(self.repo)) for path in self.repo.rglob("*") if path.is_dir()}
        for signal_name in ("SIGINT", "SIGTERM"):
            with self.subTest(signal=signal_name):
                marker = self.base / f"{signal_name}.json"
                result = self.command(["bash", GENERATOR, "install", self.repo, "--map", self.map_path],
                                      code=1, env={"PYTHONPATH": str(injection),
                                                   "LEYLINE_TEST_TARGET": str(self.repo),
                                                   "LEYLINE_TEST_WRITE_MARKER": str(marker),
                                                   "LEYLINE_TEST_SIGNAL": signal_name})
                self.assertTrue(marker.is_file(), "no actual project write was observed")
                observed = json.loads(marker.read_text())
                self.assertTrue(observed["exists"] and observed["bytes"], observed)
                self.assertIn(signal_name, result.stderr)
                self.assertEqual(self.bytes_state(), before)
                self.assertEqual({str(path.relative_to(self.repo)) for path in self.repo.rglob("*") if path.is_dir()},
                                 before_dirs, "interruption left generated directories behind")

    def test_human_edit_at_existing_file_publication_is_preserved(self):
        self.dirty_user_files()
        self.draft()
        injection = self.base / "edit-race"
        injection.mkdir()
        marker = self.base / "edit-race.json"
        target = self.repo / "AGENTS.md"
        addition = "\nHuman edit immediately before control pointer publication.\n"
        write(injection, "sitecustomize.py", '''import json, os
from pathlib import Path
original = os.replace
target = Path(os.environ["LEYLINE_TEST_TARGET"])
marker = Path(os.environ["LEYLINE_TEST_RACE_MARKER"])
def displace(source, destination, *args, **kwargs):
    if Path(source) == target and not marker.exists():
        target.write_bytes(target.read_bytes() + os.environ["LEYLINE_TEST_HUMAN_EDIT"].encode())
        marker.write_text(json.dumps({"path": str(target), "bytes": target.read_bytes().hex()}))
    return original(source, destination, *args, **kwargs)
os.replace = displace
''')
        expected = self.bytes_state()
        expected["AGENTS.md"] += addition.encode()
        before_dirs = {str(path.relative_to(self.repo)) for path in self.repo.rglob("*") if path.is_dir()}
        self.command(["bash", GENERATOR, "install", self.repo, "--map", self.map_path], code=1,
                     env={"PYTHONPATH": str(injection), "LEYLINE_TEST_TARGET": str(target),
                          "LEYLINE_TEST_RACE_MARKER": str(marker), "LEYLINE_TEST_HUMAN_EDIT": addition})
        self.assertTrue(marker.is_file(), "human edit was not injected at the displacement seam")
        self.assertEqual(bytes.fromhex(json.loads(marker.read_text())["bytes"]), expected["AGENTS.md"])
        self.assertEqual(self.bytes_state(), expected, "installation lost the new edit or retained another generated write")
        self.assertEqual({str(path.relative_to(self.repo)) for path in self.repo.rglob("*") if path.is_dir()}, before_dirs)

    def test_identical_concurrent_file_at_exclusive_publication_keeps_ownership(self):
        self.dirty_user_files()
        self.draft()
        injection = self.base / "link-race"
        injection.mkdir()
        marker = self.base / "link-race.json"
        target = self.repo / "scripts/control-config.json"
        write(injection, "sitecustomize.py", '''import json, os
from pathlib import Path
original = os.link
target = Path(os.environ["LEYLINE_TEST_TARGET"])
marker = Path(os.environ["LEYLINE_TEST_RACE_MARKER"])
def publish(source, destination, *args, **kwargs):
    if Path(destination) == target and not marker.exists():
        target.write_bytes(Path(source).read_bytes())
        stat = target.stat()
        marker.write_text(json.dumps({"bytes": target.read_bytes().hex(),
                                      "inode": stat.st_ino, "device": stat.st_dev}))
    return original(source, destination, *args, **kwargs)
os.link = publish
''')
        expected = self.bytes_state()
        self.command(["bash", GENERATOR, "install", self.repo, "--map", self.map_path], code=1,
                     env={"PYTHONPATH": str(injection), "LEYLINE_TEST_TARGET": str(target),
                          "LEYLINE_TEST_RACE_MARKER": str(marker)})
        self.assertTrue(marker.is_file(), "concurrent writer did not create the file before the exclusive link")
        observation = json.loads(marker.read_text())
        expected["scripts/control-config.json"] = bytes.fromhex(observation["bytes"])
        self.assertEqual(self.bytes_state(), expected, "rollback removed another writer's identical bytes")
        self.assertEqual((target.stat().st_dev, target.stat().st_ino),
                         (observation["device"], observation["inode"]), "rollback replaced the concurrent writer's file")

    def test_real_feature_pass_preserves_checkout_and_evidence(self):
        self.install()
        self.dirty_user_files()
        before = self.bytes_state()
        report = self.run_control("feature", "briefing")
        self.assertEqual(report["status"], "passed")
        self.assertFalse(report["source"]["sourceChanged"])
        self.assertEqual(set(report["checks"][0]["executed"]), SCENARIOS)
        self.assertEqual(self.bytes_state(), before)
        self.assert_retained(report)

    def test_declared_break_fails_actual_assertion_then_restore_passes(self):
        self.install()
        self.dirty_user_files()
        self.git("apply", str(self.patch))
        broken = self.bytes_state()
        report = self.run_control("feature", "briefing", code=1)
        self.assertEqual(report["status"], "failed")
        failures = [check for check in report["checks"] if check["status"] == "failed"]
        self.assertTrue(any("briefing.return-summary" in check["executed"] for check in failures), report)
        self.assertEqual(self.bytes_state(), broken)
        self.assert_retained(report)
        self.git("apply", "-R", str(self.patch))
        restored = self.run_control("feature", "briefing")
        self.assert_retained(restored)
        self.assertNotEqual(restored["runId"], report["runId"])

    def test_missing_prerequisite_is_incomplete_and_preserves_checkout(self):
        self.install()
        (self.repo / "fixtures/ready.txt").unlink()
        self.dirty_user_files()
        before = self.bytes_state()
        report = self.run_control("feature", "briefing", code=3)
        self.assertEqual(report["status"], "incomplete")
        self.assertIn({"need": "fixture-assets", "status": "missing"},
                      [{"need": item["need"], "status": item["status"]} for item in report["prerequisites"]])
        self.assertEqual(self.bytes_state(), before)
        self.assert_retained(report, expect_runner=False)

    def test_zero_assertions_is_incomplete(self):
        self.install()
        before = self.bytes_state()
        report = self.run_control("feature", "briefing", code=3, env={"LEYLINE_FIXTURE_MODE": "zero"})
        self.assertEqual(report["status"], "incomplete")
        self.assertFalse(report["checks"][0]["executed"])
        self.assertEqual(self.bytes_state(), before)
        self.assert_retained(report)

    def test_snapshot_source_mutation_is_incomplete_and_preserves_user_bytes(self):
        self.install()
        self.dirty_user_files()
        before = self.bytes_state()
        report = self.run_control("feature", "briefing", code=3, env={"LEYLINE_FIXTURE_MODE": "mutate"})
        self.assertEqual(report["status"], "incomplete")
        self.assertTrue(report["source"]["sourceChanged"])
        self.assertEqual(self.bytes_state(), before)
        self.assert_retained(report)

    def test_original_source_mutation_during_run_is_incomplete(self):
        self.install()
        sync = self.base / "sync"
        sync.mkdir()
        env = dict(self.env, LEYLINE_FIXTURE_MODE="wait", LEYLINE_FIXTURE_SYNC_DIR=str(sync))
        process = subprocess.Popen([*self.control, "feature", "briefing", "--json"], cwd=self.repo,
                                   env=env, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        self.addCleanup(lambda: process.kill() if process.poll() is None else None)
        deadline = time.monotonic() + 15
        while not (sync / "ready").exists() and process.poll() is None and time.monotonic() < deadline:
            time.sleep(0.01)
        self.assertTrue((sync / "ready").exists(), "runner did not reach the source-mutation handshake")
        changed = SOURCE + "\n// user's edit while the isolated run was active\n"
        write(self.repo, "src/hosted/briefing.mjs", changed)
        (sync / "release").write_text("continue")
        stdout, stderr = process.communicate(timeout=25)
        self.assertEqual(process.returncode, 3, (stdout, stderr))
        report = json.loads(stdout)
        self.assertTrue(report["source"]["sourceChanged"])
        self.assertEqual((self.repo / "src/hosted/briefing.mjs").read_text(), changed)
        checked = write(self.base, "external-source-report.json", stdout)
        self.assertTrue(self.conform("report", checked, "--exit", "3")["valid"])
        self.assert_retained(report)

    def test_concurrent_runs_own_resources_and_retain_distinct_evidence(self):
        self.install()
        before = self.bytes_state()
        def run():
            result = self.command([*self.control, "feature", "briefing", "--json"],
                                  env={"LEYLINE_FIXTURE_MODE": "overlap"})
            return json.loads(result.stdout)
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            first, second = list(pool.map(lambda _: run(), range(2)))
        self.assertEqual(self.bytes_state(), before)
        self.assertNotEqual(first["runId"], second["runId"])
        self.assertNotEqual(first["evidenceDir"], second["evidenceDir"])
        self.assertNotEqual(first["snapshot"]["path"], second["snapshot"]["path"])
        a, b = self.assert_retained(first), self.assert_retained(second)
        self.assertNotEqual(a["tempPath"], b["tempPath"])
        self.assertNotEqual(a["pid"], b["pid"])

    def test_dynamic_conformance_after_committing_install(self):
        self.install()
        self.git("add", ".")
        self.git("commit", "-qm", "install generated control")
        self.dirty_user_files()
        before = self.bytes_state()
        result = self.conform("dynamic", self.repo, "--trust", "--feature", "briefing", "--timeout", "20")
        self.assertTrue(result["static"]["conformant"], result)
        self.assertEqual({probe["probe"]: probe["status"] for probe in result["probes"]},
                         {"list": "passed", "describe": "passed", "unknown": "passed", "baseline": "passed",
                          "break": "passed", "restore": "passed", "parallel": "passed"})
        self.assertEqual(self.bytes_state(), before)
        self.assertEqual(len(self.git("worktree", "list").stdout.splitlines()), 1)


if __name__ == "__main__":
    if shutil.which("node") is None:
        raise SystemExit("Node is required for generated-control installation fixtures")
    unittest.main(verbosity=2)
