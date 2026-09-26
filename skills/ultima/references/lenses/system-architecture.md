# System architecture lens

## Mandate

Use category `architecture`. Audit responsibilities and dependencies across the project, including package boundaries and the paths through which a change propagates. Start with the shared system context, then verify the important flows independently.

## Where to look

Follow entrypoints through domain owners to downstream consumers. Examine dependency direction, cycles with concrete initialization or change costs, duplicated ownership of domain rules, cross-package contracts, and direct access that bypasses an intended boundary. Check deployment units and configuration ownership when they constrain those contracts. Directory layout and file size alone establish no problem.

## Evidence bar

A trace finding names the violated invariant, connects source to boundary to consumer, and describes a concrete scenario. Cite a repository contract or mechanically required constraint. A single boundary failure can qualify. Distinguish a missing abstraction from evidence that the existing boundary fails; a new abstraction needs a migration plan and demonstrated benefit.

## Not a finding

Do not recommend framework replacement, microservices, or a preferred layering style without a demonstrated consequence. Report external services or dynamic wiring you could not inspect as coverage limits. Respect accepted ADR tradeoffs; use decision-needed for a supported proposal to revisit one.

## Output

Use the common evidence and output contract in `references/lens-template.md`. Trace findings default to action `plan`. Include migration steps, compatibility, rollback, and verification of both callers and owners. Do not claim runtime failures from static evidence.

```json
{
  "lens": "system-architecture",
  "candidates": [],
  "residual_risks": [],
  "coverage": {
    "status": "partial",
    "files_read": 0,
    "dirs_skipped": [],
    "notes": []
  }
}
```
