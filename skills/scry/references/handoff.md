# Map handoff

Use this reference whenever a map closes or a user revisits a map that is already closed. The map records decisions. The handoff tells the user what action follows.

## Closeout

Keep the source map closed. Do not create implementation tickets as children of the map and do not create tickets automatically during closeout.

Before writing the completion note, inspect the map body and all its comments for an existing build effort. Follow source-linked implementation work before suggesting new tickets. Search the configured tracker across all states for this map URL in `Planning source:` or legacy `Builds toward:` lines, including work whose source comment was never saved. If an existing-effort search or a linked issue read fails, report that uncertainty and give a prompt to recheck the handoff; do not claim tickets are absent. A build effort is a separate issue whose body contains:

```text
Work kind: build
Planning source: [Map title](map-url)
```

The build effort can also be linked from the map under `## Build effort`. Accept an older `## Build order` comment listing flat implementation tickets too. Read those tickets even when there is no separate build parent; their `Builds toward:` planning-map link is valid legacy provenance. Its implementation tickets identify membership with:

```text
Build parent: [Build title](build-url)
```

When a linked build effort or legacy ticket list exists, read its current tickets and dependencies. Write its title and URL in **Next step**, report the first open, ready, unclaimed ticket with satisfied blockers in build order, and give a copyable prompt to implement that ticket. When none is available, name pending reviews or blockers and give a prompt to check progress on the effort. If its destination is already delivered, report completion. Reuse the existing effort and tickets. Do not propose a second build effort.

When no build effort exists and the destination needs implementation, put this copyable prompt in **Next step**, replacing the bracketed values:

```text
Use the completed planning map [Map title](map-url) to propose the implementation work for [outcome]. Keep the map as the planning source and create a separate build effort with ordered implementation tickets. Show me the proposed slices before creating tickets, then create the build effort and tickets after I accept them. End by giving me the first available implementation ticket and an exact prompt to start it.
```

When the destination needs no downstream work, say so directly and write `No further work is required for this destination.` When another decision remains, name the decision and point the user back to the open ticket or map rather than handing off to implementation.

## Revisiting a closed map

A closed map is read-only. Report:

1. the destination and completion note;
2. any linked build effort and its first available ticket;
3. the remaining decision or blocker, if one exists;
4. the copyable implementation prompt when implementation is needed and no build effort exists;
5. completion when no downstream work remains.

Read existing issues and links before deriving the report. A missing or failed read leaves the map unchanged and the handoff unresolved. Treat older flat build-ticket lists as evidence of an existing build effort when their bodies contain `Builds toward:`, `Planning source:`, or `Build parent:` links, then report those links without creating replacements.
