"""Host activation probe for natural skill discovery. One bounded model call at most.

Two synthetic canary skills with random folder names are installed where the
discovery adapter installs the catalog. One is automatic. The other is
explicit-only twice over: `disable-model-invocation: true` in its frontmatter,
which Claude Code reads, and `agents/openai.yaml` with
`policy.allow_implicit_invocation: false`, which Codex reads. Each SKILL.md holds
a fresh secret word. The prompt asks for both words without naming a skill or a
path, and it forbids searching the workspace: an explicit canary the model finds
by listing files says nothing about what the host offered, so it can only judge
as ambiguous. The probe writes a candidate evidence record; a maintainer reviews
it before copying it into host-evidence/.

Only unambiguous evidence gives a status. skill_discovery is verified when the
automatic canary is read directly: one plain read of exactly its path, with its
random name and secret absent from every earlier command and output. A secret
that reaches the response while no command output ever held it means the host
loaded the skill invisibly, which records `unavailable`. Anything else,
including a run where the model never loads the automatic canary, stays unknown.
explicit_only_honored fails on a direct read of the explicit canary or an
invisible load of it, is verified when its secret appears nowhere beside a
verified automatic load, and otherwise stays unknown.
"""
import json
from pathlib import Path
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
PROMPT = ('This is a host capability probe. All files are synthetic fixtures.\n'
          'What are the alpha probe word and the beta probe word? Use only the skills this session offers you. '
          'You may open a skill file the session lists, but do not search, list or browse the workspace for other files. '
          'Put each word you found in the report field and say which word you could not find. Do not edit files.')


def cap(status, evidence, **fields):
    return {'status': status, 'observed_at': process_family.now(), 'evidence': [evidence], **fields}


def install_canaries(work, names, nonces):
    root = work / discovery.SKILLS_DIR
    for word, (activation, description) in CANARIES.items():
        folder = root / names[word]
        folder.mkdir(parents=True)
        flag = 'disable-model-invocation: true\n' if activation == 'explicit' else ''
        (folder / 'SKILL.md').write_text(
            '---\nname: %s\ndescription: "%s"\n%s---\n\n# %s probe word\n\n'
            'This skill exists only for a host capability probe.\n'
            'The %s probe word is %s.\n'
            'Reply with the word exactly as written and do nothing else.\n' % (
                names[word], description, flag, word.title(), word, nonces[word]))
        if activation == 'explicit':
            (folder / 'agents').mkdir()
            (folder / 'agents' / 'openai.yaml').write_text(OPENAI_POLICY)
    return discovery.snapshot(root)


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
    work = out / 'workspace'
    for name in ('home', 'artifacts', 'bin'):
        (work / name).mkdir(parents=True)
    discovery.write_files(work, discovery.BASE_FILES)
    (work / '.gitignore').write_text(discovery.GITIGNORE)
    discovery.git(work, 'init', '-q', '-b', 'main')
    discovery.git(work, 'add', '.')
    discovery.git(work, '-c', 'user.name=Mana Fixture', '-c', 'user.email=fixture@example.invalid', 'commit', '-qm', 'probe base')
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
        return finish(record, out)
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
    if caps.get('skill_discovery', {}).get('status') != 'verified':
        record['unknown'].append('explicit_only_honored: needs a verified automatic load in the same invocation; ' + detail)
    elif verdicts['beta'] in ('direct', 'invisible'):
        caps['explicit_only_honored'] = cap('failed', 'explicit-only canary loaded from ordinary language: ' + detail)
    elif verdicts['beta'] == 'absent':
        caps['explicit_only_honored'] = cap('verified', 'explicit-only canary stayed unloaded while the automatic one loaded: ' + detail,
                                            notes='one observation; the canary carried both disable-model-invocation and '
                                                  'allow_implicit_invocation: false, and the model could also have declined it')
    else:
        record['unknown'].append('explicit_only_honored: ' + detail)
    return finish(record, out)


def finish(record, out):
    record['recorded_at'] = process_family.now()
    text = json.dumps(record, indent=2, sort_keys=True).replace(str(out.resolve()), '<probe-dir>')
    (out / 'host-evidence.json').write_text(text + '\n')
    return json.loads(text)
