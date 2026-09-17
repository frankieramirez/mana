---
name: vision
description: "Hold one roadmap of ordered milestones on the tracker, derive each milestone's status from the maps and build efforts that serve it, and say what is left and what to start next above the ticket level. Use when asked for the roadmap, the milestones, where we are overall, how much is left, what the next milestone is, what we should do next at a high level, to add or reorder a milestone, or /vision."
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

Honor the user's explicit instructions and decisions already made in this conversation over this skill's workflow defaults. A rule this file states with never, or as read-only, is a gate: it holds whatever the conversation says, and an instruction to cross one is declined and reported. Continue authorized work; ask only about unresolved choices that would materially change the result.

If a skill rule requires a pause or leaves requested work unfinished, name and link to the exact SKILL.md and quote the rule. Then explain what decision or prerequisite is missing. Distinguish a required gate from your interpretation.

Maps decide and build efforts deliver, one ticket at a time. Neither says how far the larger goal has come or what to start when the board is clear. This skill keeps one **roadmap** on the tracker: a destination, ordered milestones, and the maps and efforts that serve each one. Status is derived from those linked issues every time the skill runs, so nothing else ever has to write the roadmap.

## Operating principles

- **One roadmap per repo.** It is one tracker issue whose body carries the exact line `Work kind: roadmap`. Nothing lives in a repo file, because two sessions finishing on two branches would collide there.
- **Links point up.** A map or build effort names its milestone with a `Milestone:` line in its own body. The roadmap never has to be written when they close.
- **This skill is the only writer.** Every write to the roadmap body goes through the guarded update below. Other skills read it and link to it.
- **Status is derived, never typed.** A milestone's status comes from the state of the issues that name it. The body records the result, and the next run recomputes it.
- **No dates, no estimates.** Progress is counts.
- **Refer by name.** In anything a person reads, use the milestone name and the issue title with the link wrapped inside it.

`<SKILL_DIR>` is the absolute directory this SKILL.md lives in. Substitute the real path every time it appears. Do not assign it to a shell variable first: a sandboxed or worktree-isolated session refuses `bash "$VAR/script.sh"` because it cannot resolve the path to read the script.

## Scripts

`scripts/tickets.sh` reads and writes the tracker on GitHub (`git` and `gh` only), Linear, or Jira (`python3` and the tracker's environment variables). Exit 3 means the token cannot write. `tickets.sh -h` prints usage. This skill uses `create`, `view`, `body`, `update-body`, `find`, `children`, `blocked`, and `next` without `--claim`.

## Arguments

Parse tokens, then treat the remainder as the argument.

| Input | Effect |
|-------|--------|
| none, no roadmap | Chart one (Stage 2) |
| none, roadmap exists | Reconcile and report (Stage 3, Stage 4) |
| `add <name>` | Append a milestone after the last one, then Stage 3 |
| `done <n>` | Mark milestone n done even though something linked is still open, recording why, then Stage 3 |
| `reopen <n>` | Undo a `done`, then Stage 3 |
| `order <n> <n> ...` | Reorder milestones by their current numbers, then Stage 3 |
| `you-pick` | Accept every recommended answer in the charting round. Same meaning as the user saying "make the decisions" or "you pick" |

## Execution spine

1. Resolve the tracker and find the roadmap (Stage 1).
2. No roadmap: chart it (Stage 2) and stop.
3. Roadmap: apply any edit, reconcile status (Stage 3).
4. Report and hand off (Stage 4).

---

## Stage 1: Tracker and roadmap

Read `docs/agents/issue-tracker.md` when it exists. Its `Tracker:` line names the tracker and its `Adapter flags:` line gives the flags for the bundled script. Missing file: GitHub, no flags. On a GitHub Enterprise host, pass `GH_HOST=<host>` inline on every script call. Shell state does not persist between calls. On Linear or Jira, when the host exposes a connector for that tracker, use it for the same operations; otherwise run the script. Never mix the two in one run. For `local`, load `references/scratch.md` and treat `.scratch/roadmap.md` as the roadmap. For `other`, follow the tracker file's Conventions.

Find the roadmap in this order and stop at the first hit:

1. The `Roadmap:` line in the `## Agent skills` block of `CLAUDE.md` or `AGENTS.md`. Prefer the file containing the block; ties use `CLAUDE.md`. The value is a tracker id, an issue URL, or a local path.
2. The marker, across all states:

   ```bash
   bash "<SKILL_DIR>/scripts/tickets.sh" <adapter flags> find "Work kind: roadmap"
   ```

   One open hit is the roadmap. More than one open hit: list them and stop, because the pointer line is the only way to choose. Only closed hits count as no roadmap, and the report mentions them.

Read the roadmap with `view`. Confirm the exact body line `Work kind: roadmap`; an issue that lacks it is not the roadmap, whatever the pointer says. Say so and stop.

---

## Stage 2: Chart

Load `references/roadmap-shape.md` and `references/milestones.md`.

Interrogate the destination first, then the milestones, following `references/milestones.md`. Read `CONTEXT.md` and any ADRs when they exist and use the project's words. Stop when the destination is one or two lines and every milestone has a name and one outcome sentence. Everything too dim to name goes under **Not yet planned**.

Create the issue:

```bash
bash "<SKILL_DIR>/scripts/tickets.sh" <adapter flags> create "Roadmap: <destination in a few words>" <<'EOF_ROADMAP'
<body from references/roadmap-shape.md>
EOF_ROADMAP
```

Exit 3 means the token cannot write. Load `references/scratch.md` and keep the roadmap under `.scratch/`.

Then write the pointer. Add `Roadmap: <id or URL>` to the `## Agent skills` block of the file that holds it, after `Domain docs:` when that line exists and otherwise before `Peer reviewer:`, `Persona:`, and `Style:`. Change only that one line; keep every other line's text and order. The block is absent: create it in the existing instruction file, preferring `CLAUDE.md`, holding only this line.

Charting is one session. Do not chart a map for the first milestone here. Run Stage 4 with every milestone `planned` and stop.

---

## Stage 3: Reconcile

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

`add`, `done`, `reopen`, or `order` changes the **Milestones** section of the replacement body as `references/roadmap-shape.md` describes. `done` on a milestone whose derived status is not `done` writes a `Confirmed done:` line with the reason the user gave; `reopen` removes it. An edit that names a milestone number that does not exist stops without writing.

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
| `done` | A `Confirmed done:` line is present, or every map naming it is closed, at least one map or effort names it, and every effort naming it is closed |
| `building` | Every map naming it is closed and at least one effort naming it is open |
| `deciding` | At least one open map names it |
| `planned` | Nothing names it |

A milestone the previous body marked `done` by the rules alone, that now has an open member, goes back to `building` or `deciding`; only a `Confirmed done:` line holds. The **current** milestone is the first one that is not `done`.

For the current milestone only, fetch the detail Stage 4 needs: each open map's first frontier row with `map.sh frontier` on GitHub, or the tracker file's Wayfinding operations elsewhere, and each open effort's available ticket by the same reads portal uses: `children`, `view` on open members, and `blocked`. Never pass `--claim`.

### 3e. Write

Rewrite the body from the snapshot: the same sections in the same order, each milestone's status, its Maps and Efforts lines, and its Left line updated, and any **Not yet planned** line whose name now matches a milestone removed. Preserve every other line. Write under the guard:

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

---

## Stage 4: Report

Write the result as markdown, not as a code block. A cell holds one line, and links go in bare so the terminal renders them. Refer to milestones by name and issues by title with the link wrapped inside.

### Vision

| | |
|---|---|
| **Destination** | one line |
| **Milestones** | done/total, then the names in order with each status |
| **Current** | name and status, then maps closed/open and efforts delivered/open |
| **Left** | the current milestone's Left line |
| **Unattached** | count of maps and efforts naming no milestone, or `none` |
| **Unplanned** | count of Not yet planned lines, or `none` |

**Next step:** \<skill> on \<milestone or ticket with link>. \<One sentence on why.>

**Prompt:** `\<one line that starts it>`

Name any milestone whose status changed this run, in one sentence above the table. Next step is the first row that holds for the current milestone:

| Condition | Next step | Prompt |
|-----------|-----------|--------|
| An open map has a frontier ticket | `scry` on that ticket | `Resolve <ticket URL> on its map.` |
| An open effort has an available ticket | `cast` on that ticket | `Implement <ticket URL>, following its brief.` |
| A closed map has no effort | `conjure` on the map | `Use the completed planning map <map URL> to propose the implementation work, keeping the map as the planning source.` |
| An open effort has nothing available | `conjure` on the effort | `Check progress and close out the build effort at <parent URL> once the pending work is complete.` |
| The milestone is `planned` | `scry` for a new map | `Chart a map toward <milestone outcome>, serving milestone <name> on <roadmap URL>.` |
| Every milestone is `done` and nothing is unplanned | none | Say the destination is reached and omit the prompt |

The prompt is natural language that works whether or not the named skill is installed. Stop after the report. This skill does not hand off.

## References

| Reference | Load at | Purpose |
|-----------|---------|---------|
| `references/roadmap-shape.md` | Stage 2, Stage 3 | Roadmap body, the upward link, edits |
| `references/milestones.md` | Stage 2 | The charting interview at milestone grain |
| `references/scratch.md` | Stage 1 on local, Stage 2 on exit 3 | The roadmap as a file |
