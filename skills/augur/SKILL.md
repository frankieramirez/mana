---
name: augur
description: "Find what a change could break beyond its diff, name the one fact it is safe because of, and prove that fact by running real code instead of writing it up. Use for blast radius, what could this break, is this change safe, what else does this touch, reviewing a small diff you do not trust, or /augur."
argument-hint: "[blank for current branch's diff | base:<ref> | PR number | path]"
---

# Augur

Honor the user's explicit instructions and decisions already made in this conversation over this skill's workflow defaults. Continue authorized work; ask only about unresolved choices that would materially change the result. Preparing or reviewing work does not authorize publishing it.

If a skill rule requires a pause or leaves requested work unfinished, name and link to the exact SKILL.md, quote the rule, and explain what decision is missing. Distinguish a required gate from your interpretation.

Listing the callers is not the job. Any grep does that in a second. The job is the breakage grep will not show, and then a proof that the change is safe, produced by running code rather than by writing a convincing paragraph.

A writeup that sounds right is worthless on its own. It reads as convincing whether or not it is true. So the deliverable is one or two facts the whole thing depends on, each pushed as far up the evidence ladder as is cheap, with the rung named.

## Scope

Never switch branches. The argument selects what to read, never permission to mutate the tree.

- `base:<ref>`: diff the current checkout against that ref. `BASE=$(git merge-base HEAD <ref>)`.
- PR number or URL: `gh pr view <n> --json baseRefName,headRefName,headRefOid,files` and `gh pr diff <n> --color=never`. Read changed files with `git show <sha>:<path>` after `git fetch --no-tags origin <headRefName>`; do not check the PR out.
- A path: the working-tree change under that path against the branch base.
- Blank: the current branch against its PR base (`gh pr view --json baseRefName`) or the repo's default branch.

```bash
echo "BASE:$BASE" && git diff --name-only "$BASE" && git diff -U10 "$BASE" && echo "UNTRACKED:" && git ls-files --others --exclude-standard
```

Untracked files are in scope. `git diff` never shows them, and a new file is exactly the kind of change whose reach nobody has looked at yet. Read each one in full.

## The evidence ladder

Every safety fact reports the rung it reached. Never round up.

| Rung | What you have |
|------|---------------|
| 1 | You said so. Worthless alone. |
| 2 | You pointed at the line: a real `file:line`, or the library's own source at the pinned version. |
| 3 | You walked the failure path step by step and showed it cannot reach. |
| 4 | You ran it: a script or test that calls the real code and fails loud when you are wrong. |
| 5 | You reproduced it in the running app. |

A fact below rung 4 is reported as unproven, in those words. Rung 4 is usually one small script that imports the same library the app ships and calls the exact function in question. When the change is config, a script, or prose that a tool consumes, the real code is that tool: run the validator, the parser, or the loader against the changed file and against a deliberately broken copy.

## Steps

### 1. Read the change

The diff, the symbols it adds, changes, and deletes, and what the code now does differently, including the part the diff does not spell out. For a PR, read the title, body, and commit subjects for the stated intent, then compare it to what the diff actually does.

### 2. Find the one fact it is safe because of

Most changes that look scary are safe because of a single fact, such as "this call only drops cache entries that are already expired and touches nothing else." Find that fact. When it holds, most of the scary cases die at once. Spend the time here, not on a long list of maybes. A wide change may have two such facts. More than three means the change is several changes, so say that.

### 3. Look where grep stops

- The source of the library you call, at the pinned version in the lockfile, plus any local patch of it.
- When things run: microtasks, unmount and teardown, request lifecycle, retries.
- What a symbol search misses: the JSON an API returns, a database column, a wire format, another language reading the same bytes, a feature flag, code three hops downstream.
- Callers that reach the symbol by string: reflection, dynamic dispatch, config keys, route tables.

### 4. Rate each risk

For each, name how it breaks, the `file:line`, how likely it is, and how bad it would be. Keep the risks you confirmed. List the ones you checked and cleared separately. A search that finds nothing is an answer; write it down as one. Never invent a caller or an API.

### 5. Prove the fact

Read `references/proof.md` now. Write a script that runs the real code, run it, and paste what happened. If a cheap proof is impossible (it needs infrastructure, secrets, a device, or an hour), say so and stop at the highest rung reached. Do not substitute a paragraph for the run.

### 6. Widen for a large change

When step 2 produced more than one safety fact, dispatch two generic subagents with the same brief (the diff, the candidate fact, the ladder) and merge their answers. Different runs catch different real bugs. Keep the merge in this context; subagents return findings, they do not post or edit.

## Report

Write it under this repo's dispel rules when that skill is installed; otherwise plain sentences, no dashes. Cite real code. Strip anything private before it goes anywhere public.

```
What it does
<what changed, including the part that is not obvious>

The fact it is safe because of
<the fact>. Rung <n>. <proof output, or "unproven: <why>">

Risks
- <how it breaks> at <file:line>. Likely: <low|medium|high>. Cost: <low|medium|high>. Check: <how>.

Cleared
- <what you checked and why it is fine>

Before you merge
- <the cheapest test or repro that catches the real bug, including the script you wrote and its path>
```

## References

| Reference | Load at | Purpose |
|-----------|---------|---------|
| `references/proof.md` | Step 5 | How to write and run the proving script |
