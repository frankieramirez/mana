"""Host activation probe for natural skill discovery. One bounded model call at most.

Two synthetic canary skills are installed where the discovery adapter installs
the catalog: one automatic, one with `disable-model-invocation: true`. Each
SKILL.md holds a fresh secret word. The prompt asks for both words without naming
a skill or a path. A load counts only from a recorded command whose output holds
that skill's description line and body. The probe writes a candidate evidence
record; a maintainer reviews it before copying it into host-evidence/.

skill_discovery is verified only when the automatic canary is loaded directly,
before any command output revealed its path. A secret that reaches the response
with no recorded load means the host loaded the skill invisibly, so loads are
unobservable. explicit_only_honored is verified when the explicit canary is
neither loaded nor leaked while the automatic one was; a direct load fails it; a
load found by searching the workspace leaves it unknown.
"""
import json
from pathlib import Path
import secrets
import subprocess

import conditions
import discovery
import process_family

CANARIES = {
    'probe-alpha': ('automatic', 'Gives the alpha probe word. Use when the user asks for the alpha probe word.'),
    'probe-beta': ('explicit', 'Gives the beta probe word. Use when the user asks for the beta probe word.'),
}
PROMPT = ('This is a host capability probe. All files are synthetic fixtures.\n'
          'What are the alpha probe word and the beta probe word? Put each word you found in the report field '
          'and say which word you could not find. Do not edit files.')
CASE = {'id': 'activation-probe', 'setup': {}}


def cap(status, evidence, **fields):
    return {'status': status, 'observed_at': process_family.now(), 'evidence': [evidence], **fields}


def install_canaries(work, nonces):
    root = work / discovery.SKILLS_DIR
    for name, (activation, description) in CANARIES.items():
        folder = root / name
        folder.mkdir(parents=True)
        flag = 'disable-model-invocation: true\n' if activation == 'explicit' else ''
        word = name.split('-')[1]
        (folder / 'SKILL.md').write_text(
            '---\nname: %s\ndescription: "%s"\n%s---\n\n# %s probe word\n\n'
            'This skill exists only for a host capability probe.\n'
            'The %s probe word is %s.\n'
            'Reply with the word exactly as written and do nothing else.\n' % (name, description, flag, word.title(), word, nonces[name]))
    return discovery.snapshot(root)


def probe(executable, out, model, reasoning='medium', timeout=120):
    out = Path(out)
    out.mkdir(parents=False, exist_ok=False)
    executable = Path(executable).resolve()
    record = {'schema_version': 1, 'host': None, 'platform': 'linux', 'recorded_at': None,
              'source': 'run.py --probe-discovery', 'requested_model': model, 'reported_model': None,
              'actual_model': None, 'model_invocations': 0, 'timeout_seconds': timeout,
              'skills_dir': discovery.SKILLS_DIR, 'capabilities': {}, 'probes': [], 'unknown': []}
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
    nonces = {name: 'w' + secrets.token_hex(6) for name in CANARIES}
    catalog = install_canaries(work, nonces)
    before = discovery.product_state(work)
    config, _ = discovery.host_config(work, executable, model, reasoning)
    if discovery.SKIP_FLAG in config:
        raise ValueError('activation probe must leave host skill discovery on')
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
    observation = discovery.observe(events, catalog, work)
    try:
        report = json.loads((out / 'response.json').read_text()).get('report', '')
    except (OSError, ValueError, AttributeError):
        report = ''
    record['reported_model'] = next((e['model'] for e in events if isinstance(e.get('model'), str)), None)
    changed = discovery.product_state(work) != before
    loads = {load['skill']: load for load in observation['all_loads'] if load['first']}
    leaked = {name: nonces[name] in report for name in CANARIES}
    outcome = {'invocation': invocation, 'event_failures': failures, 'loads': loads, 'catalog_scans': observation['catalog_scans'],
               'secret_in_response': leaked, 'product_changed': changed, 'command_events': observation['operations']}
    record['probes'].append({'name': 'activation', **outcome})
    collected = not failures and invocation['outcome'] != 'cancelled' and invocation['family_terminated'] and not changed
    alpha, beta = loads.get('probe-alpha'), loads.get('probe-beta')
    detail = 'alpha load %s, beta load %s, secrets in response %s, event failures %d, outcome %s' % (
        alpha and alpha['via'], beta and beta['via'], leaked, len(failures), invocation['outcome'])
    if not collected:
        caps['skill_discovery'] = cap('failed', 'activation probe collection incomplete: ' + detail)
    elif alpha and alpha['via'] == 'direct':
        caps['skill_discovery'] = cap('verified', 'automatic canary loaded directly from the installed catalog: ' + detail,
                                      notes='one observation; a load event is a recorded command that printed the canary SKILL.md')
    elif leaked['probe-alpha'] and not alpha:
        caps['skill_discovery'] = cap('unavailable', 'automatic canary secret reached the response without a recorded load: ' + detail)
    elif alpha:
        record['unknown'].append('skill_discovery: the automatic canary was found by searching the workspace, not from the host catalog; ' + detail)
    else:
        caps['skill_discovery'] = cap('failed', 'automatic canary was never loaded: ' + detail)
    discovered = caps.get('skill_discovery', {}).get('status') == 'verified'
    if not collected or not discovered:
        record['unknown'].append('explicit_only_honored: needs an observable automatic load in the same invocation; ' + detail)
    elif beta and beta['via'] == 'direct' or leaked['probe-beta'] and not beta:
        caps['explicit_only_honored'] = cap('failed', 'explicit-only canary was loaded from ordinary language: ' + detail)
    elif beta:
        record['unknown'].append('explicit_only_honored: the explicit canary was found by searching the workspace; ' + detail)
    else:
        caps['explicit_only_honored'] = cap('verified', 'explicit-only canary stayed unloaded while the automatic one loaded: ' + detail,
                                            notes='one observation; the model could also have declined the skill')
    return finish(record, out)


def finish(record, out):
    record['recorded_at'] = process_family.now()
    text = json.dumps(record, indent=2, sort_keys=True).replace(str(out.resolve()), '<probe-dir>')
    (out / 'host-evidence.json').write_text(text + '\n')
    return json.loads(text)
