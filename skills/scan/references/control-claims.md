# Reconcile control claims

Load this at Stage 5 when the repo has a `Control:` line in its `## Agent skills` block, or the PR, ticket or request cites a control run. Read `references/control-evidence.md` first: it says what a control report can establish. This file says how a review turns that reading into requirement statuses without doing more than the review was asked to do.

## Stay inside the review's authority

Reading the pointer, saved reports and artifacts is static inspection. Running any control command, including `list`, `describe` and `--plan`, executes project code.

- Pass `--scope static` for a report-only, read-only or comment request, and under `mode:agent` unless the caller authorized running checks. Run no control command under that scope.
- Pass `--scope local` only when the request says to run checks. Then run only the commands the reader lists in `execution.rerun`, save each fresh report under `$RUN_DIR`, and read it the same way.
- Evidence never widens Stage 6. A supported claim does not authorize a fix, commit, push, comment or ticket change, and the review leaves product files, HEAD and the index as it found them.

## Read every cited report

1. Write `$RUN_DIR/control-criteria.json`, mapping each `R<n>` to the scenario ids the PR, ticket or feature map says cover it: `{"R1": ["briefing.return-summary"], "R4": []}`. A requirement nobody claimed a scenario for maps to `[]`, so it shows as uncovered.
2. Read each report the PR or ticket cites, and any report saved under the run, against the reviewed checkout:

   ```bash
   bash "<SKILL_DIR>/scripts/conform.sh" evidence --repo <repo> --report <report.json> --criteria "$RUN_DIR/control-criteria.json" --scope static > "$RUN_DIR/evidence-<runId>.json"
   ```

   Add `--exit` with the process exit when you have it, and `--digest` when you have the reviewed digest. With no report at all, run it once without `--report` so the pointer state is still recorded.
3. After the validator's requirement verdicts are merged (Stage 5b, step 3), write the requirements to `$RUN_DIR/requirements.json` in the metadata shape and reconcile them:

   ```bash
   bash "<SKILL_DIR>/scripts/review.sh" claims --requirements "$RUN_DIR/requirements.json" --evidence "$RUN_DIR/evidence-<runId>.json" --out "$RUN_DIR/requirements-reconciled.json"
   ```

   Pass one `--evidence` per report. Its `requirements` are the final ones for the report, `metadata.json` and the `mode:agent` JSON. Do not edit a status it set.

## What the helper decides

| Control claim | Requirement |
|---|---|
| `contradicted`: a current report failed a covering scenario | `unmet`, whatever reading, a screenshot or a rendered summary said |
| `supported`: a current report passed every covering scenario | `cannot_tell` becomes `met`; an `unmet` from a finding stays `unmet` |
| `unverified`: stale, unknown, rejected, blocked, unrun or uncovered | No change, except a `met` with no `file:line` becomes `cannot_tell` |

Each requirement keeps a `control` record with the claim, the capture status, the relevance, the reason, the `runId`, the raw report path, the scenario ids, the report's HEAD and the reviewed HEAD. A requirement no report covers has `control: null`.

## Report it

Put the claim beside each requirement line: `R1 met: control run run-2 passed briefing.return-summary at <head>`, `R2 unmet: control run run-2 failed briefing.empty-state`, `R3 cannot tell: control run run-1 is stale; src/activity.js changed after it ran`, `R4 cannot tell: no scenario covers it`. Link the raw report and its `runId`, and show the report's HEAD beside the reviewed HEAD when they differ.

A screenshot that rendered, a summary that printed, or a PR sentence saying the check passed is never a pass: a failed check stays failed. A supported claim covers only the scenarios that ran. It never makes the whole PR verified and never replaces the project's `Validation:` gate. Coverage names every claim left unverified and why.
