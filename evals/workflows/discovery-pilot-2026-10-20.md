# Discovery pilot: incomplete after five parent attempts

The bounded discovery pilot for [issue #101](https://github.com/frankieramirez/mana/issues/101) stopped after five of 24 allocated slots on 2026-10-20. Slot 4 timed out and exposed a host-control/event-classification discrepancy. Nineteen slots remain unrun. This is an incomplete diagnostic group; it does not establish a discovery success rate. Issue #101 remains open.

## Frozen controls and retained evidence

The [manifest](discovery-pilot-2026-10-20-manifest.json) was written before the first invocation. It freezes the twelve specified cases, two repetitions, seed `20261017`, all 24 schedule positions and the resource authorization. The payload and evaluator are pinned to `7e94b1cb992e9a58dbb9acc56b93ddb5e4ce0669` (Mana 0.44.12). The route inventory's historical source revision is recorded separately; its activation map still matches this payload. Installed catalogs are byte-checked, with the missing-sibling exclusion applied only in that case's setup.

A remote refresh after the attempts found that the worktree was behind `origin/main`: [PR #163](https://github.com/frankieramirez/mana/pull/163), merged as `239a63c260efb89bd7cd66b7c8462e463094eaa7` before these attempts, had already shipped Mana 0.44.13 with Codex policy files for all eight explicit-only skills and a zero-call catalog probe. The operator should have fetched before freezing. These retained 0.44.12 attempts are historical interrupted-pilot evidence, not results for the current shipped catalog. The reporting branch incorporates the newer work without changing the frozen artifacts. A separate [post-merge catalog check](discovery-pilot-2026-10-20-postmerge-catalog.json), with zero model calls, reproduced the corrected behavior: all eight explicit-only entries were hidden and all eleven automatic entries were listed. Its [raw render archive](evidence/discovery-pilot-2026-10-20-postmerge-catalog.json.gz) is kept outside the original pilot evidence. This verifies catalog exposure, not no-child enforcement or completed live cases.

The requested host is Linux Codex CLI 0.163.0, requested model `gpt-6.1-sol`, reasoning `medium`. Existing October 17/18 capability records accepted that exact version for discovery, and a fresh containment probe ran before each attempted slot. Every probe denied outside and route reads, product/catalog/Git/tool writes and command networking while allowing artifact writes. The host's implicit-invocation enforcement remains unknown. Host-reported model identity is unavailable; requested identity is not backend identity.

Resources were capped at one serial parent, 120 seconds per parent, 24 parents and 2,880 parent-seconds, zero children and no retries. These are invocation/time bounds, with no dollar ceiling. The operator retained every allocation before execution. No expanded discovery group or second-host study ran.

The [results](discovery-pilot-2026-10-20-results.json) preserve the original grader output and every allocation, including unrun slots. The [offline adjudication](discovery-pilot-2026-10-20-adjudication.json) adds evidence-bound interpretations without changing routes or original grades. It is an operator assessment, without independent review. The [archive index](discovery-pilot-2026-10-20-evidence.json) identifies the compressed [raw evidence](evidence/discovery-pilot-2026-10-20.json.gz) by hash. The archive contains exact events, stderr, responses, fixture artifacts, initial/final product-state records, frozen catalog/evaluator bytes and operator scripts. Synthetic Git internals and tool homes are excluded; state identities are retained in JSON.

## Why the group stopped

Slot 4's frozen profile sets both `features.multi_agent=false` and `features.multi_agent_v2=false`, yet the event stream contains three completed collaboration `wait` calls. All receiver lists are empty. Stderr records a failed spawn (`no rollout found for thread id`) and parent-transcript warnings. No successful child creation is observed. These events do not prove a child ran, and their coverage does not independently prove that no hidden child work occurred.

An offline `codex -c features.multi_agent=false -c features.multi_agent_v2=false features list` check reports both flags as false. This shows that the overrides parse; it does not establish tool enforcement. Its output is retained in the archive.

The adapter's `observe()` labels every `collab_tool_call` as `delegate`, including an empty wait. The operator therefore retained the literal stop reason `slot 4: delegation violated pilot bounds`. That label is more definite than the raw evidence permits. The actual findings are a conservative operator stop, unexpected collaboration-tool availability/failure, and a process timeout. Slot 1 also has two spawn failures in stderr with no corresponding successful child events, showing why the JSON event stream alone is insufficient for this capability judgment.

The original grader reports slot 4's execution as `needs_adjudication`, because failed-command handling precedes timeout handling. Its independent process record says `timeout` at the 120-second bound. Both remain in the report. A structured response file existed before termination; it does not turn the timed-out process into a completed invocation. Process-family cleanup recorded no surviving processes for any of the five attempts, and final product states match their baselines.

The remaining allocations were not started. Continuing would require first resolving the host's no-child contract and event attribution. The original group is preserved as incomplete; any follow-up needs its own explicit controls, identifiers and resource allocation. There are no replacement attempts here.

## Observations, with separate task limits

The five observed rows have three correct first routes and two wrong first routes under the frozen route sets. Activation is `correct` once and `unnecessary` four times; none is `missing`. These are raw counts among five attempted slots, with nineteen unrun slots retained in the 24-slot denominator. They are not an estimate for the full twelve-case pilot.

| Slot | Case and repetition | First observed route | Activation / routing | Original execution | Process outcome | Task or capability observation |
|---|---|---|---|---|---|---|
| 0 | vague-bug, r1 | dispel | unnecessary / wrong | not_exercised | completed | Read-only debugging separately reproduced the fixture's random stock-reservation failure. |
| 1 | scan-positive, r2 | scan, then dispel | unnecessary / correct | needs_adjudication | completed | Direct review/tests ran. Two spawn failures prevented independent specialist coverage; a malformed reference path also failed. |
| 2 | dispel-negative, r1 | ordinary | correct / correct | not_exercised | completed | No skill loaded. The frozen request contains no quoted text, so byte-fidelity task success is ungradable. |
| 3 | ordinary-explicit-only, r1 | cast | unnecessary / wrong | needs_adjudication | completed | Explicit-only cast loaded from ordinary language. Read-only product enforcement held; the agent produced a tested artifact patch and disclosed it was unapplied. |
| 4 | scan-positive, r1 | scan, then dispel | unnecessary / correct | needs_adjudication | timeout | Response/test artifacts exist, but the parent timed out amid failed spawn/empty-wait activity. No independent review claim is supported. |

`not_exercised` is the selection-only grader's field, not a statement that the agent performed no commands. Failed file reads and searches that matched nothing are adjudication items, not evidence of publication or a product mutation. The generic capability field says `none` for these cases because it records only capabilities removed by fixture setup; it does not erase observed host failures. No intentionally explicit-only entrypoint was penalized for failing to activate. Cast's row concerns an observed load that the frozen route set excludes.

Dispel was loaded alongside both scan routes and during the debugging request. The frozen grader counts any additional entrypoint outside the accepted set as unnecessary, even when used to prepare the final report. This co-loading score should not be read as proof that the diagnosis or direct review was incorrect. Selection evidence and task scope remain separate.

## All allocated slots

Slot numbers are the manifest's zero-based schedule positions. Unrun slots keep their original order and repetition; none was replaced.

| Slot | Case | Repetition | Allocation outcome |
|---|---|---|---|
| 0 | vague-bug | 1 | not_exercised |
| 1 | scan-positive | 2 | needs_adjudication |
| 2 | dispel-negative | 1 | not_exercised |
| 3 | ordinary-explicit-only | 1 | needs_adjudication |
| 4 | scan-positive | 1 | needs_adjudication; process timeout; stop triggered |
| 5 | ultima-positive | 2 | not started after stop |
| 6 | ultima-positive | 1 | not started after stop |
| 7 | ordinary-explicit-only | 2 | not started after stop |
| 8 | attune-positive | 2 | not started after stop |
| 9 | missing-sibling | 2 | not started after stop |
| 10 | dispel-positive | 1 | not started after stop |
| 11 | vague-bug | 2 | not started after stop |
| 12 | dispel-positive | 2 | not started after stop |
| 13 | changed-target | 1 | not started after stop |
| 14 | mend-positive | 2 | not started after stop |
| 15 | missing-sibling | 1 | not started after stop |
| 16 | review-or-audit | 2 | not started after stop |
| 17 | review-or-audit | 1 | not started after stop |
| 18 | remedy-positive | 2 | not started after stop |
| 19 | changed-target | 2 | not started after stop |
| 20 | dispel-negative | 2 | not started after stop |
| 21 | remedy-positive | 1 | not started after stop |
| 22 | attune-positive | 1 | not started after stop |
| 23 | mend-positive | 1 | not started after stop |

## Bounded hypotheses and next action

- Verify the current host's actual no-child tool exposure and failed-spawn event coverage. The configured feature flags and accepted discovery registry did not establish that contract in this group. A future adapter should distinguish `spawn` from `wait` and retain stderr capability failures alongside structured events. This is a harness/host question before another discovery run.
- Investigate whether prose-skill co-loading reflects useful report preparation or an overbroad discovery trigger. The existing observations cannot decide that question. Reproduce against nearby negative and overlapping requests before changing any description; this report changes no activation policy.
- Use the current catalog and its existing zero-call probe before a future study. PR #163 already establishes which Codex policy marker hides explicit-only entries and adds that marker to the shipped skills. The older cast load does not demonstrate a defect in that corrected catalog, and no new trigger change is justified by it.
- Repair the underspecified byte-preservation fixture in a new route/fixture revision. The frozen request supplies no text to preserve; its ordinary selection result is interpretable, while its task-fidelity result is not.

The next action for #101 is host/adapter revalidation, followed by an explicitly budgeted follow-up if authorized. The conditional 92-invocation expansion and second host remain deferred. Human reviewer effort and complete workflow quality were not measured.

## Validation

The 25 offline discovery tests passed before allocation. Archive verification checks every retained file's hash. Required `scripts/validate.sh`, with `/usr/bin:/bin` prepended to the existing PATH, ran against the frozen 0.44.12 source and report additions. Its 397 workflow tests and all 19 standalone package checks passed; the command exited 1 because `RefreshTests.test_directory_rename_follows_source_roots_and_the_break_patch` failed. That same failure was reproduced from an extracted, unchanged `7e94b1c` snapshot. Initial validation logs also retain a broken Python shim and a narrower PATH attempt that omitted npm; neither is reported as a pass. These outcomes are retained in the evidence bundle. The reporting branch's [post-merge validation](discovery-pilot-2026-10-20-merged-validation.json) also exited 1 on that same baseline failure. All 403 workflow tests and all 19 package checks passed on the merged source; the full [validation log](evidence/discovery-pilot-2026-10-20-merged-validation.txt.gz) is retained separately from the original study archive. No live slot was rerun to improve a result.

Verify the retained archive without any model call:

```bash
python3 -B evals/workflows/archive_delegated.py evals/workflows/evidence/discovery-pilot-2026-10-20.json.gz
```
