# Run project-control checks for a build

Load this in Stage 1 when the `## Agent skills` block of `CLAUDE.md` or `AGENTS.md` has a `Control:` line, and again in Stage 3. It says which control commands Cast runs, when it runs them, and what each acceptance criterion may claim from them. `references/control-evidence.md` says how to read one report; this file says when to make one and how to combine several.

## Stage 1: map criteria before the first edit

Reading the pointer, the control skill and its records is static. Run no control command yet.

1. Open the control skill the pointer names. Note its `Command:` prefix and its `Features:` and `Scenarios:` directories (`verification/features` and `verification/scenarios` when absent).
2. For each acceptance criterion, find the scenario records whose steps prove it. Match on the behavior. A feature's `sourceRoots` lists what it owns, which is often less than what it depends on.
3. Write the map as JSON outside the product files, such as `{"refunds count in the summary": ["briefing.return-summary"], "changelog notes the fix": []}`. A criterion no scenario proves maps to `[]`, and the spec check's ordinary rule covers it.

Write the map before editing any file. A map drawn after the change bends to fit it.

## Stage 3: run after the final relevant edit

A cast request authorizes local control runs, because Cast already runs the project's checks. A request limited to static or read-only work, or one that forbids running the app, does not. Local authority never covers a push, tracker write, deployment or publication. Without authority, run nothing, leave every mapped criterion `unrun`, and name the limit.

1. Resolve the base with `git merge-base HEAD origin/<default>`.
2. Once the last edit to a file a check reads has landed, run the selection and keep its output and exit code:

   ```bash
   <Command> changed --base <base> --json > <dir>/changed.json; echo "exit $?"
   ```

   `--plan`, `list` and `describe` show what would run. None of them is an executed check.
3. Read it with `bash "<SKILL_DIR>/scripts/conform.sh" evidence --repo . --report <dir>/changed.json --exit <exit> --criteria <map> --scope local`.
4. Inspect the selection. A mapped criterion left `unrun` because no check covered its scenario means the selection missed it. Widen: run `<Command> feature <id>... --json` for the features in the reader's `execution.rerun`, or `<Command> release --json` when the gap spans features, and read each new report the same way. A change to shared code, startup or fixtures that another feature depends on calls for that feature's run even when `changed` passed.
5. Another edit to a checked file makes every earlier report stale. Run the selection and the widened runs again after the new final edit.

The `Validation:` line still runs after the final edit. A control pass covers only the checks it ran. It never stands in for the required validation, and a validation pass never stands in for a scenario.

## Combine the readings

Read every report against the same map. For each criterion:

- `contradicted` when any current report fails a covering scenario. Fix it before the commit, or stop without one.
- `supported` when a current report passed every covering scenario.
- `unverified` otherwise: the selection missed it, a check was blocked or unrun, or the only report that covered it is stale or unknown. Name the reason.

A criterion mapped to a scenario reaches `supported` only through an executed, current report. Reading the source does not raise it. A criterion mapped to `[]` keeps the spec check's rule: met by source inspection or by an executed test, and the row says which.

Commit exactly the bytes the runs checked. The commit is not an edit, so the readings carry to it. Keep the run's HEAD and digest beside the commit so a reader can match them.

## Record each criterion

Each criterion gets one row in the report's criteria table: the evidence kind (`executed` or `source-inspected`), the command with its scenario ids and `runId` or the file read, the checked state (the run's HEAD and digest, or the working tree read), the status, and the claim. Keep the saved reports. The ticket closes on merge only when every row is `supported`. Otherwise the PR body ends with the reference line and names the unverified rows.
