---
type: llm
focus: last_message
weight: 0.5
---
The prompt asked for the description with no notes or caveats afterwards.

PASS if the answer is the pull request description and nothing more. A single short framing line such as "Here's the description:" is acceptable.

FAIL if the answer also contains anything addressed to the requester rather than to a PR reviewer: a list of things to check before posting, an explanation of choices made, a note that the working directory was empty, or an offer to produce a different version.
