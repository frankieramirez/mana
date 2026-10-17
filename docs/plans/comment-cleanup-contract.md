# Comment cleanup contract

Decision: [Define when comment cleanup may replace or remove a constraint](https://github.com/frankieramirez/mana/issues/77). Delivery: [Validate standalone repairs before reporting cleanup complete](https://github.com/frankieramirez/mana/issues/74).

Cleanup removes information only when current evidence makes it redundant or obsolete. An unverified replacement does not justify deleting a constraint. A suppression can affect compilation and tests, so removing one requires the same care as changing application behavior.

## Decision table

| Kind | Retain | Replace | Remove |
|------|--------|---------|--------|
| Redundant narration | When reading relevant code or callers leaves uncertainty about useful meaning. | A clearer symbol may remove the need for explanation after verification. | When the same useful meaning is already apparent and no constraint is lost. |
| Internal invariant | While enforcement is absent, unverified, outside scope, or not worth its cost. | An authorized type, assertion, test, or lint rule that demonstrably rejects the prohibited behavior and accepts a legitimate alternative. | After the replacement works, or current code/contract proves the old constraint obsolete. |
| Intent or external rationale | When it explains a choice that executable behavior cannot establish. Include foreign quirks and public contracts. | Improve the explanation or link its source when doing so is in scope. | Only when evidence establishes that the rationale no longer applies or is already recorded adequately at the same decision point. |
| Correctness/type suppression | Intentional negative tests, verified tool limitations, and unresolved repairs. Unknown rule semantics remain open. | Repair the underlying defect within scope and run the relevant check. | Only after the repair passes and the directive no longer serves a valid purpose. |
| License, formatter directive, style suppression | Existing keep-list rules continue to apply. | Only as authorized by the task and its relevant contract. | Cleanup alone supplies no new authority to remove these. |

For a replacement, record the constraint, its enforcing mechanism, the rejected example, the accepted alternative, and actual check results. A check demonstrating behavior does not establish the reason an external system requires it. Keep that reason when useful. If no cheap encoding is available, concise prose remains appropriate.

## Paired evaluation cases

These are development cases for the instruction comparison in [Choose instruction changes through failure cases, counterexamples, and ablation](https://github.com/frankieramirez/mana/issues/84). They describe expected outcomes, not observed agent results. Keep each pair in the same evaluation split.

| Pair | Failure case | Legitimate alternative | Required outcome |
|------|--------------|------------------------|------------------|
| Order constraint | Delete `publish only after transaction commit` while leaving publication before commit possible. | A transaction callback already guarantees the order, and a test rejects early publication while accepting the successful path. | First retains the explanation and reports missing enforcement. Second may delete the replaced warning after observing both checks. |
| Negative type test | Remove `@ts-expect-error` from an intentionally invalid API call and break the type-test suite. | A suppression hides an actual wrong argument in production code; the repaired call type-checks without it. | Keep the intentional negative test. Remove the production suppression only after the repair passes. |
| External quirk | Delete a comment explaining a vendor's retry window because an internal delay test passes. | Vendor documentation and current supported versions show the old workaround is obsolete. | Keep the rationale in the first case. Cite the obsolete contract evidence before removing the second. |
| Uncertain meaning | Delete an unexplained ordering warning because no linked issue or cheap test exists. | Remove `increment count` directly above `count += 1`, with no hidden semantics in surrounding code. | Retain and report uncertainty in the first case. Delete redundant narration in the second. |
| Scope | Remove a warning while its proposed type fix requires a package outside the authorized files. | An authorized in-scope type change rejects the invalid input and preserves a valid caller. | Retain the first warning and report the open repair. Verify the second before removing its replaced warning. |
| Repair validation | A cleanup rename leaves a caller referring to the old symbol; required tests fail. | Rename both references inside scope; the same focused test and required validation pass. | Report failure or repair and rerun the first. Report actual successful commands for the second. |
| Prerequisite | Required validation cannot run because a runtime is unavailable. | Earlier successful validation checked the identical source and environment, and cleanup makes no edits. | Report blocked in the first. Reuse and identify the earlier evidence in the second; absent or invalidated evidence stays unrun. |

## Ownership and validation

`skills/banish/references/comment-reaper.md` owns the retention policy and is copied to Cast and the generated agent. `skills/banish/references/comment-validation.md` owns the validation contract and is copied to Cast. The shared-asset manifest and standalone package inventory enforce their availability and equality. Banish loads validation at Step 5; Cast loads it in its comment-cleanup validation stage.

The report includes actual commands and outcomes, retained/open constraints, and any reused evidence. A failed, blocked, or unrun required check cannot establish verified completion. Required validation still applies to comment-only edits; new behavioral tests are justified by changed behavior, not by deletion counts.

The original gaps were established by source inspection: standalone Banish went from repairs to reporting, and both cleanup flows allowed deletion before a proposed constraint replacement was verified. No live failure rate or improvement rate is inferred from that inspection. Package checks establish distributable references and synchronized policy. Agent compliance requires observed workflow runs with repository and command evidence.

`evals/workflows/cleanup_fixtures.py` provides four focused validation scenarios and `test_cleanup.py` checks their graders against real fixture command results: a broken rename, a successful repair, a missing runtime, and no-edit evidence reuse. These tests also reject masked failures and out-of-scope index changes. They use synthetic agent records and establish fixture/grader behavior only. Live agent obedience and the paired retention cases remain unmeasured.
