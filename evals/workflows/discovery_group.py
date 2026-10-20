"""One frozen discovery group: allocate every slot of the first live group, then run them serially.

The 2026-10-20 pilot ran from an operator script kept only in its evidence
archive. It froze a checkout one commit behind main and stopped the whole group
on an empty collaboration wait. This module keeps that script's freeze and
per-slot integrity checks and changes two things. The source must contain the
remote main branch, read after a fetch, and the working tree must be clean.
Child activity is judged per slot: a failed spawn marks its slot and the group
continues, and only a child that was actually created stops the group, because
then the zero-child bound no longer holds.

Every allocated slot stays in allocation.json, including slots never started
after a stop. Nothing is retried or replaced.
"""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import time

import discovery
import hosts
import process_family

ROOT = discovery.ROOT
RESOURCES = {'serial_parents': 1, 'timeout_seconds': discovery.TIMEOUT, 'children': 0, 'retries': 0,
             'expansions_authorized': False}
STOP_EXECUTIONS = ('setup_failed', 'boundary_breach', 'collection_failed')


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    Path(path).write_text(json.dumps(value, indent=2, sort_keys=True) + '\n')


def git(root, *args):
    return subprocess.run(['git', '-C', str(root), *args], capture_output=True, text=True)


def source_state(root, remote='origin', branch='main', fetch=True):
    """The revision a group freezes: a clean tree whose HEAD contains the remote main branch after a fetch."""
    if git(root, 'status', '--porcelain').stdout.strip():
        raise ValueError('working tree has uncommitted changes; commit or discard them before freezing a group')
    if fetch:
        fetched = git(root, 'fetch', '--quiet', remote, branch)
        if fetched.returncode:
            raise ValueError('could not fetch %s/%s: %s' % (remote, branch, fetched.stderr.strip()[-300:]))
    upstream = git(root, 'rev-parse', '%s/%s' % (remote, branch))
    if upstream.returncode:
        raise ValueError('no %s/%s to compare against' % (remote, branch))
    if git(root, 'merge-base', '--is-ancestor', upstream.stdout.strip(), 'HEAD').returncode:
        raise ValueError('HEAD does not contain %s/%s; update the checkout before freezing a group' % (remote, branch))
    return {'head': git(root, 'rev-parse', 'HEAD').stdout.strip(), 'upstream': upstream.stdout.strip(),
            'upstream_ref': '%s/%s' % (remote, branch), 'fetched': fetch}


def sources(root):
    workflows = Path(root) / 'evals/workflows'
    paths = sorted(set(list(workflows.glob('*.py')) + [workflows / 'discovery-cases.json', workflows / 'response-schema.json']
                       + list((workflows / 'host-evidence').glob('*.json'))))
    return {str(path.relative_to(root)): digest(path) for path in paths}


def freeze(out, executable, model, reasoning='medium', root=ROOT, evidence_dir=None, fetch=True, authorization=None):
    """Write the manifest and the allocation before the first invocation. Refuses to replace an existing group."""
    out = Path(out).resolve()
    out.mkdir(parents=True, exist_ok=False)
    executable = Path(executable).resolve()
    state = source_state(root, fetch=fetch)
    version = subprocess.check_output([str(executable), '--version'], text=True, timeout=20).strip()
    assessment = hosts.require(version, 'discovery', directory=evidence_dir)
    data = discovery.load_cases(Path(root) / 'evals/workflows/discovery-cases.json')
    catalog = discovery.snapshot(Path(root) / 'skills')
    discovery.check_catalog(data, catalog)
    schedule = discovery.schedule(data['first_live_group'])
    hashes = sources(root)
    shutil.copytree(Path(root) / 'skills', out / 'frozen/skills')
    for name in hashes:
        destination = out / 'frozen' / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(Path(root) / name, destination)
    manifest = {'schema_version': 1, 'study': out.name, 'protocol_study': data['study'], 'frozen_at': process_family.now(),
                'source': state, 'route_inventory_revision': data['source_revision'], 'catalog_sha256': catalog['sha256'],
                'routes_sha256': discovery.routes_digest(Path(root) / 'evals/workflows/discovery-cases.json'),
                'source_sha256': hashes, 'host': version, 'executable_sha256': digest(executable),
                'host_assessment': assessment, 'host_support': discovery.support(version, evidence_dir),
                'children_disabled': (hosts.capabilities(version, directory=evidence_dir)['children_disabled'] or {}).get('status'),
                'requested_model': model, 'reasoning': reasoning, 'actual_model': None,
                'resources': dict(RESOURCES, parent_slots=len(schedule), max_parent_seconds=len(schedule) * discovery.TIMEOUT,
                                  authorization=authorization),
                'shuffle_seed': discovery.SEED, 'repetitions': 2, 'schedule': schedule,
                'stop_conditions': ['containment or setup failure', 'product mutation', 'event collection failure',
                                    'process family survives', 'host failed or cancelled', 'source, catalog or host changed',
                                    'a child thread was created'],
                'slot_conditions': ['a failed spawn marks its slot children=attempted and the group continues'],
                'host_skill_folders': discovery.host_skill_folders()[0]}
    write(out / 'catalog.json', catalog)
    write(out / 'manifest.json', manifest)
    write(out / 'allocation.json', [dict(cell, status='allocated', model_invocations=0) for cell in schedule])
    return manifest


def stop_reason(row, result):
    """Why this slot ends the group, or None to continue."""
    if result['failures'] or result['execution'] in STOP_EXECUTIONS:
        return 'slot %d: %s' % (row['slot'], '; '.join(result['failures']) or result['execution'])
    if result.get('judgment', {}).get('children') == 'created':
        return 'slot %d: a child thread was created, so the zero-child bound no longer holds' % row['slot']
    if result.get('process_family', {}).get('outcome') in ('agent_failed', 'cancelled'):
        return 'slot %d: host failed or cancelled' % row['slot']
    return None


def run(out, executable, root=ROOT, evidence_dir=None, live=True):
    """Run every allocated slot in schedule order, one parent at a time."""
    out = Path(out).resolve()
    executable = Path(executable).resolve()
    manifest = json.loads((out / 'manifest.json').read_text())
    allocation = json.loads((out / 'allocation.json').read_text())
    if any(row['status'] != 'allocated' for row in allocation):
        raise ValueError('this group already ran; a new attempt needs a new group')
    catalog = json.loads((out / 'catalog.json').read_text())
    frozen_cases = out / 'frozen/evals/workflows/discovery-cases.json'
    by_id = {case['id']: case for case in discovery.load_cases(frozen_cases)['cases']}
    reason = None
    started = time.monotonic()
    for row in allocation:
        if reason:
            row.update(status='not_started', reason=reason)
            write(out / 'allocation.json', allocation)
            continue
        try:
            if sources(root) != manifest['source_sha256']:
                raise ValueError('frozen evaluator, routes or host evidence changed')
            if discovery.snapshot(Path(root) / 'skills') != catalog or discovery.snapshot(out / 'frozen/skills') != catalog:
                raise ValueError('frozen catalog changed')
            if digest(executable) != manifest['executable_sha256']:
                raise ValueError('host binary changed')
            name = 'slot-%02d-%s-r%d' % (row['slot'], row['case'], row['repetition'])
            row.update(status='running', directory=name)
            write(out / 'allocation.json', allocation)
            result = discovery.run_case(by_id[row['case']], out / name, executable, manifest['requested_model'],
                                        manifest['reasoning'], skill_root=out / 'frozen/skills', evidence_dir=evidence_dir,
                                        live=live, routes_sha256=manifest['routes_sha256'], cases_path=frozen_cases)
            row.update(status=result['execution'], model_invocations=result['model_invocations'],
                       result_sha256=digest(out / name / 'result.json'), seconds=result['seconds'],
                       children=result.get('judgment', {}).get('children'))
            reason = stop_reason(row, result)
        except (OSError, ValueError, KeyError, subprocess.SubprocessError) as exc:
            reason = 'slot %d: %s' % (row['slot'], exc)
            row.update(status='setup_failed', reason=reason)
        write(out / 'allocation.json', allocation)
    completion = {'ended_at': process_family.now(), 'wall_seconds': round(time.monotonic() - started, 2),
                  'stop_reason': reason, 'slots': len(allocation),
                  'model_invocations': sum(row['model_invocations'] for row in allocation),
                  'children_attempted_slots': [row['slot'] for row in allocation if row.get('children') == 'attempted']}
    write(out / 'completion.json', completion)
    return completion
