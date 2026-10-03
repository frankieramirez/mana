# Prepare a PR target

Load at Stage 1 for a PR target, and retain its values through Stage 6. The bundled `scripts/prepare-pr.sh` selects the head and fetches the base; it never merges or pushes. Invoke it by its literal skill path as shown in SKILL.md.

## Input and repository boundary

Keep the user's target in `mend_target` as data through argument passing or a safe input read. The helper uses `gh pr view` to get state, head, base, and the canonical PR URL. That URL identifies the base repository. It resolves origin's fetch URL and every push URL through `gh repo view` and compares their canonical repository URLs with the PR's repository, including the host. An unreadable identity or mismatch stops before any fetch or branch switch. SSH and HTTPS remotes are resolved by gh; no assumption about the configured default repository is used.

Closed PRs and fork PRs stop. An unfinished Git operation or dirty starting checkout also stops. These checks do not override an explicit user instruction to prepare only or hold publication.

## Output as data

Capture the helper's successful stdout in `mend_prepared`; check its exit status before parsing. Read the fields without evaluating them:

```bash
while IFS='=' read -r key value; do
  case "$key" in
    start) mend_start=$value ;;
    head) mend_head=$value ;;
    base_ref) mend_base_ref=$value ;;
    push_ref) mend_push_ref=$value ;;
    mode) mend_mode=$value ;;
    peer_worktree) mend_peer_worktree=$value ;;
    peer_tip) mend_peer_tip=$value ;;
  esac
done <<< "$mend_prepared"
```

| Field | Meaning |
|-------|---------|
| `start` | Starting branch, or short commit when detached |
| `head` | Validated PR head name |
| `base_ref` | Full fetched base ref to merge |
| `push_ref` | Full PR branch ref on origin, including when no switch happened |
| `mode` | `current`, `created`, `existing`, or `detached` |
| `peer_worktree` | Other checkout holding the head, or empty |
| `peer_tip` | That local branch's recorded commit, or empty |

Use quoted variable expansions for subsequent Git calls. Do not rebuild shell source from these values. A report containing a literal command must shell-escape each value, including embedded single quotes; inserting a value inside double quotes is insufficient. If a peer path contains a line break, the helper stops because this output format cannot represent it.

## Movement and failures

The head fetch explicitly updates `refs/remotes/origin/<head>` and the base fetch explicitly updates `refs/remotes/origin/<base>`. A leading plus in these fetch refspecs refreshes remote-tracking refs after a remote rewrite; it does not force a local branch or a push.

Before moving, the helper counts unpushed commits with full refs. A tag sharing the head's name cannot substitute for the local branch. Another worktree's branch is left in place; this checkout detaches at the fetched head after recording that peer's tip. An existing free branch fast-forwards. A missing branch is created without `--track`, since a narrowed fetch mapping can prevent Git from configuring tracking even when the fetched ref exists. The PR push destination is recorded explicitly instead.

A failed switch or later fetch stops and reports both the starting and actual current checkout. Earlier fetches may already have refreshed remote-tracking refs. Never describe such a stop as leaving all Git state untouched.

## Peer handoff

Run the Stage 6 peer check immediately before publishing a detached result. A changed peer tip or checkout holds publication, as does a dirty peer worktree. This is a check rather than an ownership lock. Changes during a push can still leave the peer divergent; report that limit and preserve its commits.

After a successful push, the other checkout can catch up with `git pull --ff-only origin "$mend_head"` when it is clean and still holds the named head. The explicit remote and head avoid relying on an absent or different upstream. Inspect its current state before recommending the command. A failed fast-forward is a stop to reconcile, never permission to reset, discard changes, or force a push.
