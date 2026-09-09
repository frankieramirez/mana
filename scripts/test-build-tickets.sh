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
    if q=='.body': print(d['body'])
    elif q=='.state': print(d['state'])
    elif q=='.labels[].name': print('ready')
    elif q=='.assignees[].login': print('fixture')
    elif q=='[.number,.title,.url,.state] | @tsv': row(n,['number','title','url','state'])
    elif q=='[.number,.state,.title,.url] | @tsv': row(n,['number','state','title','url'])
    elif 'map(select' in q: print('')
    else: fail('unexpected view query: '+q)
elif a[:2] == ['issue','edit']:
    n=next(x for x in a[2:] if x.isdigit())
    issue(n)
    if '--body-file' in a: state[n]['body']=Path(option('--body-file')).read_text().rstrip('\n')
    save('edit '+n)
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
    elif endpoint.endswith('/dependencies/blocked_by'): print('0')
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
                if re.search(r'^Build parent: \[.*\]\(https://github.com/acme/widgets/issues/1\)$',d['body'],re.M): print(k)
        else: fail('unexpected all-state query: '+q)
    elif endpoint.endswith('/issues'):
        assert '--paginate' in a and 'Work kind: build' in q
        # Include the parent to also test the fresh per-candidate marker check.
        for k in ('1','2'):
            d=issue(k); print(f"2026-01-0{k}\t{k}\t{d['title']}\t{d['url']}")
    else: fail('unexpected api: '+str(a))
else: fail('unexpected gh command: '+str(a))
MOCK
chmod +x "$tmp/gh"
python3 - <<'PY'
import json,os
from pathlib import Path
state={str(n):{'title':f'Issue {n}','url':f'https://github.com/acme/widgets/issues/{n}',
 'state':'OPEN','body':'Slice literal [x].','parent':None} for n in range(1,7)}
state['1']['body']='Work kind: build\n\n## Destination\nDeliver the feature'
state['3'].update(state='CLOSED',body='Build parent: [Build](https://github.com/acme/widgets/issues/1)')
state['6'].update(parent='5')
Path(os.environ['GH_FIXTURE'],'state.json').write_text(json.dumps(state))
PY
run() { bash "$root/skills/sift/scripts/tickets.sh" --repo acme/widgets "$@"; }
expect_fail() { if "$@" > "$tmp/out" 2> "$tmp/err"; then echo "unexpected success: $*" >&2; exit 1; fi; }
run body 1 > "$tmp/snapshot"
run update-body 1 --expected-body "$tmp/snapshot" < "$tmp/snapshot"
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
run children 1 > "$tmp/children"
[ "$(wc -l < "$tmp/children")" -eq 3 ]
grep -q $'^3\tCLOSED\t' "$tmp/children"
NATIVE=404 run children 1 > "$tmp/fallback"
cmp "$tmp/children" "$tmp/fallback"
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
python3 "$root/scripts/test-build-python.py"
echo 'build ticket adapter fixtures: ok'
