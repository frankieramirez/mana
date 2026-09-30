# Scope and intent

Load at Stage 1, continuing through Stage 2. Paths beginning with `references/` are relative to the skill directory.

## Stage 1: Determine scope

Compute the diff range, file list, and diff. Combine into as few commands as possible.

**`base:` given (fast path).** The caller knows the base. Skip all detection:

```bash
BASE_ARG="<base_arg>"; BASE=$(git merge-base HEAD "$BASE_ARG" 2>/dev/null) || BASE="$BASE_ARG"
echo "BASE:$BASE" && echo "FILES:" && git diff --name-only $BASE && echo "DIFF:" && git diff -U10 $BASE && echo "UNTRACKED:" && git ls-files --others --exclude-standard
```

**PR number or URL given.** Do **not** check out the PR branch. First probe state:

```bash
gh pr view <number-or-url> --json state,title,body,files
```

Stop when `state` is `CLOSED` or `MERGED` (`PR is closed/merged; not reviewing.`). Stop for an obviously automated PR that does not warrant review (lock-file or manifest-only bumps, release commits, chore version increments). When in doubt, review it: a skipped review that should have run costs more than an unnecessary one.

Then fetch metadata without checkout:

```bash
gh pr view <number-or-url> --json title,body,baseRefName,headRefName,headRefOid,isCrossRepository,url,files --jq '{title, body, baseRefName, headRefName, headRefOid, isCrossRepository, url, files: [.files[].path]}'
```

Set `BASE:` to the marker `pr:<number>`. Classify the scope mode; a matching branch name alone is not enough, since a fork PR or stale local branch can share a name while pointing at unrelated code:

**`local-aligned`** requires all three: `git rev-parse --abbrev-ref HEAD` equals `headRefName`; `isCrossRepository` is false; and `git merge-base --is-ancestor <headRefOid> HEAD` exits 0. Then local Read, Grep, and blame are valid for changed paths. Resolve `<base-ref>` from `baseRefName` (fetch if needed), compute `BASE=$(git merge-base HEAD <base-ref>)`, and take `FILES:` / `DIFF:` from the **local** tree (`git diff --name-only $BASE`, `git diff -U10 $BASE`). Do not append `gh pr diff` hunks; when unpushed fixes exist the local tree is canonical. Note `scope: local-aligned` in Coverage.

**`pr-remote`** otherwise. `FILES:` from the PR `files` array, `DIFF:` from `gh pr diff <number-or-url> --color=never`. If that fails, stop with an actionable error; never fall back to checkout. Then best-effort fetch both ends without checkout:

```bash
git fetch --no-tags origin <headRefName>:refs/review/pr-<number>-head
git fetch --no-tags origin <baseRefName>
```

On success set `PR_HEAD_REF=refs/review/pr-<number>-head` and `PR_BASE_REF=$(git rev-parse FETCH_HEAD)` and pass both to reviewers. On failure, omit and note it in Coverage; reviewers then rely on diff hunks only and must **not** assume `main` as a base. In `pr-remote`, reviewers and validators must not Read or Grep workspace paths for changed files: use `git show <PR_HEAD_REF>:<path>` or the hunks.

**Branch name given.** Do not check it out. If it equals the current branch, use the standalone path. Otherwise: if a PR exists for it (`gh pr view <branch> --json baseRefName,url,headRefName`), prefer the PR path. Else resolve `origin/<branch>` (fetching if needed), compute `BASE=$(git merge-base <base-ref> <branch-ref>)`, and diff `$BASE <branch-ref>`. If the ref cannot be resolved locally, stop: "Cannot diff branch `<branch>` without checkout. Check out that branch, pass its PR URL, or review the current branch with `base:`." This is **`branch-remote`** scope, with the same no-workspace-inspection rule as `pr-remote`.

**No argument (standalone).** Resolve the base from `gh pr view --json baseRefName,url` for the current branch, then `git config branch.<current>.base` when it is set (worktree tools write it), then the repo's default branch. If no base resolves, **stop**. Do not fall back to `git diff HEAD`: that shows only uncommitted changes and silently misses every committed change on the branch.

```bash
echo "BASE:$BASE" && echo "FILES:" && git diff --name-only $BASE && echo "DIFF:" && git diff -U10 $BASE && echo "UNTRACKED:" && git ls-files --others --exclude-standard
```

`git diff $BASE` without `..HEAD` diffs the merge base against the working tree, so committed, staged, and unstaged changes all appear.

### Stage 1b: Deterministic signals

Run the bundled classifier on the same range. Working tree modes pass only `--base`; remote modes pass both fetched ends.

```bash
bash "<SKILL_DIR>/scripts/review.sh" signals --base "$BASE"
# pr-remote or branch-remote, when the fetch succeeded:
bash "<SKILL_DIR>/scripts/review.sh" signals --base "$PR_BASE_REF" --head "$PR_HEAD_REF"
```

It prints `executable_lines`, `prose_lines`, excluded file counts (docs, lock, generated, snapshot), per-file classes, path signals (`migrations`, `frontend`, `api`, `tests`, `agent_surface`, `verification`), risk words found on added lines, and `lite_eligible` with its blockers. Keep the object for Stage 3. When the script exits 4 (no `python3`) or the remote fetch failed, count executable lines yourself from the hunks (excluding docs, lock files, generated output, and snapshots) and treat the lite path as ineligible.

## Stage 2: Intent discovery

Understand what the change is trying to do. PR mode: title, body, linked issues, plus commit subjects if the body is thin. Branch mode: `git log --oneline ${BASE}..<branch-ref>`. Standalone: `git log --oneline ${BASE}..HEAD` plus the branch name.

Write a 2 to 3 line intent summary and pass it to every reviewer:

```
Intent: Replace the multi-tier tax rate lookup with a flat-rate computation.
Must not regress tax-exempt edge cases.
```

Intent shapes *how hard each reviewer looks*, never which reviewers are selected. When intent is ambiguous, write the best-effort summary and note the uncertainty in Coverage. Never block on a clarifying question.
