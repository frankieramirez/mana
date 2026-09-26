# Failure recovery lens

## Mandate

Use category `data-reliability`. Trace how important operations behave when dependencies fail and how the project recovers. Focus on supported failure scenarios at system boundaries.

## Where to look

Follow an operation from entrypoint through the failing boundary to its consumer or recovery handler. Examine timeout and cancellation propagation, retry ownership and limits, partial completion, queue acknowledgments, checkpoint or resume behavior, cleanup, and shutdown where applicable. Inspect enclosing middleware and caller policies before claiming a missing handler.

## Evidence bar

Explain the invariant and the specific failure sequence: for example, a consumer acknowledges work before the durable result and cannot recover after interruption. Quotes must connect that sequence, including the responsible boundary. Existing recovery tests can establish intended behavior; they are not production instances.

## Not a finding

Static evidence describes possible behavior, not incident frequency or measured reliability. Do not prescribe infrastructure absent a supported need. Disclose external retry policies or deployment behavior that could not be inspected. General wishes for more logging are not findings; connect a recovery blind spot to a concrete operation and consequence.

## Output

Follow `references/lens-template.md`. Trace findings use action `plan`, with remediation, compatibility, rollback, and a bounded failure-injection or recovery verification plan. Do not execute fault injection during the audit.

```json
{
  "lens": "failure-recovery",
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
