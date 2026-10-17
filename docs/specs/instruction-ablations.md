# Instruction changes supported by outcome evidence

Decision: [Choose instruction changes through failure cases, counterexamples, and ablation](https://github.com/frankieramirez/mana/issues/84).
Status: decision settled on 2026-10-17. The three prose-fidelity payloads and their execution adapter are frozen in [prose instruction-ablation payloads](../../evals/workflows/prose-ablation.md). The six confirmation source groups are frozen in [prose-ablation confirmation cases](../../evals/workflows/prose-confirmation.md) with their second review pending. Live experiments are unstarted.

## Decision and dependencies

Use the [correction contract](../plans/agent-correction-contract.md) to choose the intervention owner. Prefer a structural constraint where it can enforce the requirement, then a deterministic check for an observable predicate. Keep short guidance for intent, source entailment and other contextual judgments. Existing repaired invariants stay enabled across every instruction arm.

The [comment-cleanup contract](../plans/comment-cleanup-contract.md) defines which constraints must survive. [Runtime debugging](debugging-procedure.md) distinguishes valid boundary handling from a concealed internal invariant violation. The [effectiveness protocol](effectiveness-evaluation.md) owns execution, artifact, grading and reporting controls. This document chooses the instruction variants and the first experiment. It does not reopen those decisions or delay their independent bug fixes.

The user delegated the design choices. The selected first experiment is a narrow prose-fidelity ablation because two recorded source scenarios show both induced errors and a subsequent repair, and six short confirmation scenarios fit a small execution budget. Comment and runtime repairs proceed through their own contracts and deterministic gates while their later ablations are prepared.

## Evidence ledger

| Evidence | What it supports | What remains unmeasured |
|---|---|---|
| [Dispel correction, version 0.26.0](../../CHANGELOG.md#0260) | The old guidance induced code-derived invention in three repeats of one source scenario; the repaired guidance was clean in three. A second source scenario involved an invented PR rationale. | General accuracy. Two scenarios with repetitions are not six independent failures. |
| [Semantic findings](../../evals/semantic/findings.md) | A judge repeatedly missed one confirmed broadening of a CSV guarantee. | Reliable automated semantic acceptance; the correlated judgments do not supply independent evidence. |
| [Review merge fixtures](../../scripts/test_review_merge.py) and [recorded review corrections](../plans/frontier-workflows.md#package-b-implementation-record) | The helper enforces evidence-based confidence and preserves distinct defects and provenance. | Whether further prose changes improve live review outcomes. Keep the helper unchanged. |
| [Comment policy decision](../plans/comment-cleanup-contract.md) | Source inspection identifies deletion-before-replacement as a risk to internal invariants and external intent. | A measured frequency or observed comparative improvement. Its designed cases are acceptance fixtures. |
| [Debugging cases](debugging-procedure.md#paired-acceptance-cases) | Designed boundary, producer, disconfirmed-cause and blocked-runtime cases distinguish legitimate repairs. | Live effectiveness or repeated historical incidents. |
| [Correction-routing decision](../plans/agent-correction-contract.md) | Existing completion/evidence corrections already have owners. The palette-check proposal has valid token-derived counterexamples. | Outcome gains from the proposed consumer checks. Source inspection is not a completed trial. |

Historical failures and current published fixtures are development material. Confirmation inputs come from independent source scenarios created after the three candidate payloads are frozen. A new name, changed numbers or repeated judgment on the same source does not create independent evidence.

## Prioritized variant matrix

`Current` means the named rule in a frozen payload. `Candidate` changes only that decision rule or its named owner. `Removed` deletes that rule from the same surrounding payload, retaining user instructions, authorization, factual-fidelity requirements unrelated to the experiment and existing mechanical checks. Store the exact file-level patch and hashes for each arm.

| Priority and owner | Failure the rule should prevent | Valid behavior it must preserve | Narrow candidate and ablation scope |
|---|---|---|---|
| 1. Comment constraints: `skills/banish/references/comment-reaper.md`, shared comment validation | Deleting a comment before its internal invariant has an effective replacement, or treating unknown external rationale as disposable narration | Removing confirmed redundant narration; retaining a boundary warning, a suppression with an unresolved reason, an intentional negative test or external compatibility intent | Compare current audit-baseline guidance with the resolved constraint classification and replacement-evidence rule. Remove only the selected classification/replacement prose for the third arm. Keep the independently shipped validation hook and scope protections identical across arms; freeze its shared base separately from historical baseline reconstruction. |
| 2. Boundary guards: Sift-owned debugging reference copied into Cast | A downstream default hides a broken producer, or a categorical guard ban rejects legitimate external input handling | Optional CSV display-name fallback at the boundary; transaction repair for a settled payment missing its promised ledger entry; undoing only a disproved speculative edit | Compare pre-reference payload, the stage-loaded six-step procedure and the same payload without that reference. Current and removed are identical when no equivalent prior rule exists; report two distinct arms, not three independent treatments. Use the designed pairs for development, new contracts for confirmation. |
| 3. Test quality: `skills/cast/references/tdd.md` and scan's testing reviewer | Rejecting useful contract assertions because of their syntax, or keeping tests that mirror implementation while missing a broken behavior | Exact persisted status/format assertions used by real consumers; meaningful observable interaction counts; valid refactors that change private calls | Replace the affected categorical examples with two contract questions: does a behavior-breaking change fail, and does an internal refactor preserving that behavior pass? The removed arm omits only that test-selection paragraph. Evaluate Cast and the reviewer in separate groups to avoid changing two workflows at once. |
| 4. Prose fidelity: `skills/dispel/SKILL.md` | Invented specifics or causes; broadened promises; deleting a relevant condition while removing vague wording | Source-supported numbers and reasons, intentional uncertainty, verbatim material, an explicit request to interpret code | Compare the existing Fidelity section and final fidelity self-check with a short source-and-scope rule, then remove those two blocks only. Surrounding plain-speech source restrictions remain fixed, so this estimates their incremental value. This is the first bounded experiment. |
| 5. Evidence-based review: scan reconciliation guidance | Raising confidence from agreement, merging separate failure modes or accepting a plausible suggestion contradicted by a caller | A decisive single-source finding, an inexpensive supported correction and multiple distinct defects at one location | Keep `review.sh` and all merge fixtures unchanged. Compare existing explanatory prose with a concise evidence/contract rule and that prose removed. Retain procedural fields needed to operate the helper in every arm. Test the lead's judgments, not its ability to repeat a slogan. |

The test-quality row is a source-grounded hypothesis, not a claim that Mana has already deleted a contract test. Its current TDD paragraph says to skip internal collaborators and a database side channel; the actual contract decides whether such an observation is meaningful. Confirm both harmful rejection and preserved useful rejection before adopting a rewrite.

## Structural and deterministic replacements

When a check replaces an instruction, hold the check constant while measuring whether its explanatory prose still helps. First demonstrate that the known-bad case fails for the intended reason and legitimate variants pass. The proposed palette assertion check must accept installed-token-derived comparisons, before/after state comparisons and exact compiler-output fixtures outside its component-style scope. The completion and review-confidence fixes already have equivalent regression ownership; add no duplicate enforcement.

Map each obsolete prose paragraph to the boundary or check that now owns it. Remove only the procedure it actually enforces. A runtime assertion cannot prove external compatibility intent, and a regex that catches named invented terms cannot establish source entailment. Keep that residual context or report it as unresolved.

For short versus stage-loaded wording, preserve the decision semantics and use the same payload except for the named move. Record complete observed reads and repeated retrieval separately. A smaller entrypoint can still load more context, as the [paired record](../../evals/workflows/package-bc-results.json) demonstrates. Shortening, moving and changing judgment belong to separate experiments when attribution matters.

## First experiment: prose fidelity

Freeze audit baseline `9d1aa521974bc7c72bf9cdd676de18c09a036468`, the complete installed dispel payload and the runner snapshot. Make these three conditions before generating confirmation inputs:

| Condition | Exact change |
|---|---|
| `current-fidelity` | Unchanged Fidelity section and self-check item 9 |
| `scope-fidelity` | Replace that section and item with the candidate below |
| `section-removed` | Delete that section and item 9 only; preserve the other source restrictions and style rules |

Candidate text:

> Preserve the source's task-relevant facts, conditions, quantifiers and uncertainty. Make the wording concrete only with details the source prose states. Preserve exempt text exactly; derive new claims from it only when the user explicitly requests interpretation. A missing reason or measurement stays missing. Removing filler must preserve a qualified claim that matters to the task. Before returning, compare every changed claim with its source and restore any lost condition or unsupported addition.

Use the two historical invention cases and the published semantic examples as development checks. They can reject an obviously broken candidate before confirmation. They never contribute to the confirmation denominator. A candidate change after inspecting a confirmation output invalidates that group for confirmation of the next variant.

An evaluator creates six new source groups after the payload freeze: an absent causal explanation, an adjacent code/config inference trap, a non-exhaustive list of invalid inputs, a conditional quantitative claim, a source-supported concrete explanation, and an explicit interpretation request with a verbatim segment. Each group includes enough source context to establish an exact fidelity oracle and at least one legitimate statement the rewrite must retain. Use different subject matter and underlying contracts from the historical sources. The evaluator keeps source statements and expected judgments outside candidate access except for the task's input text.

The candidate's author does not tune against those labels. Before execution, an independent reviewer checks whether every proposed good and bad output follows from the source and user request. If reviewers cannot agree on the contract, replace that source group before freezing the manifest. Freeze source hashes, request hashes, permissible transformations and protected spans. The [confirmation cases](../../evals/workflows/prose-confirmation.md) implement these contracts; their second review is pending.

Run six groups, three conditions and two repetitions: 36 parent invocations, no children, 180 seconds each, one parent at a time. Maximum parent process time is 108 minutes. Use the same validated host, requested model and medium reasoning as the main protocol, with a fresh host check and an explicit instruction-loading wrapper. Shuffle condition/repetition cells within each source group using seed `20261017`; retain every attempt and provide no automatic retries. This group is separate from the 72-invocation comparative pilot.

The [prose adapter](../../evals/workflows/prose-ablation.md) supplies the prose fixture and the explicit condition payloads inside the existing evaluation machinery. Preserve the original raw source and final answer, plus actual skill-file reads. The optional semantic runner may grade saved outputs afterwards; it does not execute the conditions or replace human fidelity review.

## Acceptance, reversion and uncertainty

Apply the main protocol's source-state, scope and honesty gates. For prose, the primary criterion is all task-relevant claims entailed by the source while preserving required facts and protected spans. Exact preservation uses deterministic checks. Two blinded reviewers assess additions, lost conditions and unsupported interpretation from the source, then adjudicate disagreements. Judge concise style separately; a better style score cannot compensate for an invented fact.

Count each source group's outcomes across its repetitions. A candidate with a new fidelity, scope or evidence-honesty failure is withheld or reverted pending a new diagnosis. An infrastructure failure creates an incomplete comparison, never an implicit pass. Keep a first-pilot candidate for a new confirmation study only when it improves at least two distinct source groups, regresses on none and meets every critical gate. Otherwise report inconclusive or retain the existing rule. Two repetitions provide variability observations, not a reliable failure-rate estimate.

If `section-removed` preserves all observed outcomes, report that the dedicated blocks added no measured benefit on this sample. Do not remove them globally on that result alone. Confirm removal on 12 new source groups with three repetitions per condition and a second supported model, with a separately frozen budget. Keep source groups together and expose uncertainty. For a safety-relevant rule, an unseen-scenario loss outweighs an instruction-byte saving.

Report `retain`, `shorten`, `relocate`, `replace-with-check`, `remove` or `inconclusive` for each tested rule, with its exact patch, affected source groups, adverse outcomes and evidence limits. Efficiency evidence is conditional on preserved outcomes. Family usage missing from the host stays missing, and words removed are reported only as a text measure.

## Delivery sequence

Implement the independent comment and runtime contracts first with their paired deterministic regressions. Add the evaluation condition/prose adapters and grader fixtures under the main protocol. Freeze and run the first prose experiment, then choose the next matrix row from observed failures and intervention cost. Keep the no-rule comparison narrow and preserve installed package completeness. Every shipped instruction change follows the repository's version, changelog and validation rules; the decisions here alone change no installed behavior.
