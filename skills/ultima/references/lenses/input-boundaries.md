# Input boundaries lens

## Mandate

Use category `security`. Follow untrusted inputs into interpreters and privileged consumers, identifying the boundary at which the input must become constrained. Read shared context, then independently verify the relevant flow.

## Where to look

Start with requests, uploads or command inputs. Follow validation and transformations through parsers, subprocess argument handling, file access and rendering sinks. Verify escaping, parameterization and framework guarantees in their actual calling context.

## Evidence bar

Connect attacker-controlled source to a concrete consumer with the sourced invariant and qualified impact. Quote the enclosing validation or registration inspected. A dangerous-looking sink without a reachable untrusted value is insufficient. Source inspection cannot establish an executed exploit. Follow the security evidence contract in the dispatch template. Preserve static or runtime evidence status independently of confidence and impact.

## Not a finding

Do not raise generic injection warnings from a function name, recommend sanitization without a consumer contract, or duplicate an authorization defect whose remedy belongs to access control. Separate findings from Architecture or Data & Reliability by root cause, affected boundary and remedy; shared locations alone do not establish duplicates.

## Output

Use the common schema and output contract. Security work becomes a plan with behavioral verification, compatibility and rollback; decisions requiring review retain their prerequisites. Record unexamined surfaces and unavailable external controls as partial coverage.

```json
{
  "lens": "input-boundaries",
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
