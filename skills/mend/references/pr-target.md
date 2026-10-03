# Prepare a PR target

Load at Stage 1 for a PR target, and keep using it through Stage 6. The bundled `scripts/prepare-pr.sh` selects the head, fetches the base, and records both for this checkout; it never merges, and it pushes only through `--push`. Invoke it by its literal skill path as shown in SKILL.md.

## Input and repository boundary

Keep the user's target in `mend_target` as data through argument passing or a safe input read. The helper uses `gh pr view` to get state, head, base, and the canonical PR URL. That URL identifies the base repository. It resolves origin's fetch URL and every push URL through `gh repo view` and compares their canonical repository URLs with the PR's repository, including the host. When gh cannot reach an SSH host alias such as `git@work:owner/repo.git`, the helper maps the alias to its real host with `ssh -G` and resolves that instead. An unreadable identity or mismatch stops before any fetch or branch switch. No assumption about the configured default repository is used.

Closed PRs and fork PRs stop. An unfinished Git operation or dirty starting checkout also stops. These checks do not override an explicit user instruction to prepare only or hold publication.

## The record

Shell variables do not survive between an agent's tool calls, and Weaver, the audit, and the checks all run between Stage 1 and the push. So the helper writes its fields to a private file in this checkout's git directory, and every later step reads them back:

```bash
bash "<SKILL_DIR>/scripts/prepare-pr.sh" --field base_ref
```

Use the read inside the command that needs it, as a quoted command substitution such as `"$(bash "<SKILL_DIR>/scripts/prepare-pr.sh" --field base_ref)"`. Never retype a field's value into shell text. The reader splits each line on its first `=`, so a branch name containing or ending in `=` survives. The helper's stdout carries the same fields for the report; never source or evaluate it.

| Field | Meaning |
|-------|---------|
| `start` | Starting branch, or short commit when detached |
| `head` | Validated PR head name |
| `base_ref` | Full fetched base ref to merge |
| `push_ref` | Full PR branch ref on origin, including when no switch happened |
| `mode` | `current`, `created`, `existing`, or `detached` |
| `peer_worktree` | Other checkout holding the head, or empty |
| `peer_tip` | That local branch's recorded commit, or empty |

A report that shows a literal command must shell-escape each value, including embedded single quotes; inserting a value inside double quotes is insufficient. If a peer path contains a line break, the helper stops because the record cannot represent it.

## Movement and failures

The head fetch explicitly updates `refs/remotes/origin/<head>` and the base fetch explicitly updates `refs/remotes/origin/<base>`. A leading plus in these fetch refspecs refreshes remote-tracking refs after a remote rewrite; it does not force a local branch or a push.

Before moving, the helper counts unpushed commits with full refs. A tag sharing the head's name cannot substitute for the local branch. Another worktree's branch is left in place; this checkout detaches at the fetched head after recording that peer's tip. An existing free branch fast-forwards. An already-current head fast-forwards too, keeps any unpushed commits of its own for the push, and stops when it has diverged from origin. A missing branch is created without `--track`, since a narrowed fetch mapping can prevent Git from configuring tracking even when the fetched ref exists. The PR push destination is recorded explicitly instead.

A failed switch or later fetch stops and reports both the starting and actual current checkout. Earlier fetches may already have refreshed remote-tracking refs. Never describe such a stop as leaving all Git state untouched.

## Publishing and the peer

`--push` is the only way this skill publishes a prepared PR. It refuses a dirty tree, an unfinished operation, and a checkout that moved since preparation. When a peer worktree holds the head, it reruns the peer check: a changed peer tip or checkout holds publication, as does a dirty peer worktree. This is a check, and it does not lock the peer. Changes during a push can still leave the peer divergent; report that limit and preserve its commits. The push never forces, and the helper verifies that origin's ref matches `HEAD` afterwards. The record stays in place so the report can read it.

After a successful push, the other checkout can catch up with `git pull --ff-only origin <shell-escaped-head>` when it is clean and still holds the named head. The explicit remote and head avoid relying on an absent or different upstream. Inspect its current state before recommending the command. A failed fast-forward is a stop to reconcile, never permission to reset, discard changes, or force a push.
