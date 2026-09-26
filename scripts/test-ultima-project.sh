#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
python3 - <<'PY'
import copy, json, os, pathlib, re, subprocess, tempfile

script = pathlib.Path('skills/ultima/scripts/ultima.sh').resolve()

def run(*args, cwd=None, code=0):
    p = subprocess.run(['bash', str(script), *args], cwd=cwd, text=True, capture_output=True)
    assert p.returncode == code, (args, p.returncode, p.stdout, p.stderr)
    return p.stdout

def write(root, name, value):
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value) if not isinstance(value, str) else value)

def init(repo):
    env = dict(os.environ, GIT_AUTHOR_NAME='t', GIT_AUTHOR_EMAIL='t@example.com',
               GIT_COMMITTER_NAME='t', GIT_COMMITTER_EMAIL='t@example.com')
    for args in [('init', '-q'), ('add', '.'), ('commit', '-qm', 'fixture')]:
        subprocess.run(['git', *args], cwd=repo, env=env, capture_output=True, check=True)

def location(file, line, role):
    return dict(file=file, line=line, quote='write(record)', role=role)

def trace(title, **extra):
    candidate = dict(title=title, problem='A retry can persist the same operation twice.',
                     fix='Enforce one durable idempotency key at the write boundary.', strength=75,
                     effort='L', evidence_kind='trace', category='data-reliability', impact='critical', reach='system',
                     invariant='Each operation is applied once.', invariant_source='docs/adr/0001.md',
                     scenario='A client retries after a write succeeds but the reply is lost.',
                     verification='Traced handler, transaction, and retry caller in source.',
                     trace=[location('api/main.py', 1, 'source'), location('api/store.py', 2, 'boundary'),
                            location('worker/main.py', 3, 'consumer')],
                     root_cause='unkeyed retry', affected_boundary='operation persistence')
    candidate.update(extra)
    return candidate

with tempfile.TemporaryDirectory(prefix='ultima-project-') as tmp:
    tmp = pathlib.Path(tmp)
    backend = tmp / 'backend'
    write(backend, 'pyproject.toml', '[project]\nname = "service"\nversion = "0.1.0"\n')
    write(backend, 'api/main.py', 'from api.store import write\nwrite({})\n')
    write(backend, 'api/store.py', 'def write(record):\n    pass\n')
    write(backend, 'worker/main.py', 'from api.store import write\nwrite({})\n')
    write(backend, 'migrations/001.sql', 'CREATE TABLE operations (id TEXT);\n')
    write(backend, 'Dockerfile', 'FROM python:3.12\n')
    init(backend)
    profile = json.loads(run('orient', cwd=backend))
    assert profile['scope']['path'] == '.'
    assert 'system-architecture' in profile['recommended_lenses']
    assert {'data-integrity', 'failure-recovery'} <= set(profile['recommended_lenses'])
    assert 'design-system' not in profile['recommended_lenses']
    for key in ('components', 'manifests', 'dependency_edges', 'entrypoints', 'data_files', 'deployment_files'):
        assert key in profile['system_map'], (key, profile['system_map'])
    assert 'coverage' in profile['system_map']
    run('orient', '--category', 'ux', cwd=backend, code=2)
    arch = json.loads(run('orient', '--category', 'architecture', cwd=backend))
    assert arch['recommended_lenses'] == ['system-architecture'], arch['recommended_lenses']
    run('orient', '--category', 'nonsense', cwd=backend, code=1)

    mono = tmp / 'mono'
    write(mono, 'package.json', {'name': 'root', 'private': True, 'workspaces': ['apps/*', 'packages/*']})
    write(mono, 'apps/web/package.json', {'name': '@app/web', 'dependencies': {'react': '^18', '@app/shared': 'workspace:*'}})
    write(mono, 'apps/web/src/Button.tsx', 'export const Button = () => <button>ok</button>\n')
    write(mono, 'apps/api/package.json', {'name': '@app/api', 'dependencies': {'@app/shared': 'workspace:*'}})
    write(mono, 'apps/api/src/index.ts', 'import {save} from "@app/shared";\nsave();\n')
    write(mono, 'packages/shared/package.json', {'name': '@app/shared'})
    write(mono, 'packages/shared/index.ts', 'export const save = () => {};\n')
    init(mono)
    whole = json.loads(run('orient', cwd=mono))
    assert whole['scope']['path'] == '.', whole['scope']
    assert {'system-architecture', 'data-integrity', 'failure-recovery', 'design-system'} <= set(whole['recommended_lenses'])
    assert whole['system_map']['dependency_edges'], whole['system_map']
    selected = json.loads(run('orient', '--category', 'ux,architecture', cwd=mono))
    assert 'system-architecture' in selected['recommended_lenses'] and 'data-integrity' not in selected['recommended_lenses']
    narrow = json.loads(run('orient', '--path', 'apps/api', cwd=mono))
    assert narrow['scope']['path'] == 'apps/api'
    assert 'design-system' not in narrow['recommended_lenses'], narrow['recommended_lenses']
    run('orient', '--path', 'apps/api', '--category', 'ux', cwd=mono, code=2)

    result = tmp / 'results'
    result.mkdir()
    write(result, 'profile.json', whole)
    serious = trace('Retry duplicates a committed operation')
    duplicate = trace('Lost response allows duplicate writes')
    distinct = trace('Similar locations with a different cause', root_cause='write skew')
    invalid = trace('Unproved trace', root_cause='unproved', trace=[location('api/main.py', 1, 'source')])
    no_invariant = trace('Trace without invariant source', root_cause='unsourced invariant', invariant_source='')
    one_location = trace('Trace reuses one location', root_cause='one location', trace=[location('api/main.py', 1, role) for role in ('source', 'boundary', 'consumer')])
    accepted = trace('Accepted tradeoff', prior_decision='docs/adr/0001.md')
    revisit = trace('Assumption no longer holds', decision_status='revisit', prior_decision='docs/adr/0001.md',
                    decision_reason='The operation now crosses service boundaries.')
    violated = trace('Implementation violates decision', decision_status='violated', prior_decision='docs/adr/0001.md')
    other_decision = trace('Another decision violated', decision_status='violated', prior_decision='docs/adr/0002.md')
    same_cause_pattern = trace('Pattern with same cause', evidence_kind='pattern', instances=[dict(file=f'api/file{i}.py', line=1, quote='write(record)') for i in range(3)])
    write(result, 'data-integrity.json', dict(lens='data-integrity', candidates=[serious, distinct, invalid, no_invariant, one_location, accepted, revisit, violated, other_decision, same_cause_pattern],
                                           coverage={'files_read': 3, 'skipped': []}, residual_risks=[]))
    write(result, 'failure-recovery.json', dict(lens='failure-recovery', candidates=[duplicate], coverage={'files_read': 3, 'skipped': []}))
    ux = dict(title='Repeated spacing', problem='Spacing departs from the documented scale.', fix='Use --space-4.',
              strength=100, effort='S', impact='low', reach='local', convention_source='tokens.css:2',
              instances=[dict(file=f'components/C{i}.tsx', line=1, quote='padding: 17') for i in range(30)],
              before={'language': 'html', 'code': '<script>alert(1)</script>'})
    write(result, 'design-system.json', dict(lens='design-system', candidates=[ux], coverage={'files_read': 30, 'skipped': []}))
    write(result, 'system-architecture.json', '{broken json')
    run('merge', str(result), '--roster', 'design-system,data-integrity,failure-recovery,system-architecture,accessibility')
    merged = json.loads((result / 'merged.json').read_text())
    by_title = {c['title']: c for c in merged['candidates']}
    assert 'Accepted tradeoff' not in by_title
    assert any(c['title'] == 'Accepted tradeoff' for c in merged['dismissed'])
    assert by_title[serious['title']]['strength'] == 75, 'agent agreement must not promote confidence'
    assert by_title[serious['title']]['rank'] < by_title[ux['title']]['rank'], 'critical trace must outrank repetitive cosmetic evidence'
    assert by_title[serious['title']]['action'] == 'plan'
    assert by_title[serious['title']]['plan_status'] == 'incomplete'
    assert set(by_title[serious['title']]['plan_missing']) == {'remediation', 'compatibility', 'rollback'}
    for candidate in (invalid, no_invariant, one_location):
        assert by_title[candidate['title']]['strength'] == 50, by_title[candidate['title']]
    assert by_title[revisit['title']]['action'] == 'decision-needed'
    assert violated['title'] in by_title and distinct['title'] in by_title
    assert other_decision['title'] in by_title and same_cause_pattern['title'] in by_title
    assert duplicate['title'] not in by_title
    assert merged['counts']['dedup_merged'] == 1, merged['counts']
    assert 'accessibility' in merged['counts']['lenses_missing']
    statuses = {lens['name']: lens['status'] for lens in merged['lenses']}
    assert statuses['system-architecture'] != 'ok', statuses
    ids = {c['title']: c['id'] for c in merged['candidates']}
    assert len(set(ids.values())) == len(ids) and all(re.fullmatch(r'F-[A-Za-z0-9]+', value) for value in ids.values()), ids
    rec = copy.deepcopy(merged)
    for c in rec['candidates']:
        if c['title'] == serious['title']:
            c['category'] = 'architecture'
    write(result, 'reconciled.json', rec)
    run('merge', str(result), '--reconciled', str(result / 'reconciled.json'))
    revised = json.loads((result / 'merged.json').read_text())
    assert {c['title']: c['id'] for c in revised['candidates']} == ids
    run('render', str(result))
    html = (result / 'report.html').read_text()
    assert '<script' not in html.lower() and '&lt;script&gt;alert(1)&lt;/script&gt;' in html
    for label in ('Overview', 'UX &amp; accessibility', 'Architecture', 'Data &amp; reliability'):
        assert label in html, label
    assert 'type="radio"' in html
    assert 'Planning needed' in html and 'further planning' in html
    assert 'partial' in html.lower(), 'incomplete agent coverage must be visible'
    for value in ids.values():
        assert f'id="{value}"' in html and f'href="#{value}"' in html, value

    focused = tmp / 'focused'
    focused.mkdir()
    write(focused, 'profile.json', arch)
    # Broken direct artifacts must hydrate a usable return rather than losing evidence.
    write(focused, 'system-architecture.json', '{broken json')
    for coverage, expected in [
        ({'files_read': 3, 'skipped': []}, 'partial'),
        ({'status': 'complete', 'files_read': 3, 'skipped': []}, 'complete'),
        ({'status': 'complete', 'files_read': 3, 'dirs_skipped': ['.git', 'node_modules']}, 'complete'),
        ({'status': 'complete', 'files_read': 3, 'skipped': ['legacy/']}, 'partial'),
        ({'status': 'complete', 'files_read': 3, 'dirs_skipped': ['legacy/']}, 'partial'),
        ({'status': 'partial', 'files_read': 3, 'skipped': []}, 'partial'),
    ]:
        write(focused, 'returns/system-architecture.json', dict(lens='system-architecture', candidates=[], coverage=coverage))
        run('merge', str(focused), '--roster', 'system-architecture')
        hydrated = json.loads((focused / 'merged.json').read_text())
        assert hydrated['lenses'][0]['hydration'] == 'return'
        assert hydrated['lenses'][0]['status'] == 'ok'
        run('render', str(focused))
        focused_html = (focused / 'report.html').read_text()
        assert '<strong>Architecture:</strong> ' + expected + ' coverage.' in focused_html, coverage
        assert '<strong>UX &amp; accessibility:</strong> not examined coverage.' in focused_html
        assert '<strong>Data &amp; reliability:</strong> not examined coverage.' in focused_html

    documented = trace('Documented migration', remediation=['Add a durable key.', 'Backfill before enforcing uniqueness.'],
                       compatibility='Accept old requests during rollout.', rollback='Disable the new writer before reverting.')
    write(focused, 'returns/system-architecture.json', dict(lens='system-architecture', candidates=[documented], coverage={'status': 'complete'}))
    run('merge', str(focused), '--roster', 'system-architecture')
    documented_result = json.loads((focused / 'merged.json').read_text())['candidates'][0]
    assert documented_result['plan_status'] == 'documented' and documented_result['plan_missing'] == []

print('ultima project fixture tests: ok')
PY
