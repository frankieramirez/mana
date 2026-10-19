# Read project-control evidence

Load this when a workflow meets a project control: a `Control:` line in the `## Agent skills` block of `CLAUDE.md` or `AGENTS.md`, a saved run report, or a criterion that a control scenario could cover. It says what a control/0 report can and cannot establish, in the evidence words every workflow already uses: `passed`, `failed`, `blocked`, `unrun`, and `stale` as a relevance label.

## Interpret with the bundled reader

```bash
bash "<SKILL_DIR>/scripts/conform.sh" evidence --repo <repo> --report <report.json> --exit <actual-exit> --criteria <criteria.json> --scope <static|local>
```

The reader opens files and reads the repo's HEAD. It never runs the control, package scripts, or tests, so it is safe under a read-only request. `--criteria` maps each acceptance criterion to the scenario ids that cover it, such as `{"empty account shows zero": ["briefing.no-activity"]}`. Leave it out and every scenario in the report becomes its own criterion. Pass the exit code the control process actually returned whenever you have it. Pass `--digest` when a fresh report or `describe` gave you the checked-byte digest of the state under review.

Read its JSON, then report in plain words. Exit 0 means every criterion is supported, 1 means the report was rejected or a current check failed, and 3 means at least one criterion stays unverified.

## Find the control

| `control.state` | What to do |
|---|---|
| `present` | The pointer and its `Command:` line resolve. Use the control within the authority below |
| `absent` | Say no project control was discovered. Use the repo's existing guidance, tests and source inspection. Never report a control check that did not happen |
| `broken` | Name the exact gap from `control.detail`. Use supported existing checks when authorized. A missing mapping is not evidence that nothing needs checking |

## Authority

Every control command executes project code, including `list`, `describe` and `--plan`. Reading the pointer, records and saved reports does not.

- A static-only or read-only request runs no control command. Uncovered criteria stay `unrun` and name that limit.
- An instruction to run local checks covers `execution.rerun`. Local-only authority still excludes pushes, tracker writes, deployments and publication.
- A successful discovery or `--plan` is never an executed check.

## Report and identity

A report proves nothing until it passes validation. The reader rejects a report that is malformed, misses required fields, disagrees with its own process exit, or claims a pass with zero executed cases, a skipped expected case, a missing prerequisite, or a source change. A rejected report leaves every criterion `unrun`.

`identity.relevance` says whether a valid report describes the state under review:

| Relevance | Meaning |
|---|---|
| `current` | Same HEAD, and the checked bytes match: the reviewed digest is equal, or every file in the report's checked-file list hashes the same in the reviewed checkout |
| `stale` | A different HEAD, a different digest, or a checked file that changed or vanished. `identity.changed` names the files |
| `unknown` | The checkout changed during the run, or the report carries no checked-file list and no reviewed digest was given. The same HEAD alone does not establish identity |

Keep both identities visible when they differ. A stale or unknown report is historical evidence: it supports no current claim. Rerun the check when authorized or leave the claim unverified.

## Per-criterion outcome

| Raw report state | Capture status |
|---|---|
| Check `passed`, scenario executed, run `passed` or `failed` | `passed` |
| Check `failed` naming the scenario | `failed`, kept even when the run is `incomplete` or `cancelled` |
| Check `blocked` or `unavailable`, or not run because a prerequisite is missing | `blocked`, naming the prerequisite |
| Check `timed_out`, `cancelled`, `skipped` or `not_run`, or a case expected but never executed | `unrun`, with the check's reason |
| A passing check inside an `incomplete` or `cancelled` run | `unrun`: the run proves no behavior |
| No check covers the scenario | `unrun`: a coverage gap |

Each criterion keeps its own scenarios and its own claim. `supported` needs a valid, current report in which every covering scenario passed. `contradicted` needs a valid, current report with a failed covering scenario. Everything else is `unverified`. A partly covered feature or PR stays partly unverified; never round it up. A control pass covers only the checks it ran and does not replace the project's required validation.

Link the raw report and its `runId` from the evidence record, with the checked HEAD and digest beside the reviewed state.
