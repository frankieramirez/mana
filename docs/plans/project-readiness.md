# Project readiness plan

Status: planned, M1 next
Date: 2026-09-24

## Outcome

Give every project a control skill that lets a fresh agent find a feature, run the app, and report honest, revision-bound results. Mana carries a contract, recipes, and a conformance checker. Each project owns its tailored control CLI and feature map, where agents can read and extend them. There is no shared runtime package. A shared library is extracted only when three or more projects carry the same copied code with the same bugs.

Success is measured on real tasks: fewer human interventions, fewer escaped defects, and a fresh session that can reproduce a vague bug report without writing its own helper script. No readiness score.

## Why this shape

This plan started from an exploratory brief and the Lauren Tan talk at Cursor Compile that inspired it. The talk's lessons, and where they land here:

| Lesson from the talk | Where it lands |
|---|---|
| A control skill is two parts: a CLI inside the project, plus a feature map stored with it. The team keeps investing in it as critical infrastructure. | Each project owns both. Mana generates and audits them. |
| The feature map lets agents decode vague reports, such as a cropped screenshot with "???", and records how a user reaches each feature. | The main acceptance test is a vague bug report handed to a fresh session. |
| An automation maintains the feature map. | Refresh can run unattended and open a pull request when the map drifts. |
| Trust ladder: codebase, then static analysis, then rules and bugbot, then skills, then the style guide. | The contract's honesty rules are enforced by a checker instead of prose. |
| The gardener stops the bleeding with a lint rule first and cleans up later. | M4 promotes observed corrections up the ladder. |

The alternatives were weighed and set aside:

- **A shared framework.** Of ultima's roughly 10,500 verification lines, only 3,000 to 4,000 are generic plumbing. The rest is what makes each project hard. A framework extracted from one consumer copies that consumer's shape, and a package in `node_modules` is code agents cannot see or extend.
- **Bespoke systems with no shared rules.** Each project would rewrite rules like "zero tests is not a pass" and drift apart. A fix learned in one project would never reach the next.

## Current state

**ultima** is the reference implementation. `pnpm verify` already provides:

- verbs `list`, `describe`, `component`, `feature`, `changed`, and `release`, with `--plan` and `--json` (`scripts/verify.ts`)
- exit codes 0, 1, 2, 3, 130, and 143 (`scripts/verification/run.ts`)
- a report with run status, source identity, changes made during the run, and prerequisite probes
- a `judge()` where zero executed tests or a skipped expected case is incomplete, never passed
- feature and scenario records under `verification/`, bound to tests by `scenario()` calls found through the TypeScript AST
- controlled failure fakes (`controlled.ts`), a CI gate, and `claude -p` measurement (`scripts/measure/`)

Gaps: `.claude/launch.json` uses port 5174 while the docs and Cursor environment use 5173. `docs/spec/agent-infrastructure.md` still describes shipped commands as planned. The `forge` skill never calls `verify`. Several authoring rules have no enforcement. Features carry no knowledge status.

**clankhaven** is the first new consumer. It has the raw pieces:

- Playwright tests, including the only fake GitHub OAuth and a port 0 launch pattern, both inside `tests/hosted/kingdom.test.ts`
- evidence folders per issue (`evidence/v03/<issue>/`) and requirement tables (`docs/V03_ACCEPTANCE.md`)
- a module boundary test (`tests/v03/purity.test.ts`)

Gaps: no CI, no documented way to start the hosted stack of three processes plus secrets, port 4318 shared by two services, two lockfiles, and `probe/` and `played/` harnesses that point at deleted paths.

**mana** already defines the evidence vocabulary in `skills/reveal/references/capture.md`: passed, failed, blocked, unrun, and stale. It also shows the drift problem this plan targets, because no skill reads the `Proof:` or `Domain docs:` lines that `attune` writes.

## Shape

```
                  Mana skill (reusable, bash and python3 stdlib)
  ┌──────────────────────────────────────────────────────────────────┐
  │ references/contract.md   verbs, exit codes, report and feature   │
  │                          schema, judge and isolation rules       │
  │ references/recipes/      patterns lifted from ultima, clankhaven │
  │ scripts/conform.sh       static and dynamic conformance checker  │
  │ stages: inspect, draft map, ask, install, challenge, refresh     │
  └──────────────────────────────────────────────────────────────────┘
        │ audits and proposes patches        │ generates and audits
        ▼                                    ▼
  ultima `pnpm verify` (reference)     clankhaven control CLI (tailored)
  project-owned code, feature map, control skill, `Control:` pointer
```

The skill's working name is `leyline`. Its description stays plain English about the job: map a repo's features, give agents a way to run and verify them, and check that the setup stays honest.

## Contract v0

Drafted from ultima so the reference is close to conformant from the start. It stays at `control/0` until clankhaven passes; expect a `control/1`.

- **Discovery.** A `Control:` line in the `## Agent skills` block points at the project's control skill. That skill names the command prefix, such as `pnpm verify`.
- **Required verbs.** `list [--search <q>] --json`, `describe feature|scenario <id> --json`, `feature <id>... --json`, `changed [--base <ref>] --json`, and `release --json`. Optional: `--plan`, and `stack up|down` for apps that need running services.
- **Exit codes.** 0 passed. 1 proven failure. 2 usage error or malformed records. 3 incomplete, which covers a blocked prerequisite, zero executed tests, a skipped expected case, or nothing required. 130 and 143 mean cancelled.
- **Report JSON.** At minimum: `contract: "control/0"`, run id, HEAD, source digest, dirty flag, `changedDuringRun`, `status`, `checks[]` (id, scenario ids, argv, status, executed count, reason), `prerequisites[]` (need, present or missing), and `artifacts[]`. Field names follow ultima's report where they already exist. Incomplete maps to blocked or unrun in capture.md terms.
- **Feature records.** id, summary, aliases, `reach` (route, command, or shortcut plus steps), `sourceRoots`, `knowledge` (proposed, confirmed, or unresolved), and scenarios with at least one binding. Records never store verification results.
- **Judge and isolation.** A missing prerequisite is never a pass. Runs use a snapshot or a worktree. Each run owns its ports, and cleanup touches only what the run owns. A source change during a run is reported.

## Milestones

| Milestone | Deliverable | Proven when |
|---|---|---|
| M0 | This plan | Merged |
| M1 | Contract, conformance checker, and its self-tests in mana, run against ultima | Every fake violation fails the checker for the right reason, and the ultima gaps are recorded |
| M2 | The skill tailors clankhaven's control CLI and feature map | Conformance passes, and a fresh session reproduces a vague report |
| M3 | Refresh and full stage references | A second refresh on unchanged inputs produces no diff |
| M4 | Gardener | One written-only rule per pilot becomes a mechanical check |
| M5 | Loop integration and measurement | Before and after numbers on clankhaven |

### M1: contract and checker, proven on ultima

In mana:

- `skills/leyline/SKILL.md` covers the inspect and conformance stages only.
- `skills/leyline/references/contract.md` holds contract v0.
- `skills/leyline/scripts/conform.sh` is bash with embedded python3 stdlib, laid out like `skills/ultima/scripts/ultima.sh`:
  - `static <repo>` reads files and never runs project code. It checks that the `Control:` line resolves, the control skill names its prefix, records parse, ids are unique, `sourceRoots` exist, and every scenario has a literal `scenario(` binding.
  - `report <file>` validates a report against the contract, including that the exit code agrees with the status.
  - `dynamic <repo> --trust` runs project code only with explicit consent. It runs `list`, `describe`, and one `feature`, then three probes. Controlled failure: in a disposable worktree, apply the project's declared break patch, expect exit 1 naming that scenario, restore, and expect exit 0. Zero match: expect exit 3. Parallel: two worktrees at once with no collision.
- `scripts/test-leyline.sh` drives a fake control CLI with modes pass, fail, zero, blocked, malformed, lying exit, and hang, and proves the checker catches each one. `scripts/validate.sh` runs it.
- A `scripts/package-contracts.json` entry, a README section, version 0.33.0, and a CHANGELOG line.

In ultima, which stays read-only: run the checker and record every gap. A small conformance PR adds the `contract` field and `knowledge`, fixes the port mismatch, adds a `Control:` line, and declares a break patch for one scenario. It opens only after Frankie grants push access and says go.

Acceptance:

- Each fake violation mode fails the checker for the intended reason, and the conformant fake passes.
- `conform.sh static` on ultima runs no project code, confirmed by a PATH shim that logs any invocation.
- The ultima findings are recorded as found, followed by the result after the proposed patch.
- `bash scripts/validate.sh` passes.

### M2: tailor clankhaven

Add the draft map, ask, install, and challenge stages, then prepare clankhaven:

- Inspect routes in `src/app/router.tsx`, commands in `src/hosted/cli.ts`, services, tests, and prerequisites such as Chromium and environment variables. Keep facts apart from inferences.
- Draft six to eight features (sign in, kingdom, briefing, pair, credentials, agents, delete, CLI player commands), each with its reach path and knowledge status.
- Ask only about intent the code cannot settle.
- Install as a reviewed diff: a control CLI built from the recipes, with a stack launcher that reuses the fake OAuth and port 0 pattern from `kingdom.test.ts`; `scenario()` wrappers on existing tests; `skills/clankhaven-control/SKILL.md`; and the `Control:` pointer.

Acceptance:

- `conform.sh static` and `dynamic` pass on clankhaven.
- A fresh `claude -p` session in a worktree receives "came back and the briefing is empty ???" and a cropped screenshot. It finds the briefing feature, starts the stack, reproduces the problem, and cites the report without writing its own script.
- A missing Chromium makes the run incomplete with exit 3.
- One conformance case learned here ships in a skill update, and rerunning it against ultima flags or confirms ultima with no copied code.

### M3: refresh

Refresh reconciles the map with the code. It proposes new routes and commands, repairs stale references, and flags control skill facts that contradict configuration, with ultima's port mismatch as the first case. It never rewrites confirmed intent to match current code. Unchanged inputs produce no diff. It can run unattended and open a pull request.

Also in M3: stage-loaded references (`inspect.md`, `feature-map.md`, `install.md`, `challenge.md`, `refresh.md`, `control-skill-template.md`, `recipes/typescript-node.md`) and workflow eval cases for map lookup, blocked versus passed, and an unchanged refresh.

### M4: gardener

Inputs are observed corrections: repeated review comments, rules in CLAUDE.md, AGENTS.md, or skills that nothing enforces, and docs that contradict configuration. Each finding carries a stable id, the evidence, its current rung on the trust ladder, the proposed promotion, the smallest intervention, and an acceptance check. Severity and evidence level stay separate. Dismissed findings stay on record with their reasons, in `docs/agents/readiness.md`.

One promotion per pilot: in ultima, "no test asserts a color value" becomes a `packages/analysis` rule with an invalid fixture. In clankhaven, a CI workflow runs `release` and the gate.

### M5: loop integration

When a `Control:` line exists, `sift` uses the map to decode vague reports, `cast` runs `changed` and cites the report, and `scan` checks a pull request's claims against the report. Measure before and after on clankhaven with ultima's `scripts/measure` protocol, then revisit the extraction rule and the skill's name.

## Measurement log

Record each task as it runs.

| Date | Agent and model | Revision | Task | Completed | Human interventions | Fresh-session verify outcome | Notes |
|---|---|---|---|---|---|---|---|

Track across tasks: escaped defects, audit false positives, time spent restoring environments, and upkeep minutes for maps and CLIs.

## Risks

- **The contract is too tight or too loose.** v0 comes from one implementation. Clankhaven is the test.
- **Clankhaven's hosted stack resists automation.** The fake OAuth already exists. If the stack stays unreliable, scope M2 to the v0.3 dashboard.
- **Tailored CLIs cost too much per project.** Measure M2's effort. If it is high, recipes grow into fuller templates, and extraction still waits for the three-project rule.
- **Map upkeep outweighs the benefit.** The measurement log tracks it.

## Permissions

Mana work happens on this plan's branch. ultima and clankhaven stay read-only until Frankie grants push access; after that, changes go on new branches with no push or pull request without a go-ahead.

## Out of scope for v1

A shared runtime package, a framework, a hosted service, a new brand, npm publishing, a test DSL, a readiness score, automatic large rewrites, production access, and creating tracker issues without an explicit ask.
