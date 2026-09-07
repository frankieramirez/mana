---
name: mend
description: "Resolve an in-progress git merge, rebase, cherry-pick, or revert that has conflict markers or unmerged paths, or merge a pull request's base into the current branch and resolve what conflicts. Use when asked to mend, resolve merge conflicts, fix rebase conflicts, finish a conflicted rebase or cherry-pick, resolve the conflicts on this PR, my PR has conflicts, merge main into this branch, bring this branch up to date, /mend, or /resolve-merge-conflicts."
argument-hint: "[blank for the in-progress operation | PR number | PR URL | branch | base:<ref>]"
---

<!-- BEGIN MANA PERSONA -->
## Persona at invocation

Before conversational narration, read `Persona:` and `Style:` in the active project's `## Agent skills` block from `CLAUDE.md` or `AGENTS.md`. Prefer the file containing the block, then an existing file; ties use `CLAUDE.md`. A symlink pair is one file. Read the saved value anew on each invocation, including from a subdirectory using the project root. No accessible project or no line means ordinary behavior. Do not search another project or global settings for this preference.

During the `Persona at invocation` stage, `archmage` on either line loads this skill's own [references/archmage.md](references/archmage.md) for the active workflow. `off` or an absent value leaves ordinary behavior active. An unknown value leaves ordinary behavior active and gets a brief explanation when conversational output is allowed; it does not stop the work. Explicit conversation instructions override the saved voice without writing settings. A request to enable Archmage for this workflow also loads the local reference.

Apply the voice only to lead-agent conversation. Deliverables, specialist roles, reply-only responses, and JSON-only output retain their contracts, with no added narration. End the persona with this workflow unless the user requests otherwise or a `Style:` line names `archmage`, which keeps the voice on for the whole session.
<!-- END MANA PERSONA -->

# Mend

Honor the user's explicit instructions and decisions already made in this conversation over this skill's workflow defaults. A rule this file states with never, or as read-only, is a gate: it holds whatever the conversation says, and an instruction to cross one is declined and reported. Continue authorized work; ask only about unresolved choices that would materially change the result. Preparing or reviewing work does not authorize publishing it.

If a skill rule requires a pause or leaves requested work unfinished, name and link to the exact SKILL.md and quote the rule. Then explain what decision or prerequisite is missing. Distinguish a required gate from your interpretation.

Finish the merge, rebase, cherry-pick, or revert that is already in progress. With a pull request, branch, or `base:` target, start the merge on the current branch first. Read both sides of every conflict, keep both intents where they fit, and complete the git operation. Never abort.

## Operating principles

- **Already in progress, or named.** With no argument this skill finishes a conflicted operation and never starts one: no merge state means stop. A target is the one thing that lets it start a merge, and only into the branch that is checked out.
- **This branch only.** `git checkout`, `git switch`, and `gh pr checkout` are out. A PR whose head is another branch is a stop that names both branches.
- **Always resolve. Never abort.** `git merge --abort`, `git rebase --abort`, `git cherry-pick --abort`, and `git revert --abort` are out.
- **Both intents stay.** A hunk is two changes talking. Keep both when they commute. When they cannot, keep the change that matches the operation's goal and record the trade-off.
- **Invent nothing.** The resolved file contains only behavior that already lived on one side or both. No new feature, no drive-by cleanup.
- **Ours and theirs follow the operation.** On a rebase, HEAD is the branch you are rebasing onto. The script names both sides. Trust it over memory.

## Arguments

The argument is the target. It only matters when Stage 1 finds no operation in progress; a conflict already in the tree is mended as is.

| Input | Target |
|-------|--------|
| none | The in-progress operation |
| number or PR URL | That pull request's base, if the PR's head is this branch |
| `base:<ref>` | That ref, on the current checkout, with no `gh` call |
| branch name | That branch, fetched from `origin` |

The operation started is a merge of the base into the current branch. An instruction in the conversation to rebase instead is honored, and Stage 5's rebase loop takes it from there.

## Execution spine

1. Read the operation, or start it from the target (Stage 1).
2. Learn why each side changed (Stage 2).
3. Spawn Weaver on the conflicted files (Stage 3).
4. Audit, then run the project's checks (Stage 4).
5. Finish the operation (Stage 5).

---

## Stage 1: State

`<SKILL_DIR>` is the absolute directory this SKILL.md lives in. Substitute the real path every time it appears. Do not assign it to a shell variable first: a sandboxed or worktree-isolated session refuses `bash "$VAR/script.sh"` because it cannot resolve the path to read the script.

```bash
bash "<SKILL_DIR>/scripts/conflict-state"
```

The script prints:

| Field | Meaning |
|-------|---------|
| `operation` | `merge`, `rebase`, `cherry-pick`, `revert`, `am`, `unmerged`, or empty |
| `phase` | `conflicts`, `continue`, or `clear` |
| `head` | Current `HEAD` |
| `ours` | The ref the index calls ours |
| `theirs` | The ref the index calls theirs |
| `onto` | Rebase onto-commit, when there is one |
| `goal` | Subject of the operation (merge message, or the commit being replayed) |
| `files` | Unmerged paths as `path<TAB>kind`, one per line after the field |

`phase=clear` (or empty `operation`) with no target: stop. There is nothing to mend.

`phase=clear` with a target: start the merge, below, then run the script again.

`phase=continue` and an empty `files` list: the markers are gone and the operation still needs a commit or `--continue`. Jump to Stage 4, then Stage 5.

Read `git status` as a second look. A target is the only reason to start a merge; never start one to create work.

### Starting from a target

Every check here is a stop, reported in one line, with the tree untouched.

1. `git status --porcelain` prints anything: stop. Git refuses to merge into a dirty tree, and so does this skill.
2. Resolve the base ref.
   - PR number or URL: `gh pr view <n> --json baseRefName,headRefName`. `headRefName` must equal `git branch --show-current`; otherwise stop and name both branches. The base is `baseRefName`.
   - `base:<ref>`: use the ref as given. No fetch.
   - Branch name: that branch. Fetch it.
3. `git fetch --no-tags origin <base>` for a PR or branch target. The ref to merge is `origin/<base>`.
4. `git merge --no-edit <ref>`.

Exit 0 means the merge was clean: report the new merge commit under `Commit`, `Resolved: 0 files`, and stop. The branch is up to date, which is what the target asked for. Do not push.

A non-zero exit with unmerged paths is the conflict this skill exists for. Run the script again and continue with Stage 2.

---

## Stage 2: Sources

Load `references/sources.md`. For each conflicted file, recover the reason each side changed: the commits that touched the hunk, their messages, and the PR or issue those commits belong to when `gh` can see them.

Write a short brief before anyone edits a file:

```
Operation: <merge | rebase | ...>  Goal: <one line>
Ours (<ref>): <intent>
Theirs (<ref>): <intent>
```

Do not spawn Weaver until that brief exists.

---

## Stage 3: Weave

Read `references/weaver.md` from this skill's directory. Spawn one subagent with that file's full content as its instructions and the Stage 2 brief plus the file list appended. In Claude Code, prefer the installed agent named `weaver` (or `mana:weaver` when installed as a plugin) if it exists; otherwise, or on any other platform, spawn a generic subagent seeded with the reference file. Do not restate or soften its rules in the prompt.

When many files conflict and they do not share imports or types, split the file list across concurrent Weavers. Two Weavers never edit the same file.

---

## Stage 4: Audit and check

Before trusting the tree:

- Every conflict marker (`<<<<<<<`, `=======`, `>>>>>>>`) is gone.
- Weaver edited only unmerged paths. Revert anything else.
- Generated lockfiles were not hand-merged. One side was kept and the lockfile is flagged `REGENERATE`.
- Delete/modify conflicts match the brief: a delete that was the point of that side stays a delete.
- Each trade-off Weaver recorded is real (the two intents could not both live).

A bad report (markers left, scope escaped, invented behavior): restore the conflicted files with `git checkout -m -- <file>`, spawn Weaver once more with the failures named, and audit again. A second failure ends the run: report it and stop. Leave the operation in progress.

For each `REGENERATE` file, run the project's install or lockfile command (`npm install`, `pnpm install`, `cargo generate-lockfile`, and so on) so the lockfile matches the merged manifest. Do this before the checks.

Then load `references/checks.md` and run what the project already has. Fix anything the merge broke. Fixes stay inside the conflicted files and their direct fallout (a test that failed because the merge dropped an import). New behavior is still out.

---

## Stage 5: Finish

Stage the resolved files. Then complete the operation:

| Operation | Command |
|-----------|---------|
| merge | `git commit --no-edit` (reuses `MERGE_MSG`) |
| rebase | `GIT_EDITOR=true git rebase --continue`, then repeat from Stage 1 if the next commit conflicts |
| cherry-pick | `GIT_EDITOR=true git cherry-pick --continue`, then repeat from Stage 1 if more commits remain |
| revert | `GIT_EDITOR=true git revert --continue` |
| am | `GIT_EDITOR=true git am --continue` |
| unmerged | Stage the files. Do not commit. There is no operation message to reuse. |

A rebase or cherry-pick of several commits is a loop: resolve, continue, and if the next commit conflicts, go back to Stage 1. Do not stop after the first commit unless the sequence is done.

Never `--skip` a commit unless it is empty after resolution (the change already landed) and `git rebase --continue` refuses it. Record each skip.

Do not push. The caller pushes.

## Report

```
Mend: <operation>  Goal: <one line>
Resolved: <n> files
Continues: <n>  Skips: <n>

Trade-offs
- <file>: <what was dropped, and why>

Checks: <one line>
Commit: <sha or rebase HEAD>
Open: <anything left conflicted, or none>
```

## References

| Reference | Load at | Purpose |
|-----------|---------|---------|
| `references/sources.md` | Stage 2 | Recover intent from git and GitHub |
| `references/weaver.md` | Stage 3 | The agent that resolves hunks |
| `references/checks.md` | Stage 4 | Find and run the project's checks |
