# Pull request evidence

Use this reference in Stage 2 for an open branch PR, or Stage 3 for an explicit PR. Resolve `OWNER`, `REPO`, and `PR_NUMBER` from the PR URL. On Enterprise, pass `GH_HOST=<host>` inline on every `gh` call. A failed read is unknown, never proof that feedback or checks are absent.

Read lifecycle and review state, retaining the full check objects:

```bash
gh pr view PR_NUMBER --repo OWNER/REPO --json number,title,url,state,isDraft,reviewDecision,reviews,statusCheckRollup
```

Closed or merged: report completion and stop routing that PR. For open PRs, inspect unresolved review threads, including every page:

```bash
gh api graphql --paginate -f owner=OWNER -f repo=REPO -F number=PR_NUMBER -f query='
query($owner:String!, $repo:String!, $number:Int!, $endCursor:String) {
  repository(owner:$owner, name:$repo) {
    pullRequest(number:$number) {
      reviewThreads(first:100, after:$endCursor) {
        nodes { isResolved }
        pageInfo { hasNextPage endCursor }
      }
    }
  }
}' --jq '.data.repository.pullRequest.reviewThreads.nodes[] | select(.isResolved == false)'
```

`reviewDecision == CHANGES_REQUESTED` or any unresolved thread is feedback waiting. `reviews` distinguishes no submitted review from an empty aggregate decision. General PR comments are not resolved threads; inspect them if the user specifically points to feedback there.

For `CheckRun` objects, retain `status` and `conclusion`: a status other than `COMPLETED` is pending; completed `FAILURE`, `TIMED_OUT`, `CANCELLED`, `ACTION_REQUIRED`, or `STARTUP_FAILURE` needs attention. For legacy `StatusContext` objects, `PENDING` is pending and `FAILURE` or `ERROR` needs attention. Successful, neutral, or skipped checks do not imply failure. An empty rollup means no reported checks, not verified CI success.

For board routing, feedback waiting or failed checks selects the first precedence row. Prefer `remedy` for a settled batch; prefer `ward` if checks are pending alongside that feedback, or the user wants continuing attendance. Pending checks alone do not satisfy the board's feedback/failure condition.

For an explicit open PR, route waiting feedback or failed checks the same way. Otherwise use `scan` when no submitted review exists, and `ward` for continuing attendance on an already reviewed PR. Honor an explicit review or attendance request. If a required read fails, report which evidence is unknown; use another observed positive signal when one establishes the route, otherwise leave the PR route unresolved.
