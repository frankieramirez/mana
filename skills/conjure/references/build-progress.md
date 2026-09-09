# Build progress

Load when revisiting a build parent or after a build session for a ticket carrying a **Build parent** link. Use the configured tracker contract for every operation. This check runs during sessions only.

## Reconcile

Read the parent and its accepted **Build order**, then enumerate every member, including closed or canceled tickets:

```bash
bash "<SKILL_DIR>/scripts/tickets.sh" <adapter flags> view PARENT_ID
bash "<SKILL_DIR>/scripts/tickets.sh" <adapter flags> children PARENT_ID
```

Read each member's current status and resolution, its blockers and assignee, and linked PR state. Include tickets listed in the accepted order even if attachment failed. Missing slices, unreadable tickets, failed enumeration, or uncertain PR state leave the effort incomplete. An empty member list is not proof of completion. Local files use the same checks against the parent index and ticket files.

Choose the first open, ready, unclaimed ticket in build order whose blockers are complete. A canceled blocker needs evidence that its requirement was satisfied or explicitly dropped before its dependents become available. Scope the choice to this effort; a global `next` result can belong to another project effort.

## Closeout

An open PR means review is pending, even if its ticket has been manually closed. A closed unmerged PR does not prove delivery. For each canceled, duplicate, invalidated, or otherwise abandoned ticket, verify that its requirement was delivered elsewhere or explicitly removed from scope. Read the replacement ticket where applicable. Keep unresolved requirements visible.

Close the parent only when every accepted slice is accounted for, every required ticket is complete, and evidence satisfies **Destination** under **Scope**. Passing tests on an unmerged branch alone does not establish delivery. For a local or `no-pr` workflow, use the project's agreed delivery criterion; when none is recorded, report what remains to establish delivery.

For an open parent that meets those conditions, record a brief **Completion** comment with evidence links and **Next step**. Reuse an existing completion comment when retrying a failed close. Immediately re-read the parent and members before closing; changed scope or reopened work requires another reconciliation. Then close and confirm its final state:

```bash
bash "<SKILL_DIR>/scripts/tickets.sh" <adapter flags> close PARENT_ID
bash "<SKILL_DIR>/scripts/tickets.sh" <adapter flags> view PARENT_ID
```

The tracker cannot make the evidence review and close atomic. Report a concurrent change if verification reveals one. A closed parent gets a read-only status report; if its requirements are now unmet, identify them and offer an explicit action to reconcile or reopen the effort. Never claim delivery solely from the parent's closed state.

## Report and next action

Finish with the build parent's linked title, the current result, and one concrete next action:

- Available ticket: `Implement <ticket URL or file path>, following its brief.`
- Filing incomplete: `Resume filing the accepted build tickets for <parent URL or file path>, reusing existing tickets.`
- Review pending: name the PR links and say what review or merge action remains. Include `Check progress and close out the build effort at <parent URL or file path> once the pending work is complete.`
- Blocked or uncertain: name the unmet requirement or failed read and provide a prompt to resolve or recheck it.
- Delivered: say the effort is complete. Name a documented follow-up only when one exists; otherwise say no further work is required for this destination.

Update an open parent's **Next step** when it changes. Save a fresh raw body with `body PARENT_ID` to a private temporary file, derive the replacement from that snapshot, then write it with the guard. The replacement body goes on stdin; the snapshot path only guards the write:

```bash
bash "<SKILL_DIR>/scripts/tickets.sh" <adapter flags> update-body PARENT_ID --expected-body '<recorded absolute snapshot path>' <<'EOF_BODY'
<replacement derived from the snapshot>
EOF_BODY
```

Abort on a read failure or mismatch and delete the snapshot after the update; on a connector or local file, compare before writing. Preserve all other sections, and re-read after writing. An unchanged result needs no tracker write. A ticket lacking a build-parent link follows its existing workflow; legacy planning-source links alone do not authorize closing the planning map as a build parent.
