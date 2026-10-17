# Validate comment cleanup

Run the project's required validation after cleanup edits. For application-code repairs or changed compiler/linter directives, also run meaningful checks for the affected behavior. Use existing focused tests when they cover the change. Add a regression test only when it establishes behavior that matters; ordinary comment deletion does not justify invented behavior tests.

Reuse earlier successful validation only when the checked source and relevant environment are still current, no subsequent edit invalidates the result, and no unresolved concern calls for another check. Verify these conditions and name the original command and result. A no-edit cleanup can reuse valid evidence; absence of evidence remains unrun.

Preserve each command's actual exit status and output. Do not mask a failure with a successful formatter, pipeline, or later command. Distinguish a failed check from a blocked prerequisite and a check never run. A zero exit establishes only what the command actually checked. Missing dependencies, omitted assertions, or stale source cannot establish success.

If validation exposes a defect introduced by cleanup, repair or undo only that cleanup edit, preserve unrelated user work, and rerun the affected checks. Keep an unresolved constraint's comment or suppression. When a prerequisite cannot be supplied within scope, report the blocked check and remaining concern without claiming verified completion.

The final report names the executed commands, their outcomes, and any reused evidence. Required checks that failed, were blocked, or remain unrun stay visible as incomplete validation. Do not ask for new permission to run checks already covered by the user's request.
