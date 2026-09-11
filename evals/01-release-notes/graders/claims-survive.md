---
type: llm
focus: last_message
weight: 1
---
Judge only the rewritten release-notes paragraph. Ignore any framing line such as "Here's the rewrite:".

PASS only if both hold:

1. Every factual claim from the original survives: the sync engine changed, records reconcile in under a second, conflicts resolve deterministically, and the retry path no longer floods the queue.
2. No factual claim appears that the original did not contain.

On claim 1, a claim restated in plainer words still counts as surviving. "Conflicts resolve deterministically" may become "conflicts resolve the same way every time", or "both ends reach the same answer", or any wording that describes a repeatable outcome. Explaining what determinism means for the reader is a rewrite, not an addition.

On claim 2, a fabrication is a new fact: an invented latency figure, version number, date, named component, named algorithm, or a named cause the original never gave. Restating a consequence that the original's own wording implies is not a fabrication.
