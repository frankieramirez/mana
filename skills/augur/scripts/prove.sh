#!/usr/bin/env bash
# Run a proof against a preserved source snapshot, without changing the user's checkout.
set -euo pipefail
exec python3 - "$@" <<'PY'
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import signal
import stat
import subprocess
import sys
import tempfile

parser = argparse.ArgumentParser(description="Run a bash proof in an isolated, revision-bound source snapshot.")
parser.add_argument("--repo", required=True)
source = parser.add_mutually_exclusive_group(required=True)
source.add_argument("--revision", help="Reviewed commit, never a substitute checkout")
source.add_argument("--working-tree", action="store_true", help="Tracked and nonignored untracked source")
parser.add_argument("--include", action="append", default=[], help="Additional ignored source file, relative to repo")
parser.add_argument("--proof", required=True, help="Bash proof script to preserve and execute")
parser.add_argument("--context", required=True, help="JSON object with runtime and dependencies evidence")
parser.add_argument("--setup", help="Optional bash script installing pinned dependencies into the snapshot")
parser.add_argument("--break", dest="breaks", action="append", default=[],
                    help="Patch that makes the fact false; the proof must fail on a copy with it applied")
parser.add_argument("--timeout-seconds", type=float, default=120, help="Per-script execution budget (default: 120)")
args = parser.parse_args()
if args.timeout_seconds <= 0:
    parser.error("--timeout-seconds must be positive")
run = Path(tempfile.mkdtemp(prefix="augur-proof-"))
report = {"schemaVersion": 1, "status": "unproven", "runDirectory": str(run), "reason": None,
          "source": {}, "proof": None, "setup": None, "challenge": "not-run", "breaks": [], "coverage": None}
repo = Path(args.repo).resolve()
env = dict(os.environ, GIT_OPTIONAL_LOCKS="0")
for key in ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "PYTHONPATH", "NODE_PATH", "BASH_ENV", "ENV"):
    env.pop(key, None)


def git(*argv, data=None):
    return subprocess.run(["git", "-C", str(repo), *argv], input=data, env=env,
                          check=True, capture_output=True).stdout


def relative(name):
    path = Path(name)
    if path.is_absolute() or not path.parts or any(p in ("..", ".git") for p in path.parts):
        raise ValueError("unsafe source path: " + name)
    return path


def read_file(root, name):
    path = root / relative(name)
    if any(parent.is_symlink() for parent in path.parents if parent != root and root in parent.parents):
        raise ValueError("source path traverses a symlink: " + name)
    mode = path.lstat().st_mode
    if stat.S_ISLNK(mode):
        try:
            path.resolve().relative_to(root)
        except (ValueError, RuntimeError):
            raise ValueError("source symlink escapes the snapshot: " + name)
        return ("120000", os.fsencode(os.readlink(path)))
    if not stat.S_ISREG(mode):
        raise ValueError("unsupported source file: " + name)
    return ("100755" if mode & stat.S_IXUSR else "100644", path.read_bytes())


def working_source():
    for item in git("ls-files", "--stage", "-z").split(b"\0"):
        if not item:
            continue
        info, name = item.split(b"\t", 1)
        mode, _, stage = info.split()
        if mode == b"160000" or stage != b"0":
            raise ValueError("submodule or unresolved index requires an explicit isolated setup: " + os.fsdecode(name))
    names = set(os.fsdecode(p) for p in git("ls-files", "--cached", "--others", "--exclude-standard", "-z").split(b"\0") if p)
    names.update(args.include)
    files = {}
    for name in sorted(names):
        path = repo / relative(name)
        if not path.exists() and not path.is_symlink():
            if name in args.include:
                raise ValueError("additional source file is missing: " + name)
            continue  # A tracked deletion is part of the working-tree snapshot.
        files[name] = read_file(repo, name)
    return files


def commit_source(revision):
    entries = []
    for item in git("ls-tree", "-r", "-z", revision).split(b"\0"):
        if not item:
            continue
        info, name = item.split(b"\t", 1)
        mode, kind, oid = info.split()
        if kind != b"blob" or mode not in (b"100644", b"100755", b"120000"):
            raise ValueError("submodule or unsupported tree entry: " + os.fsdecode(name))
        entries.append((os.fsdecode(name), mode.decode(), oid))
    # Read Git objects directly: archive export-ignore rules must not remove source.
    data = git("cat-file", "--batch", data=b"".join(oid + b"\n" for _, _, oid in entries))
    offset, files = 0, {}
    for name, mode, oid in entries:
        end = data.index(b"\n", offset)
        actual, kind, size = data[offset:end].split()
        if actual != oid or kind != b"blob":
            raise ValueError("source object could not be read: " + name)
        offset = end + 1
        files[name] = (mode, data[offset:offset + int(size)])
        offset += int(size) + 1
    return files


def manifest(files):
    return [{"path": name, "mode": mode, "sha256": hashlib.sha256(data).hexdigest()}
            for name, (mode, data) in sorted(files.items())]


def digest(files):
    return hashlib.sha256(json.dumps(manifest(files), sort_keys=True, ensure_ascii=True).encode()).hexdigest()


def inventory(root):
    return {str(path.relative_to(root)): read_file(root, str(path.relative_to(root)))
            for path in sorted(root.rglob("*")) if path.is_symlink() or not path.is_dir()}


def execute(path, label, source_root, manifest_path=None):
    output = run / (label + ".stdout.txt")
    errors = run / (label + ".stderr.txt")
    command = ["bash", str(path)]
    script_digest = hashlib.sha256(path.read_bytes()).hexdigest()
    with output.open("wb") as stdout, errors.open("wb") as stderr:
        process = subprocess.Popen(command, cwd=source_root, env=dict(env, AUGUR_SOURCE=str(source_root),
                                   AUGUR_ARTIFACTS=str(run / "artifacts"), AUGUR_MANIFEST=str(manifest_path or run / "source-manifest.json"),
                                   PYTHONDONTWRITEBYTECODE="1"),
                                   stdout=stdout, stderr=stderr, start_new_session=True)
        timed_out = False
        try:
            code = process.wait(timeout=args.timeout_seconds)
        except subprocess.TimeoutExpired:
            timed_out = True
        # The shell exiting does not mean its background jobs have finished.
        # End run-owned work before accepting any final source or output hashes.
        remaining_processes = False
        try:
            os.killpg(process.pid, 0)
        except ProcessLookupError:
            pass
        else:
            remaining_processes = not timed_out
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        if timed_out:
            code = process.wait()
    return {"command": command, "cwd": str(source_root), "scriptSha256": script_digest,
            "exitCode": code, "stdout": str(output), "stderr": str(errors), "timedOut": timed_out, "backgroundProcesses": remaining_processes,
            "scriptChanged": hashlib.sha256(path.read_bytes()).hexdigest() != script_digest}


def check_execution(result, label):
    if result["timedOut"]:
        raise ValueError(label + " exceeded its execution budget; see retained output")
    if result["backgroundProcesses"]:
        raise ValueError(label + " left background processes running; terminated its process group")
    if result["scriptChanged"]:
        raise ValueError(label + " script changed during execution")


def coverage_line(result):
    # The proof states what it covered on a line of its own: "coverage: every age from 0 to 150, 1 reached the boundary".
    lines = [line for line in Path(result["stdout"]).read_text(errors="replace").splitlines() if line.startswith("coverage: ")]
    return lines[-1][len("coverage: "):].strip() if lines else None


def challenge(index, patch, prepared_root, files):
    # Apply the break to a copy of the prepared tree, so setup does not run twice and the
    # reviewed snapshot stays exactly as the passing proof saw it.
    label = "break-%d" % index
    target = preserved_script(patch, label + "-patch")
    broken = run / label
    shutil.copytree(prepared_root, broken, symlinks=True)
    before = digest(inventory(broken))
    applied = subprocess.run(["git", "apply", "--whitespace=nowarn", str(target)], cwd=broken, capture_output=True,
                             env=dict(env, GIT_CEILING_DIRECTORIES=str(run.parent)))
    entry = {"patch": str(target), "patchSha256": hashlib.sha256(target.read_bytes()).hexdigest(), "source": str(broken),
             "applied": applied.returncode == 0, "detected": False, "execution": None}
    if applied.returncode != 0:
        raise ValueError("break patch %d does not apply: %s" % (index, applied.stderr.decode(errors="replace").strip()))
    if digest(inventory(broken)) == before:
        raise ValueError("break patch %d changed nothing" % index)
    prepared = inventory(prepared_root)
    names = set(files) | {name for name in inventory(broken) if name not in prepared}
    broken_files = {name: read_file(broken, name) for name in sorted(names) if (broken / name).exists() or (broken / name).is_symlink()}
    broken_manifest = run / (label + "-manifest.json")
    broken_manifest.write_text(json.dumps(manifest(broken_files), indent=2) + "\n")
    entry["manifest"] = str(broken_manifest)
    report["breaks"].append(entry)
    entry["execution"] = execute(proof, label, broken, broken_manifest)
    check_execution(entry["execution"], label)
    entry["detected"] = entry["execution"]["exitCode"] != 0
    return entry["detected"]


def preserved_script(path, label):
    target = run / (label + ".sh")
    target.write_bytes(Path(path).read_bytes())
    return target


exit_code = 3
try:
    repo = Path(os.fsdecode(git("rev-parse", "--show-toplevel")).strip()).resolve()
    if args.revision and args.include:
        raise ValueError("--include applies only to a working-tree snapshot")
    context = json.loads(Path(args.context).read_text())
    if not isinstance(context, dict) or not context.get("runtime") or not context.get("dependencies"):
        raise ValueError("context must record runtime and dependencies evidence")
    (run / "context.json").write_text(json.dumps(context, indent=2) + "\n")
    report["context"] = str(run / "context.json")
    proof = preserved_script(args.proof, "proof")
    setup = preserved_script(args.setup, "setup") if args.setup else None
    head = git("rev-parse", "--verify", "HEAD").decode().strip()
    revision = git("rev-parse", "--verify", args.revision + "^{commit}").decode().strip() if args.revision else head
    files = commit_source(revision) if args.revision else working_source()
    original_digest = digest(files)
    report["source"] = {"kind": "commit" if args.revision else "working-tree", "repository": str(repo),
                        "revision": revision, "sourceDigest": original_digest, "additionalInputs": args.include,
                        "changedDuringRun": False}
    (run / "source-manifest.json").write_text(json.dumps(manifest(files), indent=2) + "\n")
    source_root = run / "source"
    source_root.mkdir()
    (run / "artifacts").mkdir()
    # Write regular files before symlinks, so a link cannot redirect a later write.
    for name, (mode, data) in sorted(files.items(), key=lambda item: item[1][0] == "120000"):
        path = source_root / relative(name)
        path.parent.mkdir(parents=True, exist_ok=True)
        if mode == "120000":
            path.symlink_to(os.fsdecode(data))
        else:
            path.write_bytes(data)
            path.chmod(0o755 if mode == "100755" else 0o644)
    if digest(inventory(source_root)) != original_digest:
        raise ValueError("snapshot differs from selected source")
    if not args.revision and (digest(working_source()) != original_digest or git("rev-parse", "HEAD").decode().strip() != head):
        raise ValueError("working source changed while capturing the snapshot")
    if setup:
        report["setup"] = execute(setup, "setup", source_root)
        check_execution(report["setup"], "setup")
        if report["setup"]["exitCode"] != 0:
            raise ValueError("dependency setup failed; see setup output")
        if digest({name: read_file(source_root, name) for name in files}) != original_digest:
            raise ValueError("dependency setup changed selected source")
    prepared_digest = digest(inventory(source_root))
    report["source"]["preparedDigest"] = prepared_digest
    report["proof"] = execute(proof, "proof", source_root)
    check_execution(report["proof"], "proof")
    snapshot_changed = digest(inventory(source_root)) != prepared_digest
    checkout_changed = not args.revision and (digest(working_source()) != original_digest or git("rev-parse", "HEAD").decode().strip() != head)
    report["source"]["snapshotChanged"] = snapshot_changed
    report["source"]["changedDuringRun"] = checkout_changed
    if snapshot_changed or checkout_changed:
        raise ValueError("source changed during execution; recapture and rerun")
    exit_code = report["proof"]["exitCode"]
    report["coverage"] = coverage_line(report["proof"])
    report["status"] = "passed" if exit_code == 0 else "failed"
    if exit_code < 0:
        exit_code = 128 - exit_code
    if exit_code == 0 and args.breaks:
        # A pass counts only once the same proof is seen failing on code that breaks the fact.
        missed = [index for index, patch in enumerate(args.breaks, 1) if not challenge(index, patch, source_root, files)]
        if digest(inventory(source_root)) != prepared_digest:
            raise ValueError("reviewed snapshot changed during the break runs; recapture and rerun")
        report["challenge"] = "missed" if missed else "detected"
        if missed:
            report["status"] = "unproven"
            report["reason"] = "proof passed on break %s; it cannot tell this code from the broken copy" % ", ".join(map(str, missed))
            exit_code = 3
except (OSError, ValueError, subprocess.SubprocessError) as error:
    report["status"] = "unproven"
    report["reason"] = str(error)
    exit_code = 3
finally:
    (run / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))
sys.exit(exit_code)
PY
