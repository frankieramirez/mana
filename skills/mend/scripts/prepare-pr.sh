#!/usr/bin/env bash
# Select a validated PR head and fetch its base, then publish the result later.
# Never merges. Pushes only through --push, without force.
set -euo pipefail

usage() {
  printf '%s\n' 'Usage: prepare-pr.sh <PR number or URL>' \
    '       prepare-pr.sh --field <start|head|base_ref|push_ref|mode|peer_worktree|peer_tip>' \
    '       prepare-pr.sh --push' \
    '       prepare-pr.sh --check-peer <head> <worktree> <recorded-tip>' \
    'Requires git and gh. Outputs key=value data; never source or eval it.'
}
if [[ ${1:-} == --help ]]; then usage; exit 0; fi
start=
fail() { printf 'prepare-pr: %s\n' "$*" >&2; exit 1; }
report_stop() {
  local result=$?
  if (( result != 0 )) && [[ -n $start ]]; then
    local current
    current=$(git symbolic-ref --quiet --short HEAD 2>/dev/null) || current=$(git rev-parse --short HEAD 2>/dev/null) || current=unknown
    printf 'prepare-pr: stopped; start=%s; current=%s\n' "$start" "$current" >&2
  fi
}
trap report_stop EXIT
valid_branch() {
  git check-ref-format "refs/heads/$1" >/dev/null 2>&1 &&
    git check-ref-format --branch "$1" >/dev/null 2>&1
}
# bash 3.2 has no ${var,,}.
lower() { printf '%s' "$1" | tr '[:upper:]' '[:lower:]'; }
require_idle() {
  local status marker
  status=$(git status --porcelain) || fail 'cannot inspect checkout'
  [[ -z $status ]] || fail 'dirty checkout'
  # A clean index can still belong to an unfinished operation.
  for marker in MERGE_HEAD CHERRY_PICK_HEAD REVERT_HEAD rebase-merge rebase-apply; do
    [[ ! -e $(git rev-parse --git-path "$marker") ]] || fail 'an operation is already in progress'
  done
}
check_peer() {
  local head=$1 peer=$2 tip=$3 current status
  valid_branch "$head" || fail 'invalid head branch'
  current=$(git rev-parse --verify "refs/heads/$head") || fail 'peer branch disappeared'
  [[ $current == "$tip" ]] || fail 'peer branch changed; hold the push and reconcile its local commits'
  [[ $(git -C "$peer" symbolic-ref --quiet HEAD) == "refs/heads/$head" ]] || fail 'peer worktree changed branches; hold the push'
  status=$(git -C "$peer" status --porcelain) || fail 'cannot inspect peer worktree; hold the push'
  [[ -z $status ]] || fail 'peer worktree is dirty; hold the push'
}
# Shell variables do not survive between an agent's tool calls, so later
# stages read the prepared values from this per-worktree record instead.
record_path() { git rev-parse --git-path mend-pr-target; }
field() {
  local key=$1 line record
  record=$(record_path)
  [[ -f $record ]] || fail 'no prepared PR in this checkout'
  while IFS= read -r line; do
    # Split on the first '=' only: a branch name can end in '='.
    if [[ ${line%%=*} == "$key" ]]; then
      printf '%s\n' "${line#*=}"
      return 0
    fi
  done < "$record"
  fail "prepared PR has no $key"
}
# gh cannot reach an SSH host alias (git@work:owner/repo). Map it through ssh's config.
resolve_repo() {
  local url=$1 host path real
  gh repo view "$url" --json url --jq .url 2>/dev/null && return 0
  case $url in
    ssh://*)
      host=${url#ssh://}
      host=${host#*@}
      path=${host#*/}
      host=${host%%/*}
      host=${host%%:*}
      ;;
    *://*) return 1 ;;
    *:*)
      host=${url%%:*}
      host=${host#*@}
      path=${url#*:}
      ;;
    *) return 1 ;;
  esac
  command -v ssh >/dev/null || return 1
  real=$(ssh -G "$host" 2>/dev/null | awk '$1 == "hostname" { print $2; exit }')
  [[ -n $real && $real != "$host" ]] || return 1
  path=${path%.git}
  gh repo view "https://$real/${path#/}" --json url --jq .url
}

if [[ ${1:-} == --check-peer ]]; then
  [[ $# == 4 ]] || { usage >&2; exit 2; }
  check_peer "$2" "$3" "$4"
  printf 'peer=unchanged\n'
  exit 0
fi
if [[ ${1:-} == --field ]]; then
  [[ $# == 2 ]] || { usage >&2; exit 2; }
  case $2 in
    start|head|base_ref|push_ref|mode|peer_worktree|peer_tip) field "$2" ;;
    *) usage >&2; exit 2 ;;
  esac
  exit 0
fi
if [[ ${1:-} == --push ]]; then
  [[ $# == 1 ]] || { usage >&2; exit 2; }
  head=$(field head)
  push_ref=$(field push_ref)
  mode=$(field mode)
  peer=$(field peer_worktree)
  peer_tip=$(field peer_tip)
  valid_branch "$head" && [[ $push_ref == "refs/heads/$head" ]] || fail 'prepared PR record is invalid'
  require_idle
  current=$(git symbolic-ref --quiet HEAD || true)
  if [[ $mode == detached ]]; then
    [[ -z $current ]] || fail 'checkout moved since preparation; hold the push'
  else
    [[ $current == "$push_ref" ]] || fail 'checkout moved since preparation; hold the push'
  fi
  if [[ -n $peer ]]; then
    check_peer "$head" "$peer" "$peer_tip"
  fi
  local_sha=$(git rev-parse --verify HEAD)
  git push origin "HEAD:$push_ref" || fail 'push rejected; hold and report the remote change'
  remote_sha=$(git ls-remote origin "$push_ref" | cut -f1)
  [[ $remote_sha == "$local_sha" ]] || fail "push not verified: origin $push_ref is ${remote_sha:-missing}"
  printf 'pushed=%s\npush_ref=%s\n' "$local_sha" "$push_ref"
  exit 0
fi

[[ $# == 1 && $1 != -* ]] || { usage >&2; exit 2; }
command -v git >/dev/null || fail 'git is unavailable'
command -v gh >/dev/null || fail 'gh is unavailable'
start=$(git symbolic-ref --quiet --short HEAD 2>/dev/null) || start=$(git rev-parse --short HEAD)
require_idle
metadata=$(gh pr view "$1" --json state,baseRefName,headRefName,isCrossRepository,url \
  --jq '[.state, .baseRefName, .headRefName, .isCrossRepository, .url] | @tsv') || fail 'cannot read PR'
IFS=$'\t' read -r state base head fork url <<< "$metadata"
[[ $state == OPEN ]] || fail 'PR is not open'
[[ $fork == false ]] || fail 'fork PR is unsupported'
valid_branch "$base" && valid_branch "$head" || fail 'invalid PR branch metadata'
pr_repo=${url%/pull/*}
[[ $pr_repo != "$url" && $pr_repo == https://* ]] || fail 'cannot resolve PR repository'
pr_repo=$(lower "$pr_repo")
origin=$(git remote get-url origin) || fail 'origin is missing'
origin_repo=$(resolve_repo "$origin") || fail 'cannot resolve origin repository'
[[ $(lower "$origin_repo") == "$pr_repo" ]] || fail 'PR repository differs from origin'
# Push URLs can differ from the fetch URL. Validate every configured destination.
push_urls=$(git remote get-url --push --all origin) || fail 'origin push destination is missing'
while IFS= read -r push_url; do
  [[ -n $push_url ]] || fail 'empty origin push destination'
  push_repo=$(resolve_repo "$push_url") || fail 'cannot resolve origin push repository'
  [[ $(lower "$push_repo") == "$pr_repo" ]] || fail 'PR repository differs from origin push destination'
done <<< "$push_urls"
remote_head="refs/remotes/origin/$head"
remote_base="refs/remotes/origin/$base"
local_head="refs/heads/$head"
git fetch --no-tags origin "+refs/heads/$head:$remote_head" || fail 'head fetch failed'
peer= peer_tip= mode=current
if [[ $(git symbolic-ref --quiet HEAD || true) != "$local_head" ]]; then
  path=
  while IFS= read -r -d '' entry; do
    case $entry in
      'worktree '*) path=${entry#worktree } ;;
      "branch $local_head") peer=$path ;;
    esac
  done < <(git worktree list --porcelain -z)
  if git show-ref --verify --quiet "$local_head"; then
    ahead=$(git rev-list --count "$remote_head..$local_head") || fail 'cannot count unpushed commits'
    [[ $ahead == 0 ]] || fail "branch $head has $ahead unpushed commits; worktree=${peer:-none}"
  fi
  if [[ -n $peer ]]; then
    [[ $peer != *$'\n'* && $peer != *$'\r'* ]] || fail 'peer path contains a line break'
    peer_tip=$(git rev-parse --verify "$local_head")
    check_peer "$head" "$peer" "$peer_tip"
    git switch --detach "$remote_head" || fail 'detached switch failed'
    mode=detached
  elif git show-ref --verify --quiet "$local_head"; then
    git switch "$head" || fail 'branch switch failed'
    # Keep stdout to the key=value contract.
    git merge --ff-only "$remote_head" >&2 || fail 'head fast-forward failed'
    mode=existing
  else
    # --track depends on the configured fetch mapping, even after an explicit fetch.
    git switch --no-track -c "$head" "$remote_head" || fail 'new branch switch failed'
    mode=created
  fi
fi
git fetch --no-tags origin "+refs/heads/$base:$remote_base" || fail 'base fetch failed'
prepared=$(printf 'start=%s\nhead=%s\nbase_ref=%s\npush_ref=%s\nmode=%s\npeer_worktree=%s\npeer_tip=%s\n' \
  "$start" "$head" "$remote_base" "$local_head" "$mode" "$peer" "$peer_tip")
record=$(record_path)
(umask 077 && printf '%s\n' "$prepared" > "$record.tmp") && mv -f "$record.tmp" "$record" || fail 'cannot record prepared PR'
printf '%s\n' "$prepared"
