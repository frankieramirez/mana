#!/usr/bin/env bash
# Exercise prepare-pr against real local repositories and worktrees.
set -euo pipefail

repo=$(cd "$(dirname "$0")/.." && pwd)
helper=$repo/skills/mend/scripts/prepare-pr.sh
real_git=$(command -v git)
root=$(mktemp -d)
trap 'rm -rf "$root"' EXIT
unset GIT_DIR GIT_WORK_TREE GIT_COMMON_DIR GIT_INDEX_FILE GIT_CONFIG_PARAMETERS GIT_CONFIG_COUNT
export GIT_CONFIG_GLOBAL=$root/gitconfig GIT_CONFIG_NOSYSTEM=1
export GIT_AUTHOR_NAME=Test GIT_AUTHOR_EMAIL=test@example.invalid
export GIT_COMMITTER_NAME=Test GIT_COMMITTER_EMAIL=test@example.invalid
export GIT_TERMINAL_PROMPT=0
mkdir -p "$root/bin"
export PATH=$root/bin:$PATH REAL_GIT=$real_git

cat > "$root/bin/gh" <<'GH'
#!/usr/bin/env bash
set -euo pipefail
if [[ $1 == pr && $2 == view ]]; then
  printf '%s\t%s\t%s\t%s\t%s\n' "${PR_STATE:-OPEN}" "${PR_BASE:-main}" "${PR_HEAD:-pr}" "${PR_FORK:-false}" "${PR_URL:-https://github.com/example/repo/pull/1}"
elif [[ $1 == repo && $2 == view ]]; then
  if [[ $3 == "$FIX_ORIGIN" ]]; then
    printf '%s\n' 'https://github.com/example/repo'
  else
    printf '%s\n' 'https://github.com/other/repo'
  fi
else
  exit 2
fi
GH
cat > "$root/bin/git" <<'GIT'
#!/usr/bin/env bash
if [[ $1 == fetch && -n ${FETCH_LOG:-} ]]; then
  printf '%s\n' "$*" >> "$FETCH_LOG"
fi
if [[ ${INJECT_SWITCH_FAIL:-0} == 1 && $1 == switch ]]; then
  printf 'injected switch failure\n' >&2
  exit 19
fi
if [[ ${INJECT_FF_FAIL:-0} == 1 && $1 == merge && ${2:-} == --ff-only ]]; then
  printf 'injected fast-forward failure\n' >&2
  exit 21
fi
if [[ ${INJECT_BASE_FETCH_FAIL:-0} == 1 && $1 == fetch && " $* " == *" +refs/heads/main:refs/remotes/origin/main "* ]]; then
  printf 'injected base fetch failure\n' >&2
  exit 20
fi
exec "$REAL_GIT" "$@"
GIT
chmod +x "$root/bin/gh" "$root/bin/git"

die() { printf 'FAIL: %s\nstdout: %s\nstderr: %s\n' "$*" "${out:-}" "${err:-}" >&2; exit 1; }
has() { [[ $1 == *"$2"* ]] || die "expected [$2] in [$1]"; }
lacks() { [[ $1 != *"$2"* ]] || die "unexpected [$2] in [$1]"; }
run() {
  local rc=0
  out=$("$@" 2> "$root/stderr") || rc=$?
  err=$(cat "$root/stderr")
  status=$rc
}
ok() { [[ $status == 0 ]] || die "expected success (status $status)"; }
stops() { [[ $status != 0 ]] || die 'expected stop'; }
value() { sed -n "s/^$1=//p" <<< "$out"; }
expect_value() { [[ $(value "$1") == "$2" ]] || die "$1 expected [$2], got [$(value "$1")]"; }
say() { printf 'ok: %s\n' "$1"; }

setup() {
  local name=$1
  case_dir=$root/$name
  mkdir -p "$case_dir"
  export FIX_ORIGIN=$case_dir/origin.git
  "$real_git" init --bare -q "$FIX_ORIGIN"
  "$real_git" init -q -b main "$case_dir/seed"
  printf 'base\n' > "$case_dir/seed/base.txt"
  "$real_git" -C "$case_dir/seed" add base.txt
  "$real_git" -C "$case_dir/seed" commit -qm base
  "$real_git" -C "$case_dir/seed" remote add origin "$FIX_ORIGIN"
  "$real_git" -C "$case_dir/seed" push -q origin main
  "$real_git" --git-dir="$FIX_ORIGIN" symbolic-ref HEAD refs/heads/main
  "$real_git" -C "$case_dir/seed" switch -qc pr
  printf 'pr\n' > "$case_dir/seed/pr.txt"
  "$real_git" -C "$case_dir/seed" add pr.txt
  "$real_git" -C "$case_dir/seed" commit -qm pr
  "$real_git" -C "$case_dir/seed" push -q origin pr
  "$real_git" clone -q "$FIX_ORIGIN" "$case_dir/work"
  work=$case_dir/work
  unset PR_STATE PR_BASE PR_HEAD PR_FORK PR_URL INJECT_SWITCH_FAIL INJECT_FF_FAIL INJECT_BASE_FETCH_FAIL FETCH_LOG || true
  out= err= status=0
}
prepare() { (cd "$work" && "$helper" 1); }
head_sha() { "$real_git" --git-dir="$FIX_ORIGIN" rev-parse "refs/heads/$1"; }
complete_merge_push() {
  (cd "$work" && "$real_git" merge --no-edit "$(value base_ref)" >/dev/null && "$real_git" push -q origin "HEAD:$(value push_ref)")
}

setup missing
# The normal fetch refspec intentionally covers main only.
"$real_git" -C "$work" config remote.origin.fetch '+refs/heads/main:refs/remotes/origin/main'
"$real_git" -C "$work" update-ref -d refs/remotes/origin/pr
if "$real_git" -C "$work" show-ref --verify --quiet refs/remotes/origin/pr; then die 'test setup retained origin/pr'; fi
run prepare; ok
expect_value start main; expect_value head pr; expect_value mode created
expect_value base_ref refs/remotes/origin/main; expect_value push_ref refs/heads/pr
[[ $("$real_git" -C "$work" branch --show-current) == pr ]] || die 'missing branch was not created'
printf 'main update\n' >> "$case_dir/seed/base.txt"
"$real_git" -C "$case_dir/seed" switch -q main
"$real_git" -C "$case_dir/seed" commit -qam main-update
"$real_git" -C "$case_dir/seed" push -q origin main
# Refresh base through the real helper before merging and pushing.
run prepare; ok
complete_merge_push
[[ $(head_sha pr) == $("$real_git" -C "$work" rev-parse HEAD) ]] || die 'explicit push missed PR head'
say 'missing branch with main-only fetch mapping, merge, explicit push'

setup stale
"$real_git" -C "$work" fetch -q origin pr
"$real_git" -C "$work" switch -q --track origin/pr
"$real_git" -C "$work" switch -q main
"$real_git" -C "$case_dir/seed" switch -q pr
printf 'later\n' >> "$case_dir/seed/pr.txt"
"$real_git" -C "$case_dir/seed" commit -qam later
"$real_git" -C "$case_dir/seed" push -q origin pr
"$real_git" -C "$work" config remote.origin.fetch '+refs/heads/main:refs/remotes/origin/main'
run prepare; ok
expect_value mode existing
[[ $("$real_git" -C "$work" rev-parse HEAD) == $(head_sha pr) ]] || die 'existing branch did not fast-forward to fresh remote head'
say 'stale tracking head refresh and existing branch fast-forward'

for peer_upstream in absent wrong; do
  setup "peer_$peer_upstream"
  "$real_git" -C "$work" fetch -q origin pr
  "$real_git" -C "$work" worktree add -q -b pr "$case_dir/peer" origin/pr
  if [[ $peer_upstream == absent ]]; then
    "$real_git" -C "$work" config --unset branch.pr.remote || true
    "$real_git" -C "$work" config --unset branch.pr.merge || true
  else
    "$real_git" -C "$work" config branch.pr.remote unrelated
    "$real_git" -C "$work" config branch.pr.merge refs/heads/wrong
  fi
  "$real_git" -C "$work" update-ref -d refs/remotes/origin/pr
  "$real_git" -C "$case_dir/seed" switch -q main
  printf 'base update\n' >> "$case_dir/seed/base.txt"
  "$real_git" -C "$case_dir/seed" commit -qam base-update
  "$real_git" -C "$case_dir/seed" push -q origin main
  old_pr=$(head_sha pr)
  run prepare; ok
  expect_value mode detached; expect_value peer_worktree "$case_dir/peer"
  [[ $(value peer_tip) == "$old_pr" ]] || die 'peer tip was not recorded'
  [[ -z $("$real_git" -C "$work" branch --show-current) ]] || die 'peer path did not detach'
  [[ $("$real_git" -C "$work" rev-parse HEAD) == "$old_pr" ]] || die 'detached at wrong head'
  complete_merge_push
  [[ $(head_sha pr) == $("$real_git" -C "$work" rev-parse HEAD) ]] || die 'detached push missed PR head'
  [[ $(head_sha pr) != "$old_pr" ]] || die 'base merge did not advance PR head'
  # The peer branch must catch up by explicit ref, independent of its upstream.
  "$real_git" -C "$case_dir/peer" pull -q --ff-only origin pr
  [[ $("$real_git" -C "$case_dir/peer" rev-parse HEAD) == $(head_sha pr) ]] || die 'peer did not catch up to pushed PR head'
  say "peer detach, merge, push and explicit sync with $peer_upstream upstream"
done

setup unpushed
"$real_git" -C "$work" fetch -q origin pr
"$real_git" -C "$work" switch -q --track origin/pr
printf 'local\n' >> "$work/pr.txt"
"$real_git" -C "$work" commit -qam local
"$real_git" -C "$work" tag pr refs/remotes/origin/pr
old_count=$("$real_git" -C "$work" rev-list --count origin/pr..pr)
full_count=$("$real_git" -C "$work" rev-list --count refs/remotes/origin/pr..refs/heads/pr)
[[ $old_count == 0 && $full_count == 1 ]] || die "ambiguous setup did not reproduce: old=$old_count full=$full_count"
"$real_git" -C "$work" switch -q main
run prepare; stops; has "$err" 'unpushed commits'
[[ $("$real_git" -C "$work" branch --show-current) == main ]] || die 'unpushed stop switched branch'
say 'unpushed branch and same-named tag stop'

setup dirty
printf 'dirty\n' >> "$work/base.txt"
run prepare; stops; has "$err" 'dirty checkout'
say 'dirty checkout stop'

for kind in closed merged fork wrongpr wrongpush; do
  setup "$kind"
  case $kind in
    closed) export PR_STATE=CLOSED ;;
    merged) export PR_STATE=MERGED ;;
    fork) export PR_FORK=true ;;
    wrongpr) export PR_URL=https://github.com/other/repo/pull/1 ;;
    wrongpush) "$real_git" -C "$work" remote set-url --push origin "$case_dir/foreign.git" ;;
  esac
  export FETCH_LOG=$case_dir/fetch.log
  run prepare; stops
  [[ $("$real_git" -C "$work" branch --show-current) == main ]] || die "$kind switched branch"
  [[ ! -e $FETCH_LOG ]] || die "$kind fetched before stopping"
  say "$kind stops before fetch or switch"
done

# These are valid refnames. Pass them as data through the real helper.
special_index=0
for branch in 'semi;colon' "apost'rophe" 'sub$(touch${IFS}marker)' 'double"quote'; do
  special_index=$((special_index + 1))
  setup "special$special_index"
  "$real_git" -C "$case_dir/seed" branch "$branch" pr
  "$real_git" -C "$case_dir/seed" push -q origin "refs/heads/$branch:refs/heads/$branch"
  export PR_HEAD=$branch
  run prepare; ok
  expect_value head "$branch"; expect_value push_ref "refs/heads/$branch"
  [[ ! -e "$work/marker" && ! -e "$case_dir/marker" ]] || die 'branch name executed as shell code'
  say "shell-significant branch: $branch"
done

setup current_no_upstream
"$real_git" -C "$work" switch -q -c pr origin/pr
"$real_git" -C "$work" config --unset branch.pr.remote || true
"$real_git" -C "$work" config --unset branch.pr.merge || true
run prepare; ok
expect_value start pr; expect_value mode current; expect_value push_ref refs/heads/pr
[[ $("$real_git" -C "$work" branch --show-current) == pr ]] || die 'already-current head moved'
say 'already-current PR with no upstream'

setup switchfail
export INJECT_SWITCH_FAIL=1
run prepare; stops
has "$err" 'start=main; current=main'
say 'failed switch reports start and current'

setup basefail
export INJECT_BASE_FETCH_FAIL=1
run prepare; stops
has "$err" 'start=main; current=pr'
say 'post-switch base fetch failure reports actual current'

setup fffail
"$real_git" -C "$work" switch -q -c pr origin/pr
"$real_git" -C "$work" switch -q main
export INJECT_FF_FAIL=1
run prepare; stops
has "$err" 'head fast-forward failed'; has "$err" 'start=main; current=pr'
say 'post-switch fast-forward failure reports actual current'

setup dirty_peer
"$real_git" -C "$work" worktree add -q -b pr "$case_dir/peer" origin/pr
printf 'dirty peer\n' >> "$case_dir/peer/pr.txt"
run prepare; stops; has "$err" 'peer worktree is dirty'
[[ $("$real_git" -C "$work" branch --show-current) == main ]] || die 'dirty peer detached checkout'
say 'dirty peer stops before detach'

setup checkpeer
"$real_git" -C "$work" fetch -q origin pr
"$real_git" -C "$work" worktree add -q -b pr "$case_dir/peer" origin/pr
tip=$("$real_git" -C "$work" rev-parse refs/heads/pr)
check() { (cd "$work" && "$helper" --check-peer pr "$case_dir/peer" "$tip"); }
run check; ok; has "$out" 'peer=unchanged'
printf 'local\n' >> "$case_dir/peer/pr.txt"
run check; stops; has "$err" 'dirty'
"$real_git" -C "$case_dir/peer" commit -qam local
run check; stops; has "$err" 'branch changed'
tip=$("$real_git" -C "$work" rev-parse refs/heads/pr)
"$real_git" -C "$case_dir/peer" switch -q --detach
run check; stops; has "$err" 'changed branches'
say 'peer guard catches dirty worktree, concurrent commit, and switched peer'

run "$helper" --help; ok; has "$out" 'Usage: prepare-pr.sh'
run "$helper"; stops; [[ $status == 2 ]] || die 'missing argument did not return usage status'
run "$helper" 1 extra; stops; [[ $status == 2 ]] || die 'extra argument did not return usage status'
run "$helper" --check-peer pr; stops; [[ $status == 2 ]] || die 'incomplete peer check did not return usage status'
say 'help succeeds and invalid arguments reject'

printf 'test-mend: all scenarios passed\n'
