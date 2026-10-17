#!/usr/bin/env bash
# Exercise the shell dispatcher and GitHub adapter against an offline transport.
set -euo pipefail
root=$(cd "$(dirname "$0")/.." && pwd)
tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT
export GH_FIXTURE="$tmp" PATH="$tmp:$PATH"
cat > "$tmp/gh" <<'MOCK'
#!/usr/bin/env python3
import json, os, re, sys
from pathlib import Path
root = Path(os.environ['GH_FIXTURE'])
state_path = root / 'state.json'
state = json.loads(state_path.read_text())
a = sys.argv[1:]
def option(name, default=''):
    return a[a.index(name)+1] if name in a else default
def fail(message):
    print(message, file=sys.stderr); sys.exit(1)
def issue(n):
    if os.environ.get('READ_FAIL') == n: fail('HTTP 500 read failed')
    if n not in state: fail('HTTP 404 Not Found')
    return state[n]
def save(kind):
    state_path.write_text(json.dumps(state))
    with (root/'mutations').open('a') as f: f.write(kind+'\n')
def row(n, fields):
    d=issue(n)
    values={'number':n, 'state':d['state'], 'title':d['title'], 'url':d['url'], 'body':d['body']}
    print('\t'.join(values[f] for f in fields))
q=option('--jq')
if a[:2] == ['issue','view']:
    n=next(x for x in a[2:] if x.isdigit())
    d=issue(n)
    if q=='.body' and os.environ.get('BODY_FAIL')==n: fail('HTTP 500 body read failed')
    if q=='.body': print(d['body'])
    elif q=='.state': print(d['state'])
    elif q=='.labels[].name': print('ready')
    elif q=='.assignees[].login': print('fixture')
    elif q=='[.assignees[].login] | join(",")': print(','.join(d.get('assignees',[])))
    elif q=='[.number,.title,.url,.state] | @tsv': row(n,['number','title','url','state'])
    elif q=='[.number,.state,.title,.url] | @tsv': row(n,['number','state','title','url'])
    elif 'map(select' in q: print('')
    else: fail('unexpected view query: '+q)
elif a[:2] == ['issue','edit']:
    n=next(x for x in a[2:] if x.isdigit())
    issue(n)
    if '--body-file' in a: state[n]['body']=Path(option('--body-file')).read_text().rstrip('\n')
    if '--remove-assignee' in a:
        gone=option('--remove-assignee').split(',')
        state[n]['assignees']=[x for x in state[n].get('assignees',[]) if x not in gone]
    if '--add-assignee' in a:
        state[n]['assignees']=[option('--add-assignee')]
        state[n]['after_claim']=True
        if os.environ.get('BODY_AFTER_CLAIM'):
            state[n]['body']=os.environ['BODY_AFTER_CLAIM']
    save('edit '+n)
elif a[:2] == ['issue','reopen']:
    n=next(x for x in a[2:] if x.isdigit())
    issue(n)['state']='OPEN'
    save('reopen '+n)
elif a[0]=='api':
    endpoint=next((x for x in a[1:] if x.startswith('repos/') or x=='user'), '')
    if endpoint=='user': print('fixture'); sys.exit()
    match=re.search(r'issues/(\d+)',endpoint)
    n=match.group(1) if match else None
    method=option('--method','GET')
    if endpoint.endswith('/parent'):
        d=issue(n)
        if os.environ.get('PARENT_FAIL'): fail('HTTP 500 parent lookup failed')
        if not d.get('parent'): fail('HTTP 404 Not Found')
        row(d['parent'], ['number','url'])
    elif endpoint.endswith('/sub_issues'):
        issue(n)
        mode=os.environ.get('NATIVE','ok')
        if mode=='404': fail('HTTP 404 Not Found')
        if mode=='403': fail('HTTP 403 Forbidden')
        if mode=='fail': fail('HTTP 500 second page failed')
        if method=='POST':
            field=next(x for x in a if x.startswith('sub_issue_id='))
            child=str(int(field.split('=')[1])-100)
            if issue(child).get('parent') not in (None,n): fail('HTTP 422 parent exists')
            state[child]['parent']=n; save('attach '+child)
        else:
            assert '--paginate' in a
            for k,d in state.items():
                if d.get('parent')==n: print(k)
    elif endpoint.endswith('/dependencies/blocked_by'):
        mode=os.environ.get('DEPS','ok')
        if issue(n).get('after_claim') and os.environ.get('DEPS_AFTER_CLAIM'):
            mode=os.environ['DEPS_AFTER_CLAIM']
        if mode in ('404','410'): fail('HTTP '+mode+' Not Found')
        if mode=='fail': fail('HTTP 500 dependency read failed')
        ids=issue(n).get('blocked_by',[])
        open_ids=[k for k in ids if issue(k)['state']=='OPEN']
        if 'length' in q: print(len(open_ids))
        elif '@tsv' in q:
            assert '--paginate' in a
            for k in ids: print(k+'\t'+issue(k)['state'])
        elif '.number' in q: print('\n'.join(open_ids))
        else: fail('unexpected blocked_by query: '+q)
    elif n:
        issue(n)
        assert q=='.id', q
        print(int(n)+100)
    elif 'state=all' in endpoint:
        assert '--paginate' in a
        if os.environ.get('SCAN_FAIL'): fail('HTTP 500 scan page failed')
        if 'contains(' in q:
            match=re.search(r'contains\(("(?:[^"\\]|\\.)*")\)',q)
            assert match, q
            needle=json.loads(match.group(1))
            for k,d in state.items():
                if needle in d['body']: row(k,['number','state','title','url'])
        elif 'Build parent:' in q:
            assert 'split("\\n")' in q, q
            for k,d in state.items():
                if re.search(r'^Build parent: \[.*\]\(https://github.com/acme/widgets/issues/1\)$',d['body'].replace('\r',''),re.M): print(k)
        else: fail('unexpected all-state query: '+q)
    elif endpoint.endswith('/issues'):
        assert '--paginate' in a and 'Work kind: build' in q
        # Include the parent to also test the fresh per-candidate marker check.
        for k in os.environ.get('NEXT_IDS','1,2').split(','):
            d=issue(k); print(f"2026-01-0{k}\t{k}\t{d['title']}\t{d['url']}")
    else: fail('unexpected api: '+str(a))
else: fail('unexpected gh command: '+str(a))
MOCK
chmod +x "$tmp/gh"
python3 - <<'PY'
import json,os
from pathlib import Path
state={str(n):{'title':f'Issue {n}','url':f'https://github.com/acme/widgets/issues/{n}',
 'state':'OPEN','body':'Slice literal [x].','parent':None} for n in range(1,8)}
# Bodies edited in the GitHub web UI come back with CRLF; the parent and issue 7 carry it.
state['1']['body']='Work kind: build\r\n\r\n## Destination\r\nDeliver the feature'
state['3'].update(state='CLOSED',assignees=['fixture'],body='Build parent: [Build](https://github.com/acme/widgets/issues/1)')
state['6'].update(parent='5')
state['7']['body']='Build parent: [Build](https://github.com/acme/widgets/issues/1)\r\n\r\nSlice literal [x].'
state['5']['body']='Blocked by: #2, #3\r\n\r\nSlice literal [x].'
state['6']['blocked_by']=['2','3']
Path(os.environ['GH_FIXTURE'],'state.json').write_text(json.dumps(state))
PY
run() { bash "$root/skills/sift/scripts/tickets.sh" --repo acme/widgets "$@"; }
expect_fail() { if "$@" > "$tmp/out" 2> "$tmp/err"; then echo "unexpected success: $*" >&2; exit 1; fi; }
run body 1 > "$tmp/snapshot"
! grep -q $'\r' "$tmp/snapshot"
printf 'Work kind: build\r\n\r\n## Destination\r\nDeliver the feature\r\n' | run update-body 1 --expected-body "$tmp/snapshot"
printf 'stale\n' > "$tmp/stale"
expect_fail run update-body 1 --expected-body "$tmp/stale" <<< replacement
grep -q 'differs' "$tmp/err"
expect_fail run update-body 1 --expected-body "$tmp/missing" <<< replacement
READ_FAIL=1 expect_fail run update-body 1 --expected-body "$tmp/snapshot" <<< replacement
run attach 2 1
before=$(wc -l < "$tmp/mutations")
run attach 2 1
[ "$(wc -l < "$tmp/mutations")" -eq "$before" ]
expect_fail run attach 6 1
[ "$(wc -l < "$tmp/mutations")" -eq "$before" ]
PARENT_FAIL=1 expect_fail run attach 4 1
NATIVE=403 expect_fail run attach 4 1
[ "$(wc -l < "$tmp/mutations")" -eq "$before" ]
NATIVE=404 run attach 4 1 2>/dev/null
run body 4 | grep -q '^Build parent:'
# Issue 7 already carries the link with CRLF endings: attach adds the native
# parent and must not prepend a second link.
run attach 7 1
tail -n 1 "$tmp/mutations" | grep -qx 'attach 7'
[ "$(run body 7 | grep -c '^Build parent:')" -eq 1 ]
before=$(wc -l < "$tmp/mutations")
run attach 7 1
[ "$(wc -l < "$tmp/mutations")" -eq "$before" ]
run children 1 > "$tmp/children"
[ "$(wc -l < "$tmp/children")" -eq 4 ]
grep -q $'^3\tCLOSED\t' "$tmp/children"
grep -q $'^7\tOPEN\t' "$tmp/children"
NATIVE=404 run children 1 > "$tmp/fallback"
diff <(sort "$tmp/children") <(sort "$tmp/fallback")
NATIVE=fail expect_fail run children 1
[ ! -s "$tmp/out" ]
SCAN_FAIL=1 expect_fail run children 1
[ ! -s "$tmp/out" ]
READ_FAIL=3 expect_fail run children 1
[ ! -s "$tmp/out" ]
run find 'literal [x].' > "$tmp/found"
grep -q $'^2\t' "$tmp/found"
SCAN_FAIL=1 expect_fail run find literal
[ ! -s "$tmp/out" ]
run next ready > "$tmp/next"
grep -q $'^2\t' "$tmp/next"
! grep -q $'^1\t' "$tmp/next"
run next ready --claim > "$tmp/claimed"
grep -q $'^2\t' "$tmp/claimed"
! grep -q $'^1\t' "$tmp/claimed"
grep -q '^edit 2$' "$tmp/mutations"
! grep -q '^edit 1$' "$tmp/mutations"
expect_fail run blocked 2
[ ! -s "$tmp/out" ]
run blocked 6 > "$tmp/blockers"
[ "$(cat "$tmp/blockers")" = "2" ]
run next ready > "$tmp/next"
! grep -q $'^6\t' "$tmp/next"
DEPS=404 run blocked 5 > "$tmp/blockers"
[ "$(cat "$tmp/blockers")" = "2" ]
DEPS=404 expect_fail run blocked 4
# An empty native result still honors documented body blockers.
run blocked 5 > "$tmp/blockers"
[ "$(cat "$tmp/blockers")" = "2" ]
# Keep dependency cases independent of the earlier claim and body-edit fixtures.
cp "$tmp/state.json" "$tmp/dependency-baseline.json"
configure_dependencies() {
  python3 - "$tmp" "$1" <<'PY'
import json,sys
from pathlib import Path
root=Path(sys.argv[1])
state=json.loads((root/'dependency-baseline.json').read_text())
for n,changes in json.loads(sys.argv[2]).items(): state[n].update(changes)
(root/'state.json').write_text(json.dumps(state))
PY
}
expect_unknown_blockers() {
  local ec=0
  run blocked "$1" > "$tmp/out" 2> "$tmp/err" || ec=$?
  [ "$ec" -eq 2 ]
  [ ! -s "$tmp/out" ]
  grep -qF "$2" "$tmp/err"
}

configure_dependencies '{"5":{"blocked_by":["3"]}}'
run blocked 5 > "$tmp/blockers"
[ "$(cat "$tmp/blockers")" = "2" ]
configure_dependencies '{"6":{"body":"Blocked by: #2, #4"}}'
run blocked 6 > "$tmp/blockers"
[ "$(cat "$tmp/blockers")" = $'2\n4' ]
configure_dependencies '{"5":{"blocked_by":["3"],"body":"Blocked by: #3"}}'
ec=0
run blocked 5 > "$tmp/out" 2> "$tmp/err" || ec=$?
[ "$ec" -eq 1 ] && [ ! -s "$tmp/out" ] && [ ! -s "$tmp/err" ]
configure_dependencies '{}'
DEPS=fail expect_unknown_blockers 5 'cannot read native blockers for 5'
BODY_FAIL=5 expect_unknown_blockers 5 'cannot read blocker body for 5'
READ_FAIL=2 expect_unknown_blockers 5 'cannot read blocker 2 for 5'
configure_dependencies '{"2":{"state":"UNKNOWN"}}'
expect_unknown_blockers 5 'unknown state for blocker 2 of 5'
configure_dependencies '{"5":{"blocked_by":["3"]},"3":{"state":"UNKNOWN"}}'
expect_unknown_blockers 5 'unknown native blocker state for 5'
configure_dependencies '{"5":{"body":"Blocked by: #3"},"3":{"state":""}}'
expect_unknown_blockers 5 'unknown state for blocker 3 of 5'
configure_dependencies '{"5":{"body":"Blocked by: other/repo#3"}}'
expect_unknown_blockers 5 'cannot parse blocker line for 5'
configure_dependencies '{"5":{"body":"\n\n\n\n\n\n\n\nBlocked by: #2\nBlocked by: #3"}}'
run blocked 5 > "$tmp/blockers"
[ "$(cat "$tmp/blockers")" = "2" ]
DEPS=404 run blocked 5 > "$tmp/blockers"
[ "$(cat "$tmp/blockers")" = "2" ]

# Neither selection nor selection-with-claim may advertise the body-blocked issue.
before=$(wc -l < "$tmp/mutations")
NEXT_IDS=5 run next ready > "$tmp/out"
[ ! -s "$tmp/out" ]
NEXT_IDS=5 run next ready --claim > "$tmp/out"
[ ! -s "$tmp/out" ]
[ "$(wc -l < "$tmp/mutations")" -eq "$before" ]
DEPS=fail NEXT_IDS=5 expect_fail run next ready --claim
[ ! -s "$tmp/out" ]
grep -q 'cannot determine readiness of 5' "$tmp/err"
[ "$(wc -l < "$tmp/mutations")" -eq "$before" ]
configure_dependencies '{"2":{"state":"UNKNOWN"}}'
NEXT_IDS=5 expect_fail run next ready --claim
[ ! -s "$tmp/out" ]
[ "$(wc -l < "$tmp/mutations")" -eq "$before" ]

# A dependency read failure after assignment releases the claim and reports unknown.
configure_dependencies '{"4":{"body":"Slice","assignees":[],"after_claim":false}}'
DEPS_AFTER_CLAIM=fail NEXT_IDS=4 expect_fail run next ready --claim
[ ! -s "$tmp/out" ]
grep -q 'cannot verify readiness after claiming 4; released claim' "$tmp/err"
python3 - "$tmp/state.json" <<'PY'
import json,sys
assert json.load(open(sys.argv[1]))['4']['assignees'] == []
PY
# A newly added fallback blocker after assignment also releases it.
configure_dependencies '{"4":{"body":"Slice","assignees":[],"after_claim":false}}'
BODY_AFTER_CLAIM='Blocked by: #2' NEXT_IDS=4 run next ready --claim > "$tmp/out"
[ ! -s "$tmp/out" ]
python3 - "$tmp/state.json" <<'PY'
import json,sys
assert json.load(open(sys.argv[1]))['4']['assignees'] == []
PY
configure_dependencies '{}'
# Reopening a closed member releases the claim from the work that closed it.
run reopen https://github.com/acme/widgets/issues/3 > "$tmp/reopened"
[ "$(cat "$tmp/reopened")" = $'reopened\t3' ]
tail -n 2 "$tmp/mutations" | grep -qx 'reopen 3'
tail -n 1 "$tmp/mutations" | grep -qx 'edit 3'
run children 1 | grep -q $'^3\tOPEN\t'
python3 - "$tmp/state.json" <<'CHECK'
import json, sys
assert json.load(open(sys.argv[1]))['3'].get('assignees') == []
CHECK
# A ticket that is already open keeps its assignee: someone may have claimed it.
before=$(wc -l < "$tmp/mutations")
run reopen 2 > "$tmp/reopened"
[ "$(cat "$tmp/reopened")" = $'already open\t2' ]
[ "$(wc -l < "$tmp/mutations")" -eq "$before" ]
python3 "$root/scripts/test-build-python.py"
echo 'build ticket adapter fixtures: ok'
