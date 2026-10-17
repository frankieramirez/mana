# Challenge an installed control

Load during Challenge when local execution is authorized. Every discovery or run command executes project code. Static conformance alone does not authorize execution.

Commit the candidate first. The challenge runs committed HEAD bytes in disposable git worktrees and names any uncommitted changes it left out.

```bash
bash "<SKILL_DIR>/scripts/conform.sh" static <repo>
bash "<SKILL_DIR>/scripts/challenge.sh" <repo> --trust --plan <plan.json> --evidence <empty-dir-outside-repo>
```

For one saved report from an ordinary run, use `conform.sh report <report.json> --exit <actual-code>`.

## What it runs

| Probe | Passes when |
|---|---|
| `static` | HEAD is statically conformant |
| `list`, `describe`, `unknown` | Discovery exits 0 with JSON and an unknown feature exits 2 |
| `baseline` | The feature passes with a valid report bound to HEAD |
| `break` | The declared patch fails the run with a failed check naming its scenario |
| `restore` | Reverting the patch restores HEAD bytes and the run passes again |
| `parallel` | Two concurrent runs pass with distinct run ids, evidence directories, snapshots, process groups and processes |
| `cancel-sigint`, `cancel-sigterm` | Signalling the CLI's process group while the runner is active returns cancelled with 130 or 143, and every started process is gone |
| plan variants | Each variant's report matches its declared outcome |

After every probe the challenger also checks:

- A listener the challenger owns, on a port the CLI did not open, still answers.
- No process observed under the run outlives it. The challenger stops any it finds and fails the probe.
- The user's HEAD, index bytes, tracked bytes and untracked bytes are unchanged.

A probe whose prerequisite did not happen is `blocked`. A probe left out with `--only` is `not_run`. Both keep exit 3, so a partial challenge never reads as a pass.

## Plan

The plan declares project-specific faults. Keep it beside the control or outside the checkout, and review it like the break patch.

```json
{
  "feature": "briefing",
  "timeoutSeconds": 120,
  "occupiedPortEnv": "APP_PREFERRED_PORT",
  "syncEnv": "APP_CHALLENGE_SYNC_DIR",
  "variants": [
    {"name": "missing-browser", "env": {"BROWSER_PATH": null}, "expect": {"status": "incomplete", "missing": ["chromium"]}},
    {"name": "zero-cases", "env": {"APP_TEST_FILTER": "no-such-test"}, "expect": {"status": "incomplete"}},
    {"name": "source-mutation", "break": true, "mutate": {"path": "src/briefing.ts"}, "expect": {"status": "incomplete", "sourceChanged": true, "failed": ["briefing.return-summary"]}},
    {"name": "teardown-failure", "break": true, "env": {"APP_FAIL_TEARDOWN": "1"}, "expect": {"status": "incomplete", "failed": ["briefing.return-summary"]}}
  ]
}
```

- `env` applies to every run; a variant's `env` overrides it, and `null` unsets a variable.
- `occupiedPortEnv` hands the occupied port to a fixture that prefers a port. A conforming fixture binds a fresh port it owns and leaves the occupant alone.
- `syncEnv` names a directory for a handshake. The runner writes `ready` once its services answer and waits for `release`. Cancellation probes signal at `ready`. A `mutate` variant appends to its path, then writes `release`. Without `syncEnv`, cancellation waits for started processes and may report blocked when the run finishes first.
- A variant can apply the declared break, remove checkout paths, and set environment. `expect.failed` lists scenarios whose failed checks must survive in the report. `expect.missing` lists prerequisites that must be reported missing.

A browser availability check belongs in the control configuration as a prerequisite probe, such as `{"need": "chromium", "probe": {"argv": ["node", "tests/browser-probe.mjs"]}}`. The probe runs in the snapshot after preparation. A failing probe makes the run incomplete and its last output line names the repair. A file existing does not prove a browser launches.

## Read the result

The evidence directory holds `challenge.json`, the retained `plan.json`, and one folder per probe run. Each run folder keeps the raw stdout, stderr, the conformance verdict and a copy of the control's own evidence directory. `manifest.json` lists every retained file with its SHA-256. The challenger removes its worktrees and scratch, then checks the manifest again; `result.json` records that check. Copied artifacts must match the digests in their reports.

Report the observed outcome per probe. Inspect expected versus executed scenario ids and every failed check, including those kept inside an incomplete run. An incomplete or cancelled run proves no behavior. Its retained failures remain diagnostic observations for the checked bytes.

## Limits

The packaged acceptance fixture is synthetic. It runs a local HTTP server, a stand-in browser and real Node assertions through a generated control. It does not establish a private consumer's install, browser, deployed behavior or cold-session usability. Those need observations from that consumer and environment. Process ownership covers processes observed under the run; a process that escapes between process table samples is outside what the challenge can see. Append actual challenge run ids and precise scope to the project ledger, retain earlier failures, and keep a failed or blocked candidate unverified.
