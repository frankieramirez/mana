# Project readiness plan

Status: M1 and the first inspect/map/install recipe shipped; consumer challenges, refresh and M4/M5 delivery remain pending
Date: 2026-09-24
Updated: 2026-10-17
Decisions: [78](https://github.com/frankieramirez/mana/issues/78), [79](https://github.com/frankieramirez/mana/issues/79), [80](https://github.com/frankieramirez/mana/issues/80), under [map 72](https://github.com/frankieramirez/mana/issues/72)

## Outcome

Give each project a control skill that lets a fresh agent find a feature, run the app, and report honest results tied to the checked source. Mana owns the portable contract, recipes, and conformance checker. Each project owns its control CLI, feature map, tests, and startup instructions. Extract a shared runtime only when three or more projects carry the same copied code with the same bugs.

Measure fewer repeated setup steps, avoidable human interventions, and escaped defects on real tasks. A readiness score, a successful process exit, and shorter instructions cannot establish those outcomes.

The October 17 decision review settled the remaining design choices without changing or running either consumer. Subsequent implementation is named separately above and in build 88. No live performance improvement is established. The historical M1 results below retain their original source revision.

## Current evidence and decisions

The consumer inspection on 2026-10-17 used immutable source revisions. Repository and issue reads ran through the GitHub connector. Searches for `control/0` and `leyline` in current Clankhaven issues returned no matches; that bounded search does not establish that all related work is absent. Recheck active work and source before implementation.

| Consumer | Observed current state | Decision |
|---|---|---|
| [Ultima at bea865cd](https://github.com/frankieramirez/ultima/tree/bea865cdbb49e0e827e30b6b5d1e768555be7fd4) | [PR 556](https://github.com/frankieramirez/ultima/pull/556) merged on 2026-09-24. Its [Control pointer](https://github.com/frankieramirez/ultima/blob/bea865cdbb49e0e827e30b6b5d1e768555be7fd4/AGENTS.md), [control instructions](https://github.com/frankieramirez/ultima/blob/bea865cdbb49e0e827e30b6b5d1e768555be7fd4/.agents/skills/testing-ultima-docs/SKILL.md), `knowledge` records, break patch, and `control/0` report now exist. [Forge](https://github.com/frankieramirez/ultima/blob/bea865cdbb49e0e827e30b6b5d1e768555be7fd4/skills/forge/SKILL.md) discovers features and verifies components. | Keep it as the reference. Remove the old proposals to add already shipped discovery and verification. Current full conformance remains unexecuted in this assessment. |
| [Clankhaven at d07dcc13](https://github.com/lightburden/clankhaven/tree/d07dcc13f819ba1e2617b0170ecd5419ee98ba1b) | The repository has moved from `frankieramirez/clankhaven` to `lightburden/clankhaven`. [AGENTS.md](https://github.com/lightburden/clankhaven/blob/d07dcc13f819ba1e2617b0170ecd5419ee98ba1b/AGENTS.md) names the hosted product as current and v0.3 as frozen. The [router](https://github.com/lightburden/clankhaven/blob/d07dcc13f819ba1e2617b0170ecd5419ee98ba1b/src/app/router.tsx) redirects `/briefing` to `/kingdom`. Existing tests exercise that return experience. | Keep the hosted return briefing as the first new consumer. Do not substitute the frozen dashboard to obtain an easier pass. If the hosted fixture cannot run, report that limit and repair its named prerequisite. |
| Clankhaven control gaps | The complete [source tree](https://api.github.com/repos/lightburden/clankhaven/git/trees/d07dcc13f819ba1e2617b0170ecd5419ee98ba1b?recursive=1) has no `verification/` or `.github/` paths. The [package scripts](https://github.com/lightburden/clankhaven/blob/d07dcc13f819ba1e2617b0170ecd5419ee98ba1b/package.json) have no control command; AGENTS has no Control pointer. This establishes no checked-in GitHub Actions workflow at this revision, not the absence of every external CI system. | Add a small adapter around existing tests, scenario records, a project control skill, and one declared break patch. Release-gate work follows the runnable pilot in M4. |
| Ultima configuration drift | The [launch profile](https://github.com/frankieramirez/ultima/blob/bea865cdbb49e0e827e30b6b5d1e768555be7fd4/.claude/launch.json) uses port 5174 while the control instructions describe 5173. Separate profiles may intentionally differ. | Use this as a refresh reconciliation case. Record which profile each instruction describes before proposing a correction; do not replace both values blindly. |

Mana already has [control/0](../../skills/leyline/references/contract.md), [conformance](../../skills/leyline/references/conformance.md), [capture evidence](../../skills/reveal/references/capture.md), a [build spec check](../../skills/cast/references/spec-check.md), and [review reconciliation](../../skills/scan/references/finish-review.md). Extend those owners. Mana 0.43.0 adds Leyline inspect/map/install with a project-owned Node recipe and local conformance fixtures under [ticket 90](https://github.com/frankieramirez/mana/issues/90). Actual consumer rollout, full challenge evidence, refresh and workflow integration remain tracked under [build 88](https://github.com/frankieramirez/mana/issues/88).

## Contract and ownership boundary

The [control contract](../../skills/leyline/references/contract.md) is authoritative. Keep `control/0`: this source inspection identifies implementation gaps, not a required schema change. A second consumer must produce conformance evidence before any incompatible contract is proposed.

- Discovery uses the root-relative `Control:` pointer and the control skill's `Command:`, optional `Prepare:`, and record-directory keys. Required verbs are `list`, `describe`, `feature`, `changed`, and `release`, all supporting `--json`.
- Run outcomes are `passed`, `failed`, `incomplete`, and `cancelled`. Exit 0 means passed or successful discovery; 1 means proven failure or malformed records; 2 means usage or unknown id; 3 means incomplete; 130/143 mean cancelled. A successful discovery or `--plan` response is never an executed feature check.
- Reports retain `runId`, `source.identity.head`, `source.identity.manifest.digest`, `source.sourceChanged`, prerequisites, and each check's `argv`, status, `expected` and `executed` scenario ids. A missing prerequisite, zero executed cases, missing expected case, or changed source cannot pass.
- Feature and scenario records contain intent and reach information. Verification outcomes live in run reports. `proposed` means inferred from source, `confirmed` means a person agreed to the intent, and `unresolved` means an open intent question. Passing tests do not confirm intent.
- Optional report fields may describe fixture kind, selected base, environment, artifact paths and hashes, timings, and teardown. Preserve the required fields and existing readers. Installation bookkeeping lives outside the feature schema. No migration or new schema version is needed for these decisions.

## Milestones

| Milestone | Deliverable | Acceptance still needed |
|---|---|---|
| M1 | Portable contract and checker | Historical results below; recheck the current reference before relying on it |
| M2 | Hosted return-briefing control pilot | Static and dynamic conformance, known failure, missing prerequisite, cold-session challenge, retained evidence and clean teardown |
| M3 | Generation, installation, and refresh | Repeatable no-diff refresh plus drift, conflict, interruption, and failed-challenge cases |
| M4 | Correction promotion | One narrow mechanical check per pilot, under the separate correction contract |
| M5 | Triage, implementation, and review integration | Honest per-criterion evidence and bounded paired task measurements |

### M1: shipped contract and historical results

Mana 0.33.0 shipped the Leyline skill, contract, conformance checker, and `scripts/test-leyline.sh`, included in `scripts/validate.sh`. The initial fixtures covered 16 static violations, 10 report lies, and 12 dynamic fake-CLI modes. They exercise ignored break patches, accepted unknown ids, incomplete discovery, mismatched exit/report outcomes, zero executed cases, missing prerequisites, missing contract identity, reused run ids, shared ports, incomplete runs, hangs, and honest runs.

The original 2026-09-24 Ultima inspection was at `7b479d4`: static conformance found 9 errors and 3 warnings. The missing Control pointer, six missing knowledge fields, two fixture-only orphan bindings, two derived-source warnings, and missing break patch described that revision. A real `verify feature dialog --json` run took 139 seconds and correctly returned incomplete, exit 3, for missing locked Chromium and an unavailable consumer-smoke fetch. Its report lacked the contract field.

A local conformance patch then passed static validation with two derived-source warnings; verification unit tests passed except a cancellation case that also failed on the unchanged checkout. PR 556 subsequently merged the reference conformance changes. These are historical observations, not results for `bea865cd`. No current dynamic consumer challenge was executed for decisions 78 through 80.

### M2: hosted return-briefing pilot

Implement one complete feature first: `briefing`, described to users as the return summary in the kingdom Overview. Aliases include "welcome back", "came back", "empty briefing", and "workers stopped". Reach records explain that `/briefing` redirects to `/kingdom`; API and CLI paths are separate ways to observe the same accounting. Authentication and worker setup are fixture prerequisites rather than six additional pilot features.

Start the source map at `src/hosted/briefing.ts`, `src/hosted/cli.ts`, `src/app/router.tsx`, and `src/app/routes/kingdom.tsx`, then include the services and fixtures their assertions actually depend on. Shared accounting or startup changes must widen selection. The proposed execution entry is `npm run --silent verify -- feature briefing --json`; it does not exist yet.

Use the existing [briefing tests](https://github.com/lightburden/clankhaven/blob/d07dcc13f819ba1e2617b0170ecd5419ee98ba1b/tests/hosted/briefing.test.ts) as the starting assertions:

| Proposed scenario id | Existing coverage to preserve | Required binding |
|---|---|---|
| `briefing.return-summary` | Synthetic worker activity, free-worker window expiry, agent lease expiry, API/CLI agreement, read-only accounting, browser redirect and welcome-back dismissal, retained daily totals after folding | Bind the existing first test with a literal scenario registration. Keep its assertions and declare its API, CLI, and browser scope. |
| `briefing.no-activity` | An account with no workers reports zero production, an empty worker list, and valid default dates; malformed or future `since` is rejected | Bind the existing second test. It proves API behavior; a browser empty-state claim requires an additional browser assertion. |

The initial records remain `proposed`. Existing assertions establish current behavior, not final product decisions about welcome-back copy, retention duration, or the default reporting window. If a requested fix depends on one of those choices, record the question as `unresolved` and continue independent setup work. This plan authorizes the pilot choice without silently confirming every consumer behavior.

#### Minimum outputs and owners

| Owner | Output |
|---|---|
| Mana | Stage references for inspect, draft map, install, challenge, and refresh; a control-skill template; a TypeScript/Node recipe; targeted conformance regressions learned from this consumer |
| Clankhaven | Project-owned `scripts/control.ts` and necessary helpers, `npm run --silent verify --` entry, `skills/clankhaven-control/SKILL.md`, and the root `Control:` pointer |
| Clankhaven | `verification/features/briefing.json`, the two scenario records, literal test bindings, and `verification/breaks/briefing.return-summary.patch` |
| Clankhaven | Reusable local fixture startup/seed/teardown, source snapshot and report adapter, plus installation history in `docs/agents/readiness.md` |

Adapt the existing Vitest tests and launch helpers. Do not add a parallel test DSL or replace the existing test runner. `changed` selects the briefing tests for related app, service, fixture, and record changes; uncertain selection widens the run. `release` invokes the project's required release checks, including the mapped feature. A briefing-only pass must not claim whole-product coverage. Determine the existing release obligations from current project instructions before implementing that verb.

#### Setup and lifecycle contract

| Area | Observed source | Required pilot behavior and unproven work |
|---|---|---|
| Install/build | Node minimum is 22.13. Root scripts use npm; both npm and pnpm lockfiles exist. [Global setup](https://github.com/lightburden/clankhaven/blob/d07dcc13f819ba1e2617b0170ecd5419ee98ba1b/tests/globalSetup.ts) compiles TypeScript and builds app/site assets. | Start with the existing npm command surface and frozen `npm ci` in the disposable snapshot. Confirm its lockfile consistency and browser setup empirically. Do not delete a lockfile as a readiness side effect. Capture build failures and duration. |
| Authentication and data | Briefing tests provide a loopback fake GitHub provider, synthetic client values, authenticated accounts, temp SQLite stores, and a file-backed fake clock. | Reuse these fixtures. Seed worker activity through the public local API and CLI. No real OAuth account, private data, deployed endpoint, paid inference, or production secret is needed. Report prerequisite names, never secret values. |
| Ports/processes | Briefing's free-port helper releases the socket before startup. [Kingdom tests](https://github.com/lightburden/clankhaven/blob/d07dcc13f819ba1e2617b0170ecd5419ee98ba1b/tests/hosted/kingdom.test.ts) use [reserved ports](https://github.com/lightburden/clankhaven/blob/d07dcc13f819ba1e2617b0170ecd5419ee98ba1b/tests/hosted/reservedPorts.ts). | Reuse reservation and owned-process patterns for provider, account, kingdom, and site. A release-to-bind gap still exists: bound retries must choose fresh owned resources. Never use a fixed port or kill an unknown listener. Prove two simultaneous runs succeed with distinct ids, directories, stores, and ports. |
| Readiness | Existing helpers wait for service startup and browser state. | Use bounded readiness probes of the fixture's expected identity and API protocol before executing scenarios. Capture the failing service and its stderr on timeout; timeout is incomplete. No fixed sleep establishes readiness. |
| Execution surface | Briefing uses Node service processes and a production-built Vite UI. [Workerd test helpers](https://github.com/lightburden/clankhaven/blob/d07dcc13f819ba1e2617b0170ecd5419ee98ba1b/tests/hosted/devServer.ts) and [preview seed tests](https://github.com/lightburden/clankhaven/blob/d07dcc13f819ba1e2617b0170ecd5419ee98ba1b/tests/hosted/previewSeed.test.ts) also exist, with temp persistence and isolated Wrangler/Miniflare registries. | Label the first pilot `hosted Node fixture`. It proves that surface only. Reuse the workerd fixtures for later Worker parity claims; Node success cannot establish Durable Object persistence or deployed behavior. |
| Isolation | Existing tests build outputs and remove temporary state. | Run from a snapshot or disposable worktree, including build and install. Record source identity before execution and detect change during it. Preserve the user's tracked files, untracked files, index, and HEAD. |
| Cleanup/evidence | Tests stop their services and delete fixture directories. Evidence is not yet a control report. | Before removing ephemeral state, copy sanitized logs, JSON report, failing/passing observations, and artifact hashes to a fresh retained evidence directory outside the fixture. Always stop owned browsers/processes and release resources, including on failure or cancellation. Teardown failure is incomplete, with the original failing checks retained. Retained files must remain readable after cleanup. |

The actual required Chromium build and installation command must come from the consumer's current dependency setup and a successful probe. Do not assume `playwright-core` supplies a downloaded browser. A missing browser or unavailable dependency is incomplete with exit 3, with its repair named. A candidate may still be reviewed as an unverified patch.

#### Challenge and acceptance

Run these in disposable copies of one pinned consumer revision. Keep every attempt, its initial/final state, report, commands, and evidence. The challenger knows the seeded fault; the cold agent sees the normal request and crop, without scenario names or the oracle answer.

1. Baseline: static conformance passes. Run discovery, describe, and `feature briefing --json`; validate the report and artifact identity. At least the two expected cases execute. A valid empty account must pass its zero-production assertions; zero production is distinct from zero tests.
2. Controlled failure: apply the declared patch that suppresses a required return summary to the disposable source. The feature must fail with exit 1 and identify `briefing.return-summary`. Restore the exact patch and rerun: it must pass. The checker must reject a CLI that returns success with a failed, skipped, or unexecuted expected case.
3. Cold session: provide "came back and the briefing is empty ???" plus a crop from the controlled-failure fixture. The agent finds the owning feature and current route, uses the documented fixture, reproduces the defect, and cites the failed check and current source identity without creating a bespoke helper. Repeat the normal-account case so a valid empty account is not diagnosed as defective.
4. Missing prerequisite: remove browser availability in a disposable environment. The feature returns incomplete/3, names Chromium, retains its evidence, and cleans up. The cold agent reports blocked verification and does not claim the report proves behavior.
5. Concurrency and source change: two concurrent runs pass with separate resources; a source mutation during a run makes it incomplete. Unknown ids return 2. Cancellation retains cancelled status and cleans up owned resources.
6. Preservation: compare HEAD, index, tracked and untracked file content in the user's checkout before and after success, known failure, blocked setup, and cancellation. Verify retained artifacts after fixture removal. Then run the full dynamic conformance challenge and carry any newly discovered contract regression back to Mana's fake fixtures and the current Ultima reference.

M2 passes only after those observations exist. The setup source inspection in this plan is not a substitute. If a test's fixtures cannot support the cold browser session yet, extract the smallest reusable fixture from the same test, record that implementation delta, and rerun the challenge.

### M3: generation, installation, and refresh

Generate a reviewable candidate diff in an isolated checkout. Existing project verification remains the starting point: inspect and adapt its entry point, records, and tests before adding a new command. A passing challenge can establish operational readiness; it cannot settle product intent or authorize publication beyond the user's request.

#### File ownership

| Surface | Ownership and update rule |
|---|---|
| Control CLI, test assertions, launch/seed/teardown code | Hand-maintained project code after initial generation. Refresh proposes a focused patch; it never regenerates these files wholesale. Preserve any existing verification command and its required checks. |
| Feature/scenario records | Project-owned data. Source-derived paths, aliases, and reach candidates may be proposed. Preserve confirmed intent, scenario expectations, stable ids, and record history. Source contradicting intent becomes a discrepancy with evidence. |
| Control skill | Project-owned instructions. Template markers may delimit generated discovery keys and measured setup facts; everything outside explicit markers is human-owned. An unmarked existing skill is entirely human-owned. |
| Root Control pointer | One managed line, changed only in a candidate diff after resolving the target. Preserve surrounding guidance and alternate-profile intent. Never create a second competing pointer or activate a dangling one. |
| `docs/agents/readiness.md` | Project-owned installation ledger. Record generator version, source revision/digest, affected paths, installed blob hashes or base commit, knowledge decisions with evidence, challenge run ids, conflicts, and pending work. Append a new record only for a material change or actual new observation. No timestamp-only refresh. |
| Reports and artifacts | Immutable observations in retained evidence storage. Refresh links them and marks relevance; it never edits a past failure into a pass or stores its status in feature records. |

Use the installed base commit/blob from the ledger to compare generator changes with subsequent edits. If a managed section changed on both sides, retain the user's content and emit a proposed resolution plus the conflicting facts. Missing base history is an unresolved ownership conflict, not permission to overwrite. This ledger is optional for existing conformant consumers; first adoption can record a baseline without reformatting the control.

#### Installation and refresh states

These are workflow states recorded in the ledger, not new `control/0` run statuses.

| Starting state or observation | Required action | Result |
|---|---|---|
| No control | Draft the smallest mapped feature, candidate CLI/instructions, pointer, and challenge in isolation | `candidate`; install only the reviewed change within existing edit authority |
| Existing usable verifier/control | Reuse it; propose only missing contract fields, records, or integration | Unchanged when conformant; otherwise a minimal candidate diff |
| Partial setup or interrupted generation | Read ledger and actual hashes; enumerate complete, absent, and conflicting paths; resume only unchanged generated parts | `partial`; preserve partial files and name exact recovery work |
| Candidate challenge passes | Retain proof, clean up, compare checkout state, and record scope | `verified` for that revision and environment; publication follows existing authority |
| Challenge fails or teardown fails | Preserve failing evidence and candidate diff; keep a previously working pointer/version intact | `failed`; fix and rerun before declaring ready |
| Required dependency, runtime, or authority unavailable | Finish permitted static inspection and report the blocked command/prerequisite | `unverified`; no fabricated execution, no automatic rollback of human work |
| Inputs and generated facts unchanged | Reuse matching observation only where relevant source and inputs remain unchanged | No file, order, timestamp, or formatting diff |
| Route/command renamed or added | Propose changed reach information or a new `proposed` feature; stable feature ids survive a route rename | Candidate diff with source citations and affected scenario ids |
| Feature implementation deleted | Flag obsolete reach/bindings; retain confirmed intent and historical id until deletion is decided | `unresolved` if intent survives; explicit reviewed retirement when it does not |
| Command/port contradicts source | Compare named profiles and actual launch behavior; propose the smallest supported fact correction | Measured correction or unresolved discrepancy; never select a port by proximity |
| Human edit conflicts with generated content | Preserve original bytes, name both sources, and offer a patch outside the managed section | `conflict`; no installation until resolved |

The feature's knowledge state changes independently: new inferred behavior is `proposed`; an explicit person-approved intent becomes `confirmed` with its decision reference; conflicting or missing intent becomes `unresolved`. Refresh never treats current code or a green check as a person approving a product change. Preserve the previously confirmed text in the ledger when recording a conflict.

#### Refresh acceptance and unattended operation

The acceptance fixture set must include unchanged input, a route rename, route deletion, a new route, stale command/port facts, a managed-section human edit, interruption after some generated files, and a syntactically valid control whose generated instructions fail. Compare exact diffs and ledger entries. Unchanged refresh produces no diff; drift produces a bounded proposal; conflict and interruption preserve every human byte; a failed control cannot become verified.

At least one generated mapped feature must run from a fresh disposable checkout through install, startup, seed, reach, assertions, report validation, teardown, and reading retained evidence. Run missing-prerequisite and failed-challenge variants as well. A report-shape fixture alone cannot prove generated instructions work.

Optional unattended refresh requires an existing scoped automation authorization, an allowlist of managed paths, known generator/base hashes, isolated execution, and no unresolved intent or ownership conflict. It may produce a candidate PR only when that publication is already authorized. Merge only when explicit authorization covers it and required checks pass; candidate publication alone does not authorize merge. Missing prerequisites leave a clearly unverified proposal when such proposals are within scope; otherwise retain the local result and report the blocked stage. No request for permission is repeated when the session already covers the action.

Deliver stage-loaded references under `skills/leyline/references/`: `inspect.md`, `feature-map.md`, `install.md`, `challenge.md`, `refresh.md`, `control-skill-template.md`, and `recipes/typescript-node.md`. Update package inventories and add acceptance fixtures when those files are implemented. Do not load every reference for a read-only inspection.

### M4: promote observed corrections

The [agent correction contract](agent-correction-contract.md), resolved under [decision 76](https://github.com/frankieramirez/mana/issues/76), owns candidate evidence, routing, rollout, and falsification. Preserve one promotion per pilot:

- Ultima: a narrow AST rule rejects fixed palette literals in component style assertions while preserving dynamic comparisons and installed-token-derived color equality.
- Clankhaven: after M2 provides a runnable control, add the release/check gate. A known failure and a missing prerequisite must block; the restored control and gate must pass without status masking.

The lack of a workflow at the inspected Clankhaven revision is a baseline fact, not a count of recurring incidents. The owner document supplies M4 acceptance; this plan supplies its M2 dependency.

### M5: consume controls in everyday work

Consume the existing pointer and contract; do not copy a CLI into Mana or make one skill depend on another installed skill. Each skill carries the small discovery/evidence rules it needs in its own stage-loaded reference, with any shared copies assigned one canonical owner in the existing asset manifest during implementation.

#### Per-skill input and output

| Workflow | Inputs and minimum interaction | Output and boundary |
|---|---|---|
| Sift, vague report triage | Read the root Control pointer and record paths. Search aliases and reach steps, compare the current route and sources, and inspect prior matching reports. If execution is authorized, use `list --search`, `describe`, and the smallest relevant feature run. | Candidate feature/scenario ids, actual reach path, observed versus inferred behavior, intent questions, and reproduction evidence with source identity. An inferred match remains a candidate until supported. No permission to edit product code or publish is implied. |
| Cast, implementation | Map acceptance criteria to features and scenario ids before changing code. After the final relevant edit, execute `changed --base <resolved-base> --json` when authorized, inspect its selection, and widen to named features or required checks if selection is incomplete. | Each criterion states source-inspected or executed evidence, command/scenario, checked state, status, and claim. Preserve the project's required `Validation:` gate. A control pass covers only its selected checks and cannot replace an unrelated required check. |
| Scan, review | Read claimed run reports and artifacts alongside reviewed head/base/scope and acceptance criteria. Compare expected versus executed cases and inspected source identity. Run a targeted check only when the requested review scope authorizes project execution. | Per-criterion supported, contradicted, or unverified assessment with evidence links. Keep reviewer confidence grounded in evidence. A matching report supports the cases it ran; it does not prove all PR requirements or authorize apply/push. |

Reading the pointer, JSON records, and existing reports is static inspection. Every control command, including `list`, `describe`, and `--plan`, executes project code. A read-only request does not implicitly authorize that execution. An existing instruction to run local checks covers them within that scope; local-only authority still excludes tracker writes, pushes, deployments, and remote publication.

#### Evidence identity and status

Keep the raw control report and link it from existing capture and review records. Use `runId` as the observation identifier, `source.identity.head` and the checked-byte manifest digest as source identity, and check `expected`/`executed` ids as coverage. Record the reviewed head/base/scope alongside the executed state. HEAD equality alone is insufficient when relevant working-tree bytes, dependencies, fixtures, configuration, or runtime inputs differ. Equal patch ids do not establish equal source.

Use [decision 73](https://github.com/frankieramirez/mana/issues/73)'s Augur provenance behavior when browser artifacts are produced: connect the screenshot or recording to the actual source, build/server fixture, command, and observed interaction. Do not infer provenance from a filename or current checkout. A source-linked screenshot establishes what it visibly shows; it does not promote every acceptance criterion to passed.

The existing capture vocabulary stays `passed`, `failed`, `blocked`, and `unrun`, with stale as a relevance label. Preserve raw `incomplete` and `cancelled` in the control report. In the consumer summary, missing prerequisites are blocked; work that did not complete is unrun with its actual timeout/cancellation reason. Preserve any individual failed checks even when the overall run is incomplete. No schema migration is required; consumers add optional evidence references while retaining existing fields. Legacy evidence without enough source identity can be shown as historical evidence, but cannot establish a current pass.

| Condition | Required behavior |
|---|---|
| No Control pointer | Use existing repo guidance, tests, and normal source inspection. Say no project control was discovered. Continue unrelated authorized work; do not invent a successful control check. |
| Broken pointer, malformed records, or incomplete map | Name the exact discovery/coverage gap. Use supported existing checks when authorized. A missing feature mapping is not evidence that nothing changed or nothing needs checking. |
| Missing prerequisite or execution outside scope | Report the blocked or unrun check and the named dependency or authority limit. Continue independent review or implementation. Do not silently install/run code under a static-only request. |
| Report predates relevant edits or inputs | Mark it stale; rerun the affected check when authorized or leave the current claim unverified. |
| Reviewed and executed state differ | Keep both identities visible. No current pass until matching source/inputs are demonstrated or the check reruns against the reviewed state. |
| `sourceChanged` during execution | Overall incomplete; retain observations for diagnosis without treating them as proof of the final checkout. |
| Expected scenario absent, skipped, or zero executed | Incomplete even if the wrapper exits zero. Reject an inconsistent passed report. |
| Some criteria verified, others uncovered | Report each independently. A partially verified feature or PR remains partly unverified; preserve existing commit/shipping gates. |
| Artifact missing or identity unavailable | Keep any independently supported check result with its precise limit; do not claim the missing visual or provenance evidence exists. |

#### Integration acceptance and delivery

First freeze the baseline payload and fixtures. Then implement M2 generation/challenge, M3 reconciliation, and the consumers' shared evidence interpretation. Add Sift discovery, Cast selection/reporting, and Scan claim reconciliation as independently reviewable steps. Run each skill's standalone package checks and existing validation gates. M4's release gate follows the runnable control; it must not be inferred from M5 review prose.

Offline integration cases must cover pointer present/absent/broken, aliases leading to the changed route, incomplete maps, malformed and lying reports, missing browser, stale bytes with the same HEAD, reviewed/executed mismatch, source changes, unknown source identity, partial criteria, and read-only/local-only scopes. Grade the actual commands and final repository state as well as the final response. Successful discovery alone must fail an oracle expecting behavioral proof. Record a failing check even when a screenshot or summary renderer succeeds.

Then run the following bounded paired task families on disposable copies of the pinned Clankhaven pilot. Use two repeats per arm for each family: 3 families x 2 arms x 2 repeats = 12 agent invocations, with a declared timeout and no automatic retries. Failure-state variants remain separate conformance fixtures; they are not extra hidden attempts.

| Task family | Same task for baseline and candidate | Observable outcome |
|---|---|---|
| Vague report | Cold session receives the return-briefing report and crop | Correct feature/route, supported diagnosis, ordinary fixture use, and no invented pass |
| Feature change | A narrow specified briefing behavior change with explicit acceptance criteria | Relevant verification after the last edit, preserved unrelated state, correct per-criterion coverage |
| Review claims | A prepared PR with one valid scoped result and one stale or uncovered claim | Accept supported evidence, reject unsupported completion, preserve review-only scope |

Use the [effectiveness evaluation contract](../specs/effectiveness-evaluation.md) and existing [workflow eval infrastructure](../../evals/workflows/README.md), with a separate study id and invocation budget. Freeze task, source, host/model, tools, authority, environment, and prerequisites across arms; retain initial/final artifacts, command statuses, raw events, and every failed attempt. Keep cases from the same underlying scenario in one source group. Distinguish setup/infrastructure failure from a completed task that fails. Regrades append new judgments without altering original traces.

The assessment host, Codex CLI `0.159.0-alpha.3`, is outside the workflow harness's validated host set. Live measurement requires a supported host or an executed containment and event-contract validation for the new host first. The 12-invocation design is a pending study, not an executed result.

Record avoidable questions separately from genuinely missing product information, repeated setup commands and setup time, escaped seeded defects, false defect reports, total elapsed time, and map/CLI upkeep. Record active reviewer time only if timed; otherwise null. Report full parent/child usage where available; unknown child usage remains null. Never infer model cost from entrypoint bytes. This small paired study can support a bounded integration decision, not a general effectiveness ranking. Repeat or widen only when the observations leave a specific unresolved concern.

## Delivery scope and evidence still owed

The map decisions authorize this Mana specification and their delegated judgment. Consumer changes, dynamic challenges, generation/integration implementation, and live measurement remain explicit delivery work. Do not describe these gates as executed because this document merged. Current external consumer sources were read only.

Retain the source revisions above when implementing, recheck intervening consumer work, and update this plan with actual challenge reports. Required empirical evidence includes a current Ultima conformance run, Clankhaven frozen install/browser readiness, the two mapped scenarios, break/restore, concurrency, cleanup and checkout preservation, refresh fixtures, consumer integration outcomes, and the bounded paired study.

Out of scope: a shared runtime package, a hosted readiness service, production access, a new test DSL, a readiness score, automatic large rewrites, and expansion to the frozen dashboard merely to bypass a blocked hosted check.
