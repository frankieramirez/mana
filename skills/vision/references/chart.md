# Chart a roadmap

Load `references/roadmap-shape.md` and `references/milestones.md`.

Use the supplied destination and milestones, resolving only missing choices with `references/milestones.md`. Load project context or a relevant ADR only when needed to interpret an outcome or constraint. The chart is ready when the destination and ordered milestone outcomes are clear; unresolved future outcomes belong under **Not yet planned**.

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

Load `references/report.md` with every milestone `planned`. Charting alone is complete after the report. Continue into further planning or implementation only when the user has authorized that broader work.

