#!/usr/bin/env python3
"""Exercise generated control reports against real Node assertions and process failures."""
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import tempfile
import time
import unittest


REPO = Path(__file__).resolve().parents[1]
TEMPLATE = REPO / "skills/leyline/references/recipes/control.ts.template"
NODE = shutil.which("node")
RUNNER = r"""
import fs from 'node:fs';
import assert from 'node:assert/strict';
const mode = process.env.CONTROL_TEST_MODE;
const output = process.argv[2];
if (mode === 'hang') {
  fs.writeFileSync(process.env.CONTROL_TEST_READY, String(process.pid));
  setInterval(() => {}, 1000);
} else {
  let assertions = [];
  for (const id of ['greeting.present', 'greeting.exact']) {
    try {
      if (id === 'greeting.present') assert.ok(fs.existsSync('src/value.txt'));
      else assert.equal(fs.readFileSync('src/value.txt', 'utf8'), 'hello\n');
      assertions.push({title:id,fullName:'greeting '+id,status:'passed'});
    } catch (error) {
      assertions.push({title:id,fullName:'greeting '+id,status:'failed',failureMessages:[error.message]});
    }
  }
  if (mode === 'zero') assertions = [];
  if (mode === 'missing') assertions.pop();
  if (mode === 'skipped') assertions[1].status = 'pending';
  if (mode === 'prefix') assertions[1].title = assertions[1].fullName = 'greeting.exact-longer';
  if (mode === 'ambiguous') assertions = [{title:'greeting.present greeting.exact',fullName:'greeting.present greeting.exact',status:'passed'}];
  if (mode === 'unknown-status') assertions[1].status = 'finished';
  if (mode === 'mutate') fs.writeFileSync('src/value.txt', 'changed during run\n');
  const failed = assertions.filter(a => a.status === 'failed').length;
  const report = {success:failed===0,numTotalTests:assertions.length,numFailedTests:failed,
    testResults:[{assertionResults:assertions}]};
  if (mode === 'bad-total') report.numTotalTests++;
  if (mode === 'runtime-error') report.numRuntimeErrorTestSuites = 1;
  if (mode === 'secret') {
    console.error('TEST_TOKEN='+process.env.TEST_TOKEN);
    report.note = 'TEST_TOKEN='+process.env.TEST_TOKEN;
  }
  fs.writeFileSync(output, mode === 'malformed' ? '{broken' : JSON.stringify(report));
  process.exitCode = failed || mode === 'crash-after-report' ? 1 : 0;
}
"""


@unittest.skipUnless(NODE, "Node >= 22.13 is needed for the generated recipe")
class RuntimeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="ctr-")
        self.addCleanup(self.tmp.cleanup)
        self.home = Path(self.tmp.name)
        self.root = self.home / "project"
        self.root.mkdir()
        for directory in ["scripts", "src", "tests", "verification/features", "verification/scenarios/greeting"]:
            (self.root / directory).mkdir(parents=True, exist_ok=True)
        shutil.copyfile(TEMPLATE, self.root / "scripts/control.ts")
        self.put("package.json", {"private": True, "type": "module"})
        self.put("verification/features/greeting.json", {
            "id": "greeting", "summary": "Welcome a returning user", "aliases": ["hello", "welcome back"],
            "sourceRoots": ["src"], "knowledge": "proposed", "reach": [{"command": "hello", "steps": []}],
        })
        for scenario in ["present", "exact"]:
            self.put(f"verification/scenarios/greeting/{scenario}.json", {
                "id": f"greeting.{scenario}", "steps": [{"action": "read greeting", "expect": "hello"}],
            })
        (self.root / "tests/run.mjs").write_text(RUNNER)
        (self.root / "src/value.txt").write_text("hello\n")
        self.config = {
            "feature": "greeting", "sourceRoots": ["src"], "bindings": ["tests/run.mjs"],
            "runner": {"argv": [NODE, "tests/run.mjs", "{report}"], "format": "vitest-json"},
            "prerequisites": [{"need": "greeting fixture", "path": "src/value.txt"}],
            "timeoutSeconds": 3, "release": None,
            "featuresDir": "verification/features", "scenariosDir": "verification/scenarios",
            "evidenceDir": str(self.home / "evidence"),
        }
        self.save_config()
        self.git("init", "-q")
        self.git("add", ".")
        self.git("-c", "user.name=Control Test", "-c", "user.email=control@example.invalid", "commit", "-qm", "fixture")

    def put(self, name, value):
        (self.root / name).write_text(json.dumps(value) + "\n")

    def save_config(self):
        self.put("scripts/control-config.json", self.config)

    def git(self, *args):
        return subprocess.run(["git", "-C", str(self.root), *args], check=True, capture_output=True).stdout

    def invoke(self, *args, mode=None, extra_env=None):
        env = os.environ.copy()
        env.pop("CONTROL_TEST_MODE", None)
        if mode:
            env["CONTROL_TEST_MODE"] = mode
        env.update(extra_env or {})
        process = subprocess.run([NODE, "--experimental-strip-types", "scripts/control.ts", *args, "--json"],
                                 cwd=self.root, env=env, capture_output=True, text=True, timeout=10)
        try:
            report = json.loads(process.stdout)
        except ValueError:
            self.fail(f"no JSON document: {process.returncode} {process.stderr} {process.stdout}")
        if report.get("mode") not in {"discovery", "plan", "error"}:
            self.assertEqual(report["exit"], process.returncode)
            self.assertTrue(report["snapshot"]["cleaned"])
            self.assertFalse(Path(report["snapshot"]["path"]).exists())
            retained = json.loads((Path(report["evidenceDir"]) / "report.json").read_text())
            self.assertEqual(report, retained)
        return process.returncode, report

    def test_real_failure_and_restore_use_current_bytes(self):
        code, baseline = self.invoke("feature", "greeting")
        self.assertEqual(code, 0)
        (self.root / "src/value.txt").write_text("broken\n")
        code, broken = self.invoke("feature", "greeting")
        self.assertEqual(code, 1)
        self.assertEqual(broken["checks"][0]["failed"], ["greeting.exact"])
        self.assertNotEqual(baseline["source"]["identity"]["manifest"]["digest"], broken["source"]["identity"]["manifest"]["digest"])
        self.assertEqual(baseline["source"]["identity"]["head"], broken["source"]["identity"]["head"])
        (self.root / "src/value.txt").write_text("hello\n")
        self.assertEqual(self.invoke("feature", "greeting")[0], 0)

    def test_report_cannot_pass_unexecuted_or_unfinished_cases(self):
        for mode in ["zero", "missing", "skipped", "prefix", "ambiguous", "unknown-status", "bad-total", "runtime-error", "malformed", "crash-after-report"]:
            with self.subTest(mode=mode):
                code, report = self.invoke("feature", "greeting", mode=mode)
                self.assertEqual(code, 3)
                self.assertEqual(report["status"], "incomplete")

    def test_missing_prerequisite_is_named(self):
        (self.root / "src/value.txt").unlink()
        code, report = self.invoke("feature", "greeting")
        self.assertEqual(code, 3)
        self.assertIn({"need": "greeting fixture", "status": "missing", "detail": None}, report["prerequisites"])
        self.assertEqual(report["checks"][0]["executed"], [])

    def test_dependency_prerequisite_is_prepared_privately_never_copied(self):
        dependency = self.root / "node_modules/vitest/vitest.mjs"
        dependency.parent.mkdir(parents=True)
        dependency.write_text("shared dependency must remain unchanged\n")
        self.config["prerequisites"].append({"need": "vitest", "path": "node_modules/vitest/vitest.mjs"})
        self.save_config()
        code, report = self.invoke("feature", "greeting")
        self.assertEqual(code, 3)
        self.assertIn({"need": "vitest", "status": "missing", "detail": None}, report["prerequisites"])
        self.config["prepare"] = {"argv": [NODE, "-e", "const fs=require('node:fs'); fs.mkdirSync('node_modules/vitest',{recursive:true}); fs.writeFileSync('node_modules/vitest/vitest.mjs','private dependency');"]}
        self.save_config()
        code, report = self.invoke("feature", "greeting")
        self.assertEqual(code, 0)
        self.assertIn({"need": "vitest", "status": "present", "detail": None}, report["prerequisites"])
        self.assertEqual(dependency.read_text(), "shared dependency must remain unchanged\n")

    def test_inherited_git_configuration_cannot_redirect_the_snapshot(self):
        code, baseline = self.invoke("feature", "greeting")
        self.assertEqual(code, 0)
        code, report = self.invoke("feature", "greeting", extra_env={
            "GIT_CONFIG_COUNT": "1", "GIT_CONFIG_KEY_0": "core.worktree", "GIT_CONFIG_VALUE_0": str(self.home / "absent"),
        })
        self.assertEqual(code, 0)
        self.assertEqual(baseline["source"]["identity"]["head"], report["source"]["identity"]["head"])
        self.assertEqual(baseline["source"]["identity"]["manifest"]["digest"], report["source"]["identity"]["manifest"]["digest"])

    def test_snapshot_source_mutation_is_incomplete_and_preserves_checkout(self):
        code, report = self.invoke("feature", "greeting", mode="mutate")
        self.assertEqual(code, 3)
        self.assertTrue(report["source"]["sourceChanged"])
        self.assertEqual((self.root / "src/value.txt").read_text(), "hello\n")

    def test_untracked_source_is_part_of_identity(self):
        _, before = self.invoke("feature", "greeting")
        (self.root / "src/new.txt").write_text("new source")
        _, after = self.invoke("feature", "greeting")
        self.assertNotEqual(before["source"]["identity"]["manifest"]["digest"], after["source"]["identity"]["manifest"]["digest"])

    def save_after_read(self, relative_path, mutation):
        """Schedule an external save exactly after the controller reads old bytes."""
        preload = self.home / "save-after-read.cjs"
        target = str(self.root / relative_path)
        preload.write_text("""
const fs=require('node:fs');
const read=fs.readFileSync;
let done=false;
fs.readFileSync=function(file,...args){
  const result=read.call(this,file,...args);
  if(!done && String(file)===TARGET){
    done=true;
    const record=JSON.parse(String(result));
    MUTATION
  }
  return result;
};
""".replace("TARGET", json.dumps(target)).replace("MUTATION", mutation))
        return {"NODE_OPTIONS": "--require " + str(preload)}

    def test_config_save_before_capture_cannot_pass_under_new_source_identity(self):
        env = self.save_after_read("scripts/control-config.json", """
record.runner.argv[0]='missing-executable-after-save';
fs.writeFileSync(file,JSON.stringify(record)+'\\n');
""")
        code, report = self.invoke("feature", "greeting", extra_env=env)
        self.assertEqual(code, 3)
        self.assertTrue(report["source"]["sourceChanged"])
        self.assertTrue(all(check["executed"] == [] for check in report["checks"]))
        self.assertFalse((Path(report["evidenceDir"]) / "feature.runner.json").exists())
        repeat_code, repeat = self.invoke("feature", "greeting")
        self.assertEqual(repeat_code, 3)
        self.assertEqual(report["source"]["identity"]["manifest"]["digest"], repeat["source"]["identity"]["manifest"]["digest"])

    def test_scenario_added_before_capture_is_expected_from_snapshot(self):
        extra = str(self.root / "verification/scenarios/greeting/additional.json")
        env = self.save_after_read("verification/scenarios/greeting/present.json", """
record.id='greeting.additional';
fs.writeFileSync(ADDITIONAL,JSON.stringify(record)+'\\n');
""".replace("ADDITIONAL", json.dumps(extra)))
        code, report = self.invoke("feature", "greeting", extra_env=env)
        self.assertEqual(code, 3)
        self.assertIn("greeting.additional", report["checks"][0]["expected"])
        self.assertIn("greeting.additional", report["checks"][0]["missing"])
        repeat_code, repeat = self.invoke("feature", "greeting")
        self.assertEqual(repeat_code, 3)
        self.assertEqual(report["source"]["identity"]["manifest"]["digest"], repeat["source"]["identity"]["manifest"]["digest"])

    def test_unknown_selector_and_invalid_base_are_usage_errors(self):
        self.assertEqual(self.invoke("feature", "unknown")[0], 2)
        self.assertEqual(self.invoke("describe", "scenario", "unknown")[0], 2)
        self.assertEqual(self.invoke("changed", "--base", "does-not-exist")[0], 2)

    def test_discovery_and_plan_never_run_the_runner(self):
        self.config["runner"]["argv"][0] = "missing-executable-control-test"
        self.save_config()
        code, report = self.invoke("list", "--search", "welcome")
        self.assertEqual(code, 0)
        self.assertEqual(report["features"][0]["id"], "greeting")
        code, report = self.invoke("feature", "greeting", "--plan")
        self.assertEqual(code, 0)
        self.assertFalse(report["executed"])
        self.assertNotIn("status", report)
        self.assertFalse((self.home / "evidence").exists())
        code, report = self.invoke("feature", "greeting")
        self.assertEqual(code, 3)
        self.assertEqual(report["checks"][0]["reason"], "runner could not start")

    def test_release_requires_project_gate_and_preserves_failure(self):
        code, report = self.invoke("release")
        self.assertEqual(code, 3)
        self.assertEqual(report["checks"][-1]["status"], "unavailable")
        (self.root / "tests/release.mjs").write_text("import assert from 'node:assert/strict'; assert.equal(2+2,4);\n")
        self.config["release"] = {"argv": [NODE, "tests/release.mjs"], "format": "exit"}
        self.save_config()
        self.assertEqual(self.invoke("release")[0], 0)
        (self.root / "tests/release.mjs").write_text("import assert from 'node:assert/strict'; assert.equal(2+2,5);\n")
        code, report = self.invoke("release")
        self.assertEqual(code, 1)
        self.assertEqual(report["checks"][-1]["status"], "failed")

    def test_evidence_cannot_write_into_checkout(self):
        self.config["evidenceDir"] = str(self.root / "new-evidence")
        self.save_config()
        process = subprocess.run([NODE, "--experimental-strip-types", "scripts/control.ts", "feature", "greeting", "--json"],
                                 cwd=self.root, capture_output=True, text=True, timeout=10)
        self.assertEqual(process.returncode, 3)
        self.assertFalse((self.root / "new-evidence").exists())

    def test_logs_and_runner_report_redact_environment_secrets(self):
        secret = "control-fixture-secret-value-123"
        code, report = self.invoke("feature", "greeting", mode="secret", extra_env={"TEST_TOKEN": secret})
        self.assertEqual(code, 0)
        for artifact in report["artifacts"]:
            self.assertNotIn(secret, Path(artifact).read_text())
        retained = json.loads((Path(report["evidenceDir"]) / "feature.runner.json").read_text())
        self.assertIn("REDACTED", retained["note"])

    def test_timeout_and_signal_cleanup_owned_processes(self):
        self.config["timeoutSeconds"] = 0.2
        self.save_config()
        ready = self.home / "ready"
        code, report = self.invoke("feature", "greeting", mode="hang", extra_env={"CONTROL_TEST_READY": str(ready)})
        self.assertEqual(code, 3)
        self.assertEqual(report["checks"][0]["status"], "timed_out")
        with self.assertRaises(ProcessLookupError):
            os.kill(int(ready.read_text()), 0)
        self.config["timeoutSeconds"] = 8
        self.save_config()
        ready.unlink()
        env = {**os.environ, "CONTROL_TEST_MODE": "hang", "CONTROL_TEST_READY": str(ready)}
        proc = subprocess.Popen([NODE, "--experimental-strip-types", "scripts/control.ts", "feature", "greeting", "--json"],
                                cwd=self.root, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        self.addCleanup(lambda: proc.poll() is None and proc.kill())
        deadline = time.monotonic() + 5
        while not ready.exists() and time.monotonic() < deadline:
            time.sleep(0.02)
        self.assertTrue(ready.exists())
        proc.send_signal(signal.SIGTERM)
        stdout, stderr = proc.communicate(timeout=5)
        self.assertEqual(proc.returncode, 143, stderr)
        report = json.loads(stdout)
        self.assertEqual(report["status"], "cancelled")
        self.assertTrue(report["snapshot"]["cleaned"])
        with self.assertRaises(ProcessLookupError):
            os.kill(int(ready.read_text()), 0)


if __name__ == "__main__":
    unittest.main()
