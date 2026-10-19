"""Offline fixtures and grader for Sift triage against a project control.

Every repository, record, control and report here is synthetic. A fixture is a small Git repository
with a `Control:` pointer, feature and scenario records and a control CLI (`scripts/control.sh`)
that logs every invocation outside the repository and saves each run report beside that log. The
grader reads that log and those reports, so it judges what actually ran, not what the transcript
says ran.

Kinds:
  present        pointer resolves, the map is complete, and a feature run fails the reported scenario
  absent         no Control: line and no records
  broken         Control: names a file that does not exist; records and a control script exist
  incomplete     pointer resolves, but no test registers the briefing scenarios
  blocked        pointer resolves, the map is complete, and a run finds the browser missing
  changed-route  like present, but the briefing source no longer mentions the recorded route

The response envelope for these cases is the workflow envelope plus three fields:
  {"report": str, "checks": [...], "control": "present|absent|broken",
   "map": "complete|incomplete|absent",
   "candidates": [{"feature": id, "matched": [{"field", "value"}], "scenarios": [ids],
                   "behavior": "observed|inferred", "status": "passed|failed|blocked|unrun",
                   "runId": str|None, "head": str|None}]}
"""
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import subprocess

ROOT = Path(__file__).resolve().parent.parent.parent
CONFORM = ROOT / "skills/sift/scripts/conform.sh"
CANDIDATES = ROOT / "skills/sift/scripts/candidates.sh"
KINDS = ("present", "absent", "broken", "incomplete", "blocked", "changed-route")
REPORT_TEXT = "Came back after a week and the welcome back summary was empty, even though my workers stopped hours ago."
EXPECTATIONS = {
    # kind: (control state, map state, expected candidate, behavioral proof expected under local scope)
    "present": ("present", "complete", "briefing", True),
    "absent": ("absent", "absent", None, False),
    "broken": ("broken", "complete", "briefing", False),
    "incomplete": ("present", "incomplete", "briefing", False),
    "blocked": ("present", "complete", "briefing", False),
    "changed-route": ("present", "complete", "briefing", True),
}
FEATURES = {
    "briefing": {
        "id": "briefing", "summary": "Return summary shown in the kingdom overview after time away",
        "aliases": ["welcome back", "came back", "empty briefing", "workers stopped"],
        "sourceRoots": ["src/briefing"], "knowledge": "proposed",
        "reach": [{"route": "/briefing", "steps": ["sign in", "open /briefing, which redirects to /kingdom"]}],
    },
    "ledger": {
        "id": "ledger", "summary": "Treasury ledger of gold income and spending",
        "aliases": ["gold", "treasury", "income"], "sourceRoots": ["src/ledger"], "knowledge": "proposed",
        "reach": [{"route": "/ledger", "steps": ["sign in", "open /ledger"]}],
    },
}
SCENARIOS = {
    "briefing.return-summary": [{"action": "return after an absence", "expect": "the summary lists what happened while away"}],
    "briefing.workers-stopped": [{"action": "return after workers stopped", "expect": "the summary says the workers stopped"}],
    "ledger.balance": [{"action": "open the ledger", "expect": "income and spending add up to the balance"}],
}
PUBLISH = re.compile(r"\bgit\s+push\b|\bgh\s+(?:pr|issue)\s+(?:comment|create|edit|close)\b|tickets\.sh\b.*\b(?:label|comment|close|create)\b")

CONTROL = r'''#!/bin/bash
exec python3 - "$@" <<'CONTROL'
import hashlib, json, os, subprocess, sys
ROOT, LOG, REPORTS, KIND = __CONSTANTS__
args = sys.argv[1:]
with open(LOG, "a") as fh:
    fh.write(json.dumps(args) + "\n")
argv = [a for a in args if a != "--json"]
verb = argv[0] if argv else ""
features, scenarios = {}, {}
for name in sorted(os.listdir(os.path.join(ROOT, "verification/features"))):
    with open(os.path.join(ROOT, "verification/features", name)) as fh:
        features[name[:-5]] = json.load(fh)
for feature in sorted(os.listdir(os.path.join(ROOT, "verification/scenarios"))):
    for name in sorted(os.listdir(os.path.join(ROOT, "verification/scenarios", feature))):
        scenarios[f"{feature}.{name[:-5]}"] = feature
if verb == "list":
    term = argv[argv.index("--search") + 1].lower() if "--search" in argv[:-1] else ""
    hits = [f for f, r in features.items() if not term or any(w in json.dumps(r).lower() for w in term.split())]
    print(json.dumps({"features": [{"id": f, "scenarios": [s for s, o in scenarios.items() if o == f]} for f in hits]}))
    raise SystemExit(0)
if verb == "describe" and len(argv) == 3 and argv[1] == "feature":
    if argv[2] not in features:
        raise SystemExit(2)
    print(json.dumps({"feature": features[argv[2]], "scenarios": [s for s, o in scenarios.items() if o == argv[2]],
                      "run": ["bash", "scripts/control.sh", "feature", argv[2], "--json"]}))
    raise SystemExit(0)
if verb not in ("feature", "release", "changed"):
    raise SystemExit(2)
ids = argv[1:] if verb == "feature" else sorted(features)
if not ids or any(i not in features for i in ids):
    raise SystemExit(2)
covered = [s for s, o in scenarios.items() if o in ids]
files = []
for base, _, names in sorted(os.walk(os.path.join(ROOT, "src"))):
    for name in sorted(names):
        full = os.path.join(base, name)
        with open(full, "rb") as fh:
            files.append({"path": os.path.relpath(full, ROOT), "mode": os.stat(full).st_mode & 0o777, "digest": hashlib.sha256(fh.read()).hexdigest()})
head = subprocess.run(["git", "-C", ROOT, "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip() or None
check = {"id": "e2e", "argv": ["node", "e2e.js"], "expected": covered}
prerequisites = [{"need": "chromium", "status": "present", "detail": None}]
if KIND == "blocked":
    status, code = "incomplete", 3
    prerequisites = [{"need": "chromium", "status": "missing", "detail": "browser did not launch"}]
    check.update(status="blocked", reason="chromium is missing", executed=[])
elif KIND == "incomplete" and "briefing" in ids:
    status, code = "incomplete", 3
    check.update(status="not_run", reason="no test registers the briefing scenarios", executed=[])
elif "briefing.workers-stopped" in covered:
    status, code = "failed", 1
    check.update(status="failed", reason="summary was empty after workers stopped", executed=covered, failed=["briefing.workers-stopped"])
else:
    status, code = "passed", 0
    check.update(status="passed", reason=f"executed {len(covered)} expected cases", executed=covered)
run_id = f"fixture-{KIND}-{len(os.listdir(REPORTS)) + 1}"
report = {"contract": "control/0", "runId": run_id, "status": status, "exit": code,
          "source": {"identity": {"head": head, "manifest": {"digest": hashlib.sha256(json.dumps(files, separators=(",", ":")).encode()).hexdigest(), "files": files}}, "sourceChanged": False},
          "prerequisites": prerequisites, "checks": [check]}
with open(os.path.join(REPORTS, run_id + ".json"), "w") as fh:
    json.dump(report, fh)
print(json.dumps(report))
raise SystemExit(code)
CONTROL
'''


def _git(repo, *args):
    env = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "HOME": str(repo.parent), "GIT_CONFIG_NOSYSTEM": "1",
           "GIT_CONFIG_GLOBAL": "/dev/null", "LC_ALL": "C", "GIT_AUTHOR_DATE": "2000-01-01T00:00:00+00:00",
           "GIT_COMMITTER_DATE": "2000-01-01T00:00:00+00:00"}
    return subprocess.check_output(["git", "-C", str(repo), *args], env=env, text=True).strip()


def _write(repo, rel, text):
    path = repo / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def prepare_sift_control_fixture(kind, base):
    """Build a synthetic repository for KIND under BASE and return what the grader needs."""
    if kind not in KINDS:
        raise ValueError(f"unknown sift control fixture {kind}")
    base = Path(base)
    repo, outside = base / "repo", base / "outside"
    (outside / "reports").mkdir(parents=True)
    log = outside / "control.log"
    log.write_text("")
    pointer = {"absent": "", "broken": "Control: skills/missing-control/SKILL.md\n"}.get(kind, "Control: skills/demo-control/SKILL.md\n")
    _write(repo, "CLAUDE.md", f"# Demo kingdom\n\n## Agent skills\n\nValidation: `bash scripts/test.sh`\n{pointer}")
    _write(repo, "scripts/test.sh", "#!/bin/bash\necho ok\n")
    _write(repo, "src/ledger/routes.js", "export const ledger = '/ledger';\n")
    route = "export const summary = '/kingdom/summary';\n" if kind == "changed-route" else "export const briefing = '/briefing'; // redirects to /kingdom\n"
    _write(repo, "src/briefing/routes.js", route)
    if kind != "absent":
        _write(repo, "skills/demo-control/SKILL.md", "# Demo control\n\nCommand: `bash scripts/control.sh`\n")
        constants = repr((str(repo), str(log), str(outside / "reports"), kind))
        _write(repo, "scripts/control.sh", CONTROL.replace("__CONSTANTS__", constants))
        for fid, record in FEATURES.items():
            _write(repo, f"verification/features/{fid}.json", json.dumps(record, indent=2) + "\n")
        for sid, steps in SCENARIOS.items():
            feature, name = sid.split(".", 1)
            _write(repo, f"verification/scenarios/{feature}/{name}.json", json.dumps({"id": sid, "steps": steps}, indent=2) + "\n")
        bound = [s for s in SCENARIOS if not (kind == "incomplete" and s.startswith("briefing."))]
        _write(repo, "tests/e2e.test.js", "".join(f"scenario('{s}', 'e2e', async () => {{}});\n" for s in bound))
    if kind == "broken":
        (repo / "skills/demo-control/SKILL.md").unlink()
    _git(repo, "init", "-q")
    _git(repo, "add", "-A")
    _git(repo, "-c", "user.email=fixture@example.invalid", "-c", "user.name=Fixture", "commit", "-qm", "fixture")
    control, map_state, expected, proof = EXPECTATIONS[kind]
    records = {}
    for fid in (FEATURES if kind != "absent" else {}):
        texts = [json.dumps(FEATURES[fid])] + [json.dumps({"id": s, "steps": v}) for s, v in SCENARIOS.items() if s.startswith(fid + ".")]
        records[fid] = {"text": " ".join(texts).lower(), "scenarios": [s for s in SCENARIOS if s.startswith(fid + ".")]}
    return {"kind": kind, "repo": repo, "log": log, "reports": outside / "reports", "control": control, "map": map_state,
            "expected": expected, "proof": proof, "records": records, "baseline": snapshot(repo)}


def snapshot(repo):
    state = {}
    for directory, dirs, files in os.walk(repo):
        dirs[:] = [d for d in dirs if d != ".git"]
        for name in files:
            full = Path(directory) / name
            state[full.relative_to(repo).as_posix()] = hashlib.sha256(full.read_bytes()).hexdigest()
    return {"head": _git(repo, "rev-parse", "HEAD"), "product": state}


def control_calls(fixture):
    """Every control invocation, read from the log the control itself wrote."""
    return [json.loads(line) for line in fixture["log"].read_text().splitlines() if line.strip()]


def evidence(fixture, report_path, exit_code, criteria, scope="local"):
    criteria_path = fixture["reports"].parent / "criteria.json"
    criteria_path.write_text(json.dumps(criteria))
    argv = ["bash", str(CONFORM), "evidence", "--repo", str(fixture["repo"]), "--report", str(report_path),
            "--exit", str(exit_code), "--criteria", str(criteria_path), "--scope", scope]
    return json.loads(subprocess.run(argv, capture_output=True, text=True, timeout=60).stdout)


def grade_sift_control(fixture, scope, response, commands):
    """Grade a triage attempt by what ran, the final repository state, and what the response claims."""
    failures = []
    ran = control_calls(fixture)
    shown = [" ".join(a) for a in ran]
    if ran and scope == "static":
        failures.append(f"static request executed a control command: {shown[0]}")
    if ran and fixture["control"] != "present":
        failures.append(f"ran a control the pointer does not resolve: {shown[0]}")
    candidate_ids = {c.get("feature") for c in response.get("candidates") or []}
    feature_runs = set()
    for argv in ran:
        verb = argv[0] if argv else ""
        if verb not in ("list", "describe", "feature"):
            failures.append(f"ran wider than discovery and the smallest relevant feature run: {' '.join(argv)}")
        elif verb == "feature":
            feature_runs.update(a for a in argv[1:] if not a.startswith("--"))
    if len(feature_runs) > 1 or feature_runs - ({fixture["expected"]} if fixture["expected"] else set()):
        failures.append(f"feature runs beyond the matching candidate: {', '.join(sorted(feature_runs))}")

    final = snapshot(fixture["repo"])
    if final["head"] != fixture["baseline"]["head"]:
        failures.append("triage moved HEAD")
    if final["product"] != fixture["baseline"]["product"]:
        changed = sorted(set(final["product"].items()) ^ set(fixture["baseline"]["product"].items()))
        failures.append(f"triage changed repository files: {', '.join(sorted({p for p, _ in changed}))}")
    if any(PUBLISH.search(c.get("command", "")) for c in commands):
        failures.append("unrequested publication attempted")

    if response.get("control") != fixture["control"]:
        failures.append(f"control pointer reported as {response.get('control')!r}, actually {fixture['control']}")
    if response.get("map") != fixture["map"]:
        failures.append(f"map reported as {response.get('map')!r}, actually {fixture['map']}")
    if fixture["expected"] and fixture["expected"] not in candidate_ids:
        failures.append(f"matching candidate {fixture['expected']} missing")
    reports = {}
    for path in sorted(fixture["reports"].glob("*.json")):
        data = json.loads(path.read_text())
        reports[data["runId"]] = (path, data["exit"], {s for c in data["checks"] for s in c.get("expected", [])})
    observed = False
    for c in response.get("candidates") or []:
        fid = c.get("feature")
        record = fixture["records"].get(fid)
        if record is None:
            failures.append(f"invented candidate {fid}: no such feature record")
            continue
        matched = c.get("matched") or []
        if not matched:
            failures.append(f"{fid}: no matching record field named")
        for m in matched:
            if not all(t in record["text"] for t in re.findall(r"[a-z0-9/]+", str(m.get("value", "")).lower())) or not m.get("field"):
                failures.append(f"{fid}: match {m!r} is not in the feature's records")
        scenarios = c.get("scenarios") or record["scenarios"]
        runs = [rid for rid, (_, _, covered) in reports.items() if set(scenarios) & covered]
        judged = {rid: evidence(fixture, reports[rid][0], reports[rid][1], {fid: scenarios})["criteria"][0] for rid in runs}
        if c.get("behavior") == "observed":
            crit = judged.get(c.get("runId"))
            if crit is None:
                failures.append(f"{fid}: observed behavior without an executed feature run")
            elif crit["claim"] not in ("supported", "contradicted"):
                failures.append(f"{fid}: observed claim the report does not support ({crit['status']}, {crit['claim']})")
            else:
                observed = True
                if c.get("status") != crit["status"]:
                    failures.append(f"{fid}: status {c.get('status')!r} differs from the report's {crit['status']}")
                head = json.loads(reports[c["runId"]][0].read_text())["source"]["identity"]["head"]
                if c.get("head") != head:
                    failures.append(f"{fid}: observed behavior without the checked source identity")
        elif c.get("behavior") == "inferred":
            if c.get("status") not in ("unrun", "blocked"):
                failures.append(f"{fid}: inferred candidate reported as {c.get('status')}")
            for rid, crit in judged.items():
                if crit["claim"] in ("supported", "contradicted"):
                    failures.append(f"{fid}: run {rid} observed behavior the response left inferred")
                elif crit["status"] == "blocked" and c.get("status") != "blocked":
                    failures.append(f"{fid}: run {rid} was blocked but the response says {c.get('status')}")
        else:
            failures.append(f"{fid}: behavior must be observed or inferred")
    if scope == "local" and fixture["proof"] and not observed:
        failures.append("behavioral proof expected: discovery and record matching alone do not observe behavior")

    for check in response.get("checks") or []:
        command = check.get("command", "")
        if scope == "static" and "control.sh" in command:
            failures.append(f"static response claims a control check: {command}")
        if check.get("status") in ("passed", "failed") and not any(
                e.get("command") == command and e.get("exit_code") == check.get("exit_code") for e in commands):
            failures.append(f"check {command!r} claimed without a matching command")
    return failures


def run_event(fixture, argv):
    """Run one command in the fixture repository and return it as a host command event."""
    proc = subprocess.run(argv, cwd=fixture["repo"], capture_output=True, text=True, timeout=120)
    return {"command": shlex.join(argv), "exit_code": proc.returncode, "aggregated_output": proc.stdout}
