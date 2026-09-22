# Maintaining Mana

Keep regressions reproducible and keep each distributed skill self-contained. These commands operate on this repository; installed skills do not invoke the maintainer tooling.

## Shared assets

`scripts/shared-assets.json` owns exact-copy relationships and generated agent/persona destinations. Edit the canonical source listed there, then run:

```bash
bash scripts/sync-assets.sh
bash scripts/sync-assets.sh --check
```

The first command renders all changes after validating declarations and destinations. The second reports drift without writing. `sync-agent.sh` and `sync-persona.sh` remain scoped compatibility wrappers backed by the same manifest and specialized renderers. New agent declarations still need their entry in `.claude-plugin/plugin.json`.

Exact copies preserve source permissions. Generated persona activation blocks retain the entrypoint's surrounding bytes. All destinations are validated before writes; an I/O failure during writing can still interrupt the batch, so rerun synchronization after resolving it.

## Standalone packages

`scripts/package-contracts.json` records each skill's required payload and audited smoke entrypoints. When intentionally adding or removing a bundled file, update that skill's inventory. This inventory is separate from ownership: a file can be required by one package without being shared.

```bash
python3 -B scripts/verify_packages.py
```

The verifier copies each skill into a temporary isolated installation, checks required files and concrete bundled references, then runs helpers from an unrelated working directory with temporary configuration and controlled tool doubles. Help entrypoints, a renderer example, and a clean conflict-state fixture execute offline. This does not exercise every helper subcommand or prove that agents follow the instructions.

Links to consuming-project templates are explicit, document-specific `project_links` exceptions. Review an exception before adding it; do not automatically exempt every missing link. Template paths with unresolved placeholders require the explicit payload inventory. Optional host capability fallbacks need a behavioral fixture when they cannot be checked structurally. Portal's absent-sibling behavior is covered by the workflow pilot.

## Turn a demonstrated failure into a regression

1. Reduce the triggering request and initial state to a small fixture. Record expected behavior separately from observed behavior. Remove credentials and private project content. Label constructed examples synthetic.
2. Identify the failure's owner. A helper defect belongs in a helper fixture. A missing package asset belongs in package verification. A decision error belongs in a workflow scenario. Use a semantic rubric only when the outcome needs judgment.
3. Check existing tests before adding a new one. Link coverage that already demonstrates the same defect. Exercise the broken form and the corrected form; include a legitimate variation so the check does not merely recognize one wording.
4. Make the narrow correction. Prefer a helper or data-contract fix when it removes the failure path. Add instruction prose when it supplies a missing decision rule. Record limits instead of claiming universal prevention from a successful agent run.

For workflow cases, the exact request, setup, allowed effects, and outcome assertions live in `evals/workflows/`. The runner preserves unsuccessful attempts. Grader fixes can regrade saved artifacts without another model invocation; original judgments remain available.

## Seed regression registry

| Failure | Evidence and regression | Coverage limit |
|---------|-------------------------|----------------|
| Roadmap creation omitted its required label | Historical fix documented in changelog 0.29.1. `scripts/test_reliability.py` tests labelled and unlabelled calls to the actual adapter; workflow case `roadmap-label` checks agent invocation. | Dry-run argument handling does not establish live tracker writes. |
| Successful rendering masked a failing check | Synthetic reproduction of the former documented pipeline in `scripts/test_reliability.py`, plus workflow case `capture-failure`. | The deterministic test executes the documented command shape. Actual agent outcomes are recorded separately. |
| Standalone package loses a required file | Synthetic deletion in `scripts/test_reliability.py` fails even after links to that file disappear. | Inventory and static paths cannot prove all dynamically constructed references. |

## Choose checks proportional to the change

```bash
# Shared assets, capture exit statuses, and package failure fixtures
python3 -B -m unittest discover -s scripts -p 'test_reliability.py'

# Persona rendering, including malformed input and symlink safety
bash scripts/test-persona.sh

# Workflow fixtures and graders, without an agent
python3 -B -m unittest discover -s evals/workflows -p 'test_*.py'

# Full required offline validation before committing
bash scripts/validate.sh
```

Run `scripts/similarity.py` when touching `scan` or `remedy`. Preserve the validator's existing exclusion of `evals/` from the prose dash check. Actual agent runs are optional maintainer commands described in the workflow README; they consume account usage and are outside normal CI.

Every shipped behavior change gets a plugin version bump and changelog entry. Maintainer-only tooling is documented without implying a new runtime dependency for consumers. Keep any remote CI results distinct from local checks.
