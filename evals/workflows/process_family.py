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
import threading
import time

PR_SET_CHILD_SUBREAPER = 36
PR_GET_CHILD_SUBREAPER = 37


class Cancelled(Exception):
    """The operator interrupted a bounded invocation."""


def now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='milliseconds')


def set_subreaper(value):
    """Set the child subreaper flag. Return the previous value, or None where unsupported."""
    if not sys.platform.startswith('linux'):
        return None
    try:
        libc = ctypes.CDLL(None, use_errno=True)
        current = ctypes.c_int(0)
        if libc.prctl(PR_GET_CHILD_SUBREAPER, ctypes.byref(current), 0, 0, 0) != 0:
            return None
        if libc.prctl(PR_SET_CHILD_SUBREAPER, value, 0, 0, 0) != 0:
            return None
        return current.value
    except (OSError, AttributeError):
        return None


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
    """Run one host invocation. Never retries. Always returns a durable record.

    Signals that arrive during the final sweep are deferred and recorded, so a
    second interrupt cannot skip the sweep or lose the record.
    """
    linux = sys.platform.startswith('linux')
    previous_reaper = set_subreaper(1)
    record = {'started_at': now(), 'timeout_seconds': timeout, 'outcome': None, 'exit_code': None,
              'subreaper': previous_reaper is not None, 'platform': sys.platform}
    runner = os.getpid()
    preexisting = {pid for pid, row in table().items() if row[0] == runner} if linux else set()
    in_main = threading.current_thread() is threading.main_thread()
    handlers = {}
    deferred = []

    def cancel(signum, frame):
        raise Cancelled('signal %d' % signum)

    def defer(signum, frame):
        deferred.append(signum)

    def restore():
        for number, handler in handlers.items():
            signal.signal(number, handler)
        if previous_reaper == 0:
            set_subreaper(0)

    if in_main:
        handlers[signal.SIGTERM] = signal.signal(signal.SIGTERM, cancel)
        handlers[signal.SIGINT] = signal.getsignal(signal.SIGINT)
    try:
        process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=stdout, stderr=stderr, text=True,
                                   start_new_session=True, env=env, cwd=cwd)
    except BaseException:
        restore()
        raise
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
        if in_main:
            signal.signal(signal.SIGTERM, defer)
            signal.signal(signal.SIGINT, defer)
        try:
            if linux:
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
            try:
                if process.stdin and not process.stdin.closed:
                    process.stdin.close()
            except OSError:
                pass
        finally:
            restore()
        record.update({'ended_at': now(), 'signalled_pids': signalled, 'surviving_pids': remaining,
                       'family_terminated': not remaining,
                       'method': 'session, group and subtree sweep with runner subreaper' if record['subreaper']
                       else 'session, group and subtree sweep without subreaper'})
        if deferred:
            record['deferred_signals'] = deferred
            if record['outcome'] != 'cancelled':
                record['outcome'] = 'cancelled'
                record['cancel_reason'] = 'signal during the termination sweep'
        if record['outcome'] == 'completed' and signalled:
            record['lingering_after_exit'] = len(signalled)
    return record
