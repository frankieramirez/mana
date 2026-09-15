## Stage 3: Route one issue

Read it first:

```bash
bash "<SKILL_DIR>/scripts/tickets.sh" <adapter flags> view ID
```

When `view` fails and the tracker shares numbers with pull requests, try `gh pr view ID --json number,title,url,state`. For a PR, load [pr.md](pr.md). If neither read succeeds, report unknown and stop.

Resolve state before labels. A closed map or closed map ticket uses its dedicated row below. Any other closed issue is done: route its `Build parent:` when present, otherwise stop. A closed or merged PR is done and does not enter a repair or attendance workflow. Only open targets reach the remaining label-based routes. Classify in this order:

| What it is | How to tell | Route to |
|------------|-------------|----------|
| A pull request | `view` fails, `gh pr view` succeeds | Use [pr.md](pr.md) to choose `scan`, `remedy`, or `ward` from observed evidence |
| A map | Label `scry:map` or `wayfinder:map` | Open: `scry` on the first frontier row, or on the map itself when the frontier is empty, so scry can report what keeps it open. Closed: search `Planning source:` and `Builds toward:` for the map URL with `find`; an effort found routes to `cast` on its available ticket or `conjure` for its progress; none found routes to `conjure` on the map |
| A map ticket | Label `scry:<type>` or `wayfinder:<type>` | Open and unclaimed: `scry` on it. Claimed by someone else: say who holds it and stop. Closed: route its parent map instead (`map.sh parent ID`) |
| A build effort | Body has the exact line `Work kind: build` | Its available ticket to `cast`, else `conjure` for a progress check, using [build.md](build.md) |
| A ready ticket | Carries the ready label | Run `blocked ID`. No open blocker and no other assignee: `cast` on it. Blocked: name every open blocker, then route the first blocker through this table instead, one hop only. Held by someone else: say who and stop |
| Waiting on a person | Carries the `ready-for-human` or `needs-info` string | Say what it waits for and stop. `sift` can move it once the answer lands |
| Untriaged | Carries the `needs-triage` string, or no label at all | `sift` on it |
| Anything else | An open issue with only category labels | `sift` on it, since it has no state the other skills read |

Resolve the current tracker identity before treating an assignment as yours, using `gh api user --jq .login` on GitHub or the configured tracker identity elsewhere. Unknown identity does not establish ownership. A ticket already assigned to the person driving this session is theirs; route it as if unclaimed and say it is already claimed.
