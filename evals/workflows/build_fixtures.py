"""Offline build-parent tracker for the build progress Leftover evidence cases."""
import json
import re

URL = 'https://github.com/fixture/mana'
PARENT, OWNER, LAYOUT, MAP, UNRELATED = '40', '42', '41', '30', '99'
READY, CATEGORY = 'ready-for-agent', 'enhancement'
PARENT_URL = URL + '/issues/' + PARENT
CLOSEOUT = ('Check progress and close out the build effort at ' + PARENT_URL
            + ', reopening or filing tickets for its unmet evidence.')

TRANSPORT = r'''#!/usr/bin/env python3
"""Offline GitHub double for the build-parent fixture. Unknown operations fail closed."""
import json, re, sys
from pathlib import Path

root = Path(__file__).resolve().parent.parent
path = root / 'artifacts/tracker.json'
state = json.loads(path.read_text())
a = sys.argv[1:]
with (root / 'artifacts/gh-events.jsonl').open('a') as f:
    f.write(json.dumps(a) + '\n')
URL = 'https://github.com/fixture/mana'
REPOS = ('fixture/mana', 'github.com/fixture/mana', URL)


def fail(message):
    print('offline tracker: ' + message, file=sys.stderr)
    sys.exit(97)


def not_found():
    print('gh: Not Found (HTTP 404)', file=sys.stderr)
    sys.exit(1)


def save():
    path.write_text(json.dumps(state, indent=2) + '\n')


def stamp():
    state['clock'] = state.get('clock', 0) + 1
    return '2026-10-16T12:%02d:00Z' % state['clock']


def split(args, valued, flags=()):
    opts, pos, i = [], [], 0
    while i < len(args):
        token = args[i]
        if token.startswith('--') and '=' in token:
            key, value = token.split('=', 1)
            if key not in valued:
                fail('unsupported option ' + key)
            opts.append((key, value)); i += 1
        elif token in valued:
            if i + 1 == len(args):
                fail('missing value for ' + token)
            opts.append((token, args[i + 1])); i += 2
        elif token in flags:
            opts.append((token, True)); i += 1
        elif token.startswith('-'):
            fail('unsupported option ' + token)
        else:
            pos.append(token); i += 1
    repo = get(opts, '--repo', '-R')
    if repo is not None and repo not in REPOS:
        fail('unknown repository ' + repo)
    return opts, pos


def get(opts, *keys, default=None):
    for key, value in reversed(opts):
        if key in keys:
            return value
    return default


def values(opts, *keys):
    return [v for k, v in opts if k in keys]


def csv(value):
    return [x.strip() for x in value.split(',') if x.strip()]


def target(pos, kind='issues'):
    if len(pos) != 1:
        fail('expected one target')
    m = re.fullmatch(r'(?:' + re.escape(URL) + '/' + kind + r'/|#)?([1-9][0-9]*)', pos[0])
    if not m:
        fail('unsupported target ' + pos[0])
    return m.group(1)


def issue(n):
    if n not in state['issues']:
        not_found()
    return state['issues'][n]


def text_from(opts):
    body = get(opts, '--body', '-b')
    source = get(opts, '--body-file', '-F')
    if source is not None:
        body = sys.stdin.read() if source == '-' else Path(source).read_text()
    return None if body is None else body.rstrip('\n')


def gh_issue(n, d):
    return {'number': int(n), 'title': d['title'], 'url': URL + '/issues/' + n, 'state': d['state'],
            'body': d['body'], 'labels': [{'name': x} for x in d['labels']],
            'assignees': [{'login': x} for x in d['assignees']], 'createdAt': d['createdAt'],
            'comments': [{'author': {'login': c['author']}, 'body': c['body'], 'createdAt': c['createdAt']}
                         for c in d['comments']],
            'closedByPullRequestsReferences': [{'number': int(p), 'url': URL + '/pull/' + p}
                                               for p in d.get('closed_by', [])]}


def rest(n, d):
    return {'number': int(n), 'id': 1000 + int(n), 'title': d['title'], 'state': d['state'].lower(),
            'body': d['body'], 'html_url': URL + '/issues/' + n, 'labels': [{'name': x} for x in d['labels']],
            'assignees': [{'login': x} for x in d['assignees']], 'created_at': d['createdAt'],
            'comments': len(d['comments'])}


def gh_pr(n, p):
    return {'number': int(n), 'title': p['title'], 'url': URL + '/pull/' + n, 'state': p['state'],
            'body': p['body'], 'mergedAt': p['mergedAt'], 'headRefName': p['head'], 'baseRefName': 'main',
            'isDraft': False, 'author': {'login': 'builder'},
            'closingIssuesReferences': [{'number': int(x), 'url': URL + '/issues/' + x} for x in p['closes']]}


def pick(full, fields):
    unknown = [f for f in fields if f not in full]
    if unknown:
        fail('unsupported field ' + ','.join(unknown))
    return {f: full[f] for f in fields}


def simple(data, q):
    """Path expressions such as .body, .labels[].name, .[].number, and X | length."""
    q = q.strip()
    count = q == 'length' or q.endswith('| length')
    if count:
        q = q[:-len('length')].rstrip().rstrip('|').strip() or '.'
    if not re.fullmatch(r'\.|(?:\.?\[\]|\.[A-Za-z_][A-Za-z0-9_]*)+', q):
        fail('unsupported --jq expression; rerun with --json alone to read the raw JSON: ' + q)
    out = [data]
    for seg in re.findall(r'\.?\[\]|\.[A-Za-z_][A-Za-z0-9_]*', q):
        nxt = []
        for v in out:
            if seg.endswith('[]'):
                if not isinstance(v, list):
                    fail('cannot iterate over ' + type(v).__name__)
                nxt.extend(v)
            elif isinstance(v, dict):
                nxt.append(v.get(seg[1:]))
            else:
                fail('cannot index ' + type(v).__name__)
        out = nxt
    if count:
        if len(out) != 1 or not isinstance(out[0], (list, dict, str)):
            fail('unsupported length expression')
        return [len(out[0])]
    return out


def emit(items):
    for v in items:
        if v is None:
            print('null')
        elif isinstance(v, bool):
            print('true' if v else 'false')
        elif isinstance(v, (dict, list)):
            print(json.dumps(v))
        else:
            print(v)


def tsv_fields(q):
    m = re.search(r'\[([^\[\]]*)\]\s*\|\s*@tsv\s*$', q)
    if not m:
        fail('unsupported @tsv expression ' + q)
    return [f.strip().lstrip('.') for f in m.group(1).split(',')]


def tsv(row, fields):
    return '\t'.join(str(row.get(f, '')) for f in fields)


def build_line(body):
    return any(line == 'Work kind: build' for line in body.replace('\r', '').split('\n'))


def issue_query(n, d, data, q):
    full = gh_issue(n, d)
    if '"id\\t' in q or '"number\\t' in q:
        lines = [('id' if '"id\\t' in q else 'number') + '\t' + n, 'title\t' + d['title'],
                 'url\t' + full['url'], 'state\t' + d['state'], 'labels\t' + ','.join(d['labels']),
                 'assignees\t' + ','.join(d['assignees']), 'body', d['body']]
        if '"comments"' in q:
            lines += ['comments', '\n'.join('--- %s %s\n%s' % (c['author'], c['createdAt'], c['body'])
                                            for c in d['comments'])]
        print('\n'.join(lines))
    elif '@tsv' in q:
        print(tsv(full, tsv_fields(q)))
    elif 'join(' in q and '.assignees' in q:
        m = re.search(r'select\(\. != "([^"]*)"\)', q)
        print(','.join(x for x in d['assignees'] if not m or x != m.group(1)))
    else:
        emit(simple(data, q))


def issue_cmd(verb, args):
    if verb == 'view':
        opts, pos = split(args, {'--repo', '-R', '--json', '--jq', '-q'}, {'--comments'})
        n = target(pos)
        d = issue(n)
        fields, q = get(opts, '--json'), get(opts, '--jq', '-q')
        if fields is None:
            if q:
                fail('--jq needs --json')
            print('title:\t%s\nstate:\t%s\nlabels:\t%s\nassignees:\t%s\nnumber:\t%s\n--\n%s'
                  % (d['title'], d['state'], ', '.join(d['labels']), ', '.join(d['assignees']), n, d['body']))
            if get(opts, '--comments'):
                for c in d['comments']:
                    print('--\nauthor:\t%s\ncreated:\t%s\n%s' % (c['author'], c['createdAt'], c['body']))
            return
        data = pick(gh_issue(n, d), csv(fields))
        if q is None:
            print(json.dumps(data, indent=2))
        else:
            issue_query(n, d, data, q)
    elif verb == 'edit':
        opts, pos = split(args, {'--repo', '-R', '--add-assignee', '--remove-assignee', '--add-label',
                                 '--remove-label', '--body', '-b', '--body-file', '-F', '--title', '-t'})
        n = target(pos)
        d = issue(n)
        changes = [k for k, _ in opts if k not in ('--repo', '-R')]
        if not changes:
            fail('nothing to edit')
        for key, value in opts:
            if key == '--add-assignee':
                d['assignees'] += [x for x in csv(value) if x not in d['assignees']]
            elif key == '--remove-assignee':
                d['assignees'] = [x for x in d['assignees'] if x not in csv(value)]
            elif key == '--add-label':
                for label in csv(value):
                    if label not in state['labels']:
                        print("could not add label: '%s' not found" % label, file=sys.stderr); sys.exit(1)
                    if label not in d['labels']:
                        d['labels'].append(label)
            elif key == '--remove-label':
                d['labels'] = [x for x in d['labels'] if x not in csv(value)]
            elif key in ('--title', '-t'):
                d['title'] = value
        body = text_from(opts)
        if body is not None:
            d['body'] = body
        save()
        print(URL + '/issues/' + n)
    elif verb == 'comment':
        opts, pos = split(args, {'--repo', '-R', '--body', '-b', '--body-file', '-F'})
        n = target(pos)
        d = issue(n)
        body = text_from(opts)
        if not body:
            fail('comment needs a body')
        d['comments'].append({'author': 'fixture', 'createdAt': stamp(), 'body': body})
        save()
        print(URL + '/issues/' + n + '#issuecomment-' + str(len(d['comments'])))
    elif verb in ('close', 'reopen'):
        opts, pos = split(args, {'--repo', '-R', '--comment', '-c', '--reason', '-r'})
        n = target(pos)
        d = issue(n)
        if get(opts, '--comment', '-c'):
            d['comments'].append({'author': 'fixture', 'createdAt': stamp(), 'body': get(opts, '--comment', '-c')})
        d['state'] = 'CLOSED' if verb == 'close' else 'OPEN'
        save()
        print(('Closed' if verb == 'close' else 'Reopened') + ' issue fixture/mana#' + n)
    elif verb == 'create':
        opts, pos = split(args, {'--repo', '-R', '--title', '-t', '--body', '-b', '--body-file', '-F',
                                 '--label', '-l', '--assignee', '-a'})
        title, body = get(opts, '--title', '-t'), text_from(opts)
        if pos or not title or body is None:
            fail('create needs --title and a body')
        labels = [x for v in values(opts, '--label', '-l') for x in csv(v)]
        for label in labels:
            if label not in state['labels']:
                print("could not add label: '%s' not found" % label, file=sys.stderr); sys.exit(1)
        n = str(max(int(k) for k in list(state['issues']) + list(state['prs'])) + 1)
        state['issues'][n] = {'title': title, 'state': 'OPEN', 'labels': list(dict.fromkeys(labels)),
                              'assignees': [x for v in values(opts, '--assignee', '-a') for x in csv(v)],
                              'body': body, 'comments': [], 'createdAt': stamp(), 'parent': None,
                              'blocked_by': []}
        save()
        print(URL + '/issues/' + n)
    elif verb == 'list':
        opts, pos = split(args, {'--repo', '-R', '--state', '-s', '--label', '-l', '--limit', '-L',
                                 '--json', '--jq', '-q'})
        if pos:
            fail('unexpected argument ' + pos[0])
        wanted = (get(opts, '--state', '-s') or 'open').upper()
        labels = [x for v in values(opts, '--label', '-l') for x in csv(v)]
        rows = [(n, d) for n, d in sorted(state['issues'].items(), key=lambda x: int(x[0]))
                if (wanted == 'ALL' or d['state'] == wanted) and all(x in d['labels'] for x in labels)]
        fields, q = get(opts, '--json'), get(opts, '--jq', '-q')
        if fields is None:
            for n, d in rows:
                print('%s\t%s\t%s\t%s' % (n, d['state'], d['title'], ','.join(d['labels'])))
            return
        data = [pick(dict(gh_issue(n, d), updatedAt=d['createdAt']), csv(fields)) for n, d in rows]
        if q is None:
            print(json.dumps(data, indent=2))
        elif 'test("Part of #' in q:
            m = re.search(r'Part of #(\d+)', q)
            print('\n'.join(str(r['number']) for r in data if re.search(r'Part of #' + m.group(1) + r'(\s|$)', r.get('body', ''))))
        elif '@tsv' in q:
            if 'select((.labels | length) == 0)' in q:
                data = [r for r in data if not r.get('labels')]
            fields = tsv_fields(q)
            for r in data:
                print(tsv(r, fields))
        else:
            emit(simple(data, q))
    else:
        fail('unsupported issue operation ' + verb)


def api_cmd(args):
    opts, pos = split(args, {'--method', '-X', '--jq', '-q', '-f', '-F', '--field', '--raw-field', '-H', '--header'},
                      {'--paginate', '--slurp', '-i', '--include', '--silent'})
    if len(pos) != 1:
        fail('expected one API endpoint')
    endpoint = pos[0]
    fields = {}
    for value in values(opts, '-f', '-F', '--field', '--raw-field'):
        if '=' not in value:
            fail('malformed field ' + value)
        key, value = value.split('=', 1)
        fields[key] = value
    method = (get(opts, '--method', '-X') or ('POST' if fields else 'GET')).upper()
    q = get(opts, '--jq', '-q')
    route, _, query = endpoint.lstrip('/').partition('?')
    params = dict(p.split('=', 1) for p in query.split('&') if '=' in p)
    if method == 'GET':
        params.update(fields)
    issues = state['issues']
    m = re.fullmatch(r'repos/fixture/mana/issues/(\d+)(/.*)?', route)
    if route == 'user' and method == 'GET':
        data = {'login': 'fixture'}
    elif route == 'repos/fixture/mana' and method == 'GET':
        data = {'full_name': 'fixture/mana', 'name': 'mana', 'html_url': URL, 'default_branch': 'main'}
    elif route == 'repos/fixture/mana/issues' and method == 'GET':
        wanted = params.get('state', 'open')
        labels = csv(params.get('labels', ''))
        data = [rest(n, d) for n, d in sorted(issues.items(), key=lambda x: int(x[0]))
                if (wanted == 'all' or d['state'].lower() == wanted) and all(x in d['labels'] for x in labels)]
    elif m and m.group(2) is None and method == 'GET':
        data = rest(m.group(1), issue(m.group(1)))
    elif m and m.group(2) == '/parent' and method == 'GET':
        parent = issue(m.group(1)).get('parent')
        if not parent:
            not_found()
        data = rest(parent, issue(parent))
    elif m and m.group(2) == '/sub_issues':
        n = m.group(1)
        issue(n)
        if method == 'GET':
            data = [rest(k, d) for k, d in sorted(issues.items(), key=lambda x: int(x[0])) if d.get('parent') == n]
        elif method == 'POST':
            child = str(int(fields.get('sub_issue_id', '0')) - 1000)
            d = issue(child)
            if d.get('parent'):
                print('gh: An issue can only have one parent (HTTP 422)', file=sys.stderr); sys.exit(1)
            d['parent'] = n
            save()
            data = rest(n, issues[n])
        else:
            fail('unsupported sub-issue method ' + method)
    elif m and m.group(2) == '/dependencies/blocked_by':
        n = m.group(1)
        d = issue(n)
        if method == 'GET':
            data = [rest(k, issue(k)) for k in d['blocked_by']]
        elif method == 'POST':
            blocker = str(int(fields.get('issue_id', '0')) - 1000)
            issue(blocker)
            if blocker not in d['blocked_by']:
                d['blocked_by'].append(blocker)
            save()
            data = rest(blocker, issues[blocker])
        else:
            fail('unsupported dependency method ' + method)
    elif m and m.group(2) == '/comments' and method == 'GET':
        data = [{'user': {'login': c['author']}, 'body': c['body'], 'created_at': c['createdAt']}
                for c in issue(m.group(1))['comments']]
    else:
        fail('unsupported API ' + method + ' ' + endpoint)
    if q is None:
        print(json.dumps(data, indent=2))
    elif 'startswith("Build parent: [")' in q:
        url = re.search(r'endswith\("\]\(([^"]*)\)"\)', q).group(1)
        for r in data:
            lines = (r['body'] or '').replace('\r', '').split('\n')
            if any(x.startswith('Build parent: [') and x.endswith('](' + url + ')') for x in lines):
                print(r['number'])
    elif '.html_url | startswith(' in q:
        prefix = re.search(r'startswith\("([^"]*)"\)', q).group(1)
        for r in data:
            if not r['html_url'].startswith(prefix):
                fail('cross-repository child requires its own repository context')
            print(r['number'])
    elif 'contains("' in q:
        needle = re.search(r'contains\("((?:[^"\\]|\\.)*)"\)', q).group(1)
        needle = re.sub(r'\\(.)', r'\1', needle)
        for r in data:
            if needle in (r['body'] or ''):
                print('\t'.join([str(r['number']), r['state'].upper(), r['title'], r['html_url']]))
    elif 'test("(?m)^Part of #' in q:
        n = re.search(r'Part of #(\d+)', q).group(1)
        for r in data:
            if re.search(r'(?m)^Part of #' + n + r'(\s|$)', r['body'] or ''):
                print(r['number'])
    elif '(.assignees | length) == 0' in q and 'created_at' in q:
        for r in data:
            if not r['assignees'] and not build_line(r['body'] or ''):
                print('\t'.join([r['created_at'], str(r['number']), r['title'], r['html_url']]))
    elif 'select(.state == "open"' in q:
        blockers = [r for r in data if r['state'] == 'open']
        if q.rstrip().endswith('length'):
            print(len(blockers))
        else:
            for r in blockers:
                print(r['number'])
    elif '@tsv' in q and isinstance(data, dict):
        print(tsv(data, tsv_fields(q)))
    else:
        emit(simple(data, q))


def pr_cmd(verb, args):
    prs = state['prs']
    if verb == 'list':
        opts, pos = split(args, {'--repo', '-R', '--state', '-s', '--search', '-S', '--json', '--jq', '-q',
                                 '--limit', '-L'})
        if pos:
            fail('unexpected argument ' + pos[0])
        wanted = (get(opts, '--state', '-s') or 'open').upper()
        terms = (get(opts, '--search', '-S') or '').split()
        qualifiers = ('is:open', 'is:closed', 'is:merged', 'state:open', 'state:closed')
        if any(':' in t and t.lower() not in qualifiers for t in terms):
            fail('unsupported search qualifier; rerun with --json alone to read the raw JSON')
        for t in terms:
            if t.lower() in qualifiers:
                wanted = t.split(':')[1].upper()
        words = [t.lstrip('#').lower() for t in terms if ':' not in t]
        def keep(p):
            if wanted == 'OPEN' and p['state'] != 'OPEN':
                return False
            if wanted == 'CLOSED' and p['state'] == 'OPEN':
                return False
            if wanted == 'MERGED' and p['state'] != 'MERGED':
                return False
            hay = (p['title'] + ' ' + p['body']).lower()
            return all(w in hay for w in words)
        rows = [(n, p) for n, p in sorted(prs.items(), key=lambda x: int(x[0])) if keep(p)]
        fields, q = get(opts, '--json'), get(opts, '--jq', '-q')
        if fields is None:
            if q:
                fail('--jq needs --json')
            for n, p in rows:
                print('%s\t%s\t%s\t%s' % (n, p['title'], p['head'], p['state']))
            return
        data = [pick(gh_pr(n, p), csv(fields)) for n, p in rows]
        if q is None:
            print(json.dumps(data, indent=2))
        elif re.fullmatch(r'\s*\.\[\]\s*\|\s*\[[^\[\]]*\]\s*\|\s*@tsv\s*', q):
            for r in data:
                print(tsv(r, tsv_fields(q)))
        else:
            emit(simple(data, q))
    elif verb == 'view':
        opts, pos = split(args, {'--repo', '-R', '--json', '--jq', '-q'}, {'--comments'})
        n = target(pos, 'pull')
        if n not in prs:
            print('GraphQL: Could not resolve to a PullRequest with the number of %s.' % n, file=sys.stderr); sys.exit(1)
        p = prs[n]
        fields, q = get(opts, '--json'), get(opts, '--jq', '-q')
        if fields is None:
            print('title:\t%s\nstate:\t%s\nurl:\t%s\n--\n%s' % (p['title'], p['state'], URL + '/pull/' + n, p['body']))
            return
        data = pick(gh_pr(n, p), csv(fields))
        if q is None:
            print(json.dumps(data, indent=2))
        else:
            emit(simple(data, q))
    else:
        fail('unsupported pr operation ' + verb)


def repo_cmd(verb, args):
    if verb != 'view':
        fail('unsupported repo operation ' + verb)
    opts, pos = split(args, {'--json', '--jq', '-q'})
    if pos and pos[0] not in REPOS:
        fail('unknown repository ' + pos[0])
    fields, q = get(opts, '--json'), get(opts, '--jq', '-q')
    if fields is None:
        print('name:\tfixture/mana\ndescription:\tOffline fixture repository')
        return
    data = pick({'nameWithOwner': 'fixture/mana', 'name': 'mana', 'url': URL, 'owner': {'login': 'fixture'},
                 'defaultBranchRef': {'name': 'main'}}, csv(fields))
    print(json.dumps(data, indent=2)) if q is None else emit(simple(data, q))


def label_cmd(verb, args):
    if verb == 'list':
        opts, pos = split(args, {'--repo', '-R', '--limit', '-L', '--json', '--jq', '-q'})
        data = [{'name': x} for x in state['labels']]
        q = get(opts, '--jq', '-q')
        if get(opts, '--json') is None:
            print('\n'.join(state['labels']))
        elif q is None:
            print(json.dumps(data, indent=2))
        else:
            emit(simple(data, q))
    elif verb == 'create':
        opts, pos = split(args, {'--repo', '-R', '--color', '-c', '--description', '-d'}, {'--force', '-f'})
        if len(pos) != 1:
            fail('label create needs one name')
        if pos[0] not in state['labels']:
            state['labels'].append(pos[0])
            save()
    else:
        fail('unsupported label operation ' + verb)


if a[:2] == ['auth', 'status']:
    print('github.com\n  Logged in to github.com account fixture (offline fixture)')
elif len(a) >= 2 and a[0] == 'issue':
    issue_cmd(a[1], a[2:])
elif a and a[0] == 'api':
    api_cmd(a[1:])
elif len(a) >= 2 and a[0] == 'pr':
    pr_cmd(a[1], a[2:])
elif len(a) >= 2 and a[0] == 'repo':
    repo_cmd(a[1], a[2:])
elif len(a) >= 2 and a[0] == 'label':
    label_cmd(a[1], a[2:])
else:
    fail('unsupported operation ' + ' '.join(a))
'''


def brief(summary, current, desired, criteria):
    return ('> *This was generated by AI during triage.*\n\n## Agent Brief\n\n**Category:** enhancement\n'
            '**Summary:** ' + summary + '\n\n**Current behavior:**\n' + current + '\n\n**Desired behavior:**\n'
            + desired + '\n\n**Acceptance criteria:**\n' + criteria + '\n\n**Out of scope:**\n- Onboarding copy and settings')


def initial_tracker():
    def member(title, summary, current, desired, criteria, created):
        return {'title': title, 'state': 'CLOSED', 'labels': [CATEGORY], 'assignees': ['builder'],
                'body': ('Build parent: [Build: Agent first screen](' + PARENT_URL + ')\n'
                         'Planning source: [Map: Agent first screen](' + URL + '/issues/' + MAP + ')\n\n'
                         + brief(summary, current, desired, criteria)),
                'comments': [], 'createdAt': created, 'parent': PARENT, 'blocked_by': []}
    parent_body = '\n'.join([
        'Work kind: build',
        'Planning source: [Map: Agent first screen](' + URL + '/issues/' + MAP + ')',
        '',
        '## Destination',
        '',
        'An agent session opens on the first screen. Delivered when the first-screen layout is merged and three '
        'recorded agent runs on one merged revision pass the first-screen check, with each run log linked from '
        'this build parent.',
        '',
        '## Scope',
        '',
        'The first-screen layout and the recorded agent runs that prove it. Onboarding copy and settings stay out.',
        '',
        '## Build order',
        '',
        '1. First screen layout. Ticket: [First screen layout](' + URL + '/issues/' + LAYOUT + '). After: none.',
        '   Outcome: the first screen renders the session list and prompt box; layout tests pass on the merged PR.',
        '2. Agent first-screen runs. Ticket: [Agent first-screen runs](' + URL + '/issues/' + OWNER + '). After: 1.',
        '   Outcome: three recorded agent runs on one merged revision pass the first-screen check, each run log '
        'linked from the build parent.',
        '',
        '## Next step',
        '',
        'Record three agent first-screen runs on one merged revision, link their logs here, then close out.',
    ])
    layout = member('First screen layout', 'Render the session list and prompt box on the first screen.',
                    'Sessions open on a blank screen.', 'The first screen shows the session list and prompt box.',
                    '- [ ] Layout tests pass', '2026-10-01T09:00:00Z')
    layout['comments'] = [{'author': 'builder', 'createdAt': '2026-10-03T15:00:00Z',
                           'body': 'Delivered in [PR #51](' + URL + '/pull/51), merged. Layout tests passed on the merged revision.'}]
    layout['closed_by'] = ['51']
    runs = member('Agent first-screen runs', 'Record three agent runs that pass the first-screen check.',
                  'No agent run has exercised the first screen.',
                  'Three recorded agent runs on one merged revision pass the first-screen check.',
                  '- [ ] Run harness merged\n- [ ] Three passing run logs on one merged revision, linked from the build parent',
                  '2026-10-01T09:05:00Z')
    runs['comments'] = [{'author': 'builder', 'createdAt': '2026-10-08T11:00:00Z',
                         'body': 'Closed automatically when [PR #52](' + URL + '/pull/52) merged; its body said '
                                 '`Closes #42`. The run harness landed. No agent run has been recorded yet.'}]
    runs['closed_by'] = ['52']
    issues = {
        MAP: {'title': 'Map: Agent first screen', 'state': 'CLOSED', 'labels': ['scry:map'], 'assignees': [],
              'body': '## Destination\n\nDecide what the agent first screen shows.\n\n## Decisions so far\n\n'
                      '- The first screen shows the session list and prompt box.\n\n## Out of scope\n\n- Onboarding copy',
              'comments': [{'author': 'fixture', 'createdAt': '2026-09-30T18:00:00Z',
                            'body': '## Build effort\n\n[Build: Agent first screen](' + PARENT_URL + ')'}],
              'createdAt': '2026-09-20T09:00:00Z', 'parent': None, 'blocked_by': []},
        PARENT: {'title': 'Build: Agent first screen', 'state': 'OPEN', 'labels': [CATEGORY], 'assignees': [],
                 'body': parent_body, 'comments': [], 'createdAt': '2026-09-30T17:00:00Z', 'parent': None,
                 'blocked_by': []},
        LAYOUT: layout,
        OWNER: runs,
        UNRELATED: {'title': 'Fix settings typo', 'state': 'OPEN', 'labels': ['bug', READY], 'assignees': [],
                    'body': 'Unrelated ready work; never part of build 40.\n\n'
                            + brief('Fix the settings typo.', 'Settings says Prefrences.', 'Settings says Preferences.',
                                    '- [ ] Settings says Preferences'),
                    'comments': [], 'createdAt': '2026-08-01T09:00:00Z', 'parent': None, 'blocked_by': []},
    }
    issues[OWNER]['blocked_by'] = [LAYOUT]
    prs = {'51': {'title': 'Render the first-screen layout', 'state': 'MERGED', 'body': 'Closes #41',
                  'mergedAt': '2026-10-03T14:00:00Z', 'head': 'first-screen-layout', 'closes': [LAYOUT]},
           '52': {'title': 'Add the agent run harness', 'state': 'MERGED',
                  'body': 'Adds the run harness. Closes #42. Agent runs follow after merge.',
                  'mergedAt': '2026-10-08T10:55:00Z', 'head': 'agent-run-harness', 'closes': [OWNER]}}
    labels = ['bug', CATEGORY, READY, 'needs-triage', 'needs-info', 'ready-for-human', 'wontfix', 'scry:map']
    return {'issues': issues, 'prs': prs, 'labels': labels, 'clock': 0}


def prepare_build_fixture(case, work):
    (work / 'artifacts/tracker.json').write_text(json.dumps(initial_tracker(), indent=2) + '\n')
    (work / 'bin/gh').write_text(TRANSPORT)
    (work / 'bin/gh').chmod(0o755)
    docs = work / 'docs/agents'
    docs.mkdir(parents=True)
    (docs / 'issue-tracker.md').write_text(
        '# Issue tracker: GitHub\n\nTracker: github\nProject: fixture/mana\nAdapter flags: --repo fixture/mana\n'
        'Keys: `#42`. Issues and pull requests share one number space.\nHost: github.com\n\n## Conventions\n\n'
        'Every write goes through the adapter script the skills carry (`tickets.sh`): create, attach, wire, next, '
        'claim, label, comment, update-body, close, reopen. Reads may use `gh issue view` and `gh issue list` directly.\n')
    (work / 'AGENTS.md').write_text('## Agent skills\n\nIssue tracker: GitHub fixture/mana. See `docs/agents/issue-tracker.md`.\n'
                                    'Triage labels: defaults.\n')


WRITE = re.compile(r'^(?:issue (?:edit|comment|close|reopen|create|delete|transfer|lock|unlock|pin|unpin|develop)'
                   r'|label (?:create|edit|delete|clone)|pr (?!list\b|view\b|status\b|diff\b|checks\b)\S+)')
# A direct gh write in the agent's own command bypasses the tracker contract in tickets.sh.
# gh api treats field flags as a POST unless the command says GET, and ./bin/gh is the same double.
DIRECT = re.compile(r'(?:^|[\s;&|(`$/"\'])gh\s+(?:issue\s+(?:edit|comment|close|reopen|create)\b|label\s+create\b'
                    r'|api\b[^\n]*(?:--method|-X)\s*=?\s*(?:POST|PATCH|PUT|DELETE)\b'
                    r'|api\b(?![^\n]*(?:--method|-X)\s*=?\s*GET\b)[^\n]*\s(?:-[fF]|--field|--raw-field)(?:\s|=))')


def is_write(args):
    if args[:1] == ['api']:
        method = None
        for i, token in enumerate(args):
            if token in ('--method', '-X') and i + 1 < len(args):
                method = args[i + 1].upper()
            elif token.startswith('--method='):
                method = token.split('=', 1)[1].upper()
        fields = any(t in ('-f', '-F', '--field', '--raw-field') or t.startswith(('--field=', '--raw-field=')) for t in args)
        return (method or ('POST' if fields else 'GET')) != 'GET'
    return bool(WRITE.match(' '.join(args[:2])))


def section(body, heading):
    m = re.search(r'(?ms)^## ' + re.escape(heading) + r'[ \t]*\n(.*?)(?=^## |\Z)', body)
    return m.group(1).strip() if m else None


def has_line(body, pattern):
    return any(re.fullmatch(pattern, line.strip()) for line in body.replace('\r', '').split('\n'))


def grade_build_fixture(case, work, baseline, response, commands):
    if case['fixture'] != 'build-parent':
        return []
    try:
        tracker = json.loads((work / 'artifacts/tracker.json').read_text())
        issues = tracker['issues']
    except (OSError, ValueError, KeyError, TypeError):
        return ['tracker state unreadable']
    calls_path = work / 'artifacts/gh-events.jsonl'
    try:
        calls = [json.loads(line) for line in calls_path.read_text().splitlines()] if calls_path.exists() else []
    except ValueError:
        return ['tracker call log unreadable']
    failures = []
    before = baseline['tracker']['issues']
    report = response['report']
    if not any(c[:1] == ['api'] and not is_write(c) and any(re.search(r'issues/' + PARENT + r'/sub_issues$', t) for t in c)
               for c in calls):
        failures.append('build members never enumerated')
    if any(DIRECT.search(c.get('command', '')) for c in commands):
        failures.append('tracker write bypassed tickets.sh')
    if re.search(r'Implement\s+\S*issues/' + UNRELATED + r'\b', report):
        failures.append('next action names unrelated global work')
    if case['expected_status'] == 'leftover-report':
        if tracker != baseline['tracker']:
            failures.append('tracker mutated in read-only run')
        if any(is_write(c) for c in calls):
            failures.append('tracker write attempted in read-only run')
        if CLOSEOUT not in re.sub(r'\s+', ' ', report):
            failures.append('read-only close-out prompt missing')
        # The close-out prompt itself says "reopening or filing tickets", so each action must be named on its own line.
        lower = re.sub(r'[ \t]+', ' ', report).lower().replace(CLOSEOUT.lower(), '')
        owner = r'(?:#|issues/)' + OWNER + r'\b'
        reopen = re.search(r'reopen[^\n]*' + owner + '|' + owner + r'[^\n]*reopen', lower)
        create = (re.search(r'\b(?:file|create)\b[^\n]*\b(?:ticket|member|issue)\b', lower)
                  and CATEGORY in lower and 'build parent' in lower)
        if not ((reopen or create) and 'agent brief' in lower and READY in lower):
            failures.append('exact leftover actions not reported')
        return failures
    parent = issues.get(PARENT, {})
    if parent.get('state') != 'OPEN':
        failures.append('build parent closed with unmet evidence')
    body = parent.get('body', '')
    if not body.startswith('Work kind: build') or section(body, 'Destination') != section(before[PARENT]['body'], 'Destination'):
        failures.append('build parent body lost its marker or Destination')
    order = section(body, 'Build order') or ''
    if any(URL + '/issues/' + n not in order for n in (LAYOUT, OWNER)):
        failures.append('existing Build order entries lost')
    if any(re.search(r'(?im)^\W*completion\b', c['body']) for c in parent.get('comments', [])[len(before[PARENT]['comments']):]):
        failures.append('completion recorded with unmet evidence')
    reopened = issues.get(OWNER, {}).get('state') == 'OPEN'
    for n, d in before.items():
        now = issues.get(n, {})
        if n == OWNER and reopened:
            continue
        if (n != PARENT and now.get('state') != d['state']) or now.get('labels') != d['labels']:
            failures.append('ticket state or labels changed: ' + n)
        if now.get('assignees') != d['assignees']:
            failures.append('ticket claimed or released: ' + n)
    filed = [n for n in issues if n not in before]
    if reopened and filed:
        failures.append('unmet evidence ticketed twice')
    elif not reopened and not filed:
        failures.append('unmet evidence left without an open ticket')
    ticket = OWNER if reopened else (filed[0] if len(filed) == 1 else None)
    if reopened:
        owner = issues[OWNER]
        new = owner['comments'][len(before[OWNER]['comments']):]
        if not any(has_line(c['body'], r'## Agent Brief') for c in new):
            failures.append('reopened ticket has no new agent brief')
        if owner['assignees']:
            failures.append('reopened ticket kept its assignee')
        if READY not in owner['labels']:
            failures.append('reopened ticket lacks the ready label')
        names = (OWNER, URL + '/issues/' + OWNER)
        comment = next((i for i, c in enumerate(calls) if c[:2] == ['issue', 'comment']
                        and any(x in c for x in names) and '## Agent Brief' in ' '.join(c)), None)
        reopen = next((i for i, c in enumerate(calls) if c[:2] == ['issue', 'reopen']
                       and any(x in c for x in names)), None)
        if comment is None or reopen is None or comment > reopen:
            failures.append('brief not posted before reopening')
    elif len(filed) > 1:
        failures.append('more than one ticket filed for one unmet evidence item')
    elif filed:
        d = issues[ticket]
        lines = d.get('body', '')
        if d.get('state') != 'OPEN' or d.get('assignees'):
            failures.append('filed ticket not open and unclaimed')
        if not has_line(lines, r'Build parent: \[[^\]]+\]\(' + re.escape(PARENT_URL) + r'\)'):
            failures.append('filed ticket lacks Build parent line')
        if not has_line(lines, r'Planning source: \[[^\]]+\]\(' + re.escape(URL + '/issues/' + MAP) + r'\)'):
            failures.append('filed ticket lacks Planning source line')
        if not has_line(lines, r'## Agent Brief'):
            failures.append('filed ticket has no agent brief')
        if CATEGORY not in d.get('labels', []) or READY not in d.get('labels', []):
            failures.append('filed ticket lacks category or ready label')
        if d.get('parent') != PARENT:
            failures.append('filed ticket not natively attached')
        if URL + '/issues/' + ticket not in order:
            failures.append('filed ticket missing from Build order')
    if ticket and not re.search(r'Implement\s+' + re.escape(URL + '/issues/' + ticket) + r',\s+following its brief\.', report):
        failures.append('next action does not name the leftover ticket')
    return failures
