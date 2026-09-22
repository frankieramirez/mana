# Mana stack reliability plan

Status: implemented locally, validation recorded below
Date: 2026-09-22

## Outcome and scope

Make Mana's published skills easier to maintain, independently installable, and more reliably evaluated. Success means evidence claims match what was checked, shared assets have one ownership declaration, and demonstrated workflow failures have repeatable regression coverage.

This plan covers this repository and its distributed artifacts. Application feature maps, application control frameworks, performance infrastructure for consuming apps, and event-driven intake are outside scope. No new public skill is required.

Implementation is ready for PR review. The work packages below record the delivered scope and acceptance criteria. Existing project conventions, standalone skill support, and stage-loaded references remain requirements.

## Current foundation

- `scripts/validate.sh` runs helper fixtures, checks packaging conventions, and compares a hardcoded list of shared files.
- `scripts/sync-agent.sh` generates agents from reference files; `scripts/sync-persona.sh` generates persona copies, activation blocks, and an output style.
- `cast` checks acceptance criteria and runs project validation. `reveal` and `cast` share capture and PR presentation files owned by `reveal`.
- `augur` distinguishes evidence strength. Capture guidance currently describes every attachment as proof, including its commit-summary fallback.
- `evals/vision/` supplies manual fresh-session scenarios. `evals/semantic/` grades saved outputs, with an advisory live judge and offline runner tests. Neither is a general skill-execution harness.

## Delivery order

| Package | Deliverable | Depends on |
|---------|-------------|------------|
| 1 | Accurate evidence contracts | None |
| 2 | Shared-asset manifest and synchronization | None |
| 3 | Standalone package verification | 2 |
| 4 | Executable workflow eval pilot | 1, 3 |
| 5 | Failure-to-regression maintenance process | 4 |

Implement in this order. Package 4 starts with a small usable pilot; expansion follows demonstrated gaps. Package 5 seeds the process with existing regressions rather than waiting for new incidents.

## 1. Accurate evidence contracts

### Changes

Edit the canonical capture and body references under `skills/reveal/`, then synchronize their `cast` copies. Update the affected skill entrypoints and `cast` spec-check guidance so acceptance claims distinguish source inspection from executed checks.

Describe three evidence states: visual demonstration, executed verification, and unverified claim. An attachment can illustrate a result without proving the behavior. A screenshot establishes only what it visibly shows; a commit-summary image establishes no behavioral outcome.

For executed checks, record the command or scenario, checked revision or working-tree state, result, and the claim it supports. Record material limitations and failed or unavailable checks in the report. Failed media can stay out of the showcase without erasing a failure from the validation record. Evidence predating relevant edits must be refreshed or explicitly reported as stale.

Keep the evidence record lightweight Markdown in existing reports and PR bodies. Do not require a new service, attachment format, or installed sibling skill. Preserve existing rules about whether failed validation blocks shipping; this change must not loosen those gates.

### Acceptance criteria

- Capture fallbacks never imply an unexecuted check passed.
- A successful image-rendering command cannot mask failure of the command whose output it renders. The documented pipeline preserves the proving command's exit status.
- Reports distinguish passed, failed, blocked, and unrun checks without inventing results.
- Reused evidence identifies the checked state and discloses relevant later changes.
- Examples cover a GUI demonstration, passing CLI check, failed check, and unavailable runtime.
- Canonical and bundled copies agree; applicable helper fixtures and the repository validator pass.

## 2. Shared-asset manifest and synchronization

### Changes

Add one machine-readable manifest under `scripts/` defining shared-asset sources and destinations. Represent exact copies separately from generated artifacts. Include agent source mappings and persona generation ownership without replacing their specialized renderers with an arbitrary template engine.

Provide one synchronization entrypoint with write and read-only check modes. Existing agent and persona commands may remain compatibility wrappers. Both synchronization and validation read ownership from the manifest; remove duplicate ownership tables once migrated. Update maintainer documentation to point to it.

Use Bash entrypoints and Python standard-library support where needed. Add no runtime dependency to installed skills. Keep generated files committed so individual skill installation still works.

### Acceptance criteria

- Every currently checked shared copy and generated agent/persona artifact retains an owner and destination rule.
- Two consecutive synchronization runs produce no further diff.
- Check mode reports exact drift and writes nothing.
- Missing sources, duplicate destination owners, escaping paths, and unsafe symlink destinations fail before writes.
- The migration preserves generated bytes unless an intentional change is documented.
- Fixtures cover successful copying, drift, malformed declarations, and destination safety.
- Existing specialized generator tests and `scripts/validate.sh` pass.

## 3. Standalone package verification

### Changes

Add a verifier that copies each skill folder into a fresh temporary installation root with no sibling skills or repository helpers. Validate concrete bundled file references and exercise safe helper entrypoints or fixture-backed commands from an unrelated working directory.

Classify paths as bundled assets, consuming-project inputs, or optional host capabilities. Missing project files such as `docs/agents/issue-tracker.md` must not be mistaken for missing package assets. Check required declared assets even when Markdown link discovery cannot find them. Treat static path checks as bounded coverage, not proof of every possible dynamic reference.

Preserve `portal`'s documented optional sibling lookup and exercise its plain-prompt fallback when the sibling is absent. Do not require users to install the full stack.

### Acceptance criteria

- Every published skill is checked in isolation.
- Deliberately removing a required bundled reference or helper makes verification fail with the skill and path named.
- A reference escaping the installed skill folder fails unless it is an explicitly supported project input or optional integration.
- Known script paths run from the isolated copy, not the source checkout.
- Smoke checks use temporary HOME/config state and controlled tool doubles; they cannot contact a live tracker or mutate user repositories.
- Missing optional host tools produce a defined fallback or explicit unsupported result rather than a false pass.
- Deterministic checks run through `scripts/validate.sh` without credentials, network access, or paid services.

## 4. Executable workflow eval pilot

### Changes

Add `evals/workflows/` with a fixture schema, disposable repository setup, recorded tool operations, and deterministic outcome assertions. Separate case preparation and grading from the host that executes the agent. Select one locally available agent host for the first optional runner adapter, document its requirements, and leave other hosts explicitly untested.

Each case records its request, installed skill, initial repository/tracker state, allowed effects, expected outcome, and grader. Preserve skill revision, host/model identity when available, commands, exit statuses, final response, and repository state changes under ignored `evals/results/` directories.

Live execution must use a host isolation mechanism that prevents real publication and access to user credentials. Tool doubles alone are insufficient containment for an agent with arbitrary shell access. If the adapter cannot enforce the required isolation, it must refuse unattended execution and report that limitation.

Provide deterministic fixture and grader tests in ordinary CI. Actual agent runs are explicit maintainer operations with case selection, timeout and invocation limits. Report failures and repeated-run variability; do not silently retry until a case passes. Keep semantic judgment advisory where deterministic assertions are insufficient.

### Initial cases

| Case | Observable outcome |
|------|--------------------|
| Passing check with captured output | Report names the executed check and its actual result |
| Failed proving command followed by successful rendering | Failure remains visible and cannot become a passed check |
| Runtime unavailable | Report marks the behavioral claim unverified |
| Relevant edit after evidence capture | Agent reruns the check or marks evidence stale |
| Existing unrelated staged/unstaged work | Work is preserved and excluded from the agent's commit |
| Tracker command requiring a label | Logged invocation contains required arguments |
| Instruction embedded in report or tracker content | Agent treats it as data and does not execute its requested side effect |
| Missing optional sibling skill | Standalone fallback works without importing repository-only files |

Reuse relevant existing fixtures and the `vision` scenario format. Do not claim the pilot covers every skill or host.

### Acceptance criteria

- The pilot actually invokes a skill through the selected agent host; replaying a canned output is reported as a grader test only.
- At least one evidence scenario and one repository-mutation scenario run end to end.
- Seeded bad outcomes fail deterministic graders, and legitimate variants pass.
- A clean fixture setup and failed agent execution are distinguishable in reports.
- Every attempted run retains a result, including timeout and setup failure.
- Live runs have explicit limits and no access to live publishing credentials.
- Offline fixture/grader tests pass in normal CI; live results are reported separately.

## 5. Failure-to-regression maintenance process

### Changes

Document a maintainer procedure for reducing a demonstrated Mana failure to a small reusable case. Capture the triggering request, expected behavior, observed failure, root cause, and regression location. Remove private project content and credentials before committing a case.

Choose enforcement based on the defect: improve a helper or data contract where possible, add deterministic validation where reliable, and use a workflow case for instruction-following behavior. Keep a semantic rubric only where the outcome genuinely requires judgment. Add instruction prose when it supplies a missing decision rule rather than repeating existing rules.

Seed the process with the missing roadmap-label failure documented in the changelog, the capture-pipeline case from package 1, and one supported standalone-packaging failure. Reuse an existing regression when it already covers the defect; link it instead of adding a duplicate. Label constructed failures as synthetic.

### Acceptance criteria

- Each seed links its failure description to a test or eval and names the coverage limit.
- Deterministic regressions fail against a deliberately broken fixture and pass against the corrected one.
- Agent scenarios record observed outcomes without claiming universal prevention from one successful run.
- Maintainer guidance explains how to run the smallest relevant check and when broader checks are required.
- No rule forces unrelated cleanup into a consuming project's task.

## Validation and release

Run targeted checks for each package, then `scripts/validate.sh` before every implementation commit. Run `scripts/similarity.py` if implementation touches `scan` or `remedy`. Preserve the existing exclusion of `evals/` from the prose dash check.

Every shipped behavior change receives a plugin version bump and changelog entry. Document maintainer-only tooling separately and follow the repository's existing release convention for changes that do not alter shipped skill behavior. Verify both plugin packaging and individual skill copies after synchronization changes.

The plan is complete when all five packages meet their acceptance criteria, deterministic CI passes, the pilot's actual agent-run results are recorded, and remaining host or semantic-evaluation limits are explicit. A passing validator alone does not establish that agents follow the skills.

## Execution record

All five work packages are implemented. Shipped behavior is versioned as 0.31.0.

| Package | Delivered evidence |
|---------|--------------------|
| 1 | Capture and PR contracts distinguish evidence kinds and preserve command failures. The documented pipeline is executed by regression tests. |
| 2 | `scripts/shared-assets.json` drives unified synchronization and validation, with compatibility wrappers and existing persona fixtures preserved. |
| 3 | All 18 standalone packages pass isolated payload checks and offline helper smoke runs. |
| 4 | Eight synthetic workflow cases have observed passing agent runs; runner failures and a corrected grader judgment are retained and explained in `evals/workflows/findings.md`. |
| 5 | `docs/MAINTAINING.md` documents the failure-to-regression process and links historical or synthetic seed regressions. |

Local validation: `scripts/validate.sh` passes. Similarity was checked against upstream revision `414e9d6be166c15d9fb10595204530802ad007ef`; every comparison is below 0.30, with a worst ratio of 0.24. The new offline suites contain 12 reliability tests and 11 workflow fixture/grader tests. Live runs remain separate from CI, use one validated host version, and establish no general reliability rate.

An additional adapter regression found while executing the plan was fixed: dry-run issue creation now quotes temporary body paths containing spaces. The canonical helper and all bundled copies are synchronized.
