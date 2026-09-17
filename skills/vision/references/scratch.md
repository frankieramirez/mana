# Roadmap as a file

Load for a `local` tracker, or when a tracker write returns exit 3.

The roadmap is `.scratch/roadmap.md`. Use the body from `roadmap-shape.md` with a title and status line above the marker:

```markdown
# Roadmap: <destination in a few words>

Status: open
Work kind: roadmap

## Destination
...
```

The `Roadmap:` line in the `## Agent skills` block holds the path. Members link up with `Milestone: <name> on [Roadmap](.scratch/roadmap.md)`, resolved against the repo root, and the skill finds them by searching `.scratch/` for that path rather than through the tracker. A remote map or effort that names the file path is still a member.

Reconcile reads the file, derives status the same way, and rewrites it in place. The guard is a comparison against the snapshot taken at the start of the run; on a mismatch, reread once and repeat.

After exit 3 on a remote tracker, keep the roadmap local and say in the report that its members will name a file path until it is published. Publishing later needs an explicit request.
