# Discovery group rerun after narrowing dispel

The rerun for [issue #168](https://github.com/frankieramirez/mana/issues/168) invoked 24 of 24 allocated parents on 2026-10-21. All allocations ran without a group stop.

Source: `f8252c133dcf3b9a9281939067a5f51ad15076a0`, the head of [PR #174](https://github.com/frankieramirez/mana/pull/174), which contains freshly fetched main `2e62790f12d0e8c0e414477bcd2979430376fe4d`. Host: `codex-cli 0.163.0`; requested model: `gpt-6.1-sol`, reasoning `medium`. Resolved model identity remains unverified.

The schedule is the same as the [#101 group](discovery-group-2026-10-20.md): twelve cases twice in the same slot order, with one serial parent, 120 seconds per parent, zero children and no retries. The runner manifest is unchanged. The user authorization is recorded separately in [discovery-group-2026-10-21-operator-context.json](discovery-group-2026-10-21-operator-context.json).

## Catalog probe

Before the group, `run.py --probe-catalog` rendered the installed catalog with `codex debug prompt-input` and made 0 model calls. It verified `explicit_only_honored` and `installation`, marked `children_disabled` failed as before, and reported no catalog findings. The rendered dispel entry matches the new description in `skills/dispel/SKILL.md` word for word. The record is [discovery-group-2026-10-21-catalog-probe.json](discovery-group-2026-10-21-catalog-probe.json).

## Pass check

No slot outside the dispel cases routed to dispel first. Both dispel-positive slots, [10, 12], routed to dispel. Dispel loaded in 2 slots, both dispel-positive, against 19 in the #101 group, where 17 of those loads were unnecessary. Unnecessary activation fell from 17 slots to 0. The check passed.

## Original classifications

Activation: `{"correct": 24}`. Routing: `{"correct": 24}`. Execution: `{"needs_adjudication": 12, "not_exercised": 9, "timeout": 3}`. Child activity: `{"attempted": 10, "none": 14}`. Process outcomes: `{"completed": 21, "timeout": 3}`.

| Slot | Case | Repetition | First route | Loaded | Activation | Routing | Execution | Process | Children |
|---|---|---|---|---|---|---|---|---|---|
| 0 | vague-bug | 1 | ordinary | none | correct | correct | needs_adjudication | completed | none |
| 1 | scan-positive | 2 | skill:scan | scan | correct | correct | timeout | timeout | attempted |
| 2 | dispel-negative | 1 | ordinary | none | correct | correct | not_exercised | completed | none |
| 3 | ordinary-explicit-only | 1 | ordinary | none | correct | correct | needs_adjudication | completed | none |
| 4 | scan-positive | 1 | skill:scan | scan | correct | correct | needs_adjudication | completed | attempted |
| 5 | ultima-positive | 2 | skill:ultima | ultima | correct | correct | timeout | timeout | attempted |
| 6 | ultima-positive | 1 | skill:ultima | ultima | correct | correct | needs_adjudication | completed | attempted |
| 7 | ordinary-explicit-only | 2 | ordinary | none | correct | correct | not_exercised | completed | none |
| 8 | attune-positive | 2 | skill:attune | attune | correct | correct | needs_adjudication | completed | none |
| 9 | missing-sibling | 2 | skill:portal | portal | correct | correct | not_exercised | completed | none |
| 10 | dispel-positive | 1 | skill:dispel | dispel | correct | correct | not_exercised | completed | none |
| 11 | vague-bug | 2 | ordinary | none | correct | correct | not_exercised | completed | none |
| 12 | dispel-positive | 2 | skill:dispel | dispel | correct | correct | not_exercised | completed | none |
| 13 | changed-target | 1 | skill:scan | scan | correct | correct | timeout | timeout | attempted |
| 14 | mend-positive | 2 | skill:mend | mend | correct | correct | needs_adjudication | completed | attempted |
| 15 | missing-sibling | 1 | skill:portal | portal | correct | correct | needs_adjudication | completed | none |
| 16 | review-or-audit | 2 | skill:scan | scan | correct | correct | needs_adjudication | completed | attempted |
| 17 | review-or-audit | 1 | skill:scan | scan | correct | correct | needs_adjudication | completed | attempted |
| 18 | remedy-positive | 2 | skill:remedy | remedy | correct | correct | needs_adjudication | completed | none |
| 19 | changed-target | 2 | skill:scan | scan | correct | correct | needs_adjudication | completed | attempted |
| 20 | dispel-negative | 2 | ordinary | none | correct | correct | not_exercised | completed | none |
| 21 | remedy-positive | 1 | skill:remedy | remedy | correct | correct | needs_adjudication | completed | none |
| 22 | attune-positive | 1 | skill:attune | attune | correct | correct | not_exercised | completed | none |
| 23 | mend-positive | 1 | skill:mend | mend | correct | correct | not_exercised | completed | attempted |

## Comparison with the #101 group

The first route changed in 9 slots, `[0, 1, 3, 4, 9, 11, 13, 15, 19]`. Each of them began with dispel in #101 and now begins with an accepted route. In 8 more slots, `[5, 6, 14, 16, 17, 18, 21, 22]`, the first route is the same and only the dispel load is gone. The other 7 slots match #101 exactly.

| Slot | Case | Repetition | #101 first route | #101 loaded | Rerun first route | Rerun loaded | Change |
|---|---|---|---|---|---|---|---|
| 0 | vague-bug | 1 | skill:dispel | dispel | ordinary | none | first route changed |
| 1 | scan-positive | 2 | skill:dispel | dispel, scan | skill:scan | scan | first route changed |
| 2 | dispel-negative | 1 | ordinary | none | ordinary | none | same |
| 3 | ordinary-explicit-only | 1 | skill:dispel | dispel | ordinary | none | first route changed |
| 4 | scan-positive | 1 | skill:dispel | dispel, scan | skill:scan | scan | first route changed |
| 5 | ultima-positive | 2 | skill:ultima | ultima, dispel | skill:ultima | ultima | loads changed |
| 6 | ultima-positive | 1 | skill:ultima | ultima, dispel | skill:ultima | ultima | loads changed |
| 7 | ordinary-explicit-only | 2 | ordinary | none | ordinary | none | same |
| 8 | attune-positive | 2 | skill:attune | attune | skill:attune | attune | same |
| 9 | missing-sibling | 2 | skill:dispel | dispel, portal | skill:portal | portal | first route changed |
| 10 | dispel-positive | 1 | skill:dispel | dispel | skill:dispel | dispel | same |
| 11 | vague-bug | 2 | skill:dispel | dispel | ordinary | none | first route changed |
| 12 | dispel-positive | 2 | skill:dispel | dispel | skill:dispel | dispel | same |
| 13 | changed-target | 1 | skill:dispel | dispel, scan | skill:scan | scan | first route changed |
| 14 | mend-positive | 2 | skill:mend | mend, dispel | skill:mend | mend | loads changed |
| 15 | missing-sibling | 1 | skill:dispel | dispel, portal | skill:portal | portal | first route changed |
| 16 | review-or-audit | 2 | skill:scan | scan, dispel | skill:scan | scan | loads changed |
| 17 | review-or-audit | 1 | skill:scan | scan, dispel | skill:scan | scan | loads changed |
| 18 | remedy-positive | 2 | skill:remedy | remedy, dispel | skill:remedy | remedy | loads changed |
| 19 | changed-target | 2 | skill:dispel | dispel, scan | skill:scan | scan | first route changed |
| 20 | dispel-negative | 2 | ordinary | none | ordinary | none | same |
| 21 | remedy-positive | 1 | skill:remedy | remedy, dispel | skill:remedy | remedy | loads changed |
| 22 | attune-positive | 1 | skill:attune | attune, dispel | skill:attune | attune | loads changed |
| 23 | mend-positive | 1 | skill:mend | mend | skill:mend | mend | same |

## Caveats

Process timeouts occurred at slots `[1, 5, 13]`. In #101 they were at slots `[4, 16, 17]`. Execution needs adjudication at slots `[0, 3, 4, 6, 8, 14, 15, 16, 17, 18, 19, 21]`, and commands are flagged for a person at slots `[0, 1, 3, 4, 5, 6, 8, 13, 14, 15, 16, 17, 18, 19, 21]`. These original events and judgments remain available without replacement calls.

Spawns were attempted and failed at slots `[1, 4, 5, 6, 13, 14, 16, 17, 19, 23]`. No child was created. The host capability record reports that child tools are not withheld, so failed spawns stay recorded as attempted child activity.

These are selection observations under the frozen route sets. The first loaded entrypoint determines routing, and an entrypoint outside the accepted set counts as unnecessary. `not_exercised` means the selection-only grader makes no workflow completion claim. No independent human adjudication has been performed. Task quality and human reviewer effort are unmeasured. These results do not establish effectiveness outside this bounded schedule.

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
- `same_schedule_as_prior`: `True`

## Validation

After the live group, with system Python first on PATH, `scripts/validate.sh` passed all 83 fixture jobs, the 42 discovery tests passed, and `run.py --discovery-check` passed. See [discovery-group-2026-10-21-validation.json](discovery-group-2026-10-21-validation.json) and the retained logs.

The original [manifest](discovery-group-2026-10-21-manifest.json), [allocations](discovery-group-2026-10-21-allocation.json), [completion record](discovery-group-2026-10-21-completion.json) and [results](discovery-group-2026-10-21-results.json) are published unchanged. The [archive metadata](discovery-group-2026-10-21-evidence.json) identifies the compressed [raw evidence](evidence/discovery-group-2026-10-21.json.gz) by SHA-256. The portable archive retains slot results, events, stderr, responses where produced, synthetic source and artifacts, frozen evaluator and catalog bytes, operator scripts and validation logs. It excludes Git internals, synthetic host homes and bytecode caches; exact baseline and final product-state identities remain in JSON. Absolute local paths in 56 archived files (events.jsonl, publication-builder.py, response.json, result.json, slot-05-ultima-positive-r2/workspace/artifacts/ultima-audit/profile.json, slot-06-ultima-positive-r1/workspace/artifacts/ultima-audit/metadata.json, slot-06-ultima-positive-r1/workspace/artifacts/ultima-audit/profile.json) are replaced with the placeholders `<run-root>`, `<mana>`, `<codex>`, `<mise>`, `<home>`. For each of those files the archive metadata keeps the original SHA-256 beside the published one, and the result hashes in the allocations and results refer to the original bytes. Publication added no parent invocation.

## Verify the retained evidence

```bash
python3 -B evals/workflows/archive_delegated.py evals/workflows/evidence/discovery-group-2026-10-21.json.gz
```
