#!/usr/bin/env python3
"""Acceptance fixtures for the Leyline challenge stage.

Each test builds a synthetic project, installs its control with Leyline's generator and
runs challenge.sh against it. The project starts a real local HTTP server and reads it
through a stand-in browser. Results cover this synthetic fixture only, never a consumer.
"""

import hashlib
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from leyline_challenge_fixture import CHALLENGE, PLAN, Fixture, write  # noqa: E402

BUILTIN = ["static", "list", "describe", "unknown", "baseline", "break", "restore", "parallel",
           "cancel-sigint", "cancel-sigterm"]
VARIANTS = [variant["name"] for variant in PLAN["variants"]]
BREAK = "briefing.return-summary"


def alive(pid):
    listed = subprocess.run(["ps", "-o", "stat=", "-p", str(pid)], capture_output=True, text=True)
    return listed.returncode == 0 and listed.stdout.strip() != "" and not listed.stdout.strip().startswith("Z")


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


@unittest.skipUnless(shutil.which("node") and shutil.which("ps"), "Node 22.13+ and ps are needed")
class ChallengeTests(unittest.TestCase):
    maxDiff = 6000

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="lc-")
        self.addCleanup(self.temp.cleanup)
        self.fixture = Fixture(Path(self.temp.name) / "fixture").build()
        self.repo = self.fixture.repo
        self.evidence = Path(self.temp.name) / "evidence"

    def bytes_state(self):
        state = {str(p.relative_to(self.repo)): p.read_bytes() for p in self.repo.rglob("*")
                 if p.is_file() and ".git" not in p.relative_to(self.repo).parts}
        for name in ("index", "HEAD"):
            state[f".git/{name}"] = (self.repo / ".git" / name).read_bytes()
        state["resolved-head"] = self.fixture.git("rev-parse", "HEAD").stdout
        state["worktrees"] = self.fixture.git("worktree", "list", "--porcelain").stdout
        return state

    def dirty_user_files(self):
        write(self.repo, "human.txt", "a staged human change\n")
        self.fixture.git("add", "human.txt")
        write(self.repo, "human.txt", "a staged human change\nplus an unstaged change\n")
        write(self.repo, "src/hosted/briefing.mjs", (self.repo / "src/hosted/briefing.mjs").read_text() + "// unstaged edit\n")
        write(self.repo, "notes/untracked.txt", "untracked human bytes\n")

    def set_plan(self, **changes):
        plan = json.loads(json.dumps(PLAN))
        plan.update(changes)
        self.fixture.plan_path.write_text(json.dumps(plan))

    def probes(self, doc):
        return {probe["probe"]: probe for probe in doc["probes"]}

    def retained_report(self, probe, index=0):
        return json.loads((self.evidence / probe["runs"][index]["stdout"]).read_text())

    def lifecycle(self, probe, index=0):
        evidence = self.evidence / probe["runs"][index]["controlEvidence"]
        return json.loads((evidence / "feature.runner.json").read_text())["fixtureLifecycle"]

    def test_every_challenge_path_passes_preserves_checkout_and_retains_evidence(self):
        self.dirty_user_files()
        before = self.bytes_state()
        code, doc, result = self.fixture.challenge(evidence=self.evidence)
        self.assertEqual(code, 0, (result.stdout[-6000:], result.stderr[-2000:]))
        probes = self.probes(doc)
        self.assertEqual(list(probes), BUILTIN + VARIANTS)
        self.assertEqual({name: p["status"] for name, p in probes.items()}, {name: "passed" for name in probes}, doc)
        self.assertEqual(doc["outcome"], "passed")
        head = self.fixture.git("rev-parse", "HEAD").stdout.strip()
        self.assertEqual(doc["source"]["head"], head)
        self.assertIn("uncommitted", doc["excludedChanges"])

        # Criterion 1: baseline and restored states pass; the declared break fails its scenario.
        self.assertEqual(self.retained_report(probes["baseline"])["status"], "passed")
        broken = self.retained_report(probes["break"])
        self.assertEqual((broken["status"], broken["exit"]), ("failed", 1))
        self.assertEqual([c["failed"] for c in broken["checks"] if c["status"] == "failed"], [[BREAK]])
        self.assertEqual(self.retained_report(probes["restore"])["status"], "passed")
        self.assertEqual(len({self.retained_report(probes[n])["runId"] for n in ("baseline", "break", "restore")}), 3)

        # Criterion 2: concurrent runs own distinct resources, the unknown listener survives,
        # and cancellation leaves no started process behind.
        parallel = probes["parallel"]
        self.assertTrue(all(parallel["distinct"].values()), parallel["distinct"])
        first, second = self.lifecycle(parallel, 0), self.lifecycle(parallel, 1)
        sentinel = doc["sentinel"]["port"]
        for life in (first, second):
            self.assertEqual(life["preferredPort"], sentinel)
            self.assertTrue(life["preferredBusy"])
            self.assertNotEqual(life["port"], sentinel)
            self.assertTrue(life["serverStopped"] and life["cleaned"], life)
        for key in ("port", "serverPid", "runnerPid", "tempPath"):
            self.assertNotEqual(first[key], second[key], key)
        self.assertTrue(doc["sentinel"]["aliveAtEnd"])
        self.assertTrue(all(p["unknownListenerAlive"] for p in doc["probes"]))
        for name, code_expected in (("cancel-sigint", 130), ("cancel-sigterm", 143)):
            run = probes[name]["runs"][0]
            report = self.retained_report(probes[name])
            self.assertEqual((report["status"], report["exit"], run["exit"]), ("cancelled", code_expected, code_expected))
            self.assertEqual(run["signalledWhile"], "the runner wrote its ready file")
            log = (self.evidence / run["controlEvidence"] / "feature.log").read_text()
            ready = json.loads(log.split("fixture ready ", 1)[1].splitlines()[0])
            self.assertIn(ready["serverPid"], run["descendantsAtSignal"])
            self.assertIn(ready["runnerPid"], run["descendantsAtSignal"])
            self.assertEqual(run["survivors"], [])
            for pid in run["observedProcesses"]:
                self.assertFalse(alive(pid), f"{name} left process {pid}")
            self.assertFalse(Path(ready["tempPath"]).exists())
            self.assertTrue(report["snapshot"]["cleaned"])

        # Criterion 3: each negative path stays incomplete and keeps the original failure.
        missing = self.retained_report(probes["missing-browser"])
        self.assertEqual((missing["status"], missing["exit"]), ("incomplete", 3))
        chromium = [p for p in missing["prerequisites"] if p["need"] == "chromium"][0]
        self.assertEqual(chromium["status"], "missing")
        self.assertIn("FIXTURE_BROWSER is not set", chromium["detail"])
        self.assertEqual(missing["checks"][0]["executed"], [])
        zero = self.retained_report(probes["zero-cases"])
        self.assertEqual((zero["status"], zero["checks"][0]["executed"]), ("incomplete", []))
        mutated = self.retained_report(probes["source-mutation"])
        self.assertEqual(mutated["status"], "incomplete")
        self.assertTrue(mutated["source"]["sourceChanged"])
        self.assertEqual(mutated["checks"][0]["status"], "failed")
        self.assertEqual(mutated["checks"][0]["failed"], [BREAK])
        teardown = self.retained_report(probes["teardown-failure"])
        self.assertEqual(teardown["status"], "incomplete")
        self.assertEqual(teardown["checks"][0]["status"], "failed")
        self.assertEqual(teardown["checks"][0]["failed"], [BREAK])
        self.assertIn("did not stop", teardown["checks"][0]["suiteErrors"][0])
        feature_process = [p for p in teardown["processes"] if p["role"] == "feature"][0]
        self.assertTrue(feature_process["lingeringAtExit"], "the stray server was not observed at runner exit")
        self.assertEqual(feature_process["survivors"], [])
        self.assertFalse(self.lifecycle(probes["teardown-failure"])["serverStopped"])
        for pid in feature_process["lingeringAtExit"]:
            self.assertFalse(alive(pid))

        # Criterion 4: HEAD, index, tracked and untracked bytes survive every path.
        self.assertEqual(self.bytes_state(), before)
        self.assertTrue(all(entry["unchanged"] for entry in doc["preservation"]), doc["preservation"])
        self.assertEqual({entry["after"] for entry in doc["preservation"]}, set(BUILTIN + VARIANTS + ["cleanup"]))

        # Retained evidence stays readable and byte-identical once every fixture is gone.
        self.assertTrue(doc["retained"]["verifiedAfterCleanup"] and doc["retained"]["scratchRemoved"])
        shutil.rmtree(self.fixture.base)
        self.assertFalse(self.repo.exists())
        manifest = json.loads((self.evidence / "manifest.json").read_text())
        self.assertEqual(len(manifest["files"]), doc["retained"]["files"])
        for item in manifest["files"]:
            self.assertEqual(sha256(self.evidence / item["path"]), item["sha256"], item["path"])
        self.assertEqual(json.loads((self.evidence / "challenge.json").read_text())["probes"][0]["probe"], "static")
        for name in ("break", "source-mutation", "teardown-failure"):
            report = self.retained_report(probes[name])
            self.assertEqual(report["source"]["identity"]["head"], head)
            copied = self.evidence / probes[name]["runs"][0]["controlEvidence"]
            self.assertEqual(json.loads((copied / "report.json").read_text()), report)
            for artifact in report["artifactDigests"]:
                retained = copied / Path(artifact["path"]).name
                self.assertEqual(sha256(retained), artifact["sha256"])
            self.assertTrue(any(c.get("failed") == [BREAK] for c in report["checks"]))

    def test_evicting_an_unknown_listener_fails_the_challenge(self):
        self.set_plan(env={"LEYLINE_FIXTURE_MODE": "evict"})
        code, doc, result = self.fixture.challenge("--only", "parallel", evidence=self.evidence)
        self.assertEqual(code, 1, result.stderr)
        probes = self.probes(doc)
        self.assertEqual(probes["baseline"]["status"], "failed")
        self.assertIn("unknown listener", probes["baseline"]["detail"])
        self.assertFalse(probes["baseline"]["unknownListenerAlive"])
        self.assertEqual(probes["parallel"]["status"], "blocked")
        self.assertFalse(alive(doc["sentinel"]["pid"]))

    def test_a_process_that_outlives_its_run_fails_the_challenge(self):
        leak = Path(self.temp.name) / "leaked.pid"
        self.set_plan(env={"LEYLINE_FIXTURE_MODE": "leak", "LEYLINE_FIXTURE_LEAK_FILE": str(leak)})
        code, doc, result = self.fixture.challenge("--only", "parallel", evidence=self.evidence)
        self.assertEqual(code, 1, result.stderr)
        baseline = self.probes(doc)["baseline"]
        self.assertEqual(baseline["status"], "failed")
        self.assertIn("outlived", baseline["detail"])
        stray = int(leak.read_text())
        self.assertIn(stray, baseline["runs"][0]["survivors"])
        deadline = time.monotonic() + 5
        while alive(stray) and time.monotonic() < deadline:
            time.sleep(0.05)
        self.assertFalse(alive(stray), "the challenger did not stop the process the run left behind")

    def test_a_run_that_writes_into_the_user_checkout_fails_the_challenge(self):
        self.dirty_user_files()
        target = self.repo / "notes/untracked.txt"
        self.set_plan(env={"LEYLINE_FIXTURE_MODE": "escape", "LEYLINE_FIXTURE_ESCAPE_PATH": str(target)})
        code, doc, result = self.fixture.challenge("--only", "parallel", evidence=self.evidence)
        self.assertEqual(code, 1, result.stderr)
        baseline = self.probes(doc)["baseline"]
        self.assertEqual(baseline["status"], "failed")
        self.assertIn("file:notes/untracked.txt", baseline["detail"])
        self.assertIn({"after": "cleanup", "unchanged": False, "changes": ["file:notes/untracked.txt"]}, doc["preservation"])

    def test_a_control_that_masks_teardown_failure_fails_the_challenge(self):
        control = self.repo / "scripts/control.ts"
        text = control.read_text()
        self.assertIn("check.suiteErrors.length > 0 || invalid", text)
        control.write_text(text.replace("check.suiteErrors.length > 0 || invalid", "invalid"))
        self.fixture.git("commit", "-qam", "drop suite error handling")
        code, doc, result = self.fixture.challenge("--only", "teardown-failure", evidence=self.evidence)
        self.assertEqual(code, 1, result.stderr)
        probe = self.probes(doc)["teardown-failure"]
        self.assertEqual(probe["status"], "failed")
        self.assertIn("expected status incomplete, got 'failed'", probe["detail"])

    def test_refusals(self):
        self.evidence.mkdir()
        (self.evidence / "earlier.txt").write_text("existing evidence is never overwritten\n")
        for argv, message in (
            (["bash", CHALLENGE, self.repo], "--trust"),
            (["bash", CHALLENGE, self.repo, "--trust", "--evidence", self.repo / "evidence"], "outside the checkout"),
            (["bash", CHALLENGE, self.repo, "--trust", "--evidence", self.evidence], "new or empty"),
            (["bash", CHALLENGE, self.repo, "--trust", "--only", "nothing"], "unknown probes"),
        ):
            refused = self.fixture.run(argv, check=False)
            self.assertEqual(refused.returncode, 2, refused.stderr)
            self.assertIn(message, refused.stderr)
        self.assertFalse((self.repo / "evidence").exists())


if __name__ == "__main__":
    unittest.main(verbosity=2)
