---
name: portal
description: "Choose the next skill and ticket from the tracker and current branch. Use for /portal, what next, route this issue, or pick up where I left off."
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

Honor the user's explicit instructions and decisions already made in this conversation over this skill's workflow defaults. Continue authorized work; ask only about unresolved choices that would materially change the result. Preparing or reviewing work does not authorize publishing it.

If a skill rule requires a pause or leaves requested work unfinished, name and link to the exact SKILL.md and quote the rule. Then explain what decision or prerequisite is missing. Distinguish a required gate from your interpretation.

Portal recommends one next action from the board or a named issue. Discovery is read-only: leave claims and other writes to the authorized handoff. A recommendation-only request ends with the report. Otherwise ask once before handoff, unless `go` or prior conversation already authorizes the selected action. With no actionable route, report the reason and stop without a question.

After an authorized handoff, continue the selected task to its requested completion, preserving the user's scope and prior decisions. A missing sibling skill does not end authorized work; use the ordinary-task fallback in Stage 5.

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
4. Finish with the report or perform the authorized handoff (Stage 5).

---

## Stage 1: Tracker

Read `docs/agents/issue-tracker.md` when it exists. Its `Tracker:` line names the tracker and its `Adapter flags:` line gives the flags for the bundled script. Missing file: GitHub, no flags. On a GitHub Enterprise host, pass `GH_HOST=<host>` inline on every script call. Shell state does not persist between calls.

Portal uses only the read side of `scripts/tickets.sh`: `list`, `view`, `body`, `children`, `find`, `blocked`, and `next` without `--claim`. Map reads use `scripts/map.sh` on GitHub (`frontier`, `children`, `view`, `parent`). On another tracker, the tracker file's "Wayfinding operations" section says what a map and a frontier are there; read them through that connector or API. For `local`, tickets are files: read them directly. For `other`, follow the tracker file's Conventions.

Resolve the label strings once. When `docs/agents/triage-labels.md` exists, take the right-hand column for `ready-for-agent`, `needs-triage`, `needs-info`, and `ready-for-human`; otherwise those are the strings. Map labels are `scry:map` and `scry:<type>`, with `wayfinder:map` and `wayfinder:<type>` as legacy spellings that mean the same thing.

---

## Stage 2: Read the board

For a blank target, load [references/board.md](references/board.md). Gather the board summary, then inspect route candidates in precedence order. Independent reads may run together. Resolve the chosen route before handing off.

## Stage 3: Route one issue

For an id or URL, load [references/issue.md](references/issue.md). Inspect only that target and the relations needed to route it. Do not run whole-board discovery to fill the report.

During either routing stage, load [references/build.md](references/build.md) only when evaluating an effort's available ticket or progress. Load [references/pr.md](references/pr.md) only when evaluating a pull request's feedback or checks.

## Stage 4: Report

Write the result as markdown, not as a code block and not as plain indented lines. A reader scans this in a terminal that renders markdown, so the fields go in a table and the links stay clickable. Plain sentences, no dashes, under this repo's `dispel` rules when that skill is installed. Refer to every issue by its title with the link wrapped inside the name; a bare number appears only in the prompt line. Emit it exactly in this shape, including the empty header cells:

### Portal

| | |
|---|---|
| **Branch** | name, then clean \| uncommitted \| unpushed, then the PR state or `no PR` |
| **Maps** | count open and the first frontier ticket, or `none` |
| **Build effort** | title, done/total, then held by you \| available \| blocked \| awaiting review counts, or `none` |
| **Roadmap** | current milestone and done/total, or `none` |
| **Ready** | the oldest ready ticket nobody holds, or `none` |
| **Inbox** | count needing triage |

**Next step:** \<skill> on \<ticket title with link>. \<One sentence on why this row won.>

**Prompt:** `\<one line that starts it>`

For whole-board mode, every row appears in this order. Use `not inspected` for deliberately deferred detail, `none` for a verified absence, and `unknown: <reason>` for a failed read. For a named target, replace the board rows with **Target**, **State**, and **Relevant context**; include only the target and relations actually inspected. When no action is available, replace Next step with the reason and omit Prompt. A cell holds one line: no newlines, no bullets, and a literal pipe inside a value is escaped as `\|`. Links go in bare so the terminal renders them. A read the tracker refused is written as `unknown: <reason>` in its row, and the route is chosen from what did load.

The prompt line is natural language that works whether or not the named skill is installed. Shapes:

- `Implement <ticket URL>, following its brief.` for a build ticket.
- `Resolve <ticket URL> on its map.` for a map ticket.
- `Check progress and close out the build effort at <parent URL> once the pending work is complete.` for a stalled effort.
- `Use the completed planning map <map URL> to propose the implementation work, keeping the map as the planning source.` for a map with no effort.
- `Triage <issue URL>.` for the inbox.
- `Report the roadmap and the next milestone to start.` for a clear board with a roadmap.
- `Review the pull request <PR URL>.` or `Resolve the review feedback on <PR URL>.` for a PR.

---

## Stage 5: Step through

The report is delivered before this question, in a user-visible message, so the choice is about action. For an actionable route that still needs authorization, ask **one** question. Skip it for a recommendation-only request, `go`, or prior authorization covering this action. Use a question tool only when it is available and permitted in the current mode; otherwise ask in conversation and wait for the reply. Do not discover or call a tool by a name from another platform. Begin it with "Step through to \<skill> on \<ticket title>?" and offer these options, the first marked recommended:

1. **Run \<skill> on \<ticket> now.** Hand off as described below.
2. **Take the runner-up instead.** Offer this only when another actionable route was verified during discovery. Name it. Do not fetch more tickets just to populate this option. Choosing it hands off to that route the same way.
3. **Something else.** Stop with the report and the prompt line in view. The person types what they want.

A pending question is not authorization. Resume the chosen route after the answer without repeating the question.

**Handing off.** The routed skill is a sibling of this one: its instructions live at `<SKILL_DIR>/../<skill>/SKILL.md`. Read that file in full and follow it from its start as if the person had invoked it with the ticket id as the argument, including its persona and tracker stages and any applicable claim. Carry forward the selected branch or PR URL when the route is not an issue. For `scan` followed by `reveal`, preserve both steps when the user authorized that sequence. Portal has not claimed anything, so any claim belongs to the routed workflow. Do not summarize the sibling's rules from memory; the file is the contract. When the sibling folder is missing, say so, then carry out the prompt line as an ordinary task and note that the skill's own workflow, such as proof capture and the pull request, is not in play.

`go` with a route that leads to nothing (a clear board, a ticket held by someone else, or a ticket waiting on a person) prints the report and stops; there is nothing to step through.

## References

| Reference | Load at | Purpose |
|-----------|---------|---------|
| `references/board.md` | Stage 2, blank target | Board summary and route precedence |
| `references/issue.md` | Stage 3, named target | State-first issue routing |
| `references/build.md` | Stage 2 or 3, effort candidate | Available ticket and progress |
| `references/pr.md` | Stage 2 or 3, PR candidate | Review and check evidence |
| `../<skill>/SKILL.md` | Stage 5, authorized handoff | The routed skill's own instructions, followed from the top |
