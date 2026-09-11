---
max_turns: 8
timeout_seconds: 180
allowed_tools: [Skill]
model: opus
runs: 3
---
Write the PR description for this change. Return only the description, with no notes or caveats afterwards.

The auth middleware now caches the JWKS response for 10 minutes instead of fetching it on every request. I added a test that asserts the cache is bypassed when the key ID is unknown. p99 on /api/me went from 340ms to 45ms in staging.
