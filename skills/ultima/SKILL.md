---
name: ultima
description: "Audit a whole project for UX problems, architecture weaknesses, and data reliability risks using parallel specialists and a tabbed HTML report. Use when asked to audit project architecture, review system boundaries, audit the frontend, review UI consistency, check data integrity or failure recovery, or /ultima."
argument-hint: "[path:<dir>] [category:<a,b>] [lens:<a,b>] [since:<days>] [report|tickets|fix[:<n>]]"
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

Audit the whole project by default. UX specialists find repeated interface problems; architecture and data reliability specialists trace important flows across boundaries. Ground each finding in repository evidence and documented decisions. Deliver one offline report with Overview, UX, Architecture, and Data & Reliability tabs, then follow the requested action mode.

For a review of one change, offer a diff review instead. This audit reports the scope actually inspected; it does not certify security, performance, or production behavior.

## Execution spine

Follow these boundaries in order. References supply detail but never change the order.

1. Create the run directory using the Stage 3 block, then profile the checkout and settle the scope (Stage 1).
2. Verify the system map and write the shared context and prior decisions (Stage 2).
3. Record metadata and announce the roster (Stage 3).
4. Read `references/lens-template.md`, `references/candidates-schema.json`, and the selected lens files, then dispatch every lens and collect every one before merging (Stage 4).
5. Read `references/finish-audit.md` and follow it to merge, reconcile, render, and summarize (Stage 5). Never synthesize directly from raw lens artifacts.
6. Ask what to do with the candidates, then do it (Stage 6). This is the one blocking question this skill asks.

## Operating principles

- **Audit first, act second.** Nothing is edited, committed, or filed until Stage 6, and then only along the branch the user picks.
- **One blocking question, at the end.** Do not stop to ask about scope, lenses, or which docs count. Infer them from the profile and the arguments, and note uncertainty in Coverage.
- **Never switch branches.** The audit reads the current checkout. `path:` narrows what is read, never what may be mutated.
- **Evidence fits the claim.** Repeated patterns need quoted instances. A single architecture flaw can qualify through a sourced invariant and a connected trace.
- **The report is rendered by the script.** It embeds quoted repo code, and the script escapes it. Never hand-write the HTML.
- **Report outcomes, not machinery.** Say what was audited, which lenses ran, and what they found. Always deliver the report link; keep intermediate artifact paths, script calls, and JSON shapes quiet unless something failed.
- **Local artifacts.** The report is a local file. Audit mode does not publish findings or write to a tracker.

`<SKILL_DIR>` is the absolute directory this SKILL.md lives in. Substitute the real path every time it appears. Do not assign it to a shell variable first: a sandboxed or worktree-isolated session refuses `bash "$VAR/script.sh"` because it cannot resolve the path to read the script.

## Arguments

Parse for these tokens. Anything else is an error; say so and stop.

| Token | Effect |
|-------|--------|
| `path:<dir>` | Audit only that directory; default is the repository root, including its packages. |
| `category:<a,b>` | Select `all`, `ux`, `architecture`, or `data-reliability`; comma lists are allowed without mixing `all` with another category. Default `all`. |
| `lens:<a,b>` | Override the recommended roster with named lenses from the table below. |
| `since:<days>` | Churn window for hot spots. Default 90. |
| `report` | Skip the Stage 6 question: the report is the deliverable. |
| `tickets` | Skip the Stage 6 question: file one ticket per strong candidate. |
| `fix` or `fix:<n>` | Skip the Stage 6 question: fix candidate `n` (default rank 1) on the current branch. |

Two action tokens together, or an unknown category or lens name, stop with a one-line reason before anything runs.

## Stage 1: Profile

Create the run directory first (Stage 3 has the block; run it now, then come back), then profile the checkout into it:

```bash
bash "<SKILL_DIR>/scripts/ultima.sh" orient --path <explicit dir or repository root> --category <categories or all> --since <days> --run-dir "$RUN_DIR"
```

The script writes `$RUN_DIR/profile.json`. It inventories manifests, components, dependency edges, entrypoints, data files, and deployment files under `system_map`, alongside frontend conventions, churn, decision docs, and lint packages. These are discovery seeds, not a verified architecture model. Use `recommended_lenses` unless `lens:` overrides it. Missing frontend code does not stop an architecture audit. Exit 2 means no applicable source for the selected categories: report that and stop. An explicit lens roster determines the categories passed to profiling, so a category filter cannot block a lens override. Exit 4 means no `python3`: gather the same profile shape by hand and disclose this in Coverage.

| Category | Lenses |
|---|---|
| `ux` | `design-system`, `interaction-states`, `accessibility`, `component-architecture` |
| `architecture` | `system-architecture` |
| `data-reliability` | `data-integrity`, `failure-recovery` |

## Stage 2: Verify the shared context

Read the profile's decision docs and relevant ADRs, including decisions about package ownership, persistence, deployment, and recovery. Follow imports and registrations to verify the important components and flows seeded by `system_map`. Trace representative entrypoints through their owners and downstream effects, including cross-package contracts where the scope permits. Prioritize consequential flows over file counts or churn. Record inaccessible dependencies and unresolved links explicitly.

Write `$RUN_DIR/system-context.md` with the verified boundaries, important flows and file references, documented decisions, and coverage limits. Distinguish discovered paths from verified dependencies. This file is shared evidence for specialists, not permission to expand an explicit path scope. Include a concise `<prior-decisions>` block with doc paths; no docs means an empty block and a coverage note. An accepted tradeoff, a violation of that decision, and a proposal to revisit it are different outcomes.

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

Write `$RUN_DIR/metadata.json` with `repo` (the `owner/name` from the origin URL, or the directory name), `head` (`git rev-parse HEAD`), `scope`, `framework`, `lenses`, and `started_at`. Then look through `$SCRATCH_ROOT/*/metadata.json` for a run with the same `repo` and `head`. A match means the report used the same commit, which can still have different uncommitted files. Say so in one line with its `report` path, record current working-tree status, then continue. Never skip the audit on that basis.

**Announce the roster** before spawning: the lenses by their plain names and what each looks for, in one line each. This is progress reporting, not a confirmation prompt.

## Stage 4: Dispatch and collect

Before assembling any prompt, read these from this skill's directory in one parallel wave: `references/lens-template.md`, `references/candidates-schema.json`, and `references/lenses/<name>.md` for every selected lens.

Fill the template for each lens and spawn it as a **generic subagent**. Do not use typed agent names. Omit the `mode` parameter so the user's permission settings apply. Launch up to the host's active-agent capacity; the lenses are read-only and can inspect the same files at once. A blocking spawn returns its result directly. An asynchronous spawn returns an ID: retain it and use the host's supported wait or completion mechanism to collect its result. Refill as slots free until every lens has run. If the host offers only serial blocking calls, run them one at a time.

Each lens receives: its lens file, the schema, the prior-decisions block, the profile path, the shared system-context path, and the one-line context values from the template's slot table. Lenses are **read-only** toward the project: non-mutating inspection only. The one permitted write is their own artifact file under `$RUN_DIR`. They never edit project files, install packages, start servers, switch branches, or commit.

Collect **every** spawned lens before Stage 5; a merge on a partial roster is a defect. For any lens whose artifact is missing or fails to parse, write its return to `$RUN_DIR/returns/<lens>.json`. The merge can use that file only when the return carries the full artifact shape, with all finding fields and evidence; a compact return with no artifact behind it is a failed lens. A lens that returned nothing usable is a failed lens: name it in Coverage, never invent its candidates.

## Stage 5: Merge, reconcile, render

Read `references/finish-audit.md` in full and follow it: merge pass 1, your reconcile of `merged.json`, merge pass 2, the render, and the terminal summary. Do not improvise a shorter path, and do not write the report by hand.

## Stage 6: Choose what happens next

After Stage 5 delivers the report as a clickable link in a user-visible message, ask **one** question, unless `report`, `tickets`, or `fix` already answered it. Shell output and a path inside a code block do not deliver the report. Never defer the link until the user chooses **Report only**. Action tokens skip the question, but still receive the report link before the action starts.

Begin the question with "Review the [project audit report](<absolute report path>), then choose what happens next." Substitute the actual path and retain the link in the preceding message even if the question tool cannot render links. The user must be able to open the report while the choice is pending.

Use the platform's blocking question tool (`AskUserQuestion` in Claude Code; call `ToolSearch` with `select:AskUserQuestion` first if the schema is not loaded) with these three options:

| Option | Behavior |
|--------|----------|
| **Report only** | Stop. The report is the deliverable. |
| **File tickets** | One ticket per strong candidate, in rank order, through the bundled tracker script. See *File tickets* in `references/finish-audit.md`. |
| **Fix one now** | Apply an eligible atomic fix on the current branch, validate, and commit when the tree was clean; plans become local briefs. See `references/fix-one.md`. The user may name a rank. |

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
