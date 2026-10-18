"""Selection-only discovery adapter: natural skill selection on a real host, stopped before product mutation.

The runner in run.py names one skill path in the prompt and sets
`features.skip_host_skill_discovery=true`. This adapter does neither. It installs
the whole catalog where the host discovers skills, sends the user's request
unchanged plus one neutral sentence, keeps the workspace read-only except
`artifacts/`, and reads selection from the host's own event stream.

Four observations stay separate. `activation` says which catalog entrypoints
were actually loaded against the preregistered routes. `routing` says whether the
observed route is accepted, an accepted fallback, or wrong. `execution` covers
what happened after selection; a selection-only run never claims a workflow
outcome. `capability_limit` records the capabilities a case removes, apart from
routing, so a correct route that hits a missing capability is not a wrong route.
Hard verdicts come only from unambiguous evidence; the rest is
`needs_adjudication` with the commands a person should read.

A result is labelled `live-discovery` only from a live invocation of the real
host whose recorded evidence accepts it for the `discovery` mode. Every run
against the fake host, including its keyword selector, is an `offline-fixture`.
"""
import hashlib
import json
import os
from pathlib import Path
import random
import re
import shlex
import shutil
import socket
import subprocess
import sys
import time

import conditions
import delegation
import hosts
import process_family

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
CASES = HERE / 'discovery-cases.json'
# Where the adapter installs the catalog inside each workspace. The host activation
# probe (discovery_probe.py) installs its canaries in the same place, so a recorded
# skill_discovery observation covers exactly this layout.
SKILLS_DIR = '.agents/skills'
SUFFIX = '\n\nAll workspace files are synthetic fixtures.'
SEED = 20261017
TIMEOUT = 120
SKIP_FLAG = 'features.skip_host_skill_discovery=true'
ACTIONS = ('write', 'git-write', 'publish', 'delegate')
# Skill folders outside the workspace that a host keeping the operator's environment may also list.
HOST_SKILL_FOLDERS = (('~/.agents/skills', Path.home() / '.agents' / 'skills'),
                      ('~/.codex/skills', Path.home() / '.codex' / 'skills'),
                      ('/etc/codex/skills', Path('/etc/codex/skills')))
SETUP_KEYS = {'files', 'branch_files', 'dirty_files', 'git', 'filler', 'exclude_skills', 'unavailable'}
GIT_STATES = (None, 'cherry-pick-conflict', 'merge-commit')
UNAVAILABLE = {'children', 'question_tool', 'skill:cast'}
CASE_KEYS = {'id', 'kind', 'skill', 'invocation', 'request', 'routes', 'forbidden_actions', 'setup'}
NAME = re.compile(r'[a-z0-9][a-z0-9-]*')
BASE_FILES = {
    'app.py': 'def total(items):\n    return sum(item["price"] for item in items)\n',
    'test_app.py': 'import unittest\nfrom app import total\n\n\nclass Total(unittest.TestCase):\n'
                   '    def test_sum(self):\n        self.assertEqual(total([{"price": 2}, {"price": 3}]), 5)\n',
    'README.md': '# Fixture shop\n\nA small synthetic project.\n',
}
GITIGNORE = 'artifacts/\nbin/\nhome/\n.agents/\n'


def file_hash(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


# ---------------------------------------------------------------- catalog

def frontmatter(text):
    """The single-line keys of a SKILL.md frontmatter block, as the catalog writes them."""
    if not text.startswith('---\n'):
        raise ValueError('SKILL.md has no frontmatter')
    end = text.find('\n---\n', 3)
    if end < 0:
        raise ValueError('SKILL.md frontmatter is not closed')
    found = {}
    for line in text[4:end].splitlines():
        key, sep, value = line.partition(':')
        if not sep or not key or key != key.strip():
            continue
        value = value.strip()
        if value.startswith('"'):
            value = json.loads(value)
        found[key] = value
    return found, text[:end + 5], text[end + 5:]


def entry(path):
    text = Path(path).read_text()
    meta, _, _ = frontmatter(text)
    name, description = meta.get('name'), meta.get('description')
    if not isinstance(name, str) or not NAME.fullmatch(name) or not isinstance(description, str) or not description:
        raise ValueError('SKILL.md needs a name and description: ' + str(path))
    flag = meta.get('disable-model-invocation', 'false')
    if flag not in ('true', 'false'):
        raise ValueError('disable-model-invocation must be true or false: ' + str(path))
    return {'name': name, 'description': description,
            'activation': 'explicit' if flag == 'true' else 'automatic'}


def snapshot(root, exclude=()):
    """Frozen metadata for every installed entrypoint, with byte digests of each skill folder."""
    root = Path(root)
    skills = []
    for path in sorted(root.glob('*/SKILL.md')):
        if path.parent.name in exclude:
            continue
        item = entry(path)
        if item['name'] != path.parent.name:
            raise ValueError('skill name differs from its folder: ' + path.parent.name)
        files = conditions.inventory(path.parent)
        item.update(entry_sha256=file_hash(path), inventory_sha256=conditions.digest(conditions.encoded(files)))
        skills.append(item)
    if not skills:
        raise ValueError('empty skill catalog: ' + str(root))
    return {'skills': skills, 'sha256': conditions.digest(conditions.encoded(skills))}


def install(skill_root, work, exclude=()):
    """Copy the catalog where the host discovers skills, then prove the installed bytes match the source."""
    source = snapshot(skill_root, exclude)
    destination = Path(work) / SKILLS_DIR
    destination.mkdir(parents=True)
    for item in source['skills']:
        shutil.copytree(Path(skill_root) / item['name'], destination / item['name'])
    installed = snapshot(destination)
    if installed != source:
        raise ValueError('installed catalog differs from its source snapshot')
    return installed


# ---------------------------------------------------------------- cases

def mentions(text, name):
    return re.search(r'(?<![\w-])' + re.escape(name) + r'(?![\w-])', text, re.IGNORECASE) is not None


def routes_digest(path=CASES):
    return file_hash(path)


def load_cases(path=CASES):
    data = json.loads(Path(path).read_text())
    if set(data) != {'version', 'study', 'source_revision', 'activation', 'first_live_group', 'cases'} or data['version'] != 1:
        raise ValueError('invalid discovery case collection')
    activation = data['activation']
    if not isinstance(activation, dict) or set(activation.values()) - {'automatic', 'explicit'}:
        raise ValueError('activation map must say automatic or explicit per skill')
    names = set(activation)
    seen, positives, negatives, overlap = set(), {}, {}, 0
    for case in data['cases']:
        if set(case) != CASE_KEYS:
            raise ValueError('invalid discovery case fields: ' + str(case.get('id')))
        cid = case['id']
        if not isinstance(cid, str) or not NAME.fullmatch(cid) or cid in seen:
            raise ValueError('invalid or duplicate discovery case id: ' + str(cid))
        seen.add(cid)
        if case['kind'] not in ('positive', 'negative', 'overlap') or case['invocation'] not in ('ordinary', 'direct'):
            raise ValueError('invalid kind or invocation: ' + cid)
        if case['skill'] is not None and case['skill'] not in names:
            raise ValueError('unknown skill: ' + cid)
        request = case['request']
        if not isinstance(request, str) or not request.strip():
            raise ValueError('empty request: ' + cid)
        named = sorted(name for name in names if mentions(request, name))
        # Ordinary language never names a catalog skill; a direct request names exactly its own.
        if case['invocation'] == 'ordinary' and named:
            raise ValueError('ordinary request names a skill: %s %s' % (cid, named))
        if case['invocation'] == 'direct' and named != [case['skill']]:
            raise ValueError('direct request must name only its skill: ' + cid)
        routes = case['routes']
        if not isinstance(routes, dict) or set(routes) != {'accepted', 'fallback'} or not routes['accepted']:
            raise ValueError('routes need a non-empty accepted list and a fallback list: ' + cid)
        listed = routes['accepted'] + routes['fallback']
        if len(set(listed)) != len(listed):
            raise ValueError('a route is listed twice: ' + cid)
        for route in listed:
            if route != 'ordinary' and not (route.startswith('skill:') and route[6:] in names):
                raise ValueError('unknown route %s: %s' % (route, cid))
        if set(case['forbidden_actions']) - set(ACTIONS):
            raise ValueError('unknown forbidden action: ' + cid)
        setup = case['setup']
        if not isinstance(setup, dict) or set(setup) - SETUP_KEYS or setup.get('git') not in GIT_STATES:
            raise ValueError('invalid setup: ' + cid)
        if set(setup.get('exclude_skills', [])) - names or set(setup.get('unavailable', [])) - UNAVAILABLE:
            raise ValueError('invalid capability setup: ' + cid)
        for key in ('files', 'branch_files', 'dirty_files'):
            for relative in setup.get(key, {}):
                if relative.startswith('/') or '..' in relative.split('/') or relative.split('/')[0] in ('.git', '.agents', 'artifacts', 'bin', 'home'):
                    raise ValueError('fixture path outside the product tree: ' + cid)
        if case['kind'] == 'positive':
            if routes['accepted'] != ['skill:' + case['skill']]:
                raise ValueError('a positive case accepts exactly its skill: ' + cid)
            # An explicit-only skill is never expected from ordinary language.
            if case['invocation'] == 'ordinary' and activation[case['skill']] != 'automatic':
                raise ValueError('ordinary positive case needs an automatic skill: ' + cid)
            positives[case['skill']] = cid
        elif case['kind'] == 'negative':
            if 'skill:' + case['skill'] in listed or case['invocation'] != 'ordinary':
                raise ValueError('a negative case never accepts its own skill and uses ordinary language: ' + cid)
            negatives[case['skill']] = cid
        else:
            overlap += 1
    if set(positives) != names or set(negatives) != names or overlap != 8:
        raise ValueError('need one positive and one negative per skill plus eight overlap cases')
    if len(data['first_live_group']) != 12 or set(data['first_live_group']) - seen:
        raise ValueError('first live group needs twelve known cases')
    return data


def check_catalog(data, catalog):
    """The preregistered activation map must still describe the frozen catalog."""
    actual = {item['name']: item['activation'] for item in catalog['skills']}
    if actual != data['activation']:
        changed = sorted(k for k in set(actual) | set(data['activation']) if actual.get(k) != data['activation'].get(k))
        raise ValueError('catalog activation differs from the preregistered routes; new routes are needed: ' + ', '.join(changed))
    return True


def schedule(ids, repetitions=2, seed=SEED):
    """The protocol's shuffle over sorted case ids and repetitions, saved before execution."""
    cells = [{'case': cid, 'repetition': rep} for cid in sorted(ids) for rep in range(1, repetitions + 1)]
    random.Random(seed).shuffle(cells)
    return [dict(cell, slot=index) for index, cell in enumerate(cells)]


# ---------------------------------------------------------------- prompt and host settings

def prompt(case):
    """The request exactly as a user would type it. No skill path, no load instruction, no route hint."""
    return case['request'] + SUFFIX


def prompt_paths(text, work):
    """Workspace or catalog paths in a prompt, which would tell the host where an entrypoint lives."""
    return [marker for marker in (str(work), SKILLS_DIR, 'SKILL.md') if marker in text]


def permission_table(work, executable):
    """Read-only product tree and Git; only artifacts/ is writable. Nothing outside is readable."""
    return {':root': 'deny', ':minimal': 'read', str(work): 'read', str(work / 'artifacts'): 'write',
            str(Path(executable).parent.parent): 'read'}


def host_config(work, executable, model, reasoning):
    table = permission_table(work, executable)
    env = {'PATH': str(work / 'bin') + ':/usr/bin:/bin', 'HOME': str(work / 'home'), 'GIT_CONFIG_NOSYSTEM': '1',
           'GIT_CONFIG_GLOBAL': '/dev/null', 'LC_ALL': 'C', 'PYTHONDONTWRITEBYTECODE': '1', 'TMPDIR': str(work / 'artifacts')}
    config = ['default_permissions="mana-eval"', 'approval_policy="never"',
              'permissions.mana-eval.filesystem={ ' + ', '.join(json.dumps(k) + '=' + json.dumps(v) for k, v in table.items()) + ' }',
              'permissions.mana-eval.network.enabled=false', 'shell_environment_policy.inherit="none"',
              'shell_environment_policy.set={ ' + ', '.join(json.dumps(k) + '=' + json.dumps(v) for k, v in env.items()) + ' }']
    # The shared settings minus the one that turns discovery off. No children: multi-agent stays disabled.
    config += [value for value in delegation.host_config(None, model, reasoning) if value != SKIP_FLAG]
    if SKIP_FLAG in config:
        raise ValueError('discovery adapter must not skip host skill discovery')
    return config


def config_args(values):
    return [part for value in values for part in ('-c', value)]


# ---------------------------------------------------------------- fixture

def git(work, *args, check=True):
    env = {'PATH': '/usr/bin:/bin', 'HOME': str(work / 'home'), 'GIT_CONFIG_NOSYSTEM': '1', 'GIT_CONFIG_GLOBAL': '/dev/null',
           'LC_ALL': 'C', 'GIT_AUTHOR_DATE': '2000-01-01T00:00:00+00:00', 'GIT_COMMITTER_DATE': '2000-01-01T00:00:00+00:00'}
    result = subprocess.run(['git', '-c', 'core.fsmonitor=false', '-c', 'core.hooksPath=/dev/null', '-C', str(work), *args],
                            env=env, capture_output=True, text=True)
    if check and result.returncode:
        raise ValueError('fixture git %s failed: %s' % (' '.join(args), result.stderr.strip()))
    return result.stdout.strip()


def write_files(work, files):
    for relative, content in files.items():
        path = work / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)


def product_state(work):
    """Every product byte plus the Git state a selection-only run must leave alone."""
    files = {}
    for directory, dirs, names in os.walk(work):
        parent = Path(directory)
        if parent == work:
            dirs[:] = [d for d in dirs if d not in ('.git', '.agents', 'artifacts', 'bin', 'home')]
        for name in names:
            path = parent / name
            files[path.relative_to(work).as_posix()] = 'symlink:' + os.readlink(path) if path.is_symlink() else file_hash(path)
    sequencer = sorted(name for name in ('CHERRY_PICK_HEAD', 'MERGE_HEAD', 'REVERT_HEAD', 'REBASE_HEAD')
                       if (work / '.git' / name).exists())
    return {'files': files, 'head': git(work, 'rev-parse', 'HEAD'), 'branch': git(work, 'branch', '--show-current'),
            'status': git(work, 'status', '--porcelain'), 'index': file_hash(work / '.git' / 'index'),
            'sequencer': sequencer, 'refs': git(work, 'for-each-ref', '--format=%(refname) %(objectname)')}


def prepare(case, base, skill_root=None):
    """A disposable repository for one case with the catalog installed for discovery."""
    setup = case['setup']
    work = Path(base) / 'workspace'
    for name in ('home', 'artifacts', 'bin'):
        (work / name).mkdir(parents=True)
    write_files(work, BASE_FILES)
    (work / '.gitignore').write_text(GITIGNORE)
    write_files(work, setup.get('files', {}))
    for number in range(setup.get('filler', 0)):
        write_files(work, {'services/module_%02d.py' % number: 'def handler_%02d(event):\n    return {"ok": True, "id": %d}\n' % (number, number)})
    # Offline doubles: publication and tracker calls fail visibly instead of reaching a service.
    gh = work / 'bin' / 'gh'
    gh.write_text('#!/bin/sh\necho "offline fixture: unsupported gh operation" >&2\nexit 97\n')
    gh.chmod(0o755)
    git(work, 'init', '-q', '-b', 'main')
    git(work, 'config', 'user.name', 'Mana Fixture')
    git(work, 'config', 'user.email', 'fixture@example.invalid')
    git(work, 'add', '.')
    git(work, 'commit', '-qm', 'fixture base')
    git(work, 'update-ref', 'refs/remotes/origin/main', 'HEAD')
    git(work, 'switch', '-qc', 'fixture-work')
    if setup.get('branch_files'):
        write_files(work, setup['branch_files'])
        git(work, 'add', '.')
        git(work, 'commit', '-qm', 'fixture branch change')
    state = setup.get('git')
    if state == 'cherry-pick-conflict':
        git(work, 'switch', '-qc', 'feature', 'main')
        write_files(work, {'app.py': 'def total(items):\n    return round(sum(item["price"] for item in items), 2)\n'})
        git(work, 'commit', '-qam', 'Round totals')
        git(work, 'switch', '-q', 'fixture-work')
        write_files(work, {'app.py': 'def total(items):\n    return sum(item["price"] * item.get("qty", 1) for item in items)\n'})
        git(work, 'commit', '-qam', 'Count quantities')
        git(work, 'cherry-pick', 'feature', check=False)
        if not (work / '.git' / 'CHERRY_PICK_HEAD').exists():
            raise ValueError('cherry-pick fixture did not stop on a conflict')
    elif state == 'merge-commit':
        git(work, 'switch', '-qc', 'feature', 'main')
        write_files(work, {'shipping.py': 'def shipping(total):\n    return 0 if total >= 50 else 5\n'})
        git(work, 'add', '.')
        git(work, 'commit', '-qm', 'Add shipping rule')
        git(work, 'switch', '-q', 'fixture-work')
        git(work, 'merge', '-q', '--no-ff', '-m', 'Merge shipping rule', 'feature')
    if setup.get('dirty_files'):
        write_files(work, setup['dirty_files'])
    catalog = install(skill_root or ROOT / 'skills', work, setup.get('exclude_skills', ()))
    return work, {'catalog': catalog, 'product_state': product_state(work)}


def preflight(work, executable, config, canary, routes=CASES):
    """Containment of the selection-only profile, checked through the host sandbox before any model call."""
    if sys.platform != 'linux':
        raise ValueError('discovery adapter supports Linux only')
    listener = socket.socket()
    listener.bind(('127.0.0.1', 0))
    listener.listen(2)
    port = listener.getsockname()[1]
    code = ('import json, pathlib, socket\nseen = {}\n'
            'def attempt(name, action):\n    try:\n        action()\n    except OSError:\n        seen[name] = "denied"\n'
            '    else:\n        seen[name] = "allowed"\n'
            'attempt("outside_read", lambda: pathlib.Path(%r).read_bytes())\n'
            'attempt("routes_read", lambda: pathlib.Path(%r).read_bytes())\n'
            'attempt("product_write", lambda: open("app.py", "ab").close())\n'
            'attempt("git_write", lambda: open(".git/mana-probe", "w").close())\n'
            'attempt("catalog_write", lambda: open(%r, "w").close())\n'
            'attempt("tool_write", lambda: open("bin/mana-probe", "w").close())\n'
            'attempt("artifact_write", lambda: pathlib.Path("artifacts/mana-probe").write_text("ok"))\n'
            'attempt("network", lambda: socket.create_connection(("127.0.0.1", %d), timeout=1).close())\n'
            'print("MANA-DISCOVERY " + json.dumps(seen, sort_keys=True))\n') % (str(canary), str(routes), SKILLS_DIR + '/mana-probe', port)
    command = [str(executable), 'sandbox', '-P', 'mana-eval', '-C', str(work), *config_args(config), '--', '/usr/bin/python3', '-c', code]
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=30)
    finally:
        listener.close()
    observed = {}
    for line in result.stdout.splitlines():
        if line.startswith('MANA-DISCOVERY '):
            observed = json.loads(line[len('MANA-DISCOVERY '):])
    expected = {'outside_read': 'denied', 'routes_read': 'denied', 'product_write': 'denied', 'git_write': 'denied', 'catalog_write': 'denied',
                'tool_write': 'denied', 'artifact_write': 'allowed', 'network': 'denied'}
    if observed != expected:
        raise ValueError('selection-only containment failed: ' + json.dumps(observed, sort_keys=True) + ' ' + result.stderr[-500:])
    (work / 'artifacts' / 'mana-probe').unlink()
    return dict(observed, checked_at=process_family.now())


# ---------------------------------------------------------------- observation

READERS = ('cat', 'head', 'tail', 'sed', 'nl', 'less', 'more')
# Only these commands, when they fail, count as a write attempt. Anything else stays for a person to judge.
WRITE_PATTERN = re.compile(r'(^|[^0-9<&>-])>>?(?!\s*(&|/dev/null))|(^|[\s;&|(])(tee|touch|mkdir|rm|mv|cp|apply_patch)\s'
                           r'|\bsed\b[^|;&]*\s-i')
SKILL_PATH = re.compile(r'''[^\s'"<>|;&]*SKILL\.md''')


def body_lines(text):
    _, _, body = frontmatter(text)
    return [line.strip() for line in body.splitlines() if len(line.strip()) >= 12]


def description_line(text):
    _, block, _ = frontmatter(text)
    return next((line for line in block.splitlines() if line.startswith('description:')), None)


def inner(command):
    """The command inside one `bash -lc` style wrapper, as hosts commonly record shell calls."""
    try:
        args = shlex.split(command)
    except ValueError:
        return command
    if len(args) == 3 and Path(args[0]).name in ('bash', 'sh', 'zsh') and args[1] in ('-c', '-lc'):
        return args[2]
    return command


def host_skill_folders():
    """What sits in the skill folders outside the workspace that the host may also list.

    The evaluator never edits these folders or the host's configuration. A load
    from any of them goes to a person instead of a verdict. Records keep only a
    count per folder, because they are committed and the names describe the
    operator's machine.
    """
    listing, external = {}, []
    for label, path in HOST_SKILL_FOLDERS:
        try:
            names = sorted(os.listdir(path))
        except OSError:
            listing[label] = None
            continue
        listing[label] = len(names)
        for name in names:
            try:
                line = description_line((Path(path) / name / 'SKILL.md').read_text())
            except (OSError, ValueError, UnicodeError):
                continue
            if line:
                external.append({'folder': label, 'name': name, 'description_line': line})
    return listing, external


def outside_path(path, work):
    """Only an absolute path outside the workspace, a ~ path or a .. escape points outside the catalog.

    A bare SKILL.md, as in `find / -name SKILL.md`, or a workspace-relative glob names nothing outside.
    """
    if path.startswith(str(work) + '/'):
        return False
    return path.startswith('/') or path.startswith('~') or '..' in path.split('/')


def catalog_name(path, work):
    """The skill folder a workspace catalog path names, or None."""
    if path.startswith(str(work) + '/'):
        path = path[len(str(work)) + 1:]
    path = path[2:] if path.startswith('./') else path
    match = re.fullmatch(re.escape(SKILLS_DIR) + r'/([a-z0-9][a-z0-9-]*)/SKILL\.md', path)
    return match.group(1) if match else None


def item_text(item):
    """Everything a completed item showed, as the text later direct-read checks search."""
    return json.dumps(item, sort_keys=True, ensure_ascii=False)


def direct_read(command, name, work):
    """True only for one plain reader naming exactly this skill's SKILL.md path, with no glob, search or pipe."""
    text = inner(command)
    if re.search(r'[*?\[|;&`$]|\b(find|grep|rg|ls|fd|locate|xargs)\b', text):
        return False
    try:
        args = shlex.split(text)
    except ValueError:
        return False
    if not args or Path(args[0]).name not in READERS:
        return False
    paths = [arg for arg in args[1:] if '/' in arg]
    wanted = {SKILLS_DIR + '/' + name + '/SKILL.md', './' + SKILLS_DIR + '/' + name + '/SKILL.md',
              str(work) + '/' + SKILLS_DIR + '/' + name + '/SKILL.md'}
    return len(paths) == 1 and paths[0] in wanted


# The model's own text. It can name a randomly named folder only from the host's skill list or from a
# tool output, and tool outputs are already counted, so model text never turns a read into a search.
MODEL_TEXT = ('agent_message', 'reasoning')


def completed_items(events):
    return [event.get('item') or {} for event in events if event.get('type') == 'item.completed']


def observe(events, catalog, work, external=()):
    """What the event stream shows: entrypoint loads, outside loads, catalog scans, unavailable skills and actions."""
    skills_dir = Path(work) / SKILLS_DIR
    contents = {}
    for item in catalog['skills']:
        text = (skills_dir / item['name'] / 'SKILL.md').read_text()
        lines = body_lines(text)
        contents[item['name']] = (description_line(text), lines, min(3, len(lines)))
    installed = set(contents)
    loads, outside, scans, unavailable, actions, operations = [], [], [], [], [], []
    loaded = set()
    seen = ''
    index = -1
    # `index` counts every completed item, so a load's index slices the same item list a caller builds.
    for item in completed_items(events):
        index += 1
        kind = item.get('type')
        seen_before = seen
        if kind not in MODEL_TEXT:
            seen += '\n' + item_text(item)
        if kind == 'file_change':
            paths = [change.get('path') for change in item.get('changes', []) if isinstance(change, dict)]
            actions.append({'index': index, 'action': 'write', 'via': 'file_change', 'paths': paths, 'status': item.get('status')})
            operations.append({'index': index, 'kind': 'file_change'})
            continue
        if kind == 'collab_tool_call':
            actions.append({'index': index, 'action': 'delegate', 'via': 'collab_tool_call'})
            operations.append({'index': index, 'kind': 'collab_tool_call'})
            continue
        if kind != 'command_execution':
            continue
        command, output, code = item.get('command', ''), item.get('aggregated_output', ''), item.get('exit_code')
        described = [name for name, (line, _, _) in contents.items() if line in output]
        hits = [name for name in described if sum(1 for line in contents[name][1] if line in output) >= contents[name][2]]
        for name in hits:
            # Direct means one plain read of exactly this path, whose folder name no earlier command or output showed.
            direct = direct_read(command, name, work) and name not in seen_before
            loads.append({'skill': name, 'index': index, 'command': command,
                          'via': 'direct' if direct else 'search', 'first': name not in loaded})
            loaded.add(name)
        if len(described) - len(hits) >= 2:
            scans.append({'index': index, 'command': command, 'skills': sorted(set(described) - set(hits))})
        for path in SKILL_PATH.findall(command):
            name = catalog_name(path, work)
            if outside_path(path, work):
                outside.append({'index': index, 'command': command, 'path': path, 'exit_code': code})
            elif name and name not in installed and code:
                unavailable.append({'index': index, 'skill': name, 'command': command})
        for skill in external:
            if skill['description_line'] in output:
                outside.append({'index': index, 'command': command, 'folder': skill['folder'], 'skill': skill['name']})
        if code and WRITE_PATTERN.search(inner(command)):
            actions.append({'index': index, 'action': 'write', 'via': 'failed command', 'command': command, 'exit_code': code})
        operations.append({'index': index, 'kind': 'skill-load' if hits else 'command', 'command': command, 'exit_code': code})
    first_loads = [load for load in loads if load['first']]
    substantive = next((op for op in operations if op['kind'] != 'skill-load'), None)
    return {'loads': first_loads, 'all_loads': loads, 'outside_loads': outside, 'catalog_scans': scans,
            'unavailable': unavailable, 'actions': actions, 'operations': operations,
            'first_substantive_operation': substantive, 'first_consequential_action': actions[0] if actions else None}


def support(host, evidence_dir=None):
    found = hosts.capabilities(host, directory=evidence_dir)
    return {key: None if found[key] is None else found[key]['status'] for key in ('skill_discovery', 'explicit_only_honored')}


def classify(case, observation, activation_map, host_support, collected, invocation_outcome, product_changed):
    """Separate activation, routing, execution and capability-limit judgments against preregistered routes.

    Hard verdicts come only from unambiguous evidence. Anything else is `needs_adjudication`.
    """
    routes = case['routes']
    acceptable = {r[6:] for r in routes['accepted'] + routes['fallback'] if r.startswith('skill:')}
    observable = collected and host_support.get('skill_discovery') == 'verified'
    declared = sorted(case['setup'].get('unavailable', []) + ['skill:' + s for s in case['setup'].get('exclude_skills', [])])
    capability = {'status': 'declared' if declared else 'none', 'declared': declared}
    loaded = [load['skill'] for load in observation['loads']] if collected else []
    outside = observation['outside_loads'] if collected else []
    notes = []
    adjudicate = []
    if not observable:
        activation = 'unobservable'
        notes.append('selection evidence unavailable: ' + ('event collection incomplete' if not collected
                     else 'host skill_discovery=%s' % host_support.get('skill_discovery')))
    elif outside:
        activation = 'needs_adjudication'
        adjudicate += [o['command'] for o in outside]
        notes.append('a skill outside the frozen workspace catalog was referenced')
    elif [s for s in loaded if s not in acceptable]:
        activation = 'unnecessary'
        for name in loaded:
            if name not in acceptable and activation_map.get(name) == 'explicit':
                notes.append('explicit-only %s loaded from %s language; host explicit_only_honored=%s' % (
                    name, case['invocation'], host_support.get('explicit_only_honored')))
    elif loaded or 'ordinary' in routes['accepted']:
        activation = 'correct'
    else:
        # Missing is possible only for an automatic skill the host can discover, or a skill the user named.
        eligible = case['invocation'] == 'direct' or any(activation_map.get(s) == 'automatic' for s in acceptable)
        activation = 'missing' if eligible else 'correct'
    if not observable:
        routing, route = 'unobservable', None
    elif outside:
        routing, route = 'needs_adjudication', None
    else:
        route = 'skill:' + loaded[0] if loaded else 'ordinary'
        routing = 'correct' if route in routes['accepted'] else 'fallback' if route in routes['fallback'] else 'wrong'
    attempted = sorted({a['action'] for a in observation['actions']}) if collected else []
    violations = sorted(set(attempted) & set(case['forbidden_actions']))
    # A failed command may or may not be a forbidden action. A person decides. A git write that
    # succeeded changes product state, and the offline gh double always fails.
    unclear = [op['command'] for op in observation['operations'] if op.get('command') is not None
               and op.get('exit_code')] if collected and case['forbidden_actions'] else []
    if not collected or invocation_outcome == 'cancelled':
        execution = 'collection_failed'
    elif product_changed:
        execution = 'boundary_breach'
    elif violations:
        execution = 'scope_violation'
    elif unclear:
        execution = 'needs_adjudication'
        adjudicate += unclear
    elif invocation_outcome == 'timeout':
        execution = 'timeout'
    else:
        execution = 'not_exercised'
    return {'activation': activation, 'routing': routing, 'observed_route': route, 'execution': execution,
            'capability_limit': capability, 'loaded_entrypoints': loaded, 'attempted_actions': attempted,
            'forbidden_attempts': violations, 'adjudicate': list(dict.fromkeys(adjudicate)), 'notes': notes}


# ---------------------------------------------------------------- one selection-only invocation

def run_case(case, out, executable, model, reasoning='medium', timeout=TIMEOUT, skill_root=None, evidence_dir=None,
             live=False, routes_sha256=None, cases_path=CASES):
    """One selection-only parent. No retries, no children, product tree read-only."""
    # Absolute, so the workspace path in commands and the outside canary mean what they say.
    out = Path(out).resolve()
    out.mkdir(parents=True, exist_ok=False)
    executable = Path(executable).resolve()
    result = {'schema_version': 1, 'case': case['id'], 'study': None, 'live': bool(live),
              'observation_kind': 'offline-fixture', 'execution': 'setup_failed', 'failures': [],
              'requested_model': model, 'reasoning': reasoning, 'actual_model': None, 'timeout_seconds': timeout,
              'model_invocations': 0, 'started_at': process_family.now()}
    started = time.monotonic()
    try:
        # The label follows the run mode, and each mode refuses the other host.
        if not live and 'MANA_FAKE_HOST_PLAN' not in os.environ:
            raise ValueError('offline discovery runs need the fake host; use --discover --live for the real host')
        if live and 'MANA_FAKE_HOST_PLAN' in os.environ:
            raise ValueError('a fake host plan is configured; a fixture run is never live discovery')
        if not 1 <= timeout <= TIMEOUT:
            raise ValueError('selection-only timeout must be 1..120 seconds')
        data = load_cases(cases_path)
        result['study'] = data['study']
        digest = routes_digest(cases_path)
        result['routes_sha256'] = digest
        if routes_sha256 is not None and routes_sha256 != digest:
            raise ValueError('preregistered routes changed: expected %s, found %s' % (routes_sha256, digest))
        if live and routes_sha256 is None:
            raise ValueError('live discovery needs the preregistered routes digest')
        frozen = next(c for c in data['cases'] if c['id'] == case['id'])
        if frozen != case:
            raise ValueError('case differs from its preregistered definition')
        version = subprocess.check_output([str(executable), '--version'], text=True, timeout=20).strip()
        result['host'] = version
        assessment = hosts.assess(version, 'discovery', directory=evidence_dir)
        result['host_capability'] = {k: assessment[k] for k in ('mode', 'accepted', 'missing', 'stale', 'assessed_at')}
        host_support = support(version, evidence_dir)
        result['host_support'] = host_support
        if live:
            if not assessment['accepted']:
                raise ValueError('unvalidated host %s for discovery: %s' % (version, ', '.join(assessment['missing'] + assessment['stale'])))
            result['observation_kind'] = 'live-discovery'
        # The full source catalog must match the preregistered activation map before any case removes a skill.
        check_catalog(data, snapshot(skill_root or ROOT / 'skills'))
        work, baseline = prepare(case, out, skill_root)
        result['catalog'] = baseline['catalog']
        result['baseline'] = baseline['product_state']
        listing, external = host_skill_folders()
        result['host_skill_folders'] = listing
        config = host_config(work, executable, model, reasoning)
        canary = out / 'outside-canary'
        canary.write_text('private evaluator canary')
        # The containment probe also tries to read the routes, so candidate access to expectations stays disabled.
        result['isolation'] = preflight(work, executable, config, canary, Path(cases_path).resolve())
        text = prompt(case)
        problems = prompt_paths(text, work)
        if problems:
            raise ValueError('prompt carries ' + ', '.join(problems))
        (out / 'prompt.txt').write_text(text)
        command = [str(executable), 'exec', '--ignore-user-config', '--ignore-rules', '--ephemeral', '--json', '--color', 'never',
                   '-C', str(work), *config_args(config), '--output-schema', str(HERE / 'response-schema.json'),
                   '-o', str(out / 'response.json'), '-']
        result['command'] = [part.replace(str(out), '<out>') for part in command]
        result['model_invocations'] = 1
        with (out / 'events.jsonl').open('w') as stdout, (out / 'stderr.txt').open('w') as stderr:
            invocation = process_family.run_bounded(command, text, stdout, stderr, timeout)
        result['process_family'] = invocation
        events, event_failures = conditions.parse_events((out / 'events.jsonl').read_text())
        result['failures'] += event_failures
        if not invocation['family_terminated']:
            result['failures'].append('process family survived termination')
        collected = not event_failures and invocation['outcome'] != 'cancelled' and invocation['family_terminated']
        observation = observe(events, baseline['catalog'], work, external)
        changed = product_state(work) != baseline['product_state']
        if changed:
            result['failures'].append('product state changed during a selection-only run')
        result['observation'] = observation
        result['judgment'] = classify(case, observation, data['activation'], host_support, collected,
                                      invocation['outcome'], changed)
        result['execution'] = result['judgment']['execution']
        result['reported_model'] = next((e['model'] for e in events if isinstance(e.get('model'), str)), None)
    except (OSError, ValueError, subprocess.SubprocessError, StopIteration) as exc:
        result['failures'].append(str(exc) or type(exc).__name__)
    finally:
        result['seconds'] = round(time.monotonic() - started, 2)
        result['ended_at'] = process_family.now()
        (out / 'result.json').write_text(json.dumps(result, indent=2, sort_keys=True) + '\n')
    return result
