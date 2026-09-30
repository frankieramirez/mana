# Interrogation

Interview the user until you share an understanding. Map the work as a **design tree**: every settled decision unblocks the decisions that hang off it.

Reuse decisions already supplied in the conversation before opening a round. Ask only about unresolved choices that would materially change the result.

Work in **rounds**. The **frontier** is every decision whose prerequisites are already settled: the questions you can ask now without guessing at answers you have not heard. Ask the whole frontier in one round. Number each question and give your recommended answer. Then wait.

```
**Q1. <title>**
<body, including choices when they help>

Recommended: <your answer>
```

Each round of answers reshapes the tree. Settled decisions push the frontier outward. A question that still depends on something open in this round belongs to a later round.

Finding facts is your job. When a frontier question needs something from the filesystem or the tracker, dispatch a subagent to look it up. Do not block the rest of the round on that lookup: ask every question whose prerequisites are already settled.

For a choice the user has not supplied or delegated, present the recommendation and wait. Investigate observable facts yourself.

**`you-pick`.** If the invocation included `you-pick`, or equivalent authority to choose was given in the conversation, treat recommended answers within that authority as accepted and continue. Still show the questions and the answers you took, so they can override.

The session is done when the frontier is empty: every branch visited, nothing left silently assumed. Once the material choices are settled, continue the authorized workflow. Do not require another confirmation of supplied decisions or delegated choices. A draft-only request ends with the draft.
