#!/usr/bin/env bash
set -euo pipefail
usage() {
  cat <<'EOF'
Local portal continuation state, schema 1. No tracker writes or permission grants.
  start SCOPE COORDINATOR map|build CURRENT_ACTIONS DESTINATION
  show SCOPE
  record SCOPE COORDINATOR UNIT STATUS WORKSPACE BRANCH COMMIT PR EVIDENCE
  stop SCOPE COORDINATOR REASON
SCOPE is the canonical tracker/project/parent identity. COORDINATOR is a unique
host chat or process identifier, not a credential. Use - for absent unit fields.
STATUS: reserved, active, verified, awaiting-review, blocked, failed.
State lives in the repository's common Git directory, shared by local worktrees.
An existing lock is never stolen. After a crash, reconcile its owner before stop.
EOF
}
die() { printf 'run-state: %s\n' "$*" >&2; exit 1; }
case "${1:-}" in -h|--help) usage; exit 0;; esac
[ $# -ge 2 ] || { usage >&2; exit 2; }
command=$1 scope=$2
shift 2
[ -n "$scope" ] && [[ "$scope" != *$'\n'* ]] || die 'scope must be a nonempty single line'
common=$(git rev-parse --path-format=absolute --git-common-dir) || die 'a Git repository is required'
key=$(printf '%s' "$scope" | git hash-object --stdin)
directory="$common/mana-portal/$key"
state="$directory/state.config"
lock="$directory/lock"
get() { git config --no-includes --file "$state" --get "$1"; }
check_state() {
  [ -f "$state" ] || die 'no saved run'
  [ "$(get run.version)" = 1 ] || die 'unsupported or incomplete state schema'
  [ "$(get run.scope)" = "$scope" ] && [ "$(get run.repository)" = "$common" ] || die 'repository or scope identity changed'
}
check_owner() {
  check_state
  [ -f "$lock/owner" ] && [ "$(cat "$lock/owner")" = "$1" ] || die 'coordinator does not own this scope lock'
}
write() { git config --no-includes --file "$temporary" "$1" "$2"; }
temporary=''
start_pending=0
cleanup() {
  [ -z "$temporary" ] || rm -f "$temporary"
  if [ "$start_pending" = 1 ] && [ -f "$lock/owner" ] && [ "$(cat "$lock/owner")" = "$owner" ]; then
    rm "$lock/owner"
    rmdir "$lock"
  fi
}
trap cleanup EXIT
case "$command" in
  start)
    [ $# -eq 4 ] || die 'start needs coordinator, kind, current actions and destination'
    owner=$1 kind=$2 actions=$3 destination=$4
    [[ "$owner" =~ ^[a-zA-Z0-9._:-]+$ ]] || die 'invalid coordinator identity'
    case "$kind" in map|build) :;; *) die 'kind must be map or build';; esac
    [ -n "$actions" ] && [ -n "$destination" ] || die 'current actions and destination are required'
    mkdir -p "$directory"
    mkdir "$lock" 2>/dev/null || die "scope already locked: $lock; verify the previous coordinator has stopped"
    printf '%s\n' "$owner" > "$lock/owner"
    start_pending=1
    if [ -f "$state" ]; then
      check_state
      [ "$(get run.kind)" = "$kind" ] && [ "$(get run.destination)" = "$destination" ] || die 'kind or destination changed; reconcile before reusing this scope'
    fi
    temporary=$(mktemp "$directory/update.XXXXXX")
    if [ -f "$state" ]; then cat "$state" > "$temporary"; fi
    write run.version 1
    write run.repository "$common"
    write run.scope "$scope"
    write run.kind "$kind"
    write run.actions "$actions"
    write run.destination "$destination"
    write run.coordinator "$owner"
    if ! git config --no-includes --file "$temporary" --get run.original >/dev/null; then
      write run.original "$(git rev-parse --show-toplevel)"
    fi
    write run.stop-reason reconciliation-required
    mv "$temporary" "$state"
    temporary=''
    start_pending=0
    printf '%s\n' "$state"
    ;;
  show)
    [ $# -eq 0 ] || die 'show needs only scope'
    check_state
    git config --no-includes --file "$state" --list
    ;;
  record)
    [ $# -eq 8 ] || die 'record needs coordinator, unit, status, workspace, branch, commit, PR and evidence'
    owner=$1 unit=$2 status=$3 workspace=$4 branch=$5 commit=$6 pr=$7 evidence=$8
    check_owner "$owner"
    [[ "$unit" =~ ^[a-zA-Z0-9-]+$ ]] || die 'invalid unit id'
    case "$status" in reserved|active|verified|awaiting-review|blocked|failed) :;; *) die 'invalid unit status';; esac
    for value in "$workspace" "$branch" "$commit" "$pr" "$evidence"; do
      [[ "$value" != *$'\n'* ]] || die 'unit fields must be single lines'
    done
    previous_status=$(get "unit.$unit.status" || true)
    if [ "$previous_status" = verified ] || [ "$previous_status" = awaiting-review ]; then
      case "$status" in reserved|active) die 'verified effects cannot restart as new work';; esac
      [ "$(get "unit.$unit.commit")" = "$commit" ] || die 'preserve the verified commit identity'
      [ "$(get "unit.$unit.evidence")" = "$evidence" ] || die 'preserve the verified evidence identity'
    fi
    if [ "$(get run.kind)" = build ]; then
      if [ "$workspace" != - ]; then
        [[ "$workspace" = /* ]] || die 'workspace must be absolute'
        [ "$workspace" != "$(get run.original)" ] || die 'original checkout cannot be a build workspace'
        if [ -d "$workspace" ]; then
          workspace=$(cd "$workspace" && pwd -P)
          [ "$workspace" != "$(get run.original)" ] || die 'original checkout cannot be a build workspace'
        fi
        [ "$branch" != - ] || die 'build workspace needs an owned branch'
        git check-ref-format --branch "$branch" >/dev/null || die 'invalid branch'
      fi
      while read -r field value; do
        [[ "$field" = "unit.$unit."* ]] && continue
        case "$field" in
          *.workspace) [ "$workspace" = - ] || [ "$value" != "$workspace" ] || die 'workspace already belongs to another unit';;
          *.branch) [ "$branch" = - ] || [ "$value" != "$branch" ] || die 'branch already belongs to another unit';;
        esac
      done < <(git config --no-includes --file "$state" --get-regexp '^unit\..*\.(workspace|branch)$' || true)
      old_workspace=$(get "unit.$unit.workspace" || true)
      old_branch=$(get "unit.$unit.branch" || true)
      [ -z "$old_workspace" ] || [ "$old_workspace" = - ] || [ "$old_workspace" = "$workspace" ] || die 'preserve the existing owned workspace'
      [ -z "$old_branch" ] || [ "$old_branch" = - ] || [ "$old_branch" = "$branch" ] || die 'preserve the existing owned branch'
    fi
    if [ "$status" = verified ] || [ "$status" = awaiting-review ]; then
      [ "$evidence" != - ] && [ -s "$evidence" ] || die 'verified work needs a nonempty evidence file'
      if [ "$(get run.kind)" = build ]; then
        [ "$commit" != - ] && [ "$workspace" != - ] || die 'verified build needs workspace and commit'
        [ "$(git -C "$workspace" rev-parse --path-format=absolute --git-common-dir)" = "$common" ] || die 'workspace belongs to another repository'
        [ "$(git -C "$workspace" branch --show-current)" = "$branch" ] || die 'owned workspace branch changed'
        git -C "$workspace" cat-file -e "$commit^{commit}" || die 'recorded commit is missing'
        git -C "$workspace" merge-base --is-ancestor "$commit" HEAD || die 'recorded commit is not in workspace history'
      fi
      [ "$status" != awaiting-review ] || [ "$pr" != - ] || die 'awaiting review needs a PR identity'
    fi
    temporary=$(mktemp "$directory/update.XXXXXX")
    cat "$state" > "$temporary"
    write "unit.$unit.status" "$status"
    write "unit.$unit.workspace" "$workspace"
    write "unit.$unit.branch" "$branch"
    write "unit.$unit.commit" "$commit"
    write "unit.$unit.pr" "$pr"
    write "unit.$unit.evidence" "$evidence"
    mv "$temporary" "$state"
    temporary=''

    ;;
  stop)
    [ $# -eq 2 ] || die 'stop needs coordinator and reason'
    check_owner "$1"
    temporary=$(mktemp "$directory/update.XXXXXX")
    cat "$state" > "$temporary"
    write run.stop-reason "$2"
    mv "$temporary" "$state"
    temporary=''
    rm "$lock/owner"
    rmdir "$lock"
    ;;
  *) die "unknown command: $command";;
esac
