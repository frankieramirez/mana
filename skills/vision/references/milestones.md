# Charting milestones

Interview the user until the destination and the milestones are shared. Work in **rounds**: ask every question whose prerequisites are already settled, number each one, give a recommended answer, then wait.

```
**Q1. <title>**
<body, including choices when they help>

Recommended: <your answer>
```

`you-pick`, or the user saying "make the decisions" or "you pick", accepts every recommended answer in the round. Still show the questions and the answers taken, so they can override.

## Round one: the destination

One or two lines that say what is true when the roadmap is done. Write it as a state of the product rather than a feature list. Push back on a destination that only names the next release; a roadmap that fits one map is a map.

Read `CONTEXT.md` and `docs/adr/` when they exist and use those words.

## Round two: the milestones

Breadth-first. A milestone is one outcome a user could notice, sized so that it takes more than one map or build effort to reach, and small enough that you can say what is left at any point. Ask for the outcomes, then the order, where the order is what unblocks what. Recommend three to six; more than that usually means two of them are one, or the destination is two roadmaps.

For each milestone draft the one-sentence outcome. Anything the user cannot yet name as an outcome goes under **Not yet planned** as a phrase, not a milestone.

Ask what the destination rules out. That goes under **Out of scope** with the reason, so a later map does not chart toward it.

## Done

The interview is done when the destination is written, every milestone has a name and an outcome, the order is agreed, and nothing is silently assumed. Do not create the issue until the user confirms, unless `you-pick` already covered that confirmation.
