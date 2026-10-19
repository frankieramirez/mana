"""Synthetic fixtures for `conform.sh evidence`: how workflows read project-control reports.

Every repository, report and criterion here is made up in a temporary directory. The fixtures
establish the reader's behavior only, not any real project's readiness.
"""
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parent.parent
READER = ROOT / "skills/leyline/scripts/conform.sh"
RETURN, EMPTY = "briefing.return-summary", "briefing.no-activity"


def sha(data):
    return hashlib.sha256(data).hexdigest()


class ControlEvidence(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix="control evidence ")
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.repo = self.root / "repo"
        self.sentinel = self.root / "control-ran"
        self.write("CLAUDE.md", "# Demo\n\n## Agent skills\n\nControl: skills/demo-control/SKILL.md\n")
        self.write("skills/demo-control/SKILL.md", "# Demo control\n\nCommand: `bash scripts/control.sh`\n")
        # A control that leaves a mark if anything ever runs it. The reader must not.
        self.write("scripts/control.sh", f"#!/bin/bash\ntouch '{self.sentinel}'\n")
        self.write("src/briefing.txt", "return summary\n")
        self.write("README.md", "unrelated\n")
        self.git("init", "-q")
        self.git("add", "-A")
        self.git("-c", "user.email=fixture@example.invalid", "-c", "user.name=Fixture", "commit", "-qm", "fixture")
        self.head = self.git("rev-parse", "HEAD").strip()

    def tearDown(self):
        self.assertFalse(self.sentinel.exists(), "the evidence reader executed the project control")

    def write(self, rel, text):
        path = self.repo / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)

    def git(self, *argv):
        return subprocess.check_output(["git", "-C", str(self.repo), *argv], text=True)

    def checked(self, paths=("src/briefing.txt",)):
        files = []
        for rel in paths:
            full = self.repo / rel
            files.append({"path": rel, "mode": full.stat().st_mode & 0o777, "digest": sha(full.read_bytes())})
        return files

    def report(self, status="passed", exit=0, checks=None, prerequisites=None, source_changed=False, files=True, head=None, digest=None):
        listed = self.checked()
        manifest = {"digest": digest or sha(json.dumps(listed, separators=(",", ":")).encode())}
        if files == "artifact":
            artifact = self.root / "manifest.json"
            artifact.write_text(json.dumps(listed, indent=2))
            manifest["artifact"] = str(artifact)
        elif files:
            manifest["files"] = listed
        if checks is None:
            checks = [self.check("passed", [RETURN, EMPTY], [RETURN, EMPTY])]
        return {"contract": "control/0", "runId": "fixture-1", "status": status, "exit": exit,
                "source": {"identity": {"head": self.head if head is None else head, "manifest": manifest}, "sourceChanged": source_changed},
                "prerequisites": prerequisites or [{"need": "chromium", "status": "present", "detail": None}],
                "checks": checks}

    @staticmethod
    def check(status, expected, executed, reason="fixture", failed=None, cid="briefing"):
        check = {"id": cid, "status": status, "reason": reason, "argv": ["bash", "scripts/control.sh"], "expected": expected, "executed": executed}
        if failed is not None:
            check["failed"] = failed
        return check

    def read(self, report=None, raw=None, exit=None, criteria=None, scope="static", extra=()):
        argv = ["bash", str(READER), "evidence", "--repo", str(self.repo), "--scope", scope, *extra]
        if report is not None or raw is not None:
            path = self.root / "report.json"
            path.write_text(raw if raw is not None else json.dumps(report))
            argv += ["--report", str(path)]
        if exit is not None:
            argv += ["--exit", str(exit)]
        if criteria is not None:
            path = self.root / "criteria.json"
            path.write_text(json.dumps(criteria))
            argv += ["--criteria", str(path)]
        result = subprocess.run(argv, capture_output=True, text=True, timeout=60)
        self.assertIn(result.returncode, (0, 1, 3), result.stderr)
        return result.returncode, json.loads(result.stdout)

    def assert_no_current_pass(self, code, doc):
        self.assertNotEqual(code, 0)
        self.assertFalse(doc["currentPass"])
        self.assertNotIn("supported", [c["claim"] for c in doc["criteria"]])

    def by_id(self, doc):
        return {c["id"]: c for c in doc["criteria"]}

    # A positive control, so the rejections below mean something.
    def test_honest_current_report_supports_its_criteria(self):
        for files in (True, "artifact"):
            code, doc = self.read(self.report(files=files), exit=0)
            self.assertEqual(code, 0, doc)
            self.assertTrue(doc["currentPass"])
            self.assertEqual(doc["identity"]["relevance"], "current")
            self.assertEqual({c["claim"] for c in doc["criteria"]}, {"supported"})

    # Malformed, stale, mismatched, zero-case and lying reports cannot establish a current pass.
    def test_malformed_report_establishes_nothing(self):
        for raw in ("not json at all", json.dumps({"contract": "control/0", "status": "passed", "exit": 0})):
            code, doc = self.read(raw=raw, criteria={"summary shows": [RETURN]})
            self.assert_no_current_pass(code, doc)
            self.assertEqual(code, 1)
            self.assertFalse(doc["report"]["valid"])
            self.assertEqual(doc["criteria"][0]["status"], "unrun")

    def test_zero_case_and_lying_reports_are_rejected(self):
        zero = self.report(checks=[self.check("passed", [], [])])
        skipped_expected = self.report(checks=[self.check("passed", [RETURN, EMPTY], [RETURN])])
        hides_failure = self.report(checks=[self.check("passed", [EMPTY], [EMPTY]), self.check("failed", [RETURN], [RETURN], cid="e2e")])
        hides_prerequisite = self.report(prerequisites=[{"need": "chromium", "status": "missing", "detail": "not installed"}])
        for report, exit in ((zero, 0), (skipped_expected, 0), (hides_failure, 0), (hides_prerequisite, 0), (self.report(), 1)):
            code, doc = self.read(report, exit=exit, criteria={"summary shows": [RETURN]})
            self.assert_no_current_pass(code, doc)
            self.assertFalse(doc["report"]["valid"], doc["report"])

    def test_mismatched_identity_cannot_pass(self):
        code, doc = self.read(self.report(head="0" * 40), exit=0)
        self.assert_no_current_pass(code, doc)
        self.assertEqual(doc["identity"]["relevance"], "stale")
        code, doc = self.read(self.report(), exit=0, extra=("--digest", "f" * 64))
        self.assert_no_current_pass(code, doc)
        self.assertEqual(doc["identity"]["relevance"], "stale")
        self.assertEqual(doc["identity"]["reviewed"]["digest"], "f" * 64)

    def test_doctored_file_list_and_missing_identity_stay_unknown(self):
        code, doc = self.read(self.report(digest="e" * 64), exit=0)
        self.assert_no_current_pass(code, doc)
        self.assertEqual(doc["identity"]["relevance"], "unknown")
        code, doc = self.read(self.report(files=False), exit=0)
        self.assert_no_current_pass(code, doc)
        self.assertEqual(doc["identity"]["relevance"], "unknown")
        self.assertIn("same HEAD alone", doc["identity"]["detail"])

    # Same HEAD with changed relevant bytes does not establish identity.
    def test_same_head_with_changed_checked_bytes_is_stale(self):
        report = self.report()
        self.write("src/briefing.txt", "edited after the run\n")
        code, doc = self.read(report, exit=0)
        self.assert_no_current_pass(code, doc)
        self.assertEqual(doc["identity"]["relevance"], "stale")
        self.assertEqual(doc["identity"]["changed"], ["src/briefing.txt"])
        self.assertEqual(doc["identity"]["reviewed"]["head"], self.head)
        (self.repo / "src/briefing.txt").chmod(0o600)
        self.write("src/briefing.txt", "return summary\n")
        self.assertEqual(self.read(report, exit=0)[1]["identity"]["changed"], ["src/briefing.txt"])

    def test_unchecked_file_edit_keeps_identity_current(self):
        report = self.report()
        self.write("README.md", "edited, but no check read it\n")
        code, doc = self.read(report, exit=0)
        self.assertEqual(code, 0, doc)
        self.assertEqual(doc["identity"]["relevance"], "current")

    # Each criterion keeps its own coverage.
    def test_each_criterion_keeps_its_own_coverage(self):
        report = self.report(status="failed", exit=1, checks=[self.check("failed", [RETURN, EMPTY], [RETURN, EMPTY], failed=[RETURN])])
        criteria = {"summary shows": [RETURN], "empty account": [EMPTY], "no scenario": [], "partly covered": [EMPTY, "browser.empty-state"]}
        code, doc = self.read(report, exit=1, criteria=criteria)
        self.assertEqual(code, 1)
        got = self.by_id(doc)
        self.assertEqual((got["summary shows"]["status"], got["summary shows"]["claim"]), ("failed", "contradicted"))
        self.assertEqual((got["empty account"]["status"], got["empty account"]["claim"]), ("passed", "supported"))
        self.assertEqual((got["no scenario"]["status"], got["no scenario"]["claim"]), ("unrun", "unverified"))
        self.assertEqual((got["partly covered"]["status"], got["partly covered"]["claim"]), ("unrun", "unverified"))
        self.assertIn("no check", got["partly covered"]["reason"])

    # Missing prerequisites become blocked; unfinished and cancelled checks stay unrun with reasons.
    def test_missing_prerequisite_is_blocked(self):
        report = self.report(status="incomplete", exit=3,
                             prerequisites=[{"need": "chromium", "status": "missing", "detail": "browser did not launch"}],
                             checks=[self.check("blocked", [RETURN], [], reason="chromium is missing", cid="e2e"),
                                     self.check("not_run", [EMPTY], [], reason="earlier check was blocked")])
        code, doc = self.read(report, exit=3)
        self.assertEqual(code, 3)
        for criterion in doc["criteria"]:
            self.assertEqual((criterion["status"], criterion["claim"]), ("blocked", "unverified"))
            self.assertIn("chromium", criterion["reason"])

    def test_unfinished_and_cancelled_checks_stay_unrun_with_reasons(self):
        timed_out = self.report(status="incomplete", exit=3, checks=[self.check("timed_out", [RETURN], [], reason="runner exceeded 120s")])
        cancelled = self.report(status="cancelled", exit=130, checks=[self.check("cancelled", [RETURN], [], reason="SIGINT while running")])
        for report, exit, reason in ((timed_out, 3, "runner exceeded 120s"), (cancelled, 130, "SIGINT while running")):
            code, doc = self.read(report, exit=exit)
            self.assertEqual(code, 3)
            self.assertEqual((doc["criteria"][0]["status"], doc["criteria"][0]["claim"]), ("unrun", "unverified"))
            self.assertIn(reason, doc["criteria"][0]["reason"])

    # Individual failed checks survive an overall incomplete run.
    def test_failed_check_survives_incomplete_run(self):
        checks = [self.check("failed", [RETURN], [RETURN], failed=[RETURN], reason="summary missing"),
                  self.check("passed", [EMPTY], [EMPTY], cid="api")]
        code, doc = self.read(self.report(status="incomplete", exit=3, checks=checks), exit=3)
        got = self.by_id(doc)
        self.assertEqual((got[RETURN]["status"], got[RETURN]["claim"]), ("failed", "contradicted"))
        self.assertEqual(got[EMPTY]["status"], "unrun")
        self.assertIn("prove no behavior", got[EMPTY]["reason"])
        self.assertEqual(code, 1)
        code, doc = self.read(self.report(status="incomplete", exit=3, checks=checks, source_changed=True), exit=3)
        self.assertEqual(doc["identity"]["relevance"], "unknown")
        got = self.by_id(doc)
        self.assertEqual((got[RETURN]["status"], got[RETURN]["claim"]), ("failed", "unverified"))
        self.assertEqual(code, 3)

    # Control commands count as project execution; scope and pointer state decide what may run.
    def test_static_scope_runs_nothing_and_offers_nothing_to_run(self):
        code, doc = self.read(criteria={"summary shows": [RETURN]})
        self.assertEqual(code, 3)
        self.assertEqual(doc["control"]["state"], "present")
        self.assertFalse(doc["execution"]["authorized"])
        self.assertEqual(doc["execution"]["rerun"], [])
        self.assertIn("list, describe and --plan", doc["execution"]["reason"])
        self.assertEqual(doc["criteria"][0]["status"], "unrun")

    def test_local_scope_names_the_control_run_without_running_it(self):
        report = self.report()
        self.write("src/briefing.txt", "edited after the run\n")
        code, doc = self.read(report, exit=0, scope="local")
        self.assertTrue(doc["execution"]["authorized"])
        self.assertEqual(doc["execution"]["rerun"], [["bash", "scripts/control.sh", "feature", "briefing", "--json"]])
        self.assertIn("no push, tracker write", doc["execution"]["reason"])

    def test_absent_and_broken_pointers_use_existing_guidance(self):
        self.write("CLAUDE.md", "# Demo\n\n## Agent skills\n\nValidation: `make test`\n")
        code, doc = self.read(criteria={"summary shows": [RETURN]}, scope="local")
        self.assertEqual(doc["control"]["state"], "absent")
        self.assertFalse(doc["execution"]["authorized"])
        self.assertIn("existing guidance", doc["execution"]["guidance"])
        self.assertEqual((doc["criteria"][0]["status"], doc["criteria"][0]["claim"]), ("unrun", "unverified"))
        self.write("CLAUDE.md", "# Demo\n\n## Agent skills\n\nControl: skills/missing/SKILL.md\n")
        code, doc = self.read(scope="local")
        self.assertEqual(doc["control"]["state"], "broken")
        self.assertIn("skills/missing/SKILL.md", doc["control"]["detail"])
        self.assertFalse(doc["execution"]["authorized"])


if __name__ == "__main__":
    unittest.main()
