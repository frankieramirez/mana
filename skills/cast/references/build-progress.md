# Build progress

Load when revisiting a build parent or after a build session for a ticket carrying a **Build parent** link. Use the configured tracker contract for every operation. This check runs during sessions only.

## Reconcile

Read the parent and its accepted **Build order**, then enumerate every member, including closed or canceled tickets:

```bash
bash "<SKILL_DIR>/scripts/tickets.sh" <adapter flags> view PARENT_ID
bash "<SKILL_DIR>/scripts/tickets.sh" <adapter flags> children PARENT_ID
```

Read each member's current status and resolution, its blockers and assignee, and linked PR state. Blockers come from the script, never from a guess at the body:

```bash
bash "<SKILL_DIR>/scripts/tickets.sh" <adapter flags> blocked MEMBER_ID
```

It prints the open blockers one per line and exits 1 when there are none. Include tickets listed in the accepted order even if attachment failed. Missing slices, unreadable tickets, failed enumeration, or uncertain PR state leave the effort incomplete. An empty member list is not proof of completion. Local files use the same checks against the parent index and ticket files.

Choose the first open, ready, unclaimed ticket in build order whose blockers are complete. A canceled blocker needs evidence that its requirement was satisfied or explicitly dropped before its dependents become available. Scope the choice to this effort; a global `next` result can belong to another project effort.

## Closeout

An open PR means review is pending, even if its ticket has been manually closed. A closed unmerged PR does not prove delivery. For each canceled, duplicate, invalidated, or otherwise abandoned ticket, verify that its requirement was delivered elsewhere or explicitly removed from scope. Read the replacement ticket where applicable. Keep unresolved requirements visible.

Close the parent only when every accepted slice is accounted for, every required ticket is complete, and evidence satisfies **Destination** under **Scope**. Passing tests on an unmerged branch alone does not establish delivery. For a local or `no-pr` workflow, use the project's agreed delivery criterion; when none is recorded, report what remains to establish delivery. When every member is closed and the evidence still falls short, follow **Leftover evidence** below.

For an open parent that meets those conditions, record a brief **Completion** comment with evidence links and **Next step**. Reuse an existing completion comment when retrying a failed close. Immediately re-read the parent and members before closing; changed scope or reopened work requires another reconciliation. Then close and confirm its final state:

```bash
bash "<SKILL_DIR>/scripts/tickets.sh" <adapter flags> close PARENT_ID
bash "<SKILL_DIR>/scripts/tickets.sh" <adapter flags> view PARENT_ID
```

The tracker cannot make the evidence review and close atomic. Report a concurrent change if verification reveals one. A closed parent gets a read-only status report; if its requirements are now unmet, identify them and offer an explicit action to reconcile or reopen the effort. Never claim delivery solely from the parent's closed state.

## Leftover evidence

Unmet **Destination** evidence always gets an open ticket. It runs when every member of an open parent is closed and accounted for with no PR awaiting review, yet the evidence falls short of **Destination**. Prose in **Next step** alone strands the effort there: the tracker's progress count reads complete, and `next` never offers the work. Treat this case as leftover evidence, never as blocked.

Name each unmet piece of evidence and what is missing from it, such as a run that never passed or checks that never ran on one revision. Its owner is the member whose **Outcome** in **Build order** names that evidence. Load `references/agent-brief.md` for the briefs below. Resolve the ready string as the one `docs/agents/triage-labels.md` maps for `ready-for-agent`, else `ready-for-agent`; the category string is the label the parent carries.

These writes need the same authorization as closing the parent. Without it, because the request is read-only or the script exits 3, write nothing: report each exact action, naming the member to reopen and the brief to post, or the ticket to file with its labels and brief.

**A closed member owns it.** Reopen that member. First post a comment headed `## Agent Brief`, following `references/agent-brief.md`, so the brief is in place before `next` can offer the ticket. Its current behavior names what the closed work delivered and why the ticket closed before its evidence existed, such as a PR whose closing keyword closed it on merge. Its acceptance criteria are the unmet evidence. A build session reads the latest `## Agent Brief` comment first, so this comment becomes the contract. `reopen` also clears the assignee left from the earlier work, so `next` can offer the ticket. Through a Linear or Jira connector, `reopen` means: leave a ticket that is already open alone, assignee included; otherwise move it to the first To Do state, else a backlog state on Linear or an In Progress status on Jira, then clear the assignee and read it again. Restore the ready label when it is missing.

```bash
bash "<SKILL_DIR>/scripts/tickets.sh" <adapter flags> comment MEMBER_ID <<'EOF_BRIEF'
<brief for the unmet evidence, from references/agent-brief.md>
EOF_BRIEF
bash "<SKILL_DIR>/scripts/tickets.sh" <adapter flags> reopen MEMBER_ID
bash "<SKILL_DIR>/scripts/tickets.sh" <adapter flags> label MEMBER_ID --add <ready string>
```

**No member owns it.** File a new member under the parent, with the parent's `Planning source:` line copied above the brief:

```bash
bash "<SKILL_DIR>/scripts/tickets.sh" <adapter flags> create "<title>" --label <category string> --label <ready string> <<'EOF_TICKET'
Build parent: [<build title>](<build URL>)
Planning source: [<source title>](<source URL or path>)

<brief from references/agent-brief.md>
EOF_TICKET
bash "<SKILL_DIR>/scripts/tickets.sh" <adapter flags> attach NEW_ID PARENT_ID
```

Append it to **Build order** as the next entry, with its ticket link, an `After:` naming the members it needs, and an `Outcome:` stating the evidence. Use the guarded parent edit under **Report and next action**. Wire it to any member reopened in this pass that it needs:

```bash
bash "<SKILL_DIR>/scripts/tickets.sh" <adapter flags> wire NEW_ID MEMBER_ID
```

Re-read each reopened or filed ticket and the parent after writing. A failed write leaves the remaining actions in the report and the parent's **Next step**. The parent stays open, so a later check returns here once every member is closed again. On local files, reopening sets the ticket file's `Status:` back to `ready-for-agent` and appends the brief under `## Comments`, and a new member is the next numbered ticket file in the effort, with the same header lines as its siblings.

## Report and next action

Finish with the build parent's linked title, the current result, and one concrete next action:

- Available ticket: `Implement <ticket URL or file path>, following its brief.`
- Filing incomplete: `Resume filing the accepted build tickets for <parent URL or file path>, reusing existing tickets.`
- Review pending: name the PR links and say what review or merge action remains. Include `Check progress and close out the build effort at <parent URL or file path> once the pending work is complete.`
- Leftover evidence: the first reopened or filed ticket in build order whose blockers are complete, as `Implement <ticket URL or file path>, following its brief.` Without write authorization, list each action from **Leftover evidence** and give `Check progress and close out the build effort at <parent URL or file path>, reopening or filing tickets for its unmet evidence.`
- Blocked or uncertain: name the unmet requirement or failed read and provide a prompt to resolve or recheck it. Unmet evidence after every member has closed is leftover evidence, never this case.
- Delivered: say the effort is complete. Name a documented follow-up only when one exists; otherwise say no further work is required for this destination.

Update an open parent's **Next step** when it changes. Save a fresh raw body with `body PARENT_ID` to a private temporary file, derive the replacement from that snapshot, then write it with the guard. The replacement body goes on stdin; the snapshot path only guards the write:

```bash
bash "<SKILL_DIR>/scripts/tickets.sh" <adapter flags> update-body PARENT_ID --expected-body '<recorded absolute snapshot path>' <<'EOF_BODY'
<replacement derived from the snapshot>
EOF_BODY
```

Abort on a read failure or mismatch and delete the snapshot after the update; on a connector or local file, compare before writing. Preserve all other sections, and re-read after writing. An unchanged result needs no tracker write. A ticket lacking a build-parent link follows its existing workflow; legacy planning-source links alone do not authorize closing the planning map as a build parent.
