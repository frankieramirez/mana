# Route agent corrections into enforceable contracts

Decision: [76](https://github.com/frankieramirez/mana/issues/76), under [the effectiveness map](https://github.com/frankieramirez/mana/issues/72).
Date: 2026-10-17. Status: implementation-ready decision; consumer interventions are not implemented by this document.

Use observed corrections to remove invalid states where practical, then enforce the remaining mechanical requirements with checks. Keep short instruction guidance for decisions that still require judgment. A repeated correction is evidence of a failure to investigate; its frequency alone does not choose the remedy.

The user delegated the decisions in this map. The choices below preserve the existing project-readiness M4 limit of one promotion per pilot. They do not reopen the project-owned control architecture or authorize unrelated cleanup.

## Bounded evidence collection

This decision inspected Mana at `9d1aa521974bc7c72bf9cdd676de18c09a036468`: changelog entries 0.26.0 through 0.42.0, the retained workflow and semantic findings, the matching helper fixtures, and the linked correction history in PRs 69 and 71. Its topics are verification honesty, completion evidence, review confidence, and prose fidelity. Consumer inspection was limited to the two M4 proposals and the current instructions, check catalogue, and CI/control entry points needed to assess them.

The consumer snapshots are Ultima `bea865cdbb49e0e827e30b6b5d1e768555be7fd4` and a private consumer app whose repository is not public. Refresh these sources before implementation. No consumer code ran during this decision.

No private session-log corpus, broad review-history export, or usage telemetry was collected. Unavailable transcripts supply no evidence. A changelog's reported experiment is historical evidence with its stated limits; it is not a new measurement performed here.

## Evidence and routing

| Correction | Observation and distinctness | Consequence and confidence | Route and current disposition |
|---|---|---|---|
| `verification-outcome` | The [capture regression](../../scripts/test_reliability.py) demonstrates a failing proving command hidden by a successful renderer. Separately, the [portal record](../../evals/workflows/package-d-results.json) preserves one synthetic agent run that recorded failed units while the first grader accepted their commits and evidence files. [The correction log](frontier-workflows.md#focused-live-evaluation-and-limits) explains the regrade. These are distinct failure mechanisms, not a production incident count. | A green artifact can be mistaken for successful behavior. High confidence in the recorded reproductions; frequency outside these cases is unknown. | Preserve independent command status and explicit run state, then check them mechanically. Both corrections already shipped. Reuse their fixtures and the control report contract; add no duplicate rule or new runtime. |
| `completion-evidence` | [PR 69](https://github.com/frankieramirez/mana/pull/69) documents one real effort whose evidence ticket closed on merge before its runs passed. The follow-up [PR 71](https://github.com/frankieramirez/mana/pull/71) adds synthetic graders. Those PRs and their cases describe one underlying incident, not independent recurrence. | Closed tickets hid unfinished evidence from the queue. High confidence in the documented incident and final-state fixtures; the new workflow cases had no live agent result in the audited release. | Preserve explicit unmet evidence in the build state and assign it a ticket. The repair is shipped. Keep final-state tests and the original failure record; do not file the same repair again. |
| `prose-fidelity` | [Changelog 0.26.0](../../CHANGELOG.md#0260) records two source scenarios: inferred scheduling behavior from exempt code, and an invented key-rotation reason. Each was repeated three times. Count two source scenarios, not six independent incidents. The later [semantic pilot](../../evals/semantic/findings.md) records a separate CSV guarantee broadening missed by its judge; its three false passes share one source scenario. | Editing can add an unsupported fact or broaden a promise. High confidence in the recorded examples; general accuracy and recurrence remain unmeasured. | Keep the narrow source-fidelity decision rule. Preserve exact exempt text with deterministic checks, and assess entailment with reviewed cases. A general style lint or an unvalidated semantic judge cannot establish factual fidelity. Feed these cases into decision 84 without tuning on its confirmation set. |
| `review-confidence` | [The current merge tests](../../scripts/test_review_merge.py) reject vote-based promotion, preserve source attribution, and exercise duplicate ordering and repeated reconciliation. Changelog 0.37.0 and 0.37.1 record the corrections. These are retained deterministic regressions; they do not establish repeated independent production incidents. | Agreement can look like stronger evidence, and merging can invalidate a supported assessment. High confidence in helper behavior covered by these fixtures. | Preserve the contribution and evidence-assessment records plus deterministic merge invariants. Retain concise guidance to judge new evidence. No additional reviewer or wording rule is selected. |

The evidence supports recurring *classes* of confusion about proof and assertions, with different observation types. It does not support a numerical claim about how often agents fail in general. Already repaired cases remain regression seeds, not a backlog of new work.

## Decision rule for future corrections

For each candidate, first establish the intended behavior and inspect the path that produced the result. Choose the first applicable intervention:

| Route | Use when | Minimum acceptance |
|---|---|---|
| Code, interface, or data contract | The producer can make the invalid state unrepresentable or reject it at the boundary, within the authorized scope. | A constructed bad state fails at that boundary; a valid alternative still works. Consumers cannot bypass the invariant through another supported entry point. |
| Deterministic check | The requirement has an observable, stable predicate but remains legal to express in source. | One known-bad case fails for the intended reason and one legitimate alternative passes. The check reports unsupported analysis and missing prerequisites accurately. |
| Judgment guidance | The decision depends on intent, semantic entailment, or context that the stronger mechanisms do not settle. | A short rule names its trigger and evidence requirement, with a failure case and a valid counterexample. Decision 84 compares it with the relevant rule removed. |
| No new intervention | The claim is unsupported, the correction is already enforced, or costs exceed its demonstrated impact. | Retain the source and disposition. Name what new evidence could change it. |

A structural correction is scoped to the demonstrated cause. Do not add a generic framework, widen accepted inputs, or refactor neighboring code solely to move a rule higher in this table. Existing externally meaningful constraints remain valid even when their enforcement is expensive.

## First pilot promotions

### Ultima: reject fixed palette literals in component style assertions

Accept a narrowed version of the M4 proposal. The [current proof bar](https://github.com/frankieramirez/ultima/blob/bea865cdbb49e0e827e30b6b5d1e768555be7fd4/skills/forge/references/proof-bar.md) forbids pinning regenerated palette values. The [analysis rule catalogue](https://github.com/frankieramirez/ultima/blob/bea865cdbb49e0e827e30b6b5d1e768555be7fd4/packages/analysis/src/rules.ts) has no rule for these assertions. This is a documented policy awaiting enforcement; this inspection found no evidence establishing repeated live violations of it.

The stable requirement is that component behavior tests must not pin a generated palette to a fixed literal. A blanket prohibition on color comparisons is too broad. [Consumer verification](https://github.com/frankieramirez/ultima/blob/bea865cdbb49e0e827e30b6b5d1e768555be7fd4/scripts/consumer-proof.ts) legitimately compares computed colors with values derived from the installed token draft. That detects a broken delivery path without hardcoding the current palette.

Implement one rule in the existing analysis package, scoped initially to component style assertions in the project's classified test files. Recognize a computed color property compared with a fixed CSS color literal, including a locally resolved literal. Support the assertion forms actually used by that scope. Resolve the source value rather than rejecting every string containing a hex value. Report an unresolved relevant expression as an analysis limit; do not claim exhaustive coverage from a syntactic subset. Do not use a repository-wide regex ban or add a shared checking framework.

Acceptance cases:

- Reject a component test that pins `backgroundColor` to a literal RGB or hex palette value, including the same literal through a local constant. The diagnostic names the assertion and owning policy.
- Accept a before/after comparison across a documented state change and a comparison against the installed theme's computed token value.
- Accept CSS compiler or token-generation fixtures whose contract is their exact emitted value, and unrelated text containing a hex string. Keep these outside the component behavior rule.
- Change a palette value in a fixture: valid token-derived verification continues to work, while a deliberately disconnected style still fails its behavioral check.

The bad fixture, valid alternatives, and actual scope inventory must pass review before the rule becomes blocking. A scoped unresolved analysis case remains visible. This is one pilot promotion, not permission to convert every authoring preference into a lint.

After enforcement ships, replace the duplicate absolute wording in Forge with the rule id, its scope, and the few cases requiring judgment. Keep the rationale for state-change and token-derived comparisons. Documentation describing unsupported cases remains necessary.

### Private consumer app: execute the project release gate in CI

Accept the existing M4 gate direction after M2 supplies a runnable project control. At the inspected revision, package.json has test and typecheck commands but no verification entry point; AGENTS.md names validation but no `Control:` pointer. The complete recursive repository tree contains no `.github/` or `verification/` directory. This establishes the inspected repository gap, not the absence of every external CI service or a history of escaped defects.

Keep this as one promotion. The workflow invokes the project's control `release` operation and its report gate using the same reviewed source identity. Configure prerequisites explicitly and retain the report when execution fails. Do not copy the release logic into workflow YAML. The exact command, setup, and branch requirements come from decisions 78 through 80, which reconcile current consumer ownership.

Acceptance cases:

- A selected deliberate feature break fails the release job and names the failed scenario; restoring it permits a successful run with expected cases executed.
- A missing browser or other prerequisite, zero executed cases, and a source change during execution cannot produce a passing gate.
- A successful renderer or artifact-upload step cannot replace the proving command's failed exit status. Evidence upload still retains the failed report.
- A workflow run identifies the tested source and report artifact. A local simulation proves only local behavior; claim CI enforcement only after the required remote job and applicable branch gate are observed.

Recheck current CI before adding anything. If another supported system already enforces this exact condition, reuse it and record the evidence. Do not create a second workflow to satisfy the old proposal. Production deployment, paid inference, real credentials, and unrelated release approvals remain outside this intervention.

## Correction record and acceptance

Keep the pilot's promotion ledger in its proposed `docs/agents/readiness.md`, using these fields. The document is project-owned and stores decisions; execution results remain in attributable run reports.

| Field | Meaning |
|---|---|
| `id`, repository, revision, scope | Stable identity and the affected project boundary. |
| Sources and observations | Links and quoted minimum evidence, observation type, independent incident ids, and repeat counts kept separately. |
| Intended outcome and consequence | The violated requirement and observable impact; severity is separate from evidence confidence. |
| Current enforcement and proposed route | Existing checks, the smallest structural/check/judgment change, and why stronger feasible routes do not settle it. |
| Bad case and valid alternative | Acceptance fixtures, executed evidence if available, and explicit coverage limits. |
| Disposition and owner | Accepted, deferred, rejected, or already enforced; target files, delivery issue, and what evidence can reopen the decision. |
| Obsolete guidance | Exact instruction passages that can be shortened after enforcement, with remaining judgment guidance retained. |

Before accepting a promotion, reproduce or construct the relevant failure and label which it is. Demonstrate the valid alternative through the same entry point. Preserve the old and new outcome when fixing a grader. Never infer success from the checker merely running, a closed issue, or an uploaded artifact.

If the narrow check rejects a documented valid behavior, repair its scope or keep it advisory while the exception is resolved. Never silence the counterexample or relabel the intended behavior to fit the check. Stop after the selected promotion per pilot; further proposals require distinct evidence and their own bounded scope.

## Handoff to instruction ablations

Decision 84 should use the observed prose-fidelity and verification cases as development evidence, then keep source scenarios separate from confirmation cases. It should compare judgment guidance only where code and deterministic checks leave a real decision. Comment-constraint retention comes from decision 77; debugging boundary handling comes from decision 81. Neither is resolved again here.

Preserve the existing confidence helper and outcome checks across all arms. Removing an instruction does not mean removing unrelated enforcement. Measure avoided defects and preserved valid behavior before considering text length or tool count. The M4 color fixture is a candidate deterministic enforcement experiment; its present source inspection is not a measured claim that it improves agent outcomes.

This decision selects the routing policy and both bounded pilot promotions. Consumer implementation, real CI observations, and comparative outcome measurements remain delivery work under the readiness plan and decisions 78 through 84.
