#!/usr/bin/env bash
# conform.sh: check that a project's control CLI and feature map keep the control/0 contract.
#
#   static [REPO]
#       Read files only. Resolve the `Control:` line, the control skill's key lines, the
#       feature and scenario records, the scenario bindings in source, and the break patches.
#       Never runs project code, package managers, or git. Prints one JSON document with
#       every finding. Exit 0 when conformant, 1 when not.
#
#   report FILE [--exit N]
#       Validate a run report against the contract: required fields, the status and exit code
#       agreeing, and the judge rules (zero executed tests, a missing prerequisite, or an
#       unexecuted expected case is never a pass). --exit is the exit code the process that
#       wrote the report returned, and must match. Exit 0 when valid, 1 when not.
#
#   dynamic REPO --trust [--feature ID] [--timeout SECONDS] [--keep]
#       Run the project's control CLI in a disposable git worktree of HEAD and probe it: list,
#       describe, an unknown selector, a baseline run, a declared break patch that must fail
#       for its scenario, the restored run, and two concurrent runs. Runs project code, so it
#       refuses without --trust. Removes only the worktree it created. Exit 0 when every probe
#       passes, 1 when one fails, 3 when a probe is blocked and none failed.
#
# Exit 2 is a usage error and exit 4 means python3 is missing. Everything here is python3
# standard library inside bash; there is no jq, no node, no pip package.

set -euo pipefail

usage() {
  awk 'NR == 1 { next } /^#/ { sub(/^# ?/, ""); print; next } { exit }' "${BASH_SOURCE[0]}"
}

die() {
  echo "conform.sh: $*" >&2
  exit 2
}

need_python() {
  command -v python3 >/dev/null 2>&1 || { echo "conform.sh: python3 not found" >&2; exit 4; }
}

run_python() {
  need_python
  python3 - "$@" <<'PY'
import json, os, re, shlex, shutil, signal, subprocess, sys, tempfile, threading, time

CONTRACT = "control/0"
KNOWLEDGE = {"proposed", "confirmed", "unresolved"}
RUN_STATUS = {"passed": {0}, "failed": {1}, "incomplete": {3}, "cancelled": {130, 143}}
CHECK_STATES = {"passed", "failed", "unavailable", "timed_out", "cancelled", "blocked", "skipped", "not_run"}
NOT_PASSING = {"failed", "unavailable", "timed_out", "cancelled", "blocked"}
PREREQ_STATES = {"present", "missing", "not_probed"}
RESULT_KEYS = {"status", "result", "results", "passed", "lastRun", "verified", "outcome"}
ID = re.compile(r"^[a-z0-9][a-z0-9-]*(\.[a-z0-9][a-z0-9-]*)*$")
KEY_LINE = re.compile(r"^(Command|Prepare|Features|Scenarios|Bindings|Breaks):[ \t]*(.+?)[ \t]*$", re.M)
BINDING = re.compile(r"""[A-Za-z_$]*[sS]cenario\(\s*['"`]([^'"`]+)['"`]""")
SKIP_DIRS = {"node_modules", ".git", "dist", "build", ".scratch", ".next", "coverage", "vendor", "target", "__pycache__", ".venv", ".turbo"}
SOURCE_EXT = {".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs", ".mts", ".cts", ".py", ".go", ".rs", ".rb", ".sh", ".swift", ".kt", ".java", ".cs"}
DEFAULTS = {"Features": "verification/features", "Scenarios": "verification/scenarios", "Bindings": ".", "Breaks": "verification/breaks"}


def usage_error(message):
    print(f"conform.sh: {message}", file=sys.stderr)
    raise SystemExit(2)


def strip_ticks(value):
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] == "`":
        value = value[1:-1].strip()
    return value


class Findings:
    def __init__(self):
        self.items = []

    def add(self, rule, message, path=None, severity="error"):
        self.items.append({"rule": rule, "severity": severity, "path": path, "message": message})

    @property
    def errors(self):
        return [f for f in self.items if f["severity"] == "error"]


def inside(root, rel):
    full = os.path.realpath(os.path.join(root, rel))
    return full if full == root or full.startswith(root + os.sep) else None


def read_text(path):
    try:
        with open(path, encoding="utf-8") as fh:
            return fh.read()
    except (OSError, UnicodeDecodeError):
        return None


def agent_block(text):
    match = re.search(r"^## Agent skills[ \t]*$", text, re.M)
    if not match:
        return None
    rest = text[match.end():]
    end = re.search(r"^## ", rest, re.M)
    return rest[: end.start()] if end else rest


def resolve_control(root, findings):
    """Find the Control: line, then the control skill and its key lines."""
    control = {"agentFile": None, "skill": None, "keys": {}}
    block_file = None
    for name in ("CLAUDE.md", "AGENTS.md"):
        text = read_text(os.path.join(root, name))
        if text is not None and agent_block(text) is not None:
            block_file = (name, agent_block(text))
            break
    if block_file is None:
        findings.add("control.pointer", "no `## Agent skills` block in CLAUDE.md or AGENTS.md, so no Control: line to follow")
    else:
        control["agentFile"] = block_file[0]
        line = re.search(r"^Control:[ \t]*(.+?)[ \t]*$", block_file[1], re.M)
        if not line:
            findings.add("control.pointer", "the `## Agent skills` block has no Control: line", block_file[0])
        else:
            rel = strip_ticks(line.group(1))
            full = inside(root, rel)
            if not full or not os.path.isfile(full):
                findings.add("control.pointer", f"Control: points at {rel}, which is not a file inside the repo", block_file[0])
            else:
                control["skill"] = rel
                text = read_text(full) or ""
                for key, value in KEY_LINE.findall(text):
                    control["keys"].setdefault(key, strip_ticks(value))
                if "Command" not in control["keys"]:
                    findings.add("control.command", "the control skill has no `Command:` line naming the CLI prefix", rel)
    for key, value in DEFAULTS.items():
        control["keys"].setdefault(key, value)
    return control


def load_json(path, findings, rule, rel):
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError) as exc:
        findings.add(rule, f"does not parse as JSON: {exc}", rel)
        return None
    if not isinstance(data, dict):
        findings.add(rule, "is not a JSON object", rel)
        return None
    return data


def str_list(value):
    return isinstance(value, list) and all(isinstance(v, str) and v for v in value)


def source_files(base):
    if os.path.isfile(base):
        yield base
        return
    for dirpath, dirnames, filenames in os.walk(base):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS and not os.path.islink(os.path.join(dirpath, d))]
        for name in filenames:
            yield os.path.join(dirpath, name)


def scan_bindings(root, roots):
    found = {}
    for rel in roots:
        base = inside(root, rel)
        if not base or not os.path.exists(base):
            continue
        for path in source_files(base):
            if os.path.splitext(path)[1] not in SOURCE_EXT:
                continue
            try:
                if os.path.getsize(path) > 2_000_000:
                    continue
            except OSError:
                continue
            text = read_text(path)
            for match in BINDING.finditer(text or ""):
                where = os.path.relpath(path, root)
                if where not in found.setdefault(match.group(1), []):
                    found[match.group(1)].append(where)
    return found


def check_static(root):
    findings = Findings()
    control = resolve_control(root, findings)
    keys = control["keys"]
    features, scenarios = {}, {}

    fdir = inside(root, keys["Features"])
    if not fdir or not os.path.isdir(fdir):
        findings.add("feature.none", f"no feature records directory at {keys['Features']}")
    else:
        for name in sorted(os.listdir(fdir)):
            if not name.endswith(".json"):
                continue
            rel = os.path.relpath(os.path.join(fdir, name), root)
            data = load_json(os.path.join(fdir, name), findings, "feature.parse", rel)
            if data is None:
                continue
            fid = data.get("id")
            if not isinstance(fid, str) or not ID.match(fid):
                findings.add("feature.fields", "id must be a lowercase dotted identifier", rel)
                continue
            if fid != name[:-5]:
                findings.add("feature.id-file", f"id {fid} does not match the file name", rel)
            if fid in features:
                findings.add("feature.duplicate", f"id {fid} is also defined in {features[fid]['path']}", rel)
                continue
            features[fid] = {"path": rel, "data": data}
            for field in ("summary",):
                if not isinstance(data.get(field), str) or not data[field].strip():
                    findings.add("feature.fields", f"{field} must be a non-empty string", rel)
            if not isinstance(data.get("aliases"), list) or not all(isinstance(a, str) for a in data.get("aliases", [])):
                findings.add("feature.fields", "aliases must be a list of strings", rel)
            roots = data.get("sourceRoots")
            if not isinstance(roots, list) or (roots and not str_list(roots)):
                findings.add("feature.fields", "sourceRoots must be a list of paths", rel)
            elif not roots:
                findings.add("feature.source-roots", "sourceRoots is empty, so changed-file selection and refresh cannot see this feature's code unless the CLI derives it", rel, "warn")
            else:
                for src in roots:
                    full = inside(root, src)
                    if not full or not os.path.exists(full):
                        findings.add("feature.source-roots", f"sourceRoots entry {src} does not exist", rel)
            if data.get("knowledge") not in KNOWLEDGE:
                findings.add("feature.knowledge", "knowledge must be proposed, confirmed, or unresolved", rel)
            if "reach" in data:
                reach = data["reach"]
                ok = isinstance(reach, list) and reach and all(
                    isinstance(r, dict) and any(isinstance(r.get(k), str) and r[k] for k in ("route", "command", "shortcut")) for r in reach)
                if not ok:
                    findings.add("feature.reach", "reach must be a non-empty list of entries with a route, command, or shortcut", rel)
            stored = sorted(RESULT_KEYS & data.keys())
            if stored:
                findings.add("record.results", f"records never store verification results; found {', '.join(stored)}", rel)

    sdir = inside(root, keys["Scenarios"])
    if sdir and os.path.isdir(sdir):
        for feature_dir in sorted(os.listdir(sdir)):
            fpath = os.path.join(sdir, feature_dir)
            if not os.path.isdir(fpath):
                continue
            for name in sorted(os.listdir(fpath)):
                if not name.endswith(".json"):
                    continue
                rel = os.path.relpath(os.path.join(fpath, name), root)
                data = load_json(os.path.join(fpath, name), findings, "scenario.parse", rel)
                if data is None:
                    continue
                sid = data.get("id")
                expected = f"{feature_dir}.{name[:-5]}"
                if not isinstance(sid, str) or not ID.match(sid):
                    findings.add("scenario.fields", "id must be a lowercase dotted identifier", rel)
                    continue
                if sid != expected:
                    findings.add("scenario.id-file", f"id {sid} should be {expected} for its location", rel)
                if sid in scenarios:
                    findings.add("scenario.duplicate", f"id {sid} is also defined in {scenarios[sid]['path']}", rel)
                    continue
                scenarios[sid] = {"path": rel, "feature": feature_dir, "data": data}
                if feature_dir not in features:
                    findings.add("scenario.feature", f"sits under {feature_dir}, which has no feature record", rel)
                steps = data.get("steps")
                if not isinstance(steps, list) or not steps or not all(
                        isinstance(s, dict) and isinstance(s.get("action"), str) and isinstance(s.get("expect"), str) for s in steps):
                    findings.add("scenario.steps", "steps must be a non-empty list of {action, expect}", rel)
                stored = sorted(RESULT_KEYS & data.keys())
                if stored:
                    findings.add("record.results", f"records never store verification results; found {', '.join(stored)}", rel)

    for fid, feature in features.items():
        own = [s for s in scenarios.values() if s["feature"] == fid]
        if not own:
            findings.add("feature.scenarios", "has no scenario records", feature["path"])
        if "reach" not in feature["data"] and not any(s["data"].get("routes") or s["data"].get("steps") for s in own):
            findings.add("feature.reach", "no reach entry and no scenario that says how a user gets there", feature["path"])

    roots = [r.strip() for r in keys["Bindings"].split(",") if r.strip()]
    bound = scan_bindings(root, roots)
    for sid, scenario in scenarios.items():
        if sid not in bound:
            findings.add("scenario.binding", f"no test registers {sid} with a literal scenario(...) call under {', '.join(roots)}", scenario["path"])
    for sid, where in sorted(bound.items()):
        if sid not in scenarios and ID.match(sid):
            findings.add("scenario.orphan-binding", f"{where[0]} registers {sid}, which has no scenario record", where[0])

    breaks = []
    bdir = inside(root, keys["Breaks"])
    if bdir and os.path.isdir(bdir):
        for name in sorted(os.listdir(bdir)):
            if not name.endswith(".patch"):
                continue
            sid = name[:-6]
            rel = os.path.relpath(os.path.join(bdir, name), root)
            breaks.append(sid)
            if sid not in scenarios:
                findings.add("break.orphan", f"break patch for {sid}, which has no scenario record", rel)
    if not breaks:
        findings.add("break.none", f"no break patches under {keys['Breaks']}, so a controlled failure cannot be probed", severity="warn")

    return {
        "contract": CONTRACT,
        "mode": "static",
        "root": root,
        "control": control,
        "counts": {"features": len(features), "scenarios": len(scenarios), "bindings": sum(len(v) for v in bound.values()), "breaks": len(breaks)},
        "features": sorted(features),
        "scenarios": {sid: s["feature"] for sid, s in sorted(scenarios.items())},
        "breaks": breaks,
        "conformant": not findings.errors,
        "findings": findings.items,
    }


def check_report(data, process_exit=None):
    findings = Findings()
    if not isinstance(data, dict):
        findings.add("report.parse", "the report is not a JSON object")
        return findings
    if data.get("contract") != CONTRACT:
        findings.add("report.contract", f"contract must be {CONTRACT!r}, got {data.get('contract')!r}")
    if not isinstance(data.get("runId"), str) or not data["runId"]:
        findings.add("report.fields", "runId must be a non-empty string")
    status = data.get("status")
    exit_code = data.get("exit")
    if status not in RUN_STATUS:
        findings.add("report.status", f"status must be one of {sorted(RUN_STATUS)}, got {status!r}")
    elif not isinstance(exit_code, int) or exit_code not in RUN_STATUS[status]:
        findings.add("report.exit", f"status {status} requires exit {sorted(RUN_STATUS[status])}, the report says {exit_code!r}")
    if process_exit is not None and process_exit != exit_code:
        findings.add("report.process-exit", f"the process exited {process_exit} but the report says {exit_code!r}")
    source = data.get("source") if isinstance(data.get("source"), dict) else {}
    identity = source.get("identity") if isinstance(source.get("identity"), dict) else None
    if identity is None or not (identity.get("head") is None or isinstance(identity.get("head"), str)):
        findings.add("report.source", "source.identity.head must record the revision (a string, or null outside git)")
    elif not isinstance((identity.get("manifest") or {}).get("digest"), str):
        findings.add("report.source", "source.identity.manifest.digest must record the hash of the checked bytes")
    if not isinstance(source.get("sourceChanged"), bool):
        findings.add("report.source", "source.sourceChanged must say whether the checkout changed during the run")
    checks = data.get("checks")
    if not isinstance(checks, list):
        findings.add("report.fields", "checks must be a list")
        checks = []
    for i, check in enumerate(checks):
        where = f"checks[{i}]"
        if not isinstance(check, dict):
            findings.add("report.check-fields", f"{where} is not an object")
            continue
        where = f"checks[{check.get('id', i)}]"
        if not isinstance(check.get("id"), str):
            findings.add("report.check-fields", f"{where} needs an id")
        if check.get("status") not in CHECK_STATES:
            findings.add("report.check-fields", f"{where} status {check.get('status')!r} is not a check state")
        if not isinstance(check.get("reason"), str):
            findings.add("report.check-fields", f"{where} needs a reason")
        for field in ("argv", "executed", "expected"):
            if not isinstance(check.get(field), list):
                findings.add("report.check-fields", f"{where} {field} must be a list")
        if check.get("status") == "passed":
            executed = check.get("executed") if isinstance(check.get("executed"), list) else []
            expected = check.get("expected") if isinstance(check.get("expected"), list) else []
            if not executed:
                findings.add("report.judge-zero", f"{where} passed with zero executed tests or cases")
            missing = [e for e in expected if e not in executed]
            if missing:
                findings.add("report.judge-expected", f"{where} passed without executing {', '.join(map(str, missing[:5]))}")
    prereqs = data.get("prerequisites")
    if not isinstance(prereqs, list):
        findings.add("report.fields", "prerequisites must be a list")
        prereqs = []
    for p in prereqs:
        if not isinstance(p, dict) or not isinstance(p.get("need"), str) or p.get("status") not in PREREQ_STATES:
            findings.add("report.prerequisite-fields", f"prerequisite {p!r} needs a need and a status of present, missing, or not_probed")
    states = [c.get("status") for c in checks if isinstance(c, dict)]
    if status == "passed":
        if "passed" not in states:
            findings.add("report.judge-empty", "status passed with no passed check")
        bad = sorted({s for s in states if s in NOT_PASSING})
        if bad:
            findings.add("report.judge-state", f"status passed while checks are {', '.join(bad)}")
        if any(isinstance(p, dict) and p.get("status") == "missing" for p in prereqs):
            findings.add("report.judge-prerequisite", "status passed while a prerequisite is missing")
        if source.get("sourceChanged") is True:
            findings.add("report.judge-source", "status passed although the checkout changed during the run")
    if status == "failed" and "failed" not in states:
        findings.add("report.judge-failed", "status failed with no failed check")
    return findings


def parse_document(stdout):
    """The report is the JSON document on stdout. Tolerate banner lines a package runner prints first."""
    text = stdout.strip()
    try:
        return json.loads(text)
    except ValueError:
        pass
    decoder = json.JSONDecoder()
    for match in re.finditer(r"^[{\[]", stdout, re.M):
        try:
            value, end = decoder.raw_decode(stdout, match.start())
        except ValueError:
            continue
        if not stdout[end:].strip():
            return value
    return None


def run_cli(command, args, cwd, timeout):
    line = command + "".join(" " + shlex.quote(a) for a in args)
    started = time.time()
    proc = subprocess.Popen(["bash", "-c", line], cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            text=True, start_new_session=True)
    try:
        out, err = proc.communicate(timeout=timeout)
        code = proc.returncode
    except subprocess.TimeoutExpired:
        os.killpg(proc.pid, signal.SIGKILL)
        out, err = proc.communicate()
        code = None
    return {"argv": line, "exit": code, "stdout": out, "stderr": err, "ms": int((time.time() - started) * 1000)}


def git(repo, *args, check=True):
    p = subprocess.run(["git", "-C", repo, *args], text=True, capture_output=True)
    if check and p.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)}: {p.stderr.strip()}")
    return p


def dynamic(root, feature, timeout, keep):
    probes = []

    def probe(name, status, detail, result=None):
        entry = {"probe": name, "status": status, "detail": detail}
        if result:
            entry.update({"argv": result["argv"], "exit": result["exit"], "ms": result["ms"]})
            if status != "passed" and result.get("stderr"):
                entry["stderr"] = result["stderr"][-2000:]
        probes.append(entry)

    doc = {"contract": CONTRACT, "mode": "dynamic", "root": root, "static": None, "worktree": None, "feature": None, "probes": probes}
    if git(root, "rev-parse", "--is-inside-work-tree", check=False).returncode != 0:
        probe("control", "blocked", "not a git checkout, so there is no disposable worktree to run in")
        return doc
    if git(root, "status", "--porcelain", check=False).stdout.strip():
        doc["excludedChanges"] = "the worktree is built from HEAD; uncommitted changes in the checkout were not probed"

    tmp = tempfile.mkdtemp(prefix="conform-")
    tree = os.path.join(tmp, "tree")
    created = False
    try:
        git(root, "worktree", "add", "--detach", "--quiet", tree, "HEAD")
        created = True
        doc["worktree"] = tree
        # Every probe input comes from HEAD, the same bytes the CLI runs against.
        tree = os.path.realpath(tree)
        static = check_static(tree)
        doc["static"] = {"conformant": static["conformant"], "findings": static["findings"]}
        command = static["control"]["keys"].get("Command")
        prepare = static["control"]["keys"].get("Prepare")
        if not command:
            probe("control", "blocked", "HEAD has no Command: line in a control skill reached from the Control: line")
            return doc
        if feature is None:
            with_break = [static["scenarios"][s] for s in static["breaks"] if s in static["scenarios"]]
            feature = with_break[0] if with_break else (static["features"][0] if static["features"] else None)
        if feature is None:
            probe("control", "blocked", "HEAD has no feature records to run")
            return doc
        doc["feature"] = feature
        if prepare:
            r = run_cli(prepare, [], tree, timeout)
            if r["exit"] != 0:
                probe("prepare", "blocked", f"Prepare: exited {r['exit']}", r)
                return doc
            probe("prepare", "passed", "the worktree is prepared", r)

        r = run_cli(command, ["list", "--json"], tree, timeout)
        listed = parse_document(r["stdout"]) if r["exit"] == 0 else None
        if listed is None:
            probe("list", "failed", "list --json must exit 0 with one JSON document", r)
        else:
            text = json.dumps(listed)
            missing = [f for f in static["features"] if f'"{f}"' not in text]
            probe("list", "failed" if missing else "passed",
                  f"list omits features {', '.join(missing)}" if missing else "every feature record is listed", r)

        r = run_cli(command, ["describe", "feature", feature, "--json"], tree, timeout)
        ok = r["exit"] == 0 and parse_document(r["stdout"]) is not None
        probe("describe", "passed" if ok else "failed", "describe feature --json exits 0 with JSON" if ok else "describe feature --json must exit 0 with one JSON document", r)

        r = run_cli(command, ["feature", "conform-missing-feature", "--json"], tree, timeout)
        probe("unknown", "passed" if r["exit"] == 2 else "failed",
              "an unknown feature is a usage error" if r["exit"] == 2 else f"an unknown feature must exit 2, got {r['exit']}", r)

        def run_feature(name, want):
            r = run_cli(command, ["feature", feature, "--json"], tree, timeout)
            if r["exit"] is None:
                probe(name, "failed", f"timed out after {timeout}s", r)
                return None
            report = parse_document(r["stdout"])
            if report is None:
                probe(name, "failed", "feature --json printed no JSON report", r)
                return None
            problems = check_report(report, r["exit"]).errors
            if problems:
                probe(name, "failed", "; ".join(p["message"] for p in problems[:4]), r)
                return None
            if r["exit"] not in want:
                if r["exit"] == 3 and 0 in want:
                    probe(name, "blocked", "the run was incomplete, so nothing is established; see the report's prerequisites", r)
                else:
                    probe(name, "failed", f"expected exit {sorted(want)}, got {r['exit']}", r)
                return None
            return r, report

        base = run_feature("baseline", {0})
        if base:
            probe("baseline", "passed", f"feature {feature} passes at HEAD", base[0])

        patches = [s for s in static["breaks"] if static["scenarios"].get(s) == feature]
        if not base:
            probe("break", "blocked", "the baseline did not pass, so a failure under the break patch would prove nothing")
        elif not patches:
            probe("break", "blocked", f"no break patch declared for a scenario of {feature}")
        else:
            sid = patches[0]
            patch = os.path.join(inside(tree, static["control"]["keys"]["Breaks"]), sid + ".patch")
            applied = git(tree, "apply", patch, check=False)
            if applied.returncode != 0:
                probe("break", "failed", f"the break patch for {sid} no longer applies: {applied.stderr.strip()}")
            else:
                broken = run_feature("break", {1})
                if broken:
                    failed = [c for c in broken[1].get("checks", []) if isinstance(c, dict) and c.get("status") == "failed"]
                    if any(sid in json.dumps(c) for c in failed):
                        probe("break", "passed", f"the break patch fails the run and names {sid}", broken[0])
                    else:
                        probe("break", "failed", f"the run failed but no failed check names {sid}, so the failure may be unrelated", broken[0])
                reverted = git(tree, "apply", "-R", patch, check=False)
                if reverted.returncode != 0:
                    probe("restore", "blocked", f"the break patch for {sid} did not revert, so the worktree no longer matches HEAD: {reverted.stderr.strip()}")
                    base = None
                else:
                    restored = run_feature("restore", {0})
                    if restored:
                        probe("restore", "passed", "reverting the break patch passes again", restored[0])

        if base:
            results = [None, None]

            def worker(i):
                results[i] = run_cli(command, ["feature", feature, "--json"], tree, timeout)

            threads = [threading.Thread(target=worker, args=(i,)) for i in (0, 1)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()
            reports = [parse_document(r["stdout"]) or {} for r in results]
            ids = {rep.get("runId") for rep in reports}
            if all(r["exit"] == 0 for r in results) and len(ids) == 2:
                probe("parallel", "passed", "two concurrent runs both pass with distinct run ids", results[0])
            else:
                probe("parallel", "failed", f"concurrent runs exited {[r['exit'] for r in results]} with run ids {sorted(map(str, ids))}", results[1])
        else:
            probe("parallel", "blocked", "the baseline did not pass, or the worktree no longer matches HEAD")
    finally:
        if created and not keep:
            git(root, "worktree", "remove", "--force", tree, check=False)
        if not keep:
            shutil.rmtree(tmp, ignore_errors=True)
    return doc


def main(argv):
    if not argv:
        usage_error("missing subcommand")
    sub, rest = argv[0], argv[1:]
    if sub == "static":
        if len(rest) > 1:
            usage_error("static takes at most one REPO")
        root = os.path.realpath(rest[0] if rest else ".")
        if not os.path.isdir(root):
            usage_error(f"static: not a directory: {root}")
        doc = check_static(root)
        print(json.dumps(doc, indent=2))
        return 0 if doc["conformant"] else 1
    if sub == "report":
        path, process_exit = None, None
        i = 0
        while i < len(rest):
            if rest[i] == "--exit" and i + 1 < len(rest):
                try:
                    process_exit = int(rest[i + 1])
                except ValueError:
                    usage_error("report: --exit takes an integer")
                i += 2
            elif path is None and not rest[i].startswith("--"):
                path, i = rest[i], i + 1
            else:
                usage_error(f"report: unexpected argument {rest[i]}")
        if path is None:
            usage_error("report: missing FILE")
        text = read_text(path)
        data = parse_document(text) if text is not None else None
        findings = Findings()
        if data is None:
            findings.add("report.parse", f"{path} is not a JSON document")
        else:
            findings = check_report(data, process_exit)
        print(json.dumps({"contract": CONTRACT, "mode": "report", "file": path, "valid": not findings.errors, "findings": findings.items}, indent=2))
        return 0 if not findings.errors else 1
    if sub == "dynamic":
        root, trust, feature, timeout, keep = None, False, None, 900, False
        i = 0
        while i < len(rest):
            arg = rest[i]
            if arg == "--trust":
                trust, i = True, i + 1
            elif arg == "--keep":
                keep, i = True, i + 1
            elif arg == "--feature" and i + 1 < len(rest):
                feature, i = rest[i + 1], i + 2
            elif arg == "--timeout" and i + 1 < len(rest):
                if not rest[i + 1].isdigit():
                    usage_error("dynamic: --timeout takes whole seconds")
                timeout, i = int(rest[i + 1]), i + 2
            elif root is None and not arg.startswith("--"):
                root, i = arg, i + 1
            else:
                usage_error(f"dynamic: unexpected argument {arg}")
        if root is None:
            usage_error("dynamic: missing REPO")
        if not trust:
            usage_error("dynamic runs the project's own code; pass --trust once the user has agreed to that")
        root = os.path.realpath(root)
        if not os.path.isdir(root):
            usage_error(f"dynamic: not a directory: {root}")
        doc = dynamic(root, feature, timeout, keep)
        print(json.dumps(doc, indent=2))
        states = {p["status"] for p in doc["probes"]}
        return 1 if "failed" in states else 3 if "blocked" in states else 0
    usage_error(f"unknown subcommand {sub}")


raise SystemExit(main(sys.argv[1:]))
PY
}

case "${1:-}" in
  static|report|dynamic) run_python "$@" ;;
  -h|--help) usage; exit 0 ;;
  "") usage; exit 2 ;;
  *) die "unknown subcommand $1" ;;
esac
