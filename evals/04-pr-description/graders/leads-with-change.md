---
type: llm
focus: last_message
weight: 1
---
Judge only the pull request description.

PASS only if both hold:

1. A reader learns what the change does before they learn anything else. Caching the JWKS response in the auth middleware is identifiable from the title or the first sentence of body text.
2. All three supplied facts appear: the JWKS response is cached for 10 minutes, a test asserts the cache is bypassed when the key ID is unknown, and p99 on /api/me moved from 340ms to 45ms, attributed to staging rather than production.

Markdown structure is not under judgment here. A description organised under headings such as "What changed" and a description written as plain paragraphs are equally acceptable, and neither shape is evidence for or against claim 1. Judge claim 1 on where the change itself appears, not on how the document is sectioned.

Length is not graded. A single sentence naming the change satisfies claim 1 as fully as a titled section does.
