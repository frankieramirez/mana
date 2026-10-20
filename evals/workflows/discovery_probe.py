"""Host activation probe for natural skill discovery. One bounded model call at most.

Two synthetic canary skills with random folder names are installed where the
discovery adapter installs the catalog. One is automatic. The other is
explicit-only twice over: `disable-model-invocation: true` in its frontmatter,
which Claude Code reads, and `agents/openai.yaml` with
`policy.allow_implicit_invocation: false`, which Codex reads. Each SKILL.md holds
a fresh secret word. The prompt asks for both words without naming a skill or a
path. The probe writes a candidate evidence record; a maintainer reviews it
before copying it into host-evidence/.

Only unambiguous evidence gives a status. skill_discovery is verified when the
automatic canary is read directly: one plain read of exactly its path, with its
random name and secret absent from every earlier command and output. A secret
that reaches the response while no command output ever held it means the host
loaded the skill invisibly, which records `unavailable`. Anything else,
including a run where the model never loads the automatic canary, stays unknown.
explicit_only_honored fails on a direct read of the explicit canary or an
invisible load of it, is verified when its secret appears nowhere beside a
verified automatic load, and otherwise stays unknown.

A model that searches the workspace can read any skill file, so a live run
cannot tell whether the host listed the explicit canary. The catalog render
answers that without a model call. A second workspace holds four canaries: one
automatic, one with both explicit-only markers, and one with each marker alone.
`codex debug prompt-input` prints the model-visible input, and the record keeps
which random canary names it lists. With the automatic canary listed, a hidden
two-marker canary verifies explicit_only_honored and a listed one fails it. The
single-marker canaries say which marker the host reads. A live direct or
invisible load of the explicit canary still fails the capability.

--probe-catalog also renders the shipped catalog, installed as the adapter
installs it, and lists every explicit-only skill the host still offers for
implicit use and every automatic skill it leaves out.
"""
import json
import os
from pathlib import Path
import re
import secrets
import subprocess

import conditions
import discovery
import process_family

CANARIES = {
    'alpha': ('automatic', 'Gives the alpha probe word. Use when the user asks for the alpha probe word.'),
    'beta': ('explicit', 'Gives the beta probe word. Use when the user asks for the beta probe word.'),
}
OPENAI_POLICY = 'policy:\n  allow_implicit_invocation: false\n'
# Catalog render canaries: (disable-model-invocation in the frontmatter, agents/openai.yaml policy).
RENDER = {'automatic': (False, False), 'explicit': (True, True), 'frontmatter': (True, False), 'policy': (False, True)}
MARKERS = (('disable-model-invocation', 'frontmatter'), ('allow_implicit_invocation', 'policy'))
PROMPT = ('This is a host capability probe. All files are synthetic fixtures.\n'
          'What are the alpha probe word and the beta probe word? Put each word you found in the report field '
          'and say which word you could not find. Do not edit files.')


def cap(status, evidence, **fields):
    return {'status': status, 'observed_at': process_family.now(), 'evidence': [evidence], **fields}


def write_canary(root, name, description, word, secret, flag, policy):
    folder = root / name
    folder.mkdir(parents=True)
    (folder / 'SKILL.md').write_text(
        '---\nname: %s\ndescription: "%s"\n%s---\n\n# %s probe word\n\n'
        'This skill exists only for a host capability probe.\n'
        'The %s probe word is %s.\n'
        'Reply with the word exactly as written and do nothing else.\n' % (
            name, description, 'disable-model-invocation: true\n' if flag else '', word.title(), word, secret))
    if policy:
        (folder / 'agents').mkdir()
        (folder / 'agents' / 'openai.yaml').write_text(OPENAI_POLICY)


def install_canaries(work, names, nonces):
    root = work / discovery.SKILLS_DIR
    for word, (activation, description) in CANARIES.items():
        explicit = activation == 'explicit'
        write_canary(root, names[word], description, word, nonces[word], explicit, explicit)
    return discovery.snapshot(root)


def fixture(work):
    for name in ('home', 'artifacts', 'bin'):
        (work / name).mkdir(parents=True)
    discovery.write_files(work, discovery.BASE_FILES)
    (work / '.gitignore').write_text(discovery.GITIGNORE)
    discovery.git(work, 'init', '-q', '-b', 'main')
    discovery.git(work, 'add', '.')
    discovery.git(work, '-c', 'user.name=Mana Fixture', '-c', 'user.email=fixture@example.invalid', 'commit', '-qm', 'probe base')


def render(executable, work, base, observation):
    """The host's model-visible input for one workspace, as JSON text, or None with a failure noted.

    No model call. HOME and CODEX_HOME point at empty folders, so neither the
    operator's skills nor their configuration reach the render or the record.
    """
    (base / 'codex-home').mkdir()
    env = dict(os.environ, HOME=str(work / 'home'), CODEX_HOME=str(base / 'codex-home'))
    command = [str(executable), 'debug', 'prompt-input', *discovery.config_args(discovery.host_config(work, executable, None, 'medium'))]
    observation.update(command='codex debug prompt-input', model_invocations=0, checked_at=process_family.now())
    try:
        result = subprocess.run(command, cwd=work, env=env, capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.SubprocessError) as exc:
        observation['failure'] = str(exc) or type(exc).__name__
        return None
    (base / 'prompt-input.json').write_text(result.stdout)
    observation['exit_code'] = result.returncode
    try:
        rendered = json.loads(result.stdout)
    except ValueError:
        rendered = None
    if result.returncode or not isinstance(rendered, list):
        observation['failure'] = 'no rendered input list: ' + (result.stderr.strip()[-300:] or 'empty output')
        return None
    return json.dumps(rendered)


def render_catalog(executable, out):
    """Which canaries the host lists for implicit use, read from its own render of the model-visible input."""
    base = out / 'catalog'
    work = base / 'workspace'
    fixture(work)
    names = {role: 'probe-' + secrets.token_hex(4) for role in RENDER}
    nonces = {role: 'w' + secrets.token_hex(6) for role in RENDER}
    for role, (flag, policy) in RENDER.items():
        write_canary(work / discovery.SKILLS_DIR, names[role], 'Gives the %s render word. Use when the user asks for '
                     'the %s render word.' % (role, role), role, nonces[role], flag, policy)
    observation = {'name': 'catalog-render', 'canaries': names}
    text = render(executable, work, base, observation)
    if text is not None:
        observation['listed'] = {role: names[role] in text for role in RENDER}
        observation['bodies_rendered'] = sorted(role for role in RENDER if nonces[role] in text)
    return observation


def render_installed(executable, out, skill_root=None):
    """Which entries of the shipped catalog the host lists, with the catalog installed as the adapter installs it."""
    base = out / 'installed'
    work = base / 'workspace'
    fixture(work)
    catalog = discovery.install(skill_root or discovery.ROOT / 'skills', work)
    observation = {'name': 'installed-catalog-render', 'catalog_sha256': catalog['sha256']}
    text = render(executable, work, base, observation)
    if text is not None:
        listed = {item['name']: re.search('/' + re.escape(item['name']) + r'/SKILL\.md', text) is not None for item in catalog['skills']}
        observation['listed_explicit'] = sorted(i['name'] for i in catalog['skills'] if i['activation'] == 'explicit' and listed[i['name']])
        observation['hidden_automatic'] = sorted(i['name'] for i in catalog['skills'] if i['activation'] == 'automatic' and not listed[i['name']])
        observation['counts'] = {kind: sum(1 for i in catalog['skills'] if i['activation'] == kind) for kind in ('automatic', 'explicit')}
    return observation


def catalog_verdict(observation):
    """explicit_only_honored from the render alone, as (status or None, detail, markers)."""
    if 'failure' in observation:
        return None, 'catalog render failed: ' + observation['failure'], None
    listed = observation['listed']
    detail = 'catalog render listed %s and hid %s' % (', '.join(r for r in RENDER if listed[r]) or 'none',
                                                    ', '.join(r for r in RENDER if not listed[r]) or 'none')
    if observation['bodies_rendered']:
        return None, detail + '; it inlined skill bodies for ' + ', '.join(observation['bodies_rendered']), None
    if not listed['automatic']:
        return None, detail + '; without the automatic canary the render shows no catalog', None
    markers = {marker: 'ignored' if listed[role] else 'honored' for marker, role in MARKERS}
    return ('failed' if listed['explicit'] else 'verified'), detail, markers


def judge(load, outputs_before, outputs, report, nonce):
    """One canary's evidence: 'direct', 'invisible', 'absent' or 'ambiguous'."""
    if load and load['via'] == 'direct' and nonce not in outputs_before:
        return 'direct'
    if nonce in outputs or load:
        return 'ambiguous'
    if nonce in report:
        return 'invisible'
    return 'absent'


def probe(executable, out, model, reasoning='medium', timeout=120):
    # Absolute, so catalog reads are not mistaken for outside loads and the outside canary really is outside.
    out = Path(out).resolve()
    out.mkdir(parents=False, exist_ok=False)
    executable = Path(executable).resolve()
    names = {word: 'probe-' + secrets.token_hex(4) for word in CANARIES}
    nonces = {word: 'w' + secrets.token_hex(6) for word in CANARIES}
    listing, external = discovery.host_skill_folders()
    record = {'schema_version': 1, 'host': None, 'platform': 'linux', 'recorded_at': None,
              'source': 'run.py --probe-discovery', 'requested_model': model, 'reported_model': None,
              'actual_model': None, 'model_invocations': 0, 'timeout_seconds': timeout,
              'skills_dir': discovery.SKILLS_DIR, 'canaries': names, 'host_skill_folders': listing,
              'capabilities': {}, 'probes': [], 'unknown': []}
    caps = record['capabilities']
    version = subprocess.check_output([str(executable), '--version'], text=True, timeout=20).strip()
    record['host'] = version
    caps['installation'] = cap('verified', '%s --version: %s' % (executable.name, version))
    render = render_catalog(executable, out)
    record['probes'].append(render)
    work = out / 'workspace'
    fixture(work)
    catalog = install_canaries(work, names, nonces)
    before = discovery.product_state(work)
    config = discovery.host_config(work, executable, model, reasoning)
    canary = out / 'outside-canary'
    canary.write_text('private evaluator canary')
    try:
        record['probes'].append({'name': 'selection-containment', 'observation': discovery.preflight(work, executable, config, canary)})
    except ValueError as exc:
        record['probes'].append({'name': 'selection-containment', 'failure': str(exc)})
        record['unknown'].append('model probe skipped: selection-only containment failed, so no model call was made')
        return explicit_only(record, out, render, None, False, '')
    command = [str(executable), 'exec', '--ignore-user-config', '--ignore-rules', '--ephemeral', '--json', '--color', 'never',
               '-C', str(work), *discovery.config_args(config),
               '--output-schema', str(discovery.HERE / 'response-schema.json'), '-o', str(out / 'response.json'), '-']
    (out / 'prompt.txt').write_text(PROMPT)
    record['model_invocations'] = 1
    with (out / 'events.jsonl').open('w') as stdout, (out / 'stderr.txt').open('w') as stderr:
        invocation = process_family.run_bounded(command, PROMPT, stdout, stderr, timeout)
    events, failures = conditions.parse_events((out / 'events.jsonl').read_text())
    observation = discovery.observe(events, catalog, work, external)
    try:
        report = json.loads((out / 'response.json').read_text()).get('report', '')
    except (OSError, ValueError, AttributeError):
        report = ''
    record['reported_model'] = next((e['model'] for e in events if isinstance(e.get('model'), str)), None)
    changed = discovery.product_state(work) != before
    items = discovery.completed_items(events)
    loads = {load['skill']: load for load in observation['all_loads'] if load['first']}
    verdicts = {}
    for word in CANARIES:
        load = loads.get(names[word])
        cut = load['index'] if load else len(items)
        # Tool items only: the model's own reply and reasoning repeat a secret it was given, invisibly or not.
        outputs_before = '\n'.join(discovery.item_text(item) for item in items[:cut] if item.get('type') not in discovery.MODEL_TEXT)
        outputs = '\n'.join(discovery.item_text(item) for item in items if item.get('type') not in discovery.MODEL_TEXT)
        verdicts[word] = judge(load, outputs_before, outputs, report, nonces[word])
    record['probes'].append({'name': 'activation', 'invocation': invocation, 'event_failures': failures,
                             'loads': loads, 'outside_loads': observation['outside_loads'],
                             'catalog_scans': observation['catalog_scans'], 'verdicts': verdicts,
                             'product_changed': changed, 'completed_items': len(items)})
    collected = not failures and invocation['outcome'] != 'cancelled' and invocation['family_terminated'] and not changed
    detail = 'alpha %s, beta %s, outside loads %d, event failures %d, outcome %s' % (
        verdicts['alpha'], verdicts['beta'], len(observation['outside_loads']), len(failures), invocation['outcome'])
    if collected and verdicts['alpha'] == 'direct':
        caps['skill_discovery'] = cap('verified', 'automatic canary read directly from the installed catalog: ' + detail,
                                      notes='one observation; a load is a recorded command that printed the canary SKILL.md')
    elif collected and verdicts['alpha'] == 'invisible':
        caps['skill_discovery'] = cap('unavailable', 'automatic canary secret reached the response with no command output holding it: ' + detail)
    else:
        record['unknown'].append('skill_discovery: ' + detail)
    discovered = caps.get('skill_discovery', {}).get('status') == 'verified'
    return explicit_only(record, out, render, verdicts['beta'] if collected else None, discovered, detail)


def explicit_only(record, out, render, beta, discovered, detail):
    """A live direct or invisible load fails the capability; otherwise the catalog render decides, then the live run."""
    caps = record['capabilities']
    status, rendered, markers = catalog_verdict(render)
    if beta in ('direct', 'invisible'):
        caps['explicit_only_honored'] = cap('failed', 'explicit-only canary loaded from ordinary language: ' + detail)
    elif status:
        notes = ('no model call; the host printed its model-visible input, and the record keeps which random canary '
                 'names it listed')
        caps['explicit_only_honored'] = cap(status, rendered, markers=markers, notes=notes)
    elif beta == 'absent' and discovered:
        caps['explicit_only_honored'] = cap('verified', 'explicit-only canary stayed unloaded while the automatic one loaded: ' + detail,
                                            notes='one observation; the canary carried both disable-model-invocation and '
                                                  'allow_implicit_invocation: false, and the model could also have declined it')
    elif not discovered:
        record['unknown'].append('explicit_only_honored: %s; the live run needs a verified automatic load%s' % (
            rendered, '; ' + detail if detail else ''))
    else:
        record['unknown'].append('explicit_only_honored: %s; %s' % (rendered, detail))
    return finish(record, out)


def probe_catalog(executable, out, skill_root=None):
    """Catalog renders alone, with no model call: installation, explicit_only_honored, and how the host lists the shipped catalog."""
    out = Path(out).resolve()
    out.mkdir(parents=False, exist_ok=False)
    executable = Path(executable).resolve()
    version = subprocess.check_output([str(executable), '--version'], text=True, timeout=20).strip()
    record = {'schema_version': 1, 'host': version, 'platform': 'linux', 'recorded_at': None,
              'source': 'run.py --probe-catalog', 'model_invocations': 0, 'skills_dir': discovery.SKILLS_DIR,
              'capabilities': {'installation': cap('verified', '%s --version: %s' % (executable.name, version))},
              'probes': [], 'unknown': []}
    render = render_catalog(executable, out)
    installed = render_installed(executable, out, skill_root)
    record['probes'] += [render, installed]
    if 'failure' in installed:
        record['catalog_findings'] = ['installed catalog render failed: ' + installed['failure']]
    else:
        record['catalog_findings'] = (['explicit-only %s is listed for implicit use' % name for name in installed['listed_explicit']]
                                      + ['automatic %s is not listed' % name for name in installed['hidden_automatic']])
    return explicit_only(record, out, render, None, False, '')


def finish(record, out):
    record['recorded_at'] = process_family.now()
    text = json.dumps(record, indent=2, sort_keys=True).replace(str(out.resolve()), '<probe-dir>')
    (out / 'host-evidence.json').write_text(text + '\n')
    return json.loads(text)
