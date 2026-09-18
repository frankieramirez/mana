# Spec: the vision skill

A project roadmap explains how current capabilities reach the destination. Milestones carry observable completion criteria and sequencing rationale. The report names the next useful action from inspected project evidence.

## Contracts

- One tracker issue, identified by the saved `Roadmap:` pointer or `roadmap` label. The legacy `Work kind: roadmap` line remains readable. New bodies omit visible machine metadata. Local trackers use `.scratch/roadmap.md` with a title and top-level status.
- Maps and build efforts link upward through `Milestone: <name> on [<roadmap title>](<url>)`. Closing work never writes the roadmap. Authorized charting or updates can link clear existing-work matches under per-member body guards; ambiguous or conflicting links require a decision.
- Reconciliation snapshots the roadmap and writes under `update-body --expected-body`. Failed required reads preserve its saved body. Member writes are independent and partial success is reported. Read-only requests leave both roadmap and members unchanged.
- Destination requirements belong to a milestone or verified baseline evidence. Milestone scope does not shrink to match whatever work happened to close.

## Charting

Read relevant release scope and inspect plausible existing work, including closed planning sources. Separate verified baseline from proposed scope. Each milestone explains its user value and why it comes here, with observable completion criteria. Identify uncertainties that could change the sequence. Catch-all milestones need justified workstreams or a proposed split. Preserve user decisions and ask only for material missing choices.

Create the labelled issue and save the pointer. Link clear matches within authorization, reconcile evidence, then report. Draft requests stop before writes. Creation does not initialize every milestone as planned.

## Status

Apply in order:

| Status | Evidence |
|--------|----------|
| done | Explicit user confirmation, or all completion criteria verified and no open member work |
| deciding | An open member map |
| building | An open effort, implementation needed from a closed map, or an identified delivery gap in work already started |
| verifying | Delivery reported complete but evidence missing |
| planned | No established activity |

Closed issues alone never prove an outcome. Legacy outcomes without criteria need scope-preserving criteria before verification. `done <n>` records an explicit reason; `reopen <n>` removes that override and recomputes status. `add` and `order` preserve existing member names. Renaming remains outside this workflow because links use milestone names.

## Presentation

The issue opens with Destination and Where we stand, followed by numbered milestones. Keep `Status:` lines for consumers. Include useful links and concrete remaining actions; omit empty Maps and Efforts fields. References belong after the milestones. Future scope names the decision needed to include it.

The conversational report leads with the consequential conclusion and a roadmap link. Explain meaningful changes and remaining gaps, then supply a next action and ordinary-language prompt. Use counts only as supporting evidence. No forced wide table, raw unattached counts, or invented dates and estimates.

## Integration and validation

The routing skill and settings accept pointers or labels plus legacy markers. Planning maps and build efforts retain their upward-link format. Standalone installs keep the existing bundled ticket and frontier scripts; no new runtime is needed.

Run `scripts/validate.sh`. Behavioral cases and their assessment criteria live in `evals/vision/`; they exercise first-run discovery, incomplete delivery evidence, and compatibility. These are agent scenarios, not regex tests of instruction wording.
