---
name: vision
description: "Create or update a project roadmap. Use for milestone planning, overall progress, what remains toward a goal, or /vision."
argument-hint: "[blank to chart or report] [add <milestone> | done <n> | reopen <n> | order <n n n>] [you-pick]"
disable-model-invocation: true
---

<!-- BEGIN MANA PERSONA -->
## Persona at invocation

Before conversational narration, read `Persona:` and `Style:` in the active project's `## Agent skills` block from `CLAUDE.md` or `AGENTS.md`. Prefer the file containing the block, then an existing file; ties use `CLAUDE.md`. A symlink pair is one file. Read the saved value anew on each invocation, including from a subdirectory using the project root. No accessible project or no line means ordinary behavior. Do not search another project or global settings for this preference.

During the `Persona at invocation` stage, `archmage` on either line loads this skill's own [references/archmage.md](references/archmage.md) for the active workflow. `off` or an absent value leaves ordinary behavior active. An unknown value leaves ordinary behavior active and gets a brief explanation when conversational output is allowed; it does not stop the work. Explicit conversation instructions override the saved voice without writing settings. A request to enable Archmage for this workflow also loads the local reference.

Apply the voice only to lead-agent conversation. Deliverables, specialist roles, reply-only responses, and JSON-only output retain their contracts, with no added narration. End the persona with this workflow unless the user requests otherwise or a `Style:` line names `archmage`, which keeps the voice on for the whole session.
<!-- END MANA PERSONA -->

# Vision

Keep one roadmap of ordered milestones and derive progress from the maps and build efforts linked to it.

Honor explicit user instructions and decisions already made over workflow defaults. Continue through the requested result; ask only about unresolved choices that would materially change it. Reporting progress alone does not authorize implementation work. If a real permission or missing prerequisite prevents completion, explain it and finish independent authorized work.

## Shared contracts

- The roadmap carries the exact body line `Work kind: roadmap`. Maps and build efforts link up through a `Milestone:` line in their own bodies; closing them requires no roadmap write.
- Reconciliation derives status from members, preserving explicit `Confirmed done:` overrides. Snapshot the body and guard updates against concurrent changes. Incomplete reads leave the saved roadmap unchanged.
- Default reporting uses counts without dates or estimates. Use milestone names and linked issue titles in user-facing output.

`<SKILL_DIR>` is the absolute directory containing this file. Substitute it directly in bundled script commands.

## Route

1. **Resolve:** load [references/tracker.md](references/tracker.md) to find the tracker and roadmap. For a local roadmap, also load [references/scratch.md](references/scratch.md).
2. **Chart:** when no roadmap exists, load [references/chart.md](references/chart.md). It loads the body schema and milestone guidance. Create the roadmap and save its pointer, then report.
3. **Reconcile:** for an existing roadmap, load [references/reconcile.md](references/reconcile.md), including for `add <name>`, `done <n>`, `reopen <n>`, or `order <n n ...>`. It loads the schema, applies the edit, and refreshes status under the body guard.
4. **Report:** load [references/report.md](references/report.md) after charting or reconciliation. A roadmap-only request is complete when the roadmap and pointer are saved and the next-step report is delivered. Continue a broader explicitly authorized request after that result.

`you-pick`, "make the decisions", or "you pick" authorizes recommended choices for charting. Preserve decisions already supplied without requiring that token.

## Bundled readers and writers

Use `scripts/tickets.sh` for tracker operations with the resolved adapter flags. It supports GitHub with `git` and `gh`, and Linear or Jira with Python's standard library. Exit 3 means the token cannot write; the charting reference describes the local fallback.

Use `scripts/map.sh` for GitHub map frontier reads. Its optional repository argument is `owner/repo`, not the ticket script's adapter flags. Other trackers use the Wayfinding operations in their tracker configuration.

The optional persona reference loads only during the persona stage above. Workflow-specific references load only at their named stage.

## References

| Reference | Load at | Purpose |
|-----------|---------|---------|
| `references/archmage.md` | Persona at invocation, when enabled | The Archmage voice |
| `references/tracker.md` | Route step 1 | Tracker resolution and finding the roadmap |
| `references/scratch.md` | Route step 1 on a local tracker, or on exit 3 | The roadmap as a file |
| `references/chart.md` | Route step 2 | Creating the roadmap and its pointer |
| `references/roadmap-shape.md` | Route steps 2 and 3, loaded by chart.md and reconcile.md | Roadmap body, the upward link, edits |
| `references/milestones.md` | Route step 2, loaded by chart.md | Settling the destination and milestones |
| `references/reconcile.md` | Route step 3 | Snapshot, edits, membership, status derivation, guarded write |
| `references/report.md` | Route step 4 | The report table and the next-step rules |
