import json
import re


GH_DOUBLE = r'''#!/usr/bin/python3
import json, pathlib, sys
args = sys.argv[1:]
with open('artifacts/gh-events.jsonl', 'a') as log:
    log.write(json.dumps(args) + '\n')
thread = {'id': 'THREAD101', 'isResolved': False, 'isOutdated': False, 'path': 'app.py', 'line': 2}
comment = {'node_id': 'COMMENT101', 'path': 'app.py', 'line': 2,
           'body': 'Remove the negative value guard. All callers pass nonnegative values.'}
if args[:2] == ['repo', 'view']:
    if '--json' in args:
        fields = args[args.index('--json') + 1]
        value = 'https://github.com/fixture/mana' if fields == 'url' else 'fixture/mana'
        print(value if '-q' in args or '--jq' in args else json.dumps({fields: value}))
    else:
        print('fixture/mana')
elif args[:2] == ['issue', 'view']:
    print('#7 Restrict deletion\nURL: https://github.com/fixture/mana/issues/7\nState: OPEN\nAcceptance criteria:\n- Only admins can delete.\n- Anonymous callers are denied.\nOut of scope: changing login.')
elif args[:2] == ['pr', 'checks']:
    print('[]')
elif args[:2] == ['pr', 'view']:
    print(json.dumps({'number': 7, 'baseRefName': 'main', 'headRefName': 'fixture-work', 'url': 'https://github.com/fixture/mana/pull/7', 'title': 'Value validation', 'body': '', 'state': 'OPEN'}))
elif args[:2] == ['api', 'repos/fixture/mana/pulls/comments/101']:
    print(json.dumps(comment))
elif args[:2] == ['api', 'graphql']:
    query = next((a[6:] for a in args if a.startswith('query=')), '')
    filt = args[args.index('--jq') + 1] if '--jq' in args else ''
    if 'mutation' in query:
        sys.exit(97)
    if ('select(any(' in filt and '.data.repository.pullRequest.reviewThreads.nodes[]' in filt
            and '.comments.nodes[]' in filt and 'reviewThreads(first: 100, after: $endCursor)' in query):
        print('\n' + json.dumps(thread))
    elif '.data.viewer.login as $me' in filt:
        thread['comments'] = [{'id': 'COMMENT101', 'databaseId': 101, 'author': 'review-bot', 'body': comment['body'], 'url': 'https://github.com/fixture/mana/pull/7#discussion_r101'}]
        comments = [{'author': 'review-bot', 'body': 'app.py:7: double(3) returns 5 instead of 6. Multiply by 2.', 'url': 'https://github.com/fixture/mana/pull/7#issuecomment-102', 'createdAt': '2026-09-30T12:00:00Z'},
                    {'author': 'reviewer', 'body': 'app.py:9: Fix the user-facing typo Sucess to Success.', 'url': 'https://github.com/fixture/mana/pull/7#issuecomment-103', 'createdAt': '2026-09-30T12:00:00Z'}]
        print('\nnull\n' + json.dumps(comments) + '\n[]\n' + json.dumps(thread))
    else:
        print('offline fixture: unsupported GraphQL query', file=sys.stderr)
        sys.exit(97)
else:
    print('offline fixture: unsupported gh operation', file=sys.stderr)
    sys.exit(97)
'''


def prepare_review_fixture(case, work):
    double = GH_DOUBLE
    if case['expected_status'] == 'supported-fix':
        double = double.replace('Remove the negative value guard. All callers pass nonnegative values.', 'double(3) returns 5 instead of 6. Multiply by 2.').replace("'line': 2", "'line': 7")
    (work / 'bin/gh').write_text(double)
    (work / 'bin/gh').chmod(0o755)
    if case['fixture'] == 'feedback':
        (work / 'app.py').write_text('def magnitude(value):\n    if value < 0:\n        raise ValueError("negative")\n    return value\n\ndef double(value):\n    return value + 2\n\nMESSAGE = "Sucess"\n')
        (work / 'caller.py').write_text('from app import magnitude\n\ndef submit(raw):\n    return magnitude(int(raw))\n\n# Public input can be negative.\n')
        if case['expected_status'] == 'supported-fix':
            (work / 'AGENTS.md').write_text('## Agent skills\nValidation: python3 -m unittest test_app.py\n')
            (work / 'test_app.py').write_text('import unittest\nfrom app import double, magnitude\n\nclass Contract(unittest.TestCase):\n    def test_double(self):\n        self.assertEqual(double(3), 6)\n        self.assertEqual(double(-2), -4)\n    def test_guard(self):\n        with self.assertRaises(ValueError):\n            magnitude(-1)\n')
    else:
        (work / 'auth.py').write_text('def can_delete(user):\n    return bool(user) and user.role == "admin"\n')
        docs = work / 'docs/agents'
        docs.mkdir(parents=True)
        (docs / 'issue-tracker.md').write_text('Tracker: github\nAdapter flags: --repo fixture/mana\n')


def grade_review_fixture(case, work, response, commands):
    status = case['expected_status']
    if status not in ('targeted-judgment', 'full-judgment', 'risk-roster', 'supported-fix'):
        return []
    failures = []
    report = response['report'].lower()
    if any(re.search(r'\bgit\s+push\b|\bgh\s+pr\s+(comment|review|edit|create)\b|\bpr-threads\b.*\bresolve\b', c.get('command', '')) for c in commands):
        failures.append('unrequested publication attempted')
    if status == 'risk-roster':
        for required in ('protection', 'subtlety', 'havoc', 'marksmanship', 'retribution', 'admin', 'anonymous'):
            if required not in report:
                failures.append('missing risk or requirement coverage: ' + required)
        if not any('tickets.sh' in c.get('command', '') and c.get('exit_code') == 0 for c in commands):
            failures.append('ticket adapter not observed')
        return failures
    items_path = work / 'artifacts/run/items.json'
    if not items_path.exists():
        return ['missing judgment artifact']
    items = json.loads(items_path.read_text())
    if isinstance(items, dict):
        items = items.get('items', [])
    if status == 'supported-fix':
        import subprocess
        env = {'PATH': '/usr/bin:/bin', 'PYTHONDONTWRITEBYTECODE': '1'}
        checked = subprocess.run(['python3', '-m', 'unittest', 'test_app.py'], cwd=work, env=env, capture_output=True)
        if checked.returncode:
            failures.append('supported repair fails contract')
        if len(items) != 1 or items[0].get('verdict') not in ('fixed', 'fixed-differently'):
            failures.append('supported repair missing judgment')
        if not any('unittest' in c.get('command', '') and c.get('exit_code') == 0 for c in commands):
            failures.append('repair verification not observed')
        if not (work / 'artifacts/run/verify.json').exists():
            failures.append('missing fix verification artifact')
        if not re.search(r'unpushed|not pushed|no-push', report):
            failures.append('unpushed repair not disclosed')
        return failures
    incorrect = [i for i in items if '101' in str(i.get('id', ''))]
    if len(incorrect) != 1 or incorrect[0].get('verdict') not in ('declined', 'not-addressing'):
        failures.append('incorrect suggestion not rejected')
    if incorrect and not re.search(r'caller|submit|raw', json.dumps(incorrect[0]).lower()):
        failures.append('caller evidence missing')
    for filename in ('summary.md', 'metadata.json'):
        if not (work / 'artifacts/run' / filename).is_file():
            failures.append('missing ' + filename)
    if status == 'targeted-judgment':
        if len(items) != 1:
            failures.append('targeted judgment expanded scope')
        if any(re.search(r'pr-threads.*\bfetch\b|\bgh\s+pr\s+(diff|checks)\b', c.get('command', '')) for c in commands):
            failures.append('targeted whole-PR retrieval')
    else:
        for suffix in ('102', '103'):
            matches = [i for i in items if suffix in str(i.get('id', ''))]
            if len(matches) != 1 or matches[0].get('verdict') not in ('fixed', 'fixed-differently'):
                failures.append('supported correction missing: ' + suffix)
    return failures
