# Local build effort

Load for a local tracker or after a tracker write returns exit 3. Keep the build effort under `.scratch/<slug>/`, where `<slug>` names the implementation destination. For a configured local tracker, use its ticket directory convention instead.

```text
.scratch/<slug>/build.md
.scratch/<slug>/tickets/01-<ticket-slug>.md
.scratch/<slug>/tickets/02-<ticket-slug>.md
```

Use the parent shape from `references/build-effort.md`, with `# Build: <outcome>` and `Status: open` above `Work kind: build`. Persist the accepted order before writing tickets. The parent never has `Status: ready-for-agent`.

Each ticket begins:

```markdown
# <title>

Status: ready-for-agent
Category: bug | enhancement
Build parent: [<build title>](../build.md)
Planning source: [<source title>](<map URL or spec path>)
Blocked by: 01-<ticket-slug>.md

<brief from agent-brief.md>
```

The build order links these paths. Resolve relative paths against the containing file. Enumerate both the order and files with the matching build-parent link, read every status, and stop on a missing or unreadable file. Resume reuses matching tickets, including closed ones, and creates only missing slices. Claiming rewrites `Status: claimed` with the builder's name. Closeout follows `references/build-progress.md` and sets the parent's `Status: closed` only after its destination is delivered.

If a remote write failed after some tickets were created, record their real URLs in the local order and preserve their IDs. Store only missing slices locally; do not recreate remote tickets. Keep any remote parent URL in the local record too. Record failed attachments or edges so a resumed session repairs them before calling filing complete. An uncertain create requires a read to establish whether it succeeded before a local replacement can be written.

For a local map, save a link to the build file in its handoff while preserving its closed status. If the map is remote and writes are denied, report the local parent path and explain that its source link could not be recorded remotely. End with the exact file or issue to work next. Publishing local tickets later needs an explicit request.
