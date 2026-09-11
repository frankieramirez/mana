---
type: llm
focus: last_message
weight: 0.5
---
The prompt asked for the rewritten section with no commentary.

PASS if the answer is the rewritten documentation section and nothing more. A single short framing line such as "Here's the section:" is acceptable.

Documentation speaks to whoever reads the docs. A sentence telling that reader what to do, such as "catch this where you call it", is part of the section and PASSES.

FAIL only on text addressed to the person who requested the rewrite: a list of what was cut, an explanation of the editing choices, a note that the file could not be found, a caveat about what to verify, or an offer to produce a different version.
