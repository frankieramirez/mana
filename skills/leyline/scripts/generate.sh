#!/usr/bin/env bash
# Generate a project-owned control candidate without executing project code.
# inspect REPO
# map REPO --spec SPEC.json --out MAP.json
# install REPO --map MAP.json
# refresh REPO [--out CANDIDATE.json] [--map MAP.json] [--challenge EVIDENCE_DIR]
# refresh REPO --apply CANDIDATE.json
# The first recipe covers one explicitly mapped briefing feature and Vitest JSON.
# Existing controls and changed source are preserved. Refresh reconciles an installed
# control from its ledger: focused edits for proven drift, named findings for the rest.
set -euo pipefail
case "${1:-}" in
  --help|-h)
    sed -n '2,10s/^# //p' "${BASH_SOURCE[0]}"
    exit 0 ;;
esac
command -v python3 >/dev/null 2>&1 || { echo 'generate.sh: python3 is required' >&2; exit 4; }
python3 - "${BASH_SOURCE[0]}" "$@" <<'PY'
import argparse, difflib, hashlib, json, os, re, shutil, signal, stat, subprocess, sys, tempfile
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


def git_blob(data):
    return hashlib.sha1(b'blob %d\0' % len(data) + data).hexdigest()


BEGIN_MARK = '<!-- BEGIN GENERATED CONTROL DISCOVERY -->'
END_MARK = '<!-- END GENERATED CONTROL DISCOVERY -->'


def managed_block(text):
    """The marked discovery block, markers included, or None when it is absent or ambiguous."""
    if text.count(BEGIN_MARK) != 1 or text.count(END_MARK) != 1:
        return None
    start, end = text.index(BEGIN_MARK), text.index(END_MARK)
    return text[start:end + len(END_MARK)] if start < end else None


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
        if ('path' in need) == ('probe' in need):
            fail('each prerequisite names exactly one path or probe command')
        if 'path' in need:
            relative(root, need.get('path'))
        else:
            argv(need['probe'], f"prerequisite {need['need']} probe")
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


def installed_files(plan):
    # Blob ids let refresh recover installed base bytes once the candidate is committed.
    files = {}
    for name, item in sorted(plan['outputs'].items()):
        entry = {'digest': item['digest'], 'blob': git_blob(item['text'].encode()), 'ownership': item['ownership']}
        if name == 'scripts/control.ts':
            entry['templateDigest'] = plan['generator']['files'][RUNTIME]
        elif name.startswith('skills/') and name.endswith('-control/SKILL.md'):
            entry['templateDigest'] = plan['generator']['files'][TEMPLATE]
        files[name] = entry
    return files


def managed_blocks(plan):
    blocks = {}
    for name, item in plan['outputs'].items():
        block = managed_block(item['text'])
        if name.startswith('skills/') and block is not None:
            blocks[name] = block
    return blocks


def ledger_output(plan):
    record = {'generator': plan['generator'], 'mapDigest': plan['mapDigest'], 'state': 'candidate',
              'source': {'head': plan['source']['head'], 'manifestDigest': plan['source']['manifest']['digest']},
              'installedFiles': installed_files(plan),
              'managed': managed_blocks(plan),
              'knowledge': {'briefing': 'proposed'}, 'challengeRunIds': [],
              'pending': ['Run static and dynamic conformance from committed candidate bytes.',
                          'Retain prerequisite, source-change, teardown and cold-session evidence for the actual consumer.',
                          'This installation has no consumer readiness or performance claim.']}
    text = plan['ledger']['text']
    text += ('\n' if text.endswith('\n') else '\n\n') + f"<!-- leyline-install:{plan['mapDigest']} -->\n"
    text += '## Control installation candidate\n\n```json\n' + encode(record).decode() + '```\n'
    return {'before': plan['ledger']['before'], 'text': text, 'digest': digest(text.encode()), 'ownership': 'append-only installation record'}


def check_candidate(root, plan, outputs):
    """Static-check the complete candidate before writing any project file."""
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


def publish(root, outputs):
    """Write outputs whose current state is item['before']; roll back owned writes on failure."""
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
        priority = {'scripts.verify': 1, 'Control line': 2, 'append-only installation record': 3, 'append-only refresh record': 3}
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
    check_candidate(root, plan, outputs)
    if source(root) != plan['source']:
        fail('source changed while checking the candidate; nothing was installed')
    publish(root, outputs)
    return {'mode': 'install', 'state': 'candidate', 'mapDigest': claimed, 'paths': sorted(outputs),
            'staticConformant': True, 'executedProjectCode': False,
            'next': 'Commit the candidate for HEAD-based dynamic conformance; execute and retain actual challenge reports before claiming readiness.'}


# Refresh -----------------------------------------------------------------------
# Refresh reads the ledger, the checkout and optional retained challenge evidence.
# It never executes project code. It proposes focused edits to generator-owned
# values and the marked discovery block, and names everything it cannot decide.
REFRESH = 'mana-control-refresh/1'
CONFIG = 'scripts/control-config.json'
RUNTIME_PATH = 'scripts/control.ts'
LAUNCH = '.claude/launch.json'
RECORD = re.compile(r'<!-- leyline-(install|refresh):([0-9a-f]{64}) -->\n## [^\n]*\n\n```json\n(.*?)```\n', re.S)
ROUTE = re.compile(r'''['"`](/[A-Za-z0-9._~:/-]*)(?=['"`?#])''')
PORT = re.compile(r'(?i)(?:\bport\s+|\blocalhost:|\b127\.0\.0\.1:|\b0\.0\.0\.0:)(\d{2,5})\b')
SKILL_PATH = re.compile(r'^skills/([a-z0-9][a-z0-9-]*)-control/SKILL\.md$')
RANK = {'unchanged': 0, 'verified': 1, 'unverified': 2, 'unresolved': 3, 'candidate': 4, 'failed': 5, 'conflict': 6, 'partial': 7}


def is_recovery(name):
    return Path(name).name.startswith(('.leyline-stage-', '.leyline-recovery-'))


def plain_path(value):
    if not isinstance(value, str) or not value or '\\' in value or '{' in value or value.startswith('-'):
        return False
    rel = Path(value)
    return not rel.is_absolute() and '..' not in rel.parts and '.git' not in rel.parts and rel.as_posix() == value


def strings(value, pointer=()):
    if isinstance(value, str):
        yield pointer, value
    elif isinstance(value, dict):
        for key in sorted(value):
            yield from strings(value[key], pointer + (key,))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            yield from strings(item, pointer + (index,))


def json_edit(text, changes):
    """Apply value changes without reformatting human bytes, or return None."""
    try:
        before = json.loads(text)
        value = json.loads(text)
        for pointer, old, new in changes:
            parent = value
            for key in pointer[:-1]:
                parent = parent[key]
            if parent[pointer[-1]] != old:
                return None
            parent[pointer[-1]] = new
    except (ValueError, KeyError, IndexError, TypeError):
        return None
    if encode(before).decode() == text:
        return encode(value).decode()
    counts = {}
    for _pointer, old, new in changes:
        counts[(old, new)] = counts.get((old, new), 0) + 1
    out = text
    for (old, new), count in counts.items():
        literal = json.dumps(old, ensure_ascii=False)
        if out.count(literal) != count:
            return None
        out = out.replace(literal, json.dumps(new, ensure_ascii=False))
    try:
        return out if json.loads(out) == value else None
    except ValueError:
        return None


def read_ledger(root):
    path = root / LEDGER
    if not path.is_file():
        return []
    records = []
    for kind, mark, body in RECORD.findall(path.read_text()):
        try:
            value = json.loads(body)
        except ValueError:
            fail(f'{LEDGER} has an unreadable {kind} record {mark}; repair it before refreshing')
        if not isinstance(value, dict):
            fail(f'{LEDGER} record {mark} is not a JSON object')
        records.append({'kind': kind, 'mark': mark, 'record': value})
    return records


class Tree:
    """Blob ids of one commit, read through the version control CLI without checking anything out."""

    def __init__(self, root, commit):
        self.root, self.commit, self.blobs = root, commit, {}
        out = git(root, 'ls-tree', '-r', '-z', '--full-tree', commit, required=False) if commit else None
        self.available = out is not None
        for entry in (out or b'').decode(errors='replace').split('\0'):
            if entry:
                meta, name = entry.split('\t', 1)
                parts = meta.split()
                if parts[1] == 'blob':
                    self.blobs[name] = parts[2]

    def has(self, name):
        return name in self.blobs or any(n.startswith(name + '/') for n in self.blobs)

    def under(self, name):
        if name in self.blobs:
            return {'': self.blobs[name]}
        prefix = name + '/'
        return {n[len(prefix):]: b for n, b in self.blobs.items() if n.startswith(prefix)}

    def text(self, name):
        data = git(self.root, 'show', f'{self.commit}:{name}', required=False)
        try:
            return data.decode() if data is not None else None
        except UnicodeDecodeError:
            return None


def challenge_observation(root, path):
    evidence = Path(path).resolve(strict=True)
    if evidence == root or root in evidence.parents:
        fail('challenge evidence must stay outside the checkout')
    manifest = read_json(evidence / 'manifest.json')
    files = manifest.get('files')
    mismatched = []
    if not isinstance(files, list) or digest(json.dumps(files, sort_keys=True).encode()) != manifest.get('digest'):
        mismatched.append('manifest.json')
        files = files if isinstance(files, list) else []
    listed = set()
    for item in files:
        name = item.get('path') if isinstance(item, dict) else None
        target = evidence / name if isinstance(name, str) and plain_path(name) else None
        listed.add(name)
        if target is None or not target.is_file() or digest(target.read_bytes()) != item.get('sha256'):
            mismatched.append(str(name))
    if 'challenge.json' not in listed:
        mismatched.append('challenge.json (not in the manifest)')
    doc = read_json(evidence / 'challenge.json') if (evidence / 'challenge.json').is_file() else {}
    probes = doc.get('probes') if isinstance(doc.get('probes'), list) else []
    states = {p.get('status') for p in probes if isinstance(p, dict)}
    outcome = 'interrupted' if doc.get('interrupted') else 'failed' if 'failed' in states else 'incomplete' if states - {'passed'} or not states else 'passed'
    result = evidence / 'result.json'
    if result.is_file():
        final = read_json(result)
        # result.json is written after the manifest, so it can only lower the outcome.
        if final.get('outcome') != 'passed' or not (final.get('retained') or {}).get('verifiedAfterCleanup'):
            if outcome == 'passed':
                outcome = final.get('outcome') if final.get('outcome') in ('failed', 'incomplete', 'interrupted') else 'failed'
    else:
        outcome = outcome if outcome != 'passed' else 'incomplete'
    run_ids = sorted({r.get('runId') for p in probes if isinstance(p, dict) for r in p.get('runs') or [] if isinstance(r, dict) and isinstance(r.get('runId'), str)})
    head = (doc.get('source') or {}).get('head') if isinstance(doc.get('source'), dict) else None
    current = git(root, 'rev-parse', 'HEAD').decode().strip()
    status = git(root, 'status', '--porcelain', '-z', '--untracked-files=all').decode().split('\0')
    dirty = sorted(entry[3:] for entry in status if entry and entry[3:] != LEDGER and not is_recovery(entry[3:]))
    relevance = 'current' if head == current and not dirty else 'stale'
    return {'outcome': outcome, 'head': head, 'feature': doc.get('feature'), 'runIds': run_ids,
            'probes': {p.get('probe'): p.get('status') for p in probes if isinstance(p, dict)},
            'evidence': {'dir': str(evidence), 'manifestDigest': manifest.get('digest'), 'verified': not mismatched,
                         'mismatched': sorted(set(mismatched))[:20]},
            'relevance': relevance, 'uncommitted': dirty[:20]}


class Refresh:
    def __init__(self, root, map_path=None, challenge_path=None):
        self.root = root
        self.inputs = {'map': str(Path(map_path).resolve()) if map_path else None,
                       'challenge': str(Path(challenge_path).resolve()) if challenge_path else None}
        self.findings = {}
        self.json_changes = {}
        self.text_edits = {}
        self.renames = {}
        self.not_checked = []
        self.facts = {}
        self.source = source(root)
        self.files = self.source['manifest']['files']
        self._blobs = {}

    # Bookkeeping ---------------------------------------------------------------
    def add(self, kind, subject, severity, detail, paths=(), resolution=None, evidence=None):
        key = f'{kind}:{subject}'
        self.findings[key] = {'id': key, 'kind': kind, 'severity': severity, 'detail': detail,
                              'paths': sorted(set(paths)), 'resolution': resolution, 'evidence': evidence or {}}
        return key

    def change(self, path, pointer, old, new, finding):
        self.json_changes.setdefault(path, []).append((tuple(pointer), old, new, finding))

    def text(self, name):
        try:
            return (self.root / name).read_text()
        except (OSError, UnicodeDecodeError):
            return None

    def exists(self, name):
        return (self.root / name).exists() or (self.root / name).is_symlink()

    def blob(self, name):
        if name not in self._blobs:
            state = self.files.get(name)
            self._blobs[name] = git_blob((self.root / name).read_bytes()) if state and state['kind'] == 'file' else None
        return self._blobs[name]

    def current_under(self, name):
        if name in self.files:
            return [name]
        return sorted(n for n in self.files if n.startswith(name + '/') and not is_recovery(n))

    # Renames ---------------------------------------------------------------------
    def find_rename(self, old):
        """A unique exact-content rename since HEAD or the generation base, or the reasons there is none."""
        tree = self.head_tree if self.head_tree.has(old) else self.base_tree if self.base_tree.has(old) else None
        if tree is None:
            return None, [], 'the path is in neither HEAD nor the generation base, so no rename can be proven'
        entries = tree.under(old)
        candidates = []
        if '' in entries:
            candidates = [n for n in self.files if not is_recovery(n) and n != old and not tree.has(n) and self.blob(n) == entries['']]
        elif entries:
            first, blob = sorted(entries.items())[0]
            for name in self.files:
                if name.endswith('/' + first) and self.blob(name) == blob:
                    folder = name[:-len(first) - 1]
                    present = self.current_under(folder)
                    if folder != old and not tree.has(folder) and len(present) == len(entries) and all(
                            self.blob(f'{folder}/{rel}') == b for rel, b in entries.items()):
                        candidates.append(folder)
        candidates = sorted(set(candidates))
        if len(candidates) == 1:
            return candidates[0], candidates, f'identical content now lives only at {candidates[0]}'
        hints = []
        status = git(self.root, 'diff', '-M', '--name-status', '-z', tree.commit, required=False)
        fields = (status or b'').decode(errors='replace').split('\0')
        i = 0
        while i < len(fields):
            code = fields[i]
            if code.startswith(('R', 'C')) and i + 2 < len(fields):
                if fields[i + 1] == old or fields[i + 1].startswith(old + '/'):
                    hints.append({'similarity': code, 'from': fields[i + 1], 'to': fields[i + 2]})
                i += 3
            else:
                i += 2 if code else 1
        reason = 'several paths hold identical content' if candidates else 'no path holds identical content'
        return None, candidates + [h['to'] for h in hints[:5]], reason

    # Analysis --------------------------------------------------------------------
    def run(self):
        records = read_ledger(self.root)
        self.records = records
        recovery = [n for n in self.files if is_recovery(n)]
        result = {'format': REFRESH, 'contract': 'control/0', 'inputs': self.inputs, 'generator': generator_identity(),
                  'source': {'head': self.source['head'], 'manifestDigest': self.source['manifest']['digest']},
                  'executedProjectCode': False}
        installs = [r for r in records if r['kind'] == 'install']
        plan = None
        if self.inputs['map']:
            plan = read_json(self.inputs['map'])
            claimed = plan.pop('mapDigest', None)
            if plan.get('format') != FORMAT or digest(canonical(plan)) != claimed:
                fail('map format or digest is invalid; it cannot describe an interrupted installation')
            plan['mapDigest'] = claimed
            if not any(r['mark'] == claimed for r in installs):
                return self.partial(result, plan, recovery)
            result['mapRecorded'] = claimed
        if recovery:
            self.recovery_finding(recovery, {})
        if not installs:
            self.add('ownership', 'base-missing', 'conflict',
                     f'{LEDGER} has no installation record, so generated and human bytes cannot be told apart. '
                     'Refresh edits nothing. Pass the installation map with --map to inspect an interrupted installation.',
                     [LEDGER])
            return self.finish(result, None, records)
        install = installs[-1]['record']
        last = records[-1]['record']
        self.installed = last.get('installedFiles') or {}
        self.managed = last.get('managed') or {}
        self.origins = dict(last.get('origins') or {})
        self.generation_head = (install.get('source') or {}).get('head')
        self.head_tree = Tree(self.root, self.source['head'])
        self.base_tree = Tree(self.root, self.generation_head)
        if not self.base_tree.available:
            self.not_checked.append(f'generation base {self.generation_head} is not readable; route drift and base renames were not checked')
        self.config = self.load_json(CONFIG, 'config')
        controls = inspect(self.root)['controls']
        self.skill_path = self.check_pointer(controls)
        features = self.load_features()
        self.check_paths(features)
        self.check_features(features)
        self.check_routes(features)
        self.check_bindings(features)
        self.check_breaks()
        self.check_managed()
        self.check_runtime(install)
        self.check_command()
        self.check_ports()
        self.features = features
        challenge = challenge_observation(self.root, self.inputs['challenge']) if self.inputs['challenge'] else None
        return self.finish(result, challenge, records)

    def load_json(self, name, label):
        if not (self.root / name).is_file():
            self.add(f'{label}-missing', name, 'needs_adjudication', f'{name} is absent; its checks were skipped and nothing is recreated', [name])
            return None
        try:
            value = json.loads((self.root / name).read_text())
        except (ValueError, UnicodeDecodeError) as exc:
            self.add(f'{label}-unreadable', name, 'needs_adjudication', f'{name} is not valid JSON: {exc}', [name])
            return None
        return value if isinstance(value, dict) else None

    def load_features(self):
        folder = (self.config or {}).get('featuresDir', 'verification/features')
        features = {}
        if not plain_path(folder):
            return features
        for path in sorted((self.root / folder).glob('*.json')):
            name = path.relative_to(self.root).as_posix()
            record = self.load_json(name, 'feature')
            if record is not None:
                features[name] = record
        return features

    def confirmed(self, record):
        if record.get('knowledge') != 'confirmed':
            return {}
        folder = (self.config or {}).get('scenariosDir', 'verification/scenarios')
        scenarios = {}
        for path in sorted((self.root / folder / str(record.get('id'))).glob('*.json')):
            try:
                value = json.loads(path.read_text())
                scenarios[value.get('id')] = value.get('steps')
            except (ValueError, OSError, AttributeError):
                continue
        return {'confirmedIntent': {'feature': record.get('id'), 'summary': record.get('summary'), 'scenarios': scenarios,
                                    'note': 'confirmed intent survives; refresh never edits it'}}

    def check_pointer(self, controls):
        if len(controls) > 1:
            self.add('pointer-multiple', 'control', 'needs_adjudication', 'more than one Control pointer exists; refresh never picks one',
                     [c['agentFile'] for c in controls])
        if not controls:
            self.add('pointer-missing', 'control', 'needs_adjudication', 'no Control pointer exists; refresh does not recreate one')
            names = [n for n in self.installed if SKILL_PATH.match(n)]
            return names[0] if len(names) == 1 else None
        target = controls[0]['path']
        if plain_path(target) and not self.exists(target):
            new, candidates, reason = self.find_rename(target)
            agent = controls[0]['agentFile']
            old_line = f'Control: {target}'
            text = self.text(agent) or ''
            if new and text.count(old_line) == 1:
                key = self.add('pointer-renamed', target, 'proposed', f'the Control target moved: {reason}', [agent],
                               {'replace': old_line, 'with': f'Control: {new}'})
                self.text_edits[agent] = (text.replace(old_line, f'Control: {new}'), key)
                return new
            self.add('pointer-dangling', target, 'needs_adjudication', f'the Control target is missing: {reason}', [agent],
                     evidence={'candidates': candidates})
        return target if plain_path(target) else None

    def check_paths(self, features):
        refs = {}
        for name, record in features.items():
            for index, value in enumerate(record.get('sourceRoots') or []):
                if isinstance(value, str):
                    refs.setdefault(value, []).append((name, ('sourceRoots', index), True))
        if self.config is not None:
            for pointer, value in strings(self.config):
                if pointer and pointer[0] in ('feature', 'featuresDir', 'scenariosDir', 'evidenceDir', 'format'):
                    continue
                if plain_path(value) and (self.exists(value) or self.head_tree.has(value) or self.base_tree.has(value)):
                    refs.setdefault(value, []).append((CONFIG, pointer, False))
        for value in sorted(refs):
            if not plain_path(value) or self.exists(value):
                continue
            new, candidates, reason = self.find_rename(value)
            files = sorted({ref[0] for ref in refs[value]})
            source_root = any(ref[2] for ref in refs[value])
            if new:
                self.renames[value] = new
                key = self.add('path-renamed', value, 'proposed', f'{value} moved to {new}: {reason}. Refresh updates the recorded path only; tests and runtime code stay as written.',
                               files, {'from': value, 'to': new})
                for name, pointer, _root in refs[value]:
                    self.change(name, pointer, value, new, key)
            else:
                self.add('source-root-missing' if source_root else 'path-missing', value, 'needs_adjudication',
                         f'{value} is referenced but missing: {reason}', files, evidence={'candidates': candidates})

    def check_features(self, features):
        for name, record in features.items():
            roots = [r for r in record.get('sourceRoots') or [] if isinstance(r, str)]
            if roots and all(not self.exists(r) and r not in self.renames for r in roots):
                self.add('feature-implementation-missing', str(record.get('id')), 'needs_adjudication',
                         'every source root of this feature is gone. The record, its id and its intent are kept until a person decides on retirement.',
                         [name], evidence={'knowledge': record.get('knowledge'), **self.confirmed(record)})

    def routes_now(self, roots):
        found = set()
        for root in roots:
            for name in self.current_under(root):
                text = self.text(name)
                if text is not None:
                    found.update(ROUTE.findall(text))
        return found

    def routes_base(self, roots):
        found = set()
        for current in roots:
            # A path renamed by an applied refresh is read at its generation-base name.
            root = self.origins.get(current, current)
            for rel in self.base_tree.under(root):
                text = self.base_tree.text(f'{root}/{rel}' if rel else root)
                if text is not None:
                    found.update(ROUTE.findall(text))
        return found

    def check_routes(self, features):
        if not self.base_tree.available:
            return
        mapped = {str(r.get('route')).split('?', 1)[0] for f in features.values() for r in f.get('reach') or [] if isinstance(r, dict) and r.get('route')}
        for name, record in features.items():
            roots = [r for r in record.get('sourceRoots') or [] if isinstance(r, str)]
            now = self.routes_now([self.renames.get(r, r) for r in roots])
            base = self.routes_base(roots)
            removed, added = base - now, now - base - mapped
            consumed = set()
            feature = str(record.get('id'))
            for index, entry in enumerate(record.get('reach') or []):
                route = entry.get('route') if isinstance(entry, dict) else None
                if not isinstance(route, str):
                    continue
                path = route.split('?', 1)[0]
                if path in now:
                    continue
                if path not in base:
                    self.not_checked.append(f'{feature} route {route} is not a literal in its source roots at the generation base or now')
                    continue
                if len(removed) == 1 and len(added) == 1:
                    new = next(iter(added))
                    consumed.add(new)
                    key = self.add('route-renamed', f'{feature}:{route}', 'proposed',
                                   f'{route} is the only route literal that left the source roots and {new} the only one that arrived. The feature id and its scenarios stay.',
                                   [name], {'from': route, 'to': new}, {'feature': feature, **self.confirmed(record)})
                    self.change(name, ('reach', index, 'route'), route, route.replace(path, new, 1), key)
                else:
                    self.add('route-missing', f'{feature}:{route}', 'needs_adjudication',
                             f'{route} was a literal in the source roots at the generation base and is gone. Decide the new reach or retire the feature; refresh keeps the record.',
                             [name], evidence={'feature': feature, 'removed': sorted(removed), 'added': sorted(added), **self.confirmed(record)})
            for route in sorted(added - consumed):
                self.add('route-added', f'{feature}:{route}', 'needs_adjudication',
                         f'{route} arrived in the source roots of {feature} and no feature reaches it. Map it as reach or a new proposed feature, or leave it unmapped.',
                         [name], evidence={'feature': feature})

    def check_bindings(self, features):
        if self.config is None:
            return
        registered = {}
        for value in self.config.get('bindings') or []:
            if not plain_path(value):
                continue
            for name in self.current_under(self.renames.get(value, value)):
                if Path(name).suffix in {'.ts', '.tsx', '.js', '.mjs', '.cts', '.mts'}:
                    for scenario in BINDING.findall(self.text(name) or ''):
                        registered.setdefault(scenario, []).append(name)
        folder = self.config.get('scenariosDir', 'verification/scenarios')
        recorded = {}
        for record in features.values():
            for path in sorted((self.root / folder / str(record.get('id'))).glob('*.json')) if plain_path(folder) else []:
                try:
                    recorded[json.loads(path.read_text()).get('id')] = path.relative_to(self.root).as_posix()
                except (ValueError, OSError, AttributeError):
                    continue
        for scenario in sorted(set(recorded) - set(registered), key=str):
            self.add('binding-stale', str(scenario), 'needs_adjudication',
                     f'{scenario} has a record and no literal registration under the configured bindings. Scenario ids are stable; refresh never renames them.',
                     [recorded[scenario]], evidence={'unrecorded': sorted(set(registered) - set(recorded))})
        for scenario in sorted(set(registered) - set(recorded)):
            self.add('binding-orphan', scenario, 'needs_adjudication',
                     f'{scenario} is registered in a test without a scenario record. Add the record or rename the registration.',
                     registered[scenario])

    def breaks_dir(self):
        text = self.text(self.skill_path) if self.skill_path else None
        match = re.search(r'^Breaks:[ \t]*`?([^`\n]+?)`?[ \t]*$', text or '', re.M)
        return match.group(1) if match else 'verification/breaks'

    def check_breaks(self):
        folder = self.breaks_dir()
        if not plain_path(folder):
            return
        for path in sorted((self.root / folder).glob('*.patch')):
            name = path.relative_to(self.root).as_posix()
            if git(self.root, 'apply', '--check', str(path), required=False) is not None:
                continue
            text = path.read_text()
            rewritten = text
            for old, new in sorted(self.renames.items(), key=lambda item: -len(item[0])):
                rewritten = re.sub(rf'(?m)^(diff --git a/|--- a/|\+\+\+ b/)({re.escape(old)})(?=/| |$)', lambda m: m.group(1) + new, rewritten)
                rewritten = re.sub(rf'(?m)^(diff --git a/\S+ b/)({re.escape(old)})(?=/|$)', lambda m: m.group(1) + new, rewritten)
            applies = False
            if rewritten != text:
                with tempfile.NamedTemporaryFile('w', suffix='.patch', delete=False) as handle:
                    handle.write(rewritten)
                try:
                    applies = git(self.root, 'apply', '--check', handle.name, required=False) is not None
                finally:
                    os.unlink(handle.name)
            if applies:
                key = self.add('break-renamed', name, 'proposed', 'the break patch applies again once its file headers follow the proven renames', [name])
                self.text_edits[name] = (rewritten, key)
            else:
                self.add('break-stale', name, 'needs_adjudication',
                         'the declared break patch no longer applies to the checkout. A person rewrites it so it still breaks the scenario it names.', [name])

    def check_managed(self):
        name = self.skill_path
        match = SKILL_PATH.match(name or '')
        current = self.text(name) if name else None
        if current is None or not match or self.config is None:
            return
        bindings = [self.renames.get(b, b) for b in self.config.get('bindings') or [] if isinstance(b, str)]
        rendered = (SKILL / TEMPLATE).read_text().replace('{{PROJECT}}', match.group(1)).replace('{{BINDINGS}}', ', '.join(bindings))
        desired, block = managed_block(rendered), managed_block(current)
        entry = self.installed.get(name) or {}
        base = self.managed.get(name)
        if base is None and entry.get('digest') == digest(current.encode()):
            base = block
        if block is None:
            if base is not None and desired != base:
                self.add('managed-markers-missing', name, 'needs_adjudication',
                         'the discovery markers are gone, so the whole file is human-owned and the generated update has nowhere to go',
                         [name], {'proposedBlock': desired})
            return
        if block == desired:
            return
        if base is None:
            self.add('managed-base-missing', name, 'conflict',
                     'the discovery block differs from the generated one and no installed base is recorded. Human bytes are kept.',
                     [name], {'proposedBlock': desired}, {'current': block})
        elif block == base:
            key = self.add('managed-update', name, 'proposed', 'the marked discovery block follows the current configuration; text outside the markers is untouched', [name])
            self.text_edits[name] = (current.replace(block, desired), key)
            self.managed_next = desired
        elif desired == base:
            self.add('managed-section-edited', name, 'info', 'a person edited the marked discovery block; refresh keeps those bytes', [name])
        else:
            self.add('managed-conflict', name, 'conflict',
                     'a person edited the marked discovery block and the generated block changed too. Human bytes are kept; review the proposed block.',
                     [name], {'proposedBlock': desired}, {'current': block, 'base': base})

    def check_runtime(self, install):
        entry = self.installed.get(RUNTIME_PATH)
        if entry is None:
            return
        base_template = entry.get('templateDigest') or (install.get('generator') or {}).get('files', {}).get(RUNTIME)
        now_template = generator_identity()['files'][RUNTIME]
        if base_template == now_template:
            return
        generated = (SKILL / RUNTIME).read_text()
        current = self.text(RUNTIME_PATH)
        if current is None:
            self.add('runtime-missing', RUNTIME_PATH, 'needs_adjudication', 'the generator runtime changed and the project runtime is absent; nothing is recreated', [RUNTIME_PATH])
            return
        if current == generated:
            self.runtime_next = (generated, now_template)
            return
        if digest(current.encode()) == entry.get('digest'):
            key = self.add('runtime-update', RUNTIME_PATH, 'proposed', 'the runtime is byte-identical to its installed base, so the generator update applies as a reviewed patch', [RUNTIME_PATH])
            self.text_edits[RUNTIME_PATH] = (generated, key)
            self.runtime_next = (generated, now_template)
            return
        base = git(self.root, 'cat-file', 'blob', entry['blob'], required=False) if entry.get('blob') else None
        if base is None:
            self.add('runtime-base-missing', RUNTIME_PATH, 'needs_adjudication',
                     'the runtime has hand edits, the generator runtime changed, and the installed base bytes are not in this repository. Hand edits are kept.', [RUNTIME_PATH])
            return
        with tempfile.TemporaryDirectory(prefix='leyline-merge-') as folder:
            paths = []
            for label, data in (('current', current.encode()), ('base', base), ('generated', generated.encode())):
                Path(folder, label).write_bytes(data)
                paths.append(str(Path(folder, label)))
            merged = subprocess.run(['git', 'merge-file', '-p', '-L', 'project', '-L', 'installed', '-L', 'generator', *paths], capture_output=True)
        text = merged.stdout.decode(errors='replace')
        if merged.returncode == 0:
            key = self.add('runtime-update', RUNTIME_PATH, 'proposed', 'the generator update merges cleanly with the hand edits, which are kept', [RUNTIME_PATH])
            self.text_edits[RUNTIME_PATH] = (text, key)
            self.runtime_next = (generated, now_template)
        else:
            self.add('runtime-conflict', RUNTIME_PATH, 'conflict',
                     'the generator update overlaps hand edits. The project runtime is kept; resolve the proposed merge by hand.',
                     [RUNTIME_PATH], {'proposedMerge': text})

    def check_command(self):
        text = self.text(self.skill_path) if self.skill_path else None
        match = re.search(r'^Command:[ \t]*`?([^`\n]+?)`?[ \t]*$', text or '', re.M)
        if not match:
            return
        words = match.group(1).split()
        script = None
        if words[:2] == ['npm', 'run']:
            script = next((w for w in words[2:] if not w.startswith('-')), None)
        elif words[:1] == ['pnpm']:
            script = next((w for w in words[1:] if w != 'run' and not w.startswith('-')), None)
        if script is None:
            self.not_checked.append(f'Command {match.group(1)!r} is not a package script this check can read')
            return
        package = self.load_json('package.json', 'package') if (self.root / 'package.json').is_file() else None
        scripts = (package or {}).get('scripts') if isinstance((package or {}).get('scripts'), dict) else {}
        if script not in scripts:
            self.add('command-missing', script, 'needs_adjudication',
                     f'the control Command runs package script {script!r}, which package.json no longer has. A person restores it or changes the Command.',
                     ['package.json', self.skill_path])
            return
        value = scripts[script]
        if not isinstance(value, str):
            return
        for token in value.split():
            if plain_path(token) and not self.exists(token) and (self.head_tree.has(token) or self.base_tree.has(token)):
                new, candidates, reason = self.find_rename(token)
                if new:
                    key = self.add('command-path-renamed', token, 'proposed', f'the package script target moved: {reason}', ['package.json'], {'from': token, 'to': new})
                    self.change('package.json', ('scripts', script), value, value.replace(token, new), key)
                else:
                    self.add('command-path-missing', token, 'needs_adjudication', f'package script {script!r} names a missing path: {reason}',
                             ['package.json'], evidence={'candidates': candidates})

    def check_ports(self):
        profiles = []
        if (self.root / LAUNCH).is_file():
            launch = self.load_json(LAUNCH, 'launch')
            for item in (launch or {}).get('configurations') or []:
                if isinstance(item, dict) and isinstance(item.get('name'), str):
                    profiles.append({'name': item['name'], 'port': item.get('port') if isinstance(item.get('port'), int) else None})
        text = self.text(self.skill_path) if self.skill_path else None
        if not profiles or text is None:
            return
        # Distinct named profiles are facts to keep apart, never values to unify.
        self.facts['launchProfiles'] = profiles
        ports = {p['port'] for p in profiles if p['port'] is not None}
        for number, line in enumerate(text.splitlines(), 1):
            for match in PORT.finditer(line):
                port = int(match.group(1))
                named = [p for p in profiles if re.search(rf'(?<![\w-]){re.escape(p["name"])}(?![\w-])', line)]
                subject = f'{self.skill_path}:{number}:{port}'
                evidence = {'line': number, 'text': line.strip(), 'instructionPort': port, 'profiles': profiles}
                if len(named) == 1 and named[0]['port'] == port:
                    continue
                if len(named) == 1:
                    self.add('port-drift', subject, 'needs_adjudication',
                             f'line {number} describes profile {named[0]["name"]!r} on port {port}; {LAUNCH} gives that profile port {named[0]["port"]}. '
                             'Which value is right needs a measured launch or a person. Neither file is edited.',
                             [self.skill_path, LAUNCH], evidence=evidence)
                elif len(named) > 1:
                    self.add('port-ambiguous', subject, 'needs_adjudication',
                             f'line {number} names several launch profiles, so port {port} cannot be attributed to one', [self.skill_path, LAUNCH], evidence=evidence)
                elif port not in ports:
                    self.add('port-unattributed', subject, 'needs_adjudication',
                             f'line {number} gives port {port}, which no launch profile uses, and names no profile. Record which profile it describes before correcting either value.',
                             [self.skill_path, LAUNCH], evidence=evidence)

    def recovery_finding(self, recovery, outputs):
        listed = []
        for name in recovery:
            data = (self.root / name).read_bytes()
            matches = [f'{out} {kind}' for out, item in sorted(outputs.items())
                       for kind, value in (('candidate bytes', item.get('digest')), ('original bytes', (item.get('before') or {}).get('digest')))
                       if value == digest(data)]
            listed.append({'path': name, 'digest': digest(data), 'matches': matches})
        self.add('recovery-files', 'checkout', 'needs_adjudication',
                 'installer staging or recovery files remain. Their bytes are kept; inspect each before removing it.',
                 recovery, evidence={'files': listed})

    # Interrupted installation ----------------------------------------------------
    def recipe_matches(self, plan):
        """Rebuild the pre-install source and recompute the recipe; True, or why it cannot be shown."""
        with tempfile.TemporaryDirectory(prefix='leyline-recipe-') as folder:
            original = Path(folder).resolve()
            for name, state in plan['source']['manifest']['files'].items():
                target = original / name
                target.parent.mkdir(parents=True, exist_ok=True)
                if state['kind'] == 'symlink':
                    target.symlink_to(state['target'])
                    continue
                path = self.root / name
                data = path.read_bytes() if path.is_file() and not path.is_symlink() else None
                if data is None or digest(data) != state['digest']:
                    # An output written over an existing file: its original bytes come from HEAD.
                    data = git(self.root, 'show', f'HEAD:{name}', required=False)
                if data is None or digest(data) != state['digest']:
                    return f'the original bytes of {name} are not recoverable'
                target.write_bytes(data)
                os.chmod(target, state['mode'])
            try:
                validate_spec(original, plan['spec'])
                expected = build_outputs(original, inspect(original), plan['spec'])
            except Problem as exc:
                return str(exc)
            return True if expected == plan['outputs'] else 'its candidate contents differ from the declared recipe'

    def partial(self, result, plan, recovery):
        outputs = dict(plan['outputs'])
        outputs[LEDGER] = ledger_output(plan)
        complete, absent, conflicting = [], [], []
        for name, item in sorted(outputs.items()):
            state = file_state(self.root / name) if plain_path(name) else None
            if state is not None and state.get('digest') == item['digest']:
                complete.append(name)
            elif state == item['before']:
                absent.append(name)
            else:
                conflicting.append({'path': name, 'current': state, 'original': item['before'], 'candidateDigest': item['digest']})
        base = plan['source']['manifest']['files']
        drift = sorted({n for n, s in self.files.items() if n not in outputs and not is_recovery(n) and base.get(n) != s} |
                       {n for n in base if n not in outputs and n not in self.files})
        generator_same = plan['generator'] == generator_identity()
        recipe = self.recipe_matches(plan) if generator_same and not conflicting and not drift else None
        work = [f'Keep {c["path"]}: its bytes match neither the original nor the candidate. Decide them before resuming.' for c in conflicting]
        work += [f'Source changed since the map at {n}; regenerate and review a new map after deciding the partial files.' for n in drift]
        if not generator_same:
            work.append('The generator changed since the map; resume would write different bytes. Regenerate the map.')
        if recipe is not None and recipe is not True:
            work.append(f'The map cannot be checked against the recipe ({recipe}); a map checksum alone does not authorize generated bytes. Regenerate the map.')
        if recovery:
            self.recovery_finding(recovery, outputs)
            work += [f'Inspect {n} and remove it once its bytes are accounted for.' for n in recovery]
        resumable = bool(absent) and not conflicting and not drift and generator_same and recipe is True
        result['partial'] = {'map': self.inputs['map'], 'mapDigest': plan['mapDigest'], 'complete': complete, 'absent': absent,
                             'conflicting': conflicting, 'drift': drift, 'recovery': recovery, 'resumable': resumable,
                             'recoveryWork': work or ['Resume writes the absent outputs in installation order, then the ledger record.']}
        result['state'] = 'partial'
        result['findings'] = sorted(self.findings.values(), key=lambda f: f['id'])
        result['edits'] = {name: {'findings': [], 'withheld': not resumable,
                                  'diff': ''.join(difflib.unified_diff((self.text(name) or '').splitlines(True) if self.exists(name) else [],
                                                                       outputs[name]['text'].splitlines(True), f'a/{name}', f'b/{name}'))}
                           for name in absent}
        result['writes'] = {name: {k: outputs[name][k] for k in ('before', 'text', 'digest', 'ownership')} for name in absent} if resumable else {}
        result['ledgerAppend'] = resumable
        result['knowledgeChanged'] = False
        return result

    # Result ----------------------------------------------------------------------
    def finish(self, result, challenge, records):
        edits = {}
        for name, changes in sorted(self.json_changes.items()):
            text = self.text(name)
            new = json_edit(text, [(p, o, n) for p, o, n, _f in changes]) if text is not None else None
            if new is None:
                for _p, _o, _n, key in changes:
                    finding = self.findings[key]
                    finding['severity'] = 'needs_adjudication'
                    finding['detail'] += f' The edit to {name} cannot be placed without reformatting human bytes, so it is left to a person.'
            else:
                edits[name] = (text, new, sorted({key for *_rest, key in changes}))
        for name, (new, key) in sorted(self.text_edits.items()):
            edits[name] = (self.text(name), new, [key])
        findings = sorted(self.findings.values(), key=lambda f: f['id'])
        severities = {f['severity'] for f in findings}
        if 'conflict' in severities:
            state = 'conflict'
        elif challenge and (challenge['outcome'] in ('failed', 'interrupted')):
            state = 'failed'
        elif edits:
            state = 'candidate'
        elif 'needs_adjudication' in severities:
            state = 'unresolved'
        elif challenge and not (challenge['outcome'] == 'passed' and challenge['evidence']['verified'] and challenge['relevance'] == 'current'):
            state = 'unverified'
        elif challenge:
            state = 'verified'
        else:
            state = 'unchanged'
        # Conflicts block every edit: no installation until a person resolves them.
        applied = {} if state == 'conflict' else edits
        result.update(state=state, findings=findings, notChecked=sorted(set(self.not_checked)), facts=self.facts, challenge=challenge)
        result['edits'] = {name: {'findings': keys, 'diff': ''.join(difflib.unified_diff(old.splitlines(True), new.splitlines(True), f'a/{name}', f'b/{name}')),
                                  'withheld': name not in applied}
                           for name, (old, new, keys) in edits.items()}
        writes = {}
        for name, (old, new, _keys) in applied.items():
            before = file_state(self.root / name)
            writes[name] = {'before': before, 'text': new, 'digest': digest(new.encode()),
                            'ownership': (self.installed.get(name) or {}).get('ownership', 'focused refresh edit')}
        record = self.record(state, findings, applied, challenge, records) if records else None
        last = records[-1]['record'] if records else None
        if record is not None and (applied or self.material(record) != self.material(last)):
            ledger = self.root / LEDGER
            text = ledger.read_text()
            mark = digest(canonical(record))
            text += ('\n' if text.endswith('\n') else '\n\n') + f'<!-- leyline-refresh:{mark} -->\n## Control refresh\n\n```json\n' + encode(record).decode() + '```\n'
            writes[LEDGER] = {'before': file_state(ledger), 'text': text, 'digest': digest(text.encode()), 'ownership': 'append-only refresh record'}
            result['ledgerRecord'] = record
        for name, item in writes.items():
            if name not in result['edits']:
                result['edits'][name] = {'findings': [], 'withheld': False,
                                         'diff': ''.join(difflib.unified_diff(self.text(name).splitlines(True) if self.exists(name) else [], item['text'].splitlines(True), f'a/{name}', f'b/{name}'))}
        result['writes'] = writes
        result['ledgerAppend'] = LEDGER in writes
        result['knowledgeChanged'] = False
        return result

    def record(self, state, findings, applied, challenge, records):
        last = records[-1]['record']
        installed = json.loads(json.dumps(last.get('installedFiles') or {}))
        managed = dict(last.get('managed') or {})
        for name, (_old, new, keys) in applied.items():
            if name in installed:
                installed[name].update(digest=digest(new.encode()), blob=git_blob(new.encode()))
        if getattr(self, 'managed_next', None) and self.skill_path in applied:
            managed[self.skill_path] = self.managed_next
            installed.setdefault(self.skill_path, {})['templateDigest'] = generator_identity()['files'][TEMPLATE]
        runtime = getattr(self, 'runtime_next', None)
        if runtime and (RUNTIME_PATH in applied or self.text(RUNTIME_PATH) == runtime[0]) and RUNTIME_PATH in installed:
            # The recorded base is the generated text, so a later merge sees hand edits as edits.
            installed[RUNTIME_PATH].update(templateDigest=runtime[1], blob=git_blob(runtime[0].encode()))
            if RUNTIME_PATH not in applied:
                installed[RUNTIME_PATH]['digest'] = digest(runtime[0].encode())
        applied_keys = {key for _old, _new, keys in applied.values() for key in keys}
        origins = dict(getattr(self, 'origins', {}))
        for finding in findings:
            if finding['kind'] == 'path-renamed' and finding['id'] in applied_keys:
                moved = finding['resolution']
                origins[moved['to']] = origins.pop(moved['from'], moved['from'])
        knowledge ={str(r.get('id')): r.get('knowledge') for r in getattr(self, 'features', {}).values()}
        intent = {}
        for finding in findings:
            snapshot = finding['evidence'].get('confirmedIntent')
            if snapshot and finding['id'] not in applied_keys:
                intent[snapshot['feature']] = snapshot
        run_ids = sorted(set(last.get('challengeRunIds') or []) | set((challenge or {}).get('runIds') or []))
        summary = None
        if challenge:
            summary = {k: challenge[k] for k in ('outcome', 'head', 'feature', 'relevance')}
            summary['evidence'] = {k: challenge['evidence'][k] for k in ('dir', 'manifestDigest', 'verified')}
        record = {'kind': 'refresh', 'state': state, 'generator': generator_identity(),
                  'base': {'installMap': next(r['mark'] for r in reversed(records) if r['kind'] == 'install') if any(r['kind'] == 'install' for r in records) else None,
                           'generationHead': getattr(self, 'generation_head', None)},
                  'source': {'head': self.source['head'], 'manifestDigest': self.source['manifest']['digest']},
                  'installedFiles': installed, 'managed': managed, 'origins': origins,
                  'applied': sorted(applied_keys),
                  'findings': [{'id': f['id'], 'kind': f['kind'], 'severity': f['severity']} for f in findings if f['id'] not in applied_keys],
                  'knowledge': knowledge, 'challengeRunIds': run_ids,
                  'challenge': summary if challenge else last.get('challenge')}
        if intent:
            record['confirmedIntent'] = intent
        record['pending'] = [] if state == 'verified' else [
            'A passing challenge of the current committed bytes, refreshed with --challenge, is still owed before any readiness claim.']
        return record

    @staticmethod
    def material(record):
        if record is None:
            return None
        challenge = record.get('challenge') or {}
        return canonical({'installedFiles': record.get('installedFiles') or {}, 'managed': record.get('managed') or {},
                          'origins': record.get('origins') or {},
                          'findings': record.get('findings') or [], 'knowledge': record.get('knowledge') or {},
                          'challengeRunIds': record.get('challengeRunIds') or [],
                          'challenge': {k: challenge.get(k) for k in ('outcome', 'head', 'evidence')} if challenge else None})


def refresh(root, args):
    if args.apply:
        candidate = read_json(args.apply)
        claimed = candidate.pop('candidateDigest', None)
        if candidate.get('format') != REFRESH or digest(canonical(candidate)) != claimed:
            fail('refresh candidate format or digest is invalid; regenerate it')
        fresh = Refresh(root, candidate['inputs']['map'], candidate['inputs']['challenge']).run()
        if fresh != candidate:
            fail('the checkout, ledger or inputs changed since this refresh candidate was reviewed; regenerate and review it')
        if fresh['state'] == 'partial' and not fresh['partial']['resumable']:
            fail('the interrupted installation cannot resume: ' + ' '.join(fresh['partial']['recoveryWork']))
        writes = fresh['writes']
        for name in writes:
            path = relative(root, name)
            if any(parent.is_symlink() for parent in [path, *path.parents] if parent != root and root in parent.parents):
                fail(f'output path crosses a symlink: {name}')
        if fresh['state'] == 'partial' and writes:
            plan = read_json(candidate['inputs']['map'])
            outputs = dict(plan['outputs'])
            outputs[LEDGER] = ledger_output(plan)
            check_candidate(root, plan, outputs)
        if writes:
            publish(root, {name: {k: item[k] for k in ('before', 'text', 'digest', 'ownership')} for name, item in writes.items()})
        return {'mode': 'refresh', 'applied': True, 'state': fresh['state'], 'written': sorted(writes),
                'ledgerAppend': fresh['ledgerAppend'], 'withheld': sorted(n for n, e in fresh['edits'].items() if e['withheld']),
                'executedProjectCode': False, 'knowledgeChanged': False}
    result = Refresh(root, args.map, args.challenge).run()
    result['candidateDigest'] = digest(canonical(result))
    if args.out:
        target = output_path(args.out, root)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(encode(result))
    summary = {k: result.get(k) for k in ('state', 'findings', 'notChecked', 'facts', 'challenge', 'partial', 'ledgerAppend', 'knowledgeChanged', 'executedProjectCode')}
    summary.update(mode='refresh', candidate=str(output_path(args.out, root)) if args.out else None,
                   candidateDigest=result['candidateDigest'], diff=bool(result['writes']),
                   edits={name: {'findings': e['findings'], 'withheld': e['withheld']} for name, e in (result.get('edits') or {}).items()},
                   writes=sorted(result['writes']))
    return {k: v for k, v in summary.items() if v is not None}


parser = argparse.ArgumentParser(description='Inspect, map and install a project-owned control candidate.')
sub = parser.add_subparsers(dest='mode', required=True)
for name in ('inspect', 'map', 'install', 'refresh'):
    command = sub.add_parser(name)
    command.add_argument('repo')
    if name == 'map':
        command.add_argument('--spec', required=True)
        command.add_argument('--out', required=True)
    if name == 'install':
        command.add_argument('--map', required=True)
    if name == 'refresh':
        command.add_argument('--out')
        command.add_argument('--map')
        command.add_argument('--challenge')
        command.add_argument('--apply')
args = parser.parse_args(sys.argv[2:])
try:
    root = Path(args.repo).resolve(strict=True)
    if not root.is_dir():
        fail('repository must be a directory')
    if args.mode == 'refresh' and args.apply and (args.out or args.map or args.challenge):
        fail('--apply takes only the reviewed candidate; its inputs are recorded inside it')
    modes = {'inspect': lambda: inspect(root), 'map': lambda: write_map(root, args), 'install': lambda: install(root, args),
             'refresh': lambda: refresh(root, args)}
    result = modes[args.mode]()
    print(json.dumps(result, indent=2))
except (Problem, OSError, UnicodeError, KeyError, TypeError, ValueError) as exc:
    print('generate.sh: ' + str(exc), file=sys.stderr)
    sys.exit(1)
PY
