# The proving script

A proof calls the real code and exits non-zero when the safety fact is false. Paste its output verbatim. A passing execution supports rung 4 only when the assertions test the stated fact against the reviewed source.

## Select and preserve the source

Write the bash proof and a context JSON file outside the repository, in a private scratch directory created with `mktemp -d`. Record the observed runtime version and dependency version or lockfile evidence under `runtime` and `dependencies` in the context file. Use the project's own toolchain. An unverified dependency version leaves the fact unproven.

For a PR, resolve its full head commit and fetch that exact object if needed. Pass the resolved commit to the helper:

```bash
bash "<SKILL_DIR>/scripts/prove.sh" --repo "<repo root>" --revision "<reviewed commit>" --proof "<scratch>/fact.sh" --context "<scratch>/context.json"
```

For a branch, path, or base-ref review, include the current local changes:

```bash
bash "<SKILL_DIR>/scripts/prove.sh" --repo "<repo root>" --working-tree --proof "<scratch>/fact.sh" --context "<scratch>/context.json"
```

The helper copies tracked and nonignored untracked files, including local modifications and deletions. Add `--include <relative file>` for an ignored file that affects the fact. Inspect imported code, config and fixtures for relevant omitted inputs before running. Never use `--revision HEAD` to stand in for dirty source. A path-limited review still needs the source that its callers and dependencies execute.

The helper retains a private run directory with the source snapshot, file hashes, context, preserved scripts, output and `report.json`. It never switches branches or writes Git metadata. Commit snapshots read Git objects directly, including files excluded by archive attributes. Working-tree snapshots check the source before capture completes and after execution. A changed source identity produces `unproven`; recapture and rerun instead of attributing stale evidence to the latest tree. These are before/after checks, not a filesystem monitor.

## Run the real code

- **Check the loaded source.** The helper starts the proof in its isolated source directory and exports `AUGUR_SOURCE`. Import the exact function or module there, then bind the loaded first-party implementation to its expected selected-source path and SHA-256 in `AUGUR_MANIFEST`. Print the resolved path and hash. Snapshot containment alone is insufficient: setup could add a stale copy under another directory. Generated or compiled first-party code requires explicitly verified derivation from the selected source; otherwise report the fact as unproven. For Python, check the implementation module's `__file__` or the function's inspected source path, including modules under `src/`. Check the selected implementation file itself, not just a package wrapper. Use the equivalent loaded-module location for other runtimes. Do not change to the user's checkout, import its absolute paths, or reimplement the logic in the proof. Clearing ambient Python and Node import paths cannot prevent an editable installation, runtime startup hook or wrapper from loading another checkout. This source-origin assertion is required; the helper does not enforce arbitrary runtime imports or build derivations.
- **Use pinned dependencies.** If setup is necessary and already authorized, supply `--setup <scratch>/setup.sh`. It runs in the snapshot before the proof and must preserve the selected source and lockfiles. Record the actual runtime and dependency versions in the output as well as the context. Setup may add dependencies or build outputs; the helper hashes the prepared tree before running the proof. A copied environment that still imports the user's checkout is invalid evidence.
- **Keep source stable.** Put proof artifacts in `AUGUR_ARTIFACTS`, outside the snapshot. Source changes, including files added during the proof, make the run unproven. Python bytecode writes are disabled. No edits, commits or branch switches in the user's checkout. This helper isolates files; it is not a security sandbox for untrusted code.
- **Fail loud.** Assert the bad case. A script that only prints values does not test the fact. When the fact is that a value cannot be null, construct the input that could make it null and check the actual guard.
- **Keep the budget cheap.** Each setup or proof script has a 120-second default budget. Use `--timeout-seconds` only when the scoped check warrants it. A timeout is unproven, with output retained. Setup and proof scripts must stop and wait for their own background jobs before exiting. The helper terminates remaining processes in their process group and marks such a run unproven; a shell returning zero while its server still runs is incomplete execution. Do not detach work into another process group.
- **Paste the evidence.** Include the report path, reviewed commit, source digest, runtime/dependency context, command, exit code and output. Preserve a failure even if later rendering succeeds. `passed` records execution success; the report still needs to explain which assertion proves the safety fact.

A minimal proof file is:

```bash
#!/usr/bin/env bash
# Proves: <the fact, one line>
set -euo pipefail
cd "${AUGUR_SOURCE:?missing isolated source}"
<runtime> - <<'CODE'
<print the actual runtime and dependency versions>
<import the real implementation module from the current snapshot>
<assert its path and hash match the expected selected-source manifest entry>
<construct the bad case>
<assert; exit 1 on failure>
print("ok: <the fact>")
CODE
```

For example, a Python proof verifies the loaded implementation before testing its behavior:

```python
import hashlib
import json
import os
from pathlib import Path
import my_app.implementation as implementation

snapshot = Path(os.environ["AUGUR_SOURCE"]).resolve()
selected = json.loads(Path(os.environ["AUGUR_MANIFEST"]).read_text())
expected_path = "src/my_app/implementation.py"  # The reviewed implementation file.
expected = next(item for item in selected if item["path"] == expected_path)
assert expected["mode"] in ("100644", "100755"), "unproven: select the implementation file itself"
loaded = Path(implementation.__file__).resolve()
assert loaded == snapshot / expected_path, f"unproven: unexpected implementation path: {loaded}"
actual_hash = hashlib.sha256(loaded.read_bytes()).hexdigest()
assert actual_hash == expected["sha256"], "unproven: implementation differs from selected source"
print(f"implementation: {loaded}; sha256: {actual_hash}")
# Assert the safety fact by calling implementation here.
```

## When a cheap proof is impossible

Unavailable commits, unresolved merges, submodules requiring separate materialization, escaping symlinks, required Git metadata, missing dependencies or infrastructure may prevent this helper from running the exact source. Name the missing prerequisite and report the highest rung reached as **unproven**. Missing runtime or dependencies and a failed source-origin check leave the fact unproven even when the helper records the command as a nonzero `failed` execution; distinguish these from an assertion that disproves the safety fact. Do not substitute a successful run in another checkout. Put the cheapest real check in "Before you merge", such as a revision-bound staging run or a specific test the author can run.

The preserved directory can be rerun with its recorded command and working directory. If the source or prepared environment has changed, recapture with the helper and retain the new report. Evidence from another machine must carry the same source identity and runtime/dependency context.
