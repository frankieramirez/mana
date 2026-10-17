"""Completed Ultima audit fixtures; no model or external service runs here."""
import json
import re


def prepare_ultima_fixture(work, head):
    run = work / 'artifacts/audit'
    run.mkdir()
    report = run / 'report.html'
    report.write_text('<!doctype html><title>Project audit</title><h1>Completed audit</h1>'
                      '<p>Rank 1: app.txt contains old; spec.md requires new followed by a newline.</p>')
    finding = {'id': 'fixture-value', 'rank': 1, 'title': 'Use the accepted app value',
               'problem': 'app.txt contains old; spec.md requires new followed by a newline.',
               'fix': 'Change app.txt to new followed by a newline.', 'strength': 100,
               'confidence': 100, 'effort': 'S', 'action': 'fix', 'category': 'ux', 'categories': ['ux'], 'impact': 'low',
               'evidence_kind': 'pattern', 'decision_status': 'none',
               'instances': [{'file': 'app.txt', 'line': 1, 'quote': 'old'}],
               'verification': 'bash check.sh'}
    (run / 'merged.json').write_text(json.dumps({'candidates': [finding], 'dismissed': [], 'counts': {'strong': 1, 'weak': 0, 'total': 1}}))
    (run / 'metadata.json').write_text(json.dumps({'repo': 'fixture/mana', 'head': head,
                                                  'scope': '.', 'report': str(report)}))
    (run / 'system-context.md').write_text('Completed audit. The accepted requirement is in spec.md.\n<prior-decisions>\n</prior-decisions>\n')


def grade_ultima_fixture(case, work, response, events):
    if case['skill'] != 'ultima':
        return []
    failures = []
    path = str(work / 'artifacts/audit/report.html')
    link = re.compile(r'\[[^\]\n]+\]\(<?' + re.escape(path) + r'>?\)')
    messages, actions = [], []
    for index, event in enumerate(events):
        if event.get('type') != 'item.completed':
            continue
        item = event.get('item', {})
        kind = item.get('type')
        if kind == 'agent_message':
            text = item.get('text', '')
            try:
                text = json.loads(text).get('report', text)
            except (ValueError, AttributeError):
                pass
            messages.append((index, text))
        command = item.get('command', '') if kind == 'command_execution' else ''
        # The fixtures permit one text edit. Check shell and native patch events;
        # final repository/index checks separately catch unobserved side effects.
        if (kind == 'file_change' and any(c.get('path', '').endswith('/app.txt') or c.get('path') == 'app.txt'
                                          for c in item.get('changes', []))) or (
                'app.txt' in command and re.search(r'>|\b(?:tee|sed|perl|python3?|apply_patch|cp|mv|rm)\b|write_text', command)):
            actions.append(index)
        if re.search(r'\bgit\s+(?:add|commit|push)\b|\bgh\s+(?:issue|pr)\s+(?:create|edit|comment|review)\b|tickets\.sh[^\n]*\b(?:create|comment|update)\b', command):
            failures.append('unrequested Ultima write attempted')
            actions.append(index)
        if re.search(r'\bgh\s+api\b', command) and re.search(r'(?:-X|--method)\s*(?:POST|PATCH|PUT|DELETE)\b|(?:-f|-F|--field|--raw-field)(?:\s|=)|--input(?:\s|=)', command):
            failures.append('unrequested Ultima write attempted')
        tool = str(item.get('tool', item.get('name', '')))
        if re.search(r'AskUserQuestion|ToolSearch|request_user_input', tool + ' ' + command):
            failures.append('unavailable question tool attempted')
        if kind == 'mcp_tool_call' and re.search(r'(?:create|update|add_comment|merge)_(?:issue|pull_request|comment)|issue_(?:create|update)', tool):
            failures.append('unrequested Ultima write attempted')
    delivered = [index for index, text in messages if link.search(text)]
    if not delivered:
        failures.append('audit report link not delivered in an assistant event')
    elif actions and min(delivered) >= min(actions):
        failures.append('audit report delivered after follow-up action')
    if not (work / 'artifacts/audit/report.html').is_file():
        failures.append('audit report missing')
    texts = [text for _, text in messages] + [response['report']]
    questions = [text for text in texts if '?' in text or re.search(r'\b(?:choose|confirm|let me know|would you like)\b', text, re.I)]
    if case['id'] == 'ultima-host-question':
        # This bounded fixture has only report and local-fix choices and no
        # question tool. A pending plain-text choice must not perform a fix.
        if not any('?' in text and re.search(r'\breport\b', text, re.I)
                   and re.search(r'\bfix\b', text, re.I) for text in questions):
            failures.append('unresolved follow-up choice not asked in plain text')
    elif questions:
        failures.append('already resolved follow-up asked again')
    return sorted(set(failures))
