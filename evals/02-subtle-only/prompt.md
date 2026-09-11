---
max_turns: 8
timeout_seconds: 180
allowed_tools: [Skill]
model: opus
runs: 3
---
Make this read like a person wrote it. Return only the rewritten paragraph, with no notes on what you changed.

The migration of the billing records was performed by the nightly job. Validation of each record is carried out before insertion, and any record that fails validation is written to a quarantine table for later inspection. The new index significantly improves the speed of the reconciliation query. A decision was made by the team to retain the legacy table until the end of the quarter.
