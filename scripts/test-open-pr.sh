#!/usr/bin/env bash
# Integration fixtures for open-pr.sh conflict preflight and mergeability checks.
set -euo pipefail

ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
OPEN_PR="$ROOT/skills/reveal/scripts/open-pr.sh"
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT

git init --bare "$TMP/origin.git" >/dev/null
git clone -q "$TMP/origin.git" "$TMP/repo"
git -C "$TMP/repo" config user.email test@example.invalid
git -C "$TMP/repo" config user.name Fixture
printf 'base\n' > "$TMP/repo/file"
git -C "$TMP/repo" add file
git -C "$TMP/repo" commit -qm initial
git -C "$TMP/repo" branch -M main
git -C "$TMP/repo" push -q -u origin main
git -C "$TMP/repo" branch develop main
git -C "$TMP/repo" push -q origin develop
git -C "$TMP/repo" checkout -qb feature
printf 'feature\n' > "$TMP/repo/file"
git -C "$TMP/repo" add file
git -C "$TMP/repo" commit -qm feature

cat > "$TMP/gh" <<'GH'
#!/usr/bin/env bash
set -u
log=${GH_FIXTURE_LOG:?}
printf '%s\n' "$*" >> "$log"
if [[ "$1" == --version ]]; then echo 'gh version 2.99.0'; exit 0; fi
if [[ "$1" == auth ]]; then echo 'ghp_fixture'; exit 0; fi
if [[ "$1" == repo && "$2" == view ]]; then
  [[ "$*" == *defaultBranchRef* ]] && echo main || {
    [[ ${GH_FIXTURE_FETCH_FAIL:-0} == 1 ]] && echo /missing/repository || echo "${GH_FIXTURE_REPO_URL:?}"
  }
  exit 0
fi
if [[ "$1" == pr && "$2" == list ]]; then
  jq=''; prev=''; for a in "$@"; do [[ "$prev" == --jq ]] && jq=$a; prev=$a; done
  [[ ${GH_FIXTURE_EXISTS:-0} == 1 ]] || exit 0
  printf '7\thttps://github.com/acme/widgets/pull/7\t%s\tfeature\tfalse\n' "${GH_FIXTURE_BASE:-main}"
  exit 0
fi
if [[ "$1" == pr && "$2" == view ]]; then
  jq=''; prev=''; for a in "$@"; do [[ "$prev" == --jq ]] && jq=$a; prev=$a; done
  [[ "$jq" == *url* ]] && { echo https://github.com/acme/widgets/pull/7; exit 0; }
  [[ "$jq" == *number* ]] && { echo 7; exit 0; }
  n=$(cat "${GH_FIXTURE_COUNT:?}" 2>/dev/null || echo 0); n=$((n + 1))
  printf '%s' "$n" > "${GH_FIXTURE_COUNT:?}"
  case ${GH_FIXTURE_MERGEABLE:-clean}:$n in
    read-failure:*) exit 1 ;;
    head-mismatch:*) printf 'MERGEABLE\tother-head\tmain\n' ;;
    unknown:*) printf 'UNKNOWN\t%s\t%s\n' "$(git -C "$GH_FIXTURE_REPO" rev-parse HEAD)" "${GH_FIXTURE_BASE:-main}" ;;
    retry:1|retry:2) printf 'UNKNOWN\t%s\t%s\n' "$(git -C "$GH_FIXTURE_REPO" rev-parse HEAD)" "${GH_FIXTURE_BASE:-main}" ;;
    conflicting:*) printf 'CONFLICTING\t%s\t%s\n' "$(git -C "$GH_FIXTURE_REPO" rev-parse HEAD)" "${GH_FIXTURE_BASE:-main}" ;;
    *) printf 'MERGEABLE\t%s\t%s\n' "$(git -C "$GH_FIXTURE_REPO" rev-parse HEAD)" "${GH_FIXTURE_BASE:-main}" ;;
  esac
  exit 0
fi
if [[ "$1" == pr && ( "$2" == create || "$2" == edit ) ]]; then
  echo "WRITE $*" >> "$log"
  [[ "$2" == create ]] && echo https://github.com/acme/widgets/pull/7
  exit 0
fi
echo "unexpected gh command: $*" >&2
exit 1
GH
chmod +x "$TMP/gh"
printf '#!/usr/bin/env bash\nexit 0\n' > "$TMP/sleep"
chmod +x "$TMP/sleep"
printf 'body\n' > "$TMP/body"
printf '\0' > "$TMP/proof.png"

run_open() {
  local mode=$1 expected=$2; shift 2
  local out ec
  : > "$TMP/log"; rm -f "$TMP/count"
  if out=$(cd "$TMP/repo" && GH_FIXTURE_LOG="$TMP/log" GH_FIXTURE_COUNT="$TMP/count" GH_FIXTURE_REPO="$TMP/repo" GH_FIXTURE_REPO_URL="$TMP/origin.git" GH_FIXTURE_EXISTS="${GH_FIXTURE_EXISTS:-0}" GH_FIXTURE_BASE="${GH_FIXTURE_BASE:-main}" GH_FIXTURE_MERGEABLE="${GH_FIXTURE_MERGEABLE:-clean}" GH_FIXTURE_FETCH_FAIL="${GH_FIXTURE_FETCH_FAIL:-0}" PATH="$TMP:$PATH" "$OPEN_PR" "$@" 2>"$TMP/err"); then ec=0; else ec=$?; fi
  [[ "$ec" == "$expected" ]] || { echo "FAIL $mode: exit $ec expected $expected" >&2; cat "$TMP/err" >&2; return 1; }
  printf '%s\n' "$out"
}

before=$(git -C "$TMP/repo" status --porcelain=v1)
sha=$(git -C "$TMP/repo" rev-parse HEAD)
out=$(run_open clean-check 0 --check)
[[ "$(git -C "$TMP/repo" status --porcelain=v1)" == "$before" ]]
[[ "$out" == *$'base\tmain'* && "$out" == *$'head_sha\t'"$sha"* && "$out" == *$'preflight\tclean'* ]]
run_open clean-create 0 --title title --body-file "$TMP/body" --attach "$TMP/proof.png" >/dev/null
grep -q -- 'pr create --base main' "$TMP/log"

git -C "$TMP/repo" checkout -q main
printf 'main change\n' > "$TMP/repo/file"
git -C "$TMP/repo" commit -qam main-change
git -C "$TMP/repo" push -q origin main
git -C "$TMP/repo" checkout -q feature
GH_FIXTURE_EXISTS=0 GH_FIXTURE_BASE=main run_open conflict 4 --title title --body-file "$TMP/body" --attach "$TMP/proof.png"
! grep -q '^WRITE ' "$TMP/log"
[[ -z "$(git -C "$TMP/repo" status --porcelain=v1)" ]]
[[ "$(git -C "$TMP/repo" rev-parse HEAD)" == "$sha" ]]
GH_FIXTURE_EXISTS=0 GH_FIXTURE_BASE=main run_open draft 0 --draft --title title --body-file "$TMP/body" --attach "$TMP/proof.png"
grep -q -- '--draft' "$TMP/log"

GH_FIXTURE_EXISTS=1 GH_FIXTURE_BASE=main run_open existing 0 --draft --base main --title title --body-file "$TMP/body" --attach "$TMP/proof.png"
grep -q '^WRITE .*pr edit' "$TMP/log"
! grep -q -- '--draft' "$TMP/log"
GH_FIXTURE_EXISTS=1 GH_FIXTURE_BASE=develop run_open existing-base 0 --title title --body-file "$TMP/body" --attach "$TMP/proof.png" >/dev/null
GH_FIXTURE_EXISTS=1 GH_FIXTURE_BASE=main run_open mismatched-base 1 --check --base develop >/dev/null
! grep -q '^WRITE ' "$TMP/log"

export GH_FIXTURE_EXISTS=0 GH_FIXTURE_MERGEABLE=retry
run_open post-retry 0 --draft --title title --body-file "$TMP/body" --attach "$TMP/proof.png"
[[ $(cat "$TMP/count") == 3 ]]
export GH_FIXTURE_MERGEABLE=unknown
run_open post-unknown 5 --draft --title title --body-file "$TMP/body" --attach "$TMP/proof.png"
[[ $(cat "$TMP/count") == 3 ]]
export GH_FIXTURE_MERGEABLE=conflicting
run_open post-conflict 4 --draft --title title --body-file "$TMP/body" --attach "$TMP/proof.png"
for mode in read-failure head-mismatch; do
  export GH_FIXTURE_MERGEABLE=$mode
  out=$(run_open "$mode" 5 --draft --title title --body-file "$TMP/body" --attach "$TMP/proof.png")
  [[ "$out" == *$'mergeability\tunknown'* && "$out" == *$'url\thttps://github.com/acme/widgets/pull/7'* ]]
  [[ $(cat "$TMP/count") == 3 ]]
done
export GH_FIXTURE_FETCH_FAIL=0 GH_FIXTURE_MERGEABLE=clean
GH_FIXTURE_EXISTS=0 GH_FIXTURE_BASE=main run_open dry-run 4 --dry-run --title title --body-file "$TMP/body" --attach "$TMP/proof.png"
! grep -q '^WRITE ' "$TMP/log"
export GH_FIXTURE_FETCH_FAIL=1
run_open fetch-failure 1 --check

echo 'open-pr integration fixtures: ok'
