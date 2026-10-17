"""Bounded host invocations whose whole process family is terminated and recorded.

A host runs in its own session. The runner marks itself a child subreaper, so a
tool command that double-forks or calls setsid is reparented to the runner and
stays visible. Timeout, operator cancellation and normal exit all end with a
family sweep. The sweep record is retained with the attempt.
"""
import ctypes
import datetime
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

PR_SET_CHILD_SUBREAPER = 36


class Cancelled(Exception):
    """The operator interrupted a bounded invocation."""


def now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='milliseconds')


def enable_subreaper():
    if not sys.platform.startswith('linux'):
        return False
    try:
        libc = ctypes.CDLL(None, use_errno=True)
        return libc.prctl(PR_SET_CHILD_SUBREAPER, 1, 0, 0, 0) == 0
    except (OSError, AttributeError):
        return False


def table():
    """Map live pid to (ppid, pgid, sid, state) from /proc."""
    rows = {}
    for entry in Path('/proc').iterdir():
        if not entry.name.isdigit():
            continue
        try:
            raw = (entry / 'stat').read_text()
        except OSError:
            continue
        # The command name is parenthesised and may contain spaces.
        fields = raw[raw.rindex(')') + 2:].split()
        rows[int(entry.name)] = (int(fields[1]), int(fields[2]), int(fields[3]), fields[0])
    return rows


def subtree(rows, roots):
    found, frontier = set(), set(roots)
    while frontier:
        found |= frontier
        frontier = {pid for pid, row in rows.items() if row[0] in frontier} - found
    return found


def family(root, runner, preexisting):
    """The host subtree, its session and group, and orphans reparented to the runner."""
    rows = table()
    members = subtree(rows, {root} if root in rows else set())
    members |= {pid for pid, row in rows.items() if row[1] == root or row[2] == root}
    adopted = {pid for pid, row in rows.items() if row[0] == runner and pid not in preexisting}
    members |= subtree(rows, adopted)
    members.discard(runner)
    return {pid for pid in members if pid in rows and rows[pid][3] != 'Z'}, rows


def sweep(root, runner, preexisting, rounds=50):
    """SIGKILL every family member until a fresh scan finds none alive."""
    signalled = set()
    alive = set()
    for _ in range(rounds):
        alive, _ = family(root, runner, preexisting)
        if not alive:
            break
        try:
            os.killpg(root, signal.SIGKILL)
        except OSError:
            pass
        for pid in alive:
            try:
                os.kill(pid, signal.SIGKILL)
                signalled.add(pid)
            except OSError:
                pass
        time.sleep(0.05)
        reap_adopted(runner, root, preexisting)
    alive, _ = family(root, runner, preexisting)
    reap_adopted(runner, root, preexisting)
    return sorted(signalled), sorted(alive)


def reap_adopted(runner, root, preexisting):
    """Collect zombies of orphans adopted by the runner; the host itself belongs to Popen."""
    for pid, row in table().items():
        if row[0] == runner and row[3] == 'Z' and pid != root and pid not in preexisting:
            try:
                os.waitpid(pid, os.WNOHANG)
            except ChildProcessError:
                pass


def run_bounded(command, stdin_text, stdout, stderr, timeout, env=None, cwd=None):
    """Run one host invocation. Never retries. Always returns a durable record."""
    record = {'started_at': now(), 'timeout_seconds': timeout, 'outcome': None, 'exit_code': None,
              'subreaper': enable_subreaper(), 'platform': sys.platform}
    runner = os.getpid()
    preexisting = {pid for pid, row in table().items() if row[0] == runner} if sys.platform.startswith('linux') else set()
    previous = signal.getsignal(signal.SIGTERM)

    def cancel(signum, frame):
        raise Cancelled('signal %d' % signum)

    in_main = True
    try:
        signal.signal(signal.SIGTERM, cancel)
    except ValueError:
        in_main = False
    process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=stdout, stderr=stderr, text=True,
                               start_new_session=True, env=env, cwd=cwd)
    record['host_pid'] = process.pid
    try:
        try:
            process.communicate(stdin_text, timeout=timeout)
            record['outcome'] = 'completed'
            record['exit_code'] = process.returncode
        except subprocess.TimeoutExpired:
            record['outcome'] = 'timeout'
        except (Cancelled, KeyboardInterrupt) as exc:
            record['outcome'] = 'cancelled'
            record['cancel_reason'] = type(exc).__name__ + (': ' + str(exc) if str(exc) else '')
    finally:
        if sys.platform.startswith('linux'):
            signalled, remaining = sweep(process.pid, runner, preexisting)
        else:
            signalled, remaining = [], []
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except OSError:
                pass
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            remaining = sorted(set(remaining) | {process.pid})
        for pipe in (process.stdin,):
            try:
                if pipe and not pipe.closed:
                    pipe.close()
            except OSError:
                pass
        if in_main:
            signal.signal(signal.SIGTERM, previous)
        record.update({'ended_at': now(), 'signalled_pids': signalled, 'surviving_pids': remaining,
                       'family_terminated': not remaining,
                       'method': 'session, group and subtree sweep with runner subreaper' if record['subreaper']
                       else 'session, group and subtree sweep without subreaper'})
        if record['outcome'] == 'completed' and signalled:
            record['lingering_after_exit'] = len(signalled)
    return record
