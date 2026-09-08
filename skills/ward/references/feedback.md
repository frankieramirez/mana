# Evaluate published feedback

Load during Stage 2 when a snapshot reports feedback. Read inline threads, top-level comments, and review bodies in full. An automated summary can contain multiple actionable findings; evaluate each separately. Ignore unsubmitted reviews and their inline comments until published. Approval-only events and the operator's own status notes usually need no repair.

Judge the batch in the lead context before editing. Read enough current code to defend each verdict, including callers or tests when the finding challenges an invariant. Group repeated claims and identical fixes in code the PR changed. Who wrote the comment does not determine whether it is correct.

Record each finding's source identity and snapshot fingerprint, ask, verdict, code evidence, and proposed change or explanation in the local report. Never build shell expressions from the review body.

| Verdict | Evidence and action |
|---------|---------------------|
| `fixed` | A valid improvement, including a useful nitpick. Implement the ask. |
| `fixed-differently` | The problem is real; explain and implement a better solution. |
| `not-addressing` | Cite where the code already handles it, what replaced the old code, or why the suggestion has no benefit. |
| `declined` | Cite a concrete harm the requested change would cause. |
| `question` | Draft the answer for the user. Leave the thread open. |
| `needs-human` | State what you investigated and the unresolved product or design choice. Leave the thread open and stop attendance. |

Fix valid feedback unless the evidence supports a different verdict. A deliberate-design decision requires both an artifact establishing intent and a real tradeoff reasonable engineers could decide differently. Existing behavior alone proves neither. If a question can be fully answered from the code, report its answer locally and acknowledge only its local snapshot version, leaving the GitHub thread unresolved. Continue watching, but do not claim the PR is review-clean while that thread remains open. An answer requiring human judgment stops the watch.

Outdated inline locations need an anchor check in the named file. Try the current line, then the original location and a manually chosen identifier from the ask. A missing anchor can establish that concrete in-place code disappeared; an uncertain move elsewhere needs investigation rather than a guessed fix.

## Silent resolution after judgment

Resolve `fixed` or `fixed-differently` only after the repair is validated and pushed. Resolve `not-addressing` and `declined` after recording the supporting evidence, unless the user asked to keep those threads open. Leave questions and human decisions unresolved. Top-level comments and review bodies have no thread-resolution operation.

Fetch fresh published thread contents before resolving. Compare them with the exact version evaluated, not just the thread ID. New or edited feedback stays open for evaluation. Use `data.threadId` from the fresh snapshot and check `data.resolved` before writing:

```bash
GH_HOST=<host> gh api graphql -f threadId=<thread-id> -f query='mutation($threadId: ID!) { resolveReviewThread(input: {threadId: $threadId}) { thread { id isResolved } } }'
```

This is the only review mutation in this workflow. It creates no reply. Do not post an explanation, approval, review submission, or PR body edit. A permission error leaves the thread open and stops with the failed action identified. Successful resolution must be confirmed by a new snapshot; record it locally. The observed resolved thread needs no acknowledgment. If resolution occurred entirely between polls, keep the report as evidence and reevaluate any new follow-up rather than trusting the earlier verdict.
