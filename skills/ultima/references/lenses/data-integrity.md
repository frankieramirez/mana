# Data integrity lens

## Mandate

Use category `data-reliability`. Trace consequential writes and reads across the project's persistence and messaging boundaries. Establish what must remain true before deciding that the implementation violates it.

## Where to look

Follow validation through mutations to consumers. Examine transaction boundaries, idempotency, duplicate delivery, concurrent updates, cache ownership, schema compatibility, and migration ordering where those mechanisms exist. Identify the owner of each invariant and inspect alternate paths that could enforce it, including database constraints and shared middleware.

## Evidence bar

A useful scenario states the triggering inputs or interleaving and the incorrect persisted or consumed result. Quote the source, boundary, and consumer. A single non-atomic write sequence can qualify when the invariant and failure path are supported. Absence of a visible transaction in one function is insufficient until the enclosing unit of work is checked.

## Not a finding

Do not infer corruption in production or invent load and concurrency assumptions. Record uninspected database guarantees, external consumers, and migration history as coverage limits. Classify runtime evidence only when it actually exists.

## Output

Follow `references/lens-template.md`. Trace findings use action `plan` and include compatibility across old and new readers or writers, migration steps, rollback constraints, and a verification scenario that would expose the invariant violation. A destructive or irreversible migration is never an immediate audit fix.

```json
{
  "lens": "data-integrity",
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
