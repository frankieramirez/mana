# Comment cleanup

## Review

Read `references/comment-reaper.md` from this skill's directory. Spawn one subagent with that file's full content as its instructions and append the exact session diff and scope from Stage 2a. Do not soften its rules. The reviewer may delete comments only; it must not commit or push.

## Audit

Inspect every deletion and flag before accepting it. Reject application-code edits and out-of-scope changes, preserving the session's implementation. Restore comments covered by the keep list: license headers, public API contracts, foreign quirks, formatter directives, style-only suppressions, and constraint links. Reject flags that misstate the code. Check for missed comments and suppressions within scope.

If the reviewer edits application code, escapes scope, or produces several invalid flags, undo only its changes and retry once with the failures named. A second failure stops the workflow before commit; report the reason.

## Repair

For each valid `RESHAPE`, make the smallest repair within this ticket's changed code that makes the behavior clear. Never add a guard that hides the surprise instead of removing it. Leave repairs requiring changes outside that scope open and report them.

For a comment expressing a constraint, identify the cheapest enforcement in code, such as a type or test. Implement it when already authorized and within scope. Otherwise finish the authorized cleanup and report the proposed enforcement with the affected code. Name every deleted constraint that remains unenforced. If an open item prevents the ticket's acceptance criteria from holding, stop before commit.

Run the project's required validation and meaningful tests for any changed behavior after cleanup edits. Reuse prior validation only when no edits occurred. Then continue to Stage 3, carrying deletion counts, repairs, and open items into the final report.
