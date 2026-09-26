#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
python3 - <<'PY'
import copy, json, os, pathlib, re, shutil, subprocess, tempfile

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

    performance = json.loads(run('orient', '--category', 'performance-delivery', cwd=backend))
    assert performance['recommended_lenses'] == ['performance', 'delivery']
    assert 'performance-delivery' not in profile['categories']
    assert 'performance-delivery' in json.loads(run('orient', '--category', 'all', cwd=backend))['categories']
    surfaces = performance['performance_delivery_surfaces']
    assert surfaces['execution_paths']['status'] == 'heuristic'
    assert 'api/main.py' in surfaces['execution_paths']['files']
    assert surfaces['build_boundaries']['files'] == ['pyproject.toml']
    assert surfaces['ci_configuration']['status'] == 'not-discovered'
    assert surfaces['external_deployment']['status'] == 'unavailable'

    delivery_only = tmp / 'delivery-only'
    write(delivery_only, '.gitlab-ci.yml', 'release: manual\n')
    init(delivery_only)
    delivery_profile = json.loads(run('orient', '--category', 'performance-delivery', cwd=delivery_only))
    assert delivery_profile['recommended_lenses'] == ['delivery']
    assert delivery_profile['performance_delivery_surfaces']['ci_configuration']['files'] == ['.gitlab-ci.yml']
    pd_root = tmp / 'pd-fixture'
    shutil.copytree('evals/ultima/performance-delivery', pd_root)
    init(pd_root)
    narrowed_pd = json.loads(run('orient', '--path', 'api', '--category', 'performance-delivery', cwd=pd_root))
    assert narrowed_pd['recommended_lenses'] == ['performance']
    assert not narrowed_pd['performance_delivery_surfaces']['release_contracts']['files']
    pd_run = tmp / 'pd-run'
    pd_run.mkdir()
    write(pd_run, 'profile.json', json.loads(run('orient', '--category', 'performance-delivery', cwd=pd_root)))
    def quote(file, line, role=None):
        item = dict(file=file, line=line, quote=(pd_root / file).read_text().splitlines()[line - 1])
        return dict(item, role=role) if role else item
    cost = trace('Order export repeats item reads', category='performance-delivery', effort='M',
        impact='medium', reach='package', evidence_status='static', cost_assessment='source-hypothesis',
        problem='Export runs one item query per order; runtime cost has not been measured.',
        scenario='An export with many orders performs one item read per order before writing the response.',
        fix='Batch item reads for the exported order set.', root_cause='per-order item query',
        affected_boundary='order export item reads',
        invariant=(pd_root / 'docs/contracts.md').read_text().splitlines()[2], invariant_source='docs/contracts.md:3',
        flow='export_orders consumes list_orders, which calls db.query once per order.',
        verification='Proposed: with 100 orders assert one batched item query and unchanged export contents.',
        trace=[quote('api/orders.py', 12, 'source'), quote('api/orders.py', 3, 'boundary'), quote('api/orders.py', 12, 'consumer')])
    bad_invariant = dict(cost, title='Unsupported cost contract', root_cause='invented contract', invariant='Invented rule')
    bad_pattern = dict(cost, title='Pattern bypass', root_cause='pattern bypass', evidence_kind='pattern', action='fix',
        instances=[quote('api/orders.py', i) for i in (1, 3, 12)])
    write(pd_run, 'performance.json', dict(lens='performance', candidates=[cost, bad_invariant, bad_pattern],
        coverage=dict(status='complete', files_read=3, notes=['Bounded preview is an accepted tradeoff.'])))
    run('merge', str(pd_run), '--roster', 'performance')
    costs = {c['title']: c for c in json.loads((pd_run / 'merged.json').read_text())['candidates']}
    assert costs[cost['title']]['strength'] == 75
    assert costs[bad_invariant['title']]['strength'] == 50
    assert costs[bad_pattern['title']]['action'] == 'plan'

    measured = dict(cost, title='Catalog materialization dominates the supplied profile',
        root_cause='materialize whole catalog', affected_boundary='catalog page',
        fix='Fetch the visible page at the store boundary.', evidence_status='runtime', cost_assessment='measured-bottleneck',
        invariant=(pd_root / 'docs/contracts.md').read_text().splitlines()[4], invariant_source='docs/contracts.md:5',
        flow='catalog_page materializes all products and filters them before slicing for render.',
        runtime_evidence='results/catalog-profile.txt:6 records a supplied synthetic executed profile.',
        measurement=dict(quote('results/catalog-profile.txt', 6), command='python bench_catalog.py --rows 100000 --page-size 20',
            revision='fixture-catalog-v1', environment='isolated local synthetic store', workload='100000 products, first page of 20',
            result='100000 records materialized; 82% sampled request CPU attributed to materialization/filtering',
            attribution='catalog_page all_products and public filtering; no production inference'),
        trace=[quote('api/catalog.py', 1, 'source'), quote('api/catalog.py', 2, 'boundary'), quote('api/catalog.py', 4, 'consumer')])
    missing_measurement = dict(measured, title='Unsupported measurement', root_cause='unattributed measurement', measurement={})
    invented_measurement = dict(measured, title='Invented result', root_cause='invented result',
        measurement=dict(measured['measurement'], quote='invented profiler result'))
    missing_flow = dict(cost, title='Unconnected cost quotes', root_cause='missing flow', flow='')
    write(pd_run, 'performance.json', dict(lens='performance', candidates=[cost, measured, missing_measurement, invented_measurement, missing_flow],
        coverage=dict(status='complete', files_read=3, notes=['Bounded preview is an accepted tradeoff.'])))
    overlap = dict(cost, category='architecture', title='Architecture view of batched reads', cost_assessment='')
    distinct_cost = dict(cost, category='data-reliability', title='Different cause at the same source', root_cause='separate cause')
    write(pd_run, 'system-architecture.json', dict(lens='system-architecture', candidates=[overlap], coverage={'status':'complete'}))
    write(pd_run, 'data-integrity.json', dict(lens='data-integrity', candidates=[distinct_cost], coverage={'status':'complete'}))
    write(pd_run, 'delivery.json', dict(lens='delivery', candidates=[],
        coverage=dict(status='complete', absent_scope=['CI configuration'], unavailable_scope=['partner-production deployment'])))
    run('merge', str(pd_run), '--roster', 'system-architecture,performance,data-integrity,delivery')
    pd_merged = json.loads((pd_run / 'merged.json').read_text())
    costs = {c['title']: c for c in pd_merged['candidates']}
    combined = next(c for c in pd_merged['candidates'] if c['root_cause'] == cost['root_cause'])
    assert combined['strength'] == 75 and combined['cost_assessment'] == 'source-hypothesis', combined
    assert set(combined['categories']) == {'architecture', 'performance-delivery'}
    assert pd_merged['counts']['dedup_merged'] == 1
    assert distinct_cost['title'] in costs
    assert costs[measured['title']]['cost_assessment'] == 'measured-bottleneck'
    for invalid_cost in (missing_measurement, invented_measurement, missing_flow):
        assert costs[invalid_cost['title']]['strength'] == 50, costs[invalid_cost['title']]
    for invalid_cost in (missing_measurement, invented_measurement):
        assert costs[invalid_cost['title']]['evidence_status'] == 'static'
        assert costs[invalid_cost['title']]['cost_assessment'] == 'source-hypothesis'
    assert combined['action'] == 'plan'
    pd_ids = {c['title']: c['id'] for c in pd_merged['candidates']}
    write(pd_run, 'reconciled.json', pd_merged)
    run('merge', str(pd_run), '--reconciled', str(pd_run / 'reconciled.json'))
    revised_pd = json.loads((pd_run / 'merged.json').read_text())
    assert {c['title']: c['id'] for c in revised_pd['candidates']} == pd_ids
    combined2 = next(c for c in revised_pd['candidates'] if c['id'] == combined['id'])
    assert combined2['strength'] == 75 and combined2['cost_assessment'] == 'source-hypothesis'
    run('render', str(pd_run))
    pd_html = (pd_run / 'report.html').read_text()
    assert 'id="cat-performance-delivery"' in pd_html
    assert 'Performance &amp; Delivery' in pd_html
    assert '<dt>Performance &amp; Delivery</dt><dd class="">partial</dd>' in pd_html
    assert 'absent scope: CI configuration' in pd_html and 'unavailable scope: partner-production deployment' in pd_html
    assert 'source hypothesis' in pd_html and 'measured bottleneck' in pd_html
    assert 'Unverified execution reference' in pd_html
    assert 'Existing measurement attribution' in pd_html and 'Proposed verification / acceptance' in pd_html
    assert '@media print' in pd_html and 'id="f-75"' in pd_html and '<script' not in pd_html.lower()
    for value in pd_ids.values():
        assert f'id="{value}"' in pd_html and f'href="#{value}"' in pd_html

    pd_eval = tmp / 'pd-evaluation'
    pd_eval.mkdir()
    write(pd_eval, 'profile.json', json.loads(run('orient', '--category', 'performance-delivery', cwd=pd_root)))
    for lens in ('performance', 'delivery'):
        artifact = json.loads(pathlib.Path(f'evals/ultima/results/performance-delivery/{lens}.json').read_text())
        for candidate in artifact['candidates']:
            for item in candidate['trace'] + candidate['instances'] + ([candidate['measurement']] if candidate.get('measurement') else []):
                assert item['quote'].strip() in (pd_root / item['file']).read_text().splitlines()[item['line'] - 1], item
        write(pd_eval, lens + '.json', artifact)
    run('merge', str(pd_eval), '--roster', 'performance,delivery')
    evaluated = json.loads((pd_eval / 'merged.json').read_text())
    assert len(evaluated['candidates']) == 3
    assert all(c['strength'] == 100 and c['action'] == 'plan' for c in evaluated['candidates'])
    assert sorted(c['cost_assessment'] for c in evaluated['candidates']) == ['', 'measured-bottleneck', 'source-hypothesis']
    assert all(c['plan_status'] == 'documented' for c in evaluated['candidates'])
    assert any('preview' in note for note in evaluated['coverage']['performance']['notes'])
    assert evaluated['coverage']['delivery']['absent_scope'] and evaluated['coverage']['delivery']['unavailable_scope']
    assert all('preview' not in c['title'].lower() and 'external' not in c['title'].lower() for c in evaluated['candidates'])
    run('render', str(pd_eval))
    assert '<dt>Performance &amp; Delivery</dt><dd class="">partial</dd>' in (pd_eval / 'report.html').read_text()

    security = tmp / 'security'
    write(security, 'api/routes.py', 'def read_invoice(request):\n    return load_invoice(request.invoice_id)\n')
    write(security, 'api/store.py', 'def load_invoice(invoice_id):\n    return invoices[invoice_id]\n')
    write(security, 'api/middleware.py', 'def authenticate(request):\n    return verify_session(request.session)\n')
    write(security, 'docs/security.md', 'Only the owning tenant may read an invoice.\n')
    init(security)
    security_profile = json.loads(run('orient', '--category', 'security', cwd=security))
    assert 'access-control' in security_profile['recommended_lenses']
    assert security_profile['category_applicability']['security']
    assert security_profile['security_surfaces']['authentication']['files'] == ['api/middleware.py']
    assert security_profile['security_surfaces']['external_controls']['status'] == 'unavailable'
    assert 'security' not in profile['categories'], 'default scope must remain compatible'
    assert 'access-control' not in arch['recommended_lenses']
    assert 'security' in json.loads(run('orient', '--category', 'all', cwd=security))['categories']

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

    assert '<dt>Security</dt><dd class="">not examined</dd>' in html

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
        assert '<dt>Architecture</dt><dd class="">' + expected + '</dd>' in focused_html, coverage
        assert '<dt>UX &amp; accessibility</dt><dd class="">not examined</dd>' in focused_html
        assert '<dt>Data &amp; reliability</dt><dd class="">not examined</dd>' in focused_html
        assert 'category-status' not in focused_html
        assert 'Specialists completed:' not in focused_html
        assert '<p class="lede">' not in focused_html
        assert focused_html.index('<h2>Coverage</h2>') < focused_html.index('<dt>Architecture</dt>')

    security_run = tmp / 'security-run'
    security_run.mkdir()
    write(security_run, 'profile.json', security_profile)
    finding = trace('Invoice lookup omits the tenant boundary', category='security', effort='S', action='fix',
        root_cause='unscoped invoice lookup', affected_boundary='invoice reader', evidence_status='static',
        invariant='Only the owning tenant may read an invoice.', invariant_source='docs/security.md:1',
        scenario='If a caller supplies another tenant invoice ID, this path selects that invoice; deployment exposure is unknown.',
        flow='read_invoice passes request.invoice_id to load_invoice, which indexes invoices without a tenant constraint.',
        assessment='demonstrated',
        control_review=[dict(file='api/middleware.py', line=2, quote='return verify_session(request.session)')],
        trace=[dict(file='api/routes.py', line=1, role='source', quote='def read_invoice(request):'),
               dict(file='api/routes.py', line=2, role='boundary', quote='return load_invoice(request.invoice_id)'),
               dict(file='api/store.py', line=2, role='consumer', quote='return invoices[invoice_id]')])
    cases = [finding,
        dict(finding, title='Missing enclosing control review', root_cause='missing control review', control_review=[]),
        dict(finding, title='Unrelated quote', root_cause='fabricated quote', trace=[dict(x, quote='invented()') for x in finding['trace']]),
        dict(finding, title='Missing flow', root_cause='disconnected trace', flow=''),
        dict(finding, title='No trace allowed as a pattern', root_cause='pattern bypass', evidence_kind='pattern'),
        dict(finding, title='Runtime without proof', root_cause='runtime overclaim', evidence_status='runtime'),
        dict(finding, title='Unknown external policy', root_cause='external assumption', assessment='inferred', strength=100)]
    write(security_run, 'access-control.json', dict(lens='access-control', candidates=cases,
        coverage=dict(status='partial', files_read=4, dirs_skipped=[], notes=['External policy unavailable.'],
                      unavailable_controls=['gateway policy']), residual_risks=[]))
    overlap = dict(finding, title='Separate architecture ownership issue', category='architecture',
                   root_cause='duplicated ownership', control_review=[])
    write(security_run, 'system-architecture.json', dict(lens='system-architecture', candidates=[overlap], coverage={'status':'complete'}))
    run('merge', str(security_run), '--roster', 'access-control,input-boundaries,system-architecture')
    security_merged = json.loads((security_run / 'merged.json').read_text())
    security_by_title = {c['title']: c for c in security_merged['candidates']}
    assert security_by_title[finding['title']]['strength'] == 75
    assert security_by_title[finding['title']]['action'] == 'plan'
    assert security_by_title[finding['title']]['evidence_status'] == 'static'
    for case in cases[1:]:
        assert security_by_title[case['title']]['strength'] == 50, security_by_title[case['title']]
    assert overlap['title'] in security_by_title
    run('render', str(security_run))
    security_html = (security_run / 'report.html').read_text()
    assert 'id="cat-security"' in security_html and 'Security <span>(7)</span>' in security_html
    assert '<dt>Security</dt><dd class="">partial</dd>' in security_html
    stable = security_by_title[finding['title']]['id']
    assert f'id="{stable}"' in security_html and f'href="#{stable}"' in security_html
    write(security_run, 'reconciled.json', security_merged)
    run('merge', str(security_run), '--reconciled', str(security_run / 'reconciled.json'))
    assert {c['title']: c['id'] for c in json.loads((security_run / 'merged.json').read_text())['candidates']} == {c['title']: c['id'] for c in security_merged['candidates']}

    write(security, 'api/config.py', "TOKEN = 'synthetic-sensitive-value'\n")
    redacted = dict(finding, title='Redacted source remains locatable',
        trace=[finding['trace'][0], finding['trace'][1],
               dict(file='api/config.py', line=1, role='consumer', quote="TOKEN = '[REDACTED]'")],
        before={'language': 'python', 'code': "TOKEN = '[REDACTED]'"})
    write(security_run, 'access-control.json', dict(lens='access-control', candidates=[redacted],
        coverage={'status':'complete', 'unavailable_controls':['gateway policy']}))
    write(security_run, 'input-boundaries.json', dict(lens='input-boundaries', candidates=[], coverage={'status':'complete'}))
    write(security_run, 'sensitive-data.json', dict(lens='sensitive-data', candidates=[], coverage={'status':'complete'}))
    run('merge', str(security_run), '--roster', 'access-control,input-boundaries,sensitive-data')
    run('render', str(security_run))
    assert json.loads((security_run / 'merged.json').read_text())['candidates'][0]['strength'] == 75
    for output in ('merged.json', 'report.html'):
        text = (security_run / output).read_text()
        assert 'synthetic-sensitive-value' not in text and '[REDACTED]' in text
        assert 'api/config.py' in text
    assert '<dt>Security</dt><dd class="">partial</dd>' in (security_run / 'report.html').read_text()

    eval_root = tmp / 'specialist-fixture'
    shutil.copytree('evals/ultima/security', eval_root)
    init(eval_root)
    eval_run = tmp / 'specialist-replay'
    eval_run.mkdir()
    write(eval_run, 'profile.json', json.loads(run('orient', '--category', 'security', cwd=eval_root)))
    for lens in ('access-control', 'sensitive-data'):
        shutil.copyfile(f'evals/ultima/results/{lens}.json', eval_run / f'{lens}.json')
    run('merge', str(eval_run), '--roster', 'access-control,sensitive-data')
    replay = json.loads((eval_run / 'merged.json').read_text())
    assert len(replay['candidates']) == 2
    assert all(c['strength'] == 100 and c['evidence_status'] == 'static' and c['action'] == 'plan' for c in replay['candidates'])
    assert len({c['root_cause'] for c in replay['candidates']}) == 2
    assert any('scoped /invoice' in note for note in replay['coverage']['access-control']['notes'])
    run('render', str(eval_run))
    for path in eval_run.iterdir():
        assert 'SYNTHETIC-ONLY-SECRET-53' not in path.read_text(), path
    assert '[REDACTED]' in (eval_run / 'report.html').read_text()
    assert '<dt>Security</dt><dd class="">partial</dd>' in (eval_run / 'report.html').read_text()

    documented = trace('Documented migration', remediation=['Add a durable key.', 'Backfill before enforcing uniqueness.'],
                       compatibility='Accept old requests during rollout.', rollback='Disable the new writer before reverting.')
    write(focused, 'returns/system-architecture.json', dict(lens='system-architecture', candidates=[documented], coverage={'status': 'complete'}))
    run('merge', str(focused), '--roster', 'system-architecture')
    documented_result = json.loads((focused / 'merged.json').read_text())['candidates'][0]
    assert documented_result['plan_status'] == 'documented' and documented_result['plan_missing'] == []

print('ultima project fixture tests: ok')
PY
