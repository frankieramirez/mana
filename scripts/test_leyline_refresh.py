#!/usr/bin/env python3
"""Acceptance fixtures for the Leyline refresh stage.

Each test installs a generated control into a synthetic project with Leyline's own
generator, changes the project the way a person or a later commit would, and runs
`generate.sh refresh`. Refresh never executes project code. The challenge cases run
the real challenge.sh against the same synthetic project. Nothing here is a consumer.
"""

import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from leyline_challenge_fixture import GENERATOR, Fixture, write  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
CONFORM = ROOT / "skills/leyline/scripts/conform.sh"
SKILL_FILE = "skills/challenge-fixture-control/SKILL.md"
FEATURE = "verification/features/briefing.json"
CONFIG = "scripts/control-config.json"
LEDGER = "docs/agents/readiness.md"


class RefreshTests(unittest.TestCase):
    maxDiff = 6000

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="lr-")
        self.addCleanup(self.temp.cleanup)
        self.generator = GENERATOR

    def fixture(self, install=True, name="fx"):
        fixture = Fixture(Path(self.temp.name) / name).build(install=install)
        self.fx = fixture
        return fixture

    # Helpers ---------------------------------------------------------------------
    def run_cmd(self, argv, code=0, env=None):
        result = subprocess.run([str(a) for a in argv], cwd=self.fx.repo, capture_output=True, text=True,
                                env=dict(self.fx.env, **(env or {})), timeout=600)
        if code is not None:
            self.assertEqual(result.returncode, code, (argv, result.stdout[-4000:], result.stderr[-4000:]))
        return result

    def refresh(self, *extra, code=0, out=None, generator=None):
        out = out or Path(self.temp.name) / f"candidate-{len(list(Path(self.temp.name).glob('candidate-*')))}.json"
        result = self.run_cmd(["bash", generator or self.generator, "refresh", self.fx.repo, "--out", out, *extra], code=code)
        summary = json.loads(result.stdout) if code == 0 else None
        candidate = json.loads(Path(out).read_text()) if code == 0 else None
        return summary, candidate, out

    def apply(self, candidate_path, code=0, generator=None):
        result = self.run_cmd(["bash", generator or self.generator, "refresh", self.fx.repo, "--apply", candidate_path], code=code)
        return json.loads(result.stdout) if code == 0 else result

    def read(self, rel):
        return (self.fx.repo / rel).read_text()

    def commit(self, message):
        self.fx.git("add", "-A")
        self.fx.git("commit", "-qm", message)

    def bytes_state(self):
        repo = self.fx.repo
        state = {str(p.relative_to(repo)): p.read_bytes() for p in repo.rglob("*")
                 if p.is_file() and ".git" not in p.relative_to(repo).parts}
        state[".git/index"] = (repo / ".git/index").read_bytes()
        state[".git/HEAD"] = (repo / ".git/HEAD").read_bytes()
        state["resolved-head"] = self.fx.git("rev-parse", "HEAD").stdout
        return state

    def ids(self, summary):
        return {f["id"]: f["severity"] for f in summary["findings"]}

    def static(self):
        result = self.run_cmd(["bash", CONFORM, "static", self.fx.repo], code=None)
        return json.loads(result.stdout)

    def ledger_records(self):
        text = self.read(LEDGER)
        return [json.loads(body) for body in re.findall(r"<!-- leyline-(?:install|refresh):[0-9a-f]{64} -->\n## [^\n]*\n\n```json\n(.*?)```\n", text, re.S)]

    def assert_no_diff(self):
        before = self.bytes_state()
        summary, candidate, path = self.refresh()
        self.assertFalse(summary["diff"], summary)
        self.assertEqual(summary["writes"], [])
        self.assertFalse(summary["ledgerAppend"])
        applied = self.apply(path)
        self.assertEqual(applied["written"], [])
        self.assertEqual(self.bytes_state(), before, "a refresh with no material change wrote bytes")
        return summary

    def set_confirmed(self):
        record = json.loads(self.read(FEATURE))
        record["knowledge"] = "confirmed"
        write(self.fx.repo, FEATURE, json.dumps(record, indent=2) + "\n")
        self.commit("person confirms the briefing intent")

    # Criterion 1: unchanged input -------------------------------------------------
    def test_unchanged_refresh_is_no_diff_and_deterministic(self):
        self.fixture()
        index = (self.fx.repo / ".git/index").read_bytes()
        summary = self.assert_no_diff()
        self.assertEqual((self.fx.repo / ".git/index").read_bytes(), index, "a no-diff refresh rewrote the index")
        self.assertEqual(summary["state"], "unchanged")
        self.assertEqual(summary["findings"], [])
        again = self.assert_no_diff()
        self.assertEqual(again["candidateDigest"], summary["candidateDigest"])
        self.assertFalse(summary["executedProjectCode"])

    # Criterion 2: rename, deletion, configuration drift, stale bindings ------------
    def test_source_rename_is_a_focused_edit_then_no_diff(self):
        self.fixture()
        feature_before, config_before = json.loads(self.read(FEATURE)), json.loads(self.read(CONFIG))
        test_before = self.read("tests/hosted/briefing.test.mjs")
        self.fx.git("mv", "fixtures/ready.json", "fixtures/seed.json")
        before = self.bytes_state()
        summary, candidate, path = self.refresh()
        self.assertEqual(self.bytes_state(), before, "a refresh without --apply wrote to the checkout")
        self.assertEqual(summary["state"], "candidate")
        self.assertEqual(self.ids(summary), {"path-renamed:fixtures/ready.json": "proposed"})
        self.assertEqual(sorted(summary["writes"]), sorted([FEATURE, CONFIG, LEDGER]))
        for name in (FEATURE, CONFIG):
            changed = [line for line in candidate["edits"][name]["diff"].splitlines()
                       if line.startswith(("+", "-")) and not line.startswith(("+++", "---"))]
            self.assertTrue(changed and all("fixtures/" in line for line in changed), changed)
        self.apply(path)
        feature_before["sourceRoots"] = ["src/hosted", "fixtures/seed.json"]
        self.assertEqual(json.loads(self.read(FEATURE)), feature_before)
        config_before["sourceRoots"] = ["src/hosted", "fixtures/seed.json"]
        config_before["prerequisites"][0]["path"] = "fixtures/seed.json"
        self.assertEqual(json.loads(self.read(CONFIG)), config_before)
        self.assertEqual(self.read("tests/hosted/briefing.test.mjs"), test_before, "refresh edited a human-owned test")
        self.assertTrue(self.static()["conformant"])
        record = self.ledger_records()[-1]
        self.assertEqual(record["applied"], ["path-renamed:fixtures/ready.json"])
        self.assertEqual(self.assert_no_diff()["state"], "unchanged")

    def test_directory_rename_follows_source_roots_and_the_break_patch(self):
        self.fixture()
        self.fx.git("mv", "src/hosted", "src/app")
        summary, _candidate, path = self.refresh()
        self.assertEqual(self.ids(summary), {"path-renamed:src/hosted": "proposed",
                                             "break-renamed:verification/breaks/briefing.return-summary.patch": "proposed"})
        self.apply(path)
        self.assertEqual(json.loads(self.read(FEATURE))["sourceRoots"], ["src/app", "fixtures/ready.json"])
        self.fx.git("apply", "--check", "verification/breaks/briefing.return-summary.patch")
        self.assertIn("a/src/app/briefing.mjs", self.read("verification/breaks/briefing.return-summary.patch"))
        self.assertTrue(self.static()["conformant"])
        self.assert_no_diff()

    def test_a_break_patch_with_mnemonic_prefixes_follows_the_rename(self):
        self.fixture()
        patch = "verification/breaks/briefing.return-summary.patch"
        text = self.read(patch)
        mnemonic = re.sub(r"(?m)^(diff --git )a/(\S+) b/", r"\1i/\2 w/", text)
        mnemonic = re.sub(r"(?m)^--- a/", "--- i/", re.sub(r"(?m)^\+\+\+ b/", "+++ w/", mnemonic))
        self.assertNotEqual(mnemonic, text)
        write(self.fx.repo, patch, mnemonic)
        self.commit("break patch written under diff.mnemonicprefix")
        self.fx.git("mv", "src/hosted", "src/app")
        summary, _candidate, path = self.refresh()
        self.assertEqual(self.ids(summary)[f"break-renamed:{patch}"], "proposed")
        self.apply(path)
        self.fx.git("apply", "--check", patch)
        self.assertIn("i/src/app/briefing.mjs", self.read(patch))

    def test_ambiguous_copy_is_not_guessed_as_a_rename(self):
        self.fixture()
        seed = self.read("fixtures/ready.json")
        self.fx.git("rm", "-q", "fixtures/ready.json")
        write(self.fx.repo, "fixtures/a.json", seed)
        write(self.fx.repo, "fixtures/b.json", seed)
        before = self.bytes_state()
        summary, _candidate, path = self.refresh()
        self.assertEqual(self.ids(summary), {"source-root-missing:fixtures/ready.json": "needs_adjudication"})
        self.assertEqual(sorted(summary["findings"][0]["evidence"]["candidates"]), ["fixtures/a.json", "fixtures/b.json"])
        self.apply(path)
        after = self.bytes_state()
        self.assertEqual({k for k in after if after[k] != before.get(k)}, {LEDGER})

    def test_binding_rename_updates_only_the_marked_block(self):
        self.fixture()
        human = "\n## Team notes\n\nHuman paragraph kept byte for byte.\n"
        write(self.fx.repo, SKILL_FILE, self.read(SKILL_FILE) + human)
        self.commit("human notes in the control skill")
        self.fx.git("mv", "tests/hosted/briefing.test.mjs", "tests/hosted/return.test.mjs")
        summary, candidate, path = self.refresh()
        self.assertEqual(self.ids(summary), {"path-renamed:tests/hosted/briefing.test.mjs": "proposed",
                                             f"managed-update:{SKILL_FILE}": "proposed"})
        before = self.read(SKILL_FILE)
        self.apply(path)
        after = self.read(SKILL_FILE)
        self.assertTrue(after.endswith(human))
        self.assertIn("Bindings: tests/hosted/return.test.mjs\n", after)
        self.assertEqual(before.replace("tests/hosted/briefing.test.mjs", "tests/hosted/return.test.mjs"), after)
        config = json.loads(self.read(CONFIG))
        self.assertEqual(config["bindings"], ["tests/hosted/return.test.mjs"])
        self.assertEqual(config["runner"]["argv"][1], "tests/hosted/return.test.mjs")
        self.assertTrue(self.static()["conformant"])
        self.assert_no_diff()

    def test_route_rename_is_unresolved_and_the_record_is_kept(self):
        self.fixture()
        feature_bytes = self.read(FEATURE)
        server = self.read("src/hosted/server.mjs")
        write(self.fx.repo, "src/hosted/server.mjs", server.replace("'/kingdom'", "'/realm'"))
        summary, _candidate, path = self.refresh()
        self.assertEqual(self.ids(summary), {"route-missing:briefing:/kingdom": "needs_adjudication"})
        self.assertEqual(summary["writes"], [LEDGER])
        self.apply(path)
        self.assertEqual(self.read(FEATURE), feature_bytes)
        self.assert_no_diff()

    def test_route_deletion_keeps_confirmed_intent_unresolved(self):
        self.fixture()
        self.set_confirmed()
        feature_bytes = self.read(FEATURE)
        server = self.read("src/hosted/server.mjs")
        server = re.sub(r"  if \(url.pathname === '/briefing'\).*\n", "", server)
        server = re.sub(r"  if \(url.pathname === '/kingdom'\) \{\n(?:.*\n)*?  \}\n", "", server)
        write(self.fx.repo, "src/hosted/server.mjs", server)
        summary, _candidate, path = self.refresh()
        self.assertEqual(summary["state"], "unresolved")
        self.assertEqual(self.ids(summary), {"route-missing:briefing:/kingdom": "needs_adjudication"})
        self.assertEqual(summary["writes"], [LEDGER])
        self.apply(path)
        self.assertEqual(self.read(FEATURE), feature_bytes, "refresh edited a confirmed feature")
        record = self.ledger_records()[-1]
        self.assertEqual(record["findings"], [{"id": "route-missing:briefing:/kingdom", "kind": "route-missing", "severity": "needs_adjudication"}])
        self.assert_no_diff()

    def test_unrelated_route_swap_is_not_guessed_as_a_rename(self):
        self.fixture()
        self.set_confirmed()
        feature_bytes = self.read(FEATURE)
        server = self.read("src/hosted/server.mjs")
        server = server.replace("location: '/kingdom' + url.search", "location: '/health'")
        server = re.sub(r"  if \(url.pathname === '/kingdom'\) \{\n(?:.*\n)*?  \}\n",
                        "  if (url.pathname === '/billing') return response.end('unrelated billing page');\n", server)
        write(self.fx.repo, "src/hosted/server.mjs", server)
        summary, candidate, path = self.refresh()
        self.assertEqual(summary["state"], "unresolved")
        self.assertEqual(self.ids(summary), {"route-missing:briefing:/kingdom": "needs_adjudication"})
        self.assertNotIn(FEATURE, candidate["edits"])
        self.apply(path)
        self.assertEqual(self.read(FEATURE), feature_bytes, "refresh edited a confirmed feature")
        self.assertEqual(json.loads(self.read(FEATURE))["knowledge"], "confirmed")
        self.assert_no_diff()

    def test_feature_deletion_retains_record_and_names_every_gap(self):
        self.fixture()
        self.set_confirmed()
        feature_bytes = self.read(FEATURE)
        self.fx.git("rm", "-rq", "src/hosted", "fixtures/ready.json")
        summary, _candidate, path = self.refresh()
        ids = self.ids(summary)
        for key in ("source-root-missing:src/hosted", "source-root-missing:fixtures/ready.json",
                    "feature-implementation-missing:briefing"):
            self.assertEqual(ids.get(key), "needs_adjudication", ids)
        deleted = next(f for f in summary["findings"] if f["kind"] == "feature-implementation-missing")
        self.assertEqual(deleted["evidence"]["knowledge"], "confirmed")
        self.assertEqual(summary["writes"], [LEDGER])
        self.apply(path)
        self.assertEqual(self.read(FEATURE), feature_bytes)
        self.assert_no_diff()

    def test_stale_scenario_binding_is_unresolved_and_ids_are_stable(self):
        self.fixture()
        runner = self.read("tests/hosted/briefing.test.mjs")
        write(self.fx.repo, "tests/hosted/briefing.test.mjs",
              runner.replace("scenario('briefing.return-summary'", "scenario('briefing.welcome'"))
        before = self.bytes_state()
        summary, _candidate, path = self.refresh()
        self.assertEqual(self.ids(summary), {"binding-stale:briefing.return-summary": "needs_adjudication",
                                             "binding-orphan:briefing.welcome": "needs_adjudication"})
        self.apply(path)
        after = self.bytes_state()
        self.assertEqual({k for k in after if after[k] != before.get(k)}, {LEDGER})

    def test_configuration_drift_and_distinct_launch_profiles(self):
        self.fixture()
        launch = {"version": "0.0.1", "configurations": [
            {"name": "docs", "runtimeExecutable": "npm", "runtimeArgs": ["run", "docs"], "port": 5173},
            {"name": "app", "runtimeExecutable": "npm", "runtimeArgs": ["run", "dev"], "port": 5174}]}
        write(self.fx.repo, ".claude/launch.json", json.dumps(launch, indent=2) + "\n")
        notes = ("\n## Launch\n\nThe `docs` profile serves the documentation on port 5173.\n"
                 "The `app` profile serves the kingdom on port 5174.\n")
        write(self.fx.repo, SKILL_FILE, self.read(SKILL_FILE) + notes)
        self.commit("two launch profiles with distinct ports")
        summary = self.assert_no_diff()
        self.assertEqual(summary["state"], "unchanged", summary["findings"])
        self.assertEqual([p["port"] for p in summary["facts"]["launchProfiles"]], [5173, 5174])
        drift = ("The `app` profile listens on port 5173 for previews.\n"
                 "Open http://localhost:5180 after startup.\n")
        write(self.fx.repo, SKILL_FILE, self.read(SKILL_FILE) + drift)
        package = json.loads(self.read("package.json"))
        del package["scripts"]["verify"]
        write(self.fx.repo, "package.json", json.dumps(package, indent=2) + "\n")
        before = self.bytes_state()
        summary, _candidate, path = self.refresh()
        self.assertEqual(sorted(f["kind"] for f in summary["findings"]), ["command-missing", "port-drift", "port-drift"])
        self.assertTrue(all(f["severity"] == "needs_adjudication" for f in summary["findings"]))
        drift = {f["evidence"]["instructionPort"]: f["evidence"]["attribution"] for f in summary["findings"] if f["kind"] == "port-drift"}
        self.assertEqual(drift, {5173: "named", 5180: "no profile named"})
        self.apply(path)
        after = self.bytes_state()
        self.assertEqual({k for k in after if after[k] != before.get(k)}, {LEDGER},
                         "refresh edited a launch profile, the instructions or package.json")
        self.assertEqual(json.loads(self.read(".claude/launch.json")), launch)

    # Criterion 3: confirmed intent and human-owned runtime/tests survive -------------
    def generator_copy(self, edit, name="generator-copy"):
        copy = Path(self.temp.name) / name
        shutil.copytree(ROOT / "skills/leyline", copy)
        template = copy / "references/recipes/control.ts.template"
        template.write_text(edit(template.read_text()))
        return copy / "scripts/generate.sh"

    def test_hand_edited_runtime_and_tests_survive_a_generator_update(self):
        self.fixture()
        self.set_confirmed()
        runtime = self.read("scripts/control.ts").split("\n", 1)
        hand = runtime[0] + "\n// Hand-maintained: the team tuned this adapter.\n" + runtime[1]
        write(self.fx.repo, "scripts/control.ts", hand)
        test = self.read("tests/hosted/briefing.test.mjs") + "\n// human test note\n"
        write(self.fx.repo, "tests/hosted/briefing.test.mjs", test)
        self.commit("hand edits to runtime and tests")
        # A person confirming intent is already in history; refresh records nothing for it.
        self.assertEqual(self.assert_no_diff()["state"], "unchanged")
        updated = self.generator_copy(lambda text: text + "// generator update for refresh fixtures\n")
        summary, _candidate, path = self.refresh(generator=updated)
        self.assertEqual(self.ids(summary), {"runtime-update:scripts/control.ts": "proposed"})
        self.apply(path, generator=updated)
        merged = self.read("scripts/control.ts")
        self.assertIn("// Hand-maintained: the team tuned this adapter.\n", merged)
        self.assertTrue(merged.endswith("// generator update for refresh fixtures\n"))
        self.assertEqual(self.read("tests/hosted/briefing.test.mjs"), test)
        self.assertEqual(json.loads(self.read(FEATURE))["knowledge"], "confirmed")
        summary = self.assert_no_diff_with(updated)
        self.assertEqual(summary["state"], "unchanged")

    def test_a_second_generator_update_keeps_hand_edits(self):
        self.fixture()
        runtime = self.read("scripts/control.ts").split("\n", 1)
        write(self.fx.repo, "scripts/control.ts", runtime[0] + "\n// HAND EDIT\n" + runtime[1])
        self.commit("hand edit")
        first = self.generator_copy(lambda text: text + "// gen update 1\n", "generator-1")
        summary, _candidate, path = self.refresh(generator=first)
        self.assertEqual(self.ids(summary), {"runtime-update:scripts/control.ts": "proposed"})
        self.apply(path, generator=first)
        self.commit("apply refresh 1")
        self.assertIn("// HAND EDIT", self.read("scripts/control.ts"))
        second = self.generator_copy(lambda text: text + "// gen update 1\n// gen update 2\n", "generator-2")
        before = self.read("scripts/control.ts")
        summary, _candidate, path = self.refresh(generator=second)
        self.assertEqual(self.ids(summary), {"runtime-base-missing:scripts/control.ts": "needs_adjudication"})
        self.apply(path, generator=second)
        self.assertEqual(self.read("scripts/control.ts"), before, "the second update replaced hand-edited bytes")

    def assert_no_diff_with(self, generator):
        before = self.bytes_state()
        summary, _candidate, path = self.refresh(generator=generator)
        self.assertEqual(summary["writes"], [], summary)
        self.apply(path, generator=generator)
        self.assertEqual(self.bytes_state(), before)
        return summary

    def test_overlapping_runtime_edit_is_a_conflict_that_writes_nothing_but_the_ledger(self):
        self.fixture()
        hand = self.read("scripts/control.ts").replace("} catch (error) {", "} catch (error) { // team: keep errors terse", 1)
        write(self.fx.repo, "scripts/control.ts", hand)
        self.commit("hand edit near the end of the runtime")
        updated = self.generator_copy(lambda text: text.replace("} catch (error) {", "} catch (error) { // generator: report errors", 1))
        before = self.bytes_state()
        summary, candidate, path = self.refresh(generator=updated)
        self.assertEqual(summary["state"], "conflict")
        self.assertEqual(self.ids(summary), {"runtime-conflict:scripts/control.ts": "conflict"})
        self.assertIn("<<<<<<< project", candidate["findings"][0]["resolution"]["proposedMerge"])
        self.apply(path, generator=updated)
        after = self.bytes_state()
        self.assertEqual({k for k in after if after[k] != before.get(k)}, {LEDGER})
        self.assertEqual(self.read("scripts/control.ts"), hand)

    def test_managed_block_human_edit_conflicts_with_a_generated_change(self):
        self.fixture()
        skill = self.read(SKILL_FILE).replace("Breaks: verification/breaks\n", "Breaks: verification/breaks\nHuman note inside the markers.\n")
        write(self.fx.repo, SKILL_FILE, skill)
        self.commit("human edit inside the managed block")
        summary, _candidate, _path = self.refresh()
        self.assertEqual(self.ids(summary), {f"managed-section-edited:{SKILL_FILE}": "info"})
        self.fx.git("mv", "tests/hosted/briefing.test.mjs", "tests/hosted/return.test.mjs")
        before = self.bytes_state()
        summary, candidate, path = self.refresh()
        self.assertEqual(summary["state"], "conflict")
        self.assertEqual(self.ids(summary)[f"managed-conflict:{SKILL_FILE}"], "conflict")
        self.assertTrue(all(edit["withheld"] for name, edit in candidate["edits"].items() if name != LEDGER))
        self.apply(path)
        after = self.bytes_state()
        self.assertEqual({k for k in after if after[k] != before.get(k)}, {LEDGER})
        self.assertEqual(self.read(SKILL_FILE), skill)

    def test_green_challenge_records_evidence_and_never_confirms_intent(self):
        fixture = self.fixture()
        evidence = Path(self.temp.name) / "evidence-pass"
        code, doc, result = fixture.challenge(evidence=evidence)
        self.assertEqual(code, 0, (doc or {}).get("probes", result.stderr[-3000:]))
        feature_bytes = self.read(FEATURE)
        summary, _candidate, path = self.refresh("--challenge", evidence)
        self.assertEqual(summary["state"], "verified")
        self.assertTrue(summary["challenge"]["evidence"]["verified"])
        self.apply(path)
        self.assertEqual(self.read(FEATURE), feature_bytes)
        self.assertEqual(json.loads(self.read(FEATURE))["knowledge"], "proposed")
        record = self.ledger_records()[-1]
        self.assertEqual(record["state"], "verified")
        self.assertEqual(sorted(record["challengeRunIds"]), summary["challenge"]["runIds"])
        self.assertTrue(record["challengeRunIds"])
        # Committing the ledger record moves HEAD without changing the challenged bytes.
        self.commit("record the verified challenge")
        os.utime(self.fx.repo / "fixtures/ready.json", (1, 1))
        before = self.bytes_state()
        again, _candidate, path = self.refresh("--challenge", evidence)
        self.assertEqual(again["state"], "verified")
        self.assertEqual(again["writes"], [])
        self.apply(path)
        self.assertEqual(self.bytes_state(), before, "a no-diff challenge refresh rewrote the index or a file")

    # Criterion 4: interrupted setup and failed challenge keep recoverable state ------
    def test_failed_challenge_retains_evidence_and_the_pointer(self):
        fixture = self.fixture()
        config = json.loads(self.read(CONFIG))
        config["runner"]["argv"] = ["node", "-e", "process.exit(1)", "{report}"]
        write(fixture.repo, CONFIG, json.dumps(config, indent=2) + "\n")
        self.commit("runner instructions that cannot work")
        self.assertTrue(self.static()["conformant"], "the broken control must still be statically valid")
        evidence = Path(self.temp.name) / "evidence-fail"
        code, doc, _result = fixture.challenge("--only", "break", evidence=evidence)
        self.assertEqual(code, 1, (doc or {}).get("probes"))
        manifest_before = (evidence / "manifest.json").read_bytes()
        agents = self.read("AGENTS.md")
        summary, _candidate, path = self.refresh("--challenge", evidence)
        self.assertEqual(summary["state"], "failed")
        self.assertEqual(summary["challenge"]["outcome"], "failed")
        self.assertEqual(summary["challenge"]["probes"]["baseline"], "failed")
        self.assertTrue(summary["challenge"]["evidence"]["verified"])
        # Tampered evidence can never support a verdict.
        tampered = Path(self.temp.name) / "evidence-tampered"
        shutil.copytree(evidence, tampered)
        doc_path = tampered / "challenge.json"
        doc_path.write_text(doc_path.read_text().replace('"failed"', '"passed"'))
        forged, _c, _p = self.refresh("--challenge", tampered)
        self.assertFalse(forged["challenge"]["evidence"]["verified"])
        self.assertNotEqual(forged["state"], "verified")
        self.apply(path)
        record = self.ledger_records()[-1]
        self.assertNotEqual(record["state"], "verified")
        self.assertEqual(record["challenge"]["evidence"]["dir"], str(evidence.resolve()))
        self.assertEqual(record["challengeRunIds"], summary["challenge"]["runIds"])
        self.assertTrue(record["pending"])
        self.assertEqual((evidence / "manifest.json").read_bytes(), manifest_before)
        for item in json.loads(manifest_before)["files"]:
            self.assertTrue((evidence / item["path"]).is_file(), item)
        self.assertEqual(self.read("AGENTS.md"), agents, "a failed challenge removed the working pointer")
        self.assertIn("Control: " + SKILL_FILE, agents)

    def test_interrupted_install_is_reported_and_reinstall_finishes_it(self):
        fixture = self.fixture(install=False)
        injection = Path(self.temp.name) / "kill"
        injection.mkdir()
        write(injection, "sitecustomize.py", '''import os, signal
count = [0]
original = os.link
def link(source, destination, *args, **kwargs):
    result = original(source, destination, *args, **kwargs)
    count[0] += 1
    if count[0] == 3:
        os.kill(os.getpid(), signal.SIGKILL)
    return result
os.link = link
''')
        killed = self.run_cmd(["bash", GENERATOR, "install", fixture.repo, "--map", fixture.map_path], code=None,
                              env={"PYTHONPATH": str(injection)})
        self.assertNotEqual(killed.returncode, 0)
        absent = "verification/scenarios/briefing/no-activity.json"
        write(fixture.repo, absent, "human bytes written after the interruption\n")
        before = self.bytes_state()
        summary, _candidate, path = self.refresh("--map", fixture.map_path)
        self.assertEqual(summary["state"], "partial")
        partial = summary["partial"]
        self.assertEqual(len(partial["complete"]), 3, partial)
        self.assertIn(LEDGER, partial["absent"])
        self.assertIn("AGENTS.md", partial["absent"], "the Control pointer was activated before its targets")
        self.assertEqual([c["path"] for c in partial["conflicting"]], [absent])
        self.assertEqual(len(partial["recovery"]), 1, partial)
        self.assertTrue(any("rerun install" in line for line in partial["recoveryWork"]), partial)
        self.assertEqual(summary["writes"], [])
        self.apply(path, code=1)
        self.assertEqual(self.bytes_state(), before, "refresh wrote into an interrupted installation")
        # Following the recovery work: drop the partial outputs and staging file, then install again.
        for name in [absent, *partial["complete"], *partial["recovery"]]:
            (fixture.repo / name).unlink()
        self.run_cmd(["bash", GENERATOR, "install", fixture.repo, "--map", fixture.map_path])
        self.assertTrue(self.static()["conformant"])
        self.assertEqual(self.assert_no_diff()["state"], "unchanged")

    def test_forged_or_stale_candidates_are_refused(self):
        self.fixture()
        self.fx.git("mv", "fixtures/ready.json", "fixtures/seed.json")
        _summary, candidate, path = self.refresh()
        forged = json.loads(Path(path).read_text())
        forged["writes"][CONFIG]["text"] += "\n// a recomputed digest does not authorize other bytes\n"
        forged.pop("candidateDigest")
        forged["candidateDigest"] = hashlib.sha256(json.dumps(forged, sort_keys=True, separators=(",", ":"),
                                                              ensure_ascii=False).encode()).hexdigest()
        Path(path).write_text(json.dumps(forged))
        before = self.bytes_state()
        refused = self.apply(path, code=1)
        self.assertIn("changed since this refresh candidate", refused.stderr)
        self.assertEqual(self.bytes_state(), before)
        _summary, candidate, path = self.refresh()
        write(self.fx.repo, "human.txt", "a new human file after review\n")
        before = self.bytes_state()
        self.apply(path, code=1)
        self.assertEqual(self.bytes_state(), before)

    def test_missing_ledger_is_an_ownership_conflict(self):
        self.fixture()
        (self.fx.repo / LEDGER).unlink()
        before = self.bytes_state()
        summary, _candidate, path = self.refresh()
        self.assertEqual(summary["state"], "conflict")
        self.assertEqual(self.ids(summary), {"ownership:base-missing": "conflict"})
        self.apply(path)
        self.assertEqual(self.bytes_state(), before)


if __name__ == "__main__":
    if shutil.which("node") is None:
        raise SystemExit("Node is required for refresh fixtures")
    unittest.main(verbosity=2)
