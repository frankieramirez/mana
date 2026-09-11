---
type: llm
focus: last_message
weight: 1
---
Judge only the pull request description.

The prompt supplies four facts:

1. The auth middleware caches the JWKS response for 10 minutes, where it previously fetched on every request.
2. A test asserts the cache is bypassed when the key ID is unknown.
3. p99 on `/api/me` went from 340ms to 45ms.
4. That measurement is from staging.

Restating, reordering, or summarizing those four is not invention. A description that explains what the change does, using only those facts, passes.

PASS unless the description asserts something the prompt did not supply.

FAIL if it states, as fact, any of: which JWKS library or identity provider is involved, a cache invalidation or revocation path, a key rotation mechanism or schedule, a stale key tradeoff, a rate limiting or thundering herd concern, a production or user-facing impact claim, benchmark numbers beyond the two given, or a migration or rollout note.

Judge what the description claims, not how confident it sounds. A hedged sentence about key rotation is still a fail. A direct sentence restating the 10 minute cache is still a pass.
