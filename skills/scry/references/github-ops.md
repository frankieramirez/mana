# GitHub operations

`scripts/map.sh` owns every write that shapes the map. It needs `gh` authenticated against this checkout. Set `GH_HOST` on every call when the remote is GitHub Enterprise (derive the host from `gh repo view --json url --jq .url`).

`SKILL_DIR` is the absolute directory of this skill. Set it on the first line of every Bash call.

| Subcommand | Arguments | What it does |
|------------|-----------|--------------|
| `ensure-labels` | none | Creates `wayfinder:map` and `wayfinder:{research,prototype,grilling,task}` if missing |
| `create-map` | `TITLE`, body on stdin | Opens an issue labelled `wayfinder:map`. Prints `number<TAB>url` |
| `create-ticket` | `MAP_NUMBER TYPE TITLE`, body on stdin | Opens a child labelled `wayfinder:TYPE`, attaches it as a sub-issue. Prints `number<TAB>url` |
| `wire` | `CHILD_NUMBER BLOCKER_NUMBER` | CHILD is blocked by BLOCKER (database id under the hood) |
| `frontier` | `MAP_NUMBER` | Open, unblocked, unclaimed children, map order. TSV: `number<TAB>title<TAB>type<TAB>url` |
| `claim` | `NUMBER` | Assigns the issue to the current `gh` user |
| `view` | `NUMBER` | Prints number, title, url, state, labels, assignees, body |
| `parent` | `NUMBER` | Prints the parent map number, or empty |
| `comment` | `NUMBER`, body on stdin | Posts a comment |
| `close` | `NUMBER` | Closes the issue |
| `update-body` | `NUMBER`, body on stdin | Replaces the issue body |

Without `owner/repo`, the script uses `gh repo view` in this checkout.

## Exit codes

| Code | Meaning |
|------|---------|
| 0 | Done |
| 1 | Usage or unexpected `gh` failure |
| 3 | GitHub refused the write (HTTP 403, or "Resource not accessible"). Load `scratch.md` |

## Conventions the script already encodes

- Children are GitHub sub-issues. When that API is missing, `create-ticket` writes `Part of #<map>` at the top of the child and the agent adds a task-list line on the map via `update-body`.
- Blocking uses native `blocked_by`. When that API is missing, `wire` writes `Blocked by: #<n>` at the top of the child.
- The frontier drops any child with an assignee or an open blocker.
- Claim is the assignee. That is the whole claim.

Do not call `gh issue create`, `gh api .../sub_issues`, or `gh api .../dependencies` yourself. The script is the one place those sequences live.
