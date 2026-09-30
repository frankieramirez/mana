# Reviewer selection

Load at Stage 3. Paths beginning with `references/` are relative to the skill directory.

## Stage 3: Select reviewers

Read the diff and file list. Selection is judgment about what the diff actually contains, never keyword matching; the Stage 1b signals are prompts to look, never automatic selection. Persona prompts live in `references/personas/`, one file per reviewer identifier.

**Always on:**

| Reviewer | Selected when |
|----------|---------------|
| `protection-warrior` (correctness) | Every review |
| `lore-bard` (existing feedback) | A PR was resolved in Stage 1. Not conditional on comment count; it verifies its own input and returns empty if there is genuinely nothing. |

**Conditional:**

| Reviewer | Selected when the diff touches |
|----------|-------------------------------|
| `retribution-paladin` (project standards) | At least one applicable standards file exists (Stage 3b) |
| `marksmanship-hunter` (testing) | Test files, fixtures, mocks, or harness behavior; or meaningful runtime behavior changed with no corresponding test work. Behavioral triggers: new or changed branches, state mutation, API or control-flow behavior, error handling. Production-file presence alone does not select it. |
| `subtlety-rogue` (security) | Auth, permission checks, public endpoints, user input handling, secrets |
| `fire-mage` (performance) | Query shape, algorithmic complexity, loop-heavy transforms, batching or fan-out, cache policy with real resource impact. Async code alone does not select it. |
| `demonology-warlock` (API contract) | An externally consumed boundary changes: routes, request or response shapes, serializers, published event schemas, versioning, or a public package signature with evidenced callers. A new exported symbol inside one module is not enough. |
| `restoration-shaman` (reliability) | Error handling, retries, timeouts, background jobs, async handlers, health checks |
| `unholy-death-knight` (data migration) | A migration or schema artifact is in the diff: `db/migrate/*`, `db/schema.rb`, `structure.sql`, Alembic / Flyway / Liquibase paths, Prisma migrations, or an explicit backfill script. **Not** model-only or query-only changes. |
| `balance-druid` (maintainability) | Large or structural work: substantial refactor, new abstractions, file moves, coupling or type-boundary changes, or 200+ executable changed lines |
| `havoc-demon-hunter` (adversarial) | 50+ executable changed lines; or auth, payments, persistence writes, event publication, retry or concurrency semantics, external APIs; **or a silent-pass verification mechanism of any size** |
| `windwalker-monk` (frontend races) | Async UI flows, DOM event wiring, timers, animations, effect lifecycles, or state transitions with race potential |
| `augmentation-evoker` (agent-native) | Agent tools, MCP servers, tool schemas, system-prompt construction, or a user-facing action or data path in a codebase that has an agent surface. Prose-only edits to a prompt select Discipline Priest, never this. |
| `discipline-priest` (instruction prose) | Markdown or config a model reads as instructions: `SKILL.md`, prompt files, agent definitions, `CLAUDE.md`, `AGENTS.md`, rules files. Selected on any such change regardless of line count. |

**Silent-pass verification mechanisms.** When the change *is* a verification mechanism (CI or CD gating logic, merge-blocking checks, build or deploy steps, coverage or lint gates, test infrastructure or mocks that could mask production), its risk is not blast radius, it is fidelity: it can go green while the real thing is red. Select `havoc-demon-hunter` regardless of size. The question is "if this is wrong, does it fail loudly or pass silently?" This fires on the *mechanism*, not on ordinary per-feature assertions.

**Instruction-prose files** (Markdown skills, prompts, JSON config) are product code, but runtime-focused reviewers add little. For a diff that only changes prose, select `discipline-priest` and skip `havoc-demon-hunter` unless the prose governs auth, payments, data mutation, or is itself a verification mechanism. Count only executable lines toward thresholds; prose lines are reported separately by Stage 1b.

### Stage 3b: Discover project standards paths

Glob `**/CLAUDE.md` and `**/AGENTS.md`, then filter to those whose directory is an ancestor of at least one changed file (a root file governs the whole checkout; `packages/ui/CLAUDE.md` governs everything under it).

- One or more paths: select `retribution-paladin` and pass the path list in a `<standards-paths>` block. The persona reads the files itself.
- Empty successful search: do not select it; record `project standards: not run (no applicable standards files)` in Coverage.
- Search failed or scope is uncertain: fail closed: select it and state the uncertainty.

### Stage 3c: Small-diff lite path

`depth:full` hard-disables this gate.

Collapse to a lite roster only when **all** hold: Stage 1b reported `lite_eligible: true` (fewer than 40 executable lines, no risk words, no migration, frontend, API, test, or verification signal); your own read of the diff finds no content-based risk (auth, payments, data mutation, external API, secrets, deserialization, crypto, concurrency, filesystem or process execution); Stage 3b completed; and no conditional reviewer other than `retribution-paladin` or `discipline-priest` was selected. `lite_eligible` is necessary and never sufficient. Any uncertainty resolves to the full roster: a 12-line auth change still needs it.

Lite roster: `protection-warrior`, `lore-bard` when a PR exists, `retribution-paladin` when applicable, and `discipline-priest` when the diff is prose-only. Announce the actual roster and note it in Coverage.
