# Finish the audit

Every lens has returned. This file runs the merge, the reconcile, the render, the terminal summary, and the two action modes. Follow it in order.

## Merge, pass 1

```bash
bash "<SKILL_DIR>/scripts/ultima.sh" merge "$RUN_DIR" --roster "<lens,lens,...>"
```

The script reads each `$RUN_DIR/<lens>.json`, falls back to `$RUN_DIR/returns/<lens>.json` when the artifact is missing, and applies the gates in this order:

1. Validate the finding and its evidence kind. Patterns retain quoted-instance and convention gates. Traces require the invariant and source, scenario, verification, and all source/boundary/consumer roles across at least two distinct locations.
2. Apply confidence gates independently of impact and reach. A single traced boundary issue can qualify. Static findings do not claim runtime observations.
3. Dismiss accepted documented tradeoffs. Preserve violations; route supported proposals to revisit decisions to `decision-needed`.
4. Merge findings only when root cause, affected boundary, and proposed fix match exactly. Legacy findings without those keys require matching title and fix. Overlapping quotes and similar titles alone are insufficient. Agent agreement never promotes confidence.
5. Rank strong findings before weaker ones, then by impact, reach, confidence, and effort; use churn only as a tie breaker. Preserve computed stable `id` across reconciliation and category filtering. Rank is a display position, not identity.

It writes `$RUN_DIR/merged.json` and prints one summary line. Exit 4 means no `python3`; do the same steps by hand on the artifacts, write the same shape, and say so in Coverage.

## Reconcile

Read `merged.json` in full. Re-read the strongest findings against the actual source, verify connected trace steps and invariant sources, and record any missing inspection in Coverage. Copy it to `$RUN_DIR/reconciled.json` and edit only that copy. You may:

- **Dismiss** a candidate the gates kept but you can see is wrong: the instances are inside the source of truth, the pattern is intentional per a comment the lens missed, or the fix would break something you can name. Move it to `dismissed` with a reason and `"stage": "reconcile"`.
- **Merge** two candidates the script missed, when they are one pattern described two ways. Union compatible evidence yourself; preserve the cause, boundary, and remedy. Link related findings rather than conflating distinct fixes.
- **Tighten** a title so it names the wrong thing and the right thing in twelve words.
- **Raise** a candidate's strength only by adding evidence that satisfies its evidence-kind gate. Never raise it by editing the number alone; pass 2 re-applies the gates.

- **Recommend** by setting a top-level `recommendation` string: one or two sentences on why rank 1 comes first, naming its supported impact, reach, and readiness compared with the next candidate. The report prints it in the Recommended work order block. Omit it when the ranked list already explains the order. The renderer adds no generic recommendation.

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

The script writes `$RUN_DIR/report.html` from `merged.json`, `profile.json`, and `metadata.json`, and prints the path. Never write the HTML yourself: the report embeds quoted repo code, and the script escapes every field. The report uses offline CSS category controls and no network dependency. Overview shows all findings and the system map. UX, Architecture, and Data & Reliability filter the same finding elements, preserving IDs and anchors. Keep category status in Coverage; the tab counts already show finding totals. Coverage distinguishes partially examined categories from categories not examined. Keep report copy specific to findings, decisions, and audit limits. Do not repeat counts in prose or narrate what the controls already show.

Update `metadata.json` with `report` set to that path.

## Terminal summary

Before entering Stage 6, send a user-visible assistant message with a clickable Markdown link to the existing HTML report, then the top candidates. Deliver this summary on every run, including explicit `report`, `tickets`, or `fix[:n]` modes that skip the question tool and runs with no candidates. Use the actual absolute path, for example `[Open project audit report](</tmp/ultima-501/20260909-120000-ab12cd34/report.html>)`. Keep the link outside code blocks. Shell output alone is insufficient: the user needs access before choosing or executing an action.

Use this shape as prose, not a fenced code block:

```
Project audit: <repo> at <short sha>, scope <path>
[Open project audit report](<absolute report path>)

Top candidates
  1. <title>  [<id>, <category>, confidence <n>, impact <level>, action <action>]
  2. ...
  (up to 5)

Strong <n>, weaker <n>, dismissed <n>.
Coverage: lenses <ok list>; missing <list or none>; docs consulted <list>; lint deferred to <list or none>.
```

Say briefly that the report is stored temporarily and should be saved elsewhere if the user wants to keep it. If the host supports a local file preview, open the report there as part of delivery and retain the link. If local links are unsupported, provide the absolute path and a platform-appropriate browser-opening command before entering Stage 6, including explicit action modes. On macOS you may offer `open <quoted absolute path>` as a command. Do not launch an external application unprompted.

## Action modes

### File tickets

Read `docs/agents/issue-tracker.md` when it exists. Its `Tracker:` line names the tracker and its `Adapter flags:` line gives the flags for the bundled script. Missing file: GitHub, no flags. On a GitHub Enterprise host, pass `GH_HOST=<host>` inline. On Linear or Jira, when the host exposes a connector for that tracker, use it for `ensure-labels` and `create`; it is already authenticated. Otherwise run the script with the adapter flags. GitHub always goes through the script. Never write the tracker any other way.

Resolve the label strings. When `docs/agents/triage-labels.md` exists, take the strings it maps for `enhancement` and `ready-for-agent`. Missing file: the string equals the role name. Ensure them once:

```bash
bash "<SKILL_DIR>/scripts/tickets.sh" <adapter flags> ensure-labels --color d73a4a "<enhancement string>"
bash "<SKILL_DIR>/scripts/tickets.sh" <adapter flags> ensure-labels --color 0e8a16 "<ready string>"
```

Load `references/agent-brief.md`. Write one brief per strong candidate (strength 75 or 100), in rank order. Use its stable ID in the source. The merge marks plans with missing migration details as `plan_status: incomplete`. Those tickets explicitly request further planning and list `plan_missing`; they do not imply an implementation-ready plan. Only action `fix` findings receive the ready-for-agent label; plans and decision-needed findings are not ready implementation work. Weaker candidates are not filed unless the user names them. The brief is written against behavior, since paths go stale:

- **Category:** enhancement.
- **Summary:** the candidate title.
- **Current behavior:** the `problem`, plus the supporting pattern or traced flow and representative file references.
- **Desired behavior:** the `fix`, naming the affected boundary or concrete interface change.
- **Key interfaces:** the affected boundary, callers, and owners, with evidence references.
- **Acceptance criteria:** the candidate's verification establishes the intended behavior and the project's Validation command passes. For plans, include remediation order, compatibility, rollback, and dependency prerequisites. For decision-needed work, capture the cited decision and decision_reason with the decision required before implementation.
- **Out of scope:** the other candidates, by title.

```bash
bash "<SKILL_DIR>/scripts/tickets.sh" <adapter flags> create "<title>" --label "<enhancement string>" <<'EOF'
Source: project audit <short sha>, candidate <id> (rank <rank>)

<brief from references/agent-brief.md>
EOF
```

For action `fix`, add `--label "<ready string>"` to that create command. Omit it for plans and decision-needed findings.

Exit 3 from the script means this token cannot write issues. Stop calling it. Write each brief to `$RUN_DIR/tickets/<rank>-<slug>.md` with the same body, print the paths, and tell the user the tickets are local because the tracker refused the write.

Report the filed tickets as titles wrapped around their links, in rank order.

### Fix one now

Load `references/fix-one.md` and follow it. `fix` alone takes rank 1; `fix:<n>` takes that rank.
