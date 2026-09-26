# Build and deployment lens

## Mandate

Use category `performance-delivery`. Trace the project's actual build and release contract from its entrypoint through the artifact or release boundary to the consuming runtime. Read package boundaries, test entrypoints and CI configuration. Verify deployment topology and release or rollback contracts rather than treating discovered filenames as connected steps.

## Where to look

Read the shared context, then follow the in-scope execution or release paths to their consumers. Treat profile filenames as leads until source inspection verifies the relationships.

## Evidence bar

Use trace evidence and explain the connected path in `flow`. Quote the release contract in `invariant_source` as file:line. Inspect artifact production and consumption, consequential release gates, migration ordering and rollback compatibility where relevant. Establish which gate is required and how the shipped path bypasses it. A missing CI file alone is not a defect.

Trace enclosing jobs, dependencies and external handoffs before declaring a release-order flaw or an ineffective rollback. If an external deployment step cannot be inspected, record it in `unavailable_scope` and residual_risks. Do not invent its order or turn uncertainty into a demonstrated defect. A deliberate manual release with documented checks can be valid.

## Not a finding

Never invoke deployments, execute migrations, modify CI, install tooling or run project build/test commands during audit discovery. Read existing executed evidence when supplied. Execution and changes need a separately scoped path.

## Output

Follow `references/lens-template.md`. Findings use action `plan`. Propose ordered remediation with compatible old and new consumers, rollback preconditions and bounded verification. `verification` describes proposed acceptance checks for artifact identity or release ordering, including interruption and rollback where relevant; reserve `runtime_evidence` for checks already executed. Missing plan details remain explicitly incomplete.

Return `lens: delivery`, candidates and residual_risks. Coverage states files_read, status and notes. Use `absent_scope` for verified absent CI or release surfaces and `unavailable_scope` for inaccessible configuration and external steps. A completed specialist can still have partial scope coverage.

```json
{
  "lens": "delivery",
  "candidates": [],
  "residual_risks": [],
  "coverage": {
    "status": "partial",
    "files_read": 0,
    "dirs_skipped": [],
    "absent_scope": [],
    "unavailable_scope": [],
    "notes": []
  }
}
```
