# Frontier workflow improvements

Status: packages A through C merged; B/C delegated review gate met in bounded cases; D implemented and prepared for review
Date: 2026-09-29
Updated: 2026-09-30
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


## Package B implementation record

Package B starts from `9918065266c24e01549e3f53e76a168f7735a0ad`, the package A merge with review fixes. The baseline skills were archived before editing, and that commit remains the reproducible baseline. Version 0.37.0 changes evidence judgment and deterministic merge behavior. Packages C and D remain outside this release.

The merge helper retains source contributions without a reviewer-count bonus. Its conservative exact dedup key includes the consequence and proposed fix; wording variants await semantic reconciliation. Legacy promotions recover contribution scores where present, or retain attribution with an explicit fresh-assessment requirement where those scores are missing. Confidence reassessment records added evidence separately and survives subsequent merge passes. The helper checks the record shape; the lead and validator must inspect whether that evidence actually supports the claim.

| Acceptance | Evidence and limit |
|---|---|
| Repeated weak claims stay weak | Real Bash merge fixtures check repeated confidence-50 claims, repeated unsupported claims, and cross-model provenance without promotion. |
| Single-source and low-impact defects remain eligible | A decisive P3 finding survives unchanged at confidence 100. Rubrics distinguish verified benefit from preference. |
| Distinct defects at one location remain separate | Fixtures use the same title and location with different consequences and fix paths. Wording variants remain separate until explicit semantic reconciliation. |
| Existing feedback stays accounted for | Source inspection preserves early and late harvest accounting, including top-level comments, and changes their attribution language. No live PR-feedback agent run was attempted. |
| Incorrect suggestion is declined; real corrections proceed | The repair rubric requires caller evidence before acceptance and provides worked judgments for a contradicted bot suggestion, a demonstrated defect, and a useful spelling correction. These are instruction examples, not observed live repairs. |
| Legacy artifacts retain attribution without invented evidence | Fixtures cover recoverable scores, unavailable scores, historical reviewer artifacts, fresh assessment, and repeated reconciliation. |
| Requirements and findings still get independent validation | Source inspection preserves the roster, full-review selection, requirement checks, and validator selection contracts. The validator prompt now receives reassessment evidence and uncertainty. |

Validation uses `python3 -B scripts/test_review_merge.py` (17 offline tests), `bash scripts/validate.sh`, and the complete 23-pair similarity comparison against upstream revision `414e9d6be166c15d9fb10595204530802ad007ef`. The maximum similarity ratio is 0.24, below 0.30. The initial repeated-claim fixture failed on the old vote-promotion behavior, and legacy/dedup fixtures exposed failures before their implementation. Final results and actual output are recorded in the PR evidence.

No installed files were added or moved. The existing package-contract inventories remain complete; standalone verification and shared-asset checks run through the repository validator. No shared canonical asset changed.

The live runner's host compatibility has not been revalidated. These offline fixtures and source changes establish no frontier-model performance advantage or live reliability estimate. Live repair outcomes and live reviewer judgment remain unverified.

## Package C implementation record

Package C starts from `e1f8417865b778faf0cc61297375f18551fc1c27`, the package B merge including its review fixes. Before editing, `git archive HEAD skills` saved the complete baseline under `/tmp/mana-package-c-baseline`. Its entrypoint SHA-256 values are `102587beac6e6fc97532ff0fb3fad92f797e603dd269ead170d362c15b06e982` for scan and `7d4610fe0800e79fab0f15aba124ab5212b5a12d35c6866802d5d2ebf71acfdd` for remedy. The base commit reproduces that payload; evaluation results retain every installed file hash.

Version 0.38.0 prepares stage-loaded workflows. Package D and new review-policy changes remain outside this work. No canonical shared asset changed. The existing confidence anchors, evidence reassessment, legacy artifact treatment, risk roster, and independent validator instructions remain in place.

### Reference ownership

The map was made before selecting boundaries. Scan already owned reviewer instructions in its subagent template, diff-scope rules, schema, persona files, and peer reference. Its finish-review reference already owned merge, reconciliation, validation, output, and action mechanics. Remedy already owned judgments in the evaluation rubric and role instructions in its scout, fixer, and verifier prompts. Those owners remain.

| Skill and stage | Procedure owner | Retained boundary |
|---|---|---|
| Scan 1 and 2 | `references/scope.md` | Exact diff, remote-scope restrictions, deterministic signals, intent |
| Scan 2b and 2c | `references/feedback-requirements.md` | All feedback surfaces and ticket requirements |
| Scan 3 | `references/roster.md` | Risk-based selection, standards discovery, full/lite gate |
| Scan 3d and 4 | `references/dispatch.md` | Run setup, fast pass, supported model routing and dispatch, complete collection |
| Scan 5 and 6 | Existing `references/finish-review.md` | Late feedback, evidence reconciliation, independent validation, output and actions |
| Remedy Full 1 through 3 | `references/full-mode.md` | Full fetch, CI, triage, central judgment |
| Remedy Targeted 1 and 2 | `references/targeted-mode.md` | Named-thread lookup and judgment |
| Remedy either mode, setup | `references/run-artifacts.md` | Scratch directory and artifact inventory |
| Remedy either mode, 4 through 9 | `references/publication.md` | Fix dispatch and fallback, verification, validation, publication, summary |

Entrypoints retain purpose, arguments, authorization, essential invariants, and stage routing. A resumed publication step routes directly to its owner. The targeted path no longer enters a full-PR verification fetch. Its helper pages only the thread/comment identities and location fields needed for mapping, without unrelated comment bodies, reviews, or conversation comments. Full-mode fetching retains its prior query and output contract.

### Measurement method and acceptance limits

The existing `evals/workflows` runner now accepts a frozen `--skill-root`, a requested model, and a reasoning setting. It records observed complete Markdown/JSON payload reads, repeated retrieval bytes, all command-output bytes, host token usage, and elapsed time beside outcome grading. Complete-content matching is a lower bound: partial and truncated reads are retained in command events but are not reconstructed as full file loads. Input tokens measure cumulative processing, not unique context-window size. No price or frontier-model performance claim follows from these measurements.

Codex CLI 0.159.2 passed a fresh parent containment probe before host acceptance: fixture writes worked, while outside reads, skill writes, and command networking failed. A live report-only compatibility run then produced the expected command events, turn usage, and structured response. Previously accepted 0.155.1 remains accepted. Each live scenario repeats the containment preflight. Requested model and reasoning are pinned to `gpt-6.1-sol` and `medium`; actual resolved model identity is unavailable in the recorded events.

Focused scenarios cover caller-based rejection, full-batch judgments of a real defect and useful correction, a small risky change's roster and explicit ticket requirements, and preservation of a rejected repair push. A held-out targeted repair exercises the no-subagent fallback through real tests and an unpushed commit. Roster selection stops before dispatch and cannot establish finding quality or independent validation. The full multi-reviewer equivalence criterion remains open until delegated containment, child-event observability, and paired review outcomes are established. Package C must remain a draft while that criterion is open.

Exploratory attempts are retained alongside the final comparisons. The first fixture double incorrectly returned a full-fetch response to an unsupported GraphQL query; the corrected double rejects unknown operations, with a regression test. The first publication comparison also exposed unnecessary Full-mode retrieval on resume, which led to the direct stage pointer. Neither exploratory result is silently replaced by a later attempt.

The delegation prerequisite was tested separately with the same permission profile. An ephemeral invocation failed to start its child with its agent reporting no rollout for the thread. A saved-session retry produced a child artifact confirming denied outside reads, denied skill/tool-double writes, denied networking, and allowed fixture writes. The parent JSON stream recorded a wait and the final message, but omitted the child command events and child usage. The runner therefore still disables delegation: child-event collection and grading require a validated adapter before deep-review measurements can be accepted. The successful child sandbox probe is not a passing review-equivalence test.

### Focused results

The retained record is [`evals/workflows/package-c-results.json`](../../evals/workflows/package-c-results.json). It includes all 20 workflow invocations and three compatibility invocations, payload hashes, observed reference reads, repeated-retrieval counts, actual commands that read installed files, usage, reports, and final product diffs. Raw event streams and runner snapshots remain in the ignored `evals/results/workflows-*` directories named by that record. The saved-session compatibility run also observed one completed child; its usage was not exposed. Each comparison invocation had an explicit 240-second timeout and each group an explicit limit of one, four, or five invocations. There were no automatic retries.

The table uses `workflows-v6wyetp_` and `workflows-oej_p8wh`, except the targeted rejection pair, which uses the stricter fixture repeats `workflows-p518piut` and `workflows-rj64kfih`. A second fixture regression test now rejects an unsupported query that merely mimics the helper's filter. Earlier targeted attempts remain in the record with their measurement limit. The final baseline targeted run recovered from an unsupported fixture query with a paginated identity-only query; the candidate used its bundled narrow helper directly. The double models the bundled query shapes, not the entire GitHub API. Alternate query shapes can require fixture recovery, which limits attribution of latency and context differences to the refactor alone.

Values below are baseline -> candidate. All five final focused outcome comparisons passed. Manual inspection of both held-out repair diffs confirmed the sole edit was `value + 2` -> `value * 2`, with the guard and unrelated spelling left intact. Central judgments matched on the false suggestion and both supported corrections. Both roster runs retained correctness, security, adversarial, testing, and standards coverage plus the admin-only and anonymous-denial requirements.

| Scenario | Outcome | Entry bytes | Complete Markdown/JSON bytes, lower bound | All command-output bytes | Seconds | Host input tokens | Host output tokens |
|---|---|---:|---:|---:|---:|---:|---:|
| Targeted rejection | Same caller-grounded decline, no product writes | 36,872 -> 11,134 | 48,868 -> 42,109 | 60,043 -> 51,126 | 149.28 -> 125.12 | 249,053 -> 190,027 | 2,432 -> 1,989 |
| Full-batch judgment | Same decline and two accepted corrections, dry run | 36,872 -> 11,134 | 48,868 -> 49,952 | 60,434 -> 53,460 | 147.21 -> 141.97 | 143,945 -> 169,072 | 2,572 -> 2,168 |
| Small risky change | Relevant specialists and both requirements retained | 38,665 -> 15,022 | 38,665 -> 31,962 | 118,739 -> 91,768 | 74.38 -> 96.45 | 129,584 -> 140,013 | 1,240 -> 1,370 |
| Rejected repair push | Local commit and advanced remote preserved | 36,872 -> 11,134 | 36,872 -> 26,148 | 40,754 -> 29,229 | 113.44 -> 91.31 | 142,398 -> 159,302 | 1,458 -> 1,380 |
| Held-out targeted repair | Scoped tested repair committed, not pushed | 36,872 -> 11,134 | 59,134 -> 52,375 | 68,069 -> 55,461 | 126.28 -> 141.42 | 233,166 -> 244,736 | 1,950 -> 2,146 |

No repeated complete Markdown/JSON retrieval was observed in these ten final invocations. This does not exclude repeated partial reads; the record preserves the commands. Candidate targeted runs loaded the targeted path, artifact setup, judgment rubric, and shared publication reference, with fixer/verifier prompts only in the repair case. They did not load `full-mode.md`. The resumed publication candidate loaded only the entrypoint and publication reference. The roster candidate loaded scope, feedback/requirements, and roster references, stopping before dispatch. Exact per-run inventories are in the JSON record.

Entry load fell in every focused scenario. Total complete instruction bytes rose slightly for full-batch judgment, and cumulative input tokens rose in four scenarios. Latency was mixed. Runs overlapped on the same host, and these samples establish no statistically reliable cost or speed advantage. The held-out baseline issued two queries requesting full feedback surfaces through its legacy lookup/verification path; the candidate issued two identity-only queries. The final targeted rejection pair requested no full feedback surfaces.

### Acceptance and release gate

| Criterion | Evidence | State |
|---|---|---|
| Targeted requests avoid unrelated workflow retrieval | Observed reference inventories and GraphQL request logs; real-helper regression rejects unrelated body/review fields | Met in focused cases |
| Preserve findings and requirement coverage | Paired central judgments and risk/requirements selection pass; all 19 package B merge fixtures pass | Partial: complete delegated reviewer findings and independent validation remain unmeasured |
| Named stages and isolated completeness | Package inventory includes every new reference; deletion tests fail for each of the eight stage assets; all 19 packages verify | Met |
| No new runtime sibling/repository dependency | Isolated package inspection and smoke tests; new Python measurement code stays in maintainer tooling | Met |
| Lower entry load with total context and latency reported | Observed bytes, retrievals, token usage, and elapsed times above, with context limits stated | Met for focused cases |
| Resolve measured quality regressions | Final focused outcomes match; fixture defects were repaired and affected cases repeated with all attempts retained | No measured focused regression; full review remains an open gate |

Validation includes the workflow fixture/grader suite (23 offline tests), the real merge suite (19 tests), reliability/package deletion checks (13 tests), shared-asset check mode, the complete repository validator, and all 31 similarity comparisons against upstream `414e9d6be166c15d9fb10595204530802ad007ef`. The largest similarity ratio is 0.24. New comparisons include the moved procedures; missing comparison files now fail the command. The initial measurement-function, narrow-query, and permissive-double tests each failed on the relevant old behavior before their fixes.

The PR is prepared as a draft, with the full delegated-equivalence gate visibly unmet. This follows the user's instruction to ship reviewable package C work while clearly reporting unmet acceptance criteria. It does not promote package C as behaviorally equivalent across the complete review workflow. Package B's behavior remains preserved by source and deterministic checks; package D has not begun.


## B/C delegated evaluation follow-up

The earlier implementation records describe the evidence available at shipment. Package B merged in PR #59 and package C merged in PR #61. This follow-up starts at `06fdc89` and evaluates frozen B (`e1f8417865b778faf0cc61297375f18551fc1c27`) and C (`06fdc89`) payloads. Package D has not begun.

The maintained record is [`package-bc-results.json`](../../evals/workflows/package-bc-results.json), with the adapter and reproduction procedure in [`delegated-evaluation.md`](../../evals/workflows/delegated-evaluation.md). The original focused record and all its attempts remain unchanged. Portable archives retain the new raw parent events and full persisted family histories, with reviewer artifacts and exact runner snapshots. Per-file digests can be verified offline.

### Adapter and containment evidence

A saved CLI invocation plus the documented app-server descendant and paginated-history interfaces is sufficient for this host. The collector reads history without starting or resuming model turns. It attributes commands and exit outcomes to each parent or child, retains final messages, and rejects incomplete histories. The offline audit also checks parent-stream parity, distinct reviewer and validator threads, and reviewer completion before the first merge.

The initial pilot used one parent and one child with a 180-second timeout. Both ran the immutable probe: outside reads and command networking were denied; installed instruction and tool-double writes were denied; fixture artifact writes succeeded. Every parent and child repeats that probe in the review runs. The host permission profile, model and reasoning settings match across each pair.

The first full baseline completed but was initially rejected because the collector treated nullable command output as a missing exit outcome. Its parent CLI stream established that silent commands can become null output in stored history. The adapter now preserves output availability explicitly while requiring exit outcomes; no missing text is invented. The original rejection and each offline audit remain recorded. All substantive probe and inspection outputs are available, as are the final artifacts. This was an adapter interpretation correction, not a skill behavior fix.

Host-reported model and reasoning metadata are retained. They do not establish resolved backend identity. Separate child token usage is unavailable; the parent CLI turn usage must not be called complete family usage. Complete-content reference matches and command-output bytes are lower bounds, excluding missing output, partial retrieval and some delegation prompt context. No price estimate or statistically reliable performance claim follows.

### Paired observations

The first group permits two parent invocations, each with a 900-second process timeout and an instruction limit of ten children. The host caps active threads at four including the parent. It ran baseline then candidate without automatic retries. A second group, defined before execution, permits the same bounds and reverses variant order for the held-out retry/queue case. The grading rubric was written before outcome inspection. Manual assessment has the variant visible.

The primary pair has identical starting product hashes, normalized requests and normalized host commands. Both report the role-check failure and tenant-isolation failure separately, plus the page off-by-one. Both preserve the anonymous contract, account for all four requirements, reject the misleading suggestions and make no product edits. Every selected reviewer completed before synthesis; a separate validator inspected the code and judged each finding and requirement. The candidate adds a genuine Lore Bard child for local feedback, which limits attribution of cost differences to stage loading alone.

| Scenario | B / C reviewers plus validator | Accepted seeded defects | Requirements | Scope | State |
|---|---|---|---|---|---|
| Authorization and pagination | 5 + 1 / 6 + 1 | 3 / 3, distinct role and tenant findings | Same four judgments | Preserved / preserved | Paired outcome passed |
| Held-out retry and queue | 5 + 1 / 6 + 1 | 3 / 3 failure modes, plus supported test-gap finding | Same four judgments | Preserved / preserved | Paired outcome passed |

| Primary metric | B | C |
|---|---:|---:|
| Entry bytes observed | 38,665 | 15,022 |
| Complete Markdown/JSON bytes, lower bound | 205,432 | 212,383 |
| Repeated complete retrieval bytes | 69,327 | 65,443 |
| Observed command-output bytes, all collected threads | 368,122 | 404,965 |
| Seconds, including setup and collection | 750.05 | 796.53 |
| Parent CLI input tokens | 1,716,367 | 2,029,232 |
| Parent CLI output tokens | 10,796 | 11,704 |

Entry load fell. Total observed instruction bytes, output bytes and parent-turn usage rose in this pair; latency also rose. The roster difference and single sample prevent attributing those changes solely to the refactor. Exact reference inventories, repeats, thread metadata and usage records are retained per invocation.

The held-out pair also has identical product hashes, normalized requests and host commands. Both preserve retry termination and swallowed exhaustion as distinct failure modes within one finding, with separate requirement mappings and both repair conditions. Both retain queue loss as a separate finding and validate the missing failure-path tests. Both reject catch-all exception handling, unconditional delay and unrelated cleanup. C adds an API-contract reviewer to the shared five core roles.

| Held-out metric | B | C |
|---|---:|---:|
| Entry bytes observed | 38,665 | 15,022 |
| Complete Markdown/JSON bytes, lower bound | 295,225 | 218,701 |
| Repeated complete retrieval bytes | 159,650 | 77,394 |
| Observed command-output bytes, all collected threads | 431,378 | 426,224 |
| Seconds, including setup and collection | 778.91 | 786.36 |
| Parent CLI input tokens | 2,070,767 | 1,780,287 |
| Parent CLI output tokens | 11,231 | 10,181 |

### Current gate

The B/C delegated full-review gate is met for these two bounded paired scenarios. All four reviews preserve the seeded failure modes, requirement judgments and product scope. Every selected reviewer is collected before synthesis, and each run has an independent validator. All 32 observed threads, including the pilot family, have their own successful containment probe. Original attempts and adapter rejections remain retained.

Performance is mixed: C has lower entry load in both pairs, higher total observed instruction bytes in the primary pair and lower bytes in the held-out pair. C takes slightly longer in both and selects an extra reviewer in both. Child token totals remain unavailable. These samples support no general speed or cost advantage.

No installed skill payload has changed in this follow-up, so no plugin version bump is needed. Package D has not begun.

Validation: the full repository validator passed, as did all 39 workflow tests. All 350 archived files passed digest verification. The actual command output is retained in `evals/workflows/evidence/validation.txt`. No scan or remedy payload was edited, so the similarity check was not rerun.


## Package D implementation record

Package D starts from `84a41e7`, the merge of evaluation PR #62. The full skills baseline was saved before editing under `/tmp/mana-package-d-baseline`; that base commit reproduces it. Version 0.39.0 adds optional named continuation at the existing router. The B/C gate remains limited to its two bounded paired scenarios. Its performance was mixed, backend identity remains unresolved and child token totals remain unavailable.

### Workflow and state ownership

`skills/portal/SKILL.md` retains the default router and one-handoff `go`, with a separate Stage Run for `portal run <map-or-build-effort>` and equivalent explicit natural language. Stage Run alone loads `references/run.md`. Portal owns serial continuation; a routed sibling retains its unit boundary. The standalone package inventory requires the run reference and helper, with deletion tests for both. No public skill or mandatory sibling installation was added.

`run.md` owns trusted scope/action resolution, destination stops, serial frontier and post-claim rereads, isolation, verification and cancellation/resume. It documents supported managed linked workspaces first and a Git worktree fallback with reserved paths and fresh branches. A separate clone cannot share this first version's local lock. Isolation failure stops before implementation. A missing sibling uses the scoped ordinary-task fallback and reports unavailable sibling guarantees. Cast runs inside the selected unit workspace, preserving its branch constraints.

`run-state.sh` supplies only local state and a directory lock in the common Git directory. Schema 1 stores repository/scope, current actions, destination, unit identities, owned workspace/branch, commit/PR, evidence and stop reason. Atomic state replacement preserves the previous snapshot on a failed update. Failed start reconciliation releases only its newly acquired lock. An existing coordinator's lock is never stolen. Verified effects cannot restart as reserved/active, or lose their recorded commit/evidence identities. The helper validates local commit ancestry and distinct owned workspace/branch identities; the agent still owns live tracker, remote and PR reconciliation. State never grants permission or contains copied private transcripts.

A focused fixture exposed `tickets.sh blocked` hiding native dependency-read errors behind a body fallback. The canonical sift helper now distinguishes unavailable APIs (404/410) from refused/failed reads, and requires readable fallback blocker states. Copies were synchronized through `sync-assets.sh`. This supporting guard prevents treating an unknown relation as eligibility; it does not change `next` or claim into a distributed lock.

### Deterministic acceptance evidence

The new fixture suite invokes the installed Bash state helper and real guarded tracker adapter, using an offline transport with changing issue/PR records. Git worktree and disposable origin operations are real. These tests execute no model and do not prove agent instruction adherence.

| Acceptance | Executed fixture or observation |
|---|---|
| Two independent ready build units, separate workspaces and evidence | `test_two_independent_units_have_distinct_workspaces_evidence_and_open_prs` creates real worktrees/commits, verifies each unit, and retains both PRs as awaiting review. |
| Existing single-ticket and go boundary | Independent grader tests reject a second unit or continuation state; focused live cases exercise each default. |
| Map destination stop | `test_map_frontier_reaches_destination_without_claiming_build` exercises the bundled map frontier/claim/closeout and verifies the owning decision artifact without claiming linked build work. |
| Live dependencies, ownership and changed remote | Adapter tests exercise a competing claim and a new dependency after claim; membership rereads reflect removal, and a real origin base advances before resume. Failed dependency reads remain unknown. |
| Unrelated ready work never claimed | The named parent fixture includes ready issue 99 outside membership, plus blocked/held/unready members. The oracle rejects any claim of these units. |
| Cancellation and verified resume | State tests keep committed work and unfinished edits across stop/start; a seeded cancelled-run fixture includes an actual owned commit, an open PR and narrower current authorization. |
| Missing sibling/workspace | Only portal is installed for the focused cases; ordinary-task execution must disclose unavailable guarantees. The workspace-stop oracle requires no claim or implementation under the supplied isolation limit. |
| Open PRs await review | Real-worktree fixture records distinct synthetic open PR identities and rejects premature tracker closure; the resume case must report the prior open PR as awaiting review. |
| Local overlap and malformed state | Two worktrees cannot acquire the same scope; invalid schema/destination cannot be silently reused. Missing evidence, wrong branch or missing commit cannot establish verified work. |

The initial lock test and record test failed before their helpers existed. The native-read-failure test failed on the previous adapter. The verified-record test exposed an allowed restart of verified work, then passed after the transition guard. These red outcomes are distinct from live evaluation attempts.

### Focused live evaluation and limits

The predeclared groups are in `evals/workflows/package-d-controls.json`. Every invocation repeats the host containment probe, uses Codex CLI 0.159.2 with requested `gpt-6.1-sol`, medium reasoning, delegation disabled and a 300-second process timeout. Group one permits three invocations; its corrected follow-up permits four. There are no automatic retries. Each group freezes the installed payload and runner sources, and retains raw events, structured reports, state and actual attempts separately.

Inspection of the first build invocation found a fixture defect: inherited repository validation required changing `app.txt`, while the ticket required changing its unit file. The agent preserved scope and recorded both units failed, but the initial oracle incorrectly accepted commits/evidence without checking status. The fixture now supplies applicable repository validation. The oracle requires verified/awaiting-review state and observed successful per-unit commands. The original result remains unchanged; a separate offline regrade rejects it. The map and unavailable-workspace observations remain accepted by that regrade. This is a fixture/grader correction, not proof of a passing first build run.

The second group exposed an overly literal evidence-file check: it required a stdout phrase even when the agent recorded actual successful commands, checked commits and exit outcomes. The corrected oracle accepts nonempty durable evidence alongside independently observed successful per-unit commands and verified state. A regression rejects empty evidence and a missing unit check. Separate regrades accept the corrected build and resume observations, while continuing to reject the first failed-state attempt. No live attempt was overwritten.

The raw parent events, structured reports, synthetic artifacts/state and exact loaded runner snapshots are archived per attempt under `evals/workflows/evidence/package-d-*.json.gz`. All 280 files passed digest verification through the existing archive tooling. `package-d-results.json` retains all seven invocations, original judgments, every regrade, payload hashes, loaded-reference metrics and usage. Mid-group maintainer edits could change an on-disk per-attempt source hash after modules were loaded; the frozen `runner-source` snapshots are the authoritative loaded-source pins. The runner now captures source hashes at import, and regrades include every loaded oracle hash.

| Invocation | Outcome after current offline regrade | Seconds | Parent input tokens | Parent output tokens |
|---|---|---:|---:|---:|
| Initial independent build | Rejected: conflicting fixture validation; units recorded failed | 213.23 | 324,765 | 3,668 |
| Map destination | Accepted: decision and owning artifact recorded; downstream build untouched | 217.03 | 327,448 | 3,730 |
| Workspace unavailable | Accepted: concrete prerequisite, no claims or implementation | 102.65 | 119,680 | 1,651 |
| Corrected independent build | Accepted: two verified local commits in distinct workspaces; unrelated work untouched | 252.78 | 427,524 | 4,330 |
| Single-ticket route | Accepted: one local unit, no continuation state | 77.60 | 148,466 | 1,125 |
| Named ticket with go | Accepted: one local unit, no continuation state | 78.20 | 101,900 | 1,012 |
| Seeded cancellation/resume | Accepted: prior commit and draft preserved, open PR awaiting review, only remaining independent unit committed, no publishing | 229.60 | 337,802 | 4,022 |

All six final focused outcomes pass their current offline regrades. Manual inspection confirms truthful missing-sibling reports, map/build separation, no redundant permission questions and preservation of the resume draft. The first group observes the original run payload; the second group freezes the hardened state helper. These are single observations of each scenario, with a deliberate repeat of the corrected build case. Parent usage is cumulative host processing; instruction/output byte measures are lower bounds. These serial invocations use no children and provide no information about missing child usage in the earlier B/C evaluation. No measured speed/cost comparison is claimed. Managed host worktree APIs, a live external tracker, live PR publication inside a run, arbitrary interruption timing and cross-host coordination remain unverified. Serial linked Git fallback, scoped sibling absence and synthetic current-state reconciliation are the tested surfaces. Automatic merging, stacked-PR surgery and implicit watchers remain out of scope.


### Release checks

The focused package D suite has 13 deterministic tests; the complete workflow suite has 55. Standalone verification checks all 19 packages, including both portal asset deletion cases. Shared-asset check mode is clean. All 31 required similarity comparisons against upstream `414e9d6be166c15d9fb10595204530802ad007ef` are present and below 0.30, with a maximum of 0.24; this was rerun because the canonical adapter synchronization changes scan's bundled copy. The complete repository validator is captured in `evals/workflows/evidence/package-d-validation.txt` for this release tree. The PR proof renders the actual focused test output; it establishes those executed checks, with the above live limits retained.

Comment cleanup removed five added comments, then audited subsequent additions. Its retained-lock reshape concern was resolved by failed-acquisition cleanup; no reshape items remain. The seeded-resume fixture contract docstring is retained. No automatic merge, follow-on effort or watcher is part of this shipment.

### PR 63 review fixes

Version 0.39.1 clears inherited repository-local Git variables before locating portal state and verifying unit workspaces. Two-repository regressions cover misplaced state and locks, config injection, and false acceptance of a foreign workspace. The offline claim parser accepts numeric and fixture issue URL targets and reports malformed or unsupported claims as failures. Unexpected grading exceptions now produce a failed result record. These deterministic checks extend the release evidence; the seven archived live attempts above remain unchanged and were not rerun for these fixes.
