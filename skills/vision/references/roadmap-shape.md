# Roadmap shape

The roadmap is one tracker issue. Its body is an index: it names milestones and links the maps and efforts that serve them. Decisions stay on maps, briefs stay on tickets, and the roadmap gists nothing twice.

## Body

```markdown
Work kind: roadmap

## Destination

<what is true when the roadmap is done, one or two lines>

## Notes

<relevant documents with when to consult them; standing preferences>

## Milestones

### 1. <name>

Status: planned | deciding | building | done
<one sentence outcome a user could notice>

Maps: [<title>](<url>), [<title>](<url>)
Efforts: [<title>](<url>)
Left: <one line, or nothing>

### 2. <name>

Status: planned
<outcome>

Maps: none
Efforts: none
Left: chart a map

## Not yet planned

<!-- milestones too dim to name yet, one line each -->

## Out of scope

<!-- what the destination rules out, one line each with the reason -->
```

`Work kind: roadmap` is the first line and matches exactly. The `Status:` line under each milestone is rewritten on every reconcile. A `Confirmed done: <reason>` line after `Status:` records a `done` edit and is the only status the rules do not recompute.

The **Left** line is written by the skill from the current state: the number of open maps and tickets still open under the milestone, the effort awaiting review, or `chart a map` for a planned milestone. Keep it to one line.

## The upward link

A map's **Notes** section, and a build parent's body above its Destination, carry one line:

```
Milestone: <milestone name> on [<roadmap title>](<roadmap URL>)
```

The name matches a `### n. <name>` heading exactly, case and all. The URL is how the skill finds members with `find`. On a local tracker the URL is the roadmap file path relative to the repo root.

A map or effort with no such line is allowed. The report counts it as unattached so drift is visible.

## Edits

- **add.** Append `### <next number>. <name>` with `Status: planned`, an outcome the user gives or one drafted within their authorized scope; ask if a material ambiguity remains, `Maps: none`, `Efforts: none`, and `Left: chart a map`. Remove a **Not yet planned** line with the same name.
- **done.** Add `Confirmed done: <reason>` after the milestone's `Status:` line. The reason is what the user said; ask when they gave none.
- **reopen.** Remove the `Confirmed done:` line. The next reconcile recomputes the status.
- **order.** Renumber the headings in the given order. Every existing number appears exactly once or the edit stops. Member links follow their milestone by name, so nothing else changes.

Renaming a milestone changes what every member's `Milestone:` line has to say. This skill does not rename; say so and point at the members that would need editing.
