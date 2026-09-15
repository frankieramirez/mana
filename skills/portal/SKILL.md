---
name: portal
description: "Read the tracker and the current branch, say which skill to run next and on which ticket, then run it when you say yes. Use when asked what to do next, what is next, where do I go from here, route this ticket, which skill should I use on this issue, pick up where I left off, or /portal."
argument-hint: "[blank for the whole board | issue id | issue URL | map or build number] [go]"
disable-model-invocation: true
---

<!-- BEGIN MANA PERSONA -->
## Persona at invocation

Before conversational narration, read `Persona:` and `Style:` in the active project's `## Agent skills` block from `CLAUDE.md` or `AGENTS.md`. Prefer the file containing the block, then an existing file; ties use `CLAUDE.md`. A symlink pair is one file. Read the saved value anew on each invocation, including from a subdirectory using the project root. No accessible project or no line means ordinary behavior. Do not search another project or global settings for this preference.

During the `Persona at invocation` stage, `archmage` on either line loads this skill's own [references/archmage.md](references/archmage.md) for the active workflow. `off` or an absent value leaves ordinary behavior active. An unknown value leaves ordinary behavior active and gets a brief explanation when conversational output is allowed; it does not stop the work. Explicit conversation instructions override the saved voice without writing settings. A request to enable Archmage for this workflow also loads the local reference.

Apply the voice only to lead-agent conversation. Deliverables, specialist roles, reply-only responses, and JSON-only output retain their contracts, with no added narration. End the persona with this workflow unless the user requests otherwise or a `Style:` line names `archmage`, which keeps the voice on for the whole session.
<!-- END MANA PERSONA -->

# Portal

Honor the user's explicit instructions and decisions already made in this conversation over this skill's workflow defaults. A rule this file states with never, or as read-only, is a gate: it holds whatever the conversation says, and an instruction to cross one is declined and reported. Continue authorized work; ask only about unresolved choices that would materially change the result. Preparing or reviewing work does not authorize publishing it.

If a skill rule requires a pause or leaves requested work unfinished, name and link to the exact SKILL.md and quote the rule. Then explain what decision or prerequisite is missing. Distinguish a required gate from your interpretation.

Portal reads the board and opens the way to the one thing to do next. Its own reads are read-only: it never claims, labels, comments on, or closes a ticket and never creates a branch. It ends by asking whether to step through, and on a yes it hands the session to the routed skill with the ticket already chosen. Portal never stops at a report.

The other skills each take one kind of input and do one job. Portal is the door you walk through when you do not know which one applies, or when you want the board to tell you what is next.

`<SKILL_DIR>` is the absolute directory this SKILL.md lives in. Substitute the real path every time it appears. Do not assign it to a shell variable first: a sandboxed or worktree-isolated session refuses `bash "$VAR/script.sh"` because it cannot resolve the path to read the script.

## Arguments

| Input | Effect |
|-------|--------|
| none | Read the whole board and the current branch, then route (Stage 2) |
| issue id or URL | Route that one issue (Stage 3) |
| `go` | Skip the Stage 5 question and step through the route at once. Same meaning as the user saying "just do it" or "go" |

An id is whatever the tracker uses (`42`, `ENG-42`, `PLAT-42`). A pull request number counts as an id when the tracker shares a number space with pull requests.

## Execution spine

1. Resolve the tracker and the label strings (Stage 1).
2. Blank argument: Stage 2. An id or URL: Stage 3.
3. Write the report (Stage 4).
4. Ask whether to step through, then hand off to the routed skill (Stage 5).

---

## Stage 1: Tracker

Read `docs/agents/issue-tracker.md` when it exists. Its `Tracker:` line names the tracker and its `Adapter flags:` line gives the flags for the bundled script. Missing file: GitHub, no flags. On a GitHub Enterprise host, pass `GH_HOST=<host>` inline on every script call. Shell state does not persist between calls.

Portal uses only the read side of `scripts/tickets.sh`: `list`, `view`, `body`, `children`, `find`, `blocked`, and `next` without `--claim`. Map reads use `scripts/map.sh` on GitHub (`frontier`, `children`, `view`, `parent`). On another tracker, the tracker file's "Wayfinding operations" section says what a map and a frontier are there; read them through that connector or API. For `local`, tickets are files: read them directly. For `other`, follow the tracker file's Conventions.

Resolve the label strings once. When `docs/agents/triage-labels.md` exists, take the right-hand column for `ready-for-agent`, `needs-triage`, `needs-info`, and `ready-for-human`; otherwise those are the strings. Map labels are `scry:map` and `scry:<type>`, with `wayfinder:map` and `wayfinder:<type>` as legacy spellings that mean the same thing.

---

## Stage 2: Read the board

Gather every signal below before choosing. Each read is cheap and the order of precedence in 2b needs all of them. A read that fails is reported as unknown in the report, never treated as empty.

### 2a. Signals

**The branch.** The current branch, whether it has uncommitted or unpushed work, and whether it has an open pull request:

```bash
git rev-parse --abbrev-ref HEAD
git status --porcelain
gh pr view --json number,title,url,state,isDraft,reviewDecision,mergeable,statusCheckRollup --jq '[.number,.title,.url,.state,.isDraft,.reviewDecision,.mergeable,([.statusCheckRollup[]?.conclusion] | join(","))] | @tsv'
```

A failing `gh pr view` means no pull request for this branch. Unpushed commits: `git log --oneline @{upstream}..HEAD` when an upstream exists.

**Open maps.** Every open map and its frontier:

```bash
bash "<SKILL_DIR>/scripts/tickets.sh" <adapter flags> list scry:map
bash "<SKILL_DIR>/scripts/tickets.sh" <adapter flags> list wayfinder:map
GH_HOST=<host> bash "<SKILL_DIR>/scripts/map.sh" frontier MAP_NUMBER
```

The first frontier row is the ticket a walk would take: open, unblocked, unclaimed, in map order.

**Build efforts.** Every issue whose body carries the exact line `Work kind: build`, then the members of each open one:

```bash
bash "<SKILL_DIR>/scripts/tickets.sh" <adapter flags> find "Work kind: build"
bash "<SKILL_DIR>/scripts/tickets.sh" <adapter flags> children PARENT_ID
```

For an open effort, count members by state. A member already assigned to the person driving this session is the effort's available ticket before anything else, since it is work they have started; say it is already theirs. Otherwise, for each open member with no assignee that carries the ready label, run `blocked MEMBER_ID`; the first one with no open blocker, in build order, is the available ticket. Read the parent's **Build order** section with `view PARENT_ID` when the child listing does not give the order.

**Ready tickets.** The oldest ready ticket nobody holds and nothing blocks, without claiming it:

```bash
bash "<SKILL_DIR>/scripts/tickets.sh" <adapter flags> next <ready string>
```

Never pass `--claim` here. Portal decides; the routed skill claims.

**The inbox.** Issues waiting on triage:

```bash
bash "<SKILL_DIR>/scripts/tickets.sh" <adapter flags> list <needs-triage string>
bash "<SKILL_DIR>/scripts/tickets.sh" <adapter flags> list --unlabeled
```

**Finished maps with no build effort.** Only when there is no open map, no open effort, and nothing ready. A closed map is one the `find` for `## Not yet specified` returns in a closed state. For each, search for its URL in `Planning source:` and `Builds toward:` lines with `find`; a map with no hit is a plan nobody has sliced.

### 2b. Choose the route

Take the first row whose condition holds. Report the others as context, never as a second recommendation.

| Condition | Route to | Why it comes first |
|-----------|----------|--------------------|
| The branch's open PR has changes requested, unresolved review feedback, or failing checks | `remedy` for one pass over the feedback, or `ward` to stay with the PR until it merges. Prefer `ward` when checks are still running or the PR is expected to gather more feedback; prefer `remedy` for a batch that is already in | Work someone already reviewed is the closest to done |
| The branch has uncommitted or unpushed work and no PR | `scan` on the branch, then `reveal` to open the PR | Unfinished work on the branch is lost context if it sits |
| An open map has a frontier ticket | `scry` on that ticket | A decision blocks every build ticket behind it |
| An open build effort has an available ticket | `cast` on that ticket, by id | Build order wins over the global queue, since a global `next` can belong to another effort |
| A ready ticket is available and no effort claims it | `cast` on that ticket, by id | The board says it is ready |
| An open build effort has no available ticket | `conjure` on the effort, for a progress check. Name what holds it: open PRs awaiting review, claimed tickets and who holds them, and the blockers of every blocked ticket. When a blocker is itself a ready unblocked ticket, route to `cast` on the blocker instead | Something is pending and the person needs to see what |
| The inbox has issues | `sift` | Untriaged reports become ready tickets |
| A closed map has no build effort | `conjure` on the map | The plan is done and nobody has sliced it |
| None of the above | Nothing to route. Say the board is clear and that `scry` charts a new map from a loose idea | |

When the inbox has issues and a higher row also holds, mention the inbox count in the report so it does not rot, and keep the single route.

---

## Stage 3: Route one issue

Read it first:

```bash
bash "<SKILL_DIR>/scripts/tickets.sh" <adapter flags> view ID
```

When `view` fails and the tracker shares numbers with pull requests, try `gh pr view ID --json number,title,url,state,reviewDecision,statusCheckRollup`. Classify from labels, assignees, state, and body lines, in this order:

| What it is | How to tell | Route to |
|------------|-------------|----------|
| A pull request | `view` fails, `gh pr view` succeeds | `scan` when nobody has reviewed it, `remedy` when feedback is waiting, `ward` to attend it until merge |
| A map | Label `scry:map` or `wayfinder:map` | Open: `scry` on the first frontier row, or on the map itself when the frontier is empty, so scry can report what keeps it open. Closed: search `Planning source:` and `Builds toward:` for the map URL with `find`; an effort found routes to `cast` on its available ticket or `conjure` for its progress; none found routes to `conjure` on the map |
| A map ticket | Label `scry:<type>` or `wayfinder:<type>` | Open and unclaimed: `scry` on it. Claimed by someone else: say who holds it and stop. Closed: route its parent map instead (`map.sh parent ID`) |
| A build effort | Body has the exact line `Work kind: build` | Its available ticket to `cast`, else `conjure` for a progress check, using the same rule as Stage 2 |
| A ready ticket | Carries the ready label | Run `blocked ID`. No open blocker and no other assignee: `cast` on it. Blocked: name every open blocker, then route the first blocker through this table instead, one hop only. Held by someone else: say who and stop |
| Waiting on a person | Carries the `ready-for-human` or `needs-info` string | Say what it waits for and stop. `sift` can move it once the answer lands |
| Untriaged | Carries the `needs-triage` string, or no label at all | `sift` on it |
| Closed | State is closed | Say it is done. When the body has a `Build parent:` link, route the parent instead |
| Anything else | An open issue with only category labels | `sift` on it, since it has no state the other skills read |

A ticket already assigned to the person driving this session is theirs; route it as if unclaimed and say it is already claimed.

---

## Stage 4: Report

Write the result as markdown, not as a code block and not as plain indented lines. A reader scans this in a terminal that renders markdown, so the fields go in a table and the links stay clickable. Plain sentences, no dashes, under this repo's `dispel` rules when that skill is installed. Refer to every issue by its title with the link wrapped inside the name; a bare number appears only in the prompt line. Emit it exactly in this shape, including the empty header cells:

### Portal

| | |
|---|---|
| **Branch** | name, then clean \| uncommitted \| unpushed, then the PR state or `no PR` |
| **Maps** | count open and the first frontier ticket, or `none` |
| **Build effort** | title, done/total, then held by you \| available \| blocked \| awaiting review counts, or `none` |
| **Ready** | the oldest ready ticket nobody holds, or `none` |
| **Inbox** | count needing triage |

**Next step:** \<skill> on \<ticket title with link>. \<One sentence on why this row won.>

**Prompt:** `\<one line that starts it>`

Every row appears, in this order, even when the value is `none`. A cell holds one line: no newlines, no bullets, and a literal pipe inside a value is escaped as `\|`. Links go in bare so the terminal renders them. A read the tracker refused is written as `unknown: <reason>` in its row, and the route is chosen from what did load.

The prompt line is natural language that works whether or not the named skill is installed. Shapes:

- `Implement <ticket URL>, following its brief.` for a build ticket.
- `Resolve <ticket URL> on its map.` for a map ticket.
- `Check progress and close out the build effort at <parent URL> once the pending work is complete.` for a stalled effort.
- `Use the completed planning map <map URL> to propose the implementation work, keeping the map as the planning source.` for a map with no effort.
- `Triage <issue URL>.` for the inbox.
- `Review the pull request <PR URL>.` or `Resolve the review feedback on <PR URL>.` for a PR.

---

## Stage 5: Step through

The report is delivered before this question, in a user-visible message, so the choice is about action. Ask **one** question, unless `go` already answered it. Use the platform's blocking question tool (`AskUserQuestion` in Claude Code; call `ToolSearch` with `select:AskUserQuestion` first if the schema is not loaded). Begin it with "Step through to \<skill> on \<ticket title>?" and offer these options, the first marked recommended:

1. **Run \<skill> on \<ticket> now.** Hand off as described below.
2. **Take the runner-up instead.** Name the next route the precedence table would have chosen, such as the next available ticket in build order or the inbox. Choosing it hands off to that route the same way.
3. **Something else.** Stop with the report and the prompt line in view. The person types what they want.

Without a question tool, ask the same thing in one sentence and wait.

**Handing off.** The routed skill is a sibling of this one: its instructions live at `<SKILL_DIR>/../<skill>/SKILL.md`. Read that file in full and follow it from its start as if the person had invoked it with the ticket id as the argument, including its persona stage, its tracker stage, and its own claim. Portal has not claimed anything, so the routed skill's claim is the first write of the session. Do not summarize the sibling's rules from memory; the file is the contract. When the sibling folder is missing, say so, then carry out the prompt line as an ordinary task and note that the skill's own workflow, such as proof capture and the pull request, is not in play.

`go` with a route that leads to nothing (a clear board, a ticket held by someone else, or a ticket waiting on a person) prints the report and stops; there is nothing to step through.

## References

| Reference | Load at | Purpose |
|-----------|---------|---------|
| `../<skill>/SKILL.md` | Stage 5, on a yes | The routed skill's own instructions, followed from the top |
