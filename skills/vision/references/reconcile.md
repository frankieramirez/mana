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

Also discover work that predates the roadmap: `list scry:map`, `list wayfinder:map`, and `find "Work kind: build"`. Search relevant milestone terms with `find` for closed planning work and read plausible candidates' bodies. Deduplicate by issue id. Inspect their scope and evidence against milestone criteria; a matching title alone does not establish membership. Closed historical work may establish the baseline without becoming a member.

For an authorized creation or update, add the `Milestone:` line to a clear match using `update-body --expected-body` with its own snapshot. Preserve the rest of that body and reread after writing. Do not replace a link to another roadmap or milestone automatically. Ambiguous matches, work spanning milestones, and failed link writes are reported by title with the decision needed; never count a proposed or failed link as persisted membership. A draft or report-only request proposes these associations without editing members. Do not create replacement planning for a plausible existing match while its association is unresolved.

A failed required read leaves the saved roadmap unchanged. Report what could not be established. Member linking is not atomic: if a later operation fails, report links already saved and retry discovery next run. On a concurrent member edit, reread once and retry only if the association remains clear; a second mismatch leaves that link unresolved.

### 3d. Derive status

First follow `Planning source:` links: for each closed member map, run `find "<map URL>"` and verify each hit's body. An effort with that exact planning source and no conflicting `Milestone:` line also serves the milestone; record it once. Conflicting associations remain unresolved. Do this before deriving status, so existing implementation is not overlooked.

Read the milestone's completion criteria against delivered evidence in linked work and relevant owning documents. Record which criteria are satisfied with sources and what is missing. Closed issues alone do not prove the outcome, and one effort need not cover the entire milestone. Legacy milestones without criteria keep their outcome as the scope; draft criteria from it using `milestones.md`, flag material ambiguity, and never infer completion from closure alone.

Apply the first matching row:

| Status | Rule |
|--------|------|
| `done` | A `Confirmed done:` override exists, or every completion criterion has verified evidence, no member work remains open, and no unresolved association could change that assessment |
| `deciding` | At least one member map is open |
| `building` | An effort is open, a closed map needs implementation, or evidence identifies delivery still missing |
| `verifying` | Member work is closed or the outcome is reported delivered, but completion evidence is incomplete |
| `planned` | No work or delivery evidence establishes activity yet |

Use `building` for an identified delivery gap only when work has started; a wholly unstarted milestone stays `planned`. An open map can coexist with building work: describe both in the assessment. Unknown evidence is not a demonstrated failure. Previously derived `done` can reopen when evidence or member state changes; only an explicit confirmation holds. `reopen` removes that override and recomputes status, so verified completion may still yield done.

The **current** milestone is the first not done. Also identify consequential blockers or independent work elsewhere when they affect the recommended next action. Unresolved associations take precedence over recommending duplicate planning.

For the recommended action, fetch the details needed by `references/report.md`. On GitHub, read each open map's frontier:

```bash
bash "<SKILL_DIR>/scripts/map.sh" frontier MAP_ID OWNER/REPO
```

Use the configured repository, or omit `OWNER/REPO` to resolve it from this checkout. On GitHub Enterprise, pass `GH_HOST=<host>` inline. Elsewhere use the tracker file's Wayfinding operations. The first frontier row is the map's next ticket; an empty frontier routes to inspecting the open map itself.

For each open effort, use the bundled ticket script with the resolved adapter flags to `view PARENT_ID`, `children PARENT_ID`, and `view MEMBER_ID` for each open member. Read the label for the `ready-for-agent` role from `docs/agents/triage-labels.md`, defaulting to `ready-for-agent`. Use the parent's **Build order**. Prefer a member already assigned to the current tracker user; resolve that identity with `tickets.sh check` and do not assume an unknown identity owns a ticket. Otherwise choose the first unassigned ready member in build order whose `blocked MEMBER_ID` returns 1 (no open blockers). Exit 0 means blocked; other failures make availability unknown. Read operations do not claim tickets or change member state.

### 3e. Write

Update the snapshot's milestone statuses and verified links, completion evidence, and concrete Left lines. Refresh **Where we stand** from inspected evidence; preserve the user's scope and reasoning. Remove empty Maps and Efforts fields. Remove an unplanned line only when its scope is accounted for by a milestone. Inspect evidence for a milestone before changing its completion status; fetch detailed frontier or build-ticket availability only for the recommended next action.

Keep legacy Notes and other user content unless migrating it without losing meaning. Ensure the remote `roadmap` label before removing a legacy marker. Skip a write when nothing changed. For report-only requests that exclude writes, report the derived assessment and proposed updates without saving them. Otherwise write under the guard:

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

