# Resolve tracker and roadmap

Read `docs/agents/issue-tracker.md` when it exists. Its `Tracker:` line names the tracker and its `Adapter flags:` line gives the flags for the bundled script. Missing file: GitHub, no flags. On a GitHub Enterprise host, pass `GH_HOST=<host>` inline on every script call. Shell state does not persist between calls. For `local`, load `references/scratch.md` and treat `.scratch/roadmap.md` as the roadmap. For `other`, follow the tracker file's Conventions.

Find the roadmap in this order and stop at the first hit:

1. The `Roadmap:` line in the `## Agent skills` block of `CLAUDE.md` or `AGENTS.md`. Prefer the file containing the block; ties use `CLAUDE.md`. The value is a tracker id, an issue URL, or a local path.
2. The marker, across all states:

   ```bash
   bash "<SKILL_DIR>/scripts/tickets.sh" <adapter flags> find "Work kind: roadmap"
   ```

   One open hit is the roadmap. More than one open hit: list them and stop, unless the user already identified the intended roadmap; use that selection and persist its pointer when authorized. Only closed hits count as no roadmap, and the report mentions them.

Read the roadmap with `view`. Confirm the exact body line `Work kind: roadmap`; an issue that lacks it is not the roadmap, whatever the pointer says. Say so and stop.

