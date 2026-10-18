"""Complete comparative matrix for effectiveness-pilot-1 (issue 113) and the gates before its first slot.

Evaluator-only, like the four group freezes it composes (heldout_review, heldout_debugging,
heldout_verification and heldout_prose). Anyone tuning candidate instructions must not read it.

heldout/pilot-manifest.json is the preregistered matrix: host, model and tool controls, both payload
pins and every entrypoint, per-case request, input and oracle digests, per-job time limits, the
delegation limits and the 72-slot schedule. Its digests cover only the twelve governed cases, never
the shared heldout folders as a whole. test_pilot.py holds its external digest. heldout/pilot-gates.json
sits outside the freeze and records the resource authorization and human-effort availability.

blockers() lists every closed gate. The study refuses to start, and no slot is claimed, while it is
non-empty. Delegated parity stays closed until a host evidence record verifies the
comparative-delegated mode for the pinned host; nothing here can open it without that record.

    python3 -B evals/workflows/pilot.py --check
    python3 -B evals/workflows/pilot.py --prepare /abs/mana/skills /abs/reference-package /abs/new-study
    python3 -B evals/workflows/pilot.py --freeze   # author only: rewrite pilot-manifest.json
"""
import json
from pathlib import Path
import shutil
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import conditions  # noqa: E402
import delegation  # noqa: E402
import heldout_debugging  # noqa: E402
import heldout_prose  # noqa: E402
import heldout_review  # noqa: E402
import heldout_verification  # noqa: E402
import hosts  # noqa: E402

HERE = Path(__file__).resolve().parent
HELDOUT = HERE / 'heldout'
MANIFEST_NAME = 'pilot-manifest.json'
GATES_NAME = 'pilot-gates.json'
KINDS = conditions.KINDS
# Job name -> (group, hard seconds per invocation), from the protocol's resource table.
JOBS = {'review-and-feedback': ('review', 900), 'debugging': ('debugging', 600),
        'verification-judgment': ('verification', 300), 'prose-fidelity': ('prose', 180)}
GROUP_CASES = {'review': heldout_review.CASES, 'debugging': heldout_debugging.CASE_IDS,
               'verification': heldout_verification.CASE_IDS, 'prose': heldout_prose.CASES}
CONTROLS = {
    'study': 'effectiveness-pilot-1',
    # The protocol starts from codex-cli 0.159.2. 0.163.0 replaces it before any run because it carries the live
    # focused and delegated evidence and verified process-family termination; see host_substitution.
    'host': 'codex-cli 0.163.0', 'platform': 'linux',
    'host_substitution': {'protocol_host': 'codex-cli 0.159.2', 'reason': (
        'codex-cli 0.159.2 has no process-family termination evidence; codex-cli 0.163.0 has live focused and '
        'delegated evidence. Neither verifies its active thread cap, so delegated parity stays closed.')},
    'model': 'gpt-6.1-sol', 'reasoning': 'medium', 'actual_model': None,
    'seed': 20261017, 'repetitions': 2, 'automatic_retries': 0, 'replacement_runs': 0,
    'parallel_parents': 1,
    'delegation': {'max_active_threads': 4, 'max_children': 10, 'nested': False},
    'tools': 'native filesystem tools only: no MCP servers, web search, apps, plugins, hooks, memories or user '
             'configuration; evaluator tool doubles first on PATH in every condition alike',
}
# Verified on 2026-10-18 from the git objects of each pin: the inventory digests match the group freezes and
# every entrypoint digest matches what a group recorded where it recorded one.
PAYLOADS = {
    'mana': {'repository': 'frankieramirez/mana', 'revision': '9d1aa521974bc7c72bf9cdd676de18c09a036468',
             'package_paths': ['skills'], 'install_root': 'skills', 'file_count': 181,
             'inventory_sha256': '570b33b1405a36028d2839b5d3dc9ba645b6773f7916d6ae09f035e6b10a5fc0'},
    'reference': {'repository': 'cursor/plugins', 'revision': '101b274dd991f694e1f7024be2157e5f3adf07de',
                  'package_paths': ['pstack', 'cursor-team-kit/skills/deslop'], 'install_root': '.',
                  'file_count': 171,
                  'inventory_sha256': 'b6edf110f097f8c46c579c2fe1c4c481cca0c37a75085233b7d66a5b7c642bdd'},
}
ENTRYPOINT_SHA256 = {
    'mana': {'scan/SKILL.md': '1172c50f714e136330df15c6051bcc96d6eb58738b39322e1a15ce9cfbe5d266',
             'remedy/SKILL.md': '784d4acc4a7680412683699d5fe808318e6e1aa65a9c9563eebb167463b078a1',
             'cast/SKILL.md': '4ba50041e555b52219a2a6c40f7d972fbbac109ff490ec6f53a802204937acf7',
             'reveal/references/capture.md': '273ddba9fe4cba2c60fc261747f63f8426c7a97b0df40b04f0a76c7e9ce0ba81',
             'dispel/SKILL.md': '5af33a677f43a9874ba0ed9928cec49ea3f2afe81ac0f13d938493ba3a005ac7'},
    'reference': {
        'pstack/skills/interrogate/SKILL.md': 'a16dfe179005abc22a4651b82f25b0c8ab953284276efe4e6dc341958fb63647',
        'pstack/skills/poteto-mode/SKILL.md': 'c5e6b605f46e5d9fbab31afa7a99d3d50680f2180d1fdfae3a924901bc52d99a',
        'pstack/skills/principle-test-behavior-not-implementation/SKILL.md':
            'f7223698623b6a26fea49c751e466b38e6691b1f32ce841d3983e7ffbe2b74a6',
        'pstack/skills/principle-prove-it-works/SKILL.md':
            'ec79a15025bac8d33d62011c54f3b612733fd2a024e623b531b3637aa75070e2',
        'pstack/skills/unslop/SKILL.md': 'ccab208e315ce05e2fab8eeee2f7879f1289b5c6844840b2d307adf31c79144f'},
}
STOP_CONDITIONS = (
    'containment failure in the preflight or any thread probe',
    'unexpected external write: an evaluator-owned origin ref changed',
    'corrupted frozen input: controls, schedule, payload, fixture, installed payload or tool double changed',
    'missing or incomplete child history, an uncollected thread or a child limit breach',
    'budget breach: invocation timeout or a surviving process family',
    'systematic tool-double mismatch or a missing observation',
)
ADAPTER_TRANSLATIONS = (
    'Every workspace gets home/, artifacts/ and bin/ beside the frozen product files; installed/, home/, '
    'artifacts/ and bin/ are excluded from Git status through .git/info/exclude.',
    'Debugging and prose inputs are plain directories, so the runner commits them once with a fixed author and '
    'date. HEAD, index and the final diff then exist for every condition alike.',
    'Each payload is installed whole under installed/payload/. Mana entrypoints are relative to skills/, '
    'reference entrypoints to the repository root, so pstack/ group paths gain a pstack/ prefix.',
    'The reference arm installs the complete package in every group, so groups frozen against pstack/ alone also '
    'receive cursor-team-kit/skills/deslop/, which poteto-mode names before a commit.',
    'Evaluator tool doubles from the inputs go to bin/, first on PATH in every condition. A double exit 97 is a '
    'refused write or install measured by the group grader, never a harness stop.',
)


def load(path):
    return json.loads(Path(path).read_text())


def governed_files(case):
    """Every candidate input and oracle byte that belongs to one case, keyed relative to heldout/."""
    paths = [p for p in (HELDOUT / 'inputs' / case).rglob('*')]
    paths += list((HELDOUT / 'oracles').glob(case + '.*'))
    if (HELDOUT / 'oracles' / case).is_dir():
        paths += list((HELDOUT / 'oracles' / case).rglob('*'))
    return sorted(p for p in paths if p.is_file() and '__pycache__' not in p.parts and p.suffix != '.pyc')


def case_digests(case):
    """Request, candidate input and oracle digests for one case only; other freezes share these folders."""
    inputs, oracles = {}, {}
    for path in governed_files(case):
        key = path.relative_to(HELDOUT).as_posix()
        (inputs if key.startswith('inputs/') else oracles)[key] = conditions.digest(path.read_bytes())
    return {'request_sha256': conditions.digest((HELDOUT / 'inputs' / case / 'request.md').read_bytes()),
            'inputs_sha256': conditions.digest(conditions.encoded(inputs)),
            'oracle_sha256': conditions.digest(conditions.encoded(oracles))}


def group_sources():
    """The group freezes as written: per-case entries in one shape, payload pins and freeze identities."""
    review = load(HELDOUT / 'review-manifest.json')
    debugging = load(HELDOUT / 'debugging-manifest.json')
    verification = load(HELDOUT / 'verification-manifest.json')
    prose = load(HELDOUT / 'prose-manifest.json')

    def path_of(value):
        return value['path'] if isinstance(value, dict) else value

    rows, pins = {}, {}
    for group, manifest, entries, cond in (
            ('review', review, review['cases'], review['conditions']),
            ('debugging', debugging, debugging['cases'], debugging['conditions']),
            ('verification', verification, verification['entries'], verification['packages']),
            ('prose', prose, prose['cases'], prose['conditions'])):
        pins[group] = {}
        for kind in ('mana', 'reference'):
            root = cond[kind].get('package_root') or cond[kind].get('root')
            pins[group][kind] = {'revision': cond[kind]['revision'], 'inventory_sha256': cond[kind]['inventory_sha256'],
                                 'package_paths': cond[kind].get('package_paths') or [root]}
        for entry in entries:
            entrypoints = {}
            for kind in ('mana', 'reference'):
                root = cond[kind].get('package_root') or cond[kind].get('root')
                path = path_of(entry['condition_entrypoints'][kind])
                prefix = '' if root in ('.', PAYLOADS[kind]['install_root']) else root + '/'
                entrypoints[kind] = {'path': prefix + path, 'group_sha256': (
                    entry['condition_entrypoints'][kind].get('sha256')
                    if isinstance(entry['condition_entrypoints'][kind], dict) else None)}
            rows[entry['id']] = {'group': group, 'entry': entry, 'entrypoints': entrypoints}
    freezes = {'review': conditions.digest((HELDOUT / 'review-freeze.json').read_bytes()),
               'debugging': debugging['freeze']['freeze_sha256'],
               'verification': conditions.digest((HELDOUT / 'verification-lock.json').read_bytes()),
               'prose': prose['freeze_sha256']}
    exposures = {'review': review['exposure']['events'], 'debugging': debugging['exposures'],
                 'verification': load(HELDOUT / 'verification-lock.json')['provenance']['exposure_log'],
                 'prose': prose['exposure']}
    return rows, pins, freezes, exposures


def build_manifest():
    """The complete matrix, recomputed from the group freezes and the governed case bytes."""
    rows, pins, freezes, _ = group_sources()
    cases = []
    for case in sorted(rows):
        row = rows[case]
        entry = row['entry']
        group = JOBS[entry['job']][0]
        cases.append({
            'id': case, 'group': group, 'job': entry['job'], 'source_group': entry['source_group'],
            'split': entry['split'], 'request_path': 'inputs/%s/request.md' % case,
            **case_digests(case),
            'group_fixture_sha256': entry['fixture_sha256'],
            'oracle_id': entry['oracle_id'], 'allowed_effects': entry['allowed_effects'],
            'timeout_seconds': entry['timeout_seconds'],
            'delegation_allowed': entry['delegation_allowed'],
            'condition_entrypoints': {
                'mana': {'path': row['entrypoints']['mana']['path'],
                         'sha256': ENTRYPOINT_SHA256['mana'].get(row['entrypoints']['mana']['path'])},
                'reference': {'path': row['entrypoints']['reference']['path'],
                              'sha256': ENTRYPOINT_SHA256['reference'].get(row['entrypoints']['reference']['path'])},
                'none': None},
        })
    slots = conditions.schedule([c['id'] for c in cases], CONTROLS['seed'], CONTROLS['repetitions'])
    cells = len(KINDS) * CONTROLS['repetitions']
    code = [c for c in cases if c['delegation_allowed']]
    return {
        'version': 1, 'freeze_name': 'effectiveness-pilot-1-a', **CONTROLS,
        'conditions': {**PAYLOADS, 'none': {}},
        'group_freezes': freezes,
        'group_pins': pins,
        'cases': cases,
        'totals': {'cases': len(cases), 'source_groups': len({c['source_group'] for c in cases}),
                   'parent_slots': len(slots),
                   'parent_seconds': sum(c['timeout_seconds'] * cells for c in cases),
                   'max_children': len(code) * cells * CONTROLS['delegation']['max_children']},
        'stop_conditions': list(STOP_CONDITIONS),
        'adapter_translations': list(ADAPTER_TRANSLATIONS),
        'schedule': slots,
        'schedule_sha256': conditions.digest(conditions.encoded(slots)),
    }


def inside(path, package_paths):
    return any(path == p or path.startswith(p.rstrip('/') + '/') for p in package_paths)


def matrix_problems(manifest):
    """Structural checks on a pilot manifest. An empty list means the matrix is complete."""
    problems = []
    cases = manifest['cases']
    if len(cases) != 12 or len({c['source_group'] for c in cases}) != 12:
        problems.append('the matrix needs 12 distinct source groups')
    for job, (group, seconds) in JOBS.items():
        members = [c for c in cases if c['job'] == job]
        if sorted(c['id'] for c in members) != sorted(GROUP_CASES[group]):
            problems.append('%s must hold exactly %s' % (job, ', '.join(GROUP_CASES[group])))
        for c in members:
            if c['group'] != group or c['timeout_seconds'] != seconds:
                problems.append(c['id'] + ': time limit differs from the %d second job limit' % seconds)
            if c['delegation_allowed'] is not (group != 'prose'):
                problems.append(c['id'] + ': code tasks share the delegation capability and prose has none')
    if manifest.get('repetitions') != 2 or manifest.get('automatic_retries') != 0 \
            or manifest.get('replacement_runs') != 0 or manifest.get('parallel_parents') != 1:
        problems.append('two repetitions, one parent at a time and no automatic retries or replacements')
    if set(manifest['conditions']) != set(KINDS) or manifest['conditions']['none'] != {}:
        problems.append('conditions must be mana, reference and an empty none')
    try:
        delegation.checked(manifest['delegation'])
    except ValueError as exc:
        problems.append('delegation limits: ' + str(exc))
    slots = conditions.schedule([c['id'] for c in cases], manifest['seed'], manifest['repetitions'])
    if manifest['schedule'] != slots or manifest['schedule_sha256'] != conditions.digest(conditions.encoded(slots)):
        problems.append('schedule is not the seeded sorted-block schedule')
    if len(slots) != 72:
        problems.append('the schedule must allocate 72 parent slots')
    for c in cases:
        cells = sorted((s['condition'], s['repetition']) for s in manifest['schedule'] if s['case'] == c['id'])
        if cells != sorted((k, r) for k in KINDS for r in (1, 2)):
            problems.append(c['id'] + ': needs exactly three conditions times two repetitions')
        if c['split'] != 'confirmation':
            problems.append(c['id'] + ': not untouched confirmation data')
        entry = c['condition_entrypoints']
        if set(entry) != set(KINDS) or entry['none'] is not None:
            problems.append(c['id'] + ': needs mana, reference and none entrypoints')
            continue
        for kind in ('mana', 'reference'):
            route = entry[kind]
            if not route or not route.get('path') or not conditions.DIGEST.fullmatch(route.get('sha256') or ''):
                problems.append('%s: no executable %s route' % (c['id'], kind))
            elif kind == 'reference' and not inside(route['path'], manifest['conditions'][kind]['package_paths']):
                problems.append('%s: reference route outside the reference package: %s' % (c['id'], route['path']))
        if c['group'] not in PREPARERS:
            problems.append(c['id'] + ': the runner has no workspace adapter for this group')
    for group, pins in manifest['group_pins'].items():
        for kind in ('mana', 'reference'):
            study = manifest['conditions'][kind]
            if pins[kind]['revision'] != study['revision']:
                problems.append('%s %s pin differs from the study pin' % (group, kind))
            if not all(any(inside(p, [q]) for q in study['package_paths']) for p in pins[kind]['package_paths']):
                problems.append('%s %s package lies outside the complete study package' % (group, kind))
            if pins[kind]['package_paths'] == study['package_paths'] \
                    and pins[kind]['inventory_sha256'] != study['inventory_sha256']:
                problems.append('%s %s inventory differs from the study package' % (group, kind))
    return problems


def problems(manifest=None):
    """Matrix problems plus drift between the committed manifest and the group freezes it composes."""
    manifest = load(HELDOUT / MANIFEST_NAME) if manifest is None else manifest
    found = matrix_problems(manifest)
    rebuilt = build_manifest()
    for key in sorted(set(manifest) | set(rebuilt)):
        if manifest.get(key) != rebuilt.get(key):
            found.append('pilot manifest differs from the group freezes and case bytes: ' + key)
    rows = group_sources()[0]
    for c in rebuilt['cases']:
        if c['request_sha256'] != rows[c['id']]['entry']['request_sha256']:
            found.append(c['id'] + ': request digest differs from its group freeze')
        for kind in ('mana', 'reference'):
            group_sha = rows[c['id']]['entrypoints'][kind]['group_sha256']
            if group_sha and group_sha != c['condition_entrypoints'][kind]['sha256']:
                found.append('%s: %s entrypoint digest differs from its group freeze' % (c['id'], kind))
    return found


def group_blockers():
    """Each group's own readiness: freeze intact, independent second review approved, routes confirmed."""
    found = []
    review = load(heldout_review.MANIFEST)
    review_freeze = conditions.digest(heldout_review.FREEZE.read_bytes())
    found += ['review: ' + p for p in heldout_review.manifest_failures(review)]
    if load(heldout_review.FREEZE) != heldout_review.freeze_record():
        found.append('review: freeze record does not match the inputs, oracles or manifest')
    found += ['review: ' + b for b in heldout_review.readiness_blockers(
        review, load(heldout_review.REVIEWER_RECORD), review_freeze)]
    debugging = heldout_debugging.load_manifest()
    found += ['debugging: ' + p for p in heldout_debugging.verify_manifest(debugging)]
    second = debugging['review']['second_review']
    if second['status'] != 'completed' or 'APPROVED' not in second.get('note', ''):
        found.append('debugging: second review is not completed and approved')
    if debugging['ready_for_study_freeze'] is not True or debugging['blockers']:
        found += ['debugging: ' + b for b in debugging['blockers'] or ['not ready for a study freeze']]
    found += ['verification: ' + b for b in heldout_verification.ready_for_study()]
    found += ['prose: ' + r for r in heldout_prose.readiness()]
    return found


def provenance_blockers(manifest):
    """Untouched confirmation data: no exposure event, confirmation splits and unchanged group freezes."""
    _, _, freezes, exposures = group_sources()
    found = []
    for group, events in exposures.items():
        if events:
            found.append('provenance: %s has %d exposure event(s); replace the exposed groups first' % (group, len(events)))
    if freezes != manifest['group_freezes']:
        found.append('provenance: a group freeze changed after the pilot manifest; refreeze the pilot')
    for c in manifest['cases']:
        if c['split'] != 'confirmation':
            found.append('provenance: %s is %s data' % (c['id'], c['split']))
    return found


def parity_blockers(manifest, evidence=None, at=None):
    """Delegated parity: code tasks need the comparative-delegated host mode, prose the focused one."""
    found = []
    modes = sorted({'comparative-delegated' if c['delegation_allowed'] else 'focused' for c in manifest['cases']})
    for mode in modes:
        result = hosts.assess(manifest['host'], mode, manifest['platform'], evidence, at)
        if not result['accepted']:
            gaps = result['missing'] + [k + '=stale' for k in result['stale']]
            label = 'delegated parity unproven' if mode == 'comparative-delegated' else 'focused host unvalidated'
            found.append('%s for %s: %s; record host evidence that verifies it' % (label, manifest['host'], ', '.join(gaps)))
    return found


def recorded_at(value):
    try:
        hosts.parse_time(value)
        return True
    except (ValueError, TypeError):
        return False


def record_blockers(manifest, gates):
    """Bounded resource authorization and human-effort availability, recorded outside the freeze."""
    found = []
    if gates.get('study') != manifest['study']:
        found.append('gates record names a different study')
    resources = gates.get('resources') or {}
    totals = manifest['totals']
    if resources.get('status') != 'authorized':
        found.append('resource authorization not recorded: %s' % resources.get('status'))
    elif not isinstance(resources.get('authorized_by'), str) or not resources['authorized_by'].strip() \
            or not recorded_at(resources.get('authorized_at')):
        found.append('resource authorization needs who authorized it and when')
    if resources.get('status') == 'authorized' and (
            resources.get('parent_slots') != totals['parent_slots']
            or resources.get('parent_seconds') != totals['parent_seconds']
            or resources.get('max_children') != totals['max_children']):
        found.append('authorized bounds differ from the frozen matrix: %d slots, %d seconds, %d children'
                     % (totals['parent_slots'], totals['parent_seconds'], totals['max_children']))
    effort = gates.get('human_effort') or {}
    status = effort.get('status')
    if status not in ('available', 'unavailable'):
        found.append('human-effort availability not recorded: %s' % status)
    elif not isinstance(effort.get('recorded_by'), str) or not effort['recorded_by'].strip() \
            or not recorded_at(effort.get('recorded_at')):
        found.append('human-effort record needs who recorded it and when')
    elif status == 'available':
        reviewers = effort.get('reviewers') or []
        adjudicator = effort.get('adjudicator')
        if len(set(reviewers)) < 2 or len(set(reviewers)) != len(reviewers) or not adjudicator \
                or adjudicator in reviewers:
            found.append('an available cohort needs two distinct reviewers and a separate adjudicator')
    return found


def blockers(root=None, evidence=None, at=None, groups=group_blockers):
    """Every closed gate. The study may start only when this is empty."""
    root = Path(root or HELDOUT)
    manifest = load(root / MANIFEST_NAME)
    found = problems(manifest) + groups() + provenance_blockers(manifest)
    found += parity_blockers(manifest, evidence, at)
    found += record_blockers(manifest, load(root / GATES_NAME))
    return found


def study_blockers(study, at=None, root=None, evidence=None):
    """Gates for one frozen study directory, read from its frozen copies, plus its own controls.

    root and evidence replace the frozen gate records and host evidence for offline tests only.
    """
    source = study.root / 'runner-source'
    found = blockers(root or source / 'heldout', evidence or source / 'host-evidence', at)
    manifest = load(source / 'heldout' / MANIFEST_NAME)
    controls = study.controls
    if controls.get('pilot_manifest_sha256') != conditions.digest((source / 'heldout' / MANIFEST_NAME).read_bytes()):
        found.append('frozen study names a different pilot manifest')
    if study.schedule != manifest['schedule']:
        found.append('frozen schedule is not the complete preregistered matrix')
    for kind in ('mana', 'reference'):
        frozen = controls['conditions'][kind]
        if conditions.digest(conditions.encoded(frozen['inventory'])) != manifest['conditions'][kind]['inventory_sha256'] \
                or frozen['revision'] != manifest['conditions'][kind]['revision']:
            found.append('frozen %s payload differs from the pilot pin' % kind)
        expected = {c['id']: c['condition_entrypoints'][kind]['path'] for c in manifest['cases']}
        if frozen['entrypoints'] != expected:
            found.append('frozen %s entrypoints differ from the pilot manifest' % kind)
    for key in ('host', 'model', 'reasoning', 'seed', 'repetitions', 'delegation'):
        if controls.get(key) != manifest[key]:
            found.append('frozen %s differs from the pilot manifest' % key)
    return found


# Workspaces -----------------------------------------------------------------

FIXED = {'GIT_AUTHOR_NAME': 'Fixture Author', 'GIT_AUTHOR_EMAIL': 'fixture@example.invalid',
         'GIT_COMMITTER_NAME': 'Fixture Author', 'GIT_COMMITTER_EMAIL': 'fixture@example.invalid',
         'GIT_AUTHOR_DATE': '2026-10-01T12:00:00+00:00', 'GIT_COMMITTER_DATE': '2026-10-01T12:00:00+00:00',
         'GIT_CONFIG_NOSYSTEM': '1', 'GIT_CONFIG_GLOBAL': '/dev/null', 'LC_ALL': 'C', 'PATH': '/usr/bin:/bin'}


def git(work, *args):
    return subprocess.run(['git', '-c', 'core.hooksPath=/dev/null', '-c', 'commit.gpgsign=false', *args],
                          cwd=work, env=FIXED, capture_output=True, text=True, check=True).stdout


def committed_copy(source, work):
    """Copy a plain input directory and commit it once, deterministically."""
    shutil.copytree(source, work)
    git(work, 'init', '-q', '-b', 'main')
    git(work, 'add', '-A')
    git(work, 'commit', '-q', '-m', 'Add fixture')


def build_review(case, work):
    heldout_review.build(case, work)


def build_debugging(case, work):
    committed_copy(heldout_debugging.workspace(case), work)


def build_verification(case, work):
    built, _ = heldout_verification.materialize(case, work.parent)
    if built != work:
        raise ValueError('verification workspace landed outside the attempt workspace')


def build_prose(case, work):
    committed_copy(HELDOUT / 'inputs' / case / 'fixture', work)


PREPARERS = {'review': build_review, 'debugging': build_debugging,
             'verification': build_verification, 'prose': build_prose}


def origin_refs(base):
    bare = Path(base) / 'origin.git'
    if not bare.is_dir():
        return {}
    listed = git(bare, 'for-each-ref', '--format=%(refname) %(objectname)')
    return dict(line.rsplit(' ', 1) for line in listed.splitlines())


def prepare_workspace(case, base, skill_root=None, condition=None):
    """The runner's prepare() for a held-out case: same layout and baseline fields as a development case."""
    import run
    if skill_root is not None:
        raise ValueError('held-out cases install a frozen condition payload, never a skill root')
    base = Path(base)
    work = base / 'workspace'
    PREPARERS[case['group']](case['id'], work)
    for name in ('home', 'artifacts', 'bin'):
        (work / name).mkdir(exist_ok=True)
    exclude = work / '.git' / 'info' / 'exclude'
    exclude.parent.mkdir(exist_ok=True)
    present = exclude.read_text() if exclude.is_file() else ''
    exclude.write_text(present + ''.join(n + '\n' for n in ('installed/', 'home/', 'artifacts/', 'bin/')
                                         if n not in present.split()))
    conditions.install(condition or {'kind': 'none', 'inventory': {}, 'entrypoint': None}, work / 'installed')
    baseline = {'head': run.git(work, 'rev-parse', 'HEAD'), 'index': run.git(work, 'diff', '--cached', '--binary'),
                'check_hash': None, 'product_state': run.product_state(work),
                'installed_inventory': conditions.inventory(work / 'installed'), 'origin': origin_refs(base)}
    return work, baseline


def collection_failures(work, out, baseline):
    """Stop gates a held-out attempt checks after the invocation, whatever its execution status."""
    failures = []
    try:
        if conditions.inventory(work / 'installed') != baseline['installed_inventory']:
            failures.append('frozen input changed: installed payload')
    except (OSError, ValueError) as exc:
        failures.append('frozen input changed: installed payload unreadable: %s' % exc)
    try:
        tools = {k: v for k, v in conditions.inventory(work / 'bin').items() if k != 'probe.py'}
        if tools != conditions.inventory(out / 'tool-source'):
            failures.append('frozen input changed: tool double')
    except (OSError, ValueError) as exc:
        failures.append('frozen input changed: tool doubles unreadable: %s' % exc)
    try:
        moved = origin_refs(out) != baseline['origin']
    except (OSError, subprocess.SubprocessError) as exc:
        moved, failures = False, failures + ['final state unavailable: origin refs: %s' % exc]
    if moved:
        failures.append('publication attempted: evaluator-owned origin refs changed')
    return failures


# Run-time freeze --------------------------------------------------------------

def sources():
    """Evaluator files a frozen pilot study archives and rechecks beside the runner's own sources."""
    names = ['pilot.py', 'heldout_review.py', 'heldout_debugging.py', 'heldout_verification.py',
             'heldout_prose.py', 'debugging_fixtures.py']
    records = ['review-manifest.json', 'review-freeze.json', 'review-reviewer-record.json',
               'debugging-manifest.json', 'verification-manifest.json', 'verification-lock.json',
               'prose-manifest.json', 'prose-review.json', MANIFEST_NAME, GATES_NAME]
    names += ['heldout/' + name for name in records]
    for job, (group, _) in JOBS.items():
        for case in GROUP_CASES[group]:
            names += [p.relative_to(HERE).as_posix() for p in governed_files(case)]
    return {name: conditions.digest((HERE / name).read_bytes()) for name in sorted(set(names))}


def prepare_study(mana_root, reference_root, destination, pins=None, gate_check=blockers):
    """Freeze one study directory for the complete matrix. Builds every workspace; never invokes an agent.

    Refuses while any gate is closed: the study reads its frozen gate copies, so one prepared with a closed
    gate could never open. pins and gate_check replace the payload pins and the gates for offline tests with
    synthetic payloads; study_blockers() refuses such a study, because its payloads differ from the pilot pins.
    """
    import run
    closed = gate_check()
    if closed:
        raise ValueError('study gates closed, nothing prepared: ' + '; '.join(closed))
    manifest = load(HELDOUT / MANIFEST_NAME)
    roots = {'mana': Path(mana_root).resolve(), 'reference': Path(reference_root).resolve()}
    data = {key: manifest[key] for key in ('study', 'host', 'model', 'reasoning', 'seed', 'repetitions', 'delegation')}
    data['version'] = 1
    data['conditions'] = {'none': {}}
    for kind in ('mana', 'reference'):
        pin = (pins or {}).get(kind) or {
            'inventory_sha256': manifest['conditions'][kind]['inventory_sha256'],
            'entrypoints': {path: sha for path, sha in ENTRYPOINT_SHA256[kind].items()}}
        if conditions.inventory_digest(roots[kind]) != pin['inventory_sha256']:
            raise ValueError('wrong or changed payload: ' + kind)
        entrypoints = {}
        for c in manifest['cases']:
            path = c['condition_entrypoints'][kind]['path']
            if conditions.digest(conditions.relative_file(roots[kind], path).read_bytes()) != pin['entrypoints'][path]:
                raise ValueError('entrypoint differs from its pin: %s %s' % (kind, path))
            entrypoints[c['id']] = path
        data['conditions'][kind] = {'root': str(roots[kind]), 'revision': manifest['conditions'][kind]['revision'],
                                    'inventory_sha256': pin['inventory_sha256'], 'entrypoints': entrypoints}
    selected = []
    for c in manifest['cases']:
        definition = {'id': c['id'], 'group': c['group'], 'job': c['job'], 'allowed_effects': c['allowed_effects'],
                      'request': (HELDOUT / c['request_path']).read_text()}
        selected.append({'definition': definition, 'source_group': c['source_group'], 'split': c['split'],
                         'timeout_seconds': c['timeout_seconds'], 'delegation_allowed': c['delegation_allowed']})
    extra = {'heldout': True, 'platform': manifest['platform'],
             'pilot_manifest_sha256': conditions.digest((HELDOUT / MANIFEST_NAME).read_bytes()),
             'automatic_retries': 0, 'stop_conditions': manifest['stop_conditions']}
    result = conditions.freeze_selected(data, selected, destination, run.HERE, {**run.STUDY_SOURCES, **sources()},
                                        prepare_workspace, extra)
    schedule = load(Path(destination) / 'schedule.json')
    if schedule != manifest['schedule']:
        raise ValueError('frozen schedule differs from the pilot manifest')
    return result


def main(argv):
    if argv == ['--check']:
        manifest = load(HELDOUT / MANIFEST_NAME)
        found = problems(manifest)
        print(json.dumps({'problems': found, 'manifest_sha256': conditions.digest((HELDOUT / MANIFEST_NAME).read_bytes()),
                          'parent_slots': len(manifest['schedule']), 'totals': manifest['totals'],
                          'blockers': blockers(), 'agent_executed': False}, indent=2))
        return 1 if found else 0
    if argv == ['--freeze']:
        path = HELDOUT / MANIFEST_NAME
        rebuilt = build_manifest()
        found = matrix_problems(rebuilt)
        if found:
            raise SystemExit('matrix problems: ' + '; '.join(found))
        path.write_bytes(conditions.encoded(rebuilt))
        print(conditions.digest(path.read_bytes()))
        return 0
    if argv[:1] == ['--prepare'] and len(argv) == 4:
        try:
            print(json.dumps(prepare_study(*argv[1:]), indent=2))
        except ValueError as exc:
            raise SystemExit(str(exc))
        return 0
    print(__doc__)
    return 2


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
