---
type: llm
focus: last_message
weight: 1
---
Judge only the rewritten paragraph.

PASS only if the rewrite asserts the same facts as the original:

1. Records are validated before insertion, not after.
2. Records that fail validation go to a quarantine table for later inspection.
3. The team is keeping the legacy table until the end of the quarter, and is not dropping or migrating it.
4. The index is new and it made the reconciliation query faster.

FAIL if any of these is reversed, dropped, or replaced with a different claim.
