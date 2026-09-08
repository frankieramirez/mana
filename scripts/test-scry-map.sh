#!/usr/bin/env bash
# Regression fixtures for the GitHub-backed map children and close-map commands.
set -euo pipefail

ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
MAP="$ROOT/skills/scry/scripts/map.sh"
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT

cat > "$TMP/gh" <<'GH'
#!/usr/bin/env bash
set -u
mode=${GH_FIXTURE_MODE:?}
log=${GH_FIXTURE_LOG:?}
printf '%s\n' "$*" >> "$log"
jq_expr=""
previous=""
n=""
for arg in "$@"; do
  [[ "$previous" == --jq ]] && jq_expr="$arg"
  [[ "$arg" =~ ^[0-9]+$ ]] && n="$arg"
  previous="$arg"
done

if [[ "$1" == api ]]; then
  [[ " $* " == *" --paginate "* ]] || { echo 'missing pagination' >&2; exit 1; }
  if [[ "$*" == *'/sub_issues'* ]]; then
    case "$mode" in
      native404) echo "HTTP 404" >&2; exit 1 ;;
      native500) echo "HTTP 500" >&2; exit 1 ;;
      mixed) printf '101\n' ;;
      no_children|task_only) : ;;
      *) printf '101\n102\n' ;;
    esac
  elif [[ "$*" == *'issues?state=all&per_page=100'* ]]; then
    case "$mode" in
      fallback_error) echo "HTTP 500" >&2; exit 1 ;;
      no_children|task_only) : ;;
      mixed) printf '102\n' ;;
      *) printf '101\n102\n' ;;
    esac
  else
    echo "unexpected gh api: $*" >&2; exit 1
  fi
  exit 0
fi

if [[ "$1" == issue && "$2" == view ]]; then
  if [[ "$n" == 7 && "$jq_expr" == .body ]]; then
    case "$mode" in
      body_read_error) echo 'HTTP 500' >&2; exit 1 ;;
      body_stale) printf 'changed body\n' ;;
      *) printf 'same body\n' ;;
    esac
    exit 0
  fi
  if [[ "$n" == 100 ]]; then
    case "$jq_expr" in
      '.labels[].name')
        case "$mode" in
          nonmap) echo scry:task ;;
          legacy) echo wayfinder:map ;;
          *) echo scry:map ;;
        esac ;;
      .state) [[ "$mode" == parent_closed ]] && echo CLOSED || echo OPEN ;;
      .body)
        [[ "$mode" == map_read_error ]] && { echo 'HTTP 500' >&2; exit 1; }
        [[ "$mode" == task_only ]] && printf '%s\n' '- [ ] #102' || printf '%s\n' '## Destination' ;;
      *) echo "unexpected map read: $*" >&2; exit 1 ;;
    esac
  else
    [[ "$n" == 101 || "$n" == 102 ]] || { echo "unexpected child: $n" >&2; exit 1; }
    [[ "$mode" == read_error && "$n" == 102 ]] && { echo 'HTTP 500' >&2; exit 1; }
    [[ "$mode" == missing_child && "$n" == 102 ]] && exit 0
    state=CLOSED
    case "$mode:$n" in
      assigned:101|blocked:101|mixed:102|task_only:102) state=OPEN ;;
      unknown:102) state=UNKNOWN ;;
    esac
    [[ "$jq_expr" == *'@tsv'* ]] || { echo "unexpected child read: $*" >&2; exit 1; }
    printf '%s\t%s\tChild %s\thttps://github.com/acme/widgets/issues/%s\n' "$n" "$state" "$n" "$n"
  fi
  exit 0
fi
if [[ "$1" == issue && "$2" == edit && "$n" == 7 ]]; then
  body_file=""
  previous=""
  for arg in "$@"; do
    [[ "$previous" == --body-file ]] && body_file="$arg"
    previous="$arg"
  done
  [[ -n "$body_file" && "$(cat "$body_file")" == "replacement body" ]] || exit 1
  printf 'edited payload:replacement body\n' >> "$log"
  exit 0
fi
if [[ "$1" == issue && "$2" == close && "$n" == 100 ]]; then printf 'closed\n'; exit 0; fi
echo "unexpected gh command: $*" >&2; exit 1

GH
chmod +x "$TMP/gh"

fail=0
run_case() {
  local name=$1 mode=$2 expected_ec=$3 expected_write=$4; shift 4
  local out ec writes
  : > "$TMP/log"
  if out=$(GH_FIXTURE_MODE="$mode" GH_FIXTURE_LOG="$TMP/log" PATH="$TMP:$PATH" "$MAP" "$@" acme/widgets 2>"$TMP/err"); then ec=0; else ec=$?; fi
  writes=$(grep -c 'issue close' "$TMP/log" || true)
  local output_ok=0 expected_children
  expected_children=$'101\tCLOSED\tChild 101\thttps://github.com/acme/widgets/issues/101\n102\tOPEN\tChild 102\thttps://github.com/acme/widgets/issues/102'
  [[ "$mode" == all_closed ]] && expected_children=$'101\tCLOSED\tChild 101\thttps://github.com/acme/widgets/issues/101\n102\tCLOSED\tChild 102\thttps://github.com/acme/widgets/issues/102'
  [[ "$mode" == mixed ]] && expected_children=$'101\tCLOSED\tChild 101\thttps://github.com/acme/widgets/issues/101\n102\tOPEN\tChild 102\thttps://github.com/acme/widgets/issues/102'
  if [[ "$1" == children ]]; then output_ok=1; [[ "$out" == "$expected_children" ]] && output_ok=0; fi
  if [[ "$ec" != "$expected_ec" || "$writes" != "$expected_write" || "$output_ok" -ne 0 ]]; then
    echo "FAIL $name (exit=$ec writes=$writes)" >&2; cat "$TMP/err" >&2; fail=1
  else echo "ok $name"; fi
}

run_case "assigned child refuses close" assigned 1 0 close-map 100
run_case "blocked child refuses close" blocked 1 0 close-map 100
run_case "all closed closes parent" all_closed 0 1 close-map 100
run_case "legacy map label closes parent" legacy 0 1 close-map 100
run_case "native 404 fallback closes parent" native404 0 1 close-map 100
run_case "mixed native fallback refuses open child" mixed 1 0 close-map 100
run_case "native unknown error refuses close" native500 1 0 close-map 100
run_case "child read error refuses close" read_error 1 0 close-map 100
run_case "fallback read failure refuses close" fallback_error 1 0 close-map 100
run_case "map read failure refuses close" map_read_error 1 0 close-map 100
run_case "unknown child state refuses close" unknown 1 0 close-map 100
run_case "missing child response refuses close" missing_child 1 0 close-map 100
run_case "task-list child refuses close" task_only 1 0 close-map 100
run_case "no-child map can close" no_children 0 1 close-map 100
run_case "already closed is idempotent" parent_closed 0 0 close-map 100
run_case "non-map refuses close" nonmap 1 0 close-map 100
run_case "children returns all native children" all_closed 0 0 children 100
run_case "children returns mixed fallback children" mixed 0 0 children 100

run_update_case() {
  local name=$1 mode=$2 expected_ec=$3 expected_write=$4 snapshot=${5:-}
  local out ec writes
  local -a args=(update-body 7)
  [ -n "$snapshot" ] && args+=(--expected-body "$snapshot")
  args+=(acme/widgets)
  : > "$TMP/log"
  if out=$(GH_FIXTURE_MODE="$mode" GH_FIXTURE_LOG="$TMP/log" PATH="$TMP:$PATH" "$MAP" "${args[@]}" 2>"$TMP/err" <<'EOF'
replacement body
EOF
  ); then ec=0; else ec=$?; fi
  writes=$(grep -c 'issue edit' "$TMP/log" || true)
  payload_ok=0
  [[ "$expected_ec" != 0 || "$(grep -c '^edited payload:replacement body$' "$TMP/log" || true)" == 1 ]] && payload_ok=1
  if [[ "$ec" != "$expected_ec" || "$writes" != "$expected_write" || "$payload_ok" != 1 ]]; then
    echo "FAIL $name (exit=$ec writes=$writes)" >&2; cat "$TMP/err" >&2; fail=1
  else echo "ok $name"; fi
}

snapshot="$TMP/body"
printf 'same body\n' > "$snapshot"
run_update_case "update-body accepts unchanged snapshot" body_unchanged 0 1 "$snapshot"
run_update_case "update-body rejects stale snapshot" body_stale 1 0 "$snapshot"
run_update_case "update-body rejects missing snapshot" body_unchanged 1 0 "$TMP/missing"
run_update_case "update-body rejects body read error" body_read_error 1 0 "$snapshot"
run_update_case "update-body keeps old usage" body_unchanged 0 1

body_out=$(GH_FIXTURE_MODE=body_unchanged GH_FIXTURE_LOG="$TMP/log" PATH="$TMP:$PATH" "$MAP" body 7 acme/widgets)
[[ "$body_out" == "same body" ]] || { echo "FAIL body command" >&2; fail=1; }
[[ "$fail" -eq 0 ]]
