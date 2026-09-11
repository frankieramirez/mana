---
type: llm
focus: last_message
weight: 1
---
Judge only the pull request description.

The prompt supplies three facts and no reasoning. Anything beyond those three facts is the model's inference.

PASS if the description asserts nothing the prompt did not supply.

FAIL if it states, as fact, any of: why the cache is bypassed for unknown key IDs (for example a key-rotation rationale), which JWKS library or identity provider is involved, a cache invalidation or revocation path, a tradeoff about stale keys, a rate-limiting concern, benchmark numbers beyond the two given, or a migration or rollout note.

An inference is still a fabrication when it is plausible. This grader is about whether the description claims more than it was told.
