# Workflow effectiveness evaluation

Decision: [Specify a fair benchmark for workflow effectiveness and review effort](https://github.com/frankieramirez/mana/issues/82), under [Improve mana's reliability and measured effectiveness](https://github.com/frankieramirez/mana/issues/72).
Status: protocol settled on 2026-10-17; the focused condition adapter ships in mana 0.43.0. Sealed attempt records, blinded review packets and append-only judgments are implemented offline. The evidence-backed host registry, shared delegation limits, per-thread probes and process-family termination are implemented and tested offline ([host validation](../../evals/workflows/condition-execution.md#host-validation-and-delegated-arms)). Codex CLI 0.163.0 has live evidence for focused and delegated attempts. No host is validated for comparative delegated runs yet, because its thread cap was never challenged. Held-out fixtures remain pending; live runs and human review are unstarted.

## Decision and evidence

Run a diagnostic pilot of 12 source scenarios, three conditions and two repetitions on one validated host/model. The 72 planned parent invocations compare frozen Mana, a pinned reference suite and the same agent with neither suite. Measure completed work and reviewer effort. Keep natural-language discovery in its own study.

Extend `evals/workflows/`. Its existing adapter preserves failed attempts, source hashes, repository state, commands and separate regrades. The [delegated collector](../../evals/workflows/delegated-evaluation.md) observes child work. The [B/C record](../../evals/workflows/package-bc-results.json) covers two paired scenarios, with visible variant labels during manual grading and incomplete family usage. Those results support bounded observations. They establish no general performance ranking. The [semantic pilot](../../evals/semantic/findings.md) repeatedly missed the same confirmed scope error. Judge agreement and repeated verdicts cannot replace an outcome oracle.

This specification does not launch the pilot. The opt-in [frozen condition adapter](../../evals/workflows/condition-execution.md) installs separate Mana, reference and no-suite payloads for nine existing development cases, with identical frozen inputs and verified inventories. Its legacy path keeps the original Mana behavior. Passing `--skill-root` alone still cannot run the other conditions. Each allocated slot now gets a sealed attempt record, and completed attempts export to anonymized review packets with independent judgment and regrade records; see [sealed attempts and blinded review](../../evals/workflows/condition-execution.md#sealed-attempts-and-blinded-review). No reviewer cohort has used them. The held-out dataset, longer delegated jobs and validated live host remain separate tickets under [build 88](https://github.com/frankieramirez/mana/issues/88); the complete protocol is not yet executable.

## Conditions and source freeze

| Condition | Installed instructions | Invocation |
|---|---|---|
| `mana` | Skills at `9d1aa521974bc7c72bf9cdd676de18c09a036468` | Explicitly load the task's owning workflow |
| `reference` | Selected suite in `cursor/plugins` at `101b274dd991f694e1f7024be2157e5f3adf07de` | Explicitly load its corresponding workflow and required supporting files |
| `none` | No suite, persona, global memory or user configuration | Supply the same ordinary task and fixture documentation |

The current Mana pin is the audit baseline. A newer release is a separately named condition, never a silent replacement. Store the reference's resolved package root and entrypoint paths in the frozen controls. Resolve mappings before outcome collection. A task without an equivalent executable reference route fails preparation and needs a revised design before the entire matrix is frozen.

All conditions receive the same product requirements, requested actions, tool capabilities and task data. Only the explicit instruction-loading prefix and installed payload differ. A suite-specific artifact format is collected as produced; graders normalize it outside candidate context. Do not add a helpful workflow recipe to only one condition. Preserve required package support and report every adapter translation.

Start with Codex CLI 0.159.2, requested `gpt-6.1-sol`, reasoning `medium`, Linux. These are the delegated runner's recorded pins, subject to a fresh containment and event-contract check. An unavailable model or host blocks the group. Substitution creates a new controls version before any run. Keep requested and host-reported model identity separate; unresolved backend identity stays null.

## Task set

These are the fixed task families and requested outcomes for this pilot. Implement one new fixture per row. Existing public cases are development checks only. Their prompts, source variants and expected outputs cannot become confirmation data under a new filename.

| ID | Ordinary request and fixture contract | Outcome oracle held outside the workspace |
|---|---|---|
| `review-contracts` | Review a small authorization and listing diff against explicit caller and ticket contracts; report only. Include two independent defects sharing one line and a misleading cleanup suggestion. | Find both failure modes and the listing defect; preserve the valid caller behavior and product state. |
| `feedback-repair` | Handle a named feedback batch locally. One suggestion fixes arithmetic, one would remove a valid boundary guard, and one is a supported inexpensive correction. | Accept supported repairs, decline the guard removal with caller evidence, validate the repair and preserve unrelated files. |
| `review-no-change` | Review a correct refactor whose internal calls changed while externally observable behavior and requirements remain satisfied. | Report no actionable defect; distinguish optional preferences and preserve the tree. |
| `debug-partial-retry` | Repair an intermittent retry failure. Supply a deterministic schedule, a partial prior operation and a failing example. | Reproduce, preserve the legitimate retry boundary, repair the cause, and pass interrupted/repeated execution controls. |
| `debug-boundary` | Diagnose malformed external input reaching a pure internal operation. Include a plausible proposal to catch every internal exception. | Validate at the actual boundary, retain legitimate input, preserve programming-error propagation and demonstrate the failure. |
| `debug-false-premise` | Investigate a reported regression with a misleading causal claim and logs that permit a discriminating check. The reported behavior is correct under the documented contract. | Test the premise, cite the observation, make no speculative repair, and state any unresolved observation. |
| `verify-contract-test` | Judge tests around an internal refactor. A literal-value assertion protects a persisted contract read by a separate consumer; another assertion only spies on an internal call. | Preserve the contract test and repair or remove the implementation-coupled check; a contract-breaking mutation must fail. |
| `verify-stale-proof` | Assess a change using an earlier passing artifact, a later source edit and a renderer that can succeed after the check fails. | Reject stale attribution, preserve actual check status and distinguish rendering from product verification. |
| `verify-unavailable` | Check a claimed interaction when its required runtime is unavailable; source inspection and a synthetic illustration remain possible. | Report the missing runtime and unverified behavior without inventing a pass or installing an unrequested dependency. |
| `prose-exempt` | Rewrite prose beside a code/config sample. Preserve the sample; the prose omits a runtime number and causal explanation that can be guessed from it. | Preserve exempt bytes and every stated fact; add no inferred mechanism, number or reason. |
| `prose-scope` | Shorten a statement guaranteeing success only for valid records. One invalid case is named without claiming it is exhaustive. | Preserve the quantified scope and conditions while removing filler. |
| `prose-verbatim` | Return a requested quotation exactly and make no editorial changes. | Exact bytes, including intentional stylistic violations; no rewriting intervention. |

Before collecting results, an evaluator who is not editing the candidate instructions instantiates the fixtures and locks their hashes. Write complete requests, source snapshots, allowed effects, expected failure identities and valid alternative outcomes. Have a second reviewer check the contracts and the known-good/known-bad oracles. If the author of a later candidate reads a fixture or its labels while tuning, mark that source group `development` and replace it with an untouched group for confirmation. Until these steps happen, the rows are a manifest outline, not a claim of a held-out dataset.

Each manifest entry contains `id`, `source_group`, `job`, `split`, `fixture_sha256`, `request_path`, `request_sha256`, `allowed_effects`, `condition_entrypoints`, `timeout_seconds`, `delegation_allowed`, and `oracle_id`. `allowed_effects` names product paths, local commit permission and the artifact directory. These cases forbid external publication. `oracle_id` identifies evaluator-only material outside the agent's permitted mounts. Expected answers never enter the invocation prompt or final-response schema.

## Execution and resource bounds

Run one parent invocation at a time. For each scenario, run all six condition/repetition cells as a block. Seed Python's standard-library shuffle with `20261017` over the six cells, processing case IDs in sorted order; save the resulting schedule before execution. Preserve every allocated slot, including setup failures and timeouts. There are no automatic retries or replacement runs. A damaged group is reported incomplete; an explicitly recorded follow-up gets its own budget and identifiers.

| Job | Cases | Parent slots | Hard seconds per invocation | Maximum parent process time |
|---|---:|---:|---:|---:|
| Review and feedback | 3 | 18 | 900 | 16,200 seconds |
| Debugging | 3 | 18 | 600 | 10,800 seconds |
| Verification judgment | 3 | 18 | 300 | 5,400 seconds |
| Prose fidelity | 3 | 18 | 180 | 3,240 seconds |
| Total | 12 | 72 | Per job | 35,640 seconds, or 9 hours 54 minutes |

Allow the same delegation capability in every code-task condition. Cap active threads at four including the parent, with ten children total per invocation and no nested delegation. The current host supplies the active-thread cap; the total-child cap remains an instruction bound checked after collection. A breach fails execution acceptance and stops the group. Prose tasks have no children. The planned maximum is 540 children across 54 code-task parents. The per-parent process timeout includes all child work; confirm process-group termination in the adapter probe. These are invocation/time bounds, not a dollar budget.

Repeat the existing outside-read, protected-write, fixture-write and reachable-listener network probes before each invocation, including every child. Validate delegated history completeness, thread attribution, reviewer completion and final artifacts. Keep model-service access separate from command networking. Tool doubles must reject unsupported operations rather than silently supply plausible data. If a suite requires a missing capability, stop preparation instead of measuring a crippled workflow as equivalent.

Stop the remaining group after a containment failure, unexpected external write, corrupted frozen input, missing child history, budget breach or systematic tool-double mismatch. Preserve the triggering attempt. A task-level error inside a functioning harness remains a measured outcome and does not justify selective retries.

## Grading and reviewer effort

Keep execution status separate from task outcome. Use `setup_failed`, `agent_failed`, `timeout`, `collection_failed` and `completed` for execution. Completed outcomes are `passed`, `failed` or `needs_adjudication`. An incomplete observation cannot count as a pass. Report all 72 allocated slots in the denominator and show infrastructure failures separately from task failures.

| Dimension | Definition and evidence |
|---|---|
| Supported defect | A distinct failure identity supported by current source and a reproducible observation or a complete static contract trace; deduplicate equivalent wording. |
| Missed defect | A preregistered consequential failure absent from the final actionable result or incorrectly dismissed. Report new valid defects separately after adjudication. |
| Harmful edit | An edit that breaks a valid contract, removes a useful test or constraint without replacement, or introduces a regression. Verify with hidden controls and inspect the diff. |
| Scope fidelity | Product changes, index, commits and attempted side effects match the request. Failed prohibited attempts still count where observable. |
| Evidence honesty | Claims match source identity, observed execution, exit status and coverage. Static inference, illustration and runtime proof retain distinct labels. |
| Avoidable question | The answer was already supplied or a routine choice was delegated within scope. Missing product decisions and missing capability are recorded separately. |
| Repeated correction | The same previously supplied correction is required again within a run or after the fixed, preregistered clarification. Count correction events and affected failure identities. |
| Human effort | Active reviewer seconds, files/events inspected, clarification turns, required corrections and whether the result can be accepted unchanged. Unmeasured time remains null. |

Two reviewers grade independently from anonymized artifacts with condition names and instruction contents withheld where feasible. Preserve the original evidence in a restricted archive and record masking that could not hide the variant. Reviewers receive the source contract, diff, observed commands, check outcomes and child artifacts, alongside the final message. Narrating a check without running it earns no execution credit; omitting its narration does not erase observed behavior.

Record active time from opening the review packet to the first acceptance/repair decision, excluding breaks. Cap initial review at ten active minutes per packet; unresolved packets become censored observations and enter adjudication with separate timing. Review in randomized order, retain reviewer identity and order, and disclose familiarity or repeated-source effects. Do not infer human minutes saved from token counts, model grading time or a single agent's estimate. An unavailable human review cohort leaves effort metrics explicitly unmeasured.

The first pilot supplies complete task contracts and no interactive clarification or corrective hints during execution. Record an agent's requested question and the human corrections its output would require, without sending those corrections back to selected conditions. Repeated-correction counts use only corrections already supplied in the frozen task context and repeated within the run; other cases record that metric as not applicable. A study of interactive recovery requires its own fixed response policy and budget.

Resolve disagreements against the contract and raw evidence with a third adjudicator. Store both initial grades and reasons for the final grade. An LLM judge may flag candidate violations or disagreements; it cannot be the sole oracle for factual fidelity or useful tests. Characterize its false passes and false failures before considering a gate.

## Reporting contract

Retain the runner's existing `report` and `checks` response envelope when supported. Add evaluator-owned metadata beside it, rather than teaching candidates the rubric. Each attempt record includes:

```json
{
  "schema_version": 1,
  "study": "effectiveness-pilot-1",
  "case_id": "review-contracts",
  "source_group": "sealed-review-01",
  "condition": "mana",
  "repetition": 1,
  "schedule_slot": 1,
  "controls_sha256": "resolved before execution",
  "payload_hashes": {},
  "fixture_sha256": "resolved before execution",
  "runner_hashes": {},
  "requested_model": "gpt-6.1-sol",
  "actual_model": null,
  "execution_status": "unstarted",
  "task_outcome": null,
  "failures": [],
  "artifact_index": [],
  "elapsed_seconds": null,
  "tool_operations": null,
  "retry_attempts": 0,
  "usage": {"parent": null, "children": null, "family_total": null},
  "context": {"observed_full_read_bytes": null, "repeated_read_bytes": null},
  "judgments": [],
  "human_review": {"active_seconds": null, "censored": null},
  "regrades": []
}
```

Resolve every freeze field to a concrete digest before execution. Retain raw events, initial/final product state, installed payload inventory, source snapshots, tool-double logs and all judgments. Hash and archive them with the existing archive utilities. A grader correction creates a new judgment with its own source hash; original results remain available. The sealed attempt record keeps the template's fields and adds `runner_execution`, `counts_as_pass`, `artifact_index_sha256`, `archive`, `frozen_fixture_sha256`, `tool_inventory_sha256`, `payload_inventory_sha256`, `runner_context` and `stopped_schedule`. Its `judgments` and `regrades` stay empty because each judgment is its own write-once record that names the attempt hash. Child usage may be unavailable even with complete command history. Then `family_total` remains null. Observed instruction reads are lower bounds; entrypoint size and cumulative input tokens are different measurements.

Report outcomes by source group and job, plus paired condition differences. Repetitions, defects and rubric criteria within one source group are correlated observations. Show raw task counts and cluster uncertainty by source group when estimating an interval. Twelve groups cannot establish general superiority. Report model/host limitations next to the results and keep cost and quality on separate axes.

## Decision gates and expansion

Any observed critical scope violation, fabricated execution claim or destructive harmful edit disqualifies that condition from a recommendation until its cause is understood and fixed. A single passing run does not demonstrate prevention. Report ordinary quality failures even when another task succeeds.

For this pilot, prioritize a candidate for further study only when it wins on at least two distinct source groups, loses on none, and has no new critical failure. A win means a preregistered outcome or human correction improved; a shorter answer alone is insufficient. Mixed results or ties are inconclusive. These are triage thresholds, not statistical proof or automatic release permission.

Expand after the harness completes all comparisons without unresolved systematic defects and the pilot yields an actionable hypothesis. Freeze the proposed change, run 24 new source groups on a second supported model with the same three conditions and two repetitions (144 planned parents), and predeclare that study's controls. Refresh host containment first. A broad quality claim requires reproducible improvements across the untouched groups, with a paired cluster interval excluding zero and no increase in critical failures. A speed/cost claim additionally requires equivalent measured outcomes and complete relevant resource accounting. Leave the result inconclusive when those conditions do not hold.

## Implementation handoff

1. Extend the existing case loader with separate execution conditions and evaluator-only manifests; preserve the legacy dataset. Add reference and no-suite installation paths without hidden Mana prefixes.
2. Build and lock the 12 fixture groups, mapping ordinary tasks to each condition's supported entrypoints. Add positive/negative grader fixtures and ensure validators accept legitimate variations.
3. Extend existing containment and child collection for the new condition paths. Test timeout termination and missing-capability rejection without model calls before the compatibility probe.
4. Write frozen controls and schedule, obtain the human review cohort or mark that metric unavailable, then execute the explicitly budgeted group. Discovery and instruction ablations use their own controls and report tables.

Acceptance for this decision is the protocol and manifest outline above. Implementation, compatibility probes and the 72 live invocations remain downstream work. The complete offline repository validator checks this documentation change; it does not validate the future comparative runner or establish skill effectiveness.
