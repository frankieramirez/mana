# Debug from runtime evidence

Use this procedure for an unexplained behavior defect. During triage, establish a reproducible brief without changing production behavior. During implementation, repair only within the authorized scope. A directly observed cause needs only its focused check and original-path recheck; do not invent extra hypotheses or require delegation.

## Establish the symptom

Record the observable failure, expected behavior and its source, reproduction command or user path, environment, and relevant input. Record the commit and relevant staged, unstaged, and untracked changes before investigating. Reuse a trustworthy failing test. Match the reported surface: a direct function test cannot establish that a browser-only failure is fixed.

## Distinguish causes

State a falsifiable cause and what would refute it. When several causes fit, choose the cheapest experiment that separates the leading alternatives. Inspect existing logs and state first; add temporary instrumentation only for a missing deciding value. Keep the command, result, and source identity. Check whether relevant source changed during the run. A missing prerequisite, stale source, or run with no relevant check is inconclusive.

Follow the violated contract to its owner. Normalize a valid boundary state where it enters the system, such as an optional input omitted under its schema. When an internal contract forbids the state, repair its producer or transaction and retain a useful assertion. A downstream empty/default return can conceal the violation. If the contract is uncertain, preserve the symptom and explain the uncertainty before changing semantics.

## Repair and verify

Apply the smallest repair supported by the evidence. If an experiment disproves a proposed cause, undo only this investigation's edit and temporary instrumentation. Preserve prior staged, unstaged, and untracked work. Inspect overlapping hunks; if they cannot be safely separated, explain the overlap instead of resetting the file.

Re-run the original failing path at the repaired source, plus the smallest meaningful regression check and a valid neighboring case. Run the project's required validation. A different passing check does not resolve an unverified original symptom. Report passed, failed, blocked, and unrun separately, naming the command and checked source. A source change during reproduction invalidates that association; rerun at a stable snapshot or retain an inconclusive result.

## Bound the investigation

For uncertainty, reassess after three discriminating experiments or 20 minutes, whichever comes first. Record eliminated causes and the next useful experiment. This checkpoint does not require new permission or end work already authorized. Avoid repeating an unchanged experiment. Parallelize independent causes only when their separation helps.

If setup is unavailable or exceeds the known budget, finish independent inspection and report the missing capability and exact next runnable experiment. Do not widen external access or consume an unapproved paid service. Ask only about a material missing choice or authorization. For intermittent failures, set a repetition/time budget and retain successes as well as failures with their inputs. One successful attempt is insufficient. If the symptom never reproduces, distinguish a diagnostic proposal from a verified repair.
