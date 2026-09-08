# Grilling

Interview the user until you share an understanding. Map the work as a **design tree**: every settled decision unblocks the decisions that hang off it.

Work in **rounds**. The **frontier** is every decision whose prerequisites are already settled: the questions you can ask now without guessing at answers you have not heard. Ask the whole frontier in one round. Number each question and give your recommended answer. Then wait.

```
**Q1. <title>**
<body, including choices when they help>

Recommended: <your answer>
```

Each round of answers reshapes the tree. Settled decisions push the frontier outward. A question that still depends on something open in this round belongs to a later round.

Finding facts is your job. When a frontier question needs something from the filesystem or the tracker, dispatch a subagent to look it up. Do not block the rest of the round on that lookup: ask every question whose prerequisites are already settled.

The decisions are the user's. Put each one to them and wait.

**`you-pick`.** If the invocation included `you-pick`, or the user said "make the decisions", "you pick", or "you decide", treat every recommended answer in that round as accepted and continue. Still show the questions and the answers you took, so they can override.

The interview is done when every branch of this ticket's question is settled, with nothing left silently assumed. An empty map frontier can also mean work is assigned or blocked; map completion is checked separately in Stage 3f. Do not act on the result until the user confirms you have a shared understanding, unless `you-pick` already covered that confirmation.
