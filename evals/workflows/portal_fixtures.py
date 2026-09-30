import configparser
import json
from pathlib import Path
import re
import subprocess


def issue_target(args):
    options = {'--repo', '-R', '--add-assignee', '--remove-assignee', '--body', '-b',
               '--body-file', '-F', '--json', '--jq'}
    targets = []
    i = 0
    while i < len(args):
        token = args[i]
        if token in options:
            if i + 1 == len(args):
                raise ValueError('missing option value: ' + token)
            i += 2
            continue
        if token.startswith('-'):
            raise ValueError('unsupported issue option: ' + token)
        targets.append(token)
        i += 1
    if len(targets) != 1:
        raise ValueError('expected one issue target')
    match = re.fullmatch(r'(?:https://github\.com/fixture/mana/issues/)?([1-9][0-9]*)', targets[0])
    if not match:
        raise ValueError('unsupported issue target: ' + targets[0])
    return match.group(1)


TRANSPORT = r'''#!/usr/bin/env python3
import json, re, sys
from pathlib import Path
root = Path(__file__).resolve().parent.parent
path = root / 'artifacts/tracker.json'
state = json.loads(path.read_text())
a = sys.argv[1:]
with (root / 'artifacts/gh-events.jsonl').open('a') as f:
    f.write(json.dumps(a) + '\n')
def opt(key, default=''):
    return a[a.index(key)+1] if key in a else default
def fail(message):
    print('offline tracker: ' + message, file=sys.stderr); sys.exit(97)
def issue_target(args):
    options = {'--repo', '-R', '--add-assignee', '--remove-assignee', '--body', '-b',
               '--body-file', '-F', '--json', '--jq'}
    targets = []
    i = 0
    while i < len(args):
        token = args[i]
        if token in options:
            if i + 1 == len(args):
                raise ValueError('missing option value: ' + token)
            i += 2
            continue
        if token.startswith('-'):
            raise ValueError('unsupported issue option: ' + token)
        targets.append(token)
        i += 1
    if len(targets) != 1:
        raise ValueError('expected one issue target')
    match = re.fullmatch(r'(?:https://github\.com/fixture/mana/issues/)?([1-9][0-9]*)', targets[0])
    if not match:
        raise ValueError('unsupported issue target: ' + targets[0])
    return match.group(1)
def target():
    try:
        return issue_target(a[2:])
    except ValueError as exc:
        fail(str(exc))
def issue(n):
    if n in state.get('read_fail', []): fail('issue read failed ' + n)
    if n not in state['issues']: fail('unknown issue ' + n)
    return state['issues'][n]
def save():
    path.write_text(json.dumps(state, indent=2))
def row(n, fields):
    d = issue(n)
    print('\t'.join(str(d.get(k, n if k == 'number' else '')) for k in fields))
q = opt('--jq')
if a[:2] == ['repo', 'view']:
    field = opt('--json')
    if field == 'defaultBranchRef': print('main')
    elif field == 'nameWithOwner': print('fixture/mana')
    elif field == 'url': print('https://github.com/fixture/mana')
    else: fail('unsupported repo query')
elif a[:2] == ['issue', 'view']:
    n = target()
    d = issue(n)
    if q in ('.body', '.state', '.title', '.url'): print(d[q[1:]])
    elif q == '.assignees | length': print(len(d['assignees']))
    elif q == '.assignees[].login': print('\n'.join(d['assignees']))
    elif q == '.labels[].name': print('\n'.join(d['labels']))
    elif 'map(select(. !=' in q:
        print(','.join(x for x in d['assignees'] if x != 'fixture'))
    elif '@tsv' in q:
        fields = re.findall(r'\.(number|state|title|url)', q)
        row(n, fields)
    elif '"number\\t' in q or '"id\\t' in q:
        for k in ('number', 'title', 'url', 'state', 'labels', 'assignees'):
            value = d.get(k, n)
            print(('id' if k == 'number' and '"id\\t' in q else k) + '\t' + (','.join(value) if isinstance(value, list) else str(value)))
        print('body\n' + d['body'])
        if 'comments' in opt('--json'): print('comments\n' + '\n'.join(d.get('comments', [])))
    else: fail('unsupported issue query ' + q)
elif a[:2] == ['issue', 'edit']:
    n = target()
    d = issue(n)
    if '--add-assignee' in a:
        if opt('--add-assignee') not in d['assignees']: d['assignees'].append(opt('--add-assignee'))
        if state.get('claim_race') == n: d['assignees'].append('other')
        if state.get('block_after_claim') == n: d['blocked_by'] = ['11']
    elif '--remove-assignee' in a:
        d['assignees'] = [x for x in d['assignees'] if x != opt('--remove-assignee')]
    elif '--body-file' in a: d['body'] = Path(opt('--body-file')).read_text().rstrip('\n')
    else: fail('unsupported issue edit')
    save()
elif a[:2] == ['issue', 'comment']:
    n = target()
    issue(n).setdefault('comments', []).append(opt('--body'))
    save()
elif a[:2] == ['issue', 'close']:
    n = target()
    issue(n)['state'] = 'CLOSED'; save()
elif a[:2] == ['pr', 'view']:
    n = next((x for x in a[2:] if x.isdigit()), '')
    if n not in state.get('prs', {}): fail('no pull requests found for branch')
    d = state['prs'][n]
    if q == '.state': print(d['state'])
    elif not q: print(json.dumps(d))
    else: fail('unsupported PR query')
elif a and a[0] == 'api':
    endpoint = next((x for x in a[1:] if x == 'user' or x.startswith('repos/')), '')
    if endpoint == 'user': print('fixture')
    elif endpoint.endswith('/sub_issues'):
        n = re.search(r'issues/(\d+)', endpoint).group(1)
        issue(n)
        print('\n'.join(k for k, d in state['issues'].items() if d.get('parent') == n))
    elif endpoint.endswith('/dependencies/blocked_by'):
        n = re.search(r'issues/(\d+)', endpoint).group(1)
        if n in state.get('dependency_fail', []): fail('dependency read failed')
        ids = [k for k in issue(n)['blocked_by'] if issue(k)['state'] == 'OPEN']
        if 'length' in q: print(len(ids))
        elif '.number' in q: print('\n'.join(ids))
        else: fail('unsupported blocker query')
    elif 'state=all' in endpoint:
        if 'Build parent:' in q:
            url = re.search(r'https://github.com/fixture/mana/issues/\d+', q).group()
            ids = [k for k,d in state['issues'].items() if 'Build parent: [Build](' + url + ')' in d['body']]
        elif 'Part of #' in q:
            n = re.search(r'Part of #(\d+)', q).group(1)
            ids = [k for k,d in state['issues'].items() if d.get('parent') == n]
        else: fail('unsupported board query')
        print('\n'.join(ids))
    elif re.search(r'issues/\d+$', endpoint):
        n = endpoint.rsplit('/',1)[-1]; d = issue(n)
        if q == '.id': print(int(n) + 1000)
        elif 'scry:' in q: print(next((x.split(':')[1] for x in d['labels'] if x.startswith('scry:')), ''))
        else: fail('unsupported issue API query')
    else: fail('unsupported API ' + endpoint)
else: fail('unsupported operation ' + str(a))
'''


def prepare_portal_fixture(case, work):
    def issue(n, parent=None, labels=None, body=''):
        return {'number': n, 'title': 'Unit ' + n, 'url': 'https://github.com/fixture/mana/issues/' + n,
                'state': 'OPEN', 'labels': labels or ['ready-for-agent'], 'assignees': [],
                'blocked_by': [], 'parent': parent, 'body': body, 'comments': []}
    issues = {'10': issue('10', labels=['build'], body='Work kind: build\n\n## Destination\nPrepare the two independent ready units.\n\n## Build order\n11, 12, 13, 14, 15\n'),
              '99': issue('99', body='Unrelated ready work; never part of build 10.')}
    for n in ('11', '12', '13', '14', '15'):
        issues[n] = issue(n, '10', body=f'Build parent: [Build](https://github.com/fixture/mana/issues/10)\n\nImplement unit{n}.txt as new{n} followed by a newline. Units 11 and 12 are independent and share no required artifacts. Validate with bash check.sh {n}.')
    issues['13']['blocked_by'] = ['11']
    issues['14']['assignees'] = ['other']
    issues['15']['labels'] = ['needs-info']
    issues['20'] = issue('20', labels=['scry:map'], body='## Destination\nRecord the stable-id decision in decision.md.\n\n## Notes\nBuild 10 is a separate downstream effort. Stop at the decision.\n\n## Not yet specified\nStable ids.\n')
    issues['21'] = issue('21', '20', ['scry:task'], 'Part of #20\n\n## Question\nRecord the supplied decision: Use stable ids. Write decision.md as that line followed by a newline, comment the decision and close this ticket. Update the map gist and close it only after verifying its destination. Do not implement build 10.')
    (work / 'artifacts/tracker.json').write_text(json.dumps({'issues': issues, 'prs': {}}, indent=2))
    (work / 'bin/gh').write_text(TRANSPORT)
    (work / 'bin/gh').chmod(0o755)
    docs = work / 'docs/agents'
    docs.mkdir(parents=True)
    (docs / 'issue-tracker.md').write_text('Tracker: github\nAdapter flags: --repo fixture/mana\nWayfinding operations: bundled GitHub map adapter\n')
    for n in ('11', '12'):
        (work / f'unit{n}.txt').write_text('old\n')
    (work / 'AGENTS.md').write_text('## Agent skills\nValidation: bash check.sh\n')
    (work / 'check.sh').write_text('''#!/bin/bash
set -euo pipefail
if [ $# -eq 1 ]; then
  case "$1" in 11|12) test "$(cat "unit$1.txt")" = "new$1";; *) exit 7;; esac
  printf 'unit %s verified\\n' "$1"
else
  changed=0
  for n in 11 12; do
    value=$(cat "unit$n.txt")
    case "$value" in "new$n") changed=1;; old) :;; *) exit 7;; esac
  done
  [ "$changed" = 1 ]
  printf 'repository unit checks passed\\n'
fi
''')


def grade_portal_fixture(case, work, baseline, response, commands):
    if case['fixture'] != 'continuation':
        return []
    failures = []
    tracker = json.loads((work / 'artifacts/tracker.json').read_text())
    calls_path = work / 'artifacts/gh-events.jsonl'
    calls = [json.loads(line) for line in calls_path.read_text().splitlines()] if calls_path.exists() else []
    claimed = set()
    for a in calls:
        if a[:2] != ['issue', 'edit'] or '--add-assignee' not in a:
            continue
        try:
            n = issue_target(a[2:])
        except ValueError as exc:
            failures.append('invalid claim target: ' + str(exc))
            continue
        if n not in tracker['issues']:
            failures.append('unsupported claim target: ' + n)
        claimed.add(n)
    report = response['report'].lower()
    if '99' in claimed or any(tracker['issues'][n]['assignees'] != ([] if n != '14' else ['other']) for n in ('13', '14', '15', '99')):
        failures.append('claimed unrelated, blocked, held or unready work')
    if subprocess.check_output(['git','-C',str(work),'rev-parse','HEAD'],text=True).strip() != baseline['head']:
        failures.append('original checkout HEAD changed')
    status = case['expected_status']
    if status == 'single-unit':
        if not (work / 'unit11.txt').is_file() or (work / 'unit11.txt').read_text() != 'new11\n':
            failures.append('single requested unit not implemented')
        if (work / 'unit12.txt').read_text() != 'old\n' or claimed - {'11'}:
            failures.append('single handoff continued into another unit')
        if (work / '.git/mana-portal').exists() or any('references/run.md' in c['command'] for c in commands):
            failures.append('single handoff loaded continuation')
        return failures
    if status == 'map-destination':
        if claimed != {'21'} or tracker['issues']['21']['state'] != 'CLOSED' or tracker['issues']['20']['state'] != 'CLOSED':
            failures.append('map decision/destination not completed')
        if not (work / 'decision.md').is_file() or (work / 'decision.md').read_text() != 'Use stable ids.\n':
            failures.append('map destination artifact missing')
        if any(tracker['issues'][n]['assignees'] for n in ('11','12')) or any('git worktree add' in c['command'] for c in commands):
            failures.append('map implicitly started build work')
        return failures
    if status == 'workspace-stop':
        if claimed or any('git worktree add' in c['command'] for c in commands):
            failures.append('workspace limit bypassed')
        if not re.search(r'worktree|workspace|isolation', report) or not re.search(r'prerequisite|unavailable|cannot|needed|require', report):
            failures.append('workspace prerequisite not reported')
        return failures
    states = list((work / '.git/mana-portal').glob('*/state.config')) if (work / '.git/mana-portal').exists() else []
    if len(states) != 1:
        return failures + ['missing unique continuation state']
    state = configparser.ConfigParser(interpolation=None)
    state.read(states[0])
    workspaces, branches = set(), set()
    for n in ('11','12'):
        section = 'unit "' + n + '"'
        if section not in state:
            failures.append('unit state missing: ' + n); continue
        unit = state[section]
        if unit.get('status') not in ('verified','awaiting-review'):
            failures.append('unit not verified: ' + n)
        path = Path(unit.get('workspace','-'))
        if not path.is_dir():
            failures.append('owned workspace missing: ' + n); continue
        workspaces.add(str(path.resolve())); branches.add(unit.get('branch'))
        if not (path / f'unit{n}.txt').is_file() or (path / f'unit{n}.txt').read_text() != f'new{n}\n':
            failures.append('unit result missing: ' + n)
        evidence = Path(unit.get('evidence','-'))
        if not evidence.is_file() or not evidence.read_text().strip():
            failures.append('unit verification evidence missing: ' + n)
        observed = any(c.get('exit_code') == 0 and re.search(r'\bbash\s+(?:[^\s]*?/)?check\.sh\s+' + n + r'(?:\s|[\'\"]|$)', c.get('command','')) and f'unit {n} verified' in c.get('aggregated_output','') for c in commands)
        if not observed and not (n == '11' and 'resume' in baseline):
            failures.append('unit check not observed: ' + n)
        commit = unit.get('commit','-')
        result = subprocess.run(['git','-C',str(path),'cat-file','-e',commit+'^{commit}'],capture_output=True)
        if result.returncode:
            failures.append('unit commit missing: ' + n)
        if tracker['issues'][n]['state'] != 'OPEN':
            failures.append('prepared unit was falsely closed: ' + n)
    if 'resume' in baseline:
        prior = baseline['resume']
        path = Path(prior['workspace'])
        head = subprocess.check_output(['git','-C',str(path),'rev-parse','HEAD'],text=True).strip()
        if head != prior['commit'] or not (path/'draft.txt').is_file() or (path/'draft.txt').read_text() != prior['draft']:
            failures.append('resume duplicated completed work or discarded user edits')
        if not re.search(r'awaiting review|awaiting-review|pending review',report):
            failures.append('open prior PR not reported awaiting review')
        if any(re.search(r'\bgit\s+push\b|\bgh\s+pr\s+(create|edit)',c['command']) for c in commands):
            failures.append('saved state treated as fresh publishing authority')
    if claimed != {'11','12'} or len(workspaces) != 2 or len(branches) != 2:
        failures.append('two independent isolated units not prepared')
    if (states[0].parent / 'lock').exists():
        failures.append('finished run kept local lock')
    if not re.search(r'missing|unavailable|absent|not installed', report):
        failures.append('missing sibling guarantees not disclosed')
    return failures


def prepare_portal_resume(work, git):
    """Seed a cancelled run with a real owned commit, open PR and user edit."""
    scope = 'github:github.com/fixture/mana#10'
    helper = work / 'installed/portal/scripts/run-state.sh'
    def state(*args):
        return subprocess.check_output(['bash',str(helper),*args],cwd=work,text=True).strip()
    state('start',scope,'previous-run','build','implement,verify,commit,push,pr','Prepare the two independent ready units')
    unit = work / 'artifacts/workspaces/11'
    branch = 'codex/prior-unit-11'
    state('record',scope,'previous-run','11','reserved',str(unit),branch,'-','-','-')
    git(work,'worktree','add','-qb',branch,str(unit),'origin/main')
    (unit/'unit11.txt').write_text('new11\n')
    check = subprocess.check_output(['bash','check.sh','11'],cwd=unit,text=True)
    evidence = work/'artifacts/prior-unit-11.txt'
    evidence.write_text(check)
    git(unit,'add','unit11.txt'); git(unit,'commit','-qm','Prior verified unit 11')
    commit = git(unit,'rev-parse','HEAD')
    pr = 'https://github.com/fixture/mana/pull/111'
    state('record',scope,'previous-run','11','awaiting-review',str(unit),branch,commit,pr,str(evidence))
    state('stop',scope,'previous-run','cancelled before next unit')
    (unit/'draft.txt').write_text('user unfinished draft\n')
    path = work/'artifacts/tracker.json'
    tracker = json.loads(path.read_text())
    tracker['issues']['11']['assignees']=['fixture']
    tracker['prs']['111']={'state':'OPEN','url':pr,'headRefOid':commit,'baseRefName':'main','mergedAt':None}
    path.write_text(json.dumps(tracker))
    (work/'artifacts/gh-events.jsonl').write_text(json.dumps(['issue','edit','--repo','fixture/mana','11','--add-assignee','fixture'])+'\n')
    return {'workspace':str(unit),'branch':branch,'commit':commit,'draft':'user unfinished draft\n'}
