# Control contract, version control/0

A control skill lets any agent session find a feature, run the project, and report what actually happened. The project owns the CLI, the records, and the tests. This contract fixes only what every project must agree on so reports mean the same thing everywhere. It was drafted from a working implementation and stays at `control/0` until a second project passes it.

Load this file in the Conformance stage, and whenever proposing changes to a project's control CLI or records.

## Discovery

The `## Agent skills` block in `CLAUDE.md` or `AGENTS.md` carries one line:

```
Control: skills/<project>-control/SKILL.md
```

The path is relative to the repository root. The control skill it names holds these key lines, each on its own line, values optionally in backticks:

| Key | Required | Default | Meaning |
|---|---|---|---|
| `Command:` | yes | none | The CLI prefix, such as `pnpm verify` or `npm run --silent verify --` |
| `Prepare:` | no | none | A command that readies a fresh worktree, such as `pnpm install --frozen-lockfile --offline` |
| `Features:` | no | `verification/features` | Directory of feature records |
| `Scenarios:` | no | `verification/scenarios` | Directory of scenario records, one subdirectory per feature |
| `Bindings:` | no | `.` | Comma separated paths searched for test registrations |
| `Breaks:` | no | `verification/breaks` | Directory of break patches, one per scenario id |

## Verbs

Every verb accepts `--json` and then prints exactly one JSON document on stdout. Progress goes to stderr. A package runner's banner line before the document is tolerated.

| Verb | Purpose |
|---|---|
| `list [--search <text>]` | Every feature and scenario; with `--search`, ranked candidates for a vague report |
| `describe feature <id>` and `describe scenario <id>` | Reach paths, sources, steps, bindings, and the commands that run them |
| `feature <id>...` | Run everything that proves the named features |
| `changed [--base <ref>]` | Run what the changed files select, falling back to a wider run when the selection is unsure |
| `release` | Run everything |

Optional: `--plan` prints what would run and runs nothing. `stack up` and `stack down` start and stop the services an app needs.

## Exit codes

| Code | Meaning |
|---|---|
| 0 | Passed, or a discovery verb succeeded |
| 1 | A proven failure, or malformed records |
| 2 | Usage error or an unknown id |
| 3 | Incomplete: a blocked prerequisite, zero executed tests, a skipped expected case, a timeout, a crash, or a checkout that changed during the run |
| 130, 143 | Cancelled by SIGINT or SIGTERM |

Incomplete is never a pass. In the evidence vocabulary shared by build and pull request workflows, incomplete reads as blocked or unrun.

## Run report

A run verb with `--json` prints the report. The report states the exit code the process returns.

```json
{
  "contract": "control/0",
  "runId": "20260924-1a2b3c",
  "status": "passed",
  "exit": 0,
  "source": {
    "identity": { "head": "<commit or null>", "manifest": { "digest": "<sha256 of the checked bytes>" } },
    "sourceChanged": false
  },
  "prerequisites": [{ "need": "chromium", "status": "present", "detail": null }],
  "checks": [
    {
      "id": "e2e",
      "status": "passed",
      "reason": "executed 4 expected cases",
      "argv": ["pnpm", "test:e2e"],
      "expected": ["briefing.empty-state"],
      "executed": ["briefing.empty-state"]
    }
  ]
}
```

- `status` is `passed`, `failed`, `incomplete`, or `cancelled`, and `exit` must agree with it.
- A check's `status` is one of `passed`, `failed`, `unavailable`, `timed_out`, `cancelled`, `blocked`, `skipped`, or `not_run`.
- A prerequisite's `status` is `present`, `missing`, or `not_probed`.
- Extra fields are welcome. Artifacts, logs, timings, and environment details belong in the report too.

## Judge rules

The CLI decides the outcome, and the checker holds it to these rules:

- A passed run has at least one passed check and no check that failed, timed out, was cancelled, was blocked, or was unavailable.
- A passed check executed at least one test or case, and executed every case it expected.
- A missing prerequisite rules out a pass.
- A checkout that changed during the run rules out a pass.
- A failed run names at least one failed check.

## Records

Records are data: no commands, expressions, or callbacks. They never store verification results; a run's outcome lives only in its report.

A feature record at `<Features>/<id>.json`:

| Field | Required | Meaning |
|---|---|---|
| `id` | yes | Lowercase dotted id equal to the file name |
| `summary` | yes | What the feature does, in the user's words |
| `aliases` | yes | Words a vague report might use |
| `sourceRoots` | yes | Paths the feature owns. Empty is allowed only when the CLI derives sources itself |
| `knowledge` | yes | `proposed` (drafted from code), `confirmed` (a person agreed), or `unresolved` (open question) |
| `reach` | when no scenario has routes or steps | How a user gets there: entries with a `route`, `command`, or `shortcut`, plus `steps` |

A scenario record at `<Scenarios>/<feature>/<name>.json` has `id` equal to `<feature>.<name>` and a non-empty `steps` list of `{ "action", "expect" }`. Every feature has at least one scenario.

A test registers a scenario with a literal call whose first argument is the scenario id, such as `scenario('briefing.empty-state', 'e2e', async () => { ... })`. Any function name ending in `scenario` or `Scenario` counts. Every scenario needs one, and every registration needs a record.

## Break patches

`<Breaks>/<scenario-id>.patch` is a `git apply` patch that breaks the behavior the scenario proves. With the patch applied, a run of the scenario's feature must fail, and a failed check must name the scenario id. Reverting the patch must pass again. This is how a project shows its checks can fail for the reason they claim.

## Isolation

- Runs happen in a snapshot or a worktree, never by editing the user's checkout.
- Each run owns its ports, temporary directories, and processes, and cleans up only what it owns. Two runs from the same checkout at once must both succeed with distinct run ids.
- Secrets are named, never printed. Reports record variable names, not values.
