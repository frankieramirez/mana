#!/usr/bin/env bash
# tickets.sh: build-ticket operations shared by setup-mana, sift, conjure, cast, and scan.
#
#   check                                     who the token is, and that it can read the project
#   ensure-labels [--color HEX] LABEL...      create each missing label
#   list LABEL | list --unlabeled             open issues: id<TAB>title<TAB>url<TAB>updated
#   view ID                                   fields, body, and comments
#   create TITLE --label L... [--dry-run]     body on stdin; prints id<TAB>url
#   attach CHILD PARENT                      add a build ticket to a build parent
#   children PARENT                          all build tickets: id<TAB>state<TAB>title<TAB>url
#   find TEXT                                all-state literal body search, same columns as children
#   body ID                                  print the raw issue body
#   update-body ID [--expected-body PATH]    replace body on stdin, optionally guarded by a snapshot
#   wire CHILD BLOCKER                        CHILD is blocked by BLOCKER
#   next READY_LABEL [--claim]                oldest open, unassigned, unblocked issue;
#                                             --claim assigns it only while it stays eligible
#   claim ID                                  assign yourself; refuse if someone else holds it
#   label ID [--add L]... [--remove L]...     change labels
#   comment ID                                body on stdin
#   close ID                                  close, or move to the done state
#
# Global options, before or after the subcommand:
#   --tracker github|linear|jira   default github
#   --project KEY                  Linear team key or Jira project key (or LINEAR_TEAM / JIRA_PROJECT)
#   --repo OWNER/REPO              GitHub only; default gh repo view in this checkout
#
# GitHub needs git and gh, honors GH_HOST, and exits 3 when the token cannot write (403).
# Linear needs python3 and LINEAR_API_KEY. Jira needs python3, JIRA_BASE_URL, JIRA_EMAIL,
# JIRA_API_TOKEN, and optionally JIRA_ISSUE_TYPE (default Task). Both exit 3 on 401 or 403.
# Label strings are arguments. The calling skill resolves them from docs/agents/triage-labels.md;
# this script never reads that file. IDs are whatever the tracker uses: 42, ENG-42, PROJ-42.
# A GitHub, Linear, or Jira issue URL is reduced to that id before view, claim, wire, label, comment, close.

set -euo pipefail

ERR=""
trap '[ -n "${ERR:-}" ] && rm -f "$ERR"' EXIT

usage() {
  cat <<'EOF'
usage: tickets.sh [--tracker github|linear|jira] [--project KEY] [--repo OWNER/REPO] <subcommand> [args]

  check                                  tracker, user, project; exit 3 when the token is refused
  ensure-labels [--color HEX] LABEL...   create each label that does not exist (no-op on Jira)
  list LABEL | list --unlabeled          open issues: id<TAB>title<TAB>url<TAB>updated, oldest first
  view ID                                id, title, url, state, labels, assignees, body, comments
  create TITLE --label L... [--dry-run]  body on stdin; prints id<TAB>url
  attach CHILD PARENT                    add a build ticket to a build parent
  children PARENT                        all build tickets: id<TAB>state<TAB>title<TAB>url
  find TEXT                              all-state literal body search: id/state/title/url TSV
  body ID                                print the raw issue body
  update-body ID [--expected-body PATH]  replace body on stdin, optionally guarded by a snapshot
  wire CHILD BLOCKER                     CHILD is blocked by BLOCKER
  next READY_LABEL [--claim]             id<TAB>title<TAB>url of the oldest open, unassigned,
                                         unblocked issue; empty when none. --claim assigns
                                         it, re-reads, and releases if it is no longer eligible
  claim ID                               assign yourself; exit 1 if someone else holds it
  label ID [--add L]... [--remove L]...  change labels
  comment ID                             body on stdin
  close ID                               close the issue

Exit 3 means this token cannot write; write the same shape locally instead.
EOF
}

die() {
  echo "tickets.sh: $*" >&2
  exit 1
}

# GitHub .../issues/N or .../pull/N, Linear .../issue/KEY-N, Jira .../browse/KEY-N or .../issues/KEY-N.
normalize_id() {
  local id="$1"
  case "$id" in
    *://*)
      id="${id%%\?*}"
      id="${id%%\#*}"
      id="${id%/}"
      case "$id" in
        */issues/*|*/pull/*)
          id="${id##*/}"
          ;;
        */browse/*)
          id="${id##*/browse/}"
          id="${id%%/*}"
          ;;
        */issue/*)
          id="${id##*/issue/}"
          id="${id%%/*}"
          ;;
      esac
      ;;
  esac
  printf '%s\n' "$id"
}

# ---------------------------------------------------------------- GitHub (git + gh only)

# Runs gh. Prints stderr on failure. Returns 0, 1, or 3 (403-class). Does not exit.
try_gh() {
  local ec
  ERR=$(mktemp)
  set +e
  "$@" 2>"$ERR"
  ec=$?
  set -e
  if [ "$ec" -eq 0 ]; then
    rm -f "$ERR"
    ERR=""
    return 0
  fi
  cat "$ERR" >&2
  if grep -qiE '403|Resource not accessible|HTTP 403' "$ERR"; then
    rm -f "$ERR"
    ERR=""
    return 3
  fi
  rm -f "$ERR"
  ERR=""
  return "$ec"
}

# Runs gh. On 403-class write denial, exit 3.
run_gh() {
  try_gh "$@" || exit $?
}

locate_repo() {
  local spec="${1:-}"
  if [ -z "$spec" ]; then
    spec=$(gh repo view --json nameWithOwner --jq .nameWithOwner 2>/dev/null || true)
  fi
  case "$spec" in
    */*) OWNER="${spec%%/*}"; REPO="${spec#*/}" ;;
    *) die "cannot tell which repository to use; run inside a checkout or pass --repo owner/repo" ;;
  esac
  [ -n "$OWNER" ] && [ -n "$REPO" ] || die "malformed owner/repo: '$spec'"
}

db_id() {
  local n="$1"
  gh api "repos/${OWNER}/${REPO}/issues/${n}" --jq .id
}

# POST an API write. Return 1 on any failure, including 403, so the caller can fall back.
api_write() {
  local err ec
  err=$(mktemp)
  set +e
  gh api "$@" >/dev/null 2>"$err"
  ec=$?
  set -e
  rm -f "$err"
  [ "$ec" -eq 0 ]
}

# True (exit 0) when the issue has an open blocker via API or a Blocked by: line.
gh_is_blocked() {
  local n="$1"
  local raw body ids id st
  if raw=$(gh api "repos/${OWNER}/${REPO}/issues/${n}/dependencies/blocked_by" --jq '
    (if type == "array" then . else (.blocked_by // []) end)
    | [.[] | select(.state == "open" or .state == "OPEN")]
    | length
  ' 2>/dev/null); then
    [ "${raw:-0}" -gt 0 ]
    return
  fi
  body=$(gh_body "$n")
  ids=$(printf '%s\n' "$body" | sed -n '1,8p' | grep -E '^Blocked by:' | sed 's/[^0-9, ]//g' | tr ',' ' ')
  for id in $ids; do
    [ -n "$id" ] || continue
    st=$(gh issue view --repo "$OWNER/$REPO" "$id" --json state --jq .state 2>/dev/null || true)
    if [ "$st" = "OPEN" ] || [ "$st" = "open" ]; then
      return 0
    fi
  done
  return 1
}

gh_check() {
  local login
  login=$(gh api user --jq .login) || exit 3
  gh api "repos/${OWNER}/${REPO}" --jq .full_name >/dev/null || exit 3
  printf 'tracker\tgithub\nuser\t%s\nproject\t%s/%s\n' "$login" "$OWNER" "$REPO"
}

gh_ensure_labels() {
  local color="$1"; shift
  local name existing
  [ $# -ge 1 ] || die "ensure-labels needs at least one label"
  existing=$(gh label list --repo "$OWNER/$REPO" --limit 200 --json name --jq '.[].name')
  for name in "$@"; do
    if printf '%s\n' "$existing" | grep -qxF "$name"; then
      continue
    fi
    run_gh gh label create --repo "$OWNER/$REPO" "$name" --color "$color" >/dev/null
  done
}

gh_list() {
  local label="$1"
  local filter='.[]'
  local -a args=(--repo "$OWNER/$REPO" --state open --limit 100 --json number,title,url,updatedAt,labels)
  if [ "$label" = "--unlabeled" ]; then
    filter='.[] | select((.labels | length) == 0)'
  else
    args+=(--label "$label")
  fi
  gh issue list "${args[@]}" --jq "sort_by(.updatedAt) | $filter | [.number, .title, .url, .updatedAt] | @tsv"
}

gh_view() {
  local n="$1"
  gh issue view --repo "$OWNER/$REPO" "$n" --json number,title,url,state,body,labels,assignees,comments --jq '
    [
      "id\t\(.number)",
      "title\t\(.title)",
      "url\t\(.url)",
      "state\t\(.state)",
      "labels\t\([.labels[].name] | join(","))",
      "assignees\t\([.assignees[].login] | join(","))",
      "body",
      .body,
      "comments",
      ([.comments[] | "--- \(.author.login) \(.createdAt)\n\(.body)"] | join("\n"))
    ] | join("\n")
  '
}

# A build parent is deliberately identified by one exact body line. Labels are
# workflow state and can be copied accidentally, while this marker survives
# label edits and keeps map children out of the build queue.
gh_is_build_body() {
  local body="$1"
  printf '%s\n' "$body" | grep -qxF 'Work kind: build'
}

# Bodies edited in the GitHub web UI come back with CRLF line endings, and
# every marker below is an exact line match, so strip the carriage returns
# once here. Every body read in this file goes through this function.
gh_body() {
  local n="$1"
  gh issue view --repo "$OWNER/$REPO" "$n" --json body --jq .body | tr -d '\r'
}

gh_update_body() {
  local n="$1" expected="${2:-}"
  local tmp current
  tmp=$(mktemp)
  cat > "$tmp"
  if [ -n "$expected" ]; then
    [ -f "$expected" ] || { rm -f "$tmp"; die "expected body snapshot is missing: $expected"; }
    current=$(mktemp)
    if ! gh_body "$n" > "$current"; then
      rm -f "$tmp" "$current"
      die "cannot read current body; refusing update"
    fi
    if ! cmp -s "$expected" "$current"; then
      rm -f "$tmp" "$current"
      die "current body differs from expected snapshot; refusing update"
    fi
    rm -f "$current"
  fi
  run_gh gh issue edit --repo "$OWNER/$REPO" "$n" --body-file "$tmp"
  rm -f "$tmp"
}

gh_parent_ref() {
  local n="$1" err raw
  err=$(mktemp)
  if raw=$(gh api "repos/${OWNER}/${REPO}/issues/${n}/parent" --jq '[.number,.html_url] | @tsv' 2>"$err"); then
    rm -f "$err"
    [ -n "$raw" ] || die "empty native parent response"
    printf '%s\n' "$raw"
    return
  fi
  if grep -qiE 'HTTP (404|410)|404 Not Found|410 Gone' "$err"; then
    rm -f "$err"
    gh_body "$n" >/dev/null || die "cannot verify ticket $n"
    return 0
  fi
  cat "$err" >&2
  rm -f "$err"
  die "cannot read native parent for $n"
}

gh_parent_details() {
  local n="$1"
  gh issue view --repo "$OWNER/$REPO" "$n" --json number,title,url,state --jq '[.number,.title,.url,.state] | @tsv'
}

# Return a distinct status for the one GitHub failure that means the native
# sub-issue endpoint is unavailable on older Enterprise installations. The
# caller may then use an explicit body membership link after re-reading the
# parent. Other failures remain failures and never silently become a fallback.
gh_attach_native() {
  local child="$1" parent="$2"
  local err ec child_id
  child_id=$(db_id "$child") || die "cannot read child database ID"
  [[ "$child_id" =~ ^[0-9]+$ ]] || die "invalid child database ID"
  err=$(mktemp)
  set +e
  gh api --method POST "repos/${OWNER}/${REPO}/issues/${parent}/sub_issues" -F "sub_issue_id=$child_id" >/dev/null 2>"$err"
  ec=$?
  set -e
  if [ "$ec" -eq 0 ]; then
    rm -f "$err"
    return 0
  fi
  cat "$err" >&2
  if grep -qiE 'HTTP (404|410)|404 Not Found|410 Gone' "$err"; then
    rm -f "$err"
    return 44
  fi
  if grep -qiE '403|Resource not accessible|HTTP 403' "$err"; then
    rm -f "$err"
    return 3
  fi
  rm -f "$err"
  return "$ec"
}

# Print the URL from the first "Build parent: [title](url)" line in a body,
# or nothing when the body has no such line. The Python adapter has the same
# rule in build_links().
gh_build_parent_url() {
  local body="$1" line
  while IFS= read -r line; do
    case "$line" in
      'Build parent: ['*)
        line="${line##*](}"
        printf '%s\n' "${line%)}"
        return 0
        ;;
    esac
  done <<< "$body"
}

# Die when a body already names a different build parent. Prints "linked" when
# it names this one and nothing when it names none.
gh_check_build_link() {
  local child="$1" body="$2" parent_url="$3" existing_url
  existing_url=$(gh_build_parent_url "$body")
  [ -n "$existing_url" ] || return 0
  [ "$existing_url" = "$parent_url" ] || die "ticket $child already names another build parent"
  printf 'linked\n'
}

gh_explicit_build_link() {
  local child="$1" parent="$2" parent_title="$3" parent_url="$4"
  local body target tmp
  body=$(gh_body "$child") || die "cannot read build ticket $child"
  target="Build parent: ["$parent_title"]("$parent_url")"
  local linked
  linked=$(gh_check_build_link "$child" "$body" "$parent_url") || exit $?
  [ -z "$linked" ] || return 0
  tmp=$(mktemp)
  if [ -n "$body" ]; then
    printf '%s\n\n%s\n' "$target" "$body" > "$tmp"
  else
    printf '%s\n' "$target" > "$tmp"
  fi
  run_gh gh issue edit --repo "$OWNER/$REPO" "$child" --body-file "$tmp"
  rm -f "$tmp"
}

gh_validate_build_link() {
  local child="$1" parent_url="$2" body
  body=$(gh_body "$child") || die "cannot read build ticket $child"
  gh_check_build_link "$child" "$body" "$parent_url" >/dev/null
}

gh_attach() {
  local child="$1" parent="$2"
  [ "$child" != "$parent" ] || die "a build cannot contain itself"
  local parent_row parent_title parent_url parent_body child_parent child_parent_url child_parent_ref
  parent_row=$(gh_parent_details "$parent") || die "cannot read build parent $parent"
  IFS=$'\t' read -r _ parent_title parent_url _ <<< "$parent_row"
  parent_body=$(gh_body "$parent") || die "cannot read build parent $parent"
  gh_is_build_body "$parent_body" || die "parent $parent is not marked 'Work kind: build'"
  # Read the child body before any native write so an existing explicit link
  # to another build cannot be hidden by a new native relationship.
  gh_validate_build_link "$child" "$parent_url"

  # A readable native parent is authoritative. Never reparent an unrelated
  # existing parent, even when an explicit body fallback is available.
  child_parent_ref=$(gh_parent_ref "$child" 2>/dev/null) || die "cannot read native parent for $child"
  IFS=$'\t' read -r child_parent child_parent_url <<< "$child_parent_ref"
  if [ -n "$child_parent" ] && { [ "$child_parent" != "$parent" ] || { [ -n "$child_parent_url" ] && [ "$child_parent_url" != "$parent_url" ]; }; }; then
    die "ticket $child already has native parent $child_parent"
  fi
  if [ -z "$child_parent" ]; then
    local attach_ec=0
    gh_attach_native "$child" "$parent" || attach_ec=$?
    case "$attach_ec" in
      0) ;;
      44) gh_parent_details "$parent" >/dev/null || die "cannot verify build parent $parent"; gh_explicit_build_link "$child" "$parent" "$parent_title" "$parent_url" ;;
      3) exit 3 ;;
      *) return "$attach_ec" ;;
    esac
  fi
  # Keep the body link even when native attachment worked. It makes adoption
  # and enumeration recoverable if a later native read is unavailable.
  gh_explicit_build_link "$child" "$parent" "$parent_title" "$parent_url"
}

# Build a jq expression with the parent URL embedded as a JSON string. URLs
# cannot contain newlines, but escaping backslashes and quotes keeps this safe
# for Enterprise hosts with unusual paths.
gh_membership_jq() {
  local parent_url="$1" escaped
  escaped=${parent_url//\\/\\\\}
  escaped=${escaped//\"/\\\"}
  printf '.[] | select(.pull_request == null) | select((.body // "") | gsub("\\r"; "") | split("\\n") | any(startswith("Build parent: [") and endswith("](%s)"))) | .number\n' "$escaped"
}

gh_child_numbers() {
  local parent="$1" parent_row parent_url native="" fallback="" err prefix
  parent_row=$(gh_parent_details "$parent") || die "cannot read build parent $parent"
  IFS=$'\t' read -r _ _ parent_url _ <<< "$parent_row"
  prefix=${parent_url%/*}/
  prefix=${prefix//\\/\\\\}
  prefix=${prefix//\"/\\\"}
  err=$(mktemp)
  if ! native=$(gh api --paginate "repos/${OWNER}/${REPO}/issues/${parent}/sub_issues" --jq ".[] | if (.html_url | startswith(\"$prefix\")) then .number else error(\"cross-repository child requires its own repository context\") end" 2>"$err"); then
    if grep -qiE 'HTTP (404|410)|404 Not Found|410 Gone' "$err"; then
      native=""
      gh_parent_details "$parent" >/dev/null || die "cannot verify parent after native lookup failed"
    else
      cat "$err" >&2
      rm -f "$err"
      die "cannot enumerate native build children"
    fi
  fi
  rm -f "$err"
  fallback=$(gh api --paginate "repos/${OWNER}/${REPO}/issues?state=all&per_page=100" --jq "$(gh_membership_jq "$parent_url")") || die "cannot enumerate explicit build children"
  printf '%s\n%s\n' "$native" "$fallback" | awk 'NF && !seen[$0]++'
}

gh_children() {
  local parent="$1" numbers n row result=""
  numbers=$(gh_child_numbers "$parent") || die "cannot enumerate build children"
  while IFS= read -r n; do
    [ -n "$n" ] || continue
    row=$(gh issue view --repo "$OWNER/$REPO" "$n" --json number,state,title,url --jq '[.number,.state,.title,.url] | @tsv') || die "cannot read build child $n"
    [[ "$row" == "$n"$'\t'* ]] || die "missing or mismatched build child $n"
    local child_state child_title child_url
    IFS=$'\t' read -r _ child_state child_title child_url <<< "$row"
    case "$child_state" in OPEN|CLOSED|open|closed) ;; *) die "unknown state for build child $n" ;; esac
    [ -n "$child_title" ] && [ -n "$child_url" ] || die "incomplete build child $n"
    result="${result}${row}"$'\n'
  done <<< "$numbers"
  printf '%s' "$result"
}

gh_find() {
  local needle="$1" escaped
  [ -n "$needle" ] || die "find needs nonempty text"
  [[ "$needle" != *$'\n'* && "$needle" != *$'\r'* && "$needle" != *$'\t'* ]] || die "find text must be one line without tabs"
  escaped=${needle//\\/\\\\}
  escaped=${escaped//\"/\\\"}
  local rows
  rows=$(gh api --paginate "repos/${OWNER}/${REPO}/issues?state=all&per_page=100" --jq ".[] | select(.pull_request == null) | select((.body // \"\") | contains(\"$escaped\")) | [.number,.state,.title,.html_url] | @tsv") || die "cannot search issues"
  [ -z "$rows" ] || printf '%s\n' "$rows"
}

gh_create() {
  local title="$1" dry="$2"; shift 2
  local tmp out url num
  [ $# -ge 1 ] || die "create needs at least one --label"
  tmp=$(mktemp)
  cat > "$tmp"
  if [ "$dry" = "1" ]; then
    printf 'command\tgh issue create --repo %s --title %q' "$OWNER/$REPO" "$title"
    printf ' --label %q' "$@"
    printf ' --body-file %s\n' "$tmp"
    echo "tickets.sh: dry-run left the body file at $tmp; delete it after running the command" >&2
    return
  fi
  set -- "${@/#/--label=}"
  out=$(run_gh gh issue create --repo "$OWNER/$REPO" --title "$title" "$@" --body-file "$tmp")
  rm -f "$tmp"
  url=$(printf '%s\n' "$out" | tail -n 1)
  num="${url##*/}"
  printf '%s\t%s\n' "$num" "$url"
}

gh_wire() {
  local child="$1" blocker="$2"
  local blocker_id body tmp
  blocker_id=$(db_id "$blocker")
  if ! api_write --method POST "repos/${OWNER}/${REPO}/issues/${child}/dependencies/blocked_by" -F "issue_id=${blocker_id}"; then
    body=$(gh_body "$child")
    tmp=$(mktemp)
    printf 'Blocked by: #%s\n\n%s\n' "$blocker" "$body" > "$tmp"
    run_gh gh issue edit --repo "$OWNER/$REPO" "$child" --body-file "$tmp"
    rm -f "$tmp"
  fi
}

gh_still_ready() {
  local n="$1" label="$2" me="$3"
  local state body
  state=$(gh issue view --repo "$OWNER/$REPO" "$n" --json state --jq .state)
  case "$state" in
    OPEN|open) ;;
    *) return 1 ;;
  esac
  body=$(gh_body "$n") || return 1
  gh_is_build_body "$body" && return 1
  gh issue view --repo "$OWNER/$REPO" "$n" --json labels --jq '.labels[].name' | grep -qxF "$label" || return 1
  gh issue view --repo "$OWNER/$REPO" "$n" --json assignees --jq '.assignees[].login' | grep -qxF "$me" || return 1
  [ -z "$(gh_assignees_except "$n" "$me")" ] || return 1
  if gh_is_blocked "$n"; then
    return 1
  fi
  return 0
}

gh_unclaim() {
  local n="$1" me="$2"
  gh issue edit --repo "$OWNER/$REPO" "$n" --remove-assignee "$me" >/dev/null 2>&1 || true
}

gh_next() {
  local label="$1" do_claim="${2:-0}"
  local n title url created state login others ec body candidates
  login=""
  if [ "$do_claim" = "1" ]; then
    login=$(gh api user --jq .login)
  fi
  candidates=$(gh api --paginate --method GET "repos/${OWNER}/${REPO}/issues" -f state=open -f labels="$label" -f per_page=100 --jq '
    .[]
    | select(.pull_request == null)
    | select((.assignees | length) == 0)
    | select((.body // "") | gsub("\r"; "") | split("\n") | any(. == "Work kind: build") | not)
    | [.created_at, (.number|tostring), .title, .html_url]
    | @tsv
  ') || die "cannot enumerate ready tickets"
  candidates=$(printf '%s\n' "$candidates" | LC_ALL=C sort)
  while IFS=$'\t' read -r created n title url; do
    [ -n "$n" ] || continue
    # The listing can lag a close by a few seconds; read the issue itself before trusting it.
    state=$(gh issue view --repo "$OWNER/$REPO" "$n" --json state --jq .state)
    case "$state" in
      OPEN|open) ;;
      *) continue ;;
    esac
    body=$(gh_body "$n") || die "cannot read candidate $n"
    gh_is_build_body "$body" && continue
    if gh_is_blocked "$n"; then
      continue
    fi
    if [ "$do_claim" = "1" ]; then
      others=$(gh_assignees_except "$n" "$login")
      if [ -n "$others" ]; then
        continue
      fi
      ec=0
      try_gh gh issue edit --repo "$OWNER/$REPO" "$n" --add-assignee "$login" >/dev/null || ec=$?
      if [ "$ec" -eq 3 ]; then
        exit 3
      fi
      if [ "$ec" -ne 0 ]; then
        continue
      fi
      others=$(gh_assignees_except "$n" "$login")
      if [ -n "$others" ] || ! gh_still_ready "$n" "$label" "$login"; then
        gh_unclaim "$n" "$login"
        continue
      fi
    fi
    printf '%s\t%s\t%s\n' "$n" "$title" "$url"
    return
  done <<< "$candidates"
}

gh_assignees_except() {
  local n="$1" me="$2"
  gh issue view --repo "$OWNER/$REPO" "$n" --json assignees --jq '[.assignees[].login] | map(select(. != "'"$me"'")) | join(",")'
}

gh_claim() {
  local n="$1"
  local login others
  login=$(gh api user --jq .login)
  others=$(gh_assignees_except "$n" "$login")
  if [ -n "$others" ]; then
    die "already claimed by $others"
  fi
  run_gh gh issue edit --repo "$OWNER/$REPO" "$n" --add-assignee "$login" >/dev/null
  others=$(gh_assignees_except "$n" "$login")
  if [ -n "$others" ]; then
    gh issue edit --repo "$OWNER/$REPO" "$n" --remove-assignee "$login" >/dev/null 2>&1 || true
    die "already claimed by $others"
  fi
  printf 'claimed\t%s\t%s\n' "$n" "$login"
}

gh_label() {
  local n="$1"; shift
  run_gh gh issue edit --repo "$OWNER/$REPO" "$n" "$@" >/dev/null
}

gh_comment() {
  local n="$1"
  local body
  body=$(cat)
  run_gh gh issue comment --repo "$OWNER/$REPO" "$n" --body "$body"
}

gh_close() {
  local n="$1"
  run_gh gh issue close --repo "$OWNER/$REPO" "$n"
}

# ---------------------------------------------------------------- Linear and Jira (python3 stdlib)

# The adapter reads: TICKETS_TRACKER, TICKETS_PROJECT, TICKETS_DRY, TICKETS_BODY_FILE (the body
# for create and comment; stdin carries the program itself), the tracker's own env vars, then the
# subcommand and its arguments.
run_adapter() {
  local body_file=""
  case "$1" in
    create|comment|update-body) body_file=$(mktemp); cat > "$body_file" ;;
  esac
  local ec=0
  TICKETS_TRACKER="$TRACKER" TICKETS_PROJECT="$PROJECT" TICKETS_DRY="${DRY:-0}" TICKETS_BODY_FILE="$body_file" TICKETS_EXPECTED_BODY="${EXPECTED_BODY:-}" \
    python3 - "$@" <<'PY' || ec=$?
import base64, json, os, re, sys, urllib.error, urllib.request
from urllib.parse import urlparse

TRACKER = os.environ["TICKETS_TRACKER"]
PROJECT = os.environ.get("TICKETS_PROJECT") or ""
DRY = os.environ.get("TICKETS_DRY") == "1"
DONE_TYPES = ("completed", "canceled", "duplicate")  # Linear workflow state types that mean closed


def die(msg, code=1):
    print("tickets.sh: " + msg, file=sys.stderr)
    sys.exit(code)


def need(var):
    v = os.environ.get(var)
    if not v:
        die(f"{var} is not set")
    return v


class SameOriginHTTPSRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        old = urlparse(req.full_url)
        new = urlparse(newurl)
        if new.scheme != "https" or (new.netloc or "").lower() != (old.netloc or "").lower():
            die(f"refusing redirect from {req.full_url} to {newurl}")
        return urllib.request.HTTPRedirectHandler.redirect_request(
            self, req, fp, code, msg, headers, newurl
        )


_opener = urllib.request.build_opener(SameOriginHTTPSRedirectHandler())


def require_https(url):
    p = urlparse(url)
    if p.scheme != "https" or not p.netloc:
        die(f"tracker URL must be https (got {url})")


def http(method, url, headers, payload=None):
    require_https(url)
    data = json.dumps(payload).encode() if payload is not None else None
    h = {"Content-Type": "application/json", "Accept": "application/json"}
    h.update(headers)
    req = urllib.request.Request(url, data=data, method=method, headers=h)
    try:
        with _opener.open(req, timeout=60) as r:
            raw = r.read()
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors="replace")
        if e.code in (401, 403):
            print(body[:400], file=sys.stderr)
            sys.exit(3)
        die(f"HTTP {e.code} from {url}: {body[:400]}")
    except urllib.error.URLError as e:
        die(f"cannot reach {url}: {e.reason}")


def out(*fields):
    print("\t".join(str(f) for f in fields))


def read_body():
    path = os.environ.get("TICKETS_BODY_FILE")
    if not path:
        return ""
    with open(path, encoding="utf-8") as f:
        return f.read().rstrip("\n")


def is_build(body):
    return "Work kind: build" in (body or "").splitlines()


def build_links(body):
    body = (body or "").replace("\r\n", "\n").replace("\r", "\n")
    return re.findall(r"^Build parent: \[.*\]\((.+)\)$", body, re.M)


def linked_body(body, parent_url, title):
    body = body or ""
    links = build_links(body)
    if any(url != parent_url for url in links):
        die("ticket already names another build parent")
    if "Build parent:" in body and not links:
        die("malformed build parent link; reconcile before attaching")
    return body if links else f"Build parent: [{title}]({parent_url})\n\n{body}"


def guard_body(current, expected):
    if not expected:
        return
    try:
        with open(expected, encoding="utf-8") as f:
            snapshot = f.read()
    except OSError:
        die("expected body snapshot is missing or unreadable")
    if snapshot != current + "\n":
        die("current body differs from expected snapshot; refusing update")


# ------------------------------------------------------------------ Linear

class Linear:
    def __init__(self):
        self.key = need("LINEAR_API_KEY")
        self.url = "https://api.linear.app/graphql"
        self.team_key = PROJECT or os.environ.get("LINEAR_TEAM") or ""
        self._team = None

    def gql(self, query, variables=None):
        r = http("POST", self.url, {"Authorization": self.key}, {"query": query, "variables": variables or {}})
        if r.get("errors"):
            msgs = "; ".join(e.get("message", "") for e in r["errors"])
            if any(w in msgs.lower() for w in ("authentication", "unauthorized", "forbidden", "permission")):
                print(msgs, file=sys.stderr)
                sys.exit(3)
            die("Linear: " + msgs)
        return r.get("data", {})

    def team(self):
        if self._team is None:
            if not self.team_key:
                die("a Linear team key is needed: --project KEY or LINEAR_TEAM")
            nodes = self.gql("query($k:String!){teams(filter:{key:{eq:$k}}){nodes{id key name}}}", {"k": self.team_key})["teams"]["nodes"]
            if not nodes:
                die(f"no Linear team with key {self.team_key}")
            self._team = nodes[0]
        return self._team

    def issue(self, ident):
        d = self.gql(
            "query($i:String!){issue(id:$i){id identifier title url description createdAt "
            "state{name type} labels{nodes{id name}} assignee{id name} parent{id identifier url} "
            "inverseRelations{nodes{type issue{identifier state{type}}}} "
            "comments{nodes{body createdAt user{name}}}}}",
            {"i": ident},
        )["issue"]
        if not d:
            die(f"no Linear issue {ident}")
        return d

    def me(self):
        return self.gql("query{viewer{id name}}")["viewer"]

    def check(self):
        me = self.me()
        t = self.team()
        out("tracker", "linear")
        out("user", me["name"])
        out("project", f"{t['key']} ({t['name']})")

    def label_ids(self, names, create=False, color="#ededed"):
        t = self.team()
        nodes = self.gql(
            "query($n:[String!]){issueLabels(filter:{name:{in:$n}}){nodes{id name team{id}}}}", {"n": names}
        )["issueLabels"]["nodes"]
        have = {}
        for n in nodes:
            # a workspace label (team null) or this team's label both count
            if n.get("team") is None or n["team"]["id"] == t["id"]:
                have.setdefault(n["name"], n["id"])
        ids = []
        for name in names:
            if name in have:
                ids.append(have[name])
            elif create:
                if DRY:
                    out("would-create-label", name)
                    continue
                r = self.gql(
                    "mutation($i:IssueLabelCreateInput!){issueLabelCreate(input:$i){issueLabel{id}}}",
                    {"i": {"name": name, "color": color, "teamId": t["id"]}},
                )
                ids.append(r["issueLabelCreate"]["issueLabel"]["id"])
            else:
                die(f"no Linear label named {name}; run ensure-labels first")
        return ids

    def ensure_labels(self, color, names):
        self.label_ids(names, create=True, color="#" + color.lstrip("#"))

    def open_issues(self, label=None, unlabeled=False, unassigned=False):
        t = self.team()
        flt = {"team": {"id": {"eq": t["id"]}}, "state": {"type": {"nin": list(DONE_TYPES)}}}
        if label:
            flt["labels"] = {"name": {"eq": label}}
        if unassigned:
            flt["assignee"] = {"null": True}
        q = (
            "query($f:IssueFilter,$a:String){issues(filter:$f,first:100,after:$a){"
            "pageInfo{hasNextPage endCursor} "
            "nodes{identifier title url createdAt updatedAt "
            "labels{nodes{name}} inverseRelations{nodes{type issue{state{type}}}}}}}"
        )
        nodes, after = [], None
        while True:
            conn = self.gql(q, {"f": flt, "a": after})["issues"]
            nodes.extend(conn["nodes"])
            if not conn["pageInfo"]["hasNextPage"] or not conn["pageInfo"].get("endCursor"):
                break
            after = conn["pageInfo"]["endCursor"]
        if unlabeled:
            nodes = [n for n in nodes if not n["labels"]["nodes"]]
        return nodes

    def list(self, label, unlabeled):
        for n in sorted(self.open_issues(label=label, unlabeled=unlabeled), key=lambda n: n["updatedAt"]):
            out(n["identifier"], n["title"], n["url"], n["updatedAt"])

    def view(self, ident):
        d = self.issue(ident)
        out("id", d["identifier"]); out("title", d["title"]); out("url", d["url"])
        out("state", d["state"]["name"])
        out("labels", ",".join(l["name"] for l in d["labels"]["nodes"]))
        out("assignees", d["assignee"]["name"] if d.get("assignee") else "")
        print("body"); print(d.get("description") or "")
        print("comments")
        for c in d["comments"]["nodes"]:
            print(f"--- {(c.get('user') or {}).get('name', '')} {c['createdAt']}"); print(c["body"])

    def create(self, title, labels, body):
        t = self.team()
        if DRY:
            out("would-create", json.dumps({"teamId": t["id"], "title": title, "labels": labels, "description": body}))
            return
        ids = self.label_ids(labels)
        r = self.gql(
            "mutation($i:IssueCreateInput!){issueCreate(input:$i){issue{identifier url}}}",
            {"i": {"teamId": t["id"], "title": title, "description": body, "labelIds": ids}},
        )["issueCreate"]["issue"]
        out(r["identifier"], r["url"])

    def all_issues(self, parent_id=None):
        flt = {"parent": {"id": {"eq": parent_id}}} if parent_id else {"team": {"id": {"eq": self.team()["id"]}}}
        query = (
            "query($f:IssueFilter,$a:String){issues(filter:$f,first:100,after:$a,includeArchived:true){"
            "pageInfo{hasNextPage endCursor} nodes{identifier title url description "
            "state{name type} parent{id identifier url}}}}"
        )
        nodes, after, seen = [], None, set()
        while True:
            conn = self.gql(query, {"f": flt, "a": after})["issues"]
            nodes.extend(conn["nodes"])
            page = conn["pageInfo"]
            if not page["hasNextPage"]:
                return nodes
            after = page.get("endCursor")
            if not after or after in seen:
                die("incomplete issue pagination")
            seen.add(after)

    def body(self, ident):
        print(self.issue(ident).get("description") or "")

    def update_body(self, ident, body, expected=""):
        d = self.issue(ident)
        guard_body(d.get("description") or "", expected)
        r = self.gql(
            "mutation($id:String!,$i:IssueUpdateInput!){issueUpdate(id:$id,input:$i){success}}",
            {"id": d["id"], "i": {"description": body}},
        )
        if not r["issueUpdate"]["success"]:
            die("body update failed")

    def attach(self, child, parent):
        c, p = self.issue(child), self.issue(parent)
        if c["id"] == p["id"]:
            die("a build cannot contain itself")
        if not is_build(p.get("description")):
            die("parent is not marked 'Work kind: build'")
        current_parent = c.get("parent")
        if current_parent and current_parent["id"] != p["id"]:
            die("ticket already has another native parent")
        body = linked_body(c.get("description"), p["url"], p["title"])
        if current_parent and body == (c.get("description") or ""):
            return
        r = self.gql(
            "mutation($id:String!,$i:IssueUpdateInput!){issueUpdate(id:$id,input:$i){success}}",
            {"id": c["id"], "i": {"parentId": p["id"], "description": body}},
        )
        if not r["issueUpdate"]["success"]:
            die("attachment failed")

    def children(self, parent):
        p = self.issue(parent)
        found = {}
        for n in self.all_issues(parent_id=p["id"]) + self.all_issues():
            native = n.get("parent") or {}
            if native.get("id") == p["id"] or p["url"] in build_links(n.get("description")):
                d = self.issue(n["identifier"])
                found[d["identifier"]] = d
        for d in found.values():
            out(d["identifier"], d["state"]["type"], d["title"], d["url"])

    def find(self, text):
        for d in self.all_issues():
            if text in (d.get("description") or ""):
                out(d["identifier"], d["state"]["type"], d["title"], d["url"])

    def wire(self, child, blocker):
        c = self.issue(child); b = self.issue(blocker)
        self.gql(
            "mutation($i:IssueRelationCreateInput!){issueRelationCreate(input:$i){success}}",
            {"i": {"issueId": b["id"], "relatedIssueId": c["id"], "type": "blocks"}},
        )

    @staticmethod
    def blocked(n):
        for rel in n["inverseRelations"]["nodes"]:
            if rel["type"] == "blocks" and rel["issue"]["state"]["type"] not in DONE_TYPES:
                return True
        return False

    def still_ready(self, ident, label, me_id):
        d = self.issue(ident)
        if is_build(d.get("description")) or d["state"]["type"] in DONE_TYPES:
            return False
        if label not in [l["name"] for l in d["labels"]["nodes"]]:
            return False
        a = d.get("assignee")
        if not a or a["id"] != me_id:
            return False
        if self.blocked(d):
            return False
        return True

    def unclaim(self, ident):
        d = self.issue(ident)
        self.gql(
            "mutation($id:String!,$i:IssueUpdateInput!){issueUpdate(id:$id,input:$i){success}}",
            {"id": d["id"], "i": {"assigneeId": None}},
        )

    def next(self, label, do_claim=False):
        me = self.me() if do_claim else None
        for n in sorted(self.open_issues(label=label, unassigned=True), key=lambda n: n["createdAt"]):
            if self.blocked(n):
                continue
            ident = n["identifier"]
            current = self.issue(ident)
            if is_build(current.get("description")) or current["state"]["type"] in DONE_TYPES:
                continue
            if do_claim:
                d = self.issue(ident)
                a = d.get("assignee")
                if a and a["id"] != me["id"]:
                    continue
                if not a:
                    self.gql(
                        "mutation($id:String!,$i:IssueUpdateInput!){issueUpdate(id:$id,input:$i){success}}",
                        {"id": d["id"], "i": {"assigneeId": me["id"]}},
                    )
                if not self.still_ready(ident, label, me["id"]):
                    self.unclaim(ident)
                    continue
            out(n["identifier"], n["title"], n["url"])
            return

    def claim(self, ident):
        me = self.me(); d = self.issue(ident)
        a = d.get("assignee")
        if a and a["id"] != me["id"]:
            die(f"already claimed by {a['name']}")
        self.gql("mutation($id:String!,$i:IssueUpdateInput!){issueUpdate(id:$id,input:$i){success}}",
                 {"id": d["id"], "i": {"assigneeId": me["id"]}})
        out("claimed", d["identifier"], me["name"])

    def label(self, ident, add, remove):
        d = self.issue(ident)
        have = {l["name"]: l["id"] for l in d["labels"]["nodes"]}
        for name in remove:
            have.pop(name, None)
        for name, lid in zip(add, self.label_ids(add) if add else []):
            have[name] = lid
        self.gql("mutation($id:String!,$i:IssueUpdateInput!){issueUpdate(id:$id,input:$i){success}}",
                 {"id": d["id"], "i": {"labelIds": list(have.values())}})

    def comment(self, ident, body):
        d = self.issue(ident)
        r = self.gql("mutation($i:CommentCreateInput!){commentCreate(input:$i){comment{url}}}",
                     {"i": {"issueId": d["id"], "body": body}})["commentCreate"]["comment"]
        print(r.get("url", ""))

    def close(self, ident):
        d = self.issue(ident); t = self.team()
        states = self.gql("query($t:String!){team(id:$t){states{nodes{id type position}}}}", {"t": t["id"]})["team"]["states"]["nodes"]
        done = sorted((s for s in states if s["type"] == "completed"), key=lambda s: s["position"])
        if not done:
            die("this team has no completed state")
        self.gql("mutation($id:String!,$i:IssueUpdateInput!){issueUpdate(id:$id,input:$i){success}}",
                 {"id": d["id"], "i": {"stateId": done[0]["id"]}})


# ------------------------------------------------------------------ Jira Cloud

def adf(text):
    paras = [p for p in text.split("\n\n")]
    content = []
    for p in paras:
        if not p.strip():
            continue
        lines = p.split("\n")
        nodes = []
        for i, line in enumerate(lines):
            if i:
                nodes.append({"type": "hardBreak"})
            if line:
                nodes.append({"type": "text", "text": line})
        content.append({"type": "paragraph", "content": nodes or [{"type": "text", "text": " "}]})
    return {"type": "doc", "version": 1, "content": content or [{"type": "paragraph", "content": []}]}


def adf_text(node):
    if node is None:
        return ""
    if isinstance(node, str):
        return node
    t = node.get("type")
    if t == "text":
        return node.get("text", "")
    if t == "hardBreak":
        return "\n"
    inner = "".join(adf_text(c) for c in node.get("content", []))
    if t in ("paragraph", "heading", "listItem", "codeBlock", "blockquote"):
        return inner + "\n"
    return inner


class Jira:
    def __init__(self):
        self.base = need("JIRA_BASE_URL").rstrip("/")
        require_https(self.base)
        email = need("JIRA_EMAIL"); token = need("JIRA_API_TOKEN")
        self.auth = "Basic " + base64.b64encode(f"{email}:{token}".encode()).decode()
        self.project = PROJECT or os.environ.get("JIRA_PROJECT") or ""
        self.issue_type = os.environ.get("JIRA_ISSUE_TYPE", "Task")

    def api(self, method, path, payload=None):
        return http(method, self.base + "/rest/api/3" + path, {"Authorization": self.auth}, payload)

    def url_of(self, key):
        return f"{self.base}/browse/{key}"

    def need_project(self):
        if not self.project:
            die("a Jira project key is needed: --project KEY or JIRA_PROJECT")
        return self.project

    def check(self):
        me = self.api("GET", "/myself")
        p = self.api("GET", f"/project/{self.need_project()}")
        out("tracker", "jira"); out("user", me.get("displayName", me.get("accountId", "")))
        out("project", f"{p['key']} ({p.get('name', '')})")

    def ensure_labels(self, color, names):
        self.need_project()  # Jira labels are free text; nothing to create

    def search(self, jql, fields):
        issues, token, seen = [], None, set()
        while True:
            payload = {"jql": jql, "fields": fields, "maxResults": 100}
            if token:
                payload["nextPageToken"] = token
            r = self.api("POST", "/search/jql", payload)
            issues.extend(r["issues"])
            token = r.get("nextPageToken")
            if not token:
                if r.get("isLast") is False:
                    die("incomplete issue pagination")
                break
            if token in seen:
                die("repeated issue pagination token")
            seen.add(token)
        return issues

    def list(self, label, unlabeled):
        p = self.need_project()
        cond = "labels is EMPTY" if unlabeled else f'labels = "{label}"'
        for i in self.search(f"project = {p} AND {cond} AND statusCategory != Done ORDER BY updated ASC", ["summary", "updated"]):
            out(i["key"], i["fields"]["summary"], self.url_of(i["key"]), i["fields"]["updated"])

    def view(self, key):
        i = self.api("GET", f"/issue/{key}?fields=summary,status,labels,assignee,description,comment")
        f = i["fields"]
        out("id", i["key"]); out("title", f["summary"]); out("url", self.url_of(i["key"]))
        out("state", f["status"]["name"]); out("labels", ",".join(f.get("labels") or []))
        out("assignees", (f.get("assignee") or {}).get("displayName", ""))
        print("body"); print(adf_text(f.get("description")).rstrip("\n"))
        print("comments")
        for c in (f.get("comment") or {}).get("comments", []):
            print(f"--- {(c.get('author') or {}).get('displayName', '')} {c.get('created', '')}")
            print(adf_text(c.get("body")).rstrip("\n"))

    def create(self, title, labels, body):
        p = self.need_project()
        fields = {"project": {"key": p}, "summary": title, "issuetype": {"name": self.issue_type},
                  "labels": labels, "description": adf(body)}
        if DRY:
            out("would-create", json.dumps(fields))
            return
        r = self.api("POST", "/issue", {"fields": fields})
        out(r["key"], self.url_of(r["key"]))

    def issue_record(self, key):
        return self.api("GET", f"/issue/{key}?fields=summary,status,description,parent,issuetype,labels,assignee,issuelinks")

    def all_issues(self):
        return self.search(f"project = {self.need_project()} ORDER BY created ASC",
                           ["summary", "description", "status", "parent"])

    def body(self, key):
        print(adf_text(self.issue_record(key)["fields"].get("description")).rstrip("\n"))

    def update_body(self, key, body, expected=""):
        d = self.issue_record(key)
        guard_body(adf_text(d["fields"].get("description")).rstrip("\n"), expected)
        self.api("PUT", f"/issue/{key}", {"fields": {"description": adf(body)}})

    def attach(self, child, parent):
        c, p = self.issue_record(child), self.issue_record(parent)
        if c["key"] == p["key"]:
            die("a build cannot contain itself")
        cf, pf = c["fields"], p["fields"]
        if not is_build(adf_text(pf.get("description"))):
            die("parent is not marked 'Work kind: build'")
        native = cf.get("parent")
        if native and native["key"] != p["key"]:
            die("ticket already has another native parent")
        before = adf_text(cf.get("description")).rstrip("\n")
        body = linked_body(before, self.url_of(p["key"]), pf["summary"])
        fields = {}
        if body != before:
            fields["description"] = adf(body)
        child_level = (cf.get("issuetype") or {}).get("hierarchyLevel")
        parent_level = (pf.get("issuetype") or {}).get("hierarchyLevel")
        if not native and isinstance(child_level, int) and parent_level == child_level + 1:
            fields["parent"] = {"key": p["key"]}
        if fields:
            self.api("PUT", f"/issue/{child}", {"fields": fields})

    def children(self, parent):
        p = self.issue_record(parent)
        found = {}
        # Include native children outside the configured project too.
        native = self.search(f'parent = "{p["key"]}"', ["summary", "description", "status", "parent"])
        for n in native + self.all_issues():
            f = n["fields"]
            if n in native or (f.get("parent") or {}).get("key") == p["key"] or self.url_of(p["key"]) in build_links(adf_text(f.get("description"))):
                d = self.issue_record(n["key"])
                found[d["key"]] = d
        for d in found.values():
            f = d["fields"]
            out(d["key"], f["status"]["name"], f["summary"], self.url_of(d["key"]))

    def find(self, text):
        for d in self.all_issues():
            if text in adf_text(d["fields"].get("description")):
                f = d["fields"]
                out(d["key"], f["status"]["name"], f["summary"], self.url_of(d["key"]))

    def wire(self, child, blocker):
        self.api("POST", "/issueLink", {"type": {"name": "Blocks"}, "outwardIssue": {"key": blocker}, "inwardIssue": {"key": child}})

    @staticmethod
    def blocked(issue):
        for link in issue["fields"].get("issuelinks") or []:
            other = link.get("inwardIssue")  # present when the other issue blocks this one
            if link.get("type", {}).get("name") == "Blocks" and other:
                cat = (((other.get("fields") or {}).get("status") or {}).get("statusCategory") or {}).get("key")
                if cat != "done":
                    return True
        return False

    def still_ready(self, key, label, me_id):
        i = self.api("GET", f"/issue/{key}?fields=status,labels,assignee,issuelinks")
        f = i["fields"]
        if is_build(adf_text(self.issue_record(key)["fields"].get("description"))):
            return False
        if (f.get("status") or {}).get("statusCategory", {}).get("key") == "done":
            return False
        if label not in (f.get("labels") or []):
            return False
        a = f.get("assignee")
        if not a or a.get("accountId") != me_id:
            return False
        if self.blocked(i):
            return False
        return True

    def unclaim(self, key):
        self.api("PUT", f"/issue/{key}/assignee", {"accountId": None})

    def next(self, label, do_claim=False):
        p = self.need_project()
        me = self.api("GET", "/myself") if do_claim else None
        jql = f'project = {p} AND labels = "{label}" AND statusCategory != Done AND assignee is EMPTY ORDER BY created ASC'
        for i in self.search(jql, ["summary", "issuelinks", "created"]):
            if self.blocked(i):
                continue
            key = i["key"]
            current = self.issue_record(key)["fields"]
            if is_build(adf_text(current.get("description"))) or current["status"]["statusCategory"]["key"] == "done":
                continue
            if do_claim:
                cur = self.api("GET", f"/issue/{key}?fields=assignee")["fields"].get("assignee")
                if cur and cur.get("accountId") != me["accountId"]:
                    continue
                if not cur:
                    self.api("PUT", f"/issue/{key}/assignee", {"accountId": me["accountId"]})
                if not self.still_ready(key, label, me["accountId"]):
                    self.unclaim(key)
                    continue
            out(i["key"], i["fields"]["summary"], self.url_of(i["key"]))
            return

    def claim(self, key):
        me = self.api("GET", "/myself")
        cur = self.api("GET", f"/issue/{key}?fields=assignee")["fields"].get("assignee")
        if cur and cur.get("accountId") != me["accountId"]:
            die(f"already claimed by {cur.get('displayName', cur.get('accountId'))}")
        self.api("PUT", f"/issue/{key}/assignee", {"accountId": me["accountId"]})
        out("claimed", key, me.get("displayName", me["accountId"]))

    def label(self, key, add, remove):
        update = [{"add": l} for l in add] + [{"remove": l} for l in remove]
        self.api("PUT", f"/issue/{key}", {"update": {"labels": update}})

    def comment(self, key, body):
        r = self.api("POST", f"/issue/{key}/comment", {"body": adf(body)})
        print(f"{self.url_of(key)}?focusedCommentId={r.get('id', '')}")

    def close(self, key):
        trans = self.api("GET", f"/issue/{key}/transitions").get("transitions", [])
        done = [t for t in trans if (t.get("to") or {}).get("statusCategory", {}).get("key") == "done"]
        if not done:
            die(f"no transition to a done status is available on {key}")
        self.api("POST", f"/issue/{key}/transitions", {"transition": {"id": done[0]["id"]}})


# ------------------------------------------------------------------ dispatch

def main():
    args = sys.argv[1:]
    cmd, rest = args[0], args[1:]
    t = Linear() if TRACKER == "linear" else Jira()
    if cmd == "check":
        t.check()
    elif cmd == "ensure-labels":
        color, names = rest[0], rest[1:]
        t.ensure_labels(color, names)
    elif cmd == "list":
        t.list(None if rest[0] == "--unlabeled" else rest[0], rest[0] == "--unlabeled")
    elif cmd == "view":
        t.view(rest[0])
    elif cmd == "create":
        t.create(rest[0], rest[1:], read_body())
    elif cmd == "body":
        t.body(rest[0])
    elif cmd == "update-body":
        t.update_body(rest[0], read_body(), os.environ.get("TICKETS_EXPECTED_BODY", ""))
    elif cmd == "attach":
        t.attach(rest[0], rest[1])
    elif cmd == "children":
        t.children(rest[0])
    elif cmd == "find":
        t.find(rest[0])
    elif cmd == "wire":
        t.wire(rest[0], rest[1])
    elif cmd == "next":
        t.next(rest[0], "--claim" in rest[1:])
    elif cmd == "claim":
        t.claim(rest[0])
    elif cmd == "label":
        add, remove, mode = [], [], None
        for a in rest[1:]:
            if a == "--add":
                mode = add
            elif a == "--remove":
                mode = remove
            elif mode is None:
                die("label ID [--add L]... [--remove L]...")
            else:
                mode.append(a)
        t.label(rest[0], add, remove)
    elif cmd == "comment":
        t.comment(rest[0], read_body())
    elif cmd == "close":
        t.close(rest[0])
    else:
        die("unknown subcommand: " + cmd)


main()
PY
  [ -n "$body_file" ] && rm -f "$body_file"
  return "$ec"
}

# ---------------------------------------------------------------- argument parsing and dispatch

TRACKER="github"
PROJECT=""
REPO_SPEC=""
DRY=0
EXPECTED_BODY=""
args=()
while [ $# -gt 0 ]; do
  case "$1" in
    --tracker) [ $# -ge 2 ] || die "--tracker needs a value"; TRACKER="$2"; shift 2 ;;
    --tracker=*) TRACKER="${1#--tracker=}"; shift ;;
    --project) [ $# -ge 2 ] || die "--project needs KEY"; PROJECT="$2"; shift 2 ;;
    --project=*) PROJECT="${1#--project=}"; shift ;;
    --repo) [ $# -ge 2 ] || die "--repo needs OWNER/REPO"; REPO_SPEC="$2"; shift 2 ;;
    --repo=*) REPO_SPEC="${1#--repo=}"; shift ;;
    --dry-run) DRY=1; shift ;;
    *) args+=("$1"); shift ;;
  esac
done
set -- "${args[@]+"${args[@]}"}"

case "$TRACKER" in
  github|linear|jira) ;;
  *) die "tracker must be github, linear, or jira (got '$TRACKER')" ;;
esac

cmd="${1:-}"
shift || true

case "$cmd" in
  -h|--help|help|"") usage; exit 0 ;;
esac

# Subcommand argument shaping shared by every tracker.
color="ededed"
labels=()
NEXT_CLAIM=0
case "$cmd" in
  ensure-labels)
    while [ $# -gt 0 ]; do
      case "$1" in
        --color) [ $# -ge 2 ] || die "--color needs HEX"; color="$2"; shift 2 ;;
        --color=*) color="${1#--color=}"; shift ;;
        *) labels+=("$1"); shift ;;
      esac
    done
    [ ${#labels[@]} -ge 1 ] || die "ensure-labels needs at least one label"
    ;;
  create)
    [ $# -ge 1 ] || die "create TITLE --label L..."
    title="$1"; shift
    while [ $# -gt 0 ]; do
      case "$1" in
        --label) [ $# -ge 2 ] || die "--label needs a name"; labels+=("$2"); shift 2 ;;
        --label=*) labels+=("${1#--label=}"); shift ;;
        *) die "unexpected argument: $1" ;;
      esac
    done
    [ ${#labels[@]} -ge 1 ] || die "create needs at least one --label"
    ;;
  next)
    [ $# -ge 1 ] || die "next needs a label"
    case "${2:-}" in
      --claim) NEXT_CLAIM=1 ;;
      "") ;;
      *) die "next READY_LABEL [--claim]" ;;
    esac
    ;;
  update-body)
    [ $# -eq 1 ] || { [ $# -eq 3 ] && [ "$2" = "--expected-body" ]; } || die "update-body ID [--expected-body PATH]"
    EXPECTED_BODY="${3:-}"
    ;;
  find) [ $# -eq 1 ] && [ -n "$1" ] || die "find needs literal text" ;;
  list|view|claim|comment|close|children|body) [ $# -ge 1 ] || die "$cmd needs an argument" ;;
  attach|wire) [ $# -ge 2 ] || die "$cmd needs two issue IDs" ;;
  label) [ $# -ge 2 ] || die "label ID [--add L]... [--remove L]..." ;;
  check) ;;
  *) die "unknown subcommand: $cmd" ;;
esac

case "$cmd" in
  view|claim|comment|close|children|body|update-body)
    set -- "$(normalize_id "$1")"
    ;;
  attach|wire)
    set -- "$(normalize_id "$1")" "$(normalize_id "$2")"
    ;;
  label)
    _nid="$(normalize_id "$1")"; shift
    set -- "$_nid" "$@"
    unset _nid
    ;;
esac

if [ "$TRACKER" != "github" ]; then
  case "$cmd" in
    ensure-labels) run_adapter ensure-labels "$color" "${labels[@]}" ;;
    create) run_adapter create "$title" "${labels[@]}" ;;
    *) run_adapter "$cmd" "$@" ;;
  esac
  exit $?
fi

locate_repo "$REPO_SPEC"
case "$cmd" in
  check) gh_check ;;
  ensure-labels) gh_ensure_labels "$color" "${labels[@]}" ;;
  list) gh_list "$1" ;;
  view) gh_view "$1" ;;
  create) gh_create "$title" "$DRY" "${labels[@]}" ;;
  body) gh_body "$1" ;;
  update-body) gh_update_body "$1" "$EXPECTED_BODY" ;;
  attach) gh_attach "$1" "$2" ;;
  children) gh_children "$1" ;;
  find) gh_find "$1" ;;
  wire) gh_wire "$1" "$2" ;;
  next) gh_next "$1" "$NEXT_CLAIM" ;;
  claim) gh_claim "$1" ;;
  label)
    n="$1"; shift
    edit=()
    mode=""
    while [ $# -gt 0 ]; do
      case "$1" in
        --add) mode="--add-label"; shift ;;
        --remove) mode="--remove-label"; shift ;;
        *) [ -n "$mode" ] || die "label ID [--add L]... [--remove L]..."; edit+=("$mode" "$1"); shift ;;
      esac
    done
    [ ${#edit[@]} -ge 1 ] || die "label needs --add or --remove"
    gh_label "$n" "${edit[@]}"
    ;;
  comment) gh_comment "$1" ;;
  close) gh_close "$1" ;;
esac
