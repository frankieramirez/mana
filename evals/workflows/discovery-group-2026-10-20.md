# Discovery group: all 24 allocated parents invoked

The follow-up group for [issue #101](https://github.com/frankieramirez/mana/issues/101) invoked 24 of 24 allocated parents on 2026-10-20. All allocations ran without a group stop.

Source: `2b3d3108a30ab252c204f28989173e5d17192bff`; freshly fetched main: `2b3d3108a30ab252c204f28989173e5d17192bff`. Host: `codex-cli 0.163.0`; requested model: `gpt-6.1-sol`, reasoning `medium`. Resolved model identity remains unverified.

The fixed schedule contains twelve cases twice, with one serial parent, 120 seconds per parent, zero children and no retries. No expanded or second-host study ran. The runner manifest is unchanged. The user authorization is recorded separately in [discovery-group-2026-10-20-operator-context.json](discovery-group-2026-10-20-operator-context.json).

## Original classifications

Activation: `{"correct": 7, "unnecessary": 17}`. Routing: `{"correct": 15, "wrong": 9}`. Execution: `{"needs_adjudication": 8, "not_exercised": 13, "scope_violation": 1, "timeout": 2}`. Child activity: `{"attempted": 10, "none": 14}`. Process outcomes: `{"completed": 21, "timeout": 3}`.

| Slot | Case | Repetition | First route | Activation | Routing | Execution | Process | Children |
|---|---|---|---|---|---|---|---|---|
| 0 | vague-bug | 1 | skill:dispel | unnecessary | wrong | not_exercised | completed | none |
| 1 | scan-positive | 2 | skill:dispel | unnecessary | wrong | not_exercised | completed | attempted |
| 2 | dispel-negative | 1 | ordinary | correct | correct | not_exercised | completed | none |
| 3 | ordinary-explicit-only | 1 | skill:dispel | unnecessary | wrong | not_exercised | completed | none |
| 4 | scan-positive | 1 | skill:dispel | unnecessary | wrong | timeout | timeout | attempted |
| 5 | ultima-positive | 2 | skill:ultima | unnecessary | correct | needs_adjudication | completed | attempted |
| 6 | ultima-positive | 1 | skill:ultima | unnecessary | correct | needs_adjudication | completed | attempted |
| 7 | ordinary-explicit-only | 2 | ordinary | correct | correct | not_exercised | completed | none |
| 8 | attune-positive | 2 | skill:attune | correct | correct | not_exercised | completed | none |
| 9 | missing-sibling | 2 | skill:dispel | unnecessary | wrong | not_exercised | completed | none |
| 10 | dispel-positive | 1 | skill:dispel | correct | correct | not_exercised | completed | none |
| 11 | vague-bug | 2 | skill:dispel | unnecessary | wrong | not_exercised | completed | none |
| 12 | dispel-positive | 2 | skill:dispel | correct | correct | not_exercised | completed | none |
| 13 | changed-target | 1 | skill:dispel | unnecessary | wrong | needs_adjudication | completed | attempted |
| 14 | mend-positive | 2 | skill:mend | unnecessary | correct | needs_adjudication | completed | attempted |
| 15 | missing-sibling | 1 | skill:dispel | unnecessary | wrong | needs_adjudication | completed | none |
| 16 | review-or-audit | 2 | skill:scan | unnecessary | correct | timeout | timeout | attempted |
| 17 | review-or-audit | 1 | skill:scan | unnecessary | correct | scope_violation | timeout | attempted |
| 18 | remedy-positive | 2 | skill:remedy | unnecessary | correct | not_exercised | completed | none |
| 19 | changed-target | 2 | skill:dispel | unnecessary | wrong | not_exercised | completed | attempted |
| 20 | dispel-negative | 2 | ordinary | correct | correct | not_exercised | completed | none |
| 21 | remedy-positive | 1 | skill:remedy | unnecessary | correct | needs_adjudication | completed | none |
| 22 | attune-positive | 1 | skill:attune | unnecessary | correct | needs_adjudication | completed | none |
| 23 | mend-positive | 1 | skill:mend | correct | correct | needs_adjudication | completed | attempted |

## Observed patterns

All 9 wrong first routes began with `dispel`. All 17 slots with unnecessary activation loaded `dispel`. Several subsequently loaded the task's accepted skill. This repeats a prose-first selection pattern, while leaving the usefulness of that prose preparation and the quality of the task work unmeasured. A follow-up would need to separate trigger matching from deliberate report preparation before changing any description.

The only observed explicit-only entrypoint loads were `portal` in the two cases that directly named it. No explicit-only entrypoint load was observed from ordinary-language cases. The two missing-sibling cases separately record `skill:cast` as unavailable.

Process timeouts occurred at slots `[4, 16, 17]`. Commands needing adjudication occur at slots `[4, 5, 6, 13, 14, 15, 16, 17, 21, 22, 23]`. These original events and judgments remain available without replacement calls.

## Interpretation and evidence

These are selection observations under the frozen route sets. An additional entrypoint outside the accepted set counts as unnecessary even if used for final prose. The first loaded entrypoint determines routing. Intentionally explicit-only skills are not penalized for failing to activate. `not_exercised` means the selection-only grader makes no workflow completion claim. Process timeouts are counted separately because the original classifier can report a scope violation as execution even when that same process timed out.

Slot 17's original `scope_violation` needs adjudication. Its flagged compound command wrote proof artifacts under the permitted `artifacts/` directory, then returned 1 from the proof. The failed-command write-pattern detector does not resolve write destinations. This is not evidence of a forbidden product write. The original grade is preserved, and its process timeout is reported separately. See [discovery-group-2026-10-20-operator-notes.json](discovery-group-2026-10-20-operator-notes.json) for the evidence and operator interpretation.

Failed spawns are retained as attempted child activity. Created children stop the group. The host capability record reports that child tools are not withheld. Per-slot events and stderr are the evidence for actual child activity.

Capability limits, ambiguous commands, forbidden attempts, containment probes and process outcomes are preserved separately in [discovery-group-2026-10-20-results.json](discovery-group-2026-10-20-results.json) and each slot's unchanged `result.json`. Every started slot retains its raw `events.jsonl`, `stderr.txt`, request, response where produced, fixture and artifacts. Frozen evaluator and catalog bytes are in `frozen/`.

No independent human adjudication has been performed. Task quality and human reviewer effort are unmeasured. Full repo validation ran concurrently with early slots and encountered failures; resource contention was not measured. See `validation.log` and [discovery-group-2026-10-20-validation.json](discovery-group-2026-10-20-validation.json) for validation outcomes. These results do not establish effectiveness outside this bounded schedule.

## Integrity checks

- `all_24_allocations_retained`: `True`
- `all_allocations_terminal`: `True`
- `invocation_count_matches`: `True`
- `all_result_hashes_match`: `True`
- `all_observed_products_unchanged`: `True`
- `all_observed_process_families_terminated`: `True`
- `source_hashes_match`: `True`
- `frozen_source_hashes_match`: `True`
- `catalog_hashes_match`: `True`
- `host_binary_hash_matches`: `True`

## Validation

The 46-case route/catalog check passed, and all seven offline group tests passed before the live group. Full repo validation initially failed four of 81 fixture jobs: a Python shim error, two killed test processes and the Leyline rename assertion. A subsequent run after the live group, with system Python first on PATH and four workers, failed only `RefreshTests.test_directory_rename_follows_source_roots_and_the_break_patch`. It expected `break-renamed/proposed` and received `break-stale/needs_adjudication`. The other 80 fixture jobs passed. This same assertion is documented in the historical pilot report, and no tracked source files changed in this run. See [discovery-group-2026-10-20-validation.json](discovery-group-2026-10-20-validation.json) and both retained logs for the separate outcomes.

Validation against the publication changes has its own [record](discovery-group-2026-10-20-publication-validation.json) and compressed [log](evidence/discovery-group-2026-10-20-publication-validation.txt.gz). It does not replace either original validation attempt or any live observation.

The original [manifest](discovery-group-2026-10-20-manifest.json), [allocations](discovery-group-2026-10-20-allocation.json) and [completion record](discovery-group-2026-10-20-completion.json) remain unchanged. The [archive metadata](discovery-group-2026-10-20-evidence.json) identifies the compressed [raw evidence](evidence/discovery-group-2026-10-20.json.gz) by SHA-256. The portable archive retains unchanged slot results, events, stderr, responses where produced, synthetic source and artifacts, frozen evaluator/catalog bytes, operator scripts and original validation logs. It excludes Git internals, synthetic host homes and bytecode caches; exact baseline and final product-state identities remain in JSON. The archived original local index covers a broader set of files than the portable archive; the archive's own per-file hashes cover every included byte. Publication added no parent invocation. This group is separate from the [interrupted 0.44.12 pilot](discovery-pilot-2026-10-20.md), whose five attempts and nineteen unrun allocations are unchanged.

## Verify the retained evidence

```bash
python3 -B evals/workflows/archive_delegated.py evals/workflows/evidence/discovery-group-2026-10-20.json.gz
```
