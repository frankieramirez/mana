# Comment cleanup

## Review

Read `references/comment-reaper.md` from this skill's directory. Spawn one subagent with that file's full content as its instructions and append the exact session diff and scope from Stage 2a. Do not soften its rules. The reviewer may delete comments only; it must not commit or push.

## Audit

Inspect every deletion and flag before accepting it. Reject application-code edits and out-of-scope changes, preserving the session's implementation. Restore comments covered by the reference's keep list, including pending constraints and necessary suppressions. A proposed or unverified repair does not replace its explanation. Reject flags that misstate the code. Check for missed comments and suppressions within scope.

If the reviewer edits application code, escapes scope, or produces several invalid flags, undo only its changes and retry once with the failures named. A second failure stops the workflow before commit; report the reason.

## Repair

For each valid `RESHAPE`, make the smallest authorized repair within this ticket's changed code that makes the behavior clear. Never add a guard that hides the surprise instead of removing it. Retain explanations for repairs requiring changes outside that scope and report them open.

Apply the reference's evidence-before-deletion policy to constraints and suppressions. Implement cheap enforcement when already authorized and within scope. Verify that it rejects the prohibited behavior and accepts a legitimate alternative before removing the replaced warning; keep rationale the check does not establish. Retain unverified constraints, intentional negative tests, and necessary tool workarounds. If an open item prevents the ticket's acceptance criteria from holding, stop before commit.

## Validate

Read `references/comment-validation.md` now and apply it to the final edits. A failed, blocked, or unrun required check prevents verified completion. Continue to Stage 3 with the actual validation results, deletion counts, repairs, and open items; do not describe incomplete acceptance evidence as passing.
