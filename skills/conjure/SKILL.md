---
name: conjure
description: "Turn a finished plan, spec, or decision map into a build effort with ready-for-agent tickets, or resume its filing and check progress. Use when asked to file the build tickets, break this spec into issues, turn the plan into tickets, slice the work, resume filing build tickets, check progress and close out a build effort, or /conjure."
argument-hint: "[map or build number | issue URL | spec path | blank for the plan in this conversation] [you-pick]"
disable-model-invocation: true
---

<!-- BEGIN MANA PERSONA -->
## Persona at invocation

Before conversational narration, read `Persona:` and `Style:` in the active project's `## Agent skills` block from `CLAUDE.md` or `AGENTS.md`. Prefer the file containing the block, then an existing file; ties use `CLAUDE.md`. A symlink pair is one file. Read the saved value anew on each invocation, including from a subdirectory using the project root. No accessible project or no line means ordinary behavior. Do not search another project or global settings for this preference.

During the `Persona at invocation` stage, `archmage` on either line loads this skill's own [references/archmage.md](references/archmage.md) for the active workflow. `off` or an absent value leaves ordinary behavior active. An unknown value leaves ordinary behavior active and gets a brief explanation when conversational output is allowed; it does not stop the work. Explicit conversation instructions override the saved voice without writing settings. A request to enable Archmage for this workflow also loads the local reference.

Apply the voice only to lead-agent conversation. Deliverables, specialist roles, reply-only responses, and JSON-only output retain their contracts, with no added narration. End the persona with this workflow unless the user requests otherwise or a `Style:` line names `archmage`, which keeps the voice on for the whole session.
<!-- END MANA PERSONA -->

# Conjure

Honor the user's explicit instructions and decisions already made in this conversation over this skill's workflow defaults. A rule this file states with never, or as read-only, is a gate: it holds whatever the conversation says, and an instruction to cross one is declined and reported. Continue authorized work; ask only about unresolved choices that would materially change the result. Preparing or reviewing work does not authorize publishing it.

If a skill rule requires a pause or leaves requested work unfinished, name and link to the exact SKILL.md and quote the rule. Then explain what decision or prerequisite is missing. Distinguish a required gate from your interpretation.

The deciding is done. A map, a spec, or the plan in this conversation says what should be true. This skill slices that into build tickets sized for one session each, writes a brief on every one, and tracks delivery under a separate build parent. A closed map is the planning source; the build parent owns the implementation destination.

## Operating principles

- **Decisions first.** A ticket is filed only when its question is already answered. An open decision goes back to the person, never into a brief.
- **One session per ticket.** A slice that needs two sessions is two tickets with a blocking edge.
- **The brief is the contract.** A later build session reads the brief and nothing else. Write it for a reader who has none of this conversation.
- **Refer by name.** In anything a person reads, use the ticket title with the link wrapped inside it.
- **Write to the tracker through the contract.** On Linear or Jira, use the host's connector for the operations below when one is present. Otherwise run `scripts/tickets.sh`. GitHub always goes through the script. Never write the tracker any other way.

`<SKILL_DIR>` is the absolute directory this SKILL.md lives in. Substitute the real path every time it appears. Do not assign it to a shell variable first: a sandboxed or worktree-isolated session refuses `bash "$VAR/script.sh"` because it cannot resolve the path to read the script.

## Scripts

`scripts/tickets.sh` creates tickets, labels, blocking edges, and comments on GitHub (`git` and `gh` only), Linear, or Jira (`python3` and the tracker's environment variables). Exit 3 means the token cannot write. `tickets.sh -h` prints usage.

## Arguments

Parse tokens, then treat the remainder as the source.

| Token | Effect |
|-------|--------|
| `you-pick` | Accept every recommended slice and edge in the Stage 2 round. Same meaning as the user saying "make the decisions" or "you pick". |

| Input | Source |
|-------|--------|
| none | The plan or spec already in this conversation. If none is obvious, stop and ask. |
| number or issue URL | Read that issue. A body with the exact line `Work kind: build` identifies a build parent to resume. Labelled `scry:map` (or `wayfinder:map`): the planning source. Any other issue: its body is the spec. |
| a path | Read the file. The exact line `Work kind: build` identifies a local build parent; otherwise it is the spec |

## Execution spine

1. Load the source and find existing implementation work (Stage 1). A build parent resumes its accepted order or reports progress.
2. Slice it and agree the order (Stage 2).
3. Create or reuse the build parent, file missing tickets, and wire the edges (Stage 3).
4. Check progress and give the next action (Stage 4).

---

## Tracker

Read `docs/agents/issue-tracker.md` when it exists. Its `Tracker:` line names the tracker and its `Adapter flags:` line gives the flags for the bundled script. Missing file: GitHub, no flags. On a GitHub Enterprise host, pass `GH_HOST=<host>` inline too.

The operations below are `view`, `find`, `body`, `update-body`, `ensure-labels`, `create`, `attach`, `children`, `wire`, `label`, `comment`, and `close`. Source discovery uses `find TEXT` across all states; verify matching bodies before reusing work. On Linear or Jira, when the host exposes a connector for that tracker, use it for them; it is already authenticated. Inside an Orca worktree (`ORCA_WORKTREE_ID` is set and `command -v orca` succeeds), `orca linear` is such a connector for Linear; `orca linear --help` lists its operations. Otherwise run the script with the adapter flags. GitHub always goes through the script. Never mix the two in one run. For `local`, write the tickets as `references/scratch.md` describes. For `other`, follow the tracker file's Conventions by hand.

## Stage 1: Load

Load `references/build-effort.md`. A build parent resumes the saved order: reconcile existing tickets in Stage 3 when filing is incomplete, otherwise go to Stage 4. A request only to inspect progress goes directly to Stage 4 even if filing is incomplete. Reopening the slice round is necessary only when scope or accepted slices change.

**A map.** Fetch it:

```bash
bash "<SKILL_DIR>/scripts/tickets.sh" <adapter flags> view ID
```

`ID` is a tracker id or a GitHub, Linear, or Jira issue URL; the script extracts the id. Read Destination, Notes, Decisions so far, Out of scope, Completion, Next step, and every owning document Notes names. Read all source comments. Closed maps are valid inputs and remain closed. Then enumerate native children with `children MAP_ID` and union them with exact fallback membership from the tracker file's Wayfinding operations. On GitHub, also use `find "Part of #MAP_ID"` and read matching bodies to verify the exact map number; a mention or a longer number does not establish membership. On a local map, read every linked decision-ticket file. Read every open child's labels. An open decision child labelled `scry:*` or `wayfinder:*` means deciding is still pending. Stop and name those tickets. An incomplete child read also stops the workflow. Review unresolved in-scope fog and the owning documents even when the map is closed; closure alone does not establish that the source is ready to build from.

**A spec path or another issue.** Read it in full.

**Blank.** Use the plan in this conversation.

Find an existing build effort or legacy build order using `references/build-effort.md` before proposing new tickets. Reuse matching work.

Read `CONTEXT.md` when it exists, and any ADR in the area. Use the project's words in every title and brief.

Resolve the label strings. When `docs/agents/triage-labels.md` exists, read it and take the strings it maps for `bug`, `enhancement`, and `ready-for-agent`. Missing file: the string equals the role name.

Write two lines before slicing:

```
Destination: <what is true when every ticket is closed>
Labels: <category string>, <ready string>
```

## Stage 2: Slice

Load `references/slicing.md` and follow it. Present the slices as one round: each with a title, a one-line summary, and the tickets it waits on, plus a recommended order. Wait for the answer. `you-pick` accepts the recommendations.

If the source still has an open decision that no slice can avoid, stop here and say what needs deciding.

## Stage 3: File

Load `references/agent-brief.md`. Ensure the labels exist once per session:

```bash
bash "<SKILL_DIR>/scripts/tickets.sh" <adapter flags> ensure-labels --color d73a4a <category strings>
bash "<SKILL_DIR>/scripts/tickets.sh" <adapter flags> ensure-labels --color 0e8a16 <ready string>
```

Follow `references/build-effort.md` to create or reuse the parent and persist the accepted order. Use the category label for the parent, and category plus ready labels for its children. Attach build tickets only to the build parent.

```bash
bash "<SKILL_DIR>/scripts/tickets.sh" <adapter flags> create "Build: <outcome>" --label <category string> <<'EOF_PARENT'
<parent body from references/build-effort.md>
EOF_PARENT
bash "<SKILL_DIR>/scripts/tickets.sh" <adapter flags> create "<slice title>" --label <category string> --label <ready string> <<'EOF_TICKET'
Build parent: [<build title>](<build URL>)
Planning source: [<source title>](<source URL or path>)

<brief from references/agent-brief.md>
EOF_TICKET
```

Create only missing slices. After attaching and recording each child, wire missing dependencies in a second pass:

```bash
bash "<SKILL_DIR>/scripts/tickets.sh" <adapter flags> wire CHILD_ID BLOCKER_ID
```

Exit 3 means this token cannot write issues. Load `references/scratch.md` and preserve any tickets already created in the local effort. Return its path as the next action.

## Stage 4: Progress

Load `references/build-progress.md`, reconcile the accepted order, and give the next action. A new effort normally points to its first available implementation ticket. Revisiting a delivered effort can close its build parent after the evidence checks. The planning map remains closed.

## Report

```
Conjure: <destination in a few words>
Build effort: <parent title and URL or file path>
Filed: <n new> tickets; reused: <n existing>
Order:
  1. <title> (<url>)
  2. <title> (<url>), after 1
Unspecified: <anything the source left open, or none>
Progress: <available work | filing incomplete | awaiting review | blocked | delivered>
Next step: <copyable prompt with the concrete ticket or parent link, or no further work required>
```

## References

| Reference | Load at | Purpose |
|-----------|---------|---------|
| `references/build-effort.md` | Stage 1 and Stage 3 | Parent shape, discovery, resumable filing, and guarded edits |
| `references/build-progress.md` | Stage 4 | Evidence checks, closeout, and next action |
| `references/slicing.md` | Stage 2 | What a one-session slice is, and the round that agrees the order |
| `references/agent-brief.md` | Stage 3 | The brief a build session reads |
| `references/scratch.md` | Stage 3, exit 3 only | Local tickets when GitHub writes fail |
