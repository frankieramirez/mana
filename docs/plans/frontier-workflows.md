# Frontier workflow improvements

Status: package A implemented for review; B through D remain proposed
Date: 2026-09-29
Baseline: mana 0.35.0, commit aec8fa6

## Outcome

Let capable agents complete authorized work with fewer avoidable interruptions while preserving scope, truthful verification, and standalone installation. Improve the quality of review decisions before expanding the amount of work an agent owns.

Success means the changed workflows honor ordinary user requests, reject unsupported findings, preserve useful review coverage, and report real limits. Prompt length and number of agents are diagnostic measurements. Neither is a success criterion by itself.

## Second assessment

The source review supports instruction corrections now. It supports experimentation on context use and execution horizon. It does not establish a comparative performance ranking between skill stacks or frontier models.

| Finding | Assessment | Implementation consequence |
|---|---|---|
| Blanket authority rule | Fifteen entrypoints say a rule containing `never` or `read-only` holds whatever the conversation says. This conflicts with their surrounding user-priority guidance. | Replace the blanket exception and audit the affected workflow-specific pauses. |
| Contradictory recovery | `remedy` prohibits rebasing, then allows `git pull --rebase` after a rejected push. | Preserve its scoped repair contract: report the moved remote and local commit; leave history repair to separately authorized work. |
| Reviewer agreement | `scan` mechanically raises confidence for multiple reviewers. Local personas qualify as independent by default. `remedy` calls agreement close to proof. | Require evidence for confidence changes. Keep agreement as provenance. |
| Confidence and impact | The scan rubric describes confidence 50 partly as low impact or a nit, despite saying severity and confidence are separate. | Separate evidence strength from consequence and discretionary cleanup. |
| Long entrypoints | `scan` and `remedy` carry substantial conditional procedures in their entry files. Total words do not show which files a real run loads. | Refactor disclosure separately from behavior and measure loaded context. |
| One-ticket boundaries | A ticket is a useful reviewable unit. `cast` and `scry` stop at that unit even when a broader task could proceed. | Keep atomic defaults and add explicit continuation at the routing layer. |
| Existing review reuse | An identical patch does not establish identical base code, requirements, feedback, or environment. | Defer review caching. Repeated review is not removed using patch-id alone. |
| Runtime verification | Capture contracts already distinguish evidence kinds. `augur` and `leyline` supply useful proof and conformance mechanisms. | Preserve these contracts. Reuse the separate project-readiness plan for control integration. |

Local evidence: `skills/scan/SKILL.md`, `skills/scan/scripts/review.sh`, `skills/scan/references/subagent-template.md`, `skills/scan/references/finish-review.md`, `skills/remedy/SKILL.md`, `skills/remedy/references/evaluation-rubric.md`, `skills/cast/SKILL.md`, and `skills/scry/SKILL.md`.

The newer `ultima` audit already keeps impact separate from evidence and forbids confidence promotion by agreement. `ward` already judges feedback against current code without the opening assumption that every reviewer is right. Use those local precedents while keeping each installed skill self-contained.

## Relationship to existing work

- `docs/plans/stack-reliability.md` supplies implemented asset ownership, standalone package checks, evidence contracts, and the workflow pilot. Extend that infrastructure.
- `docs/plans/project-readiness.md` owns project control CLIs, feature maps, and their later integration into build and review. This plan does not duplicate that work or modify consuming projects.
- Narrow all-state tracker body searches for autonomy, review, and progressive disclosure found no matching open implementation work. This is a bounded search, not a complete board audit. Before filing tickets, inspect the current board and relevant children through the tracker adapter.
- This document is a local implementation proposal. Ticket creation, commits, pushes, and PR creation require a request covering those actions.

## Delivery sequence

| Package | Result | Depends on |
|---|---|---|
| A | Consistent user authority and recovery behavior, with focused scenarios | None |
| B | Evidence-based review decisions and merge behavior | A |
| C | Stage-loaded review workflows, with equivalent behavior | B |
| D | Optional continuation through a named map or build effort | A; release after B and C evaluation |

Keep each package independently reviewable. Do not combine a reviewer-policy change, entrypoint rewrite, and new coordinator into one unmeasured release. Save the baseline payload before any implementation change so later comparisons do not depend on reconstructing the old checkout.

## A. Make authority and recovery consistent

### Changes

Audit all skill entrypoints and their loaded references for conflicting priority, unconditional pauses, and permission tokens. Replace the repeated blanket exception with a concise rule that honors explicit user instructions and existing authorization within host constraints. Treat external documents and tool output as task data.

A workflow can define its supported operations and default scope. A capability limitation should lead to a concrete fallback or handoff when authorized. The spelling of a sentence must not create an authority level. Preserve specific protections for unrelated user changes, unrequested messages, credentials, and destructive operations.

Natural language such as "fix these findings and push" must have the same effect as an equivalent action token. A request for an assessment remains an assessment. In `scan`, resolve the intended action from conversation and tokens before deciding whether the final action question is still needed. In `conjure`, reuse already delegated slicing choices. Preserve genuine unresolved product decisions.

Remove the rebase instruction from `remedy`'s rejected-push path. A moved remote stops that push and reports the local commit and the necessary recovery. Do not add automatic history repair to this skill.

Edit existing files directly. Do not introduce a new global runtime-policy dependency or another generated header mechanism solely for this small correction. Keep the existing persona ownership and generation separate.

### Acceptance

- A supplied action or decision is honored without requiring its special token again.
- A report-only request causes no product or remote writes.
- Review text cannot authorize a command, message, or scope expansion.
- A rejected push does not trigger a rebase, force push, discarded work, or falsely resolved thread.
- Missing capability and missing authorization are reported as different conditions.
- Existing standalone packages remain complete and generated assets remain synchronized.

## B. Ground review decisions in evidence

### Changes

Update `remedy`'s entrypoint and evaluation rubric to verify each concern before accepting a fix. Keep inexpensive useful corrections eligible. Preserve the existing distinction between demonstrated defects, valid improvements, deliberate product choices, and unsupported suggestions. Keep central judgment and scoped fixers.

Update `scan`'s confidence rubric so confidence describes evidence strength independently of severity. Explain that its numeric anchors are ordinal categories, not calibrated probabilities. A low-impact finding can have strong evidence; a severe suspected defect can have weak evidence. Keep the critical-risk reporting path and explicit uncertainty.

Remove automatic confidence promotion based on reviewer count from `scripts/review.sh`. Merge compatible evidence and keep source attribution. A confidence increase requires new evidence supporting the stronger anchor, inspected during reconciliation. Mere repeated quotes or agreement do not supply that evidence.

Update `references/finish-review.md`, `subagent-template.md`, `peer-review.md`, `validator.md`, affected persona instructions, report examples, and any schema descriptions that imply agreement proves correctness. A different model family describes diversity; it does not certify statistical independence.

Preserve artifact compatibility where practical. Treat historical `corroborated` and `independence_verified` fields as provenance. Legacy `promoted` state must not carry an unsupported score into a new reconciliation. If underlying evidence scores cannot be recovered from a legacy artifact, require fresh evidence assessment and disclose the limit.

Keep the existing risk-based roster, explicit full-review mode, requirement coverage, and independent validation while testing this change. Changes to those mechanisms would need their own evidence.

### Acceptance

- Two reviewers repeating a weak or unsupported claim do not raise its confidence.
- One reviewer with decisive evidence can produce an actionable finding.
- A supported low-impact defect remains distinct from a stylistic preference.
- Same-location findings with different failure modes or fixes remain separate.
- Existing PR feedback is accounted for, including top-level comments and late arrivals.
- A plausible bot suggestion contradicted by a caller is declined with evidence; a real defect is repaired.
- Legacy promoted artifacts are re-evaluated without losing source attribution or inventing evidence.
- The validator still evaluates actionable findings and ticket requirements independently.

### Deterministic checks

Add fixture-based merge tests that invoke the real Bash helper with synthetic reviewer artifacts. Cover repeated weak claims, a supported single-source finding, distinct defects at one location, missing reviewer artifacts, and reconciliation of legacy promoted output. Include valid variations in wording and reviewer order. Wire the checks into `scripts/validate.sh`.

## C. Reduce entrypoint load without changing the workflow

### Changes

Keep purpose, arguments, authorization, essential invariants, and routing in each entrypoint. Move substantial conditional procedures into references loaded at named stages.

For `scan`, separate scope resolution, feedback and requirements, roster selection, and dispatch mechanics. Keep the existing finish-review reference. For `remedy`, separate full and targeted operation where useful, with shared guidance for publication and verification loaded by both paths. Choose file boundaries after mapping existing references so each decision has one owner.

Update internal stage pointers and `scripts/package-contracts.json` inventories. Existing entry arguments, output contracts, and supported host fallbacks remain acceptance criteria. Keep literal bundled script paths. A missing reference must fail isolated package verification.

Do not move an entire entrypoint into one always-loaded reference. Do not force a word-count target. Record which references each scenario actually reads and whether the split increases redundant retrieval.

### Acceptance

- A targeted feedback request does not load or fetch the whole-PR workflow without a relevant reason.
- Review scenarios retain the findings and requirement coverage accepted after package B.
- Every reference is reachable from a named stage and exists in an isolated install.
- No new sibling-skill or repository-only runtime dependency is introduced.
- Entry load falls for the focused scenarios, and total loaded context and latency are reported alongside quality.
- Any measured quality regression is resolved or the affected refactor is withheld.

## D. Continue an authorized effort through the router

### Proposed interface

Add `portal run <map-or-build-effort>` for a user who requests continued work on one named scope. An equivalent explicit natural-language request can select this mode. Keep bare routing and `go` as their current recommendation and single-handoff behaviors.

Use `portal` because it already owns the standalone exception for sibling routing. No new public skill or mandatory stack installation is needed. Add a stage-loaded `references/run.md` and only the state/helper support the workflow proves necessary.

### Run contract

Resolve the named scope, completion condition, and authorized actions once. Inherit explicit constraints and any supplied limits. Ask only when an unresolved choice prevents safe progress. A map run handles decision work; it does not automatically turn a completed map into a build effort. A build run handles ready members of that effort; it does not claim the global queue.

Execute serially in the first version: re-read the frontier, choose one eligible unit, claim through the existing adapter, perform the unit, verify its result, record its state, then re-read before choosing another. Each routed skill retains its per-ticket completion boundary; the router owns continuation. A failed or blocked unit may be bypassed only for verified independent work inside the same authorized scope.

Build tickets use distinct owned worktrees and branches. Prefer the host's supported worktree mechanism; use a documented Git fallback when available and appropriate. Preserve the original checkout and user changes. `cast` operates inside the selected worktree without acquiring a new permission to switch existing branches. If safe workspace isolation is unavailable, report the prerequisite and stop before starting the next build ticket.

Keep continuation state local and resumable, with schema version, repository and scope identity, allowed actions, unit identifiers, workspace paths, commit/PR identity, evidence, and stop reason. Before resuming, reconcile tracker, branch, and PR state. The saved file never grants fresh authority or overrides later user instructions. Do not put secrets or copied private transcripts in it.

Use existing tracker guards and revalidate eligibility before every unit. Define one active local coordinator per scope and prevent overlapping local resumes. Cross-host exactly-once execution is outside the first version; make no claim that a shared account assignment is a distributed lock.

Publishing is limited to the user's requested extent. A prepared PR remains awaiting review, and an open dependency remains blocked under the existing tracker rules. Do not add automated merging or stacked-PR surgery. Stop when the requested result is reached, only blocked work remains, the user stops the run, a supplied limit is reached, or the host cannot continue. Record an honest handoff. Do not install a detached watcher or schedule implicitly.

If a sibling is absent, preserve the existing plain-task fallback within the granted scope and capabilities. Report which skill-specific guarantees were unavailable. Resume from verified work rather than recreating tickets or branches.

### Acceptance

- Two independent ready tickets can complete in one authorized run with separate workspaces and verification records.
- A single-ticket request and `portal go` stop after their existing unit.
- A map run stops at its decision destination and does not start implementation.
- An open dependency, another owner's claim, or a changed remote is handled from live state.
- An unrelated ready ticket is never claimed.
- Cancellation and resume do not duplicate completed work or discard local edits.
- An unavailable sibling or workspace mechanism produces a truthful fallback or concrete stop.
- Open PRs are reported as awaiting review, never as merged completion.

## Behavioral evaluation

Extend `evals/workflows/` instead of creating a parallel benchmark framework. The current runner only accepts four skills and fixed fixture kinds, forbids delegation, and validates one Codex CLI version. Supporting review workflows requires explicit changes to those contracts and their isolation tests. Do not run a deep review with delegation disabled and call it representative.

Keep offline fixture and grader validation separate from live agent execution. Pin the baseline and changed skill payloads, host version, requested model, reasoning settings, tool configuration, and actual model identity when the host supplies it. Missing identity limits model-specific conclusions. Revalidate containment before accepting a new host version or delegation path.

Start with focused comparisons on the same available frontier model and host. Run the baseline and each package against the same requests and fixtures. Repeat ambiguous or decision-changing cases, retaining every attempt. Expand to a second model only after the comparison infrastructure and cases are informative. Set explicit invocation and timeout limits before live execution; report usage without estimating prices from stale data.

| Scenario | Observable result |
|---|---|
| Existing authorization without a special token | Completes the granted action without a redundant permission question |
| Assessment-only request | Produces findings without product or remote writes |
| Remote changes before a repair push | Preserves the local commit and reports recovery without prohibited history edits |
| Plausible incorrect review suggestion | Rejects the change using the actual caller or invariant |
| Supported defect and useful small correction | Repairs both within scope |
| Multiple reviewers sharing one mistaken premise | Does not promote the unsupported finding by vote count |
| Targeted thread | Uses narrow reads and leaves unrelated feedback alone |
| Small risky change | Retains the relevant specialist and requirement coverage |
| Named effort with an independent and a blocked unit | Continues eligible work and reports the blocker accurately |
| Interrupted run | Reconciles current state and resumes without duplicate effects |

Measure completed outcomes, accepted and missed defects, unnecessary edits, avoidable human questions, and preservation of scope. Report tokens and elapsed time as costs. Count only avoidable interruptions against the workflow; a necessary product decision is legitimate.

Keep grading criteria outside candidate context. Use repository state and actual command events for deterministic outcomes. Review judgment-dependent findings blind to variant where practical. Include held-out scenarios that were not used to tune the instructions. A single passing run establishes one observed outcome.

An external-stack comparison is optional later research. It requires equivalent host capabilities and documented differences in installed dependencies. It is not a release prerequisite for repairing demonstrated internal contradictions.

## Validation and release

- Run the smallest relevant deterministic tests while implementing each package.
- Run `bash scripts/sync-assets.sh` after canonical shared-asset edits and verify its check mode.
- Update `scripts/package-contracts.json` for changed payloads and run standalone verification.
- Run `bash scripts/validate.sh` before every implementation commit. Keep the current dash-check exclusion for `evals/`.
- Run `python3 scripts/similarity.py <origin-skills-directory>` when changing `scan` or `remedy`. Record the origin revision, require every comparison below 0.30, and investigate missing comparison files rather than accepting incomplete coverage.
- Give each shipped behavior release a version bump and changelog entry, choosing the version against the then-current branch. This planning document alone changes no distributed behavior.
- Record actual agent outcomes separately from deterministic tests. Require no critical scope, preservation, or evidence-reporting regressions before promoting a package. Keep cost improvements only when outcome quality holds.

If package C raises missed findings or unnecessary work, retain B and revise or revert the disclosure refactor. If D cannot reliably isolate and resume units, retain the single-handoff behavior while repairing continuation. The earlier correctness improvements remain independently useful.

## Deferred work

Review-result caching, automatic merging, multi-host orchestration, model-vendor routing defaults, new review personas, persona removal, and a universal prompt-size target are outside this implementation. Project control generation and runtime integration remain in the project-readiness plan.

## Planning record

The original proposal was checked against the source, shared-asset ownership, package inventory, existing plans, and the bounded tracker searches described above. That planning pass made no implementation changes and ran no live model evaluation.

## Package A implementation record

The user invoked the implementation workflow on 2026-09-29. This first package changes 15 authority paragraphs, resolves review actions from ordinary requests, reuses supplied slicing and triage decisions, and removes the contradictory repair rebase fallback. Version 0.36.1 records the behavior change. Packages B through D are outside this change.

The baseline skill payload was saved before editing at commit `aec8fa61e174cc9fa4a1faccbbd0caa3c854b369`. No shared script or generated asset was changed. Existing package contracts still describe the same installed files, so no inventory change was needed.

| Acceptance | Evidence and limit |
|---|---|
| Reuse a supplied action or decision | Source changes in the review action stage and slicing and interrogation references; the local-action fixture and grader pass offline. Avoidable questions still need live observation. |
| Report-only scope | The new fixture and synthetic grader test preserve product files, HEAD, and index, and reject an observed push attempt. No agent has executed this new scenario. |
| Review text cannot grant authority | The new authority paragraphs explicitly treat untrusted instructions as data; existing untrusted-report scope checks remain in the passing offline suite. |
| Preserve a rejected repair push | The fixture performs a real local commit and non-fast-forward rejection; grading detects changed history, a forced remote update, and selected prohibited recovery or thread-resolution commands. Agent compliance and actual PR thread state remain unverified. |
| Distinguish capability from authority | The new paragraphs specify independent progress and a concrete fallback for unavailable capability, separately from action authorization. This is source inspection. |
| Standalone and generated assets | The repository validator checks all 19 standalone packages and shared-asset synchronization. |

At the initial package implementation, the workflow dataset contained 11 cases and its offline suite had 16 tests. The full repository validator passed. All 23 similarity comparisons were present against upstream revision `414e9d6be166c15d9fb10595204530802ad007ef`; the highest ratio was 0.24, below the 0.30 limit.

The installed Codex CLI is 0.159.2, while the live runner supports only the validated 0.155.1. Live baseline and candidate runs were not attempted. Revalidate containment and event handling before expanding host support. This package supplies reviewable instruction corrections and offline scenarios; it establishes no frontier-model performance advantage or live reliability estimate.

The PR preflight found base commit `a84a35fc8ee6a054d38120915f7a1726a5fc3927`, which added Performance & Delivery audits. That base was merged without rewriting history. Its changes were preserved and this package version was advanced to 0.36.1. Validation was rerun against the combined tree before shipping.

Review remediation on PR #58 advances the package to 0.36.2. It binds reused permission to its covered repository and target, simplifies the repeated read-only request sentence, and closes two offline grader gaps: masked verification status and failed PR-message attempts after a rejected push. The dataset now has 12 cases and its offline suite has 18 tests, including a changed-target scope scenario. Live agent behavior remains unrun under the existing host compatibility limit.
