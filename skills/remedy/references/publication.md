# Fix verification and publication

Load after judgment in either mode, or step 9 only for a dry-run summary. Paths beginning with `references/` are relative to the skill directory. Full-mode triage stays in `references/full-mode.md`; Targeted mode never needs to load it.

### 4. Fix (fix-list only)

Read `references/fixer-prompt.md` and spawn a generic subagent seeded with that prompt for each fix-list item. Do not dispatch a standalone agent by type or name. The fixer only executes: validity is already decided, so it implements and returns.

Each fixer receives the feedback ID and type, the file path and location fields (`line`, `originalLine`, `startLine`, `originalStartLine`), the reviewer's comment text, your step-3 change note, and the PR number. When an item has no file or line, the fixer finds the target from the comment text and the PR diff. It returns `status`, `files_changed`, `summary`, `tests_run`, and `blocked_reason`.

In Targeted mode, the fix-list contains only the named thread; no scouts run.

**Dispatch rules.** The same collection rules govern scouts in step 3 and the verifier in step 4b. Group fixers by disjoint target files and launch up to the host's active-agent capacity. A blocking spawn returns its result directly. An asynchronous spawn returns an ID: retain it and use the host's supported wait or completion mechanism to collect its result. Individual asynchronous spawn calls can run concurrently without a batch tool. Refill freed capacity until the queue is empty; never hard-code a batch size. On a concurrency-limit error, keep the item queued and retry after a running agent completes. Prefer completion events or bounded waits; use status reads to recover state, without busy polling or unchanged status updates. If the host offers only serial blocking calls, run the queue sequentially. Collect every result before synthesis or verification. Preserve read-only scopes for scouts and verifiers, and the host's permission settings for fixers.

**Conflict avoidance:** two fixers must never edit the same file at the same time. Step 3 told you every target file, so run the overlapping ones one after another and the rest side by side. A class fix counts every one of its sites in that check.

**No way to spawn at all.** When the harness exposes no subagent capability, or a dispatch fails outright, work the fix-list yourself one item at a time with `references/fixer-prompt.md` as your own instructions: re-read each file before editing it, run the tests around the edit, and produce the same per-item result. The `blocked` contract applies unchanged, so a contradiction stops that item and sends it back through the gate. Scouts do not run on such a host, and step 4b is done inline. This costs parallelism and nothing else, because the judgment already happened in step 3.

When the batch returns, copy each fixer's `status`, `files_changed`, `summary`, and `tests_run` into that item's `outcome` in `items.json`.

**Handling `blocked`.** A fixer may return `blocked` for exactly two reasons: the change breaks a caller or test it can see, or the code at the target does not match what the finding described. Take its `blocked_reason` as new evidence, judge the item again, and either send it back with a corrected change note or move it to the skip-list with an explanation. A blocked item never vanishes.

### 4b. Verify the fixes

Aggregate `files_changed` across fixers. Empty means skip to step 7. Otherwise check the combined diff against each ask before the validation run, so a corrected fix does not force a second one. Each fixer reported on its own edit; nobody has yet read the whole diff against the whole fix-list.

Read `references/verifier-prompt.md` before choosing how to run verification. Apply its full checks to every non-empty diff, including targeted mode and the no-subagent fallback.

- **One item on the fix-list:** read `git diff` yourself and apply the verifier's checks inline. No spawn.
- **Two or more:** write the diff, fill the verifier template's slots, and dispatch one generic subagent. A blocking spawn returns its result directly. An asynchronous spawn returns an ID: retain it and collect it through the host's supported completion mechanism before reading `verify.json`. Do not busy-poll or sleep.

```bash
RUN_DIR="<the run directory>";
git diff -- <every tracked file in files_changed> > "$RUN_DIR/fixes.diff"
git diff --no-index /dev/null <each new file a fixer created> >> "$RUN_DIR/fixes.diff"
```

The second line covers files that do not exist in `HEAD` yet, usually a test a fixer added. `git diff` alone would not show them, and the verifier would call the fix missing. Nothing is staged here; step 6 still owns the index.

Save the return to `$RUN_DIR/verify.json` and record `verified` per item in `items.json`. Then act on it:

- **`addressed: false`** and every **`unexplained`** hunk go through the `blocked` path above: take the verifier's reason as new evidence, judge the item again, and either send it back to the same fixer with a corrected change note that names what to adjust or revert, or move it to the skip-list with the explanation and tell that fixer to revert its edit. A fixer owns its own hunks and never reverts another fixer's.
- **`conventions`** entries ride along on that re-dispatch as part of the note.
- A re-dispatched fixer's return replaces that item's `outcome` in `items.json`: `status`, `files_changed`, `summary`, `tests_run`. A `reverted` return leaves the first pass's values wrong.
- One re-dispatch round, then the verifier runs once more on those items alone. Still `false` after that: change that item's verdict in `items.json` to its skip-list entry with the explanation written there, revert the edit, and name it in the summary.

Any edit that lands after a verification rebuilds `fixes.diff` and reruns the check over the whole fix-list, including a step 5 inline diagnose-and-fix pass. Step 6 stages from the refreshed `files_changed`. Re-verification never opens a new fix round beyond the one re-dispatch round above.

### 5. Validate combined state

Aggregate `files_changed` again after any re-dispatch; a fully reverted file drops off the list. Empty means skip to step 7.

Each fixer ran only the tests around its own edit. Now run the project's full validation **once** over the combined diff, since that is the only way to see two fixes interacting.

1. Run the project's validation command: the `Validation:` line in the `## Agent skills` block of `CLAUDE.md` or `AGENTS.md` when one exists, else the test suite, typecheck, and lint the project's conventions name. Run it once for the whole diff.
2. **Green** → step 6.
3. **Red on files fixers changed** → one inline diagnose-and-fix pass, then re-run. That fix landed after verification, so rebuild `fixes.diff` and rerun the step 4b check over the whole fix-list. Still red: do **not** commit; report it as a blocker in the summary with the test output.
4. **Red only on files no fixer touched** → pre-existing. Proceed, and add a commit footer: `Note: <test> was already failing before these changes.`

Record the outcome for the summary.

### 6. Commit and push

Stage exactly the files the fixers listed in `files_changed`, nothing more:

```bash
git add <files from fixer summaries>
git commit -m "$(cat <<'EOF'
Address PR review feedback (#PR_NUMBER)

- <one line per change>
EOF
)"
```

Follow the repo's commit conventions when it has them (conventional prefixes, scope rules, changeset requirements). Then push, unless `no-push` was passed:

```bash
git push
```

If the push is rejected because the remote moved, stop the push and report the local commit SHA and the changed remote. Preserve the local work and leave its fix-list threads open. History repair needs a separate action; this workflow does not rebase, merge, or force-push. Do not retry the rejected push until the remote divergence is resolved.

**Report unpushed commits loudly.** If `no-push` was passed or the push failed, say so as the first line of the summary. A PR that gets merged with these commits sitting local loses the work.

### 7. Resolve threads (no replies)

After the push succeeds, resolve the threads you handled. **Post nothing.**

Resolve when:
- Verdict was `fixed` or `fixed-differently` and the change is pushed.
- Verdict was `not-addressing` or `declined`, unless `keep-open` was passed.

Leave open when:
- Verdict was `question` or `needs-human`.
- `no-push` was passed or the push failed, for fix-list items. Until the fix is on the remote the PR shows no evidence of it, and resolving the thread would hide a concern that still stands there.
- `keep-open` was passed, for skip-list items.

**Confirm the thread ID before resolving.** On GitHub Enterprise the node ID for one thread can differ between query paths. Take the numeric ID out of the comment URL (`discussion_r2589700` gives `2589700`) and map it back:

```bash
GH_HOST=<derived-host> GH_REPO=OWNER/REPO gh api repos/{owner}/{repo}/pulls/comments/COMMENT_ID --jq .node_id
GH_HOST=<derived-host> bash "<SKILL_DIR>/scripts/pr-threads" thread PR_NUMBER COMMENT_NODE_ID OWNER/REPO
```

The `id` this returns wins over anything from the fetch. Then resolve:

```bash
GH_HOST=<derived-host> bash "<SKILL_DIR>/scripts/pr-threads" resolve THREAD_ID
```

`pr_comments` and `review_bodies` have no resolve mechanism. Nothing happens on GitHub for them at all; they are reported in the summary only.

Set `resolved` on each thread item in `items.json` as you go, true or false, so step 9 can list `resolved_thread_ids` and `left_open_thread_ids` without a second pass.

### 8. Verify

In Targeted mode, repeat the comment-to-thread lookup from `references/targeted-mode.md` and check only that thread's `isResolved`. Do not run the whole-PR fetch below. In Full mode, fetch again to check the result:

```bash
GH_HOST=<derived-host> bash "<SKILL_DIR>/scripts/pr-threads" fetch PR_NUMBER OWNER/REPO
```

`review_threads` should contain only the threads you intentionally left open. Top-level comments and review bodies still appear; that is expected.

**If threads you meant to close are still open**, return to the selected mode's judgment for those alone. Two fix-and-verify rounds is the limit. After that, stop and tell the user what keeps reappearing in <area>, what has already been fixed, and that repeated rounds on one spot usually point at a design problem.

### 8b. Watch the one run

Only when step 6 pushed. Wait for the new head's checks:

```bash
gh pr checks PR_NUMBER --watch --fail-fast
```

If the host cannot keep the watch open, use its supported bounded wait or status mechanism for the check run, then report the run as pending when it remains incomplete. Do not busy-poll. On the result:

- **Green.** Done.
- **Red on touched code** that was in the fix-list: one more fix-and-verify round, inside the two-round limit from step 8.
- **Red on a flake candidate** from step 1b. Failing the same way twice: report it as a flake candidate and do not retrigger. Failing differently: find the run with `gh run list --branch <headRefName> --status failure --json databaseId,name --limit 5`, rerun it once with `gh run rerun <databaseId> --failed`, and never a second time. The summary names the run and the reason.
- **Red on untouched code.** Stale base. Report it as in step 1b.

### 9. Summary

This is the main output and the only place your reasoning surfaces. Group items by verdict, one line each, and say *what changed* along with where.

```
Resolved N of M new items on PR #NUMBER.

Fixed (n)
  - <file:line>: <what changed>

Fixed differently (n)
  - <file:line>: <what was done instead and why>

Not addressing (n)     [resolved silently, reviewer got no explanation]
  - <file:line>: <the evidence, e.g. "null check already exists at line 85">

Declined (n)           [resolved silently, reviewer got no explanation]
  - <file:line>: <the specific harm the fix would cause>

Open questions (n)     [thread left open]
  - <file:line>: <the question, and the answer from the code if you have one>

Pushed: <sha> to <branch>
Verified: <n of n fixes matched their ask, naming any item re-dispatched or reverted>
Validation: <one line, e.g. "pnpm test passed 893/893">
CI: <green | pending | red: <check> (touched | stale base | flake candidate)>
Retried: <run-id> once, <outcome>          [only when a rerun happened]
Run: <run dir> (summary.md, items.json)
```

For `not-addressing`, `declined`, and `question` items, phrase the explanation so the user can paste it into a PR reply if they want to. Do not post it.

When any item is `needs-human`, append a decisions section. Each carries the structured `decision_context` from the rubric: what the reviewer said, what you investigated, why it needs a call, options with tradeoffs, your lean. These threads stay open.

Also surface, when applicable:
- Unpushed commits (first line, loudly).
- An unsubmitted draft review found in step 1.
- Threads still pending from a previous run (detected in step 2 as deferred but unresolved).
- A prior scan of this PR whose `patch_id` in `/tmp/scan-$(id -u)/*/metadata.json` no longer matches the pushed head: say the last scan predates this diff.
- `Still waiting on you`: prior-run `needs-human` items still open, each with its saved `decision_context`.
- `Reopened`: threads a prior run resolved that came back, and what the newest comment asks.
- The same file and concern fixed in two or more prior runs on this PR.

Before printing, write the summary block verbatim to `$RUN_DIR/summary.md`, then write `$RUN_DIR/metadata.json`:

```json
{
  "run_id": "<run-id>",
  "pr": "<PR url>",
  "repo": "OWNER/REPO",
  "host": "github.com",
  "branch": "<headRefName>",
  "mode": "full | targeted",
  "tokens": ["no-push"],
  "head_before": "<HEAD at step 1>",
  "head_after": "<the committed sha, or head_before when nothing was committed>",
  "patch_id": "<see below, or null>",
  "counts": {"fixed": 0, "fixed-differently": 0, "not-addressing": 0, "declined": 0, "question": 0, "needs-human": 0},
  "resolved_thread_ids": [],
  "left_open_thread_ids": [],
  "pushed": "<true only when step 6 pushed, false under no-push or a failed push>",
  "validation": "<the Validation line>",
  "ci": "<the CI line>",
  "completed_at": "<ISO 8601 UTC>"
}
```

`patch_id` stamps the PR diff as it stands after this run, so a later review can tell whether it saw this code: `git diff "$(git merge-base origin/<baseRefName> HEAD)" HEAD | git patch-id --stable | cut -d' ' -f1`. Under `dry-run` write the same object with `pushed: false`, `head_after` equal to `head_before`, and empty id lists.

If a blocking question tool is available (`AskUserQuestion` in Claude Code; call `ToolSearch` with `select:AskUserQuestion` first if the schema is not loaded), use it to present the `needs-human` decisions together. After the user decides, fix the code, push, and resolve. Fall back to waiting in conversation only when no such tool exists.
