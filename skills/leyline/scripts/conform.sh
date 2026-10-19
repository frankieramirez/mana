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
#   dynamic REPO --trust [--feature ID] [--timeout SECONDS] [--out DIR] [--keep]
#       Run the project's control CLI in a disposable git worktree of HEAD and probe it: list,
#       describe, an unknown selector, a baseline run, a declared break patch that must fail
#       for its scenario, the restored run, and two concurrent runs. Every probe appears in the
#       output, as blocked with a reason when it could not run. Each feature run records its
#       run id, and its report is copied with a SHA-256 into DIR (a new temporary directory by
#       default, never inside the worktree; DIR must be empty or absent). Runs project code, so
#       it refuses without --trust. Removes only the worktree it created. Exit 0 when every
#       probe passes, 1 when one fails, 3 when a probe is blocked and none failed.
#
#   evidence [--repo REPO] [--report FILE [--exit N]] [--criteria FILE] [--head SHA]
#            [--digest SHA256] [--scope static|local]
#       Read files and the repo's HEAD only; run no control command. Find the Control: pointer
#       (present, absent, or broken), validate the report as `report` does, compare its source
#       identity with the reviewed checkout, and give each criterion its own outcome in the
#       capture vocabulary (passed, failed, blocked, unrun) with a claim of supported,
#       contradicted, or unverified. --criteria is a JSON object mapping each criterion to the
#       scenario ids that cover it; without it every scenario in the report is its own
#       criterion. --head defaults to the repo's HEAD. --digest is the checked-byte digest of the
#       reviewed state when a fresh report supplied it; without it the report's checked-file
#       list is rehashed in REPO. --scope says whether control commands may run (default
#       static). Exit 0 when every criterion is supported, 1 when the report is rejected or a
#       current check failed, 3 otherwise.
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
import hashlib, json, os, re, shlex, shutil, signal, subprocess, sys, tempfile, threading, time

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
PROBES = ("list", "describe", "unknown", "baseline", "break", "restore", "parallel")
TAIL = 2000
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
    if identity is None or "head" not in identity or not (identity["head"] is None or isinstance(identity["head"], str)):
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


def split_document(stdout):
    """Return the JSON document on stdout and its exact text. Tolerate banner lines a package runner prints first."""
    text = stdout.strip()
    try:
        return json.loads(text), text
    except ValueError:
        pass
    decoder = json.JSONDecoder()
    for match in re.finditer(r"^[{\[]", stdout, re.M):
        try:
            value, end = decoder.raw_decode(stdout, match.start())
        except ValueError:
            continue
        if not stdout[end:].strip():
            return value, stdout[match.start():end]
    return None, None


def parse_document(stdout):
    return split_document(stdout)[0]


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


def dynamic(root, feature, timeout, keep, out):
    probes = []
    doc = {"contract": CONTRACT, "mode": "dynamic", "root": root, "static": None, "worktree": None, "feature": None,
           "retained": None, "probes": probes}

    def probe(name, status, detail, result=None, runs=None):
        entry = {"probe": name, "status": status, "detail": detail}
        if result:
            entry.update({"argv": result["argv"], "exit": result["exit"], "ms": result["ms"]})
            if status != "passed":
                # A report kept on disk already holds stdout. Otherwise keep its tail, where tools such
                # as pnpm print the reason a prerequisite is missing.
                if result.get("stdout") and not any(run.get("report") for run in runs or []):
                    entry["stdout"] = result["stdout"][-TAIL:]
                if result.get("stderr"):
                    entry["stderr"] = result["stderr"][-TAIL:]
        if runs is not None:
            entry["runs"] = runs
        probes.append(entry)

    try:
        probe_all(root, feature, timeout, keep, out, doc, probe)
    finally:
        kept = doc["retained"]
        if out is None and kept and os.path.isdir(kept) and not os.listdir(kept):
            os.rmdir(kept)
            doc["retained"] = None
        # Every probe appears. One that never started is blocked by the first probe that did not pass.
        seen = {p["probe"] for p in probes}
        cause = next((p for p in probes if p["status"] != "passed"), None)
        for name in PROBES:
            if name not in seen:
                why = f"the {cause['probe']} probe was {cause['status']}: {cause['detail']}" if cause else "the checker stopped first"
                probe(name, "blocked", f"not run, because {why}")
    return doc


def retain(out, name, result):
    """Copy the report a feature run printed into OUT, outside the worktree, and say where it went."""
    value, text = split_document(result["stdout"])
    run = {"runId": None, "exit": result["exit"], "report": None, "sha256": None}
    if isinstance(value, dict) and isinstance(value.get("runId"), str):
        run["runId"] = value["runId"]
    if value is not None:
        data = (text + "\n").encode("utf-8")
        path = os.path.join(out, name + ".json")
        with open(path, "wb") as fh:
            fh.write(data)
        run.update(report=path, sha256=hashlib.sha256(data).hexdigest())
    return value, run


def probe_all(root, feature, timeout, keep, out, doc, probe):
    if git(root, "rev-parse", "--is-inside-work-tree", check=False).returncode != 0:
        probe("control", "blocked", "not a git checkout, so there is no disposable worktree to run in")
        return
    if git(root, "status", "--porcelain", check=False).stdout.strip():
        doc["excludedChanges"] = "the worktree is built from HEAD; uncommitted changes in the checkout were not probed"
    if out is None:
        out = tempfile.mkdtemp(prefix="conform-reports-")
    else:
        os.makedirs(out, exist_ok=True)
    doc["retained"] = out

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
            return
        if feature is None:
            with_break = [static["scenarios"][s] for s in static["breaks"] if s in static["scenarios"]]
            feature = with_break[0] if with_break else (static["features"][0] if static["features"] else None)
        if feature is None:
            probe("control", "blocked", "HEAD has no feature records to run")
            return
        doc["feature"] = feature
        if prepare:
            r = run_cli(prepare, [], tree, timeout)
            if r["exit"] != 0:
                probe("prepare", "blocked", f"Prepare: exited {r['exit']}", r)
                return
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
            report, run = retain(out, name, r)
            runs = [run]
            if r["exit"] is None:
                probe(name, "failed", f"timed out after {timeout}s", r, runs)
                return None
            if report is None:
                probe(name, "failed", "feature --json printed no JSON report", r, runs)
                return None
            problems = check_report(report, r["exit"]).errors
            if problems:
                probe(name, "failed", "; ".join(p["message"] for p in problems[:4]), r, runs)
                return None
            if r["exit"] not in want:
                if r["exit"] == 3:
                    # An incomplete run establishes nothing, under the break patch as much as at HEAD.
                    probe(name, "blocked", "the run was incomplete, so nothing is established; see the report's prerequisites", r, runs)
                else:
                    probe(name, "failed", f"expected exit {sorted(want)}, got {r['exit']}", r, runs)
                return None
            return r, report, runs

        base = run_feature("baseline", {0})
        if base:
            probe("baseline", "passed", f"feature {feature} passes at HEAD", base[0], base[2])

        patches = [s for s in static["breaks"] if static["scenarios"].get(s) == feature]
        if not base:
            probe("break", "blocked", "the baseline did not pass, so a failure under the break patch would prove nothing")
            probe("restore", "blocked", "not run, because the baseline did not pass and no break patch was applied")
        elif not patches:
            probe("break", "blocked", f"no break patch declared for a scenario of {feature}")
            probe("restore", "blocked", "not run, because no break patch was applied")
        else:
            sid = patches[0]
            patch = os.path.join(inside(tree, static["control"]["keys"]["Breaks"]), sid + ".patch")
            applied = git(tree, "apply", patch, check=False)
            if applied.returncode != 0:
                probe("break", "failed", f"the break patch for {sid} no longer applies: {applied.stderr.strip()}")
                probe("restore", "blocked", "not run, because the break patch did not apply")
            else:
                broken = run_feature("break", {1})
                if broken:
                    failed = [c for c in broken[1].get("checks", []) if isinstance(c, dict) and c.get("status") == "failed"]
                    if any(sid in json.dumps(c) for c in failed):
                        probe("break", "passed", f"the break patch fails the run and names {sid}", broken[0], broken[2])
                    else:
                        probe("break", "failed", f"the run failed but no failed check names {sid}, so the failure may be unrelated", broken[0], broken[2])
                reverted = git(tree, "apply", "-R", patch, check=False)
                if reverted.returncode != 0:
                    probe("restore", "blocked", f"the break patch for {sid} did not revert, so the worktree no longer matches HEAD: {reverted.stderr.strip()}")
                    base = None
                else:
                    restored = run_feature("restore", {0})
                    if restored:
                        probe("restore", "passed", "reverting the break patch passes again", restored[0], restored[2])

        if base:
            results = [None, None]

            def worker(i):
                results[i] = run_cli(command, ["feature", feature, "--json"], tree, timeout)

            threads = [threading.Thread(target=worker, args=(i,)) for i in (0, 1)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()
            runs = [retain(out, f"parallel-{i + 1}", r)[1] for i, r in enumerate(results)]
            ids = {run["runId"] for run in runs}
            if all(r["exit"] == 0 for r in results) and len(ids) == 2 and None not in ids:
                probe("parallel", "passed", "two concurrent runs both pass with distinct run ids", results[0], runs)
            else:
                probe("parallel", "failed", f"concurrent runs exited {[r['exit'] for r in results]} with run ids {sorted(map(str, ids))}", results[1], runs)
        else:
            probe("parallel", "blocked", "the baseline did not pass, or the worktree no longer matches HEAD")
    finally:
        if created and not keep:
            git(root, "worktree", "remove", "--force", tree, check=False)
        if not keep:
            shutil.rmtree(tmp, ignore_errors=True)


CAPTURE = {"passed": "passed", "failed": "failed", "blocked": "blocked", "unavailable": "blocked",
           "timed_out": "unrun", "cancelled": "unrun", "skipped": "unrun", "not_run": "unrun"}


def discover_control(root):
    """Read the Control: pointer without running anything: present, absent, or broken."""
    findings = Findings()
    control = resolve_control(root, findings)
    has_line = False
    if control["agentFile"]:
        block = agent_block(read_text(os.path.join(root, control["agentFile"])) or "") or ""
        has_line = re.search(r"^Control:", block, re.M) is not None
    problems = [f["message"] for f in findings.errors]
    state = "absent" if not has_line else "broken" if problems else "present"
    return {"state": state, "agentFile": control["agentFile"], "skill": control["skill"],
            "command": control["keys"].get("Command"), "detail": "; ".join(problems) or None}


def reviewed_head(root):
    try:
        out = subprocess.run(["git", "-C", root, "rev-parse", "--verify", "HEAD"], capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.SubprocessError):
        return None
    return (out.stdout.strip() or None) if out.returncode == 0 else None


def checked_files(manifest):
    """The report's list of checked files, inline or in the artifact it names, or None."""
    files = manifest.get("files")
    if not isinstance(files, list) and isinstance(manifest.get("artifact"), str):
        text = read_text(manifest["artifact"])
        try:
            files = json.loads(text) if text is not None else None
        except ValueError:
            files = None
    if not isinstance(files, list) or not files:
        return None
    if not all(isinstance(f, dict) and isinstance(f.get("path"), str) and isinstance(f.get("digest"), str) for f in files):
        return None
    return files


def judge_identity(report, root, head, digest):
    identity = report["source"]["identity"]
    manifest = identity.get("manifest") or {}
    out = {"relevance": "unknown", "reported": {"head": identity.get("head"), "digest": manifest.get("digest")},
           "reviewed": {"head": head, "digest": digest}, "changed": [], "detail": None}
    if report["source"].get("sourceChanged"):
        out["detail"] = "the checkout changed during the run, so its observations bind to no single source state"
        return out
    if head is None and identity.get("head") is not None:
        out["detail"] = "the reviewed revision is unknown, so it cannot be matched with the report's"
        return out
    if head != identity.get("head"):
        out["relevance"], out["detail"] = "stale", f"the report checked {identity.get('head')} but the reviewed state is {head}"
        return out
    if digest is not None:
        same = digest == manifest.get("digest")
        out["relevance"] = "current" if same else "stale"
        out["detail"] = "the reviewed digest matches the checked bytes" if same else "the reviewed digest differs from the checked bytes"
        return out
    files = checked_files(manifest)
    if files is None:
        out["detail"] = "same HEAD alone does not establish identity: the report lists no checked files and no reviewed digest was given"
        return out
    listed = hashlib.sha256(json.dumps(files, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()
    if listed != manifest.get("digest"):
        out["detail"] = "the checked-file list does not hash to the reported digest"
        return out
    for item in files:
        full = inside(root, item["path"])
        if not full or not os.path.isfile(full):
            out["changed"].append(item["path"])
            continue
        with open(full, "rb") as fh:
            same = hashlib.sha256(fh.read()).hexdigest() == item["digest"]
        if not same or (isinstance(item.get("mode"), int) and os.stat(full).st_mode & 0o777 != item["mode"]):
            out["changed"].append(item["path"])
    if out["changed"]:
        out["relevance"] = "stale"
        out["detail"] = f"same HEAD, but {len(out['changed'])} checked file(s) differ in the reviewed checkout"
    else:
        out["relevance"], out["detail"] = "current", f"every one of {len(files)} checked files matches the reviewed checkout"
    return out


def scenario_outcome(sid, report, missing):
    """One scenario's observed outcome in the capture vocabulary, from a report that passed validation."""
    proving = report["status"] in ("passed", "failed")
    seen = []
    for check in report["checks"]:
        expected, executed = check.get("expected") or [], check.get("executed") or []
        if sid not in expected and sid not in executed:
            continue
        raw, label = check.get("status"), f"{check.get('id')}: {check.get('status')}, {check.get('reason')}"
        if raw in ("passed", "failed") and sid not in executed:
            state, label = "unrun", f"{check.get('id')}: expected but not executed ({check.get('reason')})"
        elif raw == "failed":
            named = check.get("failed") if isinstance(check.get("failed"), list) else executed
            state = "failed" if sid in named else "passed"
        elif raw in ("not_run", "skipped") and missing:
            state = "blocked"
        else:
            state = CAPTURE[raw]
        if state == "passed" and not proving:
            state, label = "unrun", f"the run was {report['status']}, so its passing checks prove no behavior ({label})"
        if state == "blocked" and missing:
            label += f"; missing prerequisite: {', '.join(missing)}"
        seen.append((state, label))
    if not seen:
        return "unrun", "no check in the report expected or executed this scenario"
    for state in ("failed", "passed", "blocked", "unrun"):
        for got, label in seen:
            if got == state:
                return state, label


def interpret(root, report_path, process_exit, criteria_path, head, digest, scope):
    doc = {"contract": CONTRACT, "mode": "evidence", "control": discover_control(root), "report": None,
           "identity": None, "criteria": [], "currentPass": False}
    report, valid = None, False
    if report_path is not None:
        text = read_text(report_path)
        report = parse_document(text) if text is not None else None
        findings = Findings()
        if report is None:
            findings.add("report.parse", f"{report_path} is not a JSON document")
        else:
            findings = check_report(report, process_exit)
        valid = not findings.errors
        doc["report"] = {"file": report_path, "valid": valid, "findings": findings.items,
                         "runId": report.get("runId") if isinstance(report, dict) else None,
                         "status": report.get("status") if isinstance(report, dict) else None,
                         "exit": report.get("exit") if isinstance(report, dict) else None}
    if valid:
        doc["identity"] = judge_identity(report, root, head, digest)
    if criteria_path is not None:
        text = read_text(criteria_path)
        try:
            criteria = json.loads(text) if text is not None else None
        except ValueError:
            criteria = None
        if not isinstance(criteria, dict) or not all(isinstance(v, list) and all(isinstance(s, str) for s in v) for v in criteria.values()):
            usage_error(f"evidence: {criteria_path} must be a JSON object mapping each criterion to a list of scenario ids")
    else:
        ids = []
        for check in (report.get("checks") if valid else None) or []:
            for sid in (check.get("expected") or []) + (check.get("executed") or []):
                if sid not in ids:
                    ids.append(sid)
        criteria = {sid: [sid] for sid in ids}
    relevance = doc["identity"]["relevance"] if doc["identity"] else None
    missing = [p["need"] for p in report["prerequisites"] if p.get("status") == "missing"] if valid else []
    for name, sids in criteria.items():
        scenarios = []
        for sid in sids:
            if report is None:
                state, why = "unrun", "no control report was supplied"
            elif not valid:
                state, why = "unrun", "the report was rejected, so it establishes nothing"
            else:
                state, why = scenario_outcome(sid, report, missing)
            scenarios.append({"id": sid, "status": state, "reason": why})
        states = [s["status"] for s in scenarios]
        status = next((s for s in ("failed", "blocked", "unrun") if s in states), "passed" if states else "unrun")
        reason = next((s["reason"] for s in scenarios if s["status"] == status), "no scenario covers this criterion")
        if relevance != "current" or not states:
            claim = "unverified"
        else:
            claim = "contradicted" if status == "failed" else "supported" if status == "passed" else "unverified"
        doc["criteria"].append({"id": name, "status": status, "relevance": relevance, "claim": claim,
                                "reason": reason, "scenarios": scenarios})
    doc["currentPass"] = bool(valid and relevance == "current" and report["status"] == "passed")
    control = doc["control"]
    execution = {"scope": scope, "authorized": False, "rerun": [], "guidance": None}
    if control["state"] == "absent":
        execution["guidance"] = "no project control was discovered; use the repo's existing guidance, tests and source inspection, and report no control check"
    elif control["state"] == "broken":
        execution["guidance"] = f"the control pointer is broken ({control['detail']}); name the gap and use supported existing checks"
    if scope == "static":
        execution["reason"] = "static-only scope: every control command, including list, describe and --plan, executes project code"
    elif control["state"] == "present":
        execution["authorized"] = True
        execution["reason"] = "local-only scope: run on this machine; no push, tracker write, deployment or publication"
        try:
            prefix = shlex.split(control["command"])
        except ValueError:
            prefix = None
        features = sorted({s["id"].rsplit(".", 1)[0] for c in doc["criteria"] if c["claim"] != "supported" for s in c["scenarios"] if "." in s["id"]})
        if prefix:
            execution["rerun"] = [prefix + ["feature", f, "--json"] for f in features]
    else:
        execution["reason"] = "local scope, but there is no usable control to run"
    doc["execution"] = execution
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
        root, trust, feature, timeout, keep, out = None, False, None, 900, False, None
        i = 0
        while i < len(rest):
            arg = rest[i]
            if arg == "--trust":
                trust, i = True, i + 1
            elif arg == "--keep":
                keep, i = True, i + 1
            elif arg == "--out" and i + 1 < len(rest):
                out, i = rest[i + 1], i + 2
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
        if out is not None:
            out = os.path.realpath(out)
            if os.path.exists(out) and (not os.path.isdir(out) or os.listdir(out)):
                usage_error(f"dynamic: --out must name an empty or absent directory: {out}")
        doc = dynamic(root, feature, timeout, keep, out)
        print(json.dumps(doc, indent=2))
        states = {p["status"] for p in doc["probes"]}
        return 1 if "failed" in states else 3 if "blocked" in states else 0
    if sub == "evidence":
        opts = {"--repo": ".", "--report": None, "--exit": None, "--criteria": None, "--head": None, "--digest": None, "--scope": "static"}
        i = 0
        while i < len(rest):
            if rest[i] in opts and i + 1 < len(rest):
                opts[rest[i]], i = rest[i + 1], i + 2
            else:
                usage_error(f"evidence: unexpected argument {rest[i]}")
        if opts["--scope"] not in ("static", "local"):
            usage_error("evidence: --scope is static or local")
        process_exit = None
        if opts["--exit"] is not None:
            try:
                process_exit = int(opts["--exit"])
            except ValueError:
                usage_error("evidence: --exit takes an integer")
        root = os.path.realpath(opts["--repo"])
        if not os.path.isdir(root):
            usage_error(f"evidence: not a directory: {root}")
        head = opts["--head"] if opts["--head"] is not None else reviewed_head(root)
        doc = interpret(root, opts["--report"], process_exit, opts["--criteria"], head, opts["--digest"], opts["--scope"])
        print(json.dumps(doc, indent=2))
        if doc["report"] and not doc["report"]["valid"]:
            return 1
        claims = [c["claim"] for c in doc["criteria"]]
        if "contradicted" in claims:
            return 1
        return 0 if claims and all(c == "supported" for c in claims) else 3
    usage_error(f"unknown subcommand {sub}")


raise SystemExit(main(sys.argv[1:]))
PY
}

case "${1:-}" in
  static|report|dynamic|evidence) run_python "$@" ;;
  -h|--help) usage; exit 0 ;;
  "") usage; exit 2 ;;
  *) die "unknown subcommand $1" ;;
esac
