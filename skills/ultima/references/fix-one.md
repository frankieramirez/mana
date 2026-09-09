# Fix one candidate

One candidate, on the current branch, with the project's validation run before the commit. No push, no PR, no branch switch. The walk below is printed as output before any edit; it is not a second question.

## The walk

Print each check with its answer. A failed check stops the fix: write the candidate as a ticket-shaped brief to `$RUN_DIR/tickets/<rank>-<slug>.md` using `references/agent-brief.md`, print the path, and say which check stopped it.

1. **Settled elsewhere?** Re-read the prior-decisions block and any doc the candidate or its instances cite. A doc that settles the pattern the other way stops the fix; the candidate should have been dismissed, so record it in `reconciled.json` too, then re-run merge pass 2 and render as documented in `references/finish-audit.md` so `merged.json` and `report.html` drop the candidate, and print the new report path.
2. **Whole pattern or hot instances?** Effort S: every instance. Effort M: instances in files the profile lists as hot spots, with the rest listed for a ticket. Effort L: stop; this is a ticket.
3. **New dependency or new shared piece?** A fix that adds a package, a new primitive, or a new token stops here. Adding to the design system is a decision, not a cleanup.
4. **What proves it?** Name the check that exercises the touched components: the Validation command, a typecheck, a story, a visual snapshot, a unit test. When nothing in the repo exercises them, say so, and keep the change to the instances a check does cover.
5. **Tree clean?** Run `git status --porcelain`. A dirty tree means implement and validate, then report the diff and stop without committing, so the user can commit it with their own work.

## The edit

Re-read every instance before touching it; the lens read a snapshot and the tree may have moved. An instance that no longer exists is dropped from the list, not invented back.

Make the plainest edit that answers the candidate at each instance, in the file's existing conventions: the same import style, the same class ordering, the same quote style. Use the token, component, or attribute the candidate names, and nothing else. Do not refactor around the instance, do not fix a neighboring smell, and do not touch files outside the instance list.

After the edits, re-run the check that established the candidate (the grep, the lint rule, the test, or a manual read of each instance) and show it finds no remaining instance in the fixed scope. Then run the project's validation: the `Validation:` line in the `## Agent skills` block of `CLAUDE.md` or `AGENTS.md` when one exists, else the test suite, typecheck, and lint the project's conventions name. Target the touched area by default and broaden when the change spans packages.

A validation failure means revert the edit that caused it, re-run, and report the instance as not fixed with the failure quoted. Never leave the tree red.

## The commit

Tree was clean at check 5: stage only the files in the instance list and commit with the repo's convention. The default subject is `refactor(ui): <candidate title>`. Print the sha.

Tree was dirty: no commit. Print the changed files and the validation result.

Stop there. Do not push, do not open a PR, and do not start the next candidate; say which candidates remain and that the report still lists them.

## Report

```
Fixed: <title> (rank <n>)
Instances: <fixed>/<total>, <skipped> left for a ticket
Validation: <command> passed | failed at <what>
Commit: <sha> | not committed (dirty tree)
Remaining: <n> strong candidates in <report path>
```
