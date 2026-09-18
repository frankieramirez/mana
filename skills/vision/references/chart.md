# Chart a roadmap

Load `references/roadmap-shape.md` and `references/milestones.md`.

Ground the chart and inspect existing work as `references/milestones.md` describes. Load `references/reconcile.md` for discovery and evidence rules. Before creation, settle milestone outcomes and completion criteria, account for destination coverage, and identify clear member matches. A draft request stops with the proposed roadmap and associations, without writes.

Create the dedicated `roadmap` label, then the issue. This label identifies the roadmap without putting it in a build or triage queue:

```bash
bash "<SKILL_DIR>/scripts/tickets.sh" <adapter flags> ensure-labels roadmap
```

After label creation succeeds:

```bash
bash "<SKILL_DIR>/scripts/tickets.sh" <adapter flags> create "Roadmap: <destination in a few words>" --label roadmap <<'EOF_ROADMAP'
<body from references/roadmap-shape.md>
EOF_ROADMAP
```

Check the label operation before creating the issue. Exit 3 from either operation means the token cannot write; use the fallback without continuing remote writes. On exit 3, load `references/scratch.md` and keep the roadmap under `.scratch/`. Other failures leave creation incomplete and are reported. For a configured local tracker, write the local roadmap directly without either remote operation.

Then write the pointer. Add `Roadmap: <id or URL>` to the `## Agent skills` block of the file that holds it, after `Domain docs:` when that line exists and otherwise before `Peer reviewer:`, `Persona:`, and `Style:`. Change only that one line; keep every other line's text and order. The block is absent: create it in the existing instruction file, preferring `CLAUDE.md`, holding only this line.

After saving the pointer, link clear existing-work matches and reconcile under `references/reconcile.md`. Derive initial status from that work and its evidence; do not initialize everything as planned. Load `references/report.md`. Charting alone is complete after the report. Continue into further planning or implementation only when the user has authorized that broader work.

