# Resolve tracker and roadmap

Read `docs/agents/issue-tracker.md` when it exists. Its `Tracker:` line names the tracker and its `Adapter flags:` line gives the flags for the bundled script. Missing file: GitHub, no flags. On a GitHub Enterprise host, pass `GH_HOST=<host>` inline on every script call. Shell state does not persist between calls. For `local`, load `references/scratch.md` and treat `.scratch/roadmap.md` as the roadmap. For `other`, follow the tracker file's Conventions.

Find the roadmap through the saved `Roadmap:` line in the project's `## Agent skills` block first. Prefer the file containing the block; ties use `CLAUDE.md`. Read the target with `view` (or read the local file). A pointer identifies a roadmap when its body contains Destination and Milestones sections; a stale pointer or unrelated body is reported, never overwritten.

Without a pointer, combine and deduplicate open issues from these reads:

```bash
bash "<SKILL_DIR>/scripts/tickets.sh" <adapter flags> list roadmap
bash "<SKILL_DIR>/scripts/tickets.sh" <adapter flags> find "Work kind: roadmap"
```

The second read supports legacy issues across states. Validate candidate bodies for Destination and Milestones sections. One open candidate resolves the roadmap. Multiple candidates require the user's selection unless already supplied. Only closed candidates means no active roadmap; mention them before creating a new one. Failed discovery is unknown, not an empty board.

A saved pointer, the `roadmap` label, or the legacy exact body line identifies the document; no visible marker is required for new bodies. Preserve compatibility with all three. A local `.scratch/roadmap.md` with the same sections needs no marker.
