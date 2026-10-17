#!/usr/bin/env bash
# challenge.sh: challenge an installed control/0 CLI and retain source-bound evidence.
#
#   challenge.sh REPO --trust [--plan FILE] [--feature ID] [--timeout SECONDS]
#                [--evidence DIR] [--only NAME,...]
#
# Runs the project's control CLI from committed HEAD bytes in disposable git worktrees.
# Probes discovery, a baseline run, the declared break patch, the restored run, two
# concurrent runs, cancellation by SIGINT and SIGTERM, and every variant in the plan.
# While it runs, a listener this script owns sits on a port the CLI did not open. Every
# probe checks that the listener still answers, that no process the run started outlives
# it, and that the user's HEAD, index, tracked and untracked bytes are unchanged.
#
# Raw stdout, conformance results and each run's retained evidence are copied into the
# evidence directory with a SHA-256 manifest. Worktrees and scratch are then removed and
# the manifest is checked again. --evidence must be outside REPO and empty.
#
# --only limits the optional probes (break, restore, parallel, cancel-sigint,
# cancel-sigterm and plan variants). Probes left out are not_run, which keeps exit 3.
#
# Exit 0 when every probe passes, 1 when one fails, 3 when one is blocked or not run and
# none failed, 2 for usage, 4 when python3 is missing. SIGINT or SIGTERM stops in-flight
# runs, removes worktrees and the listener, writes challenge.json marked interrupted, and
# exits 130 or 143. A process is stopped only while its process group and start time still
# match what was observed under the run, so a reused PID is left alone. Python standard
# library only.

set -euo pipefail

case "${1:-}" in
  -h|--help)
    awk 'NR == 1 { next } /^#/ { sub(/^# ?/, ""); print; next } { exit }' "${BASH_SOURCE[0]}"
    exit 0 ;;
  "")
    awk 'NR == 1 { next } /^#/ { sub(/^# ?/, ""); print; next } { exit }' "${BASH_SOURCE[0]}" >&2
    exit 2 ;;
esac
command -v python3 >/dev/null 2>&1 || { echo "challenge.sh: python3 not found" >&2; exit 4; }

# exec: a signal sent to challenge.sh reaches the Python process and its cleanup.
exec python3 - "${BASH_SOURCE[0]}" "$@" <<'PY'
import hashlib, json, os, re, shlex, shutil, signal, socket, subprocess, sys, tempfile, threading, time
from pathlib import Path

SCRIPT = Path(sys.argv[1]).resolve()
ACTIVE = set()  # Run sessions started and not yet finished, for cleanup on interruption.


class Interrupted(BaseException):
    """Raised by SIGINT or SIGTERM so every finally block runs before exit."""


def interrupted(signum, _frame):
    raise Interrupted(signal.Signals(signum).name)
CONFORM = SCRIPT.parent / "conform.sh"
NAME = re.compile(r"^[a-z0-9][a-z0-9-]*$")
BUILTIN = ["static", "list", "describe", "unknown", "baseline", "break", "restore", "parallel", "cancel-sigint", "cancel-sigterm"]
OPTIONAL = ["break", "restore", "parallel", "cancel-sigint", "cancel-sigterm"]
STATUSES = {"passed", "failed", "incomplete", "cancelled"}
SENTINEL = r'''
import socket, sys
# leyline-challenge-sentinel: an unknown listener the control under challenge did not open.
server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server.bind(("127.0.0.1", 0))
server.listen(64)
print(server.getsockname()[1], flush=True)
while True:
    connection, _ = server.accept()
    try:
        connection.sendall(sys.argv[2].encode())
    finally:
        connection.close()
'''


def usage(message):
    print(f"challenge.sh: {message}", file=sys.stderr)
    raise SystemExit(2)


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def git_env():
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    env["GIT_OPTIONAL_LOCKS"] = "0"  # Reading status must never rewrite the user's index.
    return env


def git(repo, *args, check=True):
    result = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, env=git_env())
    if check and result.returncode:
        raise RuntimeError(f"git {' '.join(args)}: {result.stderr.decode(errors='replace').strip()}")
    return result


def inside(base, value):
    base = Path(base).resolve()
    path = Path(value).resolve()
    return path == base or base in path.parents


DIGESTS = {}


def file_digest(path):
    """SHA-256 of a file, recomputed whenever any stat field that a write changes differs."""
    info = path.stat()
    key = (str(path), info.st_size, info.st_mtime_ns, info.st_ctime_ns, info.st_ino)
    if key not in DIGESTS:
        DIGESTS[key] = sha256(path.read_bytes())
    return DIGESTS[key]


def checkout_state(repo):
    """HEAD, index bytes, and tracked plus untracked bytes of the user's checkout."""
    head = git(repo, "rev-parse", "--verify", "-q", "HEAD", check=False).stdout.decode().strip() or None
    ref = git(repo, "symbolic-ref", "-q", "HEAD", check=False).stdout.decode().strip() or None
    index_rel = git(repo, "rev-parse", "--git-path", "index").stdout.decode().strip()
    index = Path(repo, index_rel)
    files = {}
    names = git(repo, "ls-files", "-z", "--cached", "--others", "--exclude-standard").stdout.decode(errors="surrogateescape").split("\0")
    for name in sorted(set(filter(None, names))):
        path = Path(repo, name)
        if path.is_symlink():
            files[name] = "link:" + sha256(os.readlink(path).encode(errors="surrogateescape"))
        elif path.is_file():
            files[name] = f"{oct(path.stat().st_mode & 0o777)}:{file_digest(path)}"
        elif path.exists():
            files[name] = "special"
        else:
            files[name] = "missing"
    worktrees = sum(1 for line in git(repo, "worktree", "list", "--porcelain").stdout.decode().splitlines() if line.startswith("worktree "))
    return {"head": head, "ref": ref, "index": file_digest(index) if index.is_file() else None,
            "files": files, "worktrees": worktrees}


def state_summary(state):
    return {"head": state["head"], "ref": state["ref"], "index": state["index"], "worktrees": state["worktrees"],
            "fileCount": len(state["files"]), "filesDigest": sha256(json.dumps(state["files"], sort_keys=True).encode())}


def state_diff(before, after, include_worktrees):
    changes = [key for key in ("head", "ref", "index") if before[key] != after[key]]
    if include_worktrees and before["worktrees"] != after["worktrees"]:
        changes.append("worktrees")
    paths = sorted(set(before["files"]) | set(after["files"]))
    changes += [f"file:{p}" for p in paths if before["files"].get(p) != after["files"].get(p)]
    return changes


def process_table():
    try:
        out = subprocess.run(["ps", "-A", "-o", "pid=,ppid=,pgid=,stat="], capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.TimeoutExpired):
        return None
    if out.returncode:
        return None
    table = {}
    for line in out.stdout.splitlines():
        parts = line.split()
        if len(parts) >= 4 and parts[0].isdigit() and parts[1].isdigit() and parts[2].isdigit():
            table[int(parts[0])] = {"ppid": int(parts[1]), "pgid": int(parts[2]), "zombie": parts[3].startswith("Z")}
    return table


def proc_identity(pid):
    """(pgid, start time, zombie) of a PID now, or None when no such process exists.

    The start time tells a reused PID apart from the process observed earlier."""
    if os.path.exists("/proc/self/stat"):
        try:
            text = Path(f"/proc/{pid}/stat").read_text()
        except OSError:
            return None
        fields = text.rsplit(")", 1)[1].split()
        return int(fields[2]), fields[19], fields[0] == "Z"
    try:
        out = subprocess.run(["ps", "-o", "pgid=,stat=,lstart=", "-p", str(pid)], capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.TimeoutExpired):
        return None
    parts = out.stdout.split()
    if out.returncode or len(parts) < 3 or not parts[0].isdigit():
        return None
    return int(parts[0]), " ".join(parts[2:]), parts[1].startswith("Z")


def owned_alive(observed):
    """PIDs whose current pgid and start time still match an identity recorded under the run."""
    alive = []
    for pid, identities in observed.items():
        now = proc_identity(pid)
        if now is not None and not now[2] and (now[0], now[1]) in identities:
            alive.append(pid)
    return sorted(alive)


def kill_owned(pid, identities):
    """SIGKILL a PID only while it is still the process that was observed."""
    handle = None
    try:
        if hasattr(os, "pidfd_open") and hasattr(signal, "pidfd_send_signal"):
            handle = os.pidfd_open(pid)  # Pins this process, so the check below cannot race a reuse.
        now = proc_identity(pid)
        if now is None or now[2] or (now[0], now[1]) not in identities:
            return False
        if handle is not None:
            signal.pidfd_send_signal(handle, signal.SIGKILL)
        else:
            os.kill(pid, signal.SIGKILL)
        return True
    except (ProcessLookupError, OSError):
        return False
    finally:
        if handle is not None:
            os.close(handle)


def reap_owned(observed, wait=3.0):
    """Wait for observed processes to end, then stop any that are still the same processes."""
    survivors = owned_alive(observed)
    deadline = time.time() + wait
    while survivors and time.time() < deadline:
        time.sleep(0.05)
        survivors = owned_alive(observed)
    killed = [pid for pid in survivors if kill_owned(pid, observed[pid])]
    return survivors, killed


def parse_document(stdout):
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


class Run:
    """One control invocation in its own session, with every descendant it starts observed."""

    def __init__(self, command, args, cwd, env, timeout, folder):
        self.line = command + "".join(" " + shlex.quote(a) for a in args)
        self.cwd, self.env, self.timeout, self.folder = cwd, env, timeout, folder
        self.observed = {}
        self.monitor_ok = True
        self.done = threading.Event()
        # A signal can arrive at any point in start(); abort() must cope with whatever exists.
        self.out = self.err = self.proc = self.thread = None

    def start(self):
        ACTIVE.add(self)
        self.folder.mkdir(parents=True, exist_ok=True)
        self.out = open(self.folder / "stdout.txt", "wb")
        self.err = open(self.folder / "stderr.txt", "wb")
        self.started = time.time()
        self.proc = subprocess.Popen(["bash", "-c", self.line], cwd=self.cwd, env=self.env, stdout=self.out,
                                     stderr=self.err, start_new_session=True)
        self.thread = threading.Thread(target=self._watch, daemon=True)
        self.thread.start()
        return self

    def _watch(self):
        while not self.done.is_set():
            table = process_table()
            if table is None:
                self.monitor_ok = False
                return
            frontier, seen = [self.proc.pid], set()
            while frontier:
                pid = frontier.pop()
                if pid in seen:
                    continue
                seen.add(pid)
                if pid in table and not table[pid]["zombie"]:
                    now = proc_identity(pid)
                    if now is not None and not now[2]:
                        self.observed.setdefault(pid, set()).add((now[0], now[1]))
                frontier += [child for child, row in table.items() if row["ppid"] == pid]
            self.done.wait(0.05)

    def descendants(self):
        return [pid for pid in self.observed if pid != self.proc.pid]

    def signal_group(self, signum):
        if self.proc is None:
            return
        try:
            os.killpg(self.proc.pid, signum)
        except ProcessLookupError:
            pass

    def finish(self):
        timed_out = False
        try:
            self.proc.wait(timeout=max(1, self.timeout - (time.time() - self.started)))
        except subprocess.TimeoutExpired:
            timed_out = True
            self.signal_group(signal.SIGTERM)
            try:
                self.proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                self.signal_group(signal.SIGKILL)
                self.proc.wait()
        self.done.set()
        self.thread.join()
        self.out.close()
        self.err.close()
        # Only processes that still match an identity seen under this run count or get stopped.
        survivors, cleaned = reap_owned(self.observed)
        ACTIVE.discard(self)
        stdout = (self.folder / "stdout.txt").read_text(errors="replace")
        code = self.proc.returncode
        # A package runner in the signalled group can die from the signal itself; a shell reports that as 128+N.
        exit_code = None if timed_out else (128 - code if code < 0 else code)
        return {"argv": self.line, "exit": exit_code, "rawReturnCode": code, "timedOut": timed_out,
                "ms": int((time.time() - self.started) * 1000), "stdout": stdout,
                "stderr": (self.folder / "stderr.txt").read_text(errors="replace"),
                "observedProcesses": sorted(self.observed), "observedIdentities": self.identities(), "survivors": survivors,
                "ownershipVerified": self.monitor_ok, "challengerKilled": cleaned}

    def identities(self):
        return sorted([pid, pgid, start] for pid, seen in self.observed.items() for pgid, start in seen)

    def abort(self):
        """Stop an unfinished run: its CLI session first, then anything left that it started."""
        if self.proc is not None:
            self.signal_group(signal.SIGTERM)
            try:
                self.proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                self.signal_group(signal.SIGKILL)
                self.proc.wait()
        self.done.set()
        if self.thread is not None and self.thread.is_alive():
            self.thread.join()
        for handle in (self.out, self.err):
            if handle is not None and not handle.closed:
                handle.close()
        survivors, killed = reap_owned(self.observed)
        ACTIVE.discard(self)
        return {"argv": self.line, "observedIdentities": self.identities(), "survivorsAfterSignal": survivors,
                "challengerKilled": killed, "remaining": owned_alive(self.observed)}


class Challenge:
    def __init__(self, repo, plan, plan_path, feature, timeout, evidence, only):
        self.repo, self.plan, self.plan_path, self.timeout = repo, plan, plan_path, timeout
        self.feature, self.evidence, self.only = feature, evidence, only
        self.scratch = Path(tempfile.mkdtemp(prefix="leyline-challenge-scratch-"))
        self.trees = []
        self.probes = []
        self.counter = 0
        self.doc = {"contract": "control/0", "mode": "challenge", "repo": str(repo), "feature": None,
                    "source": None, "plan": None, "sentinel": None, "excludedChanges": None,
                    "probes": self.probes, "preservation": [], "retained": None}

    # Evidence and bookkeeping -------------------------------------------------
    def probe(self, name, status, detail, runs=None, extra=None):
        entry = {"probe": name, "status": status, "detail": detail, "runs": runs or []}
        entry.update(extra or {})
        self.probes.append(entry)
        return entry

    def folder(self, name):
        self.counter += 1
        return self.evidence / "probes" / name / f"run-{self.counter}"

    def worktree(self, label):
        path = self.scratch / f"tree-{label}-{len(self.trees)}"
        git(self.repo, "worktree", "add", "--detach", "--quiet", str(path), self.head)
        self.trees.append(path)
        return path.resolve()

    def drop_tree(self, path):
        git(self.repo, "worktree", "remove", "--force", str(path), check=False)
        shutil.rmtree(path, ignore_errors=True)
        if path in self.trees:
            self.trees.remove(path)

    def env(self, label, extra=None, sync=None):
        env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
        tmp = self.scratch / f"tmp-{label}-{self.counter}-{time.monotonic_ns()}"
        tmp.mkdir(parents=True)
        env["TMPDIR"] = str(tmp)  # Default snapshots and control evidence land in challenger scratch.
        for source in (self.plan.get("env") or {}, extra or {}):
            for key, value in source.items():
                if value is None:
                    env.pop(key, None)
                else:
                    env[key] = str(value)
        if self.plan.get("occupiedPortEnv") and self.sentinel_port:
            env[self.plan["occupiedPortEnv"]] = str(self.sentinel_port)
        if sync is not None and self.plan.get("syncEnv"):
            env[self.plan["syncEnv"]] = str(sync)
        return env

    def retain(self, run, folder):
        """Validate the report, copy the run's evidence, and check its source binding."""
        problems = []
        report = parse_document(run["stdout"])
        record = {"argv": run["argv"], "exit": run["exit"], "ms": run["ms"], "stdout": str((folder / "stdout.txt").relative_to(self.evidence)),
                  "stderr": str((folder / "stderr.txt").relative_to(self.evidence)), "observedProcesses": run["observedProcesses"],
                  "observedIdentities": run["observedIdentities"], "survivors": run["survivors"],
                  "ownershipVerified": run["ownershipVerified"]}
        if run["timedOut"]:
            problems.append(f"the command did not finish within {self.timeout}s")
        if not run["ownershipVerified"]:
            problems.append("blocked: no process table, so process cleanup is unverified")
        elif run["survivors"]:
            problems.append(f"processes started by the run outlived it: {run['survivors']}")
        if report is None or not isinstance(report, dict):
            problems.append("no JSON report on stdout")
            return None, record, problems
        report_file = folder / "report.json"
        report_file.write_text(run["stdout"])
        if report.get("mode") in ("discovery", "plan", "error") or run["exit"] is None:
            return report, record, problems
        checked = subprocess.run(["bash", str(CONFORM), "report", str(report_file), "--exit", str(run["exit"])],
                                 capture_output=True, text=True)
        (folder / "conformance.json").write_text(checked.stdout)
        try:
            verdict = json.loads(checked.stdout)
        except ValueError:
            verdict = {"valid": False, "findings": [{"message": checked.stderr.strip()}]}
        record.update(runId=report.get("runId"), status=report.get("status"), conformant=verdict.get("valid"))
        if not verdict.get("valid"):
            problems.append("report rejected: " + "; ".join(f.get("message", "") for f in verdict.get("findings", [])[:4]))
        head = ((report.get("source") or {}).get("identity") or {}).get("head")
        if head != self.head:
            problems.append(f"report source head {head!r} is not the challenged commit {self.head}")
        evidence_dir = report.get("evidenceDir")
        if isinstance(evidence_dir, str) and os.path.isdir(evidence_dir):
            target = folder / "control-evidence"
            shutil.copytree(evidence_dir, target, symlinks=True)
            record["controlEvidence"] = str(target.relative_to(self.evidence))
            for item in report.get("artifactDigests") or []:
                path = item.get("path") if isinstance(item, dict) else None
                if not isinstance(path, str) or not inside(evidence_dir, path):
                    problems.append(f"artifact outside the run's evidence directory: {path!r}")
                    continue
                copy = target / os.path.relpath(path, evidence_dir)
                if not copy.is_file() or sha256(copy.read_bytes()) != item.get("sha256"):
                    problems.append(f"retained artifact differs from its report digest: {path}")
            if inside(self.scratch, evidence_dir):
                shutil.rmtree(evidence_dir, ignore_errors=True)
        else:
            problems.append("the run report names no readable evidence directory")
        return report, record, problems

    def sentinel_ok(self):
        if self.sentinel is None:
            return False
        if self.sentinel.poll() is not None:
            return False
        try:
            with socket.create_connection(("127.0.0.1", self.sentinel_port), timeout=3) as conn:
                conn.settimeout(3)
                return conn.recv(256).decode() == self.sentinel_token
        except OSError:
            return False

    def guard(self, entry):
        """Shared checks after every probe: the unknown listener and the user's checkout."""
        alive = self.sentinel_ok()
        changes = state_diff(self.before, checkout_state(self.repo), include_worktrees=False)
        self.doc["preservation"].append({"after": entry["probe"], "unchanged": not changes, "changes": changes[:50]})
        entry["unknownListenerAlive"] = alive
        problems = []
        if not alive:
            problems.append(f"the unknown listener on port {self.sentinel_port} no longer answers")
        if changes:
            problems.append("the user's checkout changed: " + ", ".join(changes[:10]))
        if problems and entry["status"] != "failed":
            entry["status"] = "failed"
            entry["detail"] = "; ".join(problems) + f" (probe result before this check: {entry['detail']})"

    def outcome(self, name, runs, problems, success, extra=None):
        failing = [p for p in problems if not p.startswith("blocked:")]
        status = "failed" if failing else "blocked" if problems else "passed"
        entry = self.probe(name, status, "; ".join(problems) if problems else success, runs, extra)
        self.guard(entry)
        return entry

    # Probes ---------------------------------------------------------------------
    def invoke(self, name, tree, args, env, timeout=None):
        folder = self.folder(name)
        return Run(self.command, args, tree, env, timeout or self.timeout, folder).start(), folder

    def simple(self, name, tree, args, want_exit, env=None, check_report=False):
        run, folder = self.invoke(name, tree, args, env or self.env(name))
        result = run.finish()
        report, record, problems = self.retain(result, folder)
        if not check_report:
            problems = [p for p in problems if not p.startswith("report rejected") and "evidence directory" not in p and "source head" not in p]
        if result["exit"] != want_exit:
            problems.append(f"expected exit {want_exit}, got {result['exit']}")
        return report, record, problems

    def scenario_failed(self, report, sid):
        for check in report.get("checks") or []:
            if isinstance(check, dict) and check.get("status") == "failed":
                named = check.get("failed") if isinstance(check.get("failed"), list) else check.get("executed") or []
                if sid in named:
                    return True
        return False

    def wait_for(self, run, sync):
        """Wait until the run is underway: the fixture's ready file, or a started descendant."""
        deadline = time.time() + self.timeout
        while time.time() < deadline and run.proc.poll() is None:
            if sync is not None and (sync / "ready").exists():
                return "the runner wrote its ready file"
            if sync is None and len(run.descendants()) >= 2:
                time.sleep(0.5)
                return "descendant processes were running"
            time.sleep(0.02)
        return None

    def run_static(self, tree):
        out = subprocess.run(["bash", str(CONFORM), "static", str(tree)], capture_output=True, text=True)
        try:
            static = json.loads(out.stdout)
        except ValueError:
            self.probe("static", "failed", "the static checker printed no JSON: " + out.stderr[-500:])
            return None
        folder = self.evidence / "probes" / "static"
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "static.json").write_text(out.stdout)
        command = static["control"]["keys"].get("Command")
        if not command:
            self.probe("static", "blocked", "HEAD has no Command: line reached from a Control: pointer")
            return None
        entry = self.probe("static", "passed" if static["conformant"] else "failed",
                           "HEAD is statically conformant" if static["conformant"] else
                           "static findings: " + "; ".join(f["message"] for f in static["findings"] if f["severity"] == "error")[:800])
        self.guard(entry)
        return static

    def run(self):
        self.before = self.sentinel = None
        self.sentinel_port = 0
        try:
            self.head = git(self.repo, "rev-parse", "--verify", "HEAD").stdout.decode().strip()
            self.before = checkout_state(self.repo)
            self.doc["source"] = {"head": self.head, "checkoutBefore": state_summary(self.before)}
            if git(self.repo, "status", "--porcelain", check=False).stdout.strip():
                self.doc["excludedChanges"] = "worktrees are built from HEAD; uncommitted changes in the checkout were not challenged"
            if self.plan_path:
                shutil.copyfile(self.plan_path, self.evidence / "plan.json")
                self.doc["plan"] = {"path": str(self.plan_path), "sha256": sha256(Path(self.plan_path).read_bytes()), "retained": "plan.json"}
            self.sentinel_token = "leyline-" + sha256(os.urandom(16))[:16]
            self.sentinel = subprocess.Popen([sys.executable, "-c", SENTINEL, "leyline-challenge-sentinel", self.sentinel_token],
                                             stdout=subprocess.PIPE, text=True, start_new_session=True)
            self.sentinel_port = int(self.sentinel.stdout.readline().strip() or 0)
            self.doc["sentinel"] = {"pid": self.sentinel.pid, "port": self.sentinel_port,
                                    "offeredAs": self.plan.get("occupiedPortEnv")}
            self.body()
        finally:
            # Cleanup must finish even if the signal that interrupted the challenge repeats.
            for signum in (signal.SIGINT, signal.SIGTERM):
                signal.signal(signum, signal.SIG_IGN)
            aborted = [run.abort() for run in list(ACTIVE)]
            if aborted:
                self.doc["interruptedRuns"] = aborted
            for tree in list(self.trees):
                self.drop_tree(tree)
            if self.sentinel is not None:
                alive_at_end = self.sentinel_ok()
                self.doc["sentinel"]["aliveAtEnd"] = alive_at_end
                if self.sentinel.poll() is None:
                    self.sentinel.terminate()
                    try:
                        self.sentinel.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        self.sentinel.kill()
                        self.sentinel.wait()
                if not alive_at_end:
                    self.probe("unknown-listener", "failed", "the unknown listener did not survive the challenge")
            if self.before is not None:
                after = checkout_state(self.repo)
                changes = state_diff(self.before, after, include_worktrees=True)
                self.doc["source"]["checkoutAfter"] = state_summary(after)
                self.doc["preservation"].append({"after": "cleanup", "unchanged": not changes, "changes": changes[:50]})
                if changes:
                    self.probe("preservation", "failed", "the user's checkout differs after cleanup: " + ", ".join(changes[:10]))
            shutil.rmtree(self.scratch, ignore_errors=True)

    def body(self):
        base = self.worktree("base")
        static = self.run_static(base)
        if static is None:
            return
        self.command = static["control"]["keys"]["Command"]
        prepare = static["control"]["keys"].get("Prepare")
        feature = self.feature or self.plan.get("feature")
        if feature is None:
            with_break = [static["scenarios"][s] for s in static["breaks"] if s in static["scenarios"]]
            feature = with_break[0] if with_break else (static["features"][0] if static["features"] else None)
        if feature is None:
            self.probe("feature", "blocked", "HEAD has no feature records to challenge")
            return
        self.feature = self.doc["feature"] = feature

        if not self.prepared(base, "prepare", prepare):
            return

        _, record, problems = self.simple("list", base, ["list", "--json"], 0)
        listed = parse_document(Path(self.evidence, record["stdout"]).read_text())
        missing = [f for f in static["features"] if f'"{f}"' not in json.dumps(listed)] if listed is not None else static["features"]
        if missing:
            problems.append(f"list omits features {', '.join(missing)}")
        self.outcome("list", [record], problems, "every feature record is listed")

        _, record, problems = self.simple("describe", base, ["describe", "feature", feature, "--json"], 0)
        self.outcome("describe", [record], problems, "describe feature exits 0 with JSON")

        _, record, problems = self.simple("unknown", base, ["feature", "challenge-missing-feature", "--json"], 2)
        self.outcome("unknown", [record], problems, "an unknown feature is a usage error")

        report, record, problems = self.simple("baseline", base, ["feature", feature, "--json"], 0, check_report=True)
        if report and report.get("status") != "passed":
            problems.append(f"baseline status {report.get('status')!r}")
        baseline = self.outcome("baseline", [record], problems, f"feature {feature} passes at HEAD")
        passed = baseline["status"] == "passed"

        patches = [s for s in static["breaks"] if static["scenarios"].get(s) == feature]
        self.break_patch = None
        if patches:
            self.break_sid = patches[0]
            self.break_patch = os.path.join(static["control"]["keys"]["Breaks"], self.break_sid + ".patch")

        def selected(name):
            names = {"break", "restore"} if name == "break" else {name}
            if self.only is not None and not names & self.only:
                self.probe(name, "not_run", "left out by --only")
                return False
            if not passed:
                self.probe(name, "blocked", "the baseline did not pass, so this observation would establish nothing")
                return False
            return True

        if selected("break"):
            self.break_restore(prepare)
        else:
            self.probe("restore", self.probes[-1]["status"], "the break probe did not run")
        if selected("parallel"):
            self.parallel(base)
        for name, signum, code in (("cancel-sigint", signal.SIGINT, 130), ("cancel-sigterm", signal.SIGTERM, 143)):
            if selected(name):
                self.cancel(base, name, signum, code)
        for variant in self.plan.get("variants") or []:
            if selected(variant["name"]):
                self.variant(variant, prepare)

    def break_restore(self, prepare):
        if not self.break_patch:
            self.probe("break", "blocked", f"no break patch is declared for a scenario of {self.feature}")
            self.probe("restore", "blocked", "no break patch to revert")
            return
        tree = self.worktree("break")
        if not self.prepared(tree, "break", prepare):
            self.probe("restore", "blocked", "the break worktree could not be prepared")
            return
        applied = git(tree, "apply", self.break_patch, check=False)
        if applied.returncode:
            entry = self.probe("break", "failed", f"the break patch no longer applies: {applied.stderr.decode().strip()}")
            self.guard(entry)
            self.probe("restore", "blocked", "the break patch did not apply")
            self.drop_tree(tree)
            return
        report, record, problems = self.simple("break", tree, ["feature", self.feature, "--json"], 1, check_report=True)
        if report and not self.scenario_failed(report, self.break_sid):
            problems.append(f"no failed check names {self.break_sid}, so the failure may be unrelated")
        self.outcome("break", [record], problems, f"the declared break fails the run and names {self.break_sid}")
        reverted = git(tree, "apply", "-R", self.break_patch, check=False)
        dirty = git(tree, "status", "--porcelain", "--untracked-files=all", check=False).stdout.decode().strip()
        if reverted.returncode or dirty:
            entry = self.probe("restore", "failed", "reverting the break patch did not restore HEAD bytes: " + (reverted.stderr.decode().strip() or dirty[:300]))
            self.guard(entry)
        else:
            report, record, problems = self.simple("restore", tree, ["feature", self.feature, "--json"], 0, check_report=True)
            if report and report.get("status") != "passed":
                problems.append(f"restored status {report.get('status')!r}")
            self.outcome("restore", [record], problems, "reverting the break patch passes again")
        self.drop_tree(tree)

    def prepared(self, tree, label, prepare):
        if not prepare:
            return True
        folder = self.folder(label + "-prepare")
        result = Run(prepare, [], tree, self.env(label), self.timeout, folder).start().finish()
        if result["exit"] != 0 or result["survivors"]:
            entry = self.probe(label, "blocked", f"Prepare: exited {result['exit']} with surviving processes {result['survivors']}")
            self.guard(entry)
            return False
        return True

    def parallel(self, tree):
        shared = self.env("parallel")  # One environment and TMPDIR: distinct resources must come from the control.
        runs = [self.invoke("parallel", tree, ["feature", self.feature, "--json"], shared) for _ in range(2)]
        results = [run.finish() for run, _ in runs]
        problems, records, reports = [], [], []
        for (run, folder), result in zip(runs, results):
            report, record, issues = self.retain(result, folder)
            records.append(record)
            reports.append(report or {})
            problems += issues
            if result["exit"] != 0:
                problems.append(f"a concurrent run exited {result['exit']}")
        a, b = reports
        def groups(report):
            return {p.get("pgid") for p in report.get("processes") or [] if isinstance(p, dict) and p.get("pgid")}
        distinct = {
            "runId": a.get("runId") != b.get("runId"),
            "evidenceDir": a.get("evidenceDir") != b.get("evidenceDir"),
            "snapshot": (a.get("snapshot") or {}).get("path") != (b.get("snapshot") or {}).get("path"),
            "processGroups": bool(groups(a)) and bool(groups(b)) and not groups(a) & groups(b),
            "observedProcesses": not {(i[0], i[2]) for i in records[0]["observedIdentities"]} & {(i[0], i[2]) for i in records[1]["observedIdentities"]},
        }
        clash = [k for k, ok in distinct.items() if not ok]
        if clash:
            problems.append("concurrent runs shared " + ", ".join(clash))
        self.outcome("parallel", records, problems, "two concurrent runs pass with distinct run ids, evidence, snapshots and processes",
                     {"distinct": distinct})

    def cancel(self, tree, name, signum, code):
        sync = None
        if self.plan.get("syncEnv"):
            sync = self.scratch / f"sync-{name}"
            sync.mkdir()
        run, folder = self.invoke(name, tree, ["feature", self.feature, "--json"], self.env(name, sync=sync))
        when = self.wait_for(run, sync)
        problems = []
        held = run.descendants()
        if when is None:
            problems.append("blocked: the run ended or timed out before cancellation could be delivered")
        else:
            run.signal_group(signum)  # Like a terminal interrupt: the CLI's foreground group, not the runner's group.
        result = run.finish()
        report, record, issues = self.retain(result, folder)
        problems += issues
        record["signalledWhile"] = when
        record["descendantsAtSignal"] = sorted(held)
        if when is not None:
            if result["exit"] != code:
                problems.append(f"expected exit {code}, got {result['exit']}")
            if report and report.get("status") != "cancelled":
                problems.append(f"status {report.get('status')!r} after {signal.Signals(signum).name}")
            if report and not (report.get("snapshot") or {}).get("cleaned", False):
                problems.append("the snapshot was not removed after cancellation")
        self.outcome(name, [record], problems, f"{signal.Signals(signum).name} cancels with exit {code} and every started process is gone")

    def variant(self, variant, prepare):
        name, expect = variant["name"], variant["expect"]
        tree = self.worktree(name)
        if not self.prepared(tree, name, prepare):
            self.drop_tree(tree)
            return
        if variant.get("break"):
            if not self.break_patch:
                self.probe(name, "blocked", "the variant applies the declared break, but none is declared")
                self.drop_tree(tree)
                return
            applied = git(tree, "apply", self.break_patch, check=False)
            if applied.returncode:
                self.guard(self.probe(name, "failed", f"the break patch no longer applies: {applied.stderr.decode().strip()}"))
                self.drop_tree(tree)
                return
        for rel in variant.get("remove") or []:
            target = tree / rel
            if not inside(tree, target) or not (target.exists() or target.is_symlink()):
                self.probe(name, "blocked", f"cannot remove {rel} from the disposable worktree")
                self.drop_tree(tree)
                return
            shutil.rmtree(target) if target.is_dir() and not target.is_symlink() else target.unlink()
        sync = None
        mutate = variant.get("mutate")
        if mutate:
            if not inside(tree, tree / mutate["path"]) or not (tree / mutate["path"]).is_file():
                self.guard(self.probe(name, "blocked", f"the mutate path is not a file inside the worktree: {mutate['path']}"))
                self.drop_tree(tree)
                return
            sync = self.scratch / f"sync-{name}"
            sync.mkdir()
        run, folder = self.invoke(name, tree, ["feature", self.feature, "--json"], self.env(name, variant.get("env"), sync))
        problems = []
        if mutate:
            if self.wait_for(run, sync) is None:
                problems.append("blocked: the runner never wrote its ready file, so the mutation was not made during execution")
            else:
                with open(tree / mutate["path"], "a") as handle:
                    handle.write(mutate.get("append", "\n// changed by challenge.sh during the run\n"))
                (sync / "release").write_text("release")
        result = run.finish()
        report, record, issues = self.retain(result, folder)
        problems += issues
        if report:
            if report.get("status") != expect["status"]:
                problems.append(f"expected status {expect['status']}, got {report.get('status')!r}")
            for sid in expect.get("failed") or []:
                if not self.scenario_failed(report, sid):
                    problems.append(f"the failed check for {sid} was not retained")
            for need in expect.get("missing") or []:
                if not any(isinstance(p, dict) and p.get("need") == need and p.get("status") == "missing" for p in report.get("prerequisites") or []):
                    problems.append(f"prerequisite {need} is not reported missing")
            if "sourceChanged" in expect and (report.get("source") or {}).get("sourceChanged") is not expect["sourceChanged"]:
                problems.append(f"sourceChanged is not {expect['sourceChanged']}")
        self.outcome(name, [record], problems, f"{expect['status']} as declared" + (f", retaining failures for {', '.join(expect['failed'])}" if expect.get("failed") else ""),
                     {"expect": expect})
        self.drop_tree(tree)


def load_plan(path):
    if path is None:
        return {}
    try:
        plan = json.loads(Path(path).read_text())
    except (OSError, ValueError) as exc:
        usage(f"cannot read plan {path}: {exc}")
    if not isinstance(plan, dict):
        usage("the plan must be a JSON object")
    allowed = {"feature", "timeoutSeconds", "env", "occupiedPortEnv", "syncEnv", "variants"}
    if set(plan) - allowed:
        usage(f"unknown plan keys: {sorted(set(plan) - allowed)}")
    for key in ("occupiedPortEnv", "syncEnv", "feature"):
        if key in plan and (not isinstance(plan[key], str) or not plan[key]):
            usage(f"plan {key} must be a non-empty string")
    def env_map(value, where):
        if value is None:
            return
        if not isinstance(value, dict) or any(not isinstance(k, str) or not re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", k) or not (v is None or isinstance(v, (str, int))) for k, v in value.items()):
            usage(f"{where} env must map variable names to strings or null")
    env_map(plan.get("env"), "plan")
    names = set()
    for variant in plan.get("variants") or []:
        if not isinstance(variant, dict) or not NAME.match(str(variant.get("name", ""))):
            usage("each variant needs a lowercase hyphenated name")
        if variant["name"] in BUILTIN or variant["name"] in names:
            usage(f"variant name {variant['name']} is reserved or repeated")
        names.add(variant["name"])
        extra = set(variant) - {"name", "env", "break", "remove", "mutate", "expect"}
        if extra:
            usage(f"variant {variant['name']} has unknown keys {sorted(extra)}")
        env_map(variant.get("env"), f"variant {variant['name']}")
        expect = variant.get("expect")
        if not isinstance(expect, dict) or expect.get("status") not in STATUSES or set(expect) - {"status", "failed", "missing", "sourceChanged"}:
            usage(f"variant {variant['name']} needs expect.status and only failed, missing or sourceChanged besides")
        for rel in (variant.get("remove") or []) + ([variant["mutate"].get("path")] if isinstance(variant.get("mutate"), dict) else []):
            if not isinstance(rel, str) or not rel or rel.startswith("/") or ".." in Path(rel).parts or ".git" in Path(rel).parts:
                usage(f"variant {variant['name']} paths must stay inside the checkout")
        if "mutate" in variant:
            if not isinstance(variant["mutate"], dict) or not plan.get("syncEnv"):
                usage("a mutate variant needs mutate.path and a plan syncEnv handshake")
    return plan


def main(argv):
    repo = plan_path = feature = evidence = None
    trust, timeout, only = False, None, None
    i = 0
    while i < len(argv):
        arg = argv[i]
        value = argv[i + 1] if i + 1 < len(argv) else None
        if arg == "--trust":
            trust, i = True, i + 1
            continue
        if arg in ("--plan", "--feature", "--timeout", "--evidence", "--only"):
            if value is None:
                usage(f"{arg} needs a value")
            if arg == "--plan":
                plan_path = value
            elif arg == "--feature":
                feature = value
            elif arg == "--timeout":
                if not value.isdigit() or int(value) <= 0:
                    usage("--timeout takes whole seconds")
                timeout = int(value)
            elif arg == "--evidence":
                evidence = value
            else:
                only = {name for name in value.split(",") if name}
            i += 2
            continue
        if repo is None and not arg.startswith("--"):
            repo, i = arg, i + 1
            continue
        usage(f"unexpected argument {arg}")
    if repo is None:
        usage("missing REPO")
    if not trust:
        usage("the challenge runs the project's own code; pass --trust once the user has agreed to that")
    root = Path(repo).resolve()
    if git(root, "rev-parse", "--show-toplevel", check=False).returncode:
        usage(f"not a git checkout: {root}")
    plan = load_plan(plan_path)
    if only is not None:
        unknown = only - set(OPTIONAL) - {v["name"] for v in plan.get("variants") or []}
        if unknown:
            usage(f"--only names unknown probes {sorted(unknown)}")
    # Check TMPDIR before anything is created there; a default evidence folder would land in it.
    if inside(root, tempfile.gettempdir()):
        usage("TMPDIR must be outside the checkout")
    if evidence is None:
        evidence = tempfile.mkdtemp(prefix="leyline-challenge-evidence-")
    evidence = Path(evidence).resolve()
    if inside(root, evidence):
        usage("the evidence directory must be outside the checkout")
    if evidence.exists() and any(evidence.iterdir()):
        usage("the evidence directory must be new or empty")
    evidence.mkdir(parents=True, exist_ok=True)
    challenge = Challenge(root, plan, Path(plan_path).resolve() if plan_path else None, feature,
                          timeout or int(plan.get("timeoutSeconds") or 900), evidence, only)
    for signum in (signal.SIGINT, signal.SIGTERM):
        signal.signal(signum, interrupted)
    stopped_by = None
    try:
        challenge.run()
    except RuntimeError as exc:
        challenge.probe("challenge", "blocked", str(exc))
    except Interrupted as exc:
        stopped_by = exc.args[0]
        challenge.doc["interrupted"] = stopped_by
        challenge.probe("challenge", "interrupted", f"the challenge received {stopped_by}; in-flight runs were stopped and cleanup ran")
    doc = challenge.doc
    (evidence / "challenge.json").write_text(json.dumps(doc, indent=2) + "\n")
    files = []
    for path in sorted(p for p in evidence.rglob("*") if p.is_file() and not p.is_symlink()):
        rel = path.relative_to(evidence).as_posix()
        if rel not in ("manifest.json", "result.json"):
            data = path.read_bytes()
            files.append({"path": rel, "sha256": sha256(data), "bytes": len(data)})
    manifest = {"contract": "control/0", "files": files, "digest": sha256(json.dumps(files, sort_keys=True).encode())}
    (evidence / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    # Scratch, worktrees and control snapshots are gone; the retained copy must stand alone.
    mismatched = [f["path"] for f in files if not (evidence / f["path"]).is_file() or sha256((evidence / f["path"]).read_bytes()) != f["sha256"]]
    doc["retained"] = {"dir": str(evidence), "manifest": "manifest.json", "files": len(files), "digest": manifest["digest"],
                       "scratchRemoved": not challenge.scratch.exists(), "verifiedAfterCleanup": not mismatched}
    if mismatched or challenge.scratch.exists():
        challenge.probe("retention", "failed", "retained evidence did not verify after cleanup: " + ", ".join(mismatched[:10]))
    states = {p["status"] for p in doc["probes"]}
    doc["outcome"] = "interrupted" if stopped_by else "failed" if "failed" in states else "incomplete" if states - {"passed"} else "passed"
    (evidence / "result.json").write_text(json.dumps(doc, indent=2) + "\n")
    print(json.dumps(doc, indent=2))
    if stopped_by:
        return 128 + getattr(signal, stopped_by)
    return 1 if "failed" in states else 3 if states - {"passed"} else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[2:]))
PY
