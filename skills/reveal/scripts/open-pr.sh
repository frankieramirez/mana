#!/usr/bin/env bash
# open-pr.sh: create or edit the current branch's pull request, with --attach.
# git + gh only. JSON shaping is gh --jq.
#
#   open-pr.sh --check [--base BRANCH]
#   open-pr.sh [--dry-run] [--draft] [--base BRANCH] [--title TITLE] --body-file PATH [--attach PATH|#alt]...
#
# Looks up the current branch's PR. Existing: edit. None: create (title required).
# Prints TSV fields. Exit 3 on write refusal, 4 on conflicts, 5 on unknown mergeability.
# Honors GH_HOST.
set -euo pipefail

ERR=""
WRITE_OUT=""
trap 'rm -f "${ERR:-}" "${WRITE_OUT:-}"' EXIT

usage() {
  cat <<'EOF'
usage: open-pr.sh --check [--base BRANCH]
       open-pr.sh [--dry-run] [--draft] [--base BRANCH] [--title TITLE] --body-file PATH [--attach SPEC]...

  SPEC is path or path#alt. Repeat --attach. Paths must not contain #.
  --check runs only the fetched-base preflight; no body or attach required.
  --base sets the creation base; an existing PR's base is authoritative.
  --draft allows conflicting preflight and creates new PRs as drafts.
  Existing PR review state is unchanged. The working tree must be clean.

  Looks up the current branch's PR.
    existing  gh pr edit --body-file --attach
    none      gh pr create --title --body-file --attach

  Prints:
    base, base_sha, head_sha  the checked snapshot
    preflight clean|conflicting
    action   create|edit
    url      PR url (empty on dry-run create)
    number   PR number (empty on dry-run create)
    attach   yes|skipped
    reason   empty, or why attach was skipped
    command  the gh invocation (dry-run only)
    mergeability clean|conflicting|unknown (after writing)

  Exit 3 means this token cannot write the PR.
  Exit 4 means conflicts; exit 5 means post-write mergeability is unknown.
  A PR can exist after exit 4 or 5; retain its URL.
EOF
}

die() {
  echo "open-pr.sh: $*" >&2
  exit 1
}

try_gh() {
  local ec
  ERR=$(mktemp)
  LAST_ERR=""
  set +e
  "$@" 2>"$ERR"
  ec=$?
  set -e
  LAST_ERR=$(cat "$ERR")
  if [ "$ec" -eq 0 ]; then
    rm -f "$ERR"
    ERR=""
    LAST_ERR=""
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

run_gh() {
  try_gh "$@" || exit $?
}

version_ge() {
  local a1 a2 a3 b1 b2 b3
  IFS=. read -r a1 a2 a3 <<<"${1%%-*}"
  IFS=. read -r b1 b2 b3 <<<"${2%%-*}"
  a1=${a1:-0}; a2=${a2:-0}; a3=${a3:-0}
  b1=${b1:-0}; b2=${b2:-0}; b3=${b3:-0}
  [ "$a1" -gt "$b1" ] && return 0
  [ "$a1" -lt "$b1" ] && return 1
  [ "$a2" -gt "$b2" ] && return 0
  [ "$a2" -lt "$b2" ] && return 1
  [ "$a3" -ge "$b3" ]
}

gh_version() {
  local line
  line=$(gh --version 2>/dev/null | head -n 1) || return 1
  printf '%s\n' "$line" | awk '{print $3}'
}

repo_host() {
  local url host
  if [ -n "${GH_HOST:-}" ]; then
    printf '%s\n' "$GH_HOST"
    return
  fi
  url=$(gh repo view --json url --jq .url 2>/dev/null || true)
  url="${url#https://}"
  url="${url#http://}"
  host="${url%%/*}"
  printf '%s\n' "$host"
}

# Media upload accepts OAuth (gho_) and classic PATs (ghp_). Installation
# tokens (ghs_) and user-to-server / refresh tokens fail with
# "unsupported authentication type". Only the four-character prefix is
# read; the token itself never lands in a variable.
token_kind() {
  local t
  t=$(gh auth token 2>/dev/null | cut -c1-4 || true)
  case "$t" in
    ghs_*) echo ghs ;;
    ghu_*) echo ghu ;;
    ghr_*) echo ghr ;;
    *) echo ok ;;
  esac
}

file_kind() {
  local path ext
  path=${1%%#*}
  ext=$(printf '%s\n' "$path" | tr '[:upper:]' '[:lower:]')
  ext=${ext##*.}
  case "$ext" in
    png|jpg|jpeg|gif|webp|svg) echo image ;;
    mp4|mov|webm) echo video ;;
    *) echo other ;;
  esac
}

check_attach() {
  local spec=$1 path size kind
  path=${spec%%#*}
  [ -n "$path" ] || die "empty --attach"
  [ -f "$path" ] || die "attach file missing: $path"
  kind=$(file_kind "$path")
  [ "$kind" != other ] || die "unsupported attach type: $path"
  size=$(wc -c <"$path")
  if [ "$kind" = image ] && [ "$size" -gt 10485760 ]; then
    die "image over 10 MB: $path"
  fi
  if [ "$kind" = video ] && [ "$size" -gt 104857600 ]; then
    die "video over 100 MB: $path"
  fi
}

DRY=0
CHECK=0
DRAFT=0
BASE=""
TITLE=""
BODY=""
ATTACH=()

while [ $# -gt 0 ]; do
  case "$1" in
    -h|--help|help) usage; exit 0 ;;
    --dry-run) DRY=1; shift ;;
    --check) CHECK=1; shift ;;
    --draft) DRAFT=1; shift ;;
    --base)
      [ $# -ge 2 ] || die "--base needs a value"
      BASE=$2
      shift 2
      ;;
    --title)
      [ $# -ge 2 ] || die "--title needs a value"
      TITLE=$2
      shift 2
      ;;
    --body-file)
      [ $# -ge 2 ] || die "--body-file needs a path"
      BODY=$2
      shift 2
      ;;
    --attach)
      [ $# -ge 2 ] || die "--attach needs a path"
      ATTACH+=("$2")
      shift 2
      ;;
    *) die "unknown flag: $1" ;;
  esac
done

command -v gh >/dev/null 2>&1 || die "gh is not on PATH"

# Resolve through the same repository gh will write to, including fork upstreams.
branch=$(git symbolic-ref --quiet --short HEAD) || die "need a branch"
[ -z "$(git status --porcelain)" ] || die "need a clean working tree"
repo=$(gh repo view --json url --jq .url) || die "cannot resolve repository"
existing=$(gh pr list --head "$branch" --state open --json number,url,baseRefName,headRefName,isCrossRepository --jq '.[0] // empty | [.number, .url, .baseRefName, .headRefName, .isCrossRepository] | @tsv') || die "cannot look up pull request"
action=create
number=""
url=""
if [ -n "$existing" ]; then
  IFS=$'\t' read -r number url pr_base pr_head cross <<<"$existing"
  [ "$pr_head" = "$branch" ] && [ "$cross" = false ] || die "PR head must be this branch in this repository"
  [ -z "$BASE" ] || [ "$BASE" = "$pr_base" ] || die "--base differs from existing PR base"
  BASE=$pr_base
  action=edit
fi
if [ -z "$BASE" ]; then
  BASE=$(git config "branch.$branch.base" || true)
fi
if [ -z "$BASE" ]; then
  BASE=$(gh repo view --json defaultBranchRef --jq .defaultBranchRef.name) || die "cannot resolve base"
fi
git check-ref-format "refs/heads/$BASE" >/dev/null || die "invalid base branch: $BASE"
git fetch --no-tags -- "$repo" "refs/heads/$BASE" >&2 || die "cannot fetch base"
base_sha=$(git rev-parse FETCH_HEAD)
head_sha=$(git rev-parse HEAD)
preflight=clean
if git merge-tree --write-tree "$head_sha" "$base_sha" >&2; then
  :
else
  ec=$?
  [ "$ec" -eq 1 ] || die "mergeability check failed (requires git merge-tree --write-tree)"
  preflight=conflicting
fi
printf 'base\t%s\nbase_sha\t%s\nhead_sha\t%s\npreflight\t%s\n' "$BASE" "$base_sha" "$head_sha" "$preflight"
if [ "$CHECK" -eq 1 ]; then
  [ "$preflight" = clean ] && exit 0
  exit 4
fi
if [ "$preflight" = conflicting ] && [ "$DRAFT" -eq 0 ]; then
  [ -z "$url" ] || printf 'url\t%s\nnumber\t%s\n' "$url" "$number"
  echo "open-pr.sh: resolve base conflicts before shipping, or use --draft to preserve progress." >&2
  exit 4
fi

[ -n "$BODY" ] || die "need --body-file PATH"
[ -f "$BODY" ] || die "body file missing: $BODY"
[ -s "$BODY" ] || die "body file is empty: $BODY"

command -v gh >/dev/null 2>&1 || die "gh is not on PATH"

if [ "${#ATTACH[@]}" -gt 0 ]; then
  for spec in "${ATTACH[@]}"; do
    check_attach "$spec"
  done
fi

REASON=""
ATTACH_OK=1
ver=$(gh_version) || { ATTACH_OK=0; REASON="gh is missing or silent"; }
if [ "$ATTACH_OK" -eq 1 ]; then
  if ! version_ge "$ver" "2.99.0"; then
    ATTACH_OK=0
    REASON="gh $ver is older than 2.99.0"
  fi
fi
if [ "$ATTACH_OK" -eq 1 ]; then
  host=$(repo_host)
  case "$host" in
    github.com|www.github.com|"") ;;
    *)
      ATTACH_OK=0
      REASON="host $host is not github.com (Enterprise Server skips attach)"
      ;;
  esac
fi
if [ "$ATTACH_OK" -eq 1 ]; then
  case "$(token_kind)" in
    ghs|ghu|ghr)
      ATTACH_OK=0
      REASON="this token cannot upload media (need OAuth or a classic PAT)"
      ;;
  esac
fi

if [ "$ATTACH_OK" -eq 1 ] && [ "${#ATTACH[@]}" -eq 0 ]; then
  die "need at least one --attach"
fi
if [ "$ATTACH_OK" -eq 0 ]; then
  echo "open-pr.sh: attach skipped ($REASON)." >&2
fi

if [ "$action" = create ] && [ -z "$TITLE" ]; then
  die "need --title when this branch has no pull request"
fi

cmd=(gh)
if [ "$action" = create ]; then
  cmd+=(pr create --base "$BASE" --title "$TITLE" --body-file "$BODY")
  [ "$DRAFT" -eq 0 ] || cmd+=(--draft)
else
  cmd+=(pr edit "$number" --body-file "$BODY")
fi
if [ "$ATTACH_OK" -eq 1 ]; then
  for spec in "${ATTACH[@]}"; do
    cmd+=(--attach "$spec")
  done
fi

attach_field=yes
[ "$ATTACH_OK" -eq 1 ] || attach_field=skipped

if [ "$DRY" -eq 1 ]; then
  quoted=""
  for part in "${cmd[@]}"; do
    quoted+=" $(printf '%q' "$part")"
  done
  printf 'action\t%s\n' "$action"
  printf 'url\t%s\n' "$url"
  printf 'number\t%s\n' "$number"
  printf 'attach\t%s\n' "$attach_field"
  printf 'reason\t%s\n' "$REASON"
  printf 'command\t%s\n' "${quoted# }"
  exit 0
fi

cmd_plain=(gh)
if [ "$action" = create ]; then
  cmd_plain+=(pr create --base "$BASE" --title "$TITLE" --body-file "$BODY")
  [ "$DRAFT" -eq 0 ] || cmd_plain+=(--draft)
else
  cmd_plain+=(pr edit "$number" --body-file "$BODY")
fi

WRITE_OUT=$(mktemp)
if [ "$ATTACH_OK" -eq 1 ]; then
  if try_gh "${cmd[@]}" >"$WRITE_OUT"; then
    :
  else
    ec=$?
    [ "$ec" -eq 3 ] && exit 3
    if printf '%s' "${LAST_ERR:-}" | grep -qiE 'unsupported authentication type|failed to upload|401 Unauthorized'; then
      echo "open-pr.sh: attach failed; retrying without upload." >&2
      ATTACH_OK=0
      REASON="upload refused: unsupported authentication type"
      attach_field=skipped
      run_gh "${cmd_plain[@]}" >"$WRITE_OUT"
    else
      exit "$ec"
    fi
  fi
else
  run_gh "${cmd_plain[@]}" >"$WRITE_OUT"
fi

if [ -z "$url" ]; then
  url=$(awk '/^https?:\/\// {print; exit}' "$WRITE_OUT")
  [ -n "$url" ] || url=$(gh pr view --json url --jq .url 2>/dev/null || true)
  number=${url##*/}
fi

printf 'action\t%s\n' "$action"
printf 'url\t%s\n' "$url"
printf 'number\t%s\n' "$number"
printf 'attach\t%s\n' "$attach_field"
printf 'reason\t%s\n' "$REASON"

# GitHub computes this asynchronously. A clean result must describe this HEAD.
mergeability=unknown
for attempt in 1 2 3; do
  [ -n "$number" ] || break
  state=$(gh pr view "$number" --json mergeable,headRefOid,baseRefName --jq '[.mergeable, .headRefOid, .baseRefName] | @tsv' 2>/dev/null || true)
  IFS=$'\t' read -r mergeable remote_head remote_base <<<"$state"
  if [ "$remote_head" = "$head_sha" ] && [ "$remote_base" = "$BASE" ]; then
    case "$mergeable" in
      MERGEABLE) mergeability=clean; break ;;
      CONFLICTING) mergeability=conflicting; break ;;
    esac
  fi
  [ "$attempt" -eq 3 ] || sleep 2
done
printf 'mergeability\t%s\n' "$mergeability"
case "$mergeability" in
  conflicting) exit 4 ;;
  unknown) exit 5 ;;
esac
