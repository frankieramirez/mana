#!/usr/bin/env bash
# Offline regression fixtures for native and body-backed frontier blockers.
set -euo pipefail
ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
MAP="$ROOT/skills/scry/scripts/map.sh"
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT

cat > "$TMP/gh" <<'GH'
#!/usr/bin/env bash
set -eu
mode=${GH_FIXTURE_MODE:?}
printf '%s\n' "$*" >> "$GH_FIXTURE_LOG"
jq_expr="" previous="" n=""
for arg in "$@"; do
  [[ "$previous" != --jq ]] || jq_expr="$arg"
  [[ ! "$arg" =~ ^[0-9]+$ ]] || n="$arg"
  previous="$arg"
done
if [[ "$1" == api ]]; then
  if [[ "$*" == *'/sub_issues'* ]]; then echo 101
  elif [[ "$*" == *'/dependencies/blocked_by'* ]]; then
    case "$mode" in
      unsupported_open|unsupported_closed) echo 'HTTP 404' >&2; exit 1 ;;
      gone) echo 'HTTP 410' >&2; exit 1 ;;
      native_error) echo 'HTTP 500' >&2; exit 1 ;;
      native_denied) echo 'HTTP 403' >&2; exit 1 ;;
    esac
    # Also answer the old count query, so the original bug fails behaviorally.
    if [[ "$jq_expr" == *'| length'* ]]; then
      [[ "$mode" == native_open ]] && echo 1 || echo 0
    else
      case "$mode" in
        native_open) echo open ;;
        mixed|all_closed) echo closed ;;
        native_unknown) echo UNKNOWN ;;
        native_missing_state) echo null ;;
        paginated)
          echo closed
          [[ " $* " != *' --paginate '* ]] || echo open ;;
      esac
    fi
  elif [[ " $* " == *' repos/acme/widgets/issues/101 '* ]]; then echo task
  else echo "unexpected API: $*" >&2; exit 1
  fi
elif [[ "$1" == issue && "$2" == view ]]; then
  case "$n:$jq_expr" in
    101:.state) echo OPEN ;;
    '101:.assignees | length') echo 0 ;;
    101:.title) echo 'Ready candidate' ;;
    101:.url) echo 'https://github.com/acme/widgets/issues/101' ;;
    101:.body)
      case "$mode" in
        body_error) echo 'HTTP 500' >&2; exit 1 ;;
        body_open|mixed|unsupported_open|body_unreadable|body_unknown|body_missing) echo 'Blocked by: #201' ;;
        all_closed|unsupported_closed) printf 'Blocked by: #201, #202\r\n' ;;
        multi_line) printf 'Blocked by: #202\n\nPart of #100\n\nBlocked by: #201\n' ;;
        deep_line) printf '\n\n\n\n\n\n\n\nBlocked by: #201\n' ;;
        malformed) echo 'Blocked by: acme/other#201' ;;
        *) echo 'Part of #100' ;;
      esac ;;
    201:.state)
      case "$mode" in
        body_unreadable) echo 'HTTP 500' >&2; exit 1 ;;
        body_unknown) echo UNKNOWN ;;
        body_missing) : ;;
        all_closed|unsupported_closed) echo CLOSED ;;
        *) echo OPEN ;;
      esac ;;
    202:.state) echo CLOSED ;;
    *) echo "unexpected issue read: $*" >&2; exit 1 ;;
  esac
else echo "unexpected command: $*" >&2; exit 1
fi
GH
chmod +x "$TMP/gh"

fail=0
run_case() {
  local name=$1 mode=$2 expected=$3 diagnostic=${4:-}
  local out ec=0
  : > "$TMP/log"
  out=$(GH_FIXTURE_MODE="$mode" GH_FIXTURE_LOG="$TMP/log" PATH="$TMP:$PATH" bash "$MAP" frontier 100 acme/widgets 2>"$TMP/err") || ec=$?
  local ok=1
  case "$expected" in
    ready) [[ "$ec" == 0 && "$out" == $'101\tReady candidate\ttask\thttps://github.com/acme/widgets/issues/101' ]] || ok=0 ;;
    blocked) [[ "$ec" == 0 && -z "$out" ]] || ok=0 ;;
    unknown) [[ "$ec" != 0 && -z "$out" ]] || ok=0 ;;
  esac
  [[ -z "$diagnostic" ]] || grep -qF "$diagnostic" "$TMP/err" || ok=0
  if [[ "$mode" == all_closed || "$mode" == unsupported_closed ]]; then
    grep -qF ' 201 --json state ' "$TMP/log" || ok=0
    grep -qF ' 202 --json state ' "$TMP/log" || ok=0
  fi
  if [[ "$ok" == 1 ]]; then echo "ok $name"
  else printf 'FAIL %s (exit=%s output=%s)\n' "$name" "$ec" "$out" >&2; cat "$TMP/err" >&2; fail=1
  fi
}

run_case 'native empty still honors open body blocker' body_open blocked
run_case 'closed native and open body blocker combine' mixed blocked
run_case 'open native blocker blocks' native_open blocked
run_case 'all successfully read blockers closed permits progress' all_closed ready
run_case 'no blockers permits progress' no_blockers ready
run_case 'later native dependency page blocks' paginated blocked
run_case 'multiple body blocker lines combine' multi_line blocked
run_case 'older body blocker beyond eight lines blocks' deep_line blocked
run_case 'unsupported native API honors open fallback' unsupported_open blocked
run_case 'unsupported native API permits closed fallback' unsupported_closed ready
run_case 'removed native API permits empty fallback' gone ready
run_case 'transient native failure is unknown' native_error unknown 'cannot read native blockers for #101'
run_case 'native permission failure is unknown' native_denied unknown 'cannot read native blockers for #101'
run_case 'unknown native state is unknown' native_unknown unknown 'unknown native blocker state for #101'
run_case 'missing native state is unknown' native_missing_state unknown 'unknown native blocker state for #101'
run_case 'unreadable child body is unknown' body_error unknown 'cannot read blocker body for #101'
run_case 'unreadable body blocker is unknown' body_unreadable unknown 'cannot read blocker #201 for #101'
run_case 'unknown body blocker state is unknown' body_unknown unknown 'unknown state for blocker #201 of #101'
run_case 'missing body blocker state is unknown' body_missing unknown 'unknown state for blocker #201 of #101'
run_case 'unsupported body dependency syntax is unknown' malformed unknown 'cannot parse blocker line for #101'
[[ "$fail" == 0 ]]
