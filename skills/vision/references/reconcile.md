# Reconcile a roadmap

Load `references/roadmap-shape.md` if you have not this session.

### 3a. Snapshot

Save the raw body before deriving anything. Abort on a failed read. Shell variables do not persist between calls, so record the printed path.

```bash
snapshot_path=$(mktemp)
if ! bash "<SKILL_DIR>/scripts/tickets.sh" <adapter flags> body ROADMAP_ID > "$snapshot_path"; then
  rm -f "$snapshot_path"
  exit 1
fi
printf 'original_body=%s\n' "$snapshot_path"
```

### 3b. Apply an edit

`add`, `done`, `reopen`, or `order` changes the **Milestones** section of the replacement body as `references/roadmap-shape.md` describes. `done` writes a `Confirmed done:` line with the reason the user gave, whatever the previous status, since the line is idempotent and `reopen` removes it. An edit that names a milestone number that does not exist stops without writing.

### 3c. Find the members

Search every state for issues that name the roadmap:

```bash
bash "<SKILL_DIR>/scripts/tickets.sh" <adapter flags> find "<roadmap URL>"
```

Read each hit's body. A member is an issue whose body has a `Milestone:` line naming this roadmap's URL, as `references/roadmap-shape.md` shows. A bare mention is not membership. Classify each member: a **map** carries the label `scry:map` or `wayfinder:map`; an **effort** carries the exact body line `Work kind: build`. Anything else is ignored. Record the milestone name each one names; a name that matches no milestone counts as **unattached** and is reported.

Maps and efforts that never name the roadmap are also unattached. Count them once with `list scry:map`, `list wayfinder:map`, and `find "Work kind: build"`, subtracting the members already found. Count only; do not read their bodies.

A search that fails leaves the roadmap unchanged. Report `unknown: <reason>` and stop before writing.

### 3d. Derive status

For each milestone, apply the first matching row:

| Status | Rule |
|--------|------|
| `done` | A `Confirmed done:` line is present, or at least one effort names it, every map naming it is closed, and every effort naming it is closed |
| `building` | Every map naming it is closed and at least one map or effort names it. This covers an open effort, and a closed map with no effort yet, whose Left line reads `plan implementation from <map title>` |
| `deciding` | At least one open map names it |
| `planned` | Nothing names it |

A closed map counts as sliced only when an effort names the milestone. Before writing `plan implementation from <map title>`, run `find "<map URL>"` and read each hit for a `Planning source:` line naming that map; an effort found that way is a member of the milestone even without a `Milestone:` line, so record it under Efforts. A milestone the previous body marked `done` by the rules alone, that now has an open member, goes back to `building` or `deciding`; only a `Confirmed done:` line holds. The **current** milestone is the first one that is not `done`.

For the current milestone only, fetch the details needed by `references/report.md`. On GitHub, read each open map's frontier:

```bash
bash "<SKILL_DIR>/scripts/map.sh" frontier MAP_ID OWNER/REPO
```

Use the configured repository, or omit `OWNER/REPO` to resolve it from this checkout. On GitHub Enterprise, pass `GH_HOST=<host>` inline. Elsewhere use the tracker file's Wayfinding operations. The first frontier row is the map's next ticket; an empty frontier routes to inspecting the open map itself.

For each open effort, use the bundled ticket script with the resolved adapter flags to `view PARENT_ID`, `children PARENT_ID`, and `view MEMBER_ID` for each open member. Read the label for the `ready-for-agent` role from `docs/agents/triage-labels.md`, defaulting to `ready-for-agent`. Use the parent's **Build order**. Prefer a member already assigned to the current tracker user; resolve that identity with `tickets.sh check` and do not assume an unknown identity owns a ticket. Otherwise choose the first unassigned ready member in build order whose `blocked MEMBER_ID` returns 1 (no open blockers). Exit 0 means blocked; other failures make availability unknown. Read operations do not claim tickets or change member state.

### 3e. Write

Rewrite the body from the snapshot: the same sections in the same order, each milestone's status, its Maps and Efforts lines, and its Left line updated, and any **Not yet planned** line whose name now matches a milestone removed. A milestone that is not current gets its Left line from the 3c counts alone, such as `2 maps open, 1 effort open`, with no frontier or ticket-level fetch; only the current milestone's Left line uses the detail fetched in 3d. Preserve every other line. Write under the guard:

```bash
original_body='<recorded absolute snapshot path>'
if ! bash "<SKILL_DIR>/scripts/tickets.sh" <adapter flags> update-body ROADMAP_ID --expected-body "$original_body" <<'EOF_BODY'
<updated body>
EOF_BODY
then
  rm -f "$original_body"
  exit 1
fi
rm -f "$original_body"
```

A mismatch means another session wrote first. Reread from 3a once and repeat. A second mismatch stops with the report and no write. A body that would come out identical is not written.

