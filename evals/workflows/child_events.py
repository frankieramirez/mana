"""Read saved CLI descendants through the documented app-server JSON-RPC API.

This module never starts or resumes model turns. Missing history fails closed.
"""
import json
import queue
import subprocess
import threading
import time


class Reader:
    def __init__(self, executable, transcript, timeout=20):
        self.log = transcript.open('w')
        self.stderr = transcript.with_suffix('.stderr.txt').open('w')
        self.timeout = timeout
        self.serial = 0
        self.messages = queue.Queue()
        self.process = subprocess.Popen([str(executable), 'app-server', '--listen', 'stdio://'],
                                        stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                        stderr=self.stderr, text=True)
        def read():
            for line in self.process.stdout:
                self.messages.put(line)
            self.messages.put(None)
        threading.Thread(target=read, daemon=True).start()
        try:
            self.call('initialize', {'clientInfo': {'name': 'mana_eval_reader', 'version': '1'},
                                     'capabilities': {'experimentalApi': True}})
            self.send({'method': 'initialized'})
        except Exception:
            self.close()
            raise

    def send(self, message):
        self.log.write(json.dumps({'direction': 'request', 'message': message}) + '\n')
        self.log.flush()
        self.process.stdin.write(json.dumps(message) + '\n')
        self.process.stdin.flush()

    def call(self, method, params):
        self.serial += 1
        self.send({'id': self.serial, 'method': method, 'params': params})
        deadline = time.monotonic() + self.timeout
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError('app-server response deadline exceeded')
            line = self.messages.get(timeout=remaining)
            if line is None:
                raise ValueError('app-server closed before response')
            message = json.loads(line)
            self.log.write(json.dumps({'direction': 'response', 'message': message}) + '\n')
            self.log.flush()
            if message.get('id') == self.serial:
                if 'error' in message:
                    raise ValueError(str(message['error']))
                return message['result']

    def close(self):
        self.process.terminate()
        try:
            self.process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            self.process.kill()
            self.process.wait()
        self.log.close()
        self.stderr.close()


def collect(reader, parent):
    ids = {parent}
    for archived in (False, True):
        cursor = None
        seen = set()
        for _ in range(20):
            page = reader.call('thread/list', {'ancestorThreadId': parent, 'archived': archived,
                'sourceKinds': ['subAgent', 'subAgentReview', 'subAgentCompact',
                                'subAgentThreadSpawn', 'subAgentOther'], 'limit': 100, 'cursor': cursor})
            ids.update(t['id'] for t in page['data'])
            cursor = page.get('nextCursor')
            if cursor is None:
                break
            if cursor in seen:
                raise ValueError('repeated descendant cursor')
            seen.add(cursor)
        else:
            raise ValueError('descendant pagination limit exceeded')
    threads = {}
    for identity in sorted(ids):
        thread = reader.call('thread/read', {'threadId': identity, 'includeTurns': False})['thread']
        thread['turns'] = pages(reader, 'thread/turns/list',
                                {'threadId': identity, 'itemsView': 'full', 'sortDirection': 'asc'})
        threads[identity] = thread
    return threads


def pages(reader, method, params):
    result, seen, cursor = [], set(), None
    for _ in range(100):
        page = reader.call(method, {**params, 'cursor': cursor, 'limit': 100})
        result.extend(page['data'])
        cursor = page.get('nextCursor')
        if cursor is None:
            return result
        if cursor in seen:
            raise ValueError('repeated history cursor')
        seen.add(cursor)
    raise ValueError('history pagination limit exceeded')


def inspect(threads, parent, cwd, require_probe=True):
    """Normalize persisted commands once, retaining thread and turn attribution."""
    failures, events = [], []
    if parent not in threads or len(threads) < 2:
        failures.append('parent or descendants missing')
    referenced = set()
    for identity, thread in threads.items():
        if thread.get('cwd') != str(cwd):
            failures.append('unexpected thread workspace: ' + identity)
        ancestor, seen = identity, set()
        while ancestor != parent:
            if ancestor in seen or ancestor not in threads:
                failures.append('unproven parent lineage: ' + identity)
                break
            seen.add(ancestor)
            ancestor = threads[ancestor].get('parentThreadId')
        turns = thread.get('turns', [])
        if not turns:
            failures.append('missing turns: ' + identity)
        own_commands, finals = [], []
        for turn in turns:
            if turn.get('status') != 'completed' or turn.get('itemsView') != 'full':
                failures.append('incomplete turn history: ' + identity)
            for item in turn.get('items', []):
                if item['type'] == 'subAgentActivity':
                    referenced.add(item['agentThreadId'])
                if item['type'] == 'commandExecution':
                    command = {'type': 'command_execution', 'id': item['id'], 'thread_id': identity,
                               'turn_id': turn['id'], 'command': item['command'],
                               'aggregated_output': item.get('aggregatedOutput'),
                               'exit_code': item.get('exitCode'), 'status': item.get('status'),
                               'output_available': item.get('aggregatedOutput') is not None}
                    if command['exit_code'] is None or command['status'] not in ('completed', 'failed'):
                        failures.append('missing command outcome: ' + identity)
                    # Keep availability explicit. Empty text is only the metrics projection;
                    # null output remains untouched in the archived host history.
                    command['aggregated_output'] = command['aggregated_output'] or ''
                    events.append({'type': 'item.completed', 'item': command})
                    own_commands.append(command)
                if item['type'] == 'agentMessage' and item.get('phase') == 'final_answer':
                    finals.append(item['text'])
        if not finals:
            failures.append('missing final outcome: ' + identity)
        if require_probe and not any(c['exit_code'] == 0 and
                'python3 bin/probe.py ' in c['command'] and
                'containment verified ' in c['aggregated_output'] for c in own_commands):
            failures.append('missing attributed containment probe: ' + identity)
    if referenced - threads.keys():
        failures.append('referenced child missing from collection')
    return events, failures
