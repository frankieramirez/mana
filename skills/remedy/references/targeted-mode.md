# Targeted feedback workflow

Load only for Targeted mode. Paths beginning with `references/` are relative to the skill directory.

## Targeted mode

Only the one thread named by the URL.

### 1. Extract thread context

Parse `https://HOST/OWNER/REPO/pull/NUMBER#discussion_rCOMMENT_ID`. When `HOST` is not `github.com`, pass `GH_HOST=<host>` inline on every call below.

```bash
GH_HOST=<host> gh api repos/OWNER/REPO/pulls/comments/COMMENT_ID --jq '{node_id, path, line, body}'
```

Map the comment to its thread. The helper pages thread and comment IDs to locate the match; it does not retrieve unrelated comment bodies or PR conversation surfaces:

```bash
GH_HOST=<host> bash "<SKILL_DIR>/scripts/pr-threads" thread PR_NUMBER COMMENT_NODE_ID OWNER/REPO
```

Skip any draft-review check. Nothing gets posted, so a pending review has nothing to swallow.

Read `references/run-artifacts.md` and create the run directory. Record HEAD as `head_before`. Save both responses above to `$RUN_DIR/fetch.json` before judging, the comment lookup under `comment` and the thread lookup under `review_threads`. The same artifacts (`items.json`, `summary.md`, `metadata.json`) are written for this one item, with `mode` set to `targeted`.

### 2. Judge, fix, push, resolve

Apply `references/evaluation-rubric.md` to this one thread. Account for `isOutdated` and the location fields. The cross-item reasoning is a no-op for a single thread, but read-depth and the diverts apply in full: deep-read callers, invariants, and `git blame` or PR rationale before accepting a contestable finding or overriding code that looks deliberate.

Record this item's identity, location, read depth, verdict, evidence, and change note or explanation in `$RUN_DIR/items.json`. The fix-list contains `fixed` / `fixed-differently`; other verdicts form the skip-list. No scouts run for a single thread; read the code yourself.

Load `references/publication.md` for the remaining steps. Under `dry-run`, write the step 9 summary and metadata and stop before edits or resolves. Otherwise enter step 4 for a fix, or step 7 for a skip-list verdict. Its dispatch rules and no-subagent fallback apply to this one item. With one item, apply the verifier's full checks inline. Skip validation and commit when no code changed. Step 8 verifies only this thread.
