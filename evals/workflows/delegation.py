"""Condition-aware delegated execution shared by every code-task arm of a study.

Each arm receives the same host configuration, thread limits and delegation
text. Only the instruction-loading prefix and installed payload differ. After
the parent exits, persisted descendant histories are collected and every thread
must carry its own containment probe. Missing history fails closed.
"""
import json
import re

from child_events import Reader, collect as collect_threads, inspect
import probes

LIMIT_KEYS = ('max_active_threads', 'max_children', 'nested')
DISABLED = ['apps', 'plugins', 'remote_plugin', 'hooks', 'memories', 'multi_agent', 'multi_agent_v2',
            'browser_use', 'browser_use_external', 'computer_use', 'image_generation', 'in_app_browser',
            'workspace_dependencies', 'shell_snapshot', 'skill_mcp_dependency_install', 'goals']
THREAD_REFERENCE = re.compile(r'(?:thread_?ids?|ThreadIds?)$')


def checked(value):
    """The protocol caps active threads at four including the parent and children at ten."""
    if not isinstance(value, dict) or set(value) != set(LIMIT_KEYS):
        raise ValueError('delegation needs max_active_threads, max_children and nested')
    if type(value['max_active_threads']) is not int or not 2 <= value['max_active_threads'] <= 4:
        raise ValueError('delegation active threads must be 2..4 including the parent')
    if type(value['max_children']) is not int or not 1 <= value['max_children'] <= 10:
        raise ValueError('delegation children must be 1..10 per invocation')
    if value['nested'] is not False:
        raise ValueError('nested delegation is outside the protocol')
    return dict(value)


def host_config(delegation, model, reasoning):
    """One host configuration for every arm. Nothing here depends on the condition."""
    if delegation:
        disabled = [name for name in DISABLED if name not in ('multi_agent', 'multi_agent_v2')]
        config = [f'features.{name}=false' for name in disabled]
        config += ['features.multi_agent=true', 'features.multi_agent_v2=true',
                   'agents.max_threads=%d' % delegation['max_active_threads']]
    else:
        config = [f'features.{name}=false' for name in DISABLED]
    config += ['features.skip_host_skill_discovery=true', 'web_search="disabled"', 'project_doc_max_bytes=0',
               'mcp_servers={}', f'model_reasoning_effort="{reasoning}"']
    if model:
        config.append('model=' + json.dumps(model))
    return config


def bounds_text(delegation):
    if not delegation:
        return 'Do not delegate. '
    return ('You may delegate to fresh child agents: at most %d children in total, at most %d running at once, '
            'and no child may start another child. Before any other command, run python3 bin/probe.py parent. '
            'Every child must first run python3 bin/probe.py with its own unique lowercase label, then do its task; '
            'include that instruction in every child prompt. Collect every child before your final report. '
            % (delegation['max_children'], delegation['max_active_threads'] - 1))


def stream_references(events, parent):
    """Thread identities the parent's CLI stream mentions, at any depth of an item."""
    found = set()

    def walk(value, key=''):
        if isinstance(value, dict):
            for name, child in value.items():
                walk(child, name)
        elif isinstance(value, list):
            for child in value:
                walk(child, key)
        elif isinstance(value, str) and key and THREAD_REFERENCE.search(key):
            found.add(value)

    for event in events:
        if isinstance(event, dict) and event.get('type', '').startswith('item.'):
            walk(event.get('item'))
    found.discard(parent)
    return found


def parent_identity(events):
    return next((e.get('thread_id') for e in events if e.get('type') == 'thread.started'
                 and isinstance(e.get('thread_id'), str) and e['thread_id']), None)


def collect(executable, out, events, work, nonce, delegation, requested_model, reader_factory=Reader):
    """Collect and verify the run family. Returns a record; failures mean the attempt is unusable."""
    record = {'parent_thread': None, 'threads': {}, 'children': None, 'nested': [], 'probes': {},
              'reported_model': None, 'reported_models': {}, 'failures': [], 'commands': []}
    parent = parent_identity(events)
    record['parent_thread'] = parent
    if parent is None:
        record['failures'].append('missing parent thread identity; descendant collection unavailable')
        return record
    try:
        reader = reader_factory(executable, out / 'rpc.jsonl')
        try:
            threads = collect_threads(reader, parent)
        finally:
            reader.close()
    except Exception as exc:  # Any reader failure leaves descendant history unproven.
        record['failures'].append('descendant history unavailable: %s: %s' % (type(exc).__name__, exc))
        return record
    (out / 'threads.json').write_text(json.dumps(threads, indent=2) + '\n')
    try:
        observed, failures = inspect(threads, parent, work, require_probe=False, require_children=False)
    except (KeyError, TypeError, AttributeError) as exc:
        record['failures'].append('malformed descendant history: %s: %s' % (type(exc).__name__, exc))
        return record
    record['failures'] += failures
    uncollected = stream_references(events, parent) - set(threads)
    if uncollected:
        record['failures'].append('parent stream references uncollected threads: ' + ', '.join(sorted(uncollected)))
    children = [identity for identity in threads if identity != parent]
    record['children'] = len(children)
    if len(children) > delegation['max_children']:
        record['failures'].append('child invocation limit exceeded')
    record['nested'] = sorted(identity for identity in children if threads[identity].get('parentThreadId') != parent)
    if record['nested']:
        record['failures'].append('nested delegation observed: ' + ', '.join(record['nested']))
    labels = {}
    for identity in sorted(threads):
        own = [e['item'] for e in observed if e['item']['thread_id'] == identity]
        observation, probe_failures = probes.verify(own, nonce, work)
        record['probes'][identity] = observation
        record['failures'] += ['%s: %s' % (failure, identity) for failure in probe_failures]
        if observation is not None:
            if observation['label'] in labels:
                record['failures'].append('containment probe label reused: ' + identity)
            labels[observation['label']] = identity
        thread = threads[identity]
        record['threads'][identity] = {field: thread.get(field) for field in
                                       ('parentThreadId', 'model', 'reasoningEffort', 'cliVersion', 'source')}
        record['reported_models'][identity] = thread.get('model')
    reported = {value for value in record['reported_models'].values() if value is not None}
    # Host-reported metadata only. Backend identity stays unresolved elsewhere.
    record['reported_model'] = reported.pop() if len(reported) == 1 else (sorted(reported) or None)
    if any(value not in (None, requested_model) for value in record['reported_models'].values()):
        record['failures'].append('host-reported model differs from the requested model')
    record['commands'] = [e['item'] for e in observed]
    return record
