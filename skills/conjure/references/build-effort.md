# Build effort

Load during Stage 1 when finding an existing effort, and Stage 3 when filing or resuming one.

## Parent shape

Create `Build: <implementation outcome>` with the category label only. Its body begins with `Work kind: build`. The parent is an index, so it never carries the ready-for-agent label or a decision-map label. If an existing parent carries a ready label, remove that label through the tracker contract before continuing.

```markdown
Work kind: build
Planning source: [<map or spec title>](<URL or path>)

## Destination

<observable implementation outcome and the evidence required to call it delivered>

## Scope

<what this effort delivers and what remains excluded>

## Build order

1. <accepted slice title>. Ticket: pending. After: none.
   Outcome: <acceptance criteria and proof>
2. <accepted slice title>. Ticket: pending. After: 1.
   Outcome: <acceptance criteria and proof>

## Next step

Finish filing the accepted slices, then work the first available ticket.
```

For a conversation source, put the agreed plan and its boundaries in the parent so a later session can recover it. For a planning map, read **Out of scope** too: distinguish implementation deferred until planning finished from features explicitly excluded from the build. Resolve any ambiguous build boundary before slicing.

## Find before create

Read the source body and all comments for a **Build effort** link or legacy **Build order**. Follow matching links and read their current state. Search the configured tracker, across open and closed issues, for build parents with this exact planning-source link and matching destination. For a spec or conversation, compare the scope and destination as well as the source. Also search tickets across all states for this exact source URL in `Builds toward:` or `Planning source:` lines. This recovers orphan flat tickets when filing stopped before the source comment was written. Use `find TEXT` through the tracker contract with the source URL or spec path as literal text, then read matching bodies to verify the provenance line and scope. For conversation sources, find by the recorded destination text. Connectors must exhaust pagination too. Search failure means discovery is incomplete, so report it instead of assuming there is no effort. Multiple plausible efforts require the user's choice.

A matching parent resumes in place. A closed parent gets a progress report; creating another effort requires a distinct requested destination. Legacy flat tickets can be adopted into a new parent after the accepted round, preserving their briefs and existing dependencies. Verify their current bodies and scope first; reuse completed slices too. Preserve the old map comment as history and add a link to the new parent.

```bash
bash "<SKILL_DIR>/scripts/tickets.sh" <adapter flags> find '<source URL or spec path>'
```

For local work, search the configured ticket directory and existing scratch efforts, including closed files, with the same provenance checks.

## File and resume

1. Save the entire accepted order, including acceptance criteria and edges, in the parent before creating children. Link the parent from the source issue immediately with a **Build effort** comment:

   ```markdown
   ## Build effort

   [Build: <outcome>](<parent URL>)
   ```

   Use `comment SOURCE_ID` through the tracker contract. A file source gets the parent link in a handoff section. A closed planning map stays closed.
2. Enumerate members with `children PARENT_ID` and read them, including closed tickets. Enumeration must include exact `Build parent:` links even when native attachment never succeeded; on a connector, search those links explicitly and union them with native children. Reconcile the parent's accepted order against member bodies and legacy links. A title alone is not proof that a slice exists. A ticket with a different parent requires resolving ownership before adoption.
3. Create only missing slices, with `Build parent: [<title>](<parent URL>)` and `Planning source: [<title>](<source URL or path>)` above the brief. This membership line makes a created ticket discoverable even if attachment fails. After a timed-out create, search and read matching tickets before retrying. If absence cannot be established, stop with the uncertainty and resume action.
4. Attach each ticket, then replace its pending entry with its title and link. Preserve the rest of the accepted order. Record successful writes before moving on. A failed attachment or update leaves filing incomplete; return the parent link and a prompt to resume it.
5. Wire edges after all slices have IDs. On resume, read existing dependencies and add only missing edges. Check every accepted slice has a ticket and every required edge exists before reporting filing complete.

```bash
bash "<SKILL_DIR>/scripts/tickets.sh" <adapter flags> attach CHILD_ID PARENT_ID
bash "<SKILL_DIR>/scripts/tickets.sh" <adapter flags> children PARENT_ID
```

`children` returns all members as `id<TAB>state<TAB>title<TAB>url`, including closed tickets. Native hierarchy and explicit membership both count. Failed or incomplete reads stop reconciliation. On a connector, perform the equivalent exhaustive reads and attachment. A tracker without a compatible native parent uses explicit membership links, with the ordered index on the parent. Local files use the same structure from `references/scratch.md`.

## Guard parent edits

Before editing the order or next step, save the raw body and prepare the replacement from that snapshot. Abort if a body read fails. Use a private temporary file and record its absolute path because shell state does not persist between calls.

```bash
snapshot_path=$(mktemp)
if ! bash "<SKILL_DIR>/scripts/tickets.sh" <adapter flags> body PARENT_ID > "$snapshot_path"; then
  rm -f "$snapshot_path"
  exit 1
fi
printf 'original_body=%s\n' "$snapshot_path"
```

```bash
bash "<SKILL_DIR>/scripts/tickets.sh" <adapter flags> update-body PARENT_ID --expected-body '<recorded absolute snapshot path>' <<'EOF_BODY'
<replacement derived from the snapshot>
EOF_BODY
```

Delete the snapshot after the guarded update. A mismatch requires rereading and reconciling; never overwrite another session's changes. Connectors and local files must compare the original immediately before writing too. The comparison does not eliminate the residual race between comparison and write, so re-read and verify the result.
