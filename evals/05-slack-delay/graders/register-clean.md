---
type: llm
focus: last_message
weight: 1
---
Judge only the Slack message itself.

PASS only if all three hold:

1. No sentence contains a three-item list of nouns, adjectives, or clauses, and there is no repeated negative construction such as "no X, no Y, no Z".
2. There is no closing line placed for effect that adds no information, such as "Better safe than sorry" or "That's the plan".
3. No sentence uses "not X, but Y" or "it isn't A, it's B".
