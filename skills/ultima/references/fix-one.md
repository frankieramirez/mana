# Fix one candidate

One candidate, on the current branch, with the project's validation run after the edit. Resolve the authorized actions at Stage 6 before loading this reference. A local fix leaves a validated diff; staging and committing require authorization that covers this repository and target. Publication requires its own covered authorization. The walk below is printed as output before any edit; it is not a second question.

## The walk

Print each check with its answer. A failed check stops the fix: write the candidate as a ticket-shaped brief to `$RUN_DIR/tickets/<rank>-<slug>.md` using `references/agent-brief.md`, print the path, and say which check stopped it.

1. **Settled elsewhere?** Re-read the prior-decisions block and any doc the candidate or its instances cite. An accepted documented tradeoff stops the fix; the candidate should have been dismissed, so record it in `reconciled.json` too, then re-run merge pass 2 and render as documented in `references/finish-audit.md` so `merged.json` and `report.html` drop the candidate, and print the new report path. When `metadata.json` has an `artifact_url`, read the new report and publish it to that URL so the private copy matches.
2. **Eligible atomic fix?** Only action `fix` with confidence at least 75 and decision_status other than `revisit` qualifies. Security findings (including findings contributed by a security lens), plans, trace findings, decision-needed work, and effort L become local briefs with their migration and verification details. For S or M patterns, fix the entire verified pattern atomically. If it cannot fit a bounded validated change, write a plan; never fix only the hot files.
3. **New dependency or new shared piece?** A fix that adds a package, a new primitive, or a new token stops here. Adding to the design system is a decision, not a cleanup.
4. **What proves it?** Name the check that verifies the entire affected pattern and its callers, using the candidate verification and project validation. If the check covers only some required instances, write a plan instead of a partial fix.
5. **Tree clean, commit authorized?** Run `git status --porcelain` and record whether the user's instructions authorize a commit. A dirty tree or local-only permission means implement and validate, then report the diff without staging or committing. A clean tree alone does not authorize a commit.

## The edit

Re-read every instance before touching it; the lens read a snapshot and the tree may have moved. An instance that no longer exists is dropped from the list, not invented back.

Make the plainest edit that answers the candidate at each instance, in the file's existing conventions: the same import style, the same class ordering, the same quote style. Use the token, component, or attribute the candidate names, and nothing else. Do not refactor around the instance, do not fix a neighboring smell, and do not touch files outside the instance list.

After the edits, re-run the check that established the candidate (the grep, the lint rule, the test, or a manual read of each instance) and show it finds no remaining instance in the fixed scope. Then run the project's validation: the `Validation:` line in the `## Agent skills` block of `CLAUDE.md` or `AGENTS.md` when one exists, else the test suite, typecheck, and lint the project's conventions name. Target the touched area by default and broaden when the change spans packages.

A validation failure means revert the edit that caused it, re-run, and report the instance as not fixed with the failure quoted. Never leave the tree red.

## The commit

Tree was clean at check 5 and committing is authorized: stage only the files in the instance list and commit with the repo's convention. Use the project's commit scope for the affected area; the default subject is `refactor: <candidate title>`. Print the sha.

Tree was dirty or committing is outside the authorized actions: leave the index unchanged. Print the changed files and the validation result.

Stop after the authorized action. A push, PR, or another candidate requires instructions covering that action and target. Say which candidates remain and that the report still lists them. Continue wider work only when those instructions already cover it.

## Report

```
Fixed: <title> (<id>, rank <n>)
Instances: <fixed>/<total>, <skipped> left for a ticket
Validation: <command> passed | failed at <what>
Commit: <sha> | not committed (local-only permission or dirty tree)
Remaining: <n> strong candidates in <report path>
```
