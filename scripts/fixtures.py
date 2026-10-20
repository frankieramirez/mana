#!/usr/bin/env python3
"""Runs every fixture suite validate.sh checks, in parallel, and prints only the failures.

The suites are independent: each builds its own temporary repos and hosts. The workflow
grader tests are most of the time, so they run one test class per process.
"""
import os
from pathlib import Path
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
import unittest

ROOT = Path(__file__).resolve().parent.parent
PY = [sys.executable, '-B']

# Heaviest first, so no long suite starts last and holds the run open.
SUITES = [
    ('leyline refresh fixtures', PY + ['scripts/test_leyline_refresh.py']),
    ('leyline challenge fixtures', PY + ['scripts/test_leyline_challenge.py']),
    ('leyline installation fixtures', ['scripts/test-leyline-install.sh']),
    ('leyline conformance fixtures', ['scripts/test-leyline.sh']),
    ('generated control runtime fixtures', PY + ['scripts/test_control_runtime.py']),
    ('mend PR preparation fixtures', ['scripts/test-mend.sh']),
    ('build ticket adapter fixtures', ['scripts/test-build-tickets.sh']),
    ('Augur source proof fixtures', PY + ['-m', 'unittest', 'discover', '-s', 'scripts', '-p', 'test_augur_proof.py']),
    ('PR attendance fixtures', ['scripts/test-ward.sh']),
    ('ultima audit fixtures', ['scripts/test-ultima.sh']),
    ('control evidence fixtures', PY + ['scripts/test_control_evidence.py']),
    ('review merge fixtures', PY + ['scripts/test_review_merge.py']),
    ('persona synchronization fixtures', ['scripts/test-persona.sh']),
    ('open-pr conflict fixtures', ['scripts/test-open-pr.sh']),
    ('scry map closeout fixtures', ['scripts/test-scry-map.sh']),
    ('scry frontier fixtures', ['scripts/test-scry-frontier.sh']),
    ('standalone packages', PY + ['scripts/verify_packages.py']),
    ('reliability fixtures', PY + ['-m', 'unittest', 'discover', '-s', 'scripts', '-p', 'test_reliability.py']),
    ('workflow definitions', PY + ['evals/workflows/run.py', '--check']),
    ('semantic eval runner fixtures', PY + ['-m', 'unittest', 'discover', '-s', 'evals/semantic', '-p', 'test_*.py']),
]


def workflow_classes():
    """One job per test class under evals/workflows, the way discover would find them."""
    sys.path.insert(0, str(ROOT / 'evals/workflows'))
    suite = unittest.defaultTestLoader.discover(str(ROOT / 'evals/workflows'), pattern='test_*.py')
    classes, stack = [], [suite]
    while stack:
        item = stack.pop()
        if isinstance(item, unittest.TestSuite):
            stack.extend(item)
        elif isinstance(item, unittest.loader._FailedTest):
            classes.append(item.id().split('.')[-1])
        else:
            name = '%s.%s' % (type(item).__module__, type(item).__qualname__)
            if name not in classes:
                classes.append(name)
    return sorted(classes)


def run(label, command, env=None):
    started = time.monotonic()
    result = subprocess.run(command, cwd=ROOT, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            stdin=subprocess.DEVNULL, text=True, errors='replace')
    return label, result.returncode, result.stdout, time.monotonic() - started


def main():
    jobs = [(label, command, None) for label, command in SUITES]
    env = dict(os.environ, PYTHONPATH=os.pathsep.join(filter(None, [str(ROOT / 'evals/workflows'),
                                                                     os.environ.get('PYTHONPATH')])))
    try:
        classes = workflow_classes()
    except Exception as error:  # an import error in a test module still has to fail the run
        print('FAIL: workflow grader fixtures did not load: %s' % error, file=sys.stderr)
        return 1
    # The workflow classes go in front of the light suites; the heavy suites still lead.
    heavy = 8
    jobs[heavy:heavy] = [('workflow grader fixtures (%s)' % name, PY + ['-m', 'unittest', name], env)
                         for name in classes]
    # Twice the cores: many fixtures wait on subprocesses and sleeps rather than compute.
    workers = int(os.environ.get('MANA_FIXTURE_JOBS') or 2 * (os.cpu_count() or 2))
    started, failed, slowest = time.monotonic(), [], ('', 0)
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(run, *job) for job in jobs]
        for future in as_completed(futures):
            label, code, output, seconds = future.result()
            slowest = max(slowest, (label, seconds), key=lambda pair: pair[1])
            if code != 0:
                failed.append(label)
                sys.stderr.write('%s\nFAIL: %s failed (exit %d)\n' % (output.rstrip(), label, code))
                sys.stderr.flush()
    print('fixtures: %d jobs, %d failed, %.0fs on %d workers, slowest %s at %.0fs'
          % (len(jobs), len(failed), time.monotonic() - started, workers, *slowest))
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main())
