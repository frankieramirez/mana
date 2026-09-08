# GitHub operations

`scripts/map.sh` owns every write that shapes the map. It needs `gh` authenticated against this checkout. Set `GH_HOST` on every call when the remote is GitHub Enterprise (derive the host from `gh repo view --json url --jq .url`).

`<SKILL_DIR>` is the absolute directory of this skill. Write the real path into every Bash call instead of assigning it to a shell variable.

`frontier` and `view` read `wayfinder:*` labels as their `scry:*` equivalents. Nothing writes the old names.

| Subcommand | Arguments | What it does |
|------------|-----------|--------------|
| `ensure-labels` | none | Creates `scry:map` and `scry:{research,prototype,grilling,task}` if missing |
| `create-map` | `TITLE`, body on stdin | Opens an issue labelled `scry:map`. Prints `number<TAB>url` |
| `create-ticket` | `MAP_NUMBER TYPE TITLE`, body on stdin | Opens a child labelled `scry:TYPE`, attaches it as a sub-issue. Prints `number<TAB>url` |
| `wire` | `CHILD_NUMBER BLOCKER_NUMBER` | CHILD is blocked by BLOCKER (database id under the hood) |
| `frontier` | `MAP_NUMBER` | Open, unblocked, unclaimed children, map order. TSV: `number<TAB>title<TAB>type<TAB>url` |
| `children` | `MAP_NUMBER` | All native and fallback children, including closed, assigned, and blocked tickets. TSV: `number<TAB>state<TAB>title<TAB>url`. Read failures exit 1 |
| `close-map` | `MAP_NUMBER` | Requires a map label and refuses any open child or unverifiable child state. Already closed is a no-op. The agent must first check Destination, Notes, and unresolved fog in Stage 3f |
| `claim` | `NUMBER` | Assigns the issue to the current `gh` user. Exits 1 if someone else already holds it |
| `view` | `NUMBER` | Prints number, title, url, state, labels, assignees, body |
| `parent` | `NUMBER` | Prints the parent map number, or empty |
| `body` | `NUMBER` | Prints the raw issue body |
| `comment` | `NUMBER`, body on stdin | Posts a comment |
| `close` | `NUMBER` | Closes the issue |
| `update-body` | `NUMBER`, body on stdin | Replaces the issue body. With `--expected-body PATH`, reads the proposed replacement first, then reads the current body and refuses the write if the snapshot is missing, unreadable, or differs. |

Without `owner/repo`, the script uses `gh repo view` in this checkout. The script passes `--repo` to every `gh issue` and `gh label` call so an explicit owner/repo wins.

## Exit codes

| Code | Meaning |
|------|---------|
| 0 | Done |
| 1 | Usage or unexpected `gh` failure |
| 3 | GitHub refused the write (HTTP 403, or "Resource not accessible"). Load `scratch.md` |

## Conventions the script already encodes

- Children are GitHub sub-issues. When that API is missing or refused, `create-ticket` writes `Part of #<map>` at the top of the child and the agent adds a task-list line on the map via `update-body`. If that edit is also refused, the script closes the issue it just opened and exits 3.
- Blocking uses native `blocked_by`. When that API is missing or refused, `wire` writes `Blocked by: #<n>` at the top of the child.
- The frontier finds children via sub-issues, then `Part of #<map>` on open issues and task-list `#N` lines on the map. It does not scrape every `#N` in the map body. It drops any child with an assignee or an open blocker.
- Completion uses `children`, which combines paginated native sub-issues with task-list references and paginated `Part of #<map>` links across all issue states. Native API HTTP 404 or 410 permits fallback discovery; other native read failures and failed fallback reads stop closeout. An empty frontier never proves completion. `close` only closes the supplied issue; use `close-map` for parent closeout.
- Claim is the assignee. The script refuses when another login already holds the ticket.
- Stage 3f saves the original body in a private temporary file before reviewing or deriving a replacement, then passes it to `update-body --expected-body`. A mismatch or read failure stops closeout before `close-map`. This is best-effort stale-snapshot detection: a concurrent edit can still land between the comparison and the write, because the two GitHub calls are not an atomic compare-and-swap.

Do not call `gh issue create`, `gh api .../sub_issues`, or `gh api .../dependencies` yourself. The script is the one place those sequences live.
