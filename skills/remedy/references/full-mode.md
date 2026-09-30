# Full feedback workflow

Load only for Full mode. Paths beginning with `references/` are relative to the skill directory. Step numbers continue in `references/publication.md`.

## Full mode

### 1. Create the run directory and fetch

Read `references/run-artifacts.md` and create the run directory before fetching.

If no PR number was given, detect it:

```bash
gh pr view --json number -q .number
```

Then pull everything in one call and keep a copy. `<SKILL_DIR>` is the absolute directory this SKILL.md lives in. Substitute the real path every time it appears. Do not assign it to a shell variable first: a sandboxed or worktree-isolated session refuses `bash "$VAR/script.sh"` because it cannot resolve the path to read the script. The Bash tool runs in the user's project and forgets variables between calls, so every block that touches the run directory sets `RUN_DIR` again at the top:

```bash
set -o pipefail
RUN_DIR="<the run directory>";
GH_HOST=<derived-host> bash "<SKILL_DIR>/scripts/pr-threads" fetch PR_NUMBER OWNER/REPO | tee "$RUN_DIR/fetch.json"
```

A non-zero exit from that pipeline stops the run. `tee` can leave an empty or partial `fetch.json` behind, so never triage the file a failed fetch wrote.

Record `HEAD` now as `head_before` for `metadata.json`.

Pass `OWNER/REPO` whenever you parsed it from a URL. Left out, the script asks `gh repo view` in the current checkout, and on a fork-to-upstream PR that points at the fork rather than the base repo.

The output is one JSON object with four keys:

| Key | Contents | Has file/line? | Resolvable? |
|-----|----------|----------------|-------------|
| `pending_review` | Node ID of your own unsubmitted review, or `null` | n/a | n/a |
| `review_threads` | Unresolved inline threads: thread `id`, `isOutdated`, `path`, the four location fields, and `comments` (each with `id`, `databaseId`, `author`, `body`, `url`) | Yes | Yes |
| `pr_comments` | Top-level conversation comments (`author`, `body`, `url`, `createdAt`), PR author excluded | No | No |
| `review_bodies` | Non-empty review submissions (`author`, `state`, `body`, `submittedAt`), PR author excluded | No | No |

**A non-null `pending_review` does not stop the run.** A draft review only matters to workflows that post replies, because GitHub folds those replies into the draft. Nothing here posts, so keep going. Mention the draft in the summary so the user knows it exists.

When the script errors out, `gh pr view PR_NUMBER --json reviews,comments` together with `gh api repos/{owner}/{repo}/pulls/PR_NUMBER/comments` gives you the same material in rougher form.

**Bot comments land in `pr_comments`.** Automated reviewers that post a top-level comment (architecture-reviewer, CodeRabbit summaries, Copilot, Gemini Code Assist, Sonar) carry real, concrete findings there. Read `pr_comments` bodies in full; a table of `Location | Issue` rows inside a bot comment is a list of findings, one item per row, not a single item.

### 1b. Read CI

Skip this under Targeted mode. Fetch the checks on the current head:

```bash
gh pr checks PR_NUMBER --json name,state,link,bucket 2>/dev/null || gh pr checks PR_NUMBER
```

Classify every failing check before touching anything, because one push restarts every check and a separate CI-only push is waste:

- **Touched code.** The failing job's log names a file or test this PR's diff changed. That is a finding. Carry it into the step-3 batch as an item with no reviewer, so it joins the same fix-list and the same push.
- **Untouched code.** The failure sits in files the diff never changed. Check whether the base moved: `git fetch origin <baseRefName> && git merge-base --is-ancestor origin/<baseRefName> HEAD`. Exit 1 means a stale base. Hard rule 2 forbids rebasing here, so record it for the summary: CI fails on code this PR did not touch and the base has moved; rebase or merge the base and rerun. Exit 0 makes it a flake candidate.
- **Flake candidate.** Do nothing yet. The push in step 6 gives a fresh run for free.

Under `dry-run`, report the classification and act on none of it.

### 2. Triage: new vs already handled

Classify each item before processing.

**Prior runs on this PR.** Look through `/tmp/remedy-$(id -u)/*/metadata.json` for runs whose `pr` matches, skipping any whose `tokens` include `dry-run`. Each one is a pointer to what to read; the code is still the only proof that an item was handled.

- A thread in a prior run's `resolved_thread_ids` that is unresolved now was reopened. Read the comments newer than that run's `completed_at` before judging it. The newest human comment is the ask.
- A `needs-human` item in a prior run's `items.json` whose thread is still open with no human reply since then is not re-judged. It goes under `Still waiting on you` in the summary with the saved `decision_context`. A human reply on that thread is the decision: judge the item as `fixed` along that answer.
- A `pr_comment` or `review_body` item whose `outcome.status` was `fixed` in a prior run, matched by url: open the cited location first. The change being present means already handled.

When the same file and concern was fixed in two or more prior runs on this PR, say so in the summary. Repeated rounds on one spot usually point at a design problem. This is a note, never a stop.

**Review threads.** Read the thread's comments. A substantive reply that acknowledges the concern but defers action ("need to align on this", "going to think through this", options presented without resolution) is a **pending decision**: do not reprocess it. Only the original reviewer comments with no substantive response means **new**.

**PR comments and review bodies.** These have no resolve mechanism, so they reappear every run. Two filters in order:

1. **Actionability.** Skip items with no actionable feedback or question: review wrapper boilerplate ("Here are some automated review suggestions..."), approvals, status badges, CI summaries with no ask. If there is nothing to fix, answer, or decide, drop it from the count entirely.
2. **Already handled.** Check whether the current code already reflects the change. Since this skill leaves no reply trail, **the code is the only evidence** that an item was handled: read the cited location and see whether the fix is present. A prior run's commit is a strong signal; `git log --oneline` on the branch for prior "address review feedback" commits helps.

Judge the words on the page; the account that posted them is irrelevant. A bot asking for a specific change is actionable even though the boilerplate header around that request is filler.

**Drop quietly.** An item with nothing to act on disappears: no mention in the task list, no line in the summary, no place in the totals.

If nothing is new, skip to step 8.

### 3. Judge every item (the gate)

Judge all **new** items here, in your own context, before dispatching any fix. Read `references/evaluation-rubric.md` now and apply it across the whole batch at once.

Holding the whole set is what a per-thread subagent lacks. You read each file once for all of its threads, you notice when one source is wrong in the same way across several items, and you spend the deep reads on the few items that deserve them.

Produce a verdict per item and sort into two lists:

- **fix-list**: `fixed` / `fixed-differently`. Dispatched in step 4. For each, record the file and location (the resolved location or anchor for an outdated thread) plus a one-line change note. **Class fix:** when the cross-item pass turned up sibling sites this PR touched that share the invariant, fold them into **one** fix-list item that lists every `file:line` and every feedback ID it covers, so a single fixer edits them together.
- **skip-list**: `not-addressing` / `declined` / `question` / `needs-human`. No code change. Write the *explanation for the user* now, with the evidence still open. This is the text a replying workflow would have posted; here it goes in the summary.

Put the new items in a task list tagged by verdict so the user can watch progress.

**At scale: scouts.** The verdict never leaves this context. The reads may. When there are more than 12 new items, or the new items span more than 6 files, send read-only scouts to gather the evidence first and judge every item from their returns. Below that, read the files yourself in file-clustered groups of 8 to 10 and grow the two lists as you go.

Read `references/scout-prompt.md`. Cluster the new items by file as that file describes, fill its slots once per cluster, and dispatch scouts in capacity-sized batches under the dispatch rules in step 4. Retain each returned task ID and collect every scout through the host's supported completion mechanism before applying the rubric. Each scout writes `$RUN_DIR/scouts/<cluster>.json` and returns the same object. Then apply the rubric; its section "When scouts gathered the evidence" says which field feeds which verdict. A scout's claim without a quoted `file:line` is an unread file, so open that one yourself. A scout whose artifact is missing or fails to parse leaves its items to you: judge them inline and say so in the summary. Scouts never see a verdict and never propose one.

Record every judged item in `$RUN_DIR/items.json`: `id` (thread node id or comment url), `feedback_ids` for a class item, `type`, `author`, `path`, the four location fields, `read_depth` (`hunk`, `file`, `history`, or `scout`), `verdict`, `evidence`, and either `change_note` with `sites` for the fix-list or `explanation` (plus `decision_context` when there is one) for the skip-list. Later steps add `outcome`, `verified`, and `resolved` to the same objects.

If the fix-list is empty, skip to step 7.

Under `dry-run`, load `references/publication.md` step 9 only, report the two lists, write `summary.md` and `metadata.json` as step 9 describes with `dry-run` in `tokens`, and stop. The summary holds the two lists in the step 9 shape. `items.json` is the plan and stays on disk.

After judgment, load `references/publication.md` at step 4 for fixes, or step 7 when the fix-list is empty. That reference owns verification, publication, and the final summary.
