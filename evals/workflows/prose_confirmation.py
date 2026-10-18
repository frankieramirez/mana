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
SENTENCE = r'[^.!?;:\n]*?'
SHINGLE_WORDS = 8
# Development material. A confirmation input may share no run of SHINGLE_WORDS words with any of it.
DEVELOPMENT_CORPORA = ('evals/0*-*/prompt.md', 'evals/semantic/cases.jsonl', 'evals/semantic/questions.json',
                       'evals/semantic/findings.md', 'evals/workflows/cases.json', 'evals/workflows/heldout/**/*',
                       'evals/workflows/heldout-prose.md', 'evals/workflows/test_prose_ablation.py',
                       'evals/workflows/prose-ablation/payloads/current-fidelity/SKILL.md',
                       'docs/specs/debugging-procedure.md', 'docs/plans/comment-cleanup-contract.md', 'CHANGELOG.md')
CASE_FIELDS = ('id', 'source_group', 'split', 'request', 'inputs', 'protected_spans', 'timeout_seconds')
ORACLE_FIELDS = ('schema_version', 'group', 'case_id', 'group_kind', 'evaluator_only', 'canary', 'contract',
                 'source_statements', 'legitimate_alternatives', 'statements', 'checks', 'examples')
# Words that carry no fact on their own. A clause made only of these is skipped.
STOPWORDS = frozenset('''a an the and or but if of to in on at by for from with as is are was were be been being it
    its this that these those they them their there here we our us you your i he she his her has have had do does did
    will would can could may might should must shall which who whom whose what when where how than into onto about up
    out also q'''.split())
# Register words. Style is never scored, so these never make an output pass or fail.
FILLER = frozenset('''honestly basically truly really super actually quite pretty very just simply game changer okay
    ok hey hi hello'''.split())
NEGATIONS = frozenset('''not no never neither nor none nothing nobody without cannot'''.split())
LIST_MARKER = re.compile(r'^[ \t]*(\d+[.)]|[-*\u2022])[ \t]+', re.MULTILINE)
# Words that join two statements without a claim of their own. Causal and sequence words are absent on purpose.
CONNECTOR = re.compile(r',\s*(?:(?:and|but|or|plus|though|while)\s+)?|\s+(?:and|but|or|plus|though|while)\s+')
LEADING_CONNECTOR = re.compile(r'^(?:and|but|or|plus|though)\s+')
# A statement template names its words. A wildcard would let an unstated fact map to the source.
WILDCARD = re.compile(r'(?<!\\)\.|\\[wWSdD]|\[\^|\{S\}')
EXAMPLE_FIELDS = ('id', 'label', 'polished', 'text', 'screen', 'failures', 'note')
REVIEW_FIELDS = ('status', 'reviewer', 'date', 'freeze_sha256', 'contested_groups', 'notes')


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
    if (oracle['schema_version'] != 2 or oracle['evaluator_only'] is not True
            or oracle['group'] != case['source_group'] or oracle['case_id'] != case['id']
            or oracle['group_kind'] not in GROUP_KINDS):
        raise ValueError('oracle does not belong to its case: ' + case['id'])
    if not isinstance(oracle['canary'], str) or not oracle['canary'].startswith('mana-confirmation-canary-'):
        raise ValueError('oracle needs a canary: ' + case['id'])
    for name in ('source_statements', 'legitimate_alternatives'):
        if not isinstance(oracle[name], list) or not oracle[name] or not all(isinstance(s, str) and s for s in oracle[name]):
            raise ValueError('oracle needs ' + name + ': ' + case['id'])
    if not isinstance(oracle['statements'], list) or not oracle['statements']:
        raise ValueError('oracle needs statement templates: ' + case['id'])
    for statement in oracle['statements']:
        conditions.keys(statement, ('id', 'templates'), 'oracle statement')
        if not statement['templates'] or not all(isinstance(t, str) and t for t in statement['templates']):
            raise ValueError('a statement needs templates: ' + str(statement['id']))
        for template in statement['templates']:
            if WILDCARD.search(template) or template != template.lower():
                raise ValueError('a template names lower-case words and holds no wildcard: ' + template)
            re.compile(template)
    ids = set()
    for check in oracle['checks']:
        allowed = {'id', 'kind', 'failure', 'review_question', 'present_all', 'contradict', 'adjudicate'}
        if not isinstance(check, dict) or set(check) - allowed or not {'id', 'kind', 'failure', 'review_question'} <= set(check):
            raise ValueError('invalid oracle check fields: ' + case['id'])
        if check['id'] in ids or check['kind'] not in ('preserve', 'forbid'):
            raise ValueError('invalid oracle check: ' + str(check['id']))
        if check['kind'] == 'preserve' and not check.get('present_all'):
            raise ValueError('a preserve check names what must stay: ' + check['id'])
        if check['kind'] == 'forbid' and ('present_all' in check or not (check.get('contradict') or check.get('adjudicate'))):
            raise ValueError('a forbid check names what must not appear: ' + check['id'])
        for key in ('present_all', 'contradict', 'adjudicate'):
            for pattern in check.get(key, []):
                compiled(pattern)
        ids.add(check['id'])
    kinds = {c['kind'] for c in oracle['checks']}
    if kinds != {'preserve', 'forbid'} or not any(c.get('contradict') for c in oracle['checks']):
        raise ValueError('each group needs retained statements, contradictions and failure opportunities: ' + case['id'])
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
    if len(valid) < 2 or len(failing) < 3 or not any(e['screen'] == 'screen_pass' for e in valid):
        raise ValueError('each group needs two legitimate alternatives, one that passes, and three failing outputs: '
                         + case['id'])
    if not any(e['polished'] and e['screen'] == 'screen_fail' and e['failures'] != ['protected-span-lost']
               for e in failing):
        raise ValueError('each group needs a polished output that still fails on fidelity: ' + case['id'])
    if not any(e['polished'] and e['screen'] == 'needs_adjudication' for e in failing):
        raise ValueError('each group needs a polished invented fact that the screen holds for review: ' + case['id'])
    return oracle


def tokens(text):
    """Lower-case words. A contraction keeps its stem, and n't becomes a separate negation."""
    words = []
    for raw in re.findall(r"[a-z0-9]+(?:'[a-z]+)?", text.lower().replace('’', "'")):
        if raw.endswith("n't"):
            stem = raw[:-3]
            words += [{'ca': 'can', 'wo': 'will', 'sha': 'shall'}.get(stem, stem), 'not']
        else:
            words.append(raw.split("'")[0])
    return [w for w in words if w]


def normalized(clause):
    """One clause in the form templates are written against: lower case, plain apostrophes, no inline code ticks,
    markdown marks or register filler, dashes and brackets as commas, single spaces, no edge punctuation."""
    text = clause.lower().replace('’', "'").replace('‘', "'")
    text = text.replace('`', '').replace('¢', ' cents')
    text = re.sub(r'[()\[\]]', ',', text)
    text = re.sub(r'[*_#>]', '', text)
    text = re.sub(r'\s*[—–]\s*', ', ', text)
    text = re.sub(r'\b(?:' + '|'.join(sorted(FILLER)) + r')\b', ' ', text)
    text = re.sub(r'\s+', ' ', text)
    text = re.sub(r'\s*,[\s,]*', ', ', text)
    text = text.strip(' ,.;:!?')
    return LEADING_CONNECTOR.sub('', text)


def mapped(text, statement):
    """True when the clause is one template or several joined by connectors, every word accounted for."""
    pieces, position = [], 0
    for join in CONNECTOR.finditer(text):
        pieces.append((position, join.start()))
        position = join.end()
    pieces.append((position, len(text)))
    reached = [True] + [False] * len(pieces)
    for first in range(len(pieces)):
        if reached[first]:
            for last in range(first, len(pieces)):
                if not reached[last + 1] and statement.fullmatch(text, pieces[first][0], pieces[last][1]):
                    reached[last + 1] = True
    return reached[-1]


def segments(text):
    """Clauses: no check runs across a sentence end, a semicolon, a colon or a line break outside inline code."""
    codes = re.findall(r'`[^`\n]*`', text)
    masked = re.sub(r'`[^`\n]*`', '\x01', text)
    out = []
    for piece in re.split(r'(?<=[.!?;:])\s+|\n+', masked):
        if piece.strip():
            out.append(re.sub('\x01', lambda _: codes.pop(0), piece))
    return out


def strip_code(text):
    return re.sub(r'`[^`\n]*`', ' ', text)


def negates(segment, match):
    """A negation inside the matched words or among the four words before them scopes over the match."""
    window = tokens(segment[:match.start()])[-4:] + tokens(match.group())
    return any(w in NEGATIONS for w in window)


def screen(oracle, case, output):
    """Advisory fidelity screen.

    screen_fail: a protected span is lost, or a clause contradicts a fact the source states and no negation scopes
    over the contradiction.
    screen_pass: every clause outside the protected spans is one of the oracle's statement templates, or several
    joined by plain connectors, so every factual sentence maps to source content; no cue fires; and every retained
    statement is found outside inline code, so quoting a directive name never stands in for explaining it.
    needs_adjudication: everything else. A clause no template covers (a new number, date, reason, cause, schedule,
    directory, check or actor, or a negation the templates do not state) holds the output for a reviewer, and so
    does a missing statement. Style is never scored."""
    failures, unconfirmed, cues, exact, unmapped = [], set(), set(), {}, []
    prose = output
    for span in case['protected_spans']:
        exact[span['id']] = span['text'] in output
        if not exact[span['id']]:
            failures.append('protected-span-lost')
        prose = prose.replace(span['text'], '\n')
    statement = re.compile('|'.join('(?:' + t + ')' for s in oracle['statements'] for t in s['templates']))
    for segment in segments(LIST_MARKER.sub('', prose)):
        text = normalized(segment)
        if all(w in STOPWORDS for w in tokens(text)):
            continue
        known = mapped(text, statement)
        if not known:
            cues.add('unmapped-clause')
            unmapped.append(segment.strip())
        for check in oracle['checks']:
            for pattern in check.get('contradict', []):
                for match in compiled(pattern).finditer(segment):
                    if not negates(segment, match):
                        failures.append(check['failure'])
                    elif not known:
                        cues.add(check['id'])
    for check in oracle['checks']:
        if any(compiled(p).search(prose) for p in check.get('adjudicate', [])):
            cues.add(check['id'])
    plain = strip_code(prose)
    for check in oracle['checks']:
        if check['kind'] == 'preserve' and not all(compiled(p).search(plain) for p in check['present_all']):
            unconfirmed.add(check['id'])
    verdict = 'screen_fail' if failures else 'needs_adjudication' if unconfirmed or cues else 'screen_pass'
    return {'verdict': verdict, 'failures': sorted(set(failures)), 'exact_spans': exact,
            'unconfirmed': sorted(unconfirmed), 'cues': sorted(cues), 'unmapped_clauses': unmapped,
            'style_scored': False}


def stylize(text, spans=()):
    """Register edits that change no fact: filler, an opener and a dash outside protected spans."""
    protected = [s['text'] for s in spans]
    marker = '\x00{}\x00'
    for index, span in enumerate(protected):
        text = text.replace(span, marker.format(index))
    text = 'Honestly, basically, ' + text.replace(', ', ' — ', 1)
    text += '\n\nTruly a game changer!!'
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
                                f"{sorted(example['failures'])}, got {got['verdict']} {got['failures']} "
                                f"cues={got['cues']} unconfirmed={got['unconfirmed']} unmapped={got['unmapped_clauses']}")
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
            # The screen and lock code itself, so a changed rule needs a refreeze and a new second review.
            'screen_source': 'evals/workflows/prose_confirmation.py',
            'screen_sha256': conditions.digest((HERE / 'prose_confirmation.py').read_bytes()),
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


def checked_second_review(second, author, group_ids, label='second review'):
    conditions.keys(second, REVIEW_FIELDS, label)
    if second['status'] not in ('pending', 'complete'):
        raise ValueError(label + ' status must be pending or complete')
    if not isinstance(second['contested_groups'], list) or set(second['contested_groups']) - set(group_ids):
        raise ValueError(label + ' contests a group that does not exist: '
                         + ', '.join(sorted(set(second['contested_groups']) - set(group_ids))))
    if second['status'] == 'complete' and (not second['reviewer'] or second['reviewer'] == author or not second['date']):
        raise ValueError('a completed ' + label + ' needs a reviewer other than the author and a date')
    return second


def checked_review(case_set, freeze_sha256, group_ids):
    review = read_json(Path(case_set) / 'review.json')
    conditions.keys(review, ('version', 'freeze_sha256', 'author', 'second_review', 'history'), 'review record')
    conditions.keys(review['author'], ('agent', 'role', 'session', 'date', 'tuned_candidate',
                                       'edited_candidate_or_payloads'), 'author record')
    second = checked_second_review(review['second_review'], review['author']['agent'], group_ids)
    if not isinstance(review['history'], list):
        raise ValueError('review history must be a list')
    for index, past in enumerate(review['history']):
        conditions.keys(past, ('review', 'resolution'), 'past review')
        checked_second_review(past['review'], review['author']['agent'], group_ids, f'past review {index + 1}')
        if past['review']['freeze_sha256'] == freeze_sha256:
            raise ValueError('a past review cannot name the current freeze')
    if review['freeze_sha256'] != freeze_sha256:
        raise ValueError('review record names another freeze; refreeze or review again')
    if review['author']['tuned_candidate'] is not False or review['author']['edited_candidate_or_payloads'] is not False:
        raise ValueError('the case author must be independent of the candidate')
    if second['status'] == 'complete':
        if second['freeze_sha256'] != freeze_sha256:
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
    review = checked_review(case_set, lock['freeze_sha256'], [c['source_group'] for c in lock['cases']])
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


def refreeze(case_set=CASE_SET, payload_set=pa.PAYLOAD_SET, resolution=None):
    """Author tool: rewrite the lock. A changed freeze moves a completed review into history and sends the
    second review back to pending."""
    case_set = Path(case_set)
    lock = compute_lock(case_set, payload_set)
    (case_set / 'freeze.json').write_bytes(conditions.encoded(lock))
    review = read_json(case_set / 'review.json')
    if review['freeze_sha256'] != lock['freeze_sha256']:
        if review['second_review']['status'] == 'complete':
            review['history'].append({'review': review['second_review'],
                                      'resolution': resolution or 'superseded by a refreeze'})
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
    parser.add_argument('--resolution', help='with --refreeze: how the superseded completed review was addressed')
    parser.add_argument('--manifest', type=Path, help='write a prose_ablation manifest once every gate is closed')
    parser.add_argument('--model', help='requested model for --manifest')
    parser.add_argument('--grade', nargs=2, metavar=('CASE', 'OUTPUT'), help='screen a saved final output')
    parser.add_argument('--check-study', type=Path, help='compare a frozen prose study with the lock')
    args = parser.parse_args(argv)
    try:
        if args.refreeze:
            print(json.dumps({'freeze_sha256': refreeze(resolution=args.resolution), 'agent_executed': False}))
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
