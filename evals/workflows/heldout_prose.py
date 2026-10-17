"""Held-out prose-fidelity groups: freeze integrity and evaluator-only oracle screens.

Candidates see only heldout/inputs/<case>/. Oracles under heldout/oracles/ never enter a
prompt, a fixture workspace or the response schema. No model is invoked here.
"""
import argparse
import json
from pathlib import Path
import re
import sys

import conditions

HERE = Path(__file__).resolve().parent
HELDOUT = HERE / 'heldout'
MANIFEST_NAME = 'prose-manifest.json'
REVIEW_NAME = 'prose-review.json'
CASES = ('prose-exempt', 'prose-scope', 'prose-verbatim')
JOB = 'prose-fidelity'
TOP_FIELDS = ('schema_version', 'study', 'job', 'status', 'conditions', 'cases', 'exposure', 'freeze_sha256')
FROZEN_FIELDS = ('schema_version', 'study', 'job', 'conditions', 'cases', 'exposure')
ENTRY_FIELDS = ('id', 'source_group', 'job', 'split', 'fixture_path', 'fixture_sha256', 'request_path',
                'request_sha256', 'allowed_effects', 'condition_entrypoints', 'timeout_seconds',
                'delegation_allowed', 'oracle_id', 'oracle_sha256')
EFFECT_FIELDS = ('product_paths', 'local_commit', 'artifact_dir', 'external_publication')
HEX40 = re.compile(r'[0-9a-f]{40}')
RELATIVE = re.compile(r'[A-Za-z0-9_-][A-Za-z0-9_.-]*(/[A-Za-z0-9_-][A-Za-z0-9_.-]*)*')
# A sentence span that does not stop at the dot inside a version such as 4.2.
SENTENCE = r'(?:[^.;]|\.(?=\d))*'


def load(root=HELDOUT):
    root = Path(root)
    return (json.loads((root / MANIFEST_NAME).read_text()),
            json.loads((root / REVIEW_NAME).read_text()))


def oracle_files(root, case_id):
    return Path(root) / 'oracles' / (case_id + '.json'), Path(root) / 'oracles' / case_id


def load_oracle(root, case_id):
    return json.loads(oracle_files(root, case_id)[0].read_bytes())


def computed_hashes(root, entry):
    root = Path(root)
    oracle_json, support = oracle_files(root, entry['id'])
    return {
        'request_sha256': conditions.digest((root / entry['request_path']).read_bytes()),
        'fixture_sha256': conditions.inventory_digest(root / entry['fixture_path']),
        'oracle_sha256': conditions.digest(conditions.encoded({
            'oracle': conditions.digest(oracle_json.read_bytes()),
            'support': conditions.inventory(support) if support.exists() else {}})),
    }


def freeze_sha256(manifest):
    return conditions.digest(conditions.encoded({k: manifest[k] for k in FROZEN_FIELDS}))


def fixture_files(root, entry):
    base = Path(root) / entry['fixture_path']
    return {p.relative_to(base).as_posix(): p.read_text() for p in sorted(base.rglob('*')) if p.is_file()}


def verify(root=HELDOUT):
    """Return every freeze problem; an empty list means the frozen bytes match the manifest."""
    root = Path(root)
    problems = []
    manifest, review = load(root)
    if tuple(manifest) != TOP_FIELDS:
        return ['manifest fields differ from the frozen layout']
    if manifest['job'] != JOB or manifest['schema_version'] != 1:
        problems.append('manifest job or schema version changed')
    if [c.get('id') for c in manifest['cases']] != list(CASES):
        return problems + ['case list differs from ' + ', '.join(CASES)]
    exposed = set()
    for item in manifest['exposure']:
        if set(item) != {'source_group', 'reader', 'date', 'reason'}:
            problems.append('exposure records need source_group, reader, date and reason')
        else:
            exposed.add(item['source_group'])
    problems += verify_conditions(manifest['conditions'])
    groups = set()
    for entry in manifest['cases']:
        case = entry['id']
        if tuple(entry) != ENTRY_FIELDS:
            problems.append(case + ': manifest entry fields differ from the specification')
            continue
        for key, value in computed_hashes(root, entry).items():
            if entry[key] != value:
                problems.append(f'{case}: {key} does not match frozen bytes')
        if entry['request_path'] != f'inputs/{case}/request.md' or entry['fixture_path'] != f'inputs/{case}/fixture':
            problems.append(case + ': inputs must live under inputs/<case>/')
        visible = {p.relative_to(root / 'inputs' / case).as_posix()
                   for p in (root / 'inputs' / case).rglob('*') if p.is_file()}
        if any(name != 'request.md' and not name.startswith('fixture/') for name in visible):
            problems.append(case + ': candidate inputs hold a file outside request.md and fixture/')
        group = entry['source_group']
        if not isinstance(group, str) or not conditions.IDENTIFIER.fullmatch(group) or group in groups:
            problems.append(case + ': source group must be a unique identifier')
        groups.add(group)
        expected_split = 'development' if group in exposed else 'confirmation'
        if entry['split'] != expected_split:
            problems.append(f'{case}: split must be {expected_split} for source group {group}')
        if entry['job'] != JOB or entry['timeout_seconds'] != 180 or entry['delegation_allowed'] is not False:
            problems.append(case + ': prose jobs run 180 seconds without delegation')
        effects = entry['allowed_effects']
        if not isinstance(effects, dict) or tuple(effects) != EFFECT_FIELDS:
            problems.append(case + ': allowed effects fields changed')
        else:
            files = fixture_files(root, entry)
            if (not set(effects['product_paths']) <= set(files) or effects['local_commit'] is not False
                    or effects['artifact_dir'] != 'artifacts/' or effects['external_publication'] is not False):
                problems.append(case + ': allowed effects exceed the fixture contract')
        mapping = entry['condition_entrypoints']
        if not isinstance(mapping, dict) or set(mapping) != set(conditions.KINDS) or mapping['none'] is not None:
            problems.append(case + ': condition mapping needs mana, reference and an empty none')
        else:
            for kind in ('mana', 'reference'):
                route = mapping[kind]
                if (not isinstance(route, dict) or set(route) != {'path', 'sha256'}
                        or not isinstance(route['path'], str) or not RELATIVE.fullmatch(route['path'])
                        or not isinstance(route['sha256'], str) or not conditions.DIGEST.fullmatch(route['sha256'])):
                    problems.append(f'{case}: {kind} entrypoint needs a relative path and SHA-256')
        oracle = load_oracle(root, case)
        if (oracle.get('oracle_id') != entry['oracle_id'] or oracle.get('case_id') != case
                or oracle.get('evaluator_only') is not True):
            problems.append(case + ': oracle identity does not match the manifest')
    if manifest['freeze_sha256'] != freeze_sha256(manifest):
        problems.append('freeze_sha256 does not match the frozen manifest fields')
    problems += verify_review(manifest, review)
    return problems


def verify_conditions(spec):
    problems = []
    if set(spec) != set(conditions.KINDS) or spec['none'] != {}:
        return ['conditions need mana, reference and an empty none']
    for kind in ('mana', 'reference'):
        item = spec[kind]
        required = {'source', 'revision', 'root', 'inventory_sha256', 'inventory_status'}
        if not isinstance(item, dict) or not required <= set(item):
            problems.append(kind + ': payload record is incomplete')
            continue
        if not isinstance(item['revision'], str) or not HEX40.fullmatch(item['revision']):
            problems.append(kind + ': payload revision must be a full commit')
        if item['inventory_status'] == 'verified':
            if not isinstance(item['inventory_sha256'], str) or not conditions.DIGEST.fullmatch(item['inventory_sha256']):
                problems.append(kind + ': verified payload needs an inventory digest')
        elif item['inventory_status'] != 'unresolved' or item['inventory_sha256'] is not None:
            problems.append(kind + ': an unverified payload digest must stay null')
    return problems


def verify_review(manifest, review):
    problems = []
    if set(review) != {'schema_version', 'freeze_sha256', 'author', 'second_review'}:
        return ['review record fields changed']
    if review['freeze_sha256'] != manifest['freeze_sha256']:
        problems.append('review record names a different freeze')
    author = review['author']
    if author.get('edits_candidate_instructions') is not False or not author.get('identity'):
        problems.append('fixture author must be named and must not edit candidate instructions')
    second = review['second_review']
    if second.get('status') == 'pending':
        if any(second.get(k) is not None for k in ('reviewer', 'reviewed_freeze_sha256', 'date')):
            problems.append('a pending second review cannot carry a reviewer result')
    elif second.get('status') == 'complete':
        checked = second.get('checked') or {}
        if (not second.get('reviewer') or second['reviewer'] == author['identity']
                or second.get('reviewed_freeze_sha256') != manifest['freeze_sha256']
                or set(checked) != {'contracts', 'known_good', 'known_bad', 'valid_alternatives'}
                or not all(v is True for v in checked.values())):
            problems.append('a complete second review needs a different reviewer, this freeze and every check')
    else:
        problems.append('second review status must be pending or complete')
    return problems


def readiness(root=HELDOUT):
    """Reasons the frozen groups cannot yet enter a confirmation run."""
    manifest, review = load(root)
    reasons = list(verify(root))
    for kind in ('mana', 'reference'):
        if manifest['conditions'][kind]['inventory_status'] != 'verified':
            reasons.append(kind + ' payload inventory is unresolved')
    if review['second_review']['status'] != 'complete':
        reasons.append('second review is pending')
    return reasons


def span(text, spec):
    """Select frozen bytes by markers; a missing marker is an oracle defect, never a pass."""
    position = -1
    for _ in range(spec.get('occurrence', 1)):
        position = text.find(spec['start'], position + 1)
        if position < 0:
            raise ValueError('oracle span start not found')
    begin = position if spec.get('include_start') else position + len(spec['start'])
    end = text.find(spec['end'], position + len(spec['start']))
    if end < 0:
        raise ValueError('oracle span end not found')
    return text[begin:end + (len(spec['end']) if spec.get('include_end') else 0)]


def words(text):
    return len(re.findall(r"[A-Za-z0-9_'`.]+", text))


def compiled(pattern):
    return re.compile(pattern.replace('{S}', SENTENCE), re.IGNORECASE | re.MULTILINE)


def screen_fact(fact, prose):
    """preserve: contradiction fails, a found statement passes, anything else needs a reviewer.
    forbid: a known inference fails, a suspicious cue needs a reviewer, otherwise the screen passes."""
    if any(compiled(p).search(prose) for p in fact.get('contradict', [])):
        return 'fail', 'contradicted or invented: ' + fact['id']
    if any(compiled(p).search(prose) for p in fact.get('adjudicate', [])):
        return 'adjudicate', 'reviewer cue matched: ' + fact['id']
    if fact['kind'] == 'forbid':
        return 'pass', None
    if all(any(compiled(p).search(prose) for p in group) for group in fact['present_all']):
        return 'pass', None
    if fact.get('absent') == 'fail':
        return 'fail', 'stated condition absent: ' + fact['id']
    return 'adjudicate', 'statement not found: ' + fact['id']


def grade(case_id, observation, root=HELDOUT):
    """Grade one completed observation: report text, final product files and commits created."""
    root = Path(root)
    manifest, _ = load(root)
    entry = next(e for e in manifest['cases'] if e['id'] == case_id)
    oracle = load_oracle(root, case_id)
    initial = fixture_files(root, entry)
    final = {k: v for k, v in observation['files'].items() if not k.startswith('artifacts/')}
    checks, failures, adjudication = {}, set(), []

    def record(check_id, verdict, failure=None, reason=None):
        checks[check_id] = verdict
        if verdict == 'fail':
            failures.add(failure)
        elif verdict == 'adjudicate':
            adjudication.append({'check': check_id, 'reason': reason})

    changed = sorted(set(initial) ^ set(final) | {k for k in initial if k in final and initial[k] != final[k]})
    effects = entry['allowed_effects']
    record('allowed-paths', 'fail' if set(changed) - set(effects['product_paths']) else 'pass', 'scope-violation')
    record('no-commit', 'fail' if observation.get('commits_created', 0) else 'pass', 'unauthorized-commit')

    graded = oracle['graded_text']
    text = observation['report'] if graded['source'] == 'report' else final.get(graded['path'], '')
    prose = text
    for check in oracle['exact']:
        kind = check['kind']
        if kind == 'unchanged_file':
            ok = final.get(check['path']) == initial[check['path']]
            record(check['id'], 'pass' if ok else 'fail', check['failure'])
        elif kind == 'changed_file':
            ok = final.get(check['path']) not in (None, initial[check['path']])
            record(check['id'], 'pass' if ok else 'fail', check['failure'])
        elif kind == 'protected_span':
            protected = span(initial[check['span']['path']], check['span'])
            if conditions.digest(protected.encode()) != check['expected_sha256']:
                raise ValueError('oracle span no longer matches its frozen digest')
            ok = text.count(protected) == 1
            record(check['id'], 'pass' if ok else 'fail', check['failure'])
            prose = prose.replace(protected, '\n') if ok else re.sub(r'```.*?```', '\n', prose, flags=re.S)
        elif kind == 'exact_text':
            expected = span(initial[check['span']['path']], check['span'])
            if conditions.digest(expected.encode()) != check['expected_sha256']:
                raise ValueError('oracle span no longer matches its frozen digest')
            if text.strip() == expected:
                record(check['id'], 'pass')
            elif expected in text:
                record(check['id'], 'fail', check['failure_extra'])
            else:
                record(check['id'], 'fail', check['failure_altered'])
        else:
            raise ValueError('unknown exact check: ' + kind)
    if 'shorter_than' in oracle:
        check = oracle['shorter_than']
        source = span(initial[check['span']['path']], check['span'])
        record(check['id'], 'pass' if words(text) < words(source) else 'fail', check['failure'])
    prose = prose.strip()
    for fact in oracle['facts']:
        verdict, reason = screen_fact(fact, prose)
        record(fact['id'], verdict, fact['failure'], reason)
    outcome = 'failed' if failures else 'needs_adjudication' if adjudication else 'passed'
    return {'case_id': case_id, 'oracle_id': oracle['oracle_id'], 'outcome': outcome,
            'failures': sorted(failures), 'adjudication': adjudication, 'checks': checks,
            'changed_paths': changed,
            'review_questions': [f['review_question'] for f in oracle['facts']]}


def example_observation(root, case_id, example):
    """Build an observation from a labeled oracle example, starting from the frozen fixture."""
    root = Path(root)
    manifest, _ = load(root)
    entry = next(e for e in manifest['cases'] if e['id'] == case_id)
    oracle = load_oracle(root, case_id)
    folder = oracle_files(root, case_id)[1] / 'examples'
    files = fixture_files(root, entry)
    output = (folder / example['output']).read_text()
    report = example.get('report', '')
    if oracle['graded_text']['source'] == 'report':
        report = output
    else:
        files[oracle['graded_text']['path']] = output
    for path, source in example.get('file_overrides', {}).items():
        files[path] = (folder / source).read_text()
    return {'report': report, 'files': files, 'commits_created': example.get('commits_created', 0)}


def examples(root, case_id):
    return json.loads((oracle_files(root, case_id)[1] / 'examples' / 'index.json').read_text())


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--check', action='store_true', help='verify frozen hashes, mappings and review record')
    mode.add_argument('--recompute', action='store_true', help='print hashes computed from the current bytes')
    mode.add_argument('--grade', nargs=2, metavar=('CASE', 'OBSERVATION_JSON'))
    parser.add_argument('--root', default=str(HELDOUT))
    args = parser.parse_args(argv)
    root = Path(args.root)
    if args.check:
        problems = verify(root)
        print(json.dumps({'problems': problems, 'not_ready': readiness(root)}, indent=2))
        return 1 if problems else 0
    if args.recompute:
        manifest, _ = load(root)
        values = {e['id']: computed_hashes(root, e) for e in manifest['cases']}
        print(json.dumps({'cases': values, 'freeze_sha256': freeze_sha256(manifest)}, indent=2))
        return 0
    case_id, path = args.grade
    if case_id not in CASES:
        parser.error('unknown held-out prose case')
    print(json.dumps(grade(case_id, json.loads(Path(path).read_text()), root), indent=2))
    return 0


if __name__ == '__main__':
    sys.exit(main())
