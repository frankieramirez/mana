## Stage 2: Read the board

Read branch state and summary lists for open maps, build efforts, ready work, and the inbox. Inspect frontiers and effort members only as their precedence rows become candidates. Once a route wins, leave lower-priority detail as `not inspected`; keep summary counts already read. Read closed maps only under the condition below. A read that fails is reported as unknown in the report, never treated as empty.

### 2a. Signals

**The branch.** The current branch, its work in progress, and whether it has an open pull request:

```bash
git rev-parse --abbrev-ref HEAD
gh repo view --json defaultBranchRef --jq .defaultBranchRef.name
git status --porcelain
git log --oneline <default branch>..HEAD
git rev-list --count @{upstream}..HEAD
gh pr view --json number,title,url,state,isDraft
```

When `gh repo view` fails, the default branch is `git symbolic-ref --short refs/remotes/origin/HEAD` with the `origin/` prefix removed. Work in progress means the current branch is not the default branch and either `git status --porcelain` has a line that does not start with `??`, or the log ahead of the default branch is non-empty. Untracked files alone are not work in progress, and a branch with no upstream still counts through the log. The upstream comparison identifies unpushed commits; if no upstream exists, report `no upstream` instead of inferring push state from the default-branch comparison. A closed or merged PR is historical context, not an open PR.

`gh pr view` failing with `no pull requests found for branch` on stderr means no pull request. Any other failure (auth, host, network) is `unknown: <first stderr line>` in the Branch row, and the first two rows of 2b are skipped for this run because their condition cannot be read.

**Open maps.** List open maps, deduplicating by URL. When the map row becomes a candidate, read frontiers until one is available:

```bash
bash "<SKILL_DIR>/scripts/tickets.sh" <adapter flags> list scry:map
bash "<SKILL_DIR>/scripts/tickets.sh" <adapter flags> list wayfinder:map
GH_HOST=<host> bash "<SKILL_DIR>/scripts/map.sh" frontier MAP_NUMBER
```

The first frontier row is the ticket a walk would take: open, unblocked, unclaimed, in map order.

**Build efforts.** Find issues carrying the exact body line `Work kind: build`. Read members only when evaluating an open effort:

```bash
bash "<SKILL_DIR>/scripts/tickets.sh" <adapter flags> find "Work kind: build"
bash "<SKILL_DIR>/scripts/tickets.sh" <adapter flags> children PARENT_ID
bash "<SKILL_DIR>/scripts/tickets.sh" <adapter flags> view MEMBER_ID
```

Use [build.md](build.md) to evaluate an effort. A summary may show open effort titles without member counts until that detail is inspected.

**Ready tickets.** The oldest ready ticket nobody holds and nothing blocks, without claiming it:

```bash
bash "<SKILL_DIR>/scripts/tickets.sh" <adapter flags> next <ready string>
```

Never pass `--claim` here. Portal decides; the routed skill claims.

**The inbox.** Issues waiting on triage:

```bash
bash "<SKILL_DIR>/scripts/tickets.sh" <adapter flags> list <needs-triage string>
bash "<SKILL_DIR>/scripts/tickets.sh" <adapter flags> list --unlabeled
```

**The roadmap.** Only when a `Roadmap:` line exists in the `## Agent skills` block, or `find "Work kind: roadmap"` returns exactly one open issue. Read its body with `view` and take the first `### n. <name>` whose `Status:` line is not `done` as the current milestone, with the done count over the total. This is a body read only; portal never recomputes status or writes the roadmap.

**Finished maps with no build effort.** Only when there is no open map, no open effort, and nothing ready. A closed map is one the `find` for `## Not yet specified` returns in a closed state. For each, search for its URL in `Planning source:` and `Builds toward:` lines with `find`; a map with no hit is a plan nobody has sliced.

### 2b. Choose the route

For an open branch PR, load [pr.md](pr.md) before evaluating the first row. Take the first row whose condition holds. Report the others as context, never as a second recommendation.

| Condition | Route to | Why it comes first |
|-----------|----------|--------------------|
| The branch's open PR has changes requested, unresolved review feedback, or failing checks | `remedy` for one pass over the feedback, or `ward` to stay with the PR until it merges. Prefer `ward` when checks are still running or the PR is expected to gather more feedback; prefer `remedy` for a batch that is already in | Work someone already reviewed is the closest to done |
| The branch has work in progress as defined in 2a and no PR | `scan` on the branch, then `reveal` to open the PR | Unfinished work on the branch is lost context if it sits |
| An open map has a frontier ticket | `scry` on that ticket | A decision blocks every build ticket behind it |
| An open build effort has an available ticket | `cast` on that ticket, by id | Build order wins over the global queue, since a global `next` can belong to another effort |
| A ready ticket is available and no effort claims it | `cast` on that ticket, by id | The board says it is ready |
| An open build effort has no available ticket | `conjure` on the effort, for a progress check. Name what holds it: open PRs awaiting review, claimed tickets and who holds them, and the blockers of every blocked ticket. When a blocker is itself a ready unblocked ticket, route to `cast` on the blocker instead | Something is pending and the person needs to see what |
| The inbox has issues | `sift` | Untriaged reports become ready tickets |
| A closed map has no build effort | `conjure` on the map | The plan is done and nobody has sliced it |
| A roadmap exists and has a milestone that is not `done` | `vision`, for its report and next prompt | The board is clear, and the roadmap says what to start |
| None of the above | Nothing to route. Say the board is clear and that `scry` charts a new map from a loose idea, or `vision` charts a roadmap | |

When the inbox has issues and a higher row also holds, mention the inbox count in the report so it does not rot, and keep the single route.
