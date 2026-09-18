# Roadmap shape

The roadmap explains the route from the current project to its destination. Keep milestone-level reasoning here and link to maps for detailed decisions and efforts for implementation briefs.

## Body

Use this outline, omitting optional sections and empty fields. Milestone headings and `Status:` lines remain stable for readers that consume the roadmap.

```markdown
## Destination

<the user capability or project outcome this roadmap will establish>

## Where we stand

<verified baseline, work underway, and the most consequential gap, with sources>

## Milestones

### 1. <outcome name>

Status: planned | deciding | building | verifying | done

<what this delivers and why it matters; why it comes here and what it depends on>

**Complete when**
- <observable criterion, with evidence when satisfied>

<material uncertainty, its consequence, and how to resolve it, when relevant>

Maps: [<title>](<url>)
Efforts: [<title>](<url>)
Left: <concrete remaining outcome, decision, or verification>

## Not yet planned

<future scope and the decision needed to include it, when relevant>

## Out of scope

<exclusions and reasons, when relevant>

## References

<owning documents linked to the relevant file or section, with why they matter>
```

Use repository links for documents on a remote tracker. Omit Maps and Efforts when empty. Do not print `Maps: none`, `Efforts: none`, or generic `Left: chart a map`. No visible work-kind metadata is required. Existing `Work kind: roadmap` bodies remain readable; remove that line when migrating an authorized update, after ensuring the `roadmap` label on a remote tracker. Keep a local roadmap's title and top-level status.

Rewrite milestone `Status:` from evidence on reconcile. A `Confirmed done: <reason>` line after it records the user's explicit override; keep the reason visible and distinguish confirmation from verified evidence. Completion criteria are stable scope: do not silently weaken them to match delivered work.

The **Left** line explains the most useful remaining action or gap. Omit it for done milestones. Counts may support a conclusion, but do not replace it.

## The upward link

A map's **Notes** section, and a build parent's body above its Destination, carry one line:

```
Milestone: <milestone name> on [<roadmap title>](<roadmap URL>)
```

The name matches a `### n. <name>` heading exactly, case and all. The URL is how the skill finds members with `find`. On a local tracker the URL is the roadmap file path relative to the repo root.

A map or effort with no such line is allowed. Inspect plausible matches before recommending new work; report unresolved associations by title and consequence.

## Edits

- **add.** Append `### <next number>. <name>` with an outcome and completion criteria from the user or drafted within their authorized scope. Load `milestones.md` for destination coverage and sequencing; ask if a material ambiguity remains. Reconcile existing work before assigning status. Remove a **Not yet planned** line with the same name.
- **done.** Add `Confirmed done: <reason>` after the milestone's `Status:` line. The reason is what the user said; ask when they gave none.
- **reopen.** Remove the `Confirmed done:` line. The next reconcile recomputes the status.
- **order.** Renumber the headings in the given order. Every existing number appears exactly once or the edit stops. Member links follow their milestone by name, so nothing else changes.

Renaming a milestone changes what every member's `Milestone:` line has to say. This skill does not rename; say so and point at the members that would need editing.
