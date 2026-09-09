# Finish the audit

Every lens has returned. This file runs the merge, the reconcile, the render, the terminal summary, and the two action modes. Follow it in order.

## Merge, pass 1

```bash
bash "<SKILL_DIR>/scripts/ultima.sh" merge "$RUN_DIR" --roster "<lens,lens,...>"
```

The script reads each `$RUN_DIR/<lens>.json`, falls back to `$RUN_DIR/returns/<lens>.json` when the artifact is missing, and applies the gates in this order:

1. Malformed candidates (no title, problem, fix, or quoted instance) go to Dismissed with the reason.
2. Instances are deduplicated by file and line.
3. A strength of 75 or 100 with fewer than three instances becomes 50.
4. A design-system candidate at 75 or 100 with no sourced token and no `convention_source` becomes 50.
5. A candidate with `prior_decision` set goes to Dismissed, citing the doc.
6. Candidates whose titles share most of their words, or whose quoted `file:line` sets overlap by half, merge into one: union of instances, higher strength, longer problem, the fix from the stronger one, both lenses recorded.
7. A candidate two lenses agree on, with three or more instances, is promoted one step, once.
8. Each candidate is scored against the hot spots in `profile.json`, sorted within strength tiers, and numbered.

It writes `$RUN_DIR/merged.json` and prints one summary line. Exit 4 means no `python3`; do the same steps by hand on the artifacts, write the same shape, and say so in Coverage.

## Reconcile

Read `merged.json` in full. Copy it to `$RUN_DIR/reconciled.json` and edit only that copy. You may:

- **Dismiss** a candidate the gates kept but you can see is wrong: the instances are inside the source of truth, the pattern is intentional per a comment the lens missed, or the fix would break something you can name. Move it to `dismissed` with a reason and `"stage": "reconcile"`.
- **Merge** two candidates the script missed, when they are one pattern described two ways. Union the instances yourself.
- **Tighten** a title so it names the wrong thing and the right thing in twelve words.
- **Raise** a candidate's strength only by adding a quoted instance or a `convention_source` that the lens missed. Never raise it by editing the number alone; pass 2 re-applies the gates.

- **Recommend** by setting a top-level `recommendation` string: one or two sentences on why rank 1 comes first, naming its score against the next candidate, its hot files, and how mechanical the fix is. The report prints it in the Start here block. Leave it out and the script writes a plain line from the numbers.

You may not add a candidate no lens produced, and you may not delete a dismissal.

## Merge, pass 2

```bash
bash "<SKILL_DIR>/scripts/ultima.sh" merge "$RUN_DIR" --reconciled "$RUN_DIR/reconciled.json"
```

Pass 2 restores the gates, rescores, resorts, and renumbers. `merged.json` is now final.

## Render

```bash
bash "<SKILL_DIR>/scripts/ultima.sh" render "$RUN_DIR"
```

The script writes `$RUN_DIR/report.html` from `merged.json`, `profile.json`, and `metadata.json`, and prints the path. Never write the HTML yourself: the report embeds quoted repo code, and the script escapes every field. The report has inline CSS, no script tag, and no network dependency, so it opens from `file://` anywhere.

Update `metadata.json` with `report` set to that path.

## Terminal summary

Print the report path first, then the top candidates. Keep it short; the report is the deliverable.

```
Frontend audit: <repo> at <short sha>, scope <path>
Report: <path>   (open it in a browser)

Top candidates
  1. <title>  [<lens>, strength <n>, <k> instances, effort <S|M|L>]
  2. ...
  (up to 5)

Strong <n>, weaker <n>, dismissed <n>.
Coverage: lenses <ok list>; missing <list or none>; docs consulted <list>; lint deferred to <list or none>.
```

On macOS you may offer `open <path>` as a command. Do not run it unprompted.

## Action modes

### File tickets

Read `docs/agents/issue-tracker.md` when it exists. Its `Tracker:` line names the tracker and its `Adapter flags:` line gives the flags for the bundled script. Missing file: GitHub, no flags. On a GitHub Enterprise host, pass `GH_HOST=<host>` inline. On Linear or Jira, when the host exposes a connector for that tracker, use it for `ensure-labels` and `create`; it is already authenticated. Otherwise run the script with the adapter flags. GitHub always goes through the script. Never write the tracker any other way.

Resolve the label strings. When `docs/agents/triage-labels.md` exists, take the strings it maps for `enhancement` and `ready-for-agent`. Missing file: the string equals the role name. Ensure them once:

```bash
bash "<SKILL_DIR>/scripts/tickets.sh" <adapter flags> ensure-labels --color d73a4a "<enhancement string>"
bash "<SKILL_DIR>/scripts/tickets.sh" <adapter flags> ensure-labels --color 0e8a16 "<ready string>"
```

Load `references/agent-brief.md`. Write one brief per strong candidate (strength 75 or 100), in rank order. Weaker candidates are not filed unless the user names them. The brief is written against behavior, since paths go stale:

- **Category:** enhancement.
- **Summary:** the candidate title.
- **Current behavior:** the `problem`, plus the instance count and the three hottest files as examples.
- **Desired behavior:** the `fix`, naming the token, component, or attribute.
- **Key interfaces:** the token or component from `convention_source` or `tokens[]`.
- **Acceptance criteria:** the check that established the candidate (a grep, a lint rule, a test, or a manual read of each quoted instance) finds no remaining instance under the scope path; the project's Validation command passes; any story or snapshot for the touched components updated.
- **Out of scope:** the other candidates, by title.

```bash
bash "<SKILL_DIR>/scripts/tickets.sh" <adapter flags> create "<title>" --label "<enhancement string>" --label "<ready string>" <<'EOF'
Source: frontend audit <short sha>, candidate <rank>

<brief from references/agent-brief.md>
EOF
```

Exit 3 from the script means this token cannot write issues. Stop calling it. Write each brief to `$RUN_DIR/tickets/<rank>-<slug>.md` with the same body, print the paths, and tell the user the tickets are local because the tracker refused the write.

Report the filed tickets as titles wrapped around their links, in rank order.

### Fix one now

Load `references/fix-one.md` and follow it. `fix` alone takes rank 1; `fix:<n>` takes that rank.
