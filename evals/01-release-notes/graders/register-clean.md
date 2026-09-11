---
type: llm
focus: last_message
weight: 1
---
Judge only the rewritten release-notes paragraph. Ignore any framing line such as "Here's the rewrite:".

PASS only if all three hold:

1. The first sentence says what changed. An opener that announces an announcement, such as "We're excited to" or "We're pleased to share", fails.
2. The final sentence carries information that no earlier sentence carried. A closing line that restates the paragraph, such as "That's the whole change" or "Net effect: faster syncs", fails.
3. No sentence contains a three-item list of nouns, adjectives, or clauses.
