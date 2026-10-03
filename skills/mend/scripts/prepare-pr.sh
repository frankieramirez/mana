#!/usr/bin/env bash
# Select a validated PR head and fetch its base. Never merge or push.
set -euo pipefail

usage() {
  printf '%s\n' 'Usage: prepare-pr.sh <PR number or URL>' \
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
check_peer() {
  local head=$1 peer=$2 tip=$3 current status
  valid_branch "$head" || fail 'invalid head branch'
  current=$(git rev-parse --verify "refs/heads/$head") || fail 'peer branch disappeared'
  [[ $current == "$tip" ]] || fail 'peer branch changed; hold the push and reconcile its local commits'
  [[ $(git -C "$peer" symbolic-ref --quiet HEAD) == "refs/heads/$head" ]] || fail 'peer worktree changed branches; hold the push'
  status=$(git -C "$peer" status --porcelain) || fail 'cannot inspect peer worktree; hold the push'
  [[ -z $status ]] || fail 'peer worktree is dirty; hold the push'
}
if [[ ${1:-} == --check-peer ]]; then
  [[ $# == 4 ]] || { usage >&2; exit 2; }
  check_peer "$2" "$3" "$4"
  printf 'peer=unchanged\n'
  exit 0
fi
[[ $# == 1 && $1 != -* ]] || { usage >&2; exit 2; }
command -v git >/dev/null || fail 'git is unavailable'
command -v gh >/dev/null || fail 'gh is unavailable'
start=$(git symbolic-ref --quiet --short HEAD 2>/dev/null) || start=$(git rev-parse --short HEAD)
status=$(git status --porcelain) || fail 'cannot inspect checkout'
[[ -z $status ]] || fail 'dirty checkout'
# A clean index can still belong to an unfinished operation.
for marker in MERGE_HEAD CHERRY_PICK_HEAD REVERT_HEAD rebase-merge rebase-apply; do
  [[ ! -e $(git rev-parse --git-path "$marker") ]] || fail 'an operation is already in progress'
done
metadata=$(gh pr view "$1" --json state,baseRefName,headRefName,isCrossRepository,url \
  --jq '[.state, .baseRefName, .headRefName, .isCrossRepository, .url] | @tsv') || fail 'cannot read PR'
IFS=$'\t' read -r state base head fork url <<< "$metadata"
[[ $state == OPEN ]] || fail 'PR is not open'
[[ $fork == false ]] || fail 'fork PR is unsupported'
valid_branch "$base" && valid_branch "$head" || fail 'invalid PR branch metadata'
pr_repo=${url%/pull/*}
[[ $pr_repo != "$url" && $pr_repo == https://* ]] || fail 'cannot resolve PR repository'
origin=$(git remote get-url origin) || fail 'origin is missing'
origin_repo=$(gh repo view "$origin" --json url --jq .url) || fail 'cannot resolve origin repository'
[[ ${origin_repo,,} == "${pr_repo,,}" ]] || fail 'PR repository differs from origin'
# Push URLs can differ from the fetch URL. Validate every configured destination.
push_urls=$(git remote get-url --push --all origin) || fail 'origin push destination is missing'
while IFS= read -r push_url; do
  [[ -n $push_url ]] || fail 'empty origin push destination'
  push_repo=$(gh repo view "$push_url" --json url --jq .url) || fail 'cannot resolve origin push repository'
  [[ ${push_repo,,} == "${pr_repo,,}" ]] || fail 'PR repository differs from origin push destination'
done <<< "$push_urls"
remote_head="refs/remotes/origin/$head"
remote_base="refs/remotes/origin/$base"
local_head="refs/heads/$head"
git fetch --no-tags origin "+refs/heads/$head:$remote_head" || fail 'head fetch failed'
peer= peer_tip= mode=current
if [[ $(git symbolic-ref --quiet HEAD || true) != "$local_head" ]]; then
  path=
  while IFS= read -r -d '' field; do
    case $field in
      'worktree '*) path=${field#worktree } ;;
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
    git merge --ff-only "$remote_head" || fail 'head fast-forward failed'
    mode=existing
  else
    # --track depends on the configured fetch mapping, even after an explicit fetch.
    git switch --no-track -c "$head" "$remote_head" || fail 'new branch switch failed'
    mode=created
  fi
fi
git fetch --no-tags origin "+refs/heads/$base:$remote_base" || fail 'base fetch failed'
printf 'start=%s\nhead=%s\nbase_ref=%s\npush_ref=%s\nmode=%s\npeer_worktree=%s\npeer_tip=%s\n' \
  "$start" "$head" "$remote_base" "$local_head" "$mode" "$peer" "$peer_tip"
