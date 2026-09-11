---
type: llm
focus: last_message
weight: 1
---
Judge only the rewritten paragraph.

The original says the new index "significantly improves the speed of the reconciliation query". An adverb is standing in for a measurement the original never supplies.

PASS if the replacement is a plain verb carrying the meaning on its own, such as "the new index sped up the reconciliation query" or "the reconciliation query runs faster on the new index".

FAIL if an intensifier is still propping up the verb. "significantly improves", "greatly improves", "dramatically speeds up", "makes it much faster", and "improves the speed considerably" all fail, because swapping one intensifier for another leaves the sentence doing the same thing.

FAIL if the replacement invents a timing, a percentage, or a multiplier. The original supplies no figure, so any number is a fabrication.
