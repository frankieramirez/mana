#!/usr/bin/env python3
"""Offline stand-in for the Codex CLI surfaces the evaluator uses. Never calls a model.

Tests copy this file as an executable named `codex` and describe its behavior
in a JSON plan named by MANA_FAKE_HOST_PLAN. With containment `enforced`, the
fake honors the declared `permissions.mana-eval` filesystem table and network
flag for Python commands through an audit hook, so probe results come from
real attempted operations. With `leaky`, it runs them unrestricted.
"""
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time

PLAN = json.loads(Path(os.environ['MANA_FAKE_HOST_PLAN']).read_text())
STATE = Path(PLAN['state'])

PRELUDE = r'''
import os as _os, sys as _sys
_TABLE = %(table)r
_NETWORK = %(network)r
_MINIMAL = ('/usr', '/lib', '/lib64', '/etc', '/proc', '/dev', _sys.base_prefix, _sys.prefix)
def _inside(path, root):
    root = root.rstrip('/') or '/'
    return path == root or path.startswith(root + '/')
def _mode(path):
    best, mode = '', _TABLE.get(':root', 'deny')
    for key, value in _TABLE.items():
        if not key.startswith(':') and _inside(path, key) and len(key) > len(best):
            best, mode = key, value
    if not best and _TABLE.get(':minimal') == 'read' and any(_inside(path, m) for m in _MINIMAL):
        mode = 'read'
    return mode
def _hook(event, args):
    if event == 'open':
        path, mode, flags = args
        if path is None or isinstance(path, int):
            return
        real = _os.path.abspath(_os.fsdecode(path))
        writing = bool(isinstance(flags, int) and flags & (_os.O_WRONLY | _os.O_RDWR | _os.O_CREAT | _os.O_APPEND)) \
            or (isinstance(mode, str) and any(c in mode for c in 'wax+'))
        granted = _mode(real)
        if granted == 'deny' or (writing and granted != 'write'):
            raise PermissionError(13, 'fake sandbox denied', real)
    elif event == 'socket.connect' and not _NETWORK:
        raise PermissionError(13, 'fake sandbox network denied')
_sys.addaudithook(_hook)
# Metadata lookups are not audited, so wrap them to hide denied paths as a sandbox would.
def _hidden(original):
    def stat(path, *args, **kwargs):
        if not isinstance(path, int) and _mode(_os.path.abspath(_os.fsdecode(path))) == 'deny':
            raise FileNotFoundError(2, 'fake sandbox hides this path', path)
        return original(path, *args, **kwargs)
    return stat
_os.stat = _hidden(_os.stat)
_os.lstat = _hidden(_os.lstat)
'''


def options(argv):
    found = {'configs': [], 'cwd': None, 'output': None, 'ephemeral': False, 'rest': []}
    index = 0
    while index < len(argv):
        arg = argv[index]
        if arg == '-c':
            found['configs'].append(argv[index + 1])
            index += 2
        elif arg == '-C':
            found['cwd'] = argv[index + 1]
            index += 2
        elif arg in ('-o', '--output-schema', '--color', '-P'):
            if arg == '-o':
                found['output'] = argv[index + 1]
            index += 2
        elif arg == '--ephemeral':
            found['ephemeral'] = True
            index += 1
        elif arg == '--':
            found['rest'] = argv[index + 1:]
            break
        else:
            index += 1
    return found


def policy(configs):
    table, network = {':root': 'deny'}, True
    for value in configs:
        if value.startswith('permissions.mana-eval.filesystem='):
            for key, mode in re.findall(r'("(?:[^"\\]|\\.)*")=("(?:read|write|deny)")', value):
                table[json.loads(key)] = json.loads(mode)
        if value == 'permissions.mana-eval.network.enabled=false':
            network = False
    return table, network


def python_command(args, configs, cwd):
    """Run python3 -c CODE or python3 SCRIPT ARGS, contained when the plan says so."""
    if args[1] == '-c':
        body = args[2]
    else:
        body = 'import runpy, sys\nsys.argv = %r\nrunpy.run_path(%r, run_name="__main__")\n' % (args[1:], args[1])
    if PLAN.get('containment', 'enforced') == 'enforced':
        table, network = policy(configs)
        body = PRELUDE % {'table': table, 'network': network} + body
    return subprocess.run(['/usr/bin/python3', '-c', body], cwd=cwd, capture_output=True, text=True)


def run_command(command, configs, cwd):
    words = command.split()
    if words and words[0] in ('python3', '/usr/bin/python3') and len(words) > 1:
        result = python_command(words, configs, cwd)
    else:
        result = subprocess.run(['/bin/sh', '-c', command], cwd=cwd, capture_output=True, text=True)
    return result.stdout + result.stderr, result.returncode


def daemonize(pidfile):
    """A grandchild that leaves the host session, as a misbehaving tool command could."""
    if os.fork() == 0:
        os.setsid()
        if os.fork() == 0:
            Path(pidfile).write_text(str(os.getpid()))
            time.sleep(600)
            os._exit(0)
        os._exit(0)


def emit(event):
    if PLAN.get('malformed_event_after') == event.get('type'):
        print('{"type": "item.completed"', flush=True)
    print(json.dumps(event), flush=True)


def execute(argv):
    opts = options(argv)
    prompt = sys.stdin.read()
    STATE.mkdir(parents=True, exist_ok=True)
    calls = sorted(STATE.glob('exec-*.json'))
    (STATE / ('exec-%03d.json' % len(calls))).write_text(json.dumps({'argv': argv, 'prompt': prompt, 'options': opts}))
    work = opts['cwd']
    if PLAN.get('hang'):
        daemonize(PLAN['daemon_pidfile'])
        sleeper = subprocess.Popen(['/bin/sleep', '600'])
        Path(PLAN['sleeper_pidfile']).write_text(str(sleeper.pid))
        time.sleep(600)
    parent = PLAN.get('parent_id', 'thread-parent')
    model = PLAN.get('reported_model')
    if not PLAN.get('omit_thread_started'):
        emit({'type': 'thread.started', 'thread_id': parent})
    emit({'type': 'turn.started'})
    threads = {}
    parent_items = []
    parent_started = time.time()
    for index, command in enumerate(PLAN.get('parent', {}).get('commands', [])):
        output, code = run_command(command, opts['configs'], work)
        item = {'id': 'item-%d' % index, 'type': 'command_execution', 'command': command,
                'aggregated_output': output, 'exit_code': code, 'status': 'completed' if code == 0 else 'failed'}
        emit({'type': 'item.completed', 'item': item})
        parent_items.append({'type': 'commandExecution', 'id': item['id'], 'command': command,
                             'aggregatedOutput': output, 'exitCode': code, 'status': item['status']})
    # Children run one after another for real; their recorded timing models the host's
    # agents.max_threads scheduling. `children` counts only child threads, `including_parent`
    # also counts the parent, and `ignore` lets every child open at once.
    configured = next((int(v.split('=', 1)[1]) for v in opts['configs'] if v.startswith('agents.max_threads=')), None)
    mode = PLAN.get('cap_mode', 'children')
    slots = len(PLAN.get('children', [])) or 1
    if configured is not None and mode != 'ignore':
        slots = max(1, configured - (1 if mode == 'including_parent' else 0))
    for number, child in enumerate(PLAN.get('children', [])):
        identity = child.get('id', 'thread-child-%d' % number)
        owner = child.get('parent', parent)
        items = []
        child_started = parent_started + 1 + (number // slots) * 10
        for index, command in enumerate(child.get('commands', [])):
            output, code = run_command(command, opts['configs'], work)
            items.append({'type': 'commandExecution', 'id': 'item-%d' % index, 'command': command,
                          'aggregatedOutput': output, 'exitCode': code, 'status': 'completed' if code == 0 else 'failed'})
        items.append({'type': 'agentMessage', 'phase': 'final_answer', 'text': 'child done'})
        threads[identity] = {'id': identity, 'parentThreadId': owner, 'cwd': work, 'model': child.get('model', model),
                             'reasoningEffort': 'medium', 'cliVersion': PLAN['version'], 'source': 'subAgent',
                             'turns': [{'id': 'turn-1', 'status': child.get('turn_status', 'completed'),
                                        'itemsView': 'full', 'items': items,
                                        'startedAt': child_started, 'completedAt': child_started + 9}],
                             'drop': child.get('drop')}
        activity = {'type': 'subAgentActivity', 'agentThreadId': identity, 'kind': 'started'}
        if owner == parent:
            parent_items.append(activity)
        elif owner in threads:
            threads[owner]['turns'][0]['items'].insert(0, activity)
        if child.get('stream_reference'):
            emit({'type': 'item.completed', 'item': {'id': 'spawn-%d' % number, 'type': 'collab_tool_call',
                                                      'receiver_thread_ids': [identity]}})
    parent_items.append({'type': 'agentMessage', 'phase': 'final_answer', 'text': 'parent done'})
    threads[parent] = {'id': parent, 'parentThreadId': None, 'cwd': work, 'model': model, 'reasoningEffort': 'medium',
                       'cliVersion': PLAN['version'], 'source': 'exec',
                       'turns': [{'id': 'turn-1', 'status': 'completed', 'itemsView': 'full', 'items': parent_items,
                                  'startedAt': parent_started,
                                  'completedAt': parent_started + 2 + (len(PLAN.get('children', [])) // slots + 1) * 10}]}
    if not opts['ephemeral']:
        (STATE / 'threads.json').write_text(json.dumps(threads))
    if not PLAN.get('omit_usage'):
        emit({'type': 'turn.completed', 'usage': {'input_tokens': 10, 'output_tokens': 2}})
    if opts['output'] and 'response' in PLAN:
        Path(opts['output']).write_text(json.dumps(PLAN['response']))
    return PLAN.get('exit_code', 0)


def sandbox(argv):
    opts = options(argv)
    rest = opts['rest']
    if rest and rest[0].endswith('python3') and len(rest) > 1:
        result = python_command(rest, opts['configs'], opts['cwd'])
        sys.stdout.write(result.stdout)
        sys.stderr.write(result.stderr)
        return result.returncode
    print('fake sandbox supports python3 commands only', file=sys.stderr)
    return 97


def app_server():
    threads = json.loads((STATE / 'threads.json').read_text()) if (STATE / 'threads.json').is_file() else {}
    for line in sys.stdin:
        message = json.loads(line)
        if 'id' not in message:
            continue
        method, params = message['method'], message.get('params', {})
        result, error = None, None
        if method == 'initialize':
            result = {}
        elif method == 'thread/list':
            data = []
            if not params.get('archived'):
                ancestor = params['ancestorThreadId']
                for identity, thread in threads.items():
                    owner, seen = thread.get('parentThreadId'), set()
                    while owner and owner != ancestor and owner not in seen:
                        seen.add(owner)
                        owner = threads.get(owner, {}).get('parentThreadId')
                    if owner == ancestor and thread.get('drop') != 'list':
                        data.append({'id': identity})
            result = {'data': data, 'nextCursor': None}
        elif method == 'thread/read':
            thread = threads.get(params['threadId'])
            if thread is None or thread.get('drop') == 'read':
                error = {'code': -32600, 'message': 'thread history unavailable'}
            else:
                result = {'thread': {k: v for k, v in thread.items() if k not in ('turns', 'drop')}}
        elif method == 'thread/turns/list':
            thread = threads.get(params['threadId'])
            if thread is None:
                error = {'code': -32600, 'message': 'thread history unavailable'}
            else:
                result = {'data': thread['turns'], 'nextCursor': None}
        else:
            error = {'code': -32601, 'message': 'unsupported method'}
        reply = {'id': message['id'], 'error': error} if error else {'id': message['id'], 'result': result}
        print(json.dumps(reply), flush=True)
    return 0


def main(argv):
    if argv == ['--version']:
        print(PLAN['version'])
        return 0
    if argv[:1] == ['exec']:
        return execute(argv[1:])
    if argv[:1] == ['sandbox']:
        return sandbox(argv[1:])
    if argv[:1] == ['app-server']:
        return app_server()
    print('fake host: unsupported invocation', file=sys.stderr)
    return 97


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
