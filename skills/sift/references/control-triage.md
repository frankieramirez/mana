# Triage with a project control

Load this at Stage 2a when the repo has a `Control:` line in its `## Agent skills` block or a directory of feature records. It turns a vague report into candidate features and scenarios, runs only what the request allows, and keeps what was observed apart from what was inferred. It runs alongside `references/control-evidence.md`, which says how to read a run report.

## Pick the scope

Control commands execute project code, including `list`, `describe` and `--plan`. Use `static` when the request is read-only, static-only, or says to run nothing. Use `local` when Sift may run the project's tests, which is its usual Stage 2c verification. The scope covers control commands only. Tracker writes still follow the rest of this skill, and no scope permits editing product code, pushing or deploying.

## Find candidates

Write the report's words (title, body, and any reporter replies) to a scratch file outside the repo, then:

```bash
bash "<SKILL_DIR>/scripts/candidates.sh" --repo <repo> --query-file <report.txt> --scope <static|local>
```

It reads files only. It follows the pointer, matches the report against each feature's aliases, summary, reach routes and steps, and its scenarios' steps, and looks up each reach route in the feature's `sourceRoots`. Every candidate comes back with `behavior: inferred`. Report `control.state` and `map.state` as they are:

| State | What to do |
|---|---|
| `control: present`, `map: complete` | Use the candidates and the execution plan below |
| `control: absent` | Say no project control was discovered and continue Stage 2c the ordinary way. Make no control claim |
| `control: broken` | Name `control.detail`. Candidates from the records stay inferred. Run no control command, even under local scope |
| `map: incomplete` | Name the `map.gaps` that touch a candidate. A candidate with `runnable: false` gets no feature run; its gap goes in the brief as work or as an intent question |
| `map: absent` | No records to match. Fall back to the codebase search in Stage 2a |

A reach entry with a `discrepancy` means the source no longer mentions the recorded route or command. Find the path a user takes today in the source, record it, and ask whether the record or the code is right.

## Run what the plan names

Under static scope the plan is empty: run nothing. Under local scope, run `execution.commands` from the repo root and nothing wider: `list --search`, `describe feature` for each candidate, and at most one `feature` run for the top candidate. When `execution.run` reports a tie, read the `describe` output and ask which feature the report means before any run. Never run `release`, `changed`, or a feature the report did not match. A successful `list`, `describe` or `--plan` is discovery and proves no behavior.

Save the feature run's stdout and its exit code. Map the behavior the reporter expects to the candidate's scenario ids, then read the run with `conform.sh evidence --scope local` as `references/control-evidence.md` describes.

## Record it in the brief

Add this block to the triage notes or the agent brief, one entry per candidate:

```markdown
**Control evidence:**
- Candidate: `briefing`, scenarios `briefing.workers-stopped`; matched `aliases[0]` "welcome back"
- Reach: `/briefing`, which redirects to `/kingdom` (found in the briefing routes source)
- Behavior: observed, failed, run `<runId>` at `<HEAD>`, digest `<digest>`
- Intent questions: the record's knowledge is `proposed`; confirm the summary should name stopped workers
```

- **Observed** needs a valid, current report whose claim is `supported` or `contradicted`. A contradicted claim reproduces the reported bug. Name the run id, the checked HEAD and the digest.
- **Inferred** is everything else: a record match, a successful discovery command, a stale or rejected report, or a run that was blocked or unrun. Give the status (`unrun` or `blocked`) and the reason, such as "static-only request" or "chromium is missing".
- Name the matching source for every candidate: the record field and value `candidates.sh` reported.
- A `proposed` or `unresolved` record, a reach discrepancy, a tie, or a map gap becomes an intent question. Passing tests never confirm intent.
