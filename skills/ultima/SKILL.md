---
name: ultima
description: "Audit a whole frontend codebase for design system drift, missing interaction states, accessibility gaps, and component interface problems, then present ranked candidates in a self-contained HTML report and ask whether to report only, file tickets, or fix one now. Use when asked to audit the frontend, review UI consistency, find design system drift, check design token usage, run an accessibility audit from code, review usability or interaction states, improve frontend code quality, or /ultima."
argument-hint: "[path:<dir>] [lens:<a,b>] [since:<days>] [report|tickets|fix[:<n>]]"
---

<!-- BEGIN MANA PERSONA -->
## Persona at invocation

Before conversational narration, read `Persona:` and `Style:` in the active project's `## Agent skills` block from `CLAUDE.md` or `AGENTS.md`. Prefer the file containing the block, then an existing file; ties use `CLAUDE.md`. A symlink pair is one file. Read the saved value anew on each invocation, including from a subdirectory using the project root. No accessible project or no line means ordinary behavior. Do not search another project or global settings for this preference.

During the `Persona at invocation` stage, `archmage` on either line loads this skill's own [references/archmage.md](references/archmage.md) for the active workflow. `off` or an absent value leaves ordinary behavior active. An unknown value leaves ordinary behavior active and gets a brief explanation when conversational output is allowed; it does not stop the work. Explicit conversation instructions override the saved voice without writing settings. A request to enable Archmage for this workflow also loads the local reference.

Apply the voice only to lead-agent conversation. Deliverables, specialist roles, reply-only responses, and JSON-only output retain their contracts, with no added narration. End the persona with this workflow unless the user requests otherwise or a `Style:` line names `archmage`, which keeps the voice on for the whole session.
<!-- END MANA PERSONA -->

# Ultima

Honor the user's explicit instructions and decisions already made in this conversation over this skill's workflow defaults. A rule this file states with never, or as read-only, is a gate: it holds whatever the conversation says, and an instruction to cross one is declined and reported. Continue authorized work; ask only about unresolved choices that would materially change the result. Preparing or reviewing work does not authorize publishing it.

If a skill rule requires a pause or leaves requested work unfinished, name and link to the exact SKILL.md and quote the rule. Then explain what decision or prerequisite is missing. Distinguish a required gate from your interpretation.

Audits a frontend codebase as a whole, not a diff. Four read-only lenses look for the same wrong thing repeated across files: raw values where tokens exist, screens with no loading or error state, clickable elements with no keyboard path, components whose props mirror their implementation. A script merges and ranks what they find, renders one HTML report, and then the skill asks what to do with it.

## When to use

- Before a design-system migration, to see where the code goes around the system today
- After a stretch of fast feature work, to find what drifted
- When a team wants a ranked list of UI cleanups sized for single sessions
- On a codebase you are new to, to learn its conventions and where they break

For a review of one change, this is the wrong tool; say so and offer a diff review instead.

## Execution spine

Follow these boundaries in order. References supply detail but never change the order.

1. Profile the checkout and settle the scope (Stage 1).
2. Write the prior-decisions block from the docs the profile lists (Stage 2).
3. Create the run directory, record metadata, and announce the roster (Stage 3).
4. Read `references/lens-template.md`, `references/candidates-schema.json`, and the selected lens files, then dispatch every lens and collect every one before merging (Stage 4).
5. Read `references/finish-audit.md` and follow it to merge, reconcile, render, and summarize (Stage 5). Never synthesize directly from raw lens artifacts.
6. Ask what to do with the candidates, then do it (Stage 6). This is the one blocking question this skill asks.

## Operating principles

- **Audit first, act second.** Nothing is edited, committed, or filed until Stage 6, and then only along the branch the user picks.
- **One blocking question, at the end.** Do not stop to ask about scope, lenses, or which docs count. Infer them from the profile and the arguments, and note uncertainty in Coverage.
- **Never switch branches.** The audit reads the current checkout. `path:` narrows what is read, never what may be mutated.
- **Patterns, not points.** A candidate has three or more quoted instances or it is weak. A single bug belongs to a code review.
- **The report is rendered by the script.** It embeds quoted repo code, and the script escapes it. Never hand-write the HTML.
- **Report outcomes, not machinery.** Say what was audited, which lenses ran, and what they found. Keep the run directory, script calls, and JSON shapes quiet unless something failed.
- **Nothing leaves the machine.** Lenses are local subagents. The report is a local file.

`<SKILL_DIR>` is the absolute directory this SKILL.md lives in. Substitute the real path every time it appears. Do not assign it to a shell variable first: a sandboxed or worktree-isolated session refuses `bash "$VAR/script.sh"` because it cannot resolve the path to read the script.

## Arguments

Parse for these tokens. Anything else is an error; say so and stop.

| Token | Effect |
|-------|--------|
| `path:<dir>` | Audit only that directory. Required to choose a package in a monorepo when the automatic choice is wrong. |
| `lens:<a,b>` | Run only the named lenses: `design-system`, `interaction-states`, `accessibility`, `component-architecture`. Default is all four. |
| `since:<days>` | Churn window for hot spots. Default 90. |
| `report` | Skip the Stage 6 question: the report is the deliverable. |
| `tickets` | Skip the Stage 6 question: file one ticket per strong candidate. |
| `fix` or `fix:<n>` | Skip the Stage 6 question: fix candidate `n` (default rank 1) on the current branch. |

Two action tokens together, or an unknown lens name, stop with a one-line reason before anything runs.

## Stage 1: Profile

Create the run directory first (Stage 3 has the block; run it now, then come back), then profile the checkout into it:

```bash
bash "<SKILL_DIR>/scripts/ultima.sh" orient --path <dir or .> --since <days> --run-dir "$RUN_DIR"
```

The script writes `$RUN_DIR/profile.json` and prints it: framework, styling approach, the design-system source of truth (token files, theme config, component package, imported library), parsed token values, the component inventory, the top hot spots from recent commits, the decision docs to read, and the lint packages the lenses defer to. Exit 2 means no frontend under the scope: report that in one line and stop. Exit 4 means no `python3`: gather the same facts by hand, write them as `profile.json` in the same shape, and note it in Coverage.

Read `scope.reason`. When it says the script picked a package by commit count, say which package and that `path:` picks another. When the profile lists no design-system source, say so up front: the design-system lens will then measure consistency against the repo's own most-used values, and its candidates cannot reach 100.

## Stage 2: Prior decisions

Read every file in the profile's `docs.files` list and the titles in `docs.adrs`. Open an ADR when its title touches UI, components, styling, tokens, or accessibility. Write a block of two to eight lines, each naming a settled decision and its doc:

```
<prior-decisions>
docs/adr/0007-radix-overlays.md: overlays use Radix primitives; no hand-rolled dialogs.
CONTEXT.md: "surface" means a card-level container with the elevation token.
CLAUDE.md: Tailwind utilities in feature code; CSS modules only under packages/ui.
</prior-decisions>
```

No docs means an empty block and one line in Coverage. Never block on it.

## Stage 3: Run directory and roster

```bash
SCRATCH_ROOT="/tmp/ultima-$(id -u)";
if [ -L "$SCRATCH_ROOT" ]; then echo "unsafe scratch root symlink: $SCRATCH_ROOT" >&2; exit 1; fi;
install -d -m 700 "$SCRATCH_ROOT" || exit 1;
if [ -L "$SCRATCH_ROOT" ] || [ ! -O "$SCRATCH_ROOT" ]; then echo "scratch root not owned by current user" >&2; exit 1; fi;
chmod 700 "$SCRATCH_ROOT" || exit 1;
RUN_ID=$(date +%Y%m%d-%H%M%S)-$(head -c4 /dev/urandom | od -An -tx1 | tr -d ' ');
RUN_DIR="$SCRATCH_ROOT/$RUN_ID";
(umask 077; mkdir -p "$RUN_DIR/returns" "$RUN_DIR/tickets") || exit 1;
echo "$RUN_DIR"
```

Write `$RUN_DIR/metadata.json` with `repo` (the `owner/name` from the origin URL, or the directory name), `head` (`git rev-parse HEAD`), `scope`, `framework`, `lenses`, and `started_at`. Then look through `$SCRATCH_ROOT/*/metadata.json` for a run with the same `repo` and `head`. A match means that report audited this exact tree: say so in one line with its `report` path, then continue. Never skip the audit on that basis.

**Announce the roster** before spawning: the lenses by their plain names and what each looks for, in one line each. This is progress reporting, not a confirmation prompt.

## Stage 4: Dispatch and collect

Before assembling any prompt, read these from this skill's directory in one parallel wave: `references/lens-template.md`, `references/candidates-schema.json`, and `references/lenses/<name>.md` for every selected lens.

Fill the template for each lens and spawn it as a **generic subagent**. Do not use typed agent names. Omit the `mode` parameter so the user's permission settings apply. Launch up to the host's active-agent capacity; the lenses are read-only and can inspect the same files at once. A blocking spawn returns its result directly. An asynchronous spawn returns an ID: retain it and use the host's supported wait or completion mechanism to collect its result. Refill as slots free until every lens has run. If the host offers only serial blocking calls, run them one at a time.

Each lens receives: its lens file, the schema, the prior-decisions block, the profile path, and the one-line context values from the template's slot table. Lenses are **read-only** toward the project: non-mutating inspection only. The one permitted write is their own artifact file under `$RUN_DIR`. They never edit project files, install packages, start servers, switch branches, or commit.

Collect **every** spawned lens before Stage 5; a merge on a partial roster is a defect. For any lens whose artifact is missing or fails to parse, write its compact return to `$RUN_DIR/returns/<lens>.json` so the merge can still use it. A lens that returned nothing usable is a failed lens: name it in Coverage, never invent its candidates.

## Stage 5: Merge, reconcile, render

Read `references/finish-audit.md` in full and follow it: merge pass 1, your reconcile of `merged.json`, merge pass 2, the render, and the terminal summary. Do not improvise a shorter path, and do not write the report by hand.

## Stage 6: Choose what happens next

After the summary is printed, ask **one** question, unless `report`, `tickets`, or `fix` already answered it.

Use the platform's blocking question tool (`AskUserQuestion` in Claude Code; call `ToolSearch` with `select:AskUserQuestion` first if the schema is not loaded) with these three options:

| Option | Behavior |
|--------|----------|
| **Report only** | Stop. The report is the deliverable. |
| **File tickets** | One ticket per strong candidate, in rank order, through the bundled tracker script. See *File tickets* in `references/finish-audit.md`. |
| **Fix one now** | Fix the top candidate on the current branch after a short printed check, validate, commit, stop. See `references/fix-one.md`. The user may name a rank. |

Offer **File tickets** only when the checkout has a tracker: `docs/agents/issue-tracker.md` exists, or `gh auth status` succeeds inside a GitHub remote. Otherwise offer the other two and say why the third is missing.

The report is already delivered at this point, so the question is about action, not about whether the audit is done.

## References

| Reference | Load at | Purpose |
|-----------|---------|---------|
| `scripts/ultima.sh` | Stages 1, 5 | `orient` profiles the checkout, `merge` runs the gates and the ranking, `render` writes the HTML report |
| `scripts/tickets.sh` | Stage 6, tickets | Creates labels and issues on GitHub, Linear, or Jira; same script the ticket skills carry |
| `references/lens-template.md` | Stage 4 | Dispatch shape, strength anchors, the quote-the-instance gate, the not-a-candidate table |
| `references/candidates-schema.json` | Stage 4 | JSON output contract passed to each lens |
| `references/lenses/*.md` | Stage 4 | One file per selected lens |
| `references/finish-audit.md` | Stage 5, 6 | Merge, reconcile, render, the summary, and the tickets action |
| `references/fix-one.md` | Stage 6, fix | The five checks, the edit rules, the commit rules |
| `references/agent-brief.md` | Stage 6, tickets | The brief a build session reads |
