# Performance lens

## Mandate

Use category `performance-delivery`. Trace avoidable work from a caller through a costly boundary to the affected consumer. Inspect consequential execution paths before churn. Consider repeated queries, unbounded processing, expensive client delivery and invalid cache assumptions only where the actual flow supports them.

## Where to look

Read the shared context, then follow the in-scope execution or release paths to their consumers. Treat profile filenames as leads until source inspection verifies the relationships.

## Evidence bar

Use trace evidence and explain the connected path in `flow`. Quote the source of the cost constraint in `invariant_source` as file:line. State the supported impact and reach independently of confidence. A complete proof of repeated work can establish a static defect without establishing its runtime cost.

Set `cost_assessment` to `source-hypothesis` and `evidence_status` to `static` unless existing executed evidence establishes a bottleneck attributable to this path. Never invent latency, throughput, memory, bundle size, production load or benchmark improvements. A loop alone is insufficient: inspect bounds, batching, caches, enclosing callers and accepted tradeoffs. A justified bounded operation belongs in coverage.

For `measured-bottleneck`, use `evidence_status: runtime`, `runtime_evidence`, and a `measurement` object containing file, line, verbatim quote, command, revision, environment, workload, result and attribution to the traced boundary. Read the existing result and disclose limits, including stale revisions or synthetic workloads. The artifact's existence alone does not prove attribution or production behavior. Unavailable or unrelated evidence remains a source hypothesis with bounded proposed verification.

## Not a finding

Do not run benchmarks or load tests, install profilers, start servers, build bundles or contact production. Measurements require a separately scoped execution path. Reading existing logs is inspection; a suggested check is not an executed check.

## Output

Follow `references/lens-template.md`. Findings use action `plan`, with ordered remediation, compatibility and rollback details. `verification` is a proposed behavioral or measurement acceptance criterion: state the bounded workload, the comparison or operation-count assertion, and the result that would confirm the remedy. Leave unsupported numeric budgets unset. Missing planning details remain incomplete.

Return `lens: performance`, candidates and residual_risks. Coverage states files_read, status and notes, with `absent_scope` for verified absent surfaces and `unavailable_scope` for inaccessible measurements or execution paths. Specialist completion does not establish complete scope coverage.

```json
{
  "lens": "performance",
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
