#!/usr/bin/env bash
# Fixtures for skills/leyline/scripts/conform.sh. A fake control CLI misbehaves in each way the
# checker exists to catch, and every mode must fail for its own reason while the honest CLI passes.
set -euo pipefail
cd "$(dirname "$0")/.."

python3 - <<'PY'
import hashlib, json, os, pathlib, shutil, subprocess, tempfile

script = pathlib.Path("skills/leyline/scripts/conform.sh").resolve()

FAKE = r'''
import hashlib, json, os, sys, tempfile, time, uuid

mode = os.environ.get("FAKE_MODE", "honest")
args = [a for a in sys.argv[1:] if a != "--json"]
open("ran.marker", "a").write(" ".join(sys.argv[1:]) + "\n")
FEATURES = {"greet": ["greet.hello"]}


def emit(doc, code):
    print("> fake@1.0.0 verify")  # a package runner banner the checker must tolerate
    print(json.dumps(doc))
    sys.exit(code)


if args[:1] == ["list"]:
    feats = [] if mode == "list-missing" else [{"id": f, "scenarios": s} for f, s in FEATURES.items()]
    emit({"features": feats}, 0)
if args[:2] == ["describe", "feature"]:
    if args[2] not in FEATURES:
        sys.exit(2)
    emit({"id": args[2], "scenarios": FEATURES[args[2]]}, 0)
if args[:1] == ["feature"]:
    if args[1] not in FEATURES and mode != "unknown-ok":
        print("unknown feature", file=sys.stderr)
        sys.exit(2)
    if mode == "hang":
        time.sleep(60)
    if mode == "collide":
        lock = os.path.join(tempfile.gettempdir(), "leyline-fake-shared-port")
        try:
            os.mkdir(lock)
        except FileExistsError:
            sys.exit(1)
        time.sleep(1.5)
        os.rmdir(lock)
    text = open("src/greet.txt").read().strip()
    ok = text == "hello" or mode == "ignores-break"
    if mode == "scribble" and text != "hello":
        open("src/greet.txt", "a").write("scribbled\n")  # a run that edits the file its break patch touched
    executed = [] if mode == "zero" else ["greet.hello"]
    prereqs = [{"need": "browser", "status": "missing" if mode in ("blocked-pass", "incomplete") else "present", "detail": None}]
    check = {"id": "unit", "status": "passed" if ok else "failed", "reason": "ran the greeting test",
             "argv": ["python3", "tests/test_greet.py"], "expected": [] if mode == "zero" else ["greet.hello"], "executed": executed}
    status, code = ("passed", 0) if ok else ("failed", 1)
    if mode == "incomplete" or (mode == "break-incomplete" and text != "hello"):
        check["status"], status, code = "blocked", "incomplete", 3
    report = {"contract": "control/0", "runId": "run-1" if mode == "fixed-id" else uuid.uuid4().hex, "status": status, "exit": code,
              "source": {"identity": {"head": "abc123", "manifest": {"digest": hashlib.sha256(text.encode()).hexdigest()}}, "sourceChanged": False},
              "prerequisites": prereqs, "checks": [check]}
    if mode == "no-contract":
        del report["contract"]
    if mode == "lying":
        code = 0 if code == 1 else code
    emit(report, code)
sys.exit(2)
'''


def git(repo, *a):
    env = dict(os.environ, GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@example.com",
               GIT_COMMITTER_NAME="t", GIT_COMMITTER_EMAIL="t@example.com")
    return subprocess.run(["git", *a], cwd=repo, check=True, capture_output=True, text=True, env=env)


def conform(*a, env=None, code=None):
    env = dict(env or {}, TMPDIR=OUT_ROOT)  # the worktree and default report folder land in the fixture
    p = subprocess.run(["bash", str(script), *a], text=True, capture_output=True, env=dict(os.environ, **(env or {})))
    if code is not None and p.returncode != code:
        raise AssertionError((a, p.returncode, p.stdout[-3000:], p.stderr[-2000:]))
    return p


def write(repo, rel, text):
    path = repo / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def fixture(base):
    repo = base / "app"
    write(repo, "CLAUDE.md", "# App\n\n## Agent skills\n\nValidation: `python3 tests/test_greet.py`\nControl: `skills/app-control/SKILL.md`\n")
    write(repo, "skills/app-control/SKILL.md", "---\nname: app-control\n---\n\nCommand: `python3 tools/verify.py`\nFeatures: verification/features\nScenarios: verification/scenarios\nBindings: tests\nBreaks: verification/breaks\n")
    write(repo, "verification/features/greet.json", json.dumps({
        "id": "greet", "summary": "Say hello", "aliases": ["hello"], "sourceRoots": ["src/greet.txt"],
        "knowledge": "confirmed", "reach": [{"command": "app greet", "steps": ["Run it."]}]}))
    write(repo, "verification/scenarios/greet/hello.json", json.dumps({
        "id": "greet.hello", "steps": [{"action": "Run greet.", "expect": "It prints hello."}]}))
    write(repo, "tests/test_greet.py", "scenario('greet.hello', 'unit', lambda: None)\n")
    write(repo, "src/greet.txt", "hello\n")
    write(repo, "tools/verify.py", FAKE)
    write(repo, ".gitignore", "ran.marker\n")
    git(repo, "init", "-q")
    git(repo, "add", ".")
    git(repo, "commit", "-qm", "base")
    write(repo, "src/greet.txt", "goodbye\n")
    patch = git(repo, "diff").stdout
    git(repo, "checkout", "--", "src/greet.txt")
    write(repo, "verification/breaks/greet.hello.patch", patch)
    git(repo, "add", ".")
    git(repo, "commit", "-qm", "break patch")
    return repo


def rules(doc):
    return {f["rule"] for f in doc["findings"] if f["severity"] == "error"}


with tempfile.TemporaryDirectory(prefix="leyline-") as td:
    base = pathlib.Path(td)
    OUT_ROOT = str(base / "out")
    os.makedirs(OUT_ROOT)
    repo = fixture(base)

    # static: the honest fixture conforms and no project code runs.
    doc = json.loads(conform("static", str(repo), code=0).stdout)
    assert doc["conformant"] and doc["counts"] == {"features": 1, "scenarios": 1, "bindings": 1, "breaks": 1}, doc
    assert doc["control"]["keys"]["Command"] == "python3 tools/verify.py", doc["control"]
    assert not (repo / "ran.marker").exists(), "static ran project code"

    # static: each violation fails for its own rule.
    def violate(name, change, expected):
        copy = base / name
        shutil.copytree(repo, copy)
        change(copy)
        d = json.loads(conform("static", str(copy), code=1).stdout)
        assert expected in rules(d), (name, rules(d))

    def edit(rel, fn):
        return lambda r: (r / rel).write_text(fn((r / rel).read_text()))

    def edit_json(rel, fn):
        def run(r):
            data = json.loads((r / rel).read_text())
            fn(data)
            (r / rel).write_text(json.dumps(data))
        return run

    violate("no-pointer", edit("CLAUDE.md", lambda t: t.replace("Control:", "Controls:")), "control.pointer")
    violate("bad-pointer", edit("CLAUDE.md", lambda t: t.replace("app-control", "missing")), "control.pointer")
    violate("no-command", edit("skills/app-control/SKILL.md", lambda t: t.replace("Command:", "Cmd:")), "control.command")
    violate("no-knowledge", edit_json("verification/features/greet.json", lambda d: d.pop("knowledge")), "feature.knowledge")
    violate("bad-knowledge", edit_json("verification/features/greet.json", lambda d: d.update(knowledge="verified")), "feature.knowledge")
    violate("gone-root", edit_json("verification/features/greet.json", lambda d: d.update(sourceRoots=["src/nope.txt"])), "feature.source-roots")
    violate("bad-reach", edit_json("verification/features/greet.json", lambda d: d.update(reach=[{"steps": []}])), "feature.reach")
    violate("results", edit_json("verification/features/greet.json", lambda d: d.update(status="passed")), "record.results")
    violate("id-file", edit_json("verification/features/greet.json", lambda d: d.update(id="greeting")), "feature.id-file")
    violate("bad-json", edit("verification/features/greet.json", lambda t: t[:-2]), "feature.parse")
    violate("scenario-id", edit_json("verification/scenarios/greet/hello.json", lambda d: d.update(id="greet.hi")), "scenario.id-file")
    violate("no-steps", edit_json("verification/scenarios/greet/hello.json", lambda d: d.update(steps=[])), "scenario.steps")
    violate("unbound", edit("tests/test_greet.py", lambda t: t.replace("greet.hello", "greet.other")), "scenario.binding")
    violate("orphan-binding", edit("tests/test_greet.py", lambda t: t + "scenario('greet.ghost', 'unit', f)\n"), "scenario.orphan-binding")
    violate("orphan-break", lambda r: shutil.copy(r / "verification/breaks/greet.hello.patch", r / "verification/breaks/greet.gone.patch"), "break.orphan")
    violate("no-scenarios", lambda r: shutil.rmtree(r / "verification/scenarios/greet"), "feature.scenarios")

    # report: an honest report passes and each lie is caught.
    good = {"contract": "control/0", "runId": "r1", "status": "passed", "exit": 0,
            "source": {"identity": {"head": "abc", "manifest": {"digest": "d"}}, "sourceChanged": False},
            "prerequisites": [{"need": "browser", "status": "present"}],
            "checks": [{"id": "unit", "status": "passed", "reason": "ok", "argv": ["t"], "expected": ["s"], "executed": ["s"]}]}

    def report(doc, *extra, code):
        path = base / "report.json"
        path.write_text(doc if isinstance(doc, str) else json.dumps(doc))
        return json.loads(conform("report", str(path), *extra, code=code).stdout)

    assert report(good, code=0)["valid"]
    assert report(good, "--exit", "0", code=0)["valid"]

    def lie(fn, expected, *extra):
        bad = json.loads(json.dumps(good))
        fn(bad)
        d = report(bad, *extra, code=1)
        assert expected in rules(d), (expected, rules(d))

    lie(lambda d: d.pop("contract"), "report.contract")
    lie(lambda d: d.update(exit=1), "report.exit")
    lie(lambda d: d.update(status="failed", exit=1, checks=[dict(good["checks"][0], status="failed")]), "report.process-exit", "--exit", "0")
    lie(lambda d: d["checks"][0].update(executed=[], expected=[]), "report.judge-zero")
    lie(lambda d: d["checks"][0].update(expected=["s", "t"]), "report.judge-expected")
    lie(lambda d: d["prerequisites"][0].update(status="missing"), "report.judge-prerequisite")
    lie(lambda d: d["checks"].append(dict(good["checks"][0], id="e2e", status="blocked")), "report.judge-state")
    lie(lambda d: d.update(status="failed", exit=1), "report.judge-failed")
    lie(lambda d: d["source"].update(sourceChanged=True), "report.judge-source")
    lie(lambda d: d["source"].pop("identity"), "report.source")
    assert "report.parse" in rules(report("not json", code=1))

    # dynamic: refuses without consent, then probes the honest CLI end to end.
    p = conform("dynamic", str(repo), code=2)
    assert "--trust" in p.stderr, p.stderr

    def probes(mode, code, *extra):
        p = conform("dynamic", str(repo), "--trust", "--timeout", "20", *extra, env={"FAKE_MODE": mode}, code=code)
        d = json.loads(p.stdout)
        return {x["probe"]: x["status"] for x in d["probes"]}, d

    got, doc = probes("honest", 0)
    assert got == {"list": "passed", "describe": "passed", "unknown": "passed", "baseline": "passed",
                   "break": "passed", "restore": "passed", "parallel": "passed"}, got
    assert doc["feature"] == "greet"
    worktrees = git(repo, "worktree", "list").stdout.strip().splitlines()
    assert len(worktrees) == 1, worktrees
    assert not (repo / "ran.marker").exists(), "dynamic ran in the user's checkout instead of a worktree"

    assert probes("ignores-break", 1)[0]["break"] == "failed"
    assert probes("unknown-ok", 1)[0]["unknown"] == "failed"
    assert probes("list-missing", 1)[0]["list"] == "failed"
    assert probes("lying", 1)[0]["break"] == "failed"   # the lie only shows when the run fails
    assert probes("zero", 1)[0]["baseline"] == "failed"
    assert probes("blocked-pass", 1)[0]["baseline"] == "failed"
    assert probes("no-contract", 1)[0]["baseline"] == "failed"
    assert probes("fixed-id", 1)[0]["parallel"] == "failed"
    assert probes("collide", 1)[0]["parallel"] == "failed"
    got, _ = probes("incomplete", 3)
    assert got["baseline"] == "blocked" and got["break"] == "blocked", got
    got, _ = probes("hang", 1, "--timeout", "2")
    assert got["baseline"] == "failed", got
    assert len(git(repo, "worktree", "list").stdout.strip().splitlines()) == 1

    # dynamic: a break patch that cannot be reverted blocks the restore and parallel probes.
    got, _ = probes("scribble", 3)
    assert got["break"] == "passed" and got["restore"] == "blocked" and got["parallel"] == "blocked", got

    # dynamic: every probe input comes from HEAD, never from uncommitted records in the checkout.
    write(repo, "verification/features/extra.json", json.dumps({
        "id": "extra", "summary": "Only in the working copy", "aliases": [], "sourceRoots": ["src/greet.txt"],
        "knowledge": "proposed", "reach": [{"command": "app extra"}]}))
    got, doc = probes("honest", 0)
    assert got["list"] == "passed" and "excludedChanges" in doc, (got, doc)
    (repo / "verification/features/extra.json").unlink()

    # dynamic: uncommitted changes are named as excluded, never silently probed.
    (repo / "src/greet.txt").write_text("goodbye\n")
    _, doc = probes("honest", 0)
    assert "excludedChanges" in doc, doc
    git(repo, "checkout", "--", "src/greet.txt")

    # Regressions for the checker defects the Ultima refresh reproduced. Each case reports its own
    # failure so one run shows every defect that is still present.
    defects = []

    def regression(name, fn):
        try:
            fn()
            print(f"regression passed: {name}")
        except Exception as exc:
            defects.append(f"{name}: {exc!r}"[:600])
            print(f"regression failed: {name}: {exc!r}"[:600])

    def prepare_reason_on_stdout():
        copy = base / "prepare-stdout"
        shutil.copytree(repo, copy)
        write(copy, "tools/prepare.py", 'print("ERR_STORE_MISSING the package store is empty")\nraise SystemExit(1)\n')
        edit("skills/app-control/SKILL.md", lambda t: t + "Prepare: `python3 tools/prepare.py`\n")(copy)
        git(copy, "add", ".")
        git(copy, "commit", "-qm", "prepare reports on stdout")
        p = conform("dynamic", str(copy), "--trust", "--timeout", "20", code=3)
        d = json.loads(p.stdout)
        prep = next(x for x in d["probes"] if x["probe"] == "prepare")
        assert prep["status"] == "blocked", prep
        assert "ERR_STORE_MISSING" in prep.get("stdout", ""), prep

    def break_incomplete_is_blocked():
        p = conform("dynamic", str(repo), "--trust", "--timeout", "20", env={"FAKE_MODE": "break-incomplete"})
        d = json.loads(p.stdout)
        got = {x["probe"]: x["status"] for x in d["probes"]}
        assert got["baseline"] == "passed" and got["break"] == "blocked", got
        assert got["restore"] == "passed" and got["parallel"] == "passed", got
        assert p.returncode == 3, p.returncode

    def reports_retained_with_run_ids():
        def check_runs(d, out):
            assert not os.path.exists(d["worktree"]), "the worktree should be removed"
            assert d.get("retained") == str(out), (d.get("retained"), sorted(d))
            byprobe = {x["probe"]: x for x in d["probes"]}
            seen = set()
            for name, count in (("baseline", 1), ("break", 1), ("restore", 1), ("parallel", 2)):
                runs = byprobe[name].get("runs")
                assert isinstance(runs, list) and len(runs) == count, (name, byprobe[name])
                for run in runs:
                    path = pathlib.Path(run["report"])
                    assert path.parent == out and path.is_file(), run
                    data = path.read_bytes()
                    assert hashlib.sha256(data).hexdigest() == run["sha256"], run
                    assert run["runId"] and json.loads(data)["runId"] == run["runId"], run
                    seen.add(run["runId"])
            assert len(seen) == 5, seen
            assert sorted(x.name for x in out.iterdir()) == ["baseline.json", "break.json", "parallel-1.json", "parallel-2.json", "restore.json"], list(out.iterdir())

        d = json.loads(conform("dynamic", str(repo), "--trust", "--timeout", "20", code=0).stdout)
        assert d.get("retained"), sorted(d)
        check_runs(d, pathlib.Path(d["retained"]))
        out = (base / "retained").resolve()
        d = json.loads(conform("dynamic", str(repo), "--trust", "--timeout", "20", "--out", str(out), code=0).stdout)
        check_runs(d, out)
        p = conform("dynamic", str(repo), "--trust", "--out", str(out), code=2)
        assert "--out" in p.stderr, p.stderr

    def report_without_head_fails():
        bad = json.loads(json.dumps(good))
        del bad["source"]["identity"]["head"]
        d = report(bad, code=1)
        assert "report.source" in rules(d), rules(d)
        nulled = json.loads(json.dumps(good))
        nulled["source"]["identity"]["head"] = None
        assert report(nulled, code=0)["valid"]

    def restore_always_appears():
        got, _ = probes("incomplete", 3)
        assert got.get("restore") == "blocked", got
        p = conform("dynamic", str(base / "prepare-stdout"), "--trust", "--timeout", "20")
        names = [x["probe"] for x in json.loads(p.stdout)["probes"]]
        assert "restore" in names, names

    regression("1 blocked probe keeps stdout", prepare_reason_on_stdout)
    regression("2 incomplete break run is blocked", break_incomplete_is_blocked)
    regression("3 dynamic retains run ids and reports", reports_retained_with_run_ids)
    regression("4 missing source.identity.head fails", report_without_head_fails)
    regression("5 restore always appears", restore_always_appears)
    assert not defects, defects
    assert len(git(repo, "worktree", "list").stdout.strip().splitlines()) == 1

    # usage errors
    conform("nope", code=2)
    conform("report", code=2)
    conform("--help", code=0)

print("leyline conformance fixtures: ok")
PY
