---
name: {{PROJECT}}-control
description: "Find the return briefing, inspect its scenarios, and run this project's isolated verification with source-bound reports. Use for welcome back, empty briefing, workers stopped, or checking the return summary."
---

# Project control

<!-- BEGIN GENERATED CONTROL DISCOVERY -->
Command: npm run --silent verify --
Features: verification/features
Scenarios: verification/scenarios
Bindings: {{BINDINGS}}
Breaks: verification/breaks
<!-- END GENERATED CONTROL DISCOVERY -->

The project owns this control, its records and its tests. The installation ledger is at `docs/agents/readiness.md`. Generated files become hand-maintained project code after installation. Inspect the ledger before proposing an update; preserve edits and existing intent.

## Find the behavior

Read the feature and scenario records before running code. `list --search "came back" --json` finds candidates; `describe feature briefing --json` gives their reach paths and checks. These commands execute project code and require authority covering local execution. The mapped route and test scopes come from this project's records. A discovery result or `--plan` is not an executed check.

## Execute the mapped checks

Use `feature briefing --json` to run the declared assertions. `changed --base <ref> --json` conservatively runs the complete mapped feature. `release --json` adds the explicitly configured release obligations; absent release configuration is incomplete. A feature pass covers its expected scenarios only.

Each run copies source into a disposable directory, prepares that copy when configured, runs the existing test command, and retains a `control/0` report and evidence outside the checkout. The command reports the evidence location. Project code, dependencies, credentials and the environment remain subject to the active execution authority. Preparation may need network access if the configured package command does. Missing prerequisites return incomplete; use the named repair and rerun when authorized.

Read the actual exit code, source identity, `sourceChanged`, prerequisites, and every check's expected and executed cases. Zero executed cases, skipped expectations, changed source, a timeout or failed teardown cannot pass. Keep individual failed checks even when the run is incomplete. Retained reports are observations for their checked bytes and inputs; later edits can make them stale.

## Report what ran

A report of wrong behavior asks for a diagnosis. Leave the checkout unchanged unless the request asks for a change, and describe the fix you would make instead. Stay inside the checkout and the control's evidence; the wider filesystem is no evidence for this project.

Reproduce through the control only. Debug edits to tests, or a script that feeds fixture data into app code, are a reproduction of your own, and their output is no check. When the control cannot show something, say so and leave it open.

Name the feature id and every route in its `reach` records. Cite each executed run by its full `runId`, exit code, `source.identity.head` and manifest digest, and each failed check by id. Anything a run or the source did not show you, including why a change was made, is an inference; label it as one.

Give each check's coverage in its scenario record's own words. A scenario that asserts the API alone says nothing about the page, so an empty page can be correct while that scenario passes.

An incomplete run (exit 3) proves nothing about the reported behavior. Report verification as blocked, quote the missing prerequisite and its repair exactly as the report gives them, and diagnose no defect from the checks that did run. Install a prerequisite only when the request authorizes it; then say you did and rerun the control before you claim anything.

## Evidence limits

Installation creates a candidate, with proposed feature intent. It does not establish browser coverage, hosted deployment parity, current consumer readiness, or a performance improvement. The runner's actual assertions and artifacts determine its scope. Record challenge results with their run ids in the installation ledger after execution, and keep failed observations intact.

Only the marked discovery block is a candidate for generated updates. Everything outside it belongs to the project. Confirmed intent needs a person-approved decision; passing assertions cannot confirm it.
