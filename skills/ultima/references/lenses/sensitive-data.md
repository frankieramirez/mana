# Sensitive data lens

## Mandate

Use category `security`. Trace sensitive values across storage and disclosure boundaries, including logs and response serialization. Keep secret values out of audit artifacts. Read shared context, then independently verify the relevant flow.

## Where to look

Follow credentials and personal data from configuration or domain records to consumers. Inspect serializers, log filters and retention or storage policies. Read the surrounding source needed for the trace; replace sensitive literals with [REDACTED] before any output.

## Evidence bar

Establish the confidentiality invariant from an in-scope contract and show the disclosure path. Quote redacted source fragments with accurate file:line references and inspect enclosing filters in control_review. Unknown external secret-store or log-retention policies are coverage limits. Follow the security evidence contract in the dispatch template. Preserve static or runtime evidence status independently of confidence and impact.

## Not a finding

Do not treat synthetic example credentials as live secrets or infer production exposure from their presence. Avoid duplicating a persistence integrity issue when no confidentiality invariant is violated. Separate findings from Architecture or Data & Reliability by root cause, affected boundary and remedy; shared locations alone do not establish duplicates.

## Output

Use the common schema and output contract. Security work becomes a plan with behavioral verification, compatibility and rollback; decisions requiring review retain their prerequisites. Record unexamined surfaces and unavailable external controls as partial coverage.

```json
{
  "lens": "sensitive-data",
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
