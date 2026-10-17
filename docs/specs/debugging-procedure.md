# Runtime debugging procedure

Date: 2026-10-17
Decision: [Bounded debugging](https://github.com/frankieramirez/mana/issues/81)
Status: implementation contract; the paired cases below are designed acceptance cases, not observed incidents or completed trials.

## Decision

Use one short, canonical reference owned by Sift and copied into Cast through `scripts/shared-assets.json`. Load it at Sift Stage 2c for a reported behavior defect and Cast Stage 2 when implementing a defect or investigating a failed behavior check. Do not load it for prose edits, ordinary feature work, or a failure already explained by a direct observation. This adds no public skill, mandatory agent team, or always-loaded principle catalog.

Sift uses the procedure to establish a reproducible brief without changing production behavior. Cast uses it within the authorized repair scope. Each skill ships its own complete reference. An unavailable runtime becomes an explicit evidence limit; it does not authorize deployment, external writes, or a wider repair.

## Procedure

1. Record the original observable symptom, expected behavior and its source, reproduction command or user path, environment and relevant input. Record the reviewed commit and relevant local changes. Match the reported surface: a direct function call cannot by itself verify a browser-only failure. Reuse a trustworthy existing failing test rather than demanding a second reproduction.
2. State a falsifiable cause and the observation that would refute it. When more than one cause fits, write the cheapest experiment that separates the leading alternatives. A directly observed cause needs no invented competing theory. Inspect existing logs and state first; add temporary instrumentation only when the deciding value is unavailable.
3. Run the experiment against the recorded source and surface. Keep the command, result and source identity. An incomplete setup, stale source, or a run that executed no relevant check is inconclusive. It supplies no evidence that the defect is fixed.
4. Follow the violated contract to its owner. Handle a valid boundary state where it enters the system. For a state forbidden by the internal contract, repair the producer or transaction and retain a useful assertion; a downstream empty/default return can conceal the defect. If the contract itself is uncertain, preserve the symptom and record the uncertainty before changing semantics.
5. Apply the smallest supported repair. When an experiment disproves the proposed cause, undo only this investigation's edit and temporary instrumentation. Preserve staged, unstaged and untracked work that predates the investigation. If changes overlap and cannot be separated safely, inspect the diff and leave the overlap explained rather than resetting the file.
6. Re-run the original failing path at the repaired source. Also run the smallest meaningful regression check and a valid neighboring case. Run required repository validation. Record failed, passed, blocked or unrun separately. A different check passing does not resolve an original symptom that remains unverified.

## Investigation budget

Use a short path for a directly observed, cheap defect: one focused experiment and the original-path recheck. Do not require delegation, a hypothesis table or a new test that merely restates implementation.

For uncertain defects, default to a checkpoint after three discriminating experiments or 20 minutes of investigation, whichever arrives first. This is a reassessment point, not an automatic stop or a new permission requirement. Record eliminated causes and remaining uncertainty; continue a useful next experiment within the user's existing scope and cost allowance. Avoid repeating an unchanged experiment. Parallelize independent causes only when the separation saves time.

When prerequisites are unavailable or setup exceeds the known task budget, finish independent inspection and report the exact missing capability and the next runnable experiment. Do not silently consume a paid service or broaden external access. Ask only when a material choice or authorization is actually missing. A long investigation already authorized by the user can continue across checkpoints with concise progress updates.

For intermittent failures, retain both successes and failures, inputs and attempted repetitions. Set a repetition/time budget before running. A successful attempt alone does not establish a fix. If the symptom never reproduces, report that outcome and a candidate diagnostic change separately from a verified repair.

## Paired acceptance cases

| Case | Distinguishing evidence | Expected action and acceptance |
|---|---|---|
| A CSV import omits an optional display name | Schema and an accepted input fixture allow omission | Normalize at the import boundary. Missing name renders a documented fallback; supplied names remain intact. The original import path passes. |
| A settled payment has no ledger entry | Settlement transaction promises atomic ledger creation; fault injection reproduces a partial write | Repair transaction ordering/atomicity at the producer. Do not add a rendering guard that hides the missing entry. The fault case leaves neither a settled payment nor a partial ledger; a valid settlement is unchanged. |
| A dashboard count appears one hour out of date | First hypothesis is timezone conversion. Raw timestamp and a cache-bypass experiment show the correct UTC value with stale cached content | Remove only the speculative timezone edit. Repair the invalidation trigger, rerun the original browser path and a neighboring cache-hit case. Preserve an unrelated user's staged style edit. |
| A browser symptom cannot be exercised because Chromium is absent | The command exits before any scenario executes | Record blocked, including missing prerequisite and exact retry command. Unit tests passing cannot make the browser claim pass. |
| A source file changes while a reproduction is running | Before/after source identities differ | Invalidate the association with the reviewed source; rerun at a stable snapshot or retain an inconclusive result. |

The cases deliberately distinguish legitimate handling from a concealed invariant violation. Their purpose is to catch an overbroad ban on guards as well as unsupported defensive edits.

## Delivery and evaluation

The first delivery adds the reference, its two stage-loading instructions and the sync-manifest entry. Keep the entry text to the trigger and load instruction; put the decision procedure in the reference. Required package validation must confirm both standalone payloads are complete and synchronized.

Add held-out workflow fixtures for the paired boundary/producer cases, the disproved first repair, and missing prerequisites. Grade final behavior, source/diff preservation and observed command evidence. Do not accept a final answer that merely recites the procedure. Compare the narrow reference with the current payload using the [effectiveness protocol](effectiveness-evaluation.md) and [instruction-ablation plan](instruction-ablations.md); the contracts define the keep/revert/inconclusive gate. No superiority claim follows from this design review.
