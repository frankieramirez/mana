# Spec: the vision skill

Destination: a repo set up with mana can hold one roadmap on its tracker, every map and build effort names the milestone it serves, and `vision` reports the current milestone, how much of it is left, and the exact next prompt. Portal routes to it when the board is otherwise clear.

## Why

After a map closes there is no answer to "what next" above the ticket level, and no view of how much of the larger goal remains. Product teams work against a roadmap with milestones. This gives the skills the same thing, kept where concurrent sessions cannot clobber it.

## Decisions already made

- **The roadmap is one tracker issue**, marked by the exact body line `Work kind: roadmap`. Not a file in the repo: two maps closing on two branches would conflict, and the file would be stale off main. One issue works unchanged on GitHub, Linear, Jira, and local files through `tickets.sh`.
- **Nothing points down from the roadmap.** Maps and build efforts point up with a body line, the way build tickets carry `Planning source:`. Closing a map or delivering an effort writes nothing to the roadmap, so concurrent closeouts never touch the same body.
- **`vision` is the only writer.** Status is derived on read from the linked maps and efforts, then written under the `update-body --expected-body` guard scry already uses in closeout. Two `vision` sessions at once is the only possible conflict and the guard catches it.
- **No dates, no estimates.** Progress is counts: milestones done over total, and inside the current one, maps closed over open and efforts delivered over open.
- **The name is `vision`.** The top section of the body is `Destination`, matching the map body, so the skill name and the section name stay distinct.

## Roadmap body

```markdown
Work kind: roadmap

## Destination

<what is true when the roadmap is done, one or two lines>

## Notes

<files every session should read; standing preferences; owning docs>

## Milestones

### 1. <name>  [planned | deciding | building | done]

<one sentence outcome>

Maps: [<title>](url), [<title>](url)
Efforts: [<title>](url)
Left: <one line, or "nothing">

### 2. <name>  [planned]

...

## Not yet planned

<!-- milestones too dim to name; the roadmap's fog -->

## Out of scope

<!-- what the destination rules out -->
```

Status is derived, never typed by hand:

| Status | Rule |
|--------|------|
| `planned` | no map and no effort names this milestone |
| `deciding` | at least one open map names it |
| `building` | every map naming it is closed and at least one effort naming it is open |
| `done` | every map closed and every effort delivered, or the user confirmed it with `done <n>` |

The flip to `done` is automatic. The report names any milestone whose status changed this run, and `reopen <n>` undoes a `done` confirmation. The current milestone is the first one not `done`. A milestone with nothing linked is `planned`; `vision` never invents maps or efforts for it.

## The upward link

A map's Notes carry one line:

```
Milestone: <milestone name> on [<roadmap title>](<roadmap url>)
```

A build parent carries the same line, copied from its planning map by `conjure`. `vision` discovers members with `find "<roadmap url>"` across all states and verifies the line in each body, the way conjure verifies `Part of #<map>`. A mention alone does not establish membership.

## Discovery

The pointer lives in the `## Agent skills` block as `Roadmap: #12` (or a Linear or Jira key, or a local path), inserted after `Domain docs:`. Skills read that line first. When it is absent, `find "Work kind: roadmap"` is the fallback, and more than one open hit stops with the list. `attune roadmap <id>` sets or removes the line.

## The skill

Directory `skills/vision/`. Frontmatter `name: vision`, `disable-model-invocation: true`. Description in plain English: roadmap, milestones, what is left, what should we do next at a high level, where are we, `/vision`.

Bundled script: a copy of `skills/sift/scripts/tickets.sh`, added to the copy check in `scripts/validate.sh`. The persona block comes from `scripts/sync-persona.sh`, which also drops `references/archmage.md`.

### Arguments

| Input | Effect |
|-------|--------|
| none, no roadmap | Stage 2: chart |
| none, roadmap exists | Stage 3: reconcile and report |
| `add <name>` | append a milestone, then Stage 3 |
| `done <n>` | confirm milestone n is done while something linked is still open, then Stage 3 |
| `reopen <n>` | undo a `done` confirmation, then Stage 3 |
| `order 3 1 2` | reorder, then Stage 3 |
| `you-pick` | accept every recommended answer in the charting round |

### Stage 1: Tracker

Same as `portal`: read `docs/agents/issue-tracker.md`, resolve adapter flags, pass `GH_HOST` inline. Resolve the roadmap by the rules under Discovery.

### Stage 2: Chart

Load `references/milestones.md`. Interrogate the destination, then the milestones, breadth-first at milestone grain: each milestone is one outcome a user could notice, ordered by what unblocks what. This is scry Stage 2b one level up and reuses the round shape from scry's interrogation reference, rewritten here so the skill stands alone. Write the body, create the issue with `tickets.sh create "Roadmap: <destination in a few words>"`, write the `Roadmap:` line into the `## Agent skills` block, and stop. Charting is one session.

### Stage 3: Reconcile

Read the roadmap body and snapshot it. Find every issue whose body names the roadmap URL and read its state, its `Milestone:` line, and whether it is a map (`scry:map` or `wayfinder:map`) or an effort (`Work kind: build`). An effort is delivered when its build parent is closed. Recompute every status by the table above. Rewrite the body under the guard; on a mismatch, reread once and retry, then stop and report. Clear a `Not yet planned` line when a milestone with that name now exists.

### Stage 4: Report

Markdown, not a code block, in the portal shape:

```
### Vision

| | |
|---|---|
| **Destination** | one line |
| **Milestones** | done/total |
| **Current** | name, status, maps closed/open, efforts delivered/open |
| **Left** | the milestone's Left line |
| **Unattached** | maps and efforts naming no milestone |
| **Unplanned** | count of Not yet planned lines |

**Next step:** <skill> on <milestone or ticket with link>. <why>

**Prompt:** `<one line that starts it>`
```

Next step rules, first match wins:

1. The current milestone has an open map with a frontier ticket: `scry` on that ticket.
2. It has an open effort with an available ticket: `cast` on that ticket.
3. It has a closed map with no effort: `conjure` on the map.
4. It has an open effort with nothing available: `conjure` on the effort for a progress check.
5. It is `planned`: `scry` to chart a map, with the prompt `Chart a map toward <milestone outcome>, serving milestone <name> on <roadmap URL>.`
6. Every milestone is `done` and nothing is unplanned: say so and stop.

## Hooks in other skills

- **scry Stage 2c.** When a roadmap resolves, ask which milestone the map serves, offering the current one as the recommendation, and write the `Milestone:` line into Notes. A map that serves none is allowed and says so. The handoff reference does not change.
- **conjure Stage 3.** Copy the planning map's `Milestone:` line into the build parent body. A spec source with no line gets none.
- **portal.** Add a **Roadmap** row to the board table: current milestone and done/total, or `none`. Replace the last route row: when a roadmap exists and has a milestone that is not `done`, route to `vision`; otherwise say the board is clear and `scry` charts from a loose idea. Add `vision` to the handoff sibling list.
- **attune.** Add the `roadmap` setting, its line in the block order, and its row in the settings table.
- **setup-mana.** At the end, offer to run `vision` to chart a roadmap. Do not chart inside setup.
- **README.** A `### vision` section after `portal`, and a sentence in The loop.
- **CHANGELOG and version.** `0.29.0`.
- **Local tracker.** The roadmap is `.scratch/roadmap.md`, following the scratch conventions, and members link by path.
- **Tests.** None beyond `scripts/validate.sh`. Status derivation is prose the model follows, so there is no script to fixture.

## Decided in interrogation

The milestone flip is automatic with `reopen` as the undo. No dates. The pointer is the block line. Unattached maps and efforts are allowed and reported. Portal routes to `vision` last. The local tracker is supported. Charting stops after the roadmap issue. The change is implemented directly on one branch as one pull request rather than through a build effort.

## Out of scope

- Native GitHub milestones, Linear projects, or Jira versions. Possible later as enrichment on top of the issue.
- More than one roadmap per repo.
- Dates, estimates, or velocity.
- Automatic writes to the roadmap from scry, conjure, or cast.
