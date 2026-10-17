#!/usr/bin/env bash
# Generate a project-owned control candidate without executing project code.
# inspect REPO
# map REPO --spec SPEC.json --out MAP.json
# install REPO --map MAP.json
# The first recipe covers one explicitly mapped briefing feature and Vitest JSON.
# Existing controls and changed source are preserved. Refresh is a separate workflow.
set -euo pipefail
case "${1:-}" in
  --help|-h)
    sed -n '2,7s/^# //p' "${BASH_SOURCE[0]}"
    exit 0 ;;
esac
command -v python3 >/dev/null 2>&1 || { echo 'generate.sh: python3 is required' >&2; exit 4; }
python3 - "${BASH_SOURCE[0]}" "$@" <<'PY'
import argparse, hashlib, json, os, re, shutil, signal, stat, subprocess, sys, tempfile
from pathlib import Path

SCRIPT = Path(sys.argv[1]).resolve()
SKILL = SCRIPT.parent.parent
FORMAT = 'mana-control-map/1'
GENERATOR = 'leyline-node/1'
RUNTIME = 'references/recipes/control.ts.template'
TEMPLATE = 'references/control-skill-template.md'
LEDGER = 'docs/agents/readiness.md'
ID = re.compile(r'^[a-z0-9][a-z0-9-]*$')
BINDING = re.compile(r'''[A-Za-z_$]*[sS]cenario\(\s*['"`]([^'"`]+)['"`]''')
RESULT_KEYS = {'status', 'result', 'results', 'passed', 'lastRun', 'verified', 'outcome'}


class Problem(Exception):
    pass


def fail(message):
    raise Problem(message)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def encode(value):
    return (json.dumps(value, indent=2, ensure_ascii=False) + '\n').encode()


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()


def read_json(path):
    try:
        value = json.loads(Path(path).read_text())
    except (OSError, ValueError) as exc:
        fail(f'cannot read JSON {path}: {exc}')
    if not isinstance(value, dict):
        fail(f'{path} must contain a JSON object')
    return value


def relative(root, value, exists=False):
    if not isinstance(value, str) or not value or '\\' in value:
        fail(f'invalid project-relative path: {value!r}')
    rel = Path(value)
    if rel.is_absolute() or '..' in rel.parts or '.git' in rel.parts or rel.as_posix() != value:
        fail(f'path must stay inside the project: {value!r}')
    path = root / rel
    try:
        path.resolve().relative_to(root)
    except ValueError:
        fail(f'path escapes the project: {value}')
    if exists and not path.exists():
        fail(f'missing mapped path: {value}')
    return path


def git(root, *args, required=True):
    env = {k: v for k, v in os.environ.items() if not k.startswith('GIT_')}
    try:
        result = subprocess.run(['git', '-C', str(root), *args], env=env, capture_output=True)
    except OSError as exc:
        if required:
            fail(f'git is required: {exc}')
        return None
    if result.returncode:
        if required:
            fail('cannot read project source identity: ' + result.stderr.decode(errors='replace').strip())
        return None
    return result.stdout


def file_state(path):
    if path.is_symlink():
        return {'kind': 'symlink', 'digest': digest(os.readlink(path).encode()), 'target': os.readlink(path)}
    if not path.exists():
        return None
    if not path.is_file():
        fail(f'expected a regular file: {path}')
    return {'kind': 'file', 'digest': digest(path.read_bytes()), 'mode': stat.S_IMODE(path.stat().st_mode)}


def source(root):
    top = git(root, 'rev-parse', '--show-toplevel').decode().strip()
    if Path(top).resolve() != root:
        fail('map/install requires the repository root')
    head = git(root, 'rev-parse', 'HEAD').decode().strip()
    names = git(root, 'ls-files', '-z', '--cached', '--others', '--exclude-standard').decode().split('\0')
    files = {}
    for name in sorted(set(filter(None, names))):
        path = relative(root, name)
        state = file_state(path)
        if state is not None:
            files[name] = state
    return {'head': head, 'manifest': {'digest': digest(canonical(files)), 'files': files}}


def generator_identity():
    files = {name: digest((SKILL / name).read_bytes()) for name in ('scripts/generate.sh', RUNTIME, TEMPLATE)}
    return {'id': GENERATOR, 'digest': digest(canonical(files)), 'files': files}


def inspect(root):
    agent_files, controls = [], []
    seen = set()
    for name in ('CLAUDE.md', 'AGENTS.md'):
        path = root / name
        if not path.is_file():
            continue
        relative(root, name, True)
        if path.resolve() in seen:
            continue
        seen.add(path.resolve())
        text = path.read_text()
        block = re.search(r'^## Agent skills[ \t]*$([\s\S]*?)(?=^## |\Z)', text, re.M)
        pointers = re.findall(r'^Control:[ \t]*(.+?)[ \t]*$', block[1], re.M) if block else []
        agent_files.append({'path': name, 'hasAgentSkills': bool(block), 'controls': pointers})
        controls += [{'agentFile': name, 'path': value.strip('`')} for value in pointers]
    package = read_json(root / 'package.json') if (root / 'package.json').is_file() else {}
    head = git(root, 'rev-parse', 'HEAD', required=False)
    return {'mode': 'inspect', 'executedProjectCode': False, 'root': str(root),
            'head': head.decode().strip() if head else None, 'agentFiles': agent_files,
            'controls': controls, 'packageScripts': package.get('scripts', {}),
            'recordDirectories': [p for p in ('verification/features', 'verification/scenarios') if (root / p).exists()],
            'capability': 'first-install ESM Node/Vitest adapter; existing controls require a focused manual adaptation'}


def argv(value, name, report=False):
    if not isinstance(value, dict) or not isinstance(value.get('argv'), list) or not value['argv']:
        fail(f'{name}.argv must be a nonempty argument array')
    if any(not isinstance(a, str) or not a or '\0' in a for a in value['argv']):
        fail(f'{name}.argv contains an invalid argument')
    if report and not any('{report}' in a for a in value['argv']):
        fail(f'{name}.argv must name the isolated output using {{report}}')


def validate_spec(root, spec):
    if not ID.fullmatch(spec.get('project', '')):
        fail('project must be a lowercase hyphenated name')
    feature = spec.get('feature', {})
    if not isinstance(feature, dict):
        fail('feature must be an object')
    if feature.get('id') != 'briefing':
        fail('this recipe maps the briefing feature; other recipes are not implemented')
    if feature.get('knowledge') != 'proposed':
        fail('generated feature knowledge must remain proposed')
    if not isinstance(feature.get('summary'), str) or not feature['summary'].strip():
        fail('feature.summary is required')
    if not isinstance(feature.get('aliases'), list) or not all(isinstance(x, str) for x in feature['aliases']):
        fail('feature.aliases must be a string array')
    roots = feature.get('sourceRoots')
    if not isinstance(roots, list) or not roots:
        fail('feature.sourceRoots must name the inspected source')
    for path in roots:
        relative(root, path, True)
    reach = feature.get('reach')
    if not isinstance(reach, list) or not reach or any(not isinstance(r, dict) or not any(r.get(k) for k in ('route', 'command', 'shortcut')) for r in reach):
        fail('feature.reach must explain how to reach the feature')
    scenarios = spec.get('scenarios')
    expected = {'briefing.return-summary', 'briefing.no-activity'}
    if not isinstance(scenarios, list) or {s.get('id') for s in scenarios if isinstance(s, dict)} != expected or len(scenarios) != 2:
        fail('this recipe requires briefing.return-summary and briefing.no-activity')
    for record in [feature, *scenarios]:
        if RESULT_KEYS.intersection(record):
            fail('feature/scenario records must not contain verification outcomes')
    for scenario in scenarios:
        steps = scenario.get('steps')
        if not isinstance(steps, list) or not steps or any(not isinstance(s, dict) or not isinstance(s.get('action'), str) or not s['action'].strip() or not isinstance(s.get('expect'), str) or not s['expect'].strip() for s in steps):
            fail(f"{scenario['id']} needs explicit action/expect steps")
    bindings = spec.get('bindings')
    if not isinstance(bindings, list) or not bindings:
        fail('bindings must name existing test files or directories')
    found = set()
    for name in bindings:
        path = relative(root, name, True)
        paths = [path] if path.is_file() else sorted(path.rglob('*'))
        for candidate in paths:
            if candidate.is_file() and candidate.suffix in {'.ts', '.tsx', '.js', '.mjs', '.cts', '.mts'}:
                relative(root, candidate.relative_to(root).as_posix(), True)
                found.update(BINDING.findall(candidate.read_text()))
    if found != expected:
        fail(f'literal scenario bindings must match the map; missing={sorted(expected-found)}, extra={sorted(found-expected)}')
    runner = spec.get('runner')
    argv(runner, 'runner', report=True)
    if runner.get('format') != 'vitest-json':
        fail('runner.format must be vitest-json')
    release = spec.get('release')
    if release is not None:
        argv(release, 'release', report=isinstance(release, dict) and release.get('format') == 'vitest-json')
        if release.get('format') not in ('vitest-json', 'exit'):
            fail('release.format must be vitest-json or exit')
    if spec.get('prepare') is not None:
        argv(spec['prepare'], 'prepare')
    prerequisites = spec.get('prerequisites', [])
    if not isinstance(prerequisites, list):
        fail('prerequisites must be an array')
    for need in prerequisites:
        if not isinstance(need, dict) or not isinstance(need.get('need'), str) or not need['need']:
            fail('each prerequisite needs a name')
        relative(root, need.get('path'))
    timeout = spec.get('timeoutSeconds', 60)
    if not isinstance(timeout, (int, float)) or isinstance(timeout, bool) or not 0 < timeout <= 3600:
        fail('timeoutSeconds must be positive and at most 3600')
    patch = spec.get('break', {})
    if not isinstance(patch, dict):
        fail('break must name a scenario and patch path')
    if patch.get('scenario') not in expected:
        fail('break.scenario must name a mapped scenario')
    patch_path = relative(root, patch.get('path'), True)
    if not patch_path.is_file() or not patch_path.read_text().startswith('diff --git '):
        fail('break.path must contain a git apply patch for the mapped behavior')
    git(root, 'apply', '--check', str(patch_path))


def root_guidance(root, info, spec):
    preferred = spec.get('rootAgentFile')
    if preferred is not None and preferred not in ('CLAUDE.md', 'AGENTS.md'):
        fail('rootAgentFile must be CLAUDE.md or AGENTS.md')
    entries = info['agentFiles']
    name = preferred or next((e['path'] for e in entries if e['hasAgentSkills']), entries[0]['path'] if entries else 'AGENTS.md')
    path = relative(root, name)
    return path.resolve().relative_to(root).as_posix()


def build_outputs(root, info, spec):
    if info['controls']:
        fail('an existing Control pointer is project-owned; adapt it rather than installing a competing control')
    package_path = root / 'package.json'
    package = read_json(package_path) if package_path.exists() else {'name': spec['project'], 'private': True, 'type': 'module'}
    if package.get('type') != 'module':
        fail('this TypeScript/Node recipe requires an ESM package (type: module); preserve the existing package and adapt it explicitly')
    scripts = package.setdefault('scripts', {})
    if not isinstance(scripts, dict):
        fail('package.json scripts must be an object')
    if 'verify' in scripts:
        fail('package.json already has verify; preserve it and adapt the existing verifier')
    scripts['verify'] = 'node --experimental-strip-types scripts/control.ts'
    skill_path = f"skills/{spec['project']}-control/SKILL.md"
    agent_path = root_guidance(root, info, spec)
    old_guidance = (root / agent_path).read_text() if (root / agent_path).exists() else ''
    pointer = 'Control: ' + skill_path
    header = re.search(r'^## Agent skills[ \t]*$', old_guidance, re.M)
    if header:
        guidance = old_guidance[:header.end()] + '\n\n' + pointer + old_guidance[header.end():]
    else:
        guidance = old_guidance + ('\n' if old_guidance.endswith('\n') else '\n\n' if old_guidance else '') + '## Agent skills\n\n' + pointer + '\n'
    template = (SKILL / TEMPLATE).read_text()
    skill = template.replace('{{PROJECT}}', spec['project']).replace('{{BINDINGS}}', ', '.join(spec['bindings']))
    config = {key: spec[key] for key in ('bindings', 'runner', 'prerequisites', 'release', 'prepare', 'timeoutSeconds', 'evidenceDir') if key in spec}
    config.update(feature='briefing', sourceRoots=spec['feature']['sourceRoots'],
                  featuresDir='verification/features', scenariosDir='verification/scenarios')
    config.setdefault('prerequisites', [])
    config.setdefault('release', None)
    config.setdefault('timeoutSeconds', 60)
    texts = {'scripts/control.ts': (SKILL / RUNTIME).read_text(),
             'scripts/control-config.json': encode(config).decode(), skill_path: skill,
             'verification/features/briefing.json': encode(spec['feature']).decode(),
             'package.json': encode(package).decode(), agent_path: guidance,
             f"verification/breaks/{spec['break']['scenario']}.patch": relative(root, spec['break']['path']).read_text()}
    for scenario in spec['scenarios']:
        texts[f"verification/scenarios/briefing/{scenario['id'].split('.', 1)[1]}.json"] = encode(scenario).decode()
    outputs = {}
    for name, text in texts.items():
        path = relative(root, name)
        before = file_state(path)
        if before is not None and name not in (agent_path, 'package.json'):
            fail(f'existing project-owned output must be preserved: {name}')
        outputs[name] = {'before': before, 'text': text, 'digest': digest(text.encode()),
                         'ownership': 'Control line' if name == agent_path else 'scripts.verify' if name == 'package.json' else 'project-owned after installation'}
    return outputs


def output_path(path, root):
    path = Path(path).resolve()
    if path == root or root in path.parents:
        fail('keep the review map outside the target checkout so it cannot change its own source identity')
    return path


def write_map(root, args):
    spec = read_json(args.spec)
    validate_spec(root, spec)
    info = inspect(root)
    outputs = build_outputs(root, info, spec)
    ledger_path = relative(root, LEDGER)
    ledger_base = ledger_path.read_text() if ledger_path.exists() else '# Project readiness\n'
    plan = {'format': FORMAT, 'contract': 'control/0', 'state': 'candidate', 'generator': generator_identity(),
            'source': source(root), 'spec': spec, 'outputs': outputs,
            'ledger': {'before': file_state(ledger_path), 'text': ledger_base}}
    plan['mapDigest'] = digest(canonical(plan))
    target = output_path(args.out, root)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(encode(plan))
    return {'mode': 'map', 'state': 'candidate', 'map': str(target), 'mapDigest': plan['mapDigest'],
            'source': {'head': plan['source']['head'], 'digest': plan['source']['manifest']['digest']},
            'paths': sorted([*outputs, LEDGER]), 'executedProjectCode': False}


def ledger_output(plan):
    record = {'generator': plan['generator'], 'mapDigest': plan['mapDigest'], 'state': 'candidate',
              'source': {'head': plan['source']['head'], 'manifestDigest': plan['source']['manifest']['digest']},
              'installedFiles': {name: {'digest': item['digest'], 'ownership': item['ownership']} for name, item in sorted(plan['outputs'].items())},
              'knowledge': {'briefing': 'proposed'}, 'challengeRunIds': [],
              'pending': ['Run static and dynamic conformance from committed candidate bytes.',
                          'Retain prerequisite, source-change, teardown and cold-session evidence for the actual consumer.',
                          'This installation has no consumer readiness or performance claim.']}
    text = plan['ledger']['text']
    text += ('\n' if text.endswith('\n') else '\n\n') + f"<!-- leyline-install:{plan['mapDigest']} -->\n"
    text += '## Control installation candidate\n\n```json\n' + encode(record).decode() + '```\n'
    return {'before': plan['ledger']['before'], 'text': text, 'digest': digest(text.encode()), 'ownership': 'append-only installation record'}


def install(root, args):
    plan = read_json(args.map)
    claimed = plan.pop('mapDigest', None)
    if plan.get('format') != FORMAT or digest(canonical(plan)) != claimed:
        fail('map format or digest is invalid; regenerate the review map')
    plan['mapDigest'] = claimed
    if plan.get('generator') != generator_identity():
        fail('generator/template bytes changed; regenerate and review the map')
    outputs = dict(plan['outputs'])
    outputs[LEDGER] = ledger_output(plan)
    for name in outputs:
        path = relative(root, name)
        if any(parent.is_symlink() for parent in [path, *path.parents] if parent != root and root in parent.parents):
            fail(f'output path crosses a symlink: {name}')
    if all(file_state(root / name) is not None and file_state(root / name).get('digest') == item['digest'] for name, item in outputs.items()):
        return {'mode': 'install', 'state': 'unchanged', 'mapDigest': claimed, 'paths': sorted(outputs), 'executedProjectCode': False}
    if source(root) != plan['source']:
        fail('source changed since map generation; preserve the checkout and regenerate the candidate')
    validate_spec(root, plan['spec'])
    if build_outputs(root, inspect(root), plan['spec']) != plan['outputs']:
        fail('candidate contents differ from the declared recipe; regenerate the review map')
    ledger_path = relative(root, LEDGER)
    ledger_base = {'before': file_state(ledger_path), 'text': ledger_path.read_text() if ledger_path.exists() else '# Project readiness\n'}
    if ledger_base != plan['ledger']:
        fail('ledger base differs from the project; preserve its current content')
    for name, item in outputs.items():
        if file_state(root / name) != item['before']:
            fail(f'ownership conflict at {name}; preserve the existing bytes')
    # Static-check the complete candidate before writing any project file.
    with tempfile.TemporaryDirectory(prefix='leyline-candidate-') as temporary:
        candidate = Path(temporary)
        for name, state in plan['source']['manifest']['files'].items():
            target = candidate / name
            target.parent.mkdir(parents=True, exist_ok=True)
            if state['kind'] == 'symlink':
                target.symlink_to(state['target'])
            else:
                shutil.copyfile(root / name, target)
        for name, item in outputs.items():
            target = candidate / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(item['text'])
        check = subprocess.run(['bash', str(SKILL / 'scripts/conform.sh'), 'static', str(candidate)], capture_output=True, text=True)
        if check.returncode:
            fail('generated candidate failed static conformance: ' + check.stdout + check.stderr)
    if source(root) != plan['source']:
        fail('source changed while checking the candidate; nothing was installed')
    writes, created_dirs = [], []
    def inode(path):
        try:
            value = os.lstat(path)
            return (value.st_dev, value.st_ino)
        except FileNotFoundError:
            return None
    def interrupted(signum, _frame):
        raise InterruptedError(f'installation interrupted by {signal.Signals(signum).name}; rolling back owned writes')
    handlers = {signum: signal.signal(signum, interrupted) for signum in (signal.SIGINT, signal.SIGTERM)}
    try:
        # Activate package command and discovery only after their targets exist.
        priority = {'scripts.verify': 1, 'Control line': 2, 'append-only installation record': 3}
        order = sorted(outputs, key=lambda name: (priority.get(outputs[name]['ownership'], 0), name))
        for name in order:
            item, path = outputs[name], root / name
            if file_state(path) != item['before']:
                fail(f'ownership changed during installation: {name}')
            missing = []
            parent = path.parent
            while parent != root and not parent.exists():
                missing.append(parent)
                parent = parent.parent
            for parent in reversed(missing):
                parent.mkdir()
                created_dirs.append(parent)
            staged = None
            try:
                with tempfile.NamedTemporaryFile(prefix='.leyline-stage-', dir=path.parent, delete=False) as stage:
                    staged = Path(stage.name)
                    stage.write(item['text'].encode())
                    stage.flush()
                    os.fsync(stage.fileno())
                os.chmod(staged, item['before']['mode'] if item['before'] else 0o644)
                # Record the staged inode before publishing. A failed exclusive
                # link must never claim another writer's identical contents.
                write = {'name': name, 'inode': inode(staged), 'backup': None, 'placeholder': None}
                writes.append(write)
                if item['before'] is not None:
                    with tempfile.NamedTemporaryFile(prefix='.leyline-recovery-', dir=path.parent, delete=False) as backup:
                        write['backup'] = Path(backup.name)
                        write['placeholder'] = inode(write['backup'])
                    # Move, then inspect the actual displaced bytes. Checking
                    # before a destructive replacement has a lost-update race.
                    os.replace(path, write['backup'])
                    if file_state(write['backup']) != item['before']:
                        fail(f'ownership changed before publication: {name}')
                os.link(staged, path)  # Exclusive, including replacement files.
            finally:
                if staged is not None:
                    staged.unlink(missing_ok=True)
        for write in writes:
            backup = write['backup']
            if backup is not None and file_state(backup) != outputs[write['name']]['before']:
                fail(f'displaced source changed during installation: {write["name"]}')
    except BaseException:
        for signum in handlers:
            signal.signal(signum, signal.SIG_IGN)
        for write in reversed(writes):
            name, backup = write['name'], write['backup']
            path = root / name
            if inode(path) == write['inode'] and (file_state(path) or {}).get('digest') == outputs[name]['digest']:
                path.unlink()
            if backup is not None and backup.exists():
                if inode(backup) == write['placeholder']:
                    backup.unlink()  # The original was never displaced.
                else:
                    try:
                        os.link(backup, path)
                    except FileExistsError:
                        print(f'generate.sh: concurrent bytes preserved at {path}; displaced bytes retained at {backup}', file=sys.stderr)
                    else:
                        backup.unlink()
        for path in reversed(created_dirs):
            try:
                path.rmdir()
            except OSError:
                pass
        raise
    else:
        # All outputs are committed. Handled signals during backup cleanup must
        # not initiate a rollback after an earlier backup has been removed.
        for signum in handlers:
            signal.signal(signum, signal.SIG_IGN)
        for write in writes:
            if write['backup'] is not None:
                try:
                    write['backup'].unlink()
                except OSError as exc:
                    print(f'generate.sh: installed; retained recovery file {write["backup"]}: {exc}', file=sys.stderr)
    finally:
        for signum, handler in handlers.items():
            signal.signal(signum, handler)
    return {'mode': 'install', 'state': 'candidate', 'mapDigest': claimed, 'paths': sorted(outputs),
            'staticConformant': True, 'executedProjectCode': False,
            'next': 'Commit the candidate for HEAD-based dynamic conformance; execute and retain actual challenge reports before claiming readiness.'}


parser = argparse.ArgumentParser(description='Inspect, map and install a project-owned control candidate.')
sub = parser.add_subparsers(dest='mode', required=True)
for name in ('inspect', 'map', 'install'):
    command = sub.add_parser(name)
    command.add_argument('repo')
    if name == 'map':
        command.add_argument('--spec', required=True)
        command.add_argument('--out', required=True)
    if name == 'install':
        command.add_argument('--map', required=True)
args = parser.parse_args(sys.argv[2:])
try:
    root = Path(args.repo).resolve(strict=True)
    if not root.is_dir():
        fail('repository must be a directory')
    result = inspect(root) if args.mode == 'inspect' else write_map(root, args) if args.mode == 'map' else install(root, args)
    print(json.dumps(result, indent=2))
except (Problem, OSError, UnicodeError, KeyError, TypeError, ValueError) as exc:
    print('generate.sh: ' + str(exc), file=sys.stderr)
    sys.exit(1)
PY
