#!/usr/bin/env bash
# Read one PR and remember evaluated feedback and spent repair attempts.
# GitHub writes belong to the agent, never to this helper.
set -euo pipefail
umask 077

GH="${WARD_GH:-gh}"
ROOT="${WARD_STATE_ROOT:-/tmp/ward-$(id -u)}"
DIR="" TMP="" LOCKED=0
HOST="" OWNER="" REPO="" PR="" URL="" HEAD_SHA="" PR_STATE="" PR_JSON=""

usage() {
  cat <<'EOF'
usage: pr-watch.sh snapshot [PR-number|PR-URL|auto]
       pr-watch.sh ack PR-URL KEY@VERSION [KEY@VERSION ...]
       pr-watch.sh reserve retry PR-URL SHA
       pr-watch.sh reserve fix PR-URL SHA ISSUE-KEY

snapshot reads GitHub and returns pr, checks, feedback, and saved file paths.
ack marks only the exact observed feedback version as evaluated.
reserve records one flaky rerun per head or two repairs per recurring issue.
No command edits code, posts comments, resolves threads, or reruns checks.

State defaults to /tmp/ward-<uid>/. WARD_STATE_ROOT and WARD_GH allow isolated
fixtures. Commands after the initial snapshot use its canonical PR URL.
EOF
}

die() { printf 'pr-watch.sh: %s\n' "$*" >&2; exit 1; }

gh_call() {
  if [ -n "$HOST" ]; then GH_HOST="$HOST" "$GH" "$@"; else "$GH" "$@"; fi
}

json_quote() {
  local value="$1"
  value=${value//\\/\\\\}; value=${value//\"/\\\"}
  value=${value//$'\n'/\\n}; value=${value//$'\r'/\\r}; value=${value//$'\t'/\\t}
  value=${value//$'\b'/\\b}; value=${value//$'\f'/\\f}
  printf '"%s"' "$value"
}

private_dir() {
  [ ! -L "$1" ] || die "state directory is a symlink: $1"
  mkdir -p "$1"
  [ -d "$1" ] && [ -O "$1" ] || die "state directory is not owned by this user: $1"
  chmod 700 "$1"
}

cleanup() {
  if [ -n "$TMP" ]; then rm -rf -- "$TMP"; fi
  if [ "$LOCKED" = 1 ]; then rm -f "$DIR/operation.lock/pid"; rmdir "$DIR/operation.lock"; fi
}
trap cleanup EXIT
trap 'exit 129' HUP
trap 'exit 130' INT
trap 'exit 143' TERM

locate() {
  # gh resolves numbers and branches. Only canonical URLs reach local state.
  local pattern='^https?://([A-Za-z0-9.:-]+)/([A-Za-z0-9_-]+)/([A-Za-z0-9_.-]+)/pull/([0-9]+)$'
  [[ "$1" =~ $pattern ]] || die "expected a canonical PR URL: $1"
  HOST="${BASH_REMATCH[1]}" OWNER="${BASH_REMATCH[2]}"
  REPO="${BASH_REMATCH[3]}" PR="${BASH_REMATCH[4]}"
  [ "$HOST" != . ] && [ "$HOST" != .. ] && [ "$REPO" != . ] && [ "$REPO" != .. ] || die "invalid PR URL"
  HOST=$(printf '%s' "$HOST" | tr '[:upper:]' '[:lower:]')
  OWNER=$(printf '%s' "$OWNER" | tr '[:upper:]' '[:lower:]')
  REPO=$(printf '%s' "$REPO" | tr '[:upper:]' '[:lower:]')
  PR=$(printf '%s' "$PR" | sed 's/^0*//')
  [ -n "$PR" ] || die "PR number must be positive"
  URL="https://$HOST/$OWNER/$REPO/pull/$PR"
}

metadata() {
  local target="$1" result row
  local fields='url,state,headRefOid,headRefName,headRepository,headRepositoryOwner,baseRefName,mergeable,mergeStateStatus,reviewDecision,isDraft'
  local filter='tojson, ([.url, (if .headRefOid == null or .headRefOid == "" then "-" else .headRefOid end), .state] | @tsv)'
  if [ "$target" = auto ]; then
    result=$(gh_call pr view --json "$fields" --jq "$filter") || die "cannot read the current branch PR"
  else
    result=$(gh_call pr view "$target" --json "$fields" --jq "$filter") || die "cannot read PR: $target"
  fi
  PR_JSON=$(printf '%s\n' "$result" | sed -n '1p')
  row=$(printf '%s\n' "$result" | sed -n '2p')
  IFS=$'\t' read -r URL HEAD_SHA PR_STATE <<< "$row"
  case "$PR_STATE" in OPEN|CLOSED|MERGED) ;; *) die "unknown PR state" ;; esac
  [[ "$HEAD_SHA" =~ ^[A-Za-z0-9_-]+$ ]] || die "invalid head SHA"
  [ "$PR_STATE" != OPEN ] || [ "$HEAD_SHA" != - ] || die "open PR has no head SHA"
  locate "$URL"
}

open_state() {
  private_dir "$ROOT"
  private_dir "$ROOT/$HOST"
  private_dir "$ROOT/$HOST/${OWNER}_${REPO}"
  DIR="$ROOT/$HOST/${OWNER}_${REPO}/pr-$PR"
  private_dir "$DIR"
  mkdir "$DIR/operation.lock" 2>/dev/null || die "another operation owns $DIR/operation.lock; verify the owner before recovering a stale lock"
  LOCKED=1
  printf '%s\n' "$$" > "$DIR/operation.lock/pid"
  TMP=$(mktemp -d "$DIR/.work.XXXXXX")
  if [ ! -e "$DIR/state.tsv" ]; then
    [ ! -e "$DIR/meta" ] || die "prior draft state exists in $DIR; preserve its budgets before migrating"
    printf 'ward-v2\t%s\nhead\t-\n' "$URL" > "$TMP/state.tsv"
    mv "$TMP/state.tsv" "$DIR/state.tsv"
  fi
  [ -f "$DIR/state.tsv" ] && [ ! -L "$DIR/state.tsv" ] && [ -O "$DIR/state.tsv" ] || die "unsafe state ledger"
  chmod 600 "$DIR/state.tsv"
  awk -F '\t' -v url="$URL" '
    NR==1 { if (NF!=2 || $1!="ward-v2" || $2!=url) bad=1; next }
    NR==2 { if (NF!=2 || $1!="head" || $2!~/^[A-Za-z0-9_-]+$/) bad=1; next }
    $1=="item" && NF==5 && $2~/^[A-Za-z0-9_:=\/-]+$/ && $3~/^[a-f0-9]+$/ && $4~/^[a-f0-9]+$/ && $5~/^[01]$/ { if (items[$2]++) bad=1; next }
    $1=="retry" && NF==2 && $2~/^[A-Za-z0-9_-]+$/ { if (retries[$2]++) bad=1; next }
    $1=="fix" && NF==2 && $2~/^[A-Za-z0-9_.:@=\/-]+$/ { if (++fixes[$2]>2) bad=1; next }
    { bad=1 }
    END { exit (bad || NR<2) }
  ' "$DIR/state.tsv" || die "malformed state ledger: $DIR/state.tsv"
}

THREAD_QUERY='query($owner: String!, $repo: String!, $pr: Int!, $endCursor: String) {
  repository(owner: $owner, name: $repo) {
    pullRequest(number: $pr) {
      reviewThreads(first: 100, after: $endCursor) {
        pageInfo { hasNextPage endCursor }
        nodes {
          id isResolved isOutdated path line originalLine startLine originalStartLine
          comments(first: 100) {
            pageInfo { hasNextPage endCursor }
            nodes {
              id databaseId url body createdAt updatedAt
              author { login }
              pullRequestReview { state }
            }
          }
        }
      }
    }
  }
}'

THREAD_JQ='if ((.errors // []) | length) > 0 then error("graphql errors") else
  .data.repository.pullRequest.reviewThreads as $threads |
  if $threads == null then error("missing review threads") else
    ("__WARD_CURSOR__" + (if $threads.pageInfo.hasNextPage then $threads.pageInfo.endCursor else "" end)),
    ($threads.nodes[] |
      [.comments.nodes[] | select(.pullRequestReview.state != "PENDING") |
        {id, databaseId, url, body, createdAt, updatedAt, author:(.author.login // ""), reviewState:(.pullRequestReview.state // "")}] as $comments |
      ("__WARD_NESTED__" + .id + "\t" + (if .comments.pageInfo.hasNextPage then .comments.pageInfo.endCursor else "" end)),
      ("thread:" + .id + "\t" +
        ({kind:"inline", id, threadId:.id, resolved:.isResolved, outdated:.isOutdated,
          path, line, originalLine, startLine, originalStartLine} | tojson | rtrimstr("}")) +
        ",\"comments\":" + ($comments | tojson) + "}")
    )
  end
end'

NESTED_THREAD_QUERY='query($threadId: ID!, $endCursor: String) {
  node(id: $threadId) {
    ... on PullRequestReviewThread {
      comments(first: 100, after: $endCursor) {
        pageInfo { hasNextPage endCursor }
        nodes {
          id databaseId url body createdAt updatedAt
          author { login }
          pullRequestReview { state }
        }
      }
    }
  }
}'

NESTED_THREAD_JQ='if ((.errors // []) | length) > 0 then error("graphql errors") else
  ((.data.node.comments // error("missing thread comments")) as $c |
   (if $c.pageInfo.hasNextPage then "__WARD_CURSOR__" + ($c.pageInfo.endCursor // "") else "__WARD_CURSOR__" end),
   (($c.nodes // [])[] | select((.pullRequestReview.state // "") != "PENDING") |
     {id:(.id | tostring), databaseId:(.databaseId // null), url:(.url // ""), body:(.body // ""), createdAt:(.createdAt // ""), updatedAt:(.updatedAt // ""), author:((.author.login // "")), reviewState:((.pullRequestReview.state // ""))} | tojson))
end'

json_lines_join() {
  local file="$1"
  awk 'BEGIN { printf ""; first=1 } {
    if ($0 == "") next
    if (!first) printf ","; printf "%s", $0; first=0
  } END { print "" }' "$file"
}

append_nested_comments() {
  local object="$1" additions="$2" prefix separator
  [ -n "$additions" ] || { printf '%s' "$object"; return 0; }
  prefix="${object%?}"
  prefix="${prefix%?}"
  case "$object" in
    *'"comments":[]}'*) separator="" ;;
    *) separator="," ;;
  esac
  printf '%s%s%s]}' "$prefix" "$separator" "$additions"
}

fetch_nested_comments() {
  local thread_id="$1" cursor="$2" cursor_line rc
  local records="$TMP/nested-$RANDOM.records"
  : > "$records" || return 1
  while :; do
    if [ -n "$cursor" ]; then
      gh_call api graphql -f threadId="$thread_id" -f endCursor="$cursor" -f query="$NESTED_THREAD_QUERY" --jq "$NESTED_THREAD_JQ" > "$TMP/nested.page"
    else
      gh_call api graphql -f threadId="$thread_id" -f query="$NESTED_THREAD_QUERY" --jq "$NESTED_THREAD_JQ" > "$TMP/nested.page"
    fi
    rc=$?
    [ "$rc" -eq 0 ] || return 1
    cursor_line=$(sed -n '1p' "$TMP/nested.page")
    case "$cursor_line" in
      __WARD_CURSOR__*) cursor="${cursor_line#__WARD_CURSOR__}" ;;
      *) return 1 ;;
    esac
    sed -n '2,$p' "$TMP/nested.page" >> "$records" || return 1
    [ -n "$cursor" ] || break
  done
  json_lines_join "$records"
}

fetch_threads() {
  : > "$TMP/threads.records"
  local cursor="" cursor_line rc line nested_info nested_thread nested_cursor key object additions
  while :; do
    if [ -n "$cursor" ]; then
      gh_call api graphql -f owner="$OWNER" -f repo="$REPO" -F pr="$PR" -f endCursor="$cursor" -f query="$THREAD_QUERY" --jq "$THREAD_JQ" > "$TMP/thread.page"
    else
      gh_call api graphql -f owner="$OWNER" -f repo="$REPO" -F pr="$PR" -f query="$THREAD_QUERY" --jq "$THREAD_JQ" > "$TMP/thread.page"
    fi
    rc=$?
    [ "$rc" -eq 0 ] || die "GitHub review thread fetch failed (exit $rc)" 1
    cursor_line=$(sed -n '1p' "$TMP/thread.page")
    case "$cursor_line" in __WARD_CURSOR__*) ;; *) die "missing review thread cursor" ;; esac
    nested_thread=""
    nested_cursor=""
    while IFS= read -r line; do
      case "$line" in
        __WARD_CURSOR__*) cursor="${line#__WARD_CURSOR__}" ;;
        __WARD_NESTED__*)
          nested_info="${line#__WARD_NESTED__}"
          nested_thread="${nested_info%%$'\t'*}"
          nested_cursor="${nested_info#*$'\t'}"
          ;;
        thread:$'\t'*|thread:*)
          key="${line%%$'\t'*}"
          object="${line#*$'\t'}"
          [ "$key" = "thread:$nested_thread" ] || die "GitHub review thread response was malformed" 1
          if [ -n "$nested_cursor" ]; then
            additions=$(fetch_nested_comments "$nested_thread" "$nested_cursor") \
              || die "GitHub nested review comment fetch failed" 1
            object=$(append_nested_comments "$object" "$additions")
          fi
          case "$object" in
            *'"comments":[]}'*) ;;
            *)
              printf '%s\t%s\n' "$key" "$object" >> "$TMP/threads.records" \
                || die "cannot write review thread scratch" 74
              ;;
          esac
          nested_thread=""
          nested_cursor=""
          ;;
        '') ;;
        *) die "GitHub review thread response was malformed" 1 ;;
      esac
    done < "$TMP/thread.page"
    [ -n "$nested_thread" ] && die "GitHub review thread response was incomplete" 1
    [ -n "$cursor" ] || break
  done
}

fetch_comments() {
  gh_call api --paginate "repos/$OWNER/$REPO/issues/$PR/comments" --jq '.[] | select((.body // "") | test("\\S")) | ("comment:" + ((.id // .node_id) | tostring) + "\t" + ({kind:"comment", id:((.id // .node_id) | tostring), url:(.html_url // .url // ""), body:(.body // ""), createdAt:(.created_at // ""), updatedAt:(.updated_at // ""), author:((.user.login // "")), resolved:false} | tojson))' > "$TMP/comments.records"
  local rc=$?
  [ "$rc" -eq 0 ] || die "GitHub top-level comment fetch failed (exit $rc)" 1
}

fetch_reviews() {
  gh_call api --paginate "repos/$OWNER/$REPO/pulls/$PR/reviews" --jq '.[] | select((.state // "") != "PENDING") | select((.body // "") | test("\\S")) | ("review:" + ((.id // .node_id) | tostring) + "\t" + ({kind:"review", id:((.id // .node_id) | tostring), url:(.html_url // .url // ""), body:(.body // ""), state:(.state // ""), submittedAt:(.submitted_at // ""), updatedAt:(.submitted_at // ""), author:((.user.login // "")), resolved:false} | tojson))' > "$TMP/reviews.records"
  local rc=$?
  [ "$rc" -eq 0 ] || die "GitHub review body fetch failed (exit $rc)" 1
}


fetch_checks() {
  local rc=0
  gh_call pr checks "$URL" --json name,state,bucket,link --jq . > "$TMP/checks.json" || rc=$?
  case "$rc" in 0|1|8) ;; *) die "check fetch failed (exit $rc)" ;; esac
  # Failure=1 and pending=8 are data only when gh actually returned JSON.
  local data
  data=$(cat "$TMP/checks.json")
  [[ "$data" == \[*\] ]] || die "check fetch returned no JSON array (exit $rc)"
}

observe_feedback() {
  cat "$TMP/threads.records" "$TMP/comments.records" "$TMP/reviews.records" > "$TMP/items"
  awk -F '\t' 'NF!=2 || $1!~/^[A-Za-z0-9_:=\/-]+$/ {bad=1} {if(seen[$1]++) bad=1} END{exit bad}' "$TMP/items" || die "duplicate or malformed feedback"
  # Preserve budgets and absent historical items. Only observations change.
  awk -F '\t' -v sha="$HEAD_SHA" 'BEGIN{OFS="\t"} $1=="head" {$2=sha} {print}' "$DIR/state.tsv" > "$TMP/state.tsv"
  : > "$TMP/feedback.jsonl"
  local key data digest prior old_digest version acknowledged row
  while IFS=$'\t' read -r key data; do
    digest=$(printf '%s' "$data" | git hash-object --stdin)
    prior=$(awk -F '\t' -v key="$key" '$1=="item" && $2==key {print}' "$DIR/state.tsv")
    version="$digest" acknowledged=0
    if [ -n "$prior" ]; then
      IFS=$'\t' read -r row row old_digest version acknowledged <<< "$prior"
      if [ "$digest" != "$old_digest" ]; then
        # A resolved-then-reopened item gets a new version even if its body returns unchanged.
        version=$(printf '%s\n%s' "$version" "$data" | git hash-object --stdin)
        acknowledged=0
      fi
    fi
    awk -F '\t' -v key="$key" '!($1=="item" && $2==key)' "$TMP/state.tsv" > "$TMP/next.tsv"
    printf 'item\t%s\t%s\t%s\t%s\n' "$key" "$digest" "$version" "$acknowledged" >> "$TMP/next.tsv"
    mv "$TMP/next.tsv" "$TMP/state.tsv"
    local boolean=false
    [ "$acknowledged" = 0 ] || boolean=true
    printf '{"key":"%s","version":"%s","acknowledged":%s,"data":%s}\n' "$key" "$version" "$boolean" "$data" >> "$TMP/feedback.jsonl"
  done < "$TMP/items"
}

snapshot() {
  metadata "$1"
  open_state
  local initial_head="$HEAD_SHA"
  if [ "$PR_STATE" = OPEN ]; then
    fetch_threads
    fetch_comments
    fetch_reviews
    fetch_checks
    metadata "$URL"
    [ "$initial_head" = "$HEAD_SHA" ] || die "head changed during fetch; take a fresh snapshot"
  else
    : > "$TMP/threads.records"
    : > "$TMP/comments.records"
    : > "$TMP/reviews.records"
    printf '[]\n' > "$TMP/checks.json"
  fi
  observe_feedback
  private_dir "$DIR/snapshots"
  local path
  path=$(mktemp "$DIR/snapshots/snapshot.XXXXXX")
  {
    printf '{"pr":%s,"checks":%s,"feedback":[' "$PR_JSON" "$(cat "$TMP/checks.json")"
    json_lines_join "$TMP/feedback.jsonl"
    printf '],"state_path":%s,"snapshot_path":%s}\n' "$(json_quote "$DIR")" "$(json_quote "$path")"
  } > "$TMP/snapshot.json"
  mv "$TMP/snapshot.json" "$path"
  # State has a single commit point. An interrupted snapshot is just an unused artifact.
  mv "$TMP/state.tsv" "$DIR/state.tsv"
  cat "$path"
}

acknowledge() {
  locate "$1"; shift
  [ "$#" -gt 0 ] || die "ack needs KEY@VERSION"
  open_state
  cp "$DIR/state.tsv" "$TMP/state.tsv"
  local token key version current
  for token in "$@"; do
    [[ "$token" =~ ^[A-Za-z0-9_:=/-]+@[a-f0-9]+$ ]] || die "invalid feedback version"
    key="${token%@*}" version="${token##*@}"
    current=$(awk -F '\t' -v key="$key" '$1=="item" && $2==key {print $4}' "$TMP/state.tsv")
    [ "$current" = "$version" ] || die "feedback version is stale or unknown: $key"
    awk -F '\t' -v key="$key" 'BEGIN{OFS="\t"} $1=="item" && $2==key {$5=1} {print}' "$TMP/state.tsv" > "$TMP/next.tsv"
    mv "$TMP/next.tsv" "$TMP/state.tsv"
  done
  mv "$TMP/state.tsv" "$DIR/state.tsv"
  printf '{"acknowledged":%s}\n' "$#"
}

reserve() {
  local kind="$1" sha="$3" key="$3" limit=1 count current
  locate "$2"
  [[ "$sha" =~ ^[A-Za-z0-9_-]+$ ]] && [ "$sha" != - ] || die "invalid head SHA"
  case "$kind" in
    retry) [ "$#" = 3 ] || die "retry needs PR-URL SHA" ;;
    fix) [ "$#" = 4 ] || die "fix needs PR-URL SHA ISSUE-KEY"; key="$4"; limit=2 ;;
    *) die "unknown reservation: $kind" ;;
  esac
  [[ "$key" =~ ^[A-Za-z0-9_.:@=/-]+$ ]] || die "invalid issue key"
  open_state
  current=$(awk -F '\t' '$1=="head" {print $2}' "$DIR/state.tsv")
  [ "$current" = "$sha" ] || die "head differs from saved snapshot; refresh before reserving"
  count=$(awk -F '\t' -v kind="$kind" -v key="$key" '$1==kind && $2==key {n++} END{print n+0}' "$DIR/state.tsv")
  [ "$count" -lt "$limit" ] || die "$kind budget exhausted for $key"
  cp "$DIR/state.tsv" "$TMP/state.tsv"
  printf '%s\t%s\n' "$kind" "$key" >> "$TMP/state.tsv"
  mv "$TMP/state.tsv" "$DIR/state.tsv"
  printf '{"reserved":true,"attempt":%s,"limit":%s}\n' "$((count+1))" "$limit"
}

case "${1:---help}" in
  --help|-h) usage ;;
  snapshot) [ "$#" -le 2 ] || die "snapshot accepts one target"; snapshot "${2:-auto}" ;;
  ack) [ "$#" -ge 3 ] || die "ack needs PR-URL KEY@VERSION"; shift; acknowledge "$@" ;;
  reserve) [ "$#" -ge 4 ] || die "reserve needs retry|fix PR-URL SHA [ISSUE-KEY]"; shift; reserve "$@" ;;
  *) usage >&2; exit 1 ;;
esac
