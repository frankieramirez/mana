#!/usr/bin/env python3
"""Independent confirmation cases for the first prose instruction ablation.

Candidate-visible requests and raw sources sit apart from evaluator-only oracles.
The lock freezes source, request, payload, oracle and schedule hashes, the screen
grades a saved output offline, and the readiness gates keep a confirmation run
from starting before the second review. Nothing here invokes a model."""
import argparse
import json
from pathlib import Path
import re
import sys

import conditions
import prose_ablation as pa
import run

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
CASE_SET = HERE / 'prose-confirmation'
STUDY = 'prose-fidelity-confirmation-1'
SEED = 20261017
REPETITIONS = 2
TIMEOUT_SECONDS = 180
PARENT_SLOTS = 36
# The six source groups docs/specs/instruction-ablations.md names, one confirmation group each.
GROUP_KINDS = ('absent-cause', 'adjacent-code-config', 'non-exhaustive-list', 'conditional-quantity',
               'supported-explanation', 'interpretation-verbatim')
UNPINNED_MODEL = 'unpinned-until-execution-freeze'
VERDICTS = ('screen_fail', 'needs_adjudication', 'screen_pass')
SENTENCE = r'[^.!?\n]*?'
SHINGLE_WORDS = 8
# Development material. A confirmation input may share no run of SHINGLE_WORDS words with any of it.
DEVELOPMENT_CORPORA = ('evals/0*-*/prompt.md', 'evals/semantic/cases.jsonl', 'evals/semantic/questions.json',
                       'evals/semantic/findings.md', 'evals/workflows/cases.json', 'evals/workflows/heldout/**/*',
                       'evals/workflows/heldout-prose.md', 'evals/workflows/test_prose_ablation.py',
                       'evals/workflows/prose-ablation/payloads/current-fidelity/SKILL.md',
                       'docs/specs/debugging-procedure.md', 'docs/plans/comment-cleanup-contract.md', 'CHANGELOG.md')
CASE_FIELDS = ('id', 'source_group', 'split', 'request', 'inputs', 'protected_spans', 'timeout_seconds')
ORACLE_FIELDS = ('schema_version', 'group', 'case_id', 'group_kind', 'evaluator_only', 'canary', 'contract',
                 'source_statements', 'legitimate_alternatives', 'checks', 'examples')
EXAMPLE_FIELDS = ('id', 'label', 'polished', 'text', 'screen', 'failures', 'note')


def read_json(path):
    return json.loads(Path(path).read_bytes().decode('utf-8'))


# Candidate-visible cases ------------------------------------------------------

def load_cases(case_set=CASE_SET):
    """The case collection plus each case's raw source files read byte for byte."""
    case_set = Path(case_set)
    data = read_json(case_set / 'cases.json')
    conditions.keys(data, ('version', 'study', 'reasoning', 'seed', 'repetitions', 'cases'), 'confirmation cases')
    if (data['version'] != 1 or data['study'] != STUDY or data['reasoning'] != 'medium'
            or data['seed'] != SEED or data['repetitions'] != REPETITIONS):
        raise ValueError('confirmation cases must keep the decision study, seed and repetitions')
    cases = []
    for item in data['cases']:
        conditions.keys(item, CASE_FIELDS, 'confirmation case')
        if item['timeout_seconds'] != TIMEOUT_SECONDS:
            raise ValueError('confirmation timeout must be 180 seconds: ' + str(item['id']))
        if item['inputs'] != 'inputs/' + str(item['id']):
            raise ValueError('case inputs must live at inputs/<id>: ' + str(item['id']))
        root = case_set / item['inputs']
        files = conditions.inventory(root)
        sources = {name: (root / name).read_bytes().decode('utf-8') for name in files}
        cases.append({**item, 'sources': sources, 'source_inventory': files})
    return data, cases


def render_manifest(case_set=CASE_SET, model=UNPINNED_MODEL, host=run.SUPPORTED_HOST, payload_set=pa.PAYLOAD_SET):
    """A prose_ablation study manifest; expected judgments never enter it."""
    data, cases = load_cases(case_set)
    payload_set = Path(payload_set).resolve()
    _, set_digest = pa.load_payload_set(payload_set)
    return {'version': 1, 'study': data['study'], 'host': host, 'model': model, 'reasoning': data['reasoning'],
            'seed': data['seed'], 'repetitions': data['repetitions'], 'payload_set': str(payload_set),
            'payload_set_sha256': set_digest,
            'cases': [{'id': c['id'], 'source_group': c['source_group'], 'split': c['split'],
                       'request': c['request'], 'sources': c['sources'], 'protected_spans': c['protected_spans'],
                       'timeout_seconds': c['timeout_seconds']} for c in cases]}


# Evaluator-only oracles --------------------------------------------------------

def compiled(pattern):
    return re.compile(pattern.replace('{S}', SENTENCE), re.IGNORECASE)


def checked_oracle(oracle, case):
    conditions.keys(oracle, ORACLE_FIELDS, 'oracle')
    if (oracle['schema_version'] != 1 or oracle['evaluator_only'] is not True
            or oracle['group'] != case['source_group'] or oracle['case_id'] != case['id']
            or oracle['group_kind'] not in GROUP_KINDS):
        raise ValueError('oracle does not belong to its case: ' + case['id'])
    if not isinstance(oracle['canary'], str) or not oracle['canary'].startswith('mana-confirmation-canary-'):
        raise ValueError('oracle needs a canary: ' + case['id'])
    for name in ('source_statements', 'legitimate_alternatives'):
        if not isinstance(oracle[name], list) or not oracle[name] or not all(isinstance(s, str) and s for s in oracle[name]):
            raise ValueError('oracle needs ' + name + ': ' + case['id'])
    ids = set()
    for check in oracle['checks']:
        allowed = {'id', 'kind', 'failure', 'review_question', 'present_all', 'contradict', 'adjudicate', 'absent'}
        if not isinstance(check, dict) or set(check) - allowed or not {'id', 'kind', 'failure', 'review_question'} <= set(check):
            raise ValueError('invalid oracle check fields: ' + case['id'])
        if check['id'] in ids or check['kind'] not in ('preserve', 'forbid'):
            raise ValueError('invalid oracle check: ' + str(check['id']))
        if check['kind'] == 'preserve' and not check.get('present_all'):
            raise ValueError('a preserve check names what must stay: ' + check['id'])
        if check['kind'] == 'forbid' and (not check.get('contradict') or 'present_all' in check):
            raise ValueError('a forbid check names what must not appear: ' + check['id'])
        if check.get('absent', 'adjudicate') not in ('fail', 'adjudicate'):
            raise ValueError('absent must be fail or adjudicate: ' + check['id'])
        for key in ('present_all', 'contradict', 'adjudicate'):
            for pattern in check.get(key, []):
                compiled(pattern)
        ids.add(check['id'])
    kinds = {c['kind'] for c in oracle['checks']}
    if kinds != {'preserve', 'forbid'}:
        raise ValueError('each group needs retained statements and failure opportunities: ' + case['id'])
    examples = oracle['examples']
    for example in examples:
        conditions.keys(example, EXAMPLE_FIELDS, 'oracle example')
        if example['label'] not in ('valid', 'failing') or example['screen'] not in VERDICTS:
            raise ValueError('invalid example label: ' + example['id'])
        if example['label'] == 'valid' and (example['screen'] == 'screen_fail' or example['failures']):
            raise ValueError('a valid example may never screen as a failure: ' + example['id'])
        if example['label'] == 'failing' and example['screen'] == 'screen_pass':
            raise ValueError('a failing example may never screen as a pass: ' + example['id'])
    valid = [e for e in examples if e['label'] == 'valid']
    failing = [e for e in examples if e['label'] == 'failing']
    if len(valid) < 2 or len(failing) < 3:
        raise ValueError('each group needs two legitimate alternatives and three failing outputs: ' + case['id'])
    if not any(e['polished'] and e['screen'] == 'screen_fail' and e['failures'] != ['protected-span-lost']
               for e in failing):
        raise ValueError('each group needs a polished output that still fails on fidelity: ' + case['id'])
    return oracle


def screen(oracle, case, output):
    """Advisory fidelity screen. Exact spans are conclusive; reviewers settle every other check.

    Style is never scored, so no wording quality can offset a failed check."""
    failures, unconfirmed, cues, exact = [], [], [], {}
    prose = output
    for span in case['protected_spans']:
        exact[span['id']] = span['text'] in output
        if not exact[span['id']]:
            failures.append('protected-span-lost')
        prose = prose.replace(span['text'], '\n')
    for check in oracle['checks']:
        if any(compiled(p).search(prose) for p in check.get('contradict', [])):
            failures.append(check['failure'])
            continue
        if check['kind'] == 'preserve' and not all(compiled(p).search(prose) for p in check['present_all']):
            if check.get('absent', 'adjudicate') == 'fail':
                failures.append(check['failure'])
            else:
                unconfirmed.append(check['id'])
        if any(compiled(p).search(prose) for p in check.get('adjudicate', [])):
            cues.append(check['id'])
    verdict = 'screen_fail' if failures else 'needs_adjudication' if unconfirmed or cues else 'screen_pass'
    return {'verdict': verdict, 'failures': sorted(set(failures)), 'exact_spans': exact,
            'unconfirmed': sorted(set(unconfirmed)), 'cues': sorted(set(cues)), 'style_scored': False}


def stylize(text, spans=()):
    """Register edits that change no fact: filler, an opener and a dash outside protected spans."""
    protected = [s['text'] for s in spans]
    marker = '\x00{}\x00'
    for index, span in enumerate(protected):
        text = text.replace(span, marker.format(index))
    text = 'Honestly, just to be super clear here: ' + text.replace(', ', ' — ', 1)
    text += '\n\nHope this helps, it is truly a game changer!!'
    for index, span in enumerate(protected):
        text = text.replace(marker.format(index), span)
    return text


def grade_examples(oracle, case):
    problems = []
    for example in oracle['examples']:
        for variant, text in (('as written', example['text']), ('restyled', stylize(example['text'], case['protected_spans']))):
            got = screen(oracle, case, text)
            if got['verdict'] != example['screen'] or got['failures'] != sorted(example['failures']):
                problems.append(f"{case['id']}/{example['id']} {variant}: expected {example['screen']} "
                                f"{sorted(example['failures'])}, got {got['verdict']} {got['failures']}")
    return problems


def load_oracles(case_set, cases):
    oracles = {}
    for case in cases:
        path = Path(case_set) / 'oracles' / (case['source_group'] + '.json')
        oracles[case['id']] = checked_oracle(read_json(path), case)
    return oracles


# Independence -------------------------------------------------------------------

def shingles(text):
    words = re.findall(r'[a-z0-9]+', text.lower())
    return {' '.join(words[i:i + SHINGLE_WORDS]) for i in range(len(words) - SHINGLE_WORDS + 1)}


def development_overlap(cases, root=ROOT, corpora=DEVELOPMENT_CORPORA):
    """Runs of SHINGLE_WORDS words a confirmation input shares with development material."""
    corpus = {}
    for pattern in corpora:
        for path in sorted(Path(root).glob(pattern)):
            if not path.is_file():
                continue
            try:
                text = path.read_bytes().decode('utf-8')
            except UnicodeDecodeError:
                continue
            for item in shingles(text):
                corpus.setdefault(item, path.relative_to(root).as_posix())
    hits = {}
    for case in cases:
        for name, text in [('request', case['request'])] + sorted(case['sources'].items()):
            shared = sorted(s for s in shingles(text) if s in corpus)
            if shared:
                hits[case['id'] + ':' + name] = [{'words': s, 'development_file': corpus[s]} for s in shared]
    return hits


def leaked_canaries(case_set, cases, oracles):
    """Oracle text that appears in anything a candidate could receive."""
    visible = [(Path(case_set) / 'cases.json').read_bytes().decode('utf-8')]
    for case in cases:
        visible += [case['request']] + list(case['sources'].values())
    leaks = []
    for case_id, oracle in oracles.items():
        if any(oracle['canary'] in text for text in visible):
            leaks.append(case_id)
    return leaks


# Lock -------------------------------------------------------------------------

def compute_lock(case_set=CASE_SET, payload_set=pa.PAYLOAD_SET):
    case_set = Path(case_set)
    data, cases = load_cases(case_set)
    manifest = render_manifest(case_set, payload_set=payload_set)
    selected = pa.checked_study(manifest)
    schedule = pa.build_schedule(selected, data['seed'], data['repetitions'])
    payloads = pa.verify_payload_set(payload_set)
    oracles = load_oracles(case_set, cases)
    exposures_bytes = (case_set / 'exposures.json').read_bytes()
    entries = []
    for case, chosen in zip(cases, selected):
        oracle_path = 'oracles/' + case['source_group'] + '.json'
        entries.append({'id': case['id'], 'source_group': case['source_group'], 'split': case['split'],
                        'group_kind': oracles[case['id']]['group_kind'], 'inputs': case['inputs'],
                        'request_sha256': chosen['request_sha256'], 'source_inventory': case['source_inventory'],
                        'protected_spans': [{k: s[k] for k in ('id', 'file', 'offset', 'sha256')}
                                            for s in chosen['protected_spans']],
                        'timeout_seconds': case['timeout_seconds'], 'oracle': oracle_path,
                        'oracle_sha256': conditions.digest((case_set / oracle_path).read_bytes())})
    lock = {'version': 1, 'study': data['study'], 'experiment': pa.EXPERIMENT,
            'payload_set': 'evals/workflows/prose-ablation', 'payload_set_sha256': manifest['payload_set_sha256'],
            'baseline_revision': payloads['baseline_revision'], 'payload_arms': payloads['arms'],
            'payload_patches': payloads['patches'], 'conditions': list(pa.ARMS),
            'reasoning': data['reasoning'], 'seed': data['seed'], 'repetitions': data['repetitions'],
            'parent_slots': len(schedule),
            'cases_json_sha256': conditions.digest((case_set / 'cases.json').read_bytes()),
            'cases': entries, 'schedule': schedule, 'schedule_sha256': conditions.digest(conditions.encoded(schedule)),
            'exposures_sha256': conditions.digest(exposures_bytes),
            'development_screen': {'shingle_words': SHINGLE_WORDS, 'corpora': list(DEVELOPMENT_CORPORA)}}
    lock['freeze_sha256'] = conditions.digest(conditions.encoded(lock))
    return lock


def checked_exposures(case_set, cases):
    data = read_json(Path(case_set) / 'exposures.json')
    conditions.keys(data, ('version', 'rule', 'exposures'), 'exposure record')
    groups = {c['source_group']: c for c in cases}
    exposed = []
    for item in data['exposures']:
        conditions.keys(item, ('group', 'reader', 'date', 'reason'), 'exposure')
        if item['group'] not in groups or not all(isinstance(item[k], str) and item[k] for k in ('reader', 'date', 'reason')):
            raise ValueError('exposure must name a known group, reader, date and reason')
        if groups[item['group']]['split'] != 'development':
            raise ValueError('exposed group must move to the development split: ' + item['group'])
        exposed.append(item['group'])
    return data, exposed


def checked_review(case_set, freeze_sha256):
    review = read_json(Path(case_set) / 'review.json')
    conditions.keys(review, ('version', 'freeze_sha256', 'author', 'second_review'), 'review record')
    conditions.keys(review['author'], ('agent', 'role', 'session', 'date', 'tuned_candidate',
                                       'edited_candidate_or_payloads'), 'author record')
    second = review['second_review']
    conditions.keys(second, ('status', 'reviewer', 'date', 'freeze_sha256', 'contested_groups', 'notes'),
                    'second review')
    if review['freeze_sha256'] != freeze_sha256:
        raise ValueError('review record names another freeze; refreeze or review again')
    if review['author']['tuned_candidate'] is not False or review['author']['edited_candidate_or_payloads'] is not False:
        raise ValueError('the case author must be independent of the candidate')
    if second['status'] not in ('pending', 'complete'):
        raise ValueError('second review status must be pending or complete')
    if second['status'] == 'complete':
        if (not second['reviewer'] or second['reviewer'] == review['author']['agent'] or not second['date']
                or second['freeze_sha256'] != freeze_sha256):
            raise ValueError('a completed second review needs a different reviewer and this exact freeze')
    elif any(second[k] for k in ('reviewer', 'date', 'freeze_sha256')):
        raise ValueError('a pending second review carries no reviewer, date or freeze')
    return review


def verify(case_set=CASE_SET, payload_set=pa.PAYLOAD_SET, root=ROOT):
    """Recompute the lock and every oracle verdict; report the open readiness gates."""
    case_set = Path(case_set)
    stored = (case_set / 'freeze.json').read_bytes()
    lock = compute_lock(case_set, payload_set)
    if stored != conditions.encoded(lock):
        raise ValueError('freeze.json does not match the current inputs, oracles, payloads or schedule')
    if lock['parent_slots'] != PARENT_SLOTS or len(lock['cases']) != len(GROUP_KINDS):
        raise ValueError('the confirmation study is six groups, three conditions and two repetitions')
    if len({c['source_group'] for c in lock['cases']}) != len(lock['cases']):
        raise ValueError('each source group holds one case')
    data, cases = load_cases(case_set)
    oracles = load_oracles(case_set, cases)
    problems = [p for case in cases for p in grade_examples(oracles[case['id']], case)]
    if problems:
        raise ValueError('oracle examples disagree with their labels:\n' + '\n'.join(problems))
    leaks = leaked_canaries(case_set, cases, oracles)
    if leaks:
        raise ValueError('oracle canary appears in candidate-visible text: ' + ', '.join(leaks))
    overlap = development_overlap(cases, root)
    if overlap:
        raise ValueError('confirmation input reuses development text: ' + json.dumps(overlap, indent=2))
    _, exposed = checked_exposures(case_set, cases)
    review = checked_review(case_set, lock['freeze_sha256'])
    confirmation = {c['group_kind']: c['source_group'] for c in lock['cases']
                    if c['split'] == 'confirmation' and c['source_group'] not in exposed}
    gates = []
    missing = [kind for kind in GROUP_KINDS if kind not in confirmation]
    if exposed or missing:
        gates.append('replace exposed or missing groups before confirmation: ' + ', '.join(missing or exposed))
    if review['second_review']['status'] != 'complete':
        gates.append('second review pending')
    elif review['second_review']['contested_groups']:
        gates.append('replace contested groups: ' + ', '.join(review['second_review']['contested_groups']))
    return {'freeze_sha256': lock['freeze_sha256'], 'payload_set_sha256': lock['payload_set_sha256'],
            'schedule_sha256': lock['schedule_sha256'], 'parent_slots': lock['parent_slots'],
            'groups': {c['source_group']: c['group_kind'] for c in lock['cases']}, 'exposed_groups': exposed,
            'second_review': review['second_review']['status'], 'open_gates': gates,
            'confirmation_ready': not gates, 'agent_executed': False}


def refreeze(case_set=CASE_SET, payload_set=pa.PAYLOAD_SET):
    """Author tool: rewrite the lock; a changed freeze sends the second review back to pending."""
    case_set = Path(case_set)
    lock = compute_lock(case_set, payload_set)
    (case_set / 'freeze.json').write_bytes(conditions.encoded(lock))
    review = read_json(case_set / 'review.json')
    if review['freeze_sha256'] != lock['freeze_sha256']:
        review['freeze_sha256'] = lock['freeze_sha256']
        review['second_review'] = {'status': 'pending', 'reviewer': None, 'date': None, 'freeze_sha256': None,
                                   'contested_groups': [], 'notes': None}
        (case_set / 'review.json').write_bytes(conditions.encoded(review))
    return lock['freeze_sha256']


def check_frozen_study(study_dir, case_set=CASE_SET):
    """Confirm a prose_ablation --freeze-study output carries exactly the locked cases and schedule."""
    study_dir, case_set = Path(study_dir), Path(case_set)
    lock = read_json(case_set / 'freeze.json')
    control_bytes = (study_dir / 'controls.json').read_bytes()
    schedule_bytes = (study_dir / 'schedule.json').read_bytes()
    controls = json.loads(control_bytes)
    for key in ('payload_set_sha256', 'seed', 'repetitions', 'reasoning', 'study', 'schedule_sha256'):
        if controls[key] != lock[key]:
            raise ValueError('frozen study differs from the lock: ' + key)
    if conditions.digest(schedule_bytes) != lock['schedule_sha256']:
        raise ValueError('frozen schedule differs from the lock')
    got = [{'id': c['id'], 'source_group': c['source_group'], 'split': c['split'],
            'request_sha256': c['request_sha256'], 'source_inventory': c['source_inventory'],
            'protected_spans': [{k: s[k] for k in ('id', 'file', 'offset', 'sha256')} for s in c['protected_spans']],
            'timeout_seconds': c['timeout_seconds']} for c in controls['cases']]
    want = [{k: c[k] for k in ('id', 'source_group', 'split', 'request_sha256', 'source_inventory',
                                'protected_spans', 'timeout_seconds')} for c in lock['cases']]
    if got != want:
        raise ValueError('frozen study cases differ from the lock')
    _, cases = load_cases(case_set)
    oracles = load_oracles(case_set, cases)
    visible = control_bytes.decode('utf-8') + schedule_bytes.decode('utf-8')
    for path in sorted((study_dir / 'sources').rglob('*')):
        if path.is_file():
            visible += path.read_bytes().decode('utf-8')
    for oracle in oracles.values():
        if oracle['canary'] in visible or any(e['text'] in visible for e in oracle['examples']):
            raise ValueError('oracle material reached the frozen study: ' + oracle['group'])
    return {'matches_lock': True, 'controls_sha256': conditions.digest(control_bytes),
            'parent_slots': len(json.loads(schedule_bytes)), 'agent_executed': False}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true', help='verify the lock, oracles and gates; no agent')
    parser.add_argument('--refreeze', action='store_true', help='author tool: rewrite freeze.json; no agent')
    parser.add_argument('--manifest', type=Path, help='write a prose_ablation manifest once every gate is closed')
    parser.add_argument('--model', help='requested model for --manifest')
    parser.add_argument('--grade', nargs=2, metavar=('CASE', 'OUTPUT'), help='screen a saved final output')
    parser.add_argument('--check-study', type=Path, help='compare a frozen prose study with the lock')
    args = parser.parse_args(argv)
    try:
        if args.refreeze:
            print(json.dumps({'freeze_sha256': refreeze(), 'agent_executed': False}))
            return 0
        if args.grade:
            _, cases = load_cases()
            case = next((c for c in cases if c['id'] == args.grade[0]), None)
            if case is None:
                raise ValueError('unknown confirmation case: ' + args.grade[0])
            oracle = load_oracles(CASE_SET, [case])[case['id']]
            result = screen(oracle, case, Path(args.grade[1]).read_bytes().decode('utf-8'))
            result['review_questions'] = {c['id']: c['review_question'] for c in oracle['checks']}
            print(json.dumps(result, indent=2))
            return 0
        if args.check_study:
            print(json.dumps(check_frozen_study(args.check_study), indent=2))
            return 0
        report = verify()
        if args.manifest:
            if not report['confirmation_ready']:
                raise ValueError('confirmation gates are open: ' + '; '.join(report['open_gates']))
            if not args.model:
                raise ValueError('--manifest needs --model')
            args.manifest.write_bytes(conditions.encoded(render_manifest(model=args.model)))
        elif not args.check:
            raise ValueError('choose --check, --refreeze, --manifest, --grade or --check-study')
        print(json.dumps(report, indent=2))
        return 0
    except (OSError, ValueError, KeyError) as exc:
        print('prose confirmation: ' + str(exc), file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
