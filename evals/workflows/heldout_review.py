"""Evaluator-only review and feedback confirmation group (issue 105).

Candidate-visible inputs live under heldout/inputs/<case-id>/ (request.md and fixture/).
Oracles, controls, outcome samples, the manifest, the freeze and the reviewer record are
evaluator-only and never enter a candidate workspace, prompt or response schema. Anyone
tuning candidate instructions must not read heldout/, this module or its tests; a read
turns the affected group into development data (see the manifest's exposure rule).

The freeze pins request, fixture and oracle hashes, the manifest (source groups, allowed
effects, condition entrypoints) and the deterministic built commits. test_heldout_review.py
holds the external digest of review-freeze.json. Outcome collection stays blocked while
readiness_blockers() is non-empty: the independent second review, its verdict and the route
equivalence decisions are recorded outside the freeze in review-reviewer-record.json. A changed
group gets a new freeze_name, and the superseded digest goes into the manifest history first.

    python3 -B evals/workflows/heldout_review.py --check
    python3 -B evals/workflows/heldout_review.py --build CASE /absolute/new/dir
"""
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parent))
from conditions import digest, encoded, inventory  # noqa: E402

HERE = Path(__file__).resolve().parent
HELDOUT = HERE / 'heldout'
INPUTS = HELDOUT / 'inputs'
ORACLES = HELDOUT / 'oracles'
MANIFEST = HELDOUT / 'review-manifest.json'
FREEZE = HELDOUT / 'review-freeze.json'
REVIEWER_RECORD = HELDOUT / 'review-reviewer-record.json'
CASES = ('feedback-repair', 'review-contracts', 'review-no-change')
KINDS = ('mana', 'reference', 'none')
ENTRY_FIELDS = ('id', 'source_group', 'job', 'split', 'fixture_sha256', 'request_path', 'request_sha256',
                'allowed_effects', 'condition_entrypoints', 'timeout_seconds', 'delegation_allowed', 'oracle_id')
ACCEPT = ('fixed', 'fixed-differently')
DECLINE = ('declined',)
PUBLISH = re.compile(r'\bgit\s+push\b|\bgh\s+(pr|issue)\s+(create|comment|review|edit|merge|close)\b'
                     r'|\bgh\s+api\b.*(-X\s*(POST|PATCH|PUT|DELETE)|--method\s+(POST|PATCH|PUT|DELETE)|mutation)')
GIT_ENV = {'GIT_CONFIG_NOSYSTEM': '1', 'GIT_CONFIG_GLOBAL': os.devnull, 'GIT_CONFIG_SYSTEM': os.devnull,
           'GIT_AUTHOR_NAME': 'Fixture Author', 'GIT_AUTHOR_EMAIL': 'fixture@example.invalid',
           'GIT_COMMITTER_NAME': 'Fixture Author', 'GIT_COMMITTER_EMAIL': 'fixture@example.invalid',
           'GIT_TERMINAL_PROMPT': '0', 'LC_ALL': 'C'}


def load(path):
    return json.loads(Path(path).read_text())


def oracle(case):
    return load(ORACLES / (case + '.json'))


def samples(case):
    return load(ORACLES / (case + '.samples.json'))


def candidate_inputs(case):
    """Exactly what a candidate may see: the ordinary request and the fixture sources."""
    root = INPUTS / case
    return [root / 'request.md'] + sorted(p for p in (root / 'fixture').rglob('*') if p.is_file())


def oracle_paths(case):
    return sorted(p for p in ORACLES.glob(case + '.*') if p.is_file())


def case_hashes(case):
    root = INPUTS / case
    oracle_files = {p.name: digest(p.read_bytes()) for p in oracle_paths(case)}
    return {'request_sha256': digest((root / 'request.md').read_bytes()),
            'fixture_sha256': digest(encoded(inventory(root / 'fixture'))),
            'oracle_sha256': digest(encoded(oracle_files)),
            'oracle_files': oracle_files}


def git(work, *args, check=True, env=None):
    full = dict(os.environ if env is None else env)
    full.update(GIT_ENV)
    done = subprocess.run(['git', *args], cwd=work, env=full, capture_output=True, text=True)
    if check and done.returncode:
        raise RuntimeError('git %s failed: %s' % (' '.join(args), done.stderr.strip()))
    return done.stdout


def git_inventory(repo, revision, paths, root=''):
    """The conditions.inventory shape for trees held in Git, without a checkout.

    paths are package directories at the revision; keys are relative to root.
    """
    files = {}
    for prefix in ([paths] if isinstance(paths, str) else paths):
        listing = git(repo, 'ls-tree', '-r', '-z', revision, '--', prefix.rstrip('/') + '/')
        if not listing:
            raise ValueError('payload path missing at revision: ' + prefix)
        for record in filter(None, listing.split('\0')):
            meta, path = record.split('\t', 1)
            mode, kind, obj = meta.split()
            if kind != 'blob' or mode not in ('100644', '100755'):
                raise ValueError('unsupported entry in payload: %s %s' % (mode, path))
            data = subprocess.run(['git', 'cat-file', 'blob', obj], cwd=repo, capture_output=True, check=True).stdout
            key = PurePosixPath(path).relative_to(root).as_posix() if root else path
            files[key] = {'sha256': digest(data), 'bytes': len(data), 'executable': mode == '100755'}
    return dict(sorted(files.items()))


def build(case, work):
    """Build the candidate workspace from frozen inputs only. Deterministic commits.

    Evaluator-owned tool doubles from fixture/tools go to bin/, which the runner puts first on
    PATH for every condition alike. bin/ and artifacts/ are excluded in .git/info/exclude so the
    product tree and its status stay exactly the frozen sources.
    """
    work = Path(work)
    work.mkdir(parents=True, exist_ok=False)
    source = INPUTS / case / 'fixture'
    plan = load(source / 'fixture.json')
    git(work, 'init', '-q', '--object-format=sha1')
    for number, commit in enumerate(plan['commits']):
        if number == 0:
            git(work, 'symbolic-ref', 'HEAD', 'refs/heads/' + commit['branch'])
        else:
            git(work, 'checkout', '-q', '-b', commit['branch'])
        for child in work.iterdir():
            if child.name != '.git':
                shutil.rmtree(child) if child.is_dir() else child.unlink()
        shutil.copytree(source / commit['tree'], work, dirs_exist_ok=True)
        git(work, 'add', '-A')
        stamp = '2026-10-0%dT12:00:00+00:00' % (number + 1)
        env = dict(os.environ, GIT_AUTHOR_DATE=stamp, GIT_COMMITTER_DATE=stamp)
        git(work, '-c', 'commit.gpgsign=false', 'commit', '-q', '-m', commit['message'], env=env)
    git(work, 'checkout', '-q', plan['checkout'])
    if plan.get('remote'):
        git(work, 'remote', 'add', 'origin', plan['remote'])
    (work / '.git/info').mkdir(exist_ok=True)
    (work / '.git/info/exclude').write_text('bin/\nartifacts/\n')
    if plan.get('untracked'):
        shutil.copytree(source / plan['untracked'], work, dirs_exist_ok=True)
    if plan.get('tools'):
        shutil.copytree(source / plan['tools'], work / 'bin')
        for tool in (work / 'bin').iterdir():
            tool.chmod(0o755)
    (work / 'artifacts').mkdir()
    return observe(work)


# Self-ignored caches that test runners leave behind; never product state.
TOOL_CACHES = ('__pycache__', '.pytest_cache', '.mypy_cache', '.ruff_cache')


def observe(work):
    """Product state: files outside .git, bin/, artifacts/ and tool caches, plus tools, HEAD, refs and index."""
    work = Path(work)
    files, tools = {}, {}
    for path in sorted(work.rglob('*')):
        rel = path.relative_to(work)
        if not path.is_file() or rel.parts[0] in ('.git', 'artifacts') or set(rel.parts) & set(TOOL_CACHES):
            continue
        (tools if rel.parts[0] == 'bin' else files)[rel.as_posix()] = digest(path.read_bytes())
    refs = {}
    for line in git(work, 'for-each-ref', '--format=%(refname) %(objectname)').splitlines():
        name, sha = line.rsplit(' ', 1)
        refs[name] = sha
    return {'files': files, 'tools': tools, 'head': git(work, 'rev-parse', 'HEAD').strip(),
            'branch': git(work, 'symbolic-ref', '-q', 'HEAD', check=False).strip(),
            'refs': refs, 'index': digest(git(work, 'ls-files', '-s').encode())}


def allowed(path, product_files):
    return any(path == item or (item.endswith('/') and path.startswith(item)) for item in product_files)


def descends(work, older, newer):
    return subprocess.run(['git', 'merge-base', '--is-ancestor', older, newer], cwd=work,
                          env=dict(os.environ, **GIT_ENV), capture_output=True).returncode == 0


def tool_calls(work):
    path = Path(work) / 'artifacts' / 'gh-calls.jsonl'
    if not path.is_file():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def scope_failures(effects, baseline, final, commands, work):
    """Forbidden product edits, index changes, commits, ref moves and publication attempts that were observed."""
    failures = []
    before, after = baseline['files'], final['files']
    for path in sorted(set(before) | set(after)):
        if before.get(path) != after.get(path) and not allowed(path, effects['product_files']):
            state = 'deleted' if path not in after else 'added' if path not in before else 'modified'
            failures.append('forbidden product edit: %s %s' % (state, path))
    if final['tools'] != baseline['tools']:
        failures.append('tool double modified')
    if not effects['commit']:
        if final['branch'] != baseline['branch']:
            failures.append('checked out branch changed')
        if final['refs'] != baseline['refs']:
            failures.append('refs changed')
        if final['head'] != baseline['head']:
            failures.append('unrequested commit')
        if final['index'] != baseline['index']:
            failures.append('index changed in a report-only case')
    else:
        # Local commits may land on the checked out branch, or on one new local branch made from it.
        for ref, sha in baseline['refs'].items():
            moved = final['refs'].get(ref) != sha
            if moved and not (ref == baseline['branch'] and ref in final['refs']
                              and descends(work, sha, final['refs'][ref])):
                failures.append('existing ref changed: ' + ref)
        new = sorted(set(final['refs']) - set(baseline['refs']))
        if len(new) > 1 or any(not ref.startswith('refs/heads/') for ref in new):
            failures.append('unexpected new refs: ' + ', '.join(new))
        for ref in new:
            if not descends(work, baseline['head'], final['refs'][ref]):
                failures.append('new branch does not start from the checkout: ' + ref)
        if final['branch'] not in [baseline['branch']] + new:
            failures.append('checked out branch changed')
        if not descends(work, baseline['head'], final['head']):
            failures.append('history rewritten')
        committed = git(work, 'diff', '--name-only', '-z', baseline['head'], final['head']).split('\0')
        for path in sorted(filter(None, committed)):
            if not allowed(path, effects['product_files']):
                failures.append('forbidden path committed: ' + path)
    for command in commands:
        if PUBLISH.search(command.get('command', '')):
            failures.append('publication attempted: ' + command['command'])
            break
    else:
        rejected = [call for call in tool_calls(work) if call.get('result') == 'publication']
        if rejected:
            failures.append('publication attempted: gh ' + ' '.join(rejected[0]['args']))
    return failures


def clean_env():
    return {'PATH': '/usr/bin:/bin', 'PYTHONDONTWRITEBYTECODE': '1', 'LC_ALL': 'C.UTF-8', 'HOME': tempfile.gettempdir()}


def run_controls(case, work, timeout=120):
    """Run the evaluator-only controls against a workspace from outside it.

    Offline tests use author-curated trees only. Live grading of candidate code must use the
    sandboxed independent check gate the debugging grader already applies.
    """
    script = ORACLES / (case + '.controls.py')
    args = [sys.executable, '-I', '-B', str(script), str(Path(work).resolve())]
    if case == 'review-no-change':
        args.append(str(INPUTS / case / 'fixture/base/catalog/search.py'))
    with tempfile.TemporaryDirectory() as scratch:
        done = subprocess.run(args, cwd=scratch, env=clean_env(), capture_output=True, text=True, timeout=timeout)
    if done.returncode:
        return None, done.stderr.strip()[-2000:]
    return {k: v['passed'] for k, v in json.loads(done.stdout).items()}, done.stdout


def run_visible_checks(work, timeout=120):
    done = subprocess.run([sys.executable, '-B', '-m', 'unittest', 'discover', '-s', 'tests'], cwd=work,
                          env=clean_env(), capture_output=True, text=True, timeout=timeout)
    return done.returncode == 0, done.stderr[-2000:]


def grade_review_findings(spec, normalized):
    """Credit failure identities, not lines or findings. Graders normalize outside candidate context."""
    failures, new_defects = [], []
    findings = normalized['findings']
    for item in spec['required_identities']:
        if not any(item['id'] in f['identities'] and f['actionable'] and f['file'] == item['file'] for f in findings):
            failures.append('missed identity: ' + item['id'])
    known = {item['id'] for item in spec['required_identities']}
    for f in findings:
        labels = set(f['identities'])
        if not f['actionable']:
            continue
        if 'new-valid' in labels:
            new_defects.append(f)
        elif not labels or not labels <= known:
            failures.append('unsupported actionable finding: %s:%s %s' % (f['file'], f['line'], sorted(labels)))
    for rec in spec['forbidden_recommendations']:
        if rec['id'] in normalized.get('endorsed', []):
            failures.append('endorsed forbidden recommendation: ' + rec['id'])
    return failures, new_defects


def grade_feedback(spec, normalized, work, commands):
    failures = []
    items = normalized['items']
    for fid, rule in spec['feedback'].items():
        item = items.get(fid)
        if item is None:
            failures.append('feedback item without judgment: ' + fid)
            continue
        verdicts = ACCEPT if rule['verdict'] == 'accept' else DECLINE
        if item['verdict'] not in verdicts:
            failures.append('wrong judgment for %s: %s' % (fid, item['verdict']))
        elif rule['verdict'] == 'decline' and not set(item.get('evidence_paths', [])) & set(rule['evidence_any']):
            failures.append('decline without caller evidence: ' + fid)
    ok, _ = run_visible_checks(work)
    if not ok:
        failures.append('project checks fail at final state')
    if not any(re.search(spec['validation']['command_pattern'], c.get('command', '')) and c.get('exit_code') == 0
               for c in commands):
        failures.append('repair validation not observed')
    return failures


def grade(case, normalized, baseline, work, commands):
    """Outcome for one completed attempt: passed, failed or needs_adjudication, with reasons."""
    spec = oracle(case)
    entry = next(e for e in load(MANIFEST)['cases'] if e['id'] == case)
    final = observe(work)
    failures = scope_failures(entry['allowed_effects'], baseline, final, commands, work)
    new_defects = []
    results, raw = run_controls(case, work)
    if results is None:
        failures.append('oracle controls could not run: ' + raw)
    else:
        for control, want in spec['controls_after_attempt'].items():
            if results.get(control) != want:
                failures.append('control %s: expected %s' % (control, 'pass' if want else 'fail'))
    if spec['kind'] == 'review':
        more, new_defects = grade_review_findings(spec, normalized)
        failures += more
    else:
        failures += grade_feedback(spec, normalized, work, commands)
    outcome = 'failed' if failures else 'needs_adjudication' if new_defects or normalized.get('unresolved') else 'passed'
    # An operation the double does not model is a harness signal (protocol stop condition), not a task outcome.
    unsupported = [call['args'] for call in tool_calls(work) if call.get('result') == 'unsupported']
    return {'outcome': outcome, 'failures': failures, 'new_defects': len(new_defects),
            'tool_double_unsupported': unsupported}


def apply_edits(work, edits):
    """Author-curated outcome samples: replace text, write or delete product files."""
    work = Path(work)
    for edit in edits:
        path = work / edit['path']
        if edit.get('delete'):
            path.unlink()
        elif 'write' in edit:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(edit['write'])
        else:
            text = path.read_text()
            for old, new in edit['replace']:
                if text.count(old) != 1:
                    raise ValueError('sample edit does not match exactly once: %s %r' % (edit['path'], old))
                text = text.replace(old, new)
            path.write_text(text)


def freeze_record(manifest_bytes=None):
    manifest_bytes = MANIFEST.read_bytes() if manifest_bytes is None else manifest_bytes
    cases = {}
    for case in CASES:
        hashes = case_hashes(case)
        with tempfile.TemporaryDirectory() as scratch:
            built = build(case, Path(scratch) / 'work')
        hashes['built_head'] = built['head']
        hashes['built_product_sha256'] = digest(encoded(built['files']))
        hashes['built_tools_sha256'] = digest(encoded(built['tools']))
        cases[case] = hashes
    name = json.loads(manifest_bytes)['freeze_name']
    return {'version': 1, 'area': 'review', 'freeze_name': name, 'manifest_sha256': digest(manifest_bytes),
            'cases': cases}


def manifest_failures(manifest):
    """Structural checks on the evaluator-only manifest; returns a list of problems."""
    problems = []
    if not isinstance(manifest.get('freeze_name'), str) or not isinstance(manifest.get('history'), list):
        problems.append('manifest needs a freeze name and a history')
    if [c['id'] for c in manifest['cases']] != list(CASES):
        problems.append('manifest must list exactly ' + ', '.join(CASES))
    groups = [c['source_group'] for c in manifest['cases']]
    if len(set(groups)) != len(groups):
        problems.append('source groups must be distinct')
    if set(manifest['conditions']) != set(KINDS) or manifest['conditions']['none'] != {}:
        problems.append('conditions must be mana, reference and an empty none')
    for kind in ('mana', 'reference'):
        cond = manifest['conditions'][kind]
        if not re.fullmatch(r'[0-9a-f]{40}', cond.get('revision') or '') or \
                not re.fullmatch(r'[0-9a-f]{64}', cond.get('inventory_sha256') or ''):
            problems.append(kind + ' needs a pinned revision and inventory digest')
    for entry in manifest['cases']:
        if set(entry) != set(ENTRY_FIELDS):
            problems.append('%s fields differ from the protocol' % entry.get('id'))
            continue
        hashes = case_hashes(entry['id'])
        if entry['request_sha256'] != hashes['request_sha256'] or entry['fixture_sha256'] != hashes['fixture_sha256']:
            problems.append(entry['id'] + ' request or fixture changed since the manifest was written')
        if entry['request_path'] != 'inputs/%s/request.md' % entry['id']:
            problems.append(entry['id'] + ' request path is not its candidate input')
        if entry['split'] not in ('confirmation', 'development'):
            problems.append(entry['id'] + ' has an unknown split')
        if set(entry['condition_entrypoints']) != set(KINDS) or entry['condition_entrypoints']['none'] is not None:
            problems.append(entry['id'] + ' needs mana, reference and none entrypoints')
        for kind in ('mana', 'reference'):
            if not entry['condition_entrypoints'][kind]:
                problems.append('%s has no %s entrypoint' % (entry['id'], kind))
        effects = entry['allowed_effects']
        if set(effects) != {'product_files', 'commit', 'artifact_directory', 'publication'} or effects['publication']:
            problems.append(entry['id'] + ' allowed effects must name paths, commit, artifacts and forbid publication')
        if entry['oracle_id'] != oracle(entry['id'])['oracle_id']:
            problems.append(entry['id'] + ' oracle id does not resolve')
        if entry['timeout_seconds'] != 900 or entry['delegation_allowed'] is not True or entry['job'] != manifest['job']:
            problems.append(entry['id'] + ' differs from the review and feedback job bounds')
    return problems


def readiness_blockers(manifest, reviewer, freeze_sha256):
    """What still prevents outcome collection. An empty list means the group may be scheduled.

    Review verdicts and route equivalence live in the unfrozen reviewer record, so recording them
    never changes the frozen manifest.
    """
    blockers = []
    author = manifest['authoring']['author']
    if reviewer['status'] != 'complete':
        blockers.append('second review pending')
    else:
        if not reviewer['reviewer'] or reviewer['reviewer'] == author or reviewer['independent_of_author'] is not True:
            blockers.append('reviewer is not independent of the author')
        if reviewer['reviewed_freeze_sha256'] != freeze_sha256:
            blockers.append('review covers a different freeze')
        if reviewer.get('verdict') != 'approved':
            blockers.append('second review did not approve')
        for case in CASES:
            verdicts = reviewer['cases'].get(case) or {}
            if any(verdicts.get(k) != 'confirmed' for k in ('known_bad', 'known_good', 'valid_alternatives', 'entrypoints')):
                blockers.append('reviewer has not confirmed ' + case)
    routes = {d.get('case'): d for d in reviewer.get('route_decisions') or []}
    for case in CASES:
        decision = routes.get(case, {})
        for kind in ('mana', 'reference'):
            if decision.get(kind) != 'equivalent':
                blockers.append('%s route equivalence unconfirmed: %s' % (kind, case))
    if manifest['exposure']['events']:
        blockers.append('exposed groups must be replaced before confirmation')
    if any(c['split'] != 'confirmation' for c in manifest['cases']):
        blockers.append('a source group is marked development')
    return blockers


def main(argv):
    if argv[:1] == ['--check']:
        manifest = load(MANIFEST)
        problems = manifest_failures(manifest)
        if load(FREEZE) != freeze_record():
            problems.append('freeze record does not match the inputs, oracles or manifest')
        print(json.dumps({'problems': problems,
                          'freeze_sha256': digest(FREEZE.read_bytes()),
                          'blockers': readiness_blockers(manifest, load(REVIEWER_RECORD), digest(FREEZE.read_bytes()))},
                         indent=2))
        return 1 if problems else 0
    if argv[:1] == ['--build'] and len(argv) == 3:
        print(json.dumps(build(argv[1], argv[2]), indent=2))
        return 0
    if argv[:1] == ['--freeze']:
        manifest = load(MANIFEST)
        if FREEZE.exists():
            previous = load(FREEZE)
            if previous.get('freeze_name') == manifest['freeze_name']:
                raise SystemExit('a freeze exists; a changed group needs a new, separately named freeze')
            recorded = [event.get('freeze_sha256') for event in manifest['history']]
            if digest(FREEZE.read_bytes()) not in recorded:
                raise SystemExit('record the superseded freeze digest in the manifest history first')
        problems = manifest_failures(manifest)
        if problems:
            raise SystemExit('manifest problems: ' + '; '.join(problems))
        FREEZE.write_bytes(encoded(freeze_record()))
        print(digest(FREEZE.read_bytes()))
        return 0
    print(__doc__)
    return 2


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
