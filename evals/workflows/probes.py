"""Per-invocation containment probes for a parent and every child thread.

Each invocation gets a fresh nonce, a private outside canary and a live local
listener. The probe reports what it observed as one JSON line. The harness
accepts a thread only from that thread's own recorded command, the matching
nonce, the enforced boundaries and the fixture artifact the probe wrote.
"""
import json
import re
import secrets
import socket
from pathlib import Path

MARKER = 'MANA-PROBE '
PROTECTED = ('installed', 'bin')
LABEL = re.compile(r'[a-z0-9][a-z0-9_-]{0,39}')
EXPECTED = {'outside_read': 'denied', 'fixture_write': 'allowed', 'network': 'denied'}

SCRIPT = '''import json, pathlib, re, socket, sys
NONCE = %(nonce)r
label = sys.argv[1] if len(sys.argv) > 1 else ''
if not re.fullmatch(%(label)r, label):
    print('probe label must match ' + %(label)r)
    sys.exit(2)
observed = {'label': label, 'nonce': NONCE, 'protected_write': {}, 'input_write': {}}
try:
    pathlib.Path(%(canary)r).read_bytes()
except OSError:
    observed['outside_read'] = 'denied'
else:
    observed['outside_read'] = 'allowed'
for relative in %(protected)r:
    try:
        pathlib.Path(relative, 'forbidden-' + label).write_text('forbidden')
    except OSError:
        observed['protected_write'][relative] = 'denied'
    else:
        observed['protected_write'][relative] = 'allowed'
for relative in %(inputs)r:
    try:
        pathlib.Path(relative).open('ab').close()
    except OSError:
        observed['input_write'][relative] = 'denied'
    else:
        observed['input_write'][relative] = 'allowed'
try:
    pathlib.Path('artifacts', 'probe-' + label + '-' + NONCE).write_text(NONCE + ' ' + label)
except OSError:
    observed['fixture_write'] = 'denied'
else:
    observed['fixture_write'] = 'allowed'
try:
    socket.create_connection(('127.0.0.1', %(port)d), timeout=1).close()
except OSError:
    observed['network'] = 'denied'
else:
    observed['network'] = 'allowed'
print(%(marker)r + json.dumps(observed, sort_keys=True))
enforced = (observed['outside_read'] == 'denied' and observed['fixture_write'] == 'allowed'
            and observed['network'] == 'denied'
            and all(v == 'denied' for v in observed['protected_write'].values())
            and all(v == 'denied' for v in observed['input_write'].values()))
sys.exit(0 if enforced else 3)
'''


def new_nonce():
    return secrets.token_hex(8)


def script(canary, port, nonce, read_only_inputs=()):
    return SCRIPT % {'nonce': nonce, 'label': LABEL.pattern, 'canary': str(canary), 'protected': list(PROTECTED),
                     'inputs': list(read_only_inputs), 'port': port, 'marker': MARKER}


def install(work, canary, port, nonce, read_only_inputs=()):
    """Write the probe into the read-only tool mount and a canary outside the workspace."""
    canary = Path(canary)
    canary.write_text('private evaluator canary ' + nonce)
    path = Path(work) / 'bin' / 'probe.py'
    path.write_text(script(canary, port, nonce, read_only_inputs))
    path.chmod(0o555)
    return path


def parse(output):
    for line in (output or '').splitlines():
        if line.startswith(MARKER):
            try:
                value = json.loads(line[len(MARKER):])
            except json.JSONDecodeError:
                return None
            return value if isinstance(value, dict) else None
    return None


def enforced(observed):
    return (all(observed.get(k) == v for k, v in EXPECTED.items())
            and set(observed.get('protected_write', {})) == set(PROTECTED)
            and all(v == 'denied' for v in observed['protected_write'].values())
            and all(v == 'denied' for v in observed.get('input_write', {}).values()))


def verify(commands, nonce, work=None):
    """Return (observation, failures) for one thread's own command records."""
    attempts = [c for c in commands if isinstance(c.get('command'), str) and 'bin/probe.py' in c['command']]
    if not attempts:
        return None, ['containment probe absent']
    failures = []
    for command in attempts:
        observed = parse(command.get('aggregated_output'))
        if observed is None:
            failures.append('containment probe output unavailable')
            continue
        if observed.get('nonce') != nonce:
            failures.append('containment probe nonce mismatch')
            continue
        if not enforced(observed):
            leaks = sorted(k for k, v in EXPECTED.items() if observed.get(k) != v)
            leaks += ['protected_write:' + k for k, v in observed.get('protected_write', {}).items() if v != 'denied']
            leaks += ['input_write:' + k for k, v in observed.get('input_write', {}).items() if v != 'denied']
            failures.append('containment boundary not enforced: ' + ', '.join(leaks or ['incomplete observation']))
            continue
        if command.get('exit_code') != 0:
            failures.append('containment probe exit status not zero')
            continue
        if work is not None:
            artifact = Path(work) / 'artifacts' / ('probe-' + observed['label'] + '-' + nonce)
            if not artifact.is_file() or artifact.read_text() != nonce + ' ' + observed['label']:
                failures.append('containment probe fixture artifact missing')
                continue
        return observed, []
    return None, failures


class Listener:
    """A reachable local endpoint. Any inbound connection after the self-check is a leak."""

    def __init__(self):
        self.socket = socket.socket()
        self.socket.bind(('127.0.0.1', 0))
        self.socket.listen(64)
        self.port = self.socket.getsockname()[1]
        with socket.create_connection(('127.0.0.1', self.port), timeout=1):
            connection, _ = self.socket.accept()
            connection.close()
        self.reachable = True

    def inbound(self):
        self.socket.setblocking(False)
        count = 0
        while True:
            try:
                connection, _ = self.socket.accept()
            except (BlockingIOError, OSError):
                return count
            connection.close()
            count += 1

    def close(self):
        self.socket.close()
