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


def load_challenge():
    """Execute challenge.sh's Python body as a module, without running its command line."""
    text = Path(CHALLENGE).read_text()
    source = text.split("<<'PY'\n", 1)[1].rsplit("\nPY\n", 1)[0]
    namespace = {"__name__": "leyline_challenge_under_test"}
    saved, sys.argv = sys.argv, ["python3", str(CHALLENGE)]
    try:
        exec(compile(source, str(CHALLENGE), "exec"), namespace)
    finally:
        sys.argv = saved
    return namespace


CHALLENGE_MODULE = load_challenge()


def observed(record):
    """Rebuild the challenger's observed identities from a retained run record."""
    table = {}
    for pid, pgid, start in record["observedIdentities"]:
        table.setdefault(pid, set()).add((pgid, start))
    return table


class ProcessIdentityTests(unittest.TestCase):
    def setUp(self):
        self.proc = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"], start_new_session=True)
        self.addCleanup(lambda: self.proc.poll() is None and (self.proc.kill(), self.proc.wait()))
        now = CHALLENGE_MODULE["proc_identity"](self.proc.pid)
        self.assertIsNotNone(now)
        self.pgid, self.start = now[0], now[1]

    def test_a_reused_pid_is_left_alone(self):
        # The same PID recorded for an earlier process: its start time differs from the live one.
        reused = {self.proc.pid: {(self.pgid, "start time of an earlier process")}}
        self.assertEqual(CHALLENGE_MODULE["owned_alive"](reused), [])
        self.assertEqual(CHALLENGE_MODULE["reap_owned"](reused, wait=0), ([], []))
        self.assertFalse(CHALLENGE_MODULE["kill_owned"](self.proc.pid, reused[self.proc.pid]))
        # The same PID and start time under a different process group is not the observed process either.
        regrouped = {self.proc.pid: {(self.pgid + 1, self.start)}}
        self.assertEqual(CHALLENGE_MODULE["reap_owned"](regrouped, wait=0), ([], []))
        time.sleep(0.2)
        self.assertIsNone(self.proc.poll(), "a process that was never observed was signalled")

    def test_the_observed_process_is_stopped(self):
        seen = {self.proc.pid: {(self.pgid, self.start)}}
        self.assertEqual(CHALLENGE_MODULE["reap_owned"](seen, wait=0), ([self.proc.pid], [self.proc.pid]))
        self.assertEqual(self.proc.wait(timeout=5), -signal.SIGKILL)
        self.assertEqual(CHALLENGE_MODULE["owned_alive"](seen), [])


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
            self.assertEqual(CHALLENGE_MODULE["owned_alive"](observed(run)), [], f"{name} left a process")
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

    def test_sigterm_stops_in_flight_runs_and_still_cleans_up(self):
        hold = Path(self.temp.name) / "hold"
        hold.mkdir()
        # Every run waits at its handshake, so the baseline is in flight when the signal arrives.
        self.fixture.plan_path.write_text(json.dumps({"feature": "briefing", "timeoutSeconds": 60,
                                                      "env": {"LEYLINE_FIXTURE_SYNC_DIR": str(hold)}}))
        self.dirty_user_files()
        before = self.bytes_state()
        proc = subprocess.Popen(["bash", str(CHALLENGE), str(self.repo), "--trust", "--plan", str(self.fixture.plan_path),
                                 "--evidence", str(self.evidence)], cwd=self.repo, env=self.fixture.env,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        self.addCleanup(lambda: proc.poll() is None and (proc.kill(), proc.wait()))
        deadline = time.monotonic() + 60
        while not (hold / "ready").exists() and proc.poll() is None and time.monotonic() < deadline:
            time.sleep(0.05)
        self.assertTrue((hold / "ready").exists(), "the baseline runner never reached its handshake")
        ready = json.loads((hold / "ready").read_text())
        proc.send_signal(signal.SIGTERM)
        stdout, stderr = proc.communicate(timeout=60)
        self.assertEqual(proc.returncode, 143, stderr[-3000:])
        doc = json.loads((self.evidence / "challenge.json").read_text())
        self.assertEqual(doc["interrupted"], "SIGTERM")
        self.assertEqual(json.loads(stdout)["outcome"], "interrupted")
        self.assertEqual(doc["probes"][-1]["status"], "interrupted")
        self.assertNotIn("baseline", [p["probe"] for p in doc["probes"]])
        [aborted] = doc["interruptedRuns"]
        self.assertIn("feature briefing", aborted["argv"])
        self.assertEqual(aborted["remaining"], [])
        seen = {pid for pid, _, _ in aborted["observedIdentities"]}
        self.assertTrue({ready["runnerPid"], ready["serverPid"]} <= seen, (ready, seen))
        self.assertEqual(CHALLENGE_MODULE["owned_alive"](observed(aborted)), [])
        self.assertFalse(alive(doc["sentinel"]["pid"]))
        self.assertFalse(Path(ready["tempPath"]).exists())
        self.assertEqual(self.bytes_state(), before)
        self.assertEqual(len(self.fixture.git("worktree", "list", "--porcelain").stdout.split("worktree ")) - 1, 1)
        self.assertTrue(doc["preservation"][-1]["unchanged"])
        self.assertTrue(json.loads((self.evidence / "result.json").read_text())["retained"]["verifiedAfterCleanup"])

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
