# Ship session files

A session that charts or walks a map often leaves files behind: a research note, a `CONTEXT.md` term, an ADR, an owning doc, a prototype, local ticket files. This stage finds them and offers to put them on a pull request, so the user never has to ask whether anything changed.

## Find the files

Compare the tree now with the baseline Stage 1 printed:

```bash
git status --porcelain=v1 -uall
```

A session file is a path that shows up now and was clean at baseline. Add any path the session knows it wrote: a research subagent's returned path, a prototype, a glossary or ADR edit. A path that was already dirty at baseline holds the user's own work. Leave it out of the commit even when this session also edited it, and list it under **Left alone** in the report.

No session files means nothing to ship. Say `No files changed this session.` in the report and stop here.

## Ask, unless the user already decided

Opening a pull request publishes work, so it needs a yes. `you-pick` covers interrogation answers only and does not count.

| The user said | Do |
|---------------|----|
| `pr`, or asked in this conversation for a commit, push, or PR | Ship without asking |
| `no-pr`, or asked to leave files alone | List the files and stop |
| Nothing yet | Ask once |

The question lists each session file with its kind (research note, glossary, ADR, owning doc, prototype, ticket file) and names the branch the commit would land on. Offer:

1. **Open a PR** (recommended): commit, push, and open or update the pull request.
2. **Commit only**: a local commit on the branch, nothing pushed.
3. **Leave them**: no git writes. The report still lists the files.

A prototype stays off the main line by default (see `prototype.md`). When one is in the list, the recommended option leaves it out, and a fourth option, **Open a PR with the prototype**, adds it back.

Use the host's question tool when it has one. Otherwise ask in plain text and wait.

## Branch

```bash
gh repo view --json defaultBranchRef --jq .defaultBranchRef.name
git branch --show-current
git config branch.<current>.remote
```

Never commit to the default branch. When the current branch is the default, create one before committing, and the uncommitted files move with it:

```bash
git switch -c <name>
```

The name comes from the `Branches:` line in the `## Agent skills` block of `CLAUDE.md` or `AGENTS.md`. `<id>` is the ticket this session resolved, or the map when charting, and `<slug>` is a short kebab slug of its title. An absent line means `<id>-<slug>`, such as `42-pick-the-queue`.

A branch a worktree tool made (its `HEAD` equals the default branch tip and it has no upstream) gets renamed to that name with `git branch -m <name>`. Any other branch is used as it stands. It may already carry the user's work, which is why the question names it.

## Commit

When the `## Agent skills` block has a `Validation:` line, run it first. On failure, show the output, leave the files uncommitted, and report that. Never commit around a failing check.

Stage only the session files, by path, and commit only those paths so anything the user had staged stays staged and out of this commit:

```bash
git add -- <path> <path>
git commit -m "<subject>" -m "<body>" -- <path> <path>
```

Never `git add -A` or `git add .`. Match the subject style of `git log --oneline -20`. Without a clear convention, use `docs: <ticket title>` for a walk and `docs: chart <map title>` for a chart. The body links the ticket or map URL.

**Commit only** stops here. Report the sha.

## Push and open the pull request

```bash
git push -u origin HEAD
gh pr view --json url --jq .url
```

When the branch already has a pull request, the push updates it. Report its URL and open no second one. Otherwise:

```bash
gh pr create --base <default branch> --title "<subject>" --body-file <tmp file>
```

Write the body in plain prose with no em or en dashes: lead with what the files record, link the ticket or map by name, list each file with its kind, and keep it short. Never use a closing keyword (`Closes`, `Fixes`, `Resolves`) for the ticket or the map. The ticket is already closed, and a merge must never close a map that Stage 3f has not closed.

A push or `gh` failure keeps the commit. Report the error and the branch name so the user can push it. A remote that is not GitHub gets the push and no pull request.

## Link it back

Comment the PR URL on the ticket this session resolved, or on the map when charting, with one line: `Files for this decision: <PR URL>`. On GitHub, use `map.sh comment`. On another tracker, use its Wayfinding operations. A scratch map skips this step, because the commit already carries its ticket files.

## Report

End the session report with:

```
Files: <each path and its kind>
Left alone: <paths dirty before this session, or none>
Commit: <sha> | not committed (<reason>)
Pull request: <url> | none (<reason>)
```
