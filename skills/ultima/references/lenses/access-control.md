# Access control lens

## Mandate

Use category `security`. Trace authentication and authorization across trust boundaries. Verify which identity reaches each consumer and where object ownership, tenant scope or privilege is enforced. Read shared context, then independently verify the relevant flow.

## Where to look

Start with authentication and authorization surfaces in the profile. Follow route registrations through middleware and policy checks to object reads or privileged actions. Inspect the authenticated principal and resource scope together; authentication alone does not establish ownership. Examine alternate callers only within scope.

## Evidence bar

An invariant may come from an explicit access contract or an existing policy implementation. Quote the enclosing route registration or middleware in control_review. A handler without a local guard is safe when the enclosing policy enforces the same invariant. Missing external gateway configuration stays an unresolved condition. Follow the security evidence contract in the dispatch template. Preserve static or runtime evidence status independently of confidence and impact.

## Not a finding

Do not infer public exposure from an internal route or claim a bypass without following the enclosing controls. Accepted access-policy decisions remain accepted unless new evidence justifies decision-needed. Separate findings from Architecture or Data & Reliability by root cause, affected boundary and remedy; shared locations alone do not establish duplicates.

## Output

Use the common schema and output contract. Security work becomes a plan with behavioral verification, compatibility and rollback; decisions requiring review retain their prerequisites. Record unexamined surfaces and unavailable external controls as partial coverage.

```json
{
  "lens": "access-control",
  "candidates": [],
  "residual_risks": [],
  "coverage": {
    "status": "partial",
    "files_read": 0,
    "dirs_skipped": [],
    "notes": [],
    "unavailable_controls": []
  }
}
```
