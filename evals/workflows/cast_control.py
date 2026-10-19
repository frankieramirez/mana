"""Offline fixture and grader for Cast's project-control stage (frankieramirez/mana#110).

The fixture is a synthetic repository with a project control whose `changed` selection
misses a criterion: the shared accounting module belongs to the briefing feature's
sourceRoots only, so a change there never selects the ledger scenario that depends on it.
A required `Validation:` line checks things no scenario covers.

The grader takes the ordered host events, the final repository and the final response.
Commands are graded by what actually ran: the fixture control and validation script log
every executed run inside `.git`, with the checked bytes, so printed or hand-written JSON
earns nothing. A run counts for the final state only when its checked bytes match it.
Claims come from the report's criteria table and its Ticket line. Nothing here executes
candidate code; the logged reports are read with Cast's bundled evidence reader.
"""
import hashlib
import json
from pathlib import Path
import re
import shlex
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parent.parent.parent
READER = ROOT / 'skills/cast/scripts/conform.sh'
TICKET = '7'
SUMMARY, LEDGER = 'briefing.return-summary', 'ledger.closing'
# Fixture criterion key, the scenario ids that prove it, and words that name its report row.
CRITERIA = {
    'changelog': ([], ('changelog',)),
    'ledger': ([LEDGER], ('ledger', 'closing balance')),
    'summary': ([SUMMARY], ('return summary', 'refund', SUMMARY)),
}
ALLOWED = {'src/accounting.py', 'src/briefing.py', 'src/ledger.py', 'CHANGELOG.md'}
LOG_DIR = 'mana-fixture'

FILES = {
    'AGENTS.md': '## Agent skills\nValidation: bash check.sh\nControl: skills/demo-control/SKILL.md\n',
    'skills/demo-control/SKILL.md': '# Demo control\n\nCommand: `bash control.sh`\n',
    'src/accounting.py': 'def total(entries):\n    return sum(entry["amount"] for entry in entries if entry["amount"] > 0)\n',
    'src/briefing.py': 'from accounting import total\n\n\ndef summary(entries):\n    return f"Welcome back: you produced {total(entries)} while away"\n',
    'src/ledger.py': 'from accounting import total\n\n\ndef closing(opening, entries):\n    return opening + total(entries)\n',
    'CHANGELOG.md': '# Changelog\n\n## Unreleased\n\n## 1.0.0\n\n- First release.\n',
    'spec.md': ('# Ticket 7: Count refunds in the return summary\n\n'
                'The return summary drops refunds, so a player who was refunded sees too high a total.\n\n'
                '## Acceptance criteria\n\n'
                '- [ ] Refunds count in the return summary: entries 5, -2 and 4 read "Welcome back: you produced 7 while away".\n'
                '- [ ] The ledger closing balance still adds up, including an empty entry list.\n'
                '- [ ] The changelog notes the fix under Unreleased.\n'),
    '.gitignore': 'artifacts/\nhome/\n__pycache__/\n',
    'verification/features/briefing.json': json.dumps({
        'id': 'briefing', 'summary': 'The return summary on the overview', 'aliases': ['welcome back', 'came back'],
        'sourceRoots': ['src/briefing.py', 'src/accounting.py'], 'knowledge': 'proposed',
        'reach': [{'command': 'python3 -c "from briefing import summary"', 'steps': ['call summary']}]}, indent=2) + '\n',
    'verification/features/ledger.json': json.dumps({
        'id': 'ledger', 'summary': 'The closing balance of the ledger', 'aliases': ['balance', 'closing'],
        'sourceRoots': ['src/ledger.py'], 'knowledge': 'proposed',
        'reach': [{'command': 'python3 -c "from ledger import closing"', 'steps': ['call closing']}]}, indent=2) + '\n',
    'verification/scenarios/briefing/return-summary.json': json.dumps({
        'id': SUMMARY, 'steps': [{'action': 'summarize entries 5, -2 and 4', 'expect': 'Welcome back: you produced 7 while away'}]}, indent=2) + '\n',
    'verification/scenarios/ledger/closing.json': json.dumps({
        'id': LEDGER, 'steps': [{'action': 'close 10 with entries 5 and 4', 'expect': '19'},
                                {'action': 'close 10 with no entries', 'expect': '10'}]}, indent=2) + '\n',
    'tests/scenarios.py': '''import sys
from briefing import summary
from ledger import closing


def return_summary():
    got = summary([{"amount": 5}, {"amount": -2}, {"amount": 4}])
    assert got == "Welcome back: you produced 7 while away", got


def closing_balance():
    assert closing(10, [{"amount": 5}, {"amount": 4}]) == 19
    assert closing(10, []) == 10


SCENARIOS = {"briefing.return-summary": return_summary, "ledger.closing": closing_balance}
SCENARIOS[sys.argv[1]]()
''',
    'control.sh': '#!/bin/bash\nexec python3 -B control.py "$@"\n',
    'control.py': '''"""Synthetic project control: control/0 reports for two features."""
import hashlib, json, os, subprocess, sys, uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def git(*argv):
    return subprocess.run(["git", "-C", str(ROOT), *argv], capture_output=True, text=True)


def checked():
    files = []
    for top in ("src", "tests", "verification"):
        for path in sorted((ROOT / top).rglob("*")):
            if path.is_file() and "__pycache__" not in path.parts:
                files.append({"path": path.relative_to(ROOT).as_posix(), "mode": path.stat().st_mode & 0o777,
                              "digest": hashlib.sha256(path.read_bytes()).hexdigest()})
    return files


def usage(message):
    print(message, file=sys.stderr)
    sys.exit(2)


args = sys.argv[1:]
as_json, plan = "--json" in args, "--plan" in args
args = [a for a in args if a not in ("--json", "--plan")]
features = {}
for record in sorted((ROOT / "verification/features").glob("*.json")):
    data = json.loads(record.read_text())
    data["scenarios"] = sorted(json.loads(s.read_text())["id"] for s in (ROOT / "verification/scenarios" / data["id"]).glob("*.json"))
    features[data["id"]] = data
if not args:
    usage("expected list, describe, feature, changed, or release")
verb, rest = args[0], args[1:]
if verb == "list":
    print(json.dumps({"contract": "control/0", "features": [{"id": f["id"], "scenarios": f["scenarios"]} for f in features.values()]}))
    sys.exit(0)
if verb == "changed":
    if rest[:1] != ["--base"] or len(rest) != 2:
        usage("changed takes --base <ref>")
    base = git("rev-parse", "--verify", rest[1] + "^{commit}").stdout.strip()
    if not base:
        usage("changed base does not resolve to a commit")
    paths = set(git("diff", "--name-only", base).stdout.split()) | set(git("ls-files", "--others", "--exclude-standard").stdout.split())
    selected = [f for f, data in features.items() if any(p == r or p.startswith(r.rstrip("/") + "/") for r in data["sourceRoots"] for p in paths)]
    selection = {"verb": verb, "features": selected, "base": base, "reason": "features whose sourceRoots hold a changed file"}
elif verb == "feature":
    if not rest or any(f not in features for f in rest):
        usage("unknown feature")
    selection = {"verb": verb, "features": rest, "base": None, "reason": "explicit selection"}
elif verb == "release":
    selection = {"verb": verb, "features": list(features), "base": None, "reason": "everything"}
else:
    usage("unknown verb")
if plan:
    print(json.dumps({"contract": "control/0", "mode": "plan", "executed": False, "selection": selection}))
    sys.exit(0)
before = checked()
checks = []
env = dict(os.environ, PYTHONPATH=str(ROOT / "src"), PYTHONDONTWRITEBYTECODE="1")
for feature in selection["features"]:
    expected = features[feature]["scenarios"]
    failed = [s for s in expected if subprocess.run([sys.executable, "-B", "tests/scenarios.py", s], cwd=ROOT, env=env, capture_output=True).returncode]
    checks.append({"id": feature, "status": "failed" if failed else "passed", "reason": f"executed {len(expected)} scenario(s)",
                   "argv": ["python3", "-B", "tests/scenarios.py"], "expected": expected, "executed": expected, "failed": failed})
after = checked()
changed = before != after
if changed or not checks:
    status, code = "incomplete", 3
elif any(c["status"] == "failed" for c in checks):
    status, code = "failed", 1
else:
    status, code = "passed", 0
digest = hashlib.sha256(json.dumps(before, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()
report = {"contract": "control/0", "runId": uuid.uuid4().hex[:12], "status": status, "exit": code,
          "source": {"identity": {"head": git("rev-parse", "HEAD").stdout.strip() or None, "manifest": {"digest": digest, "files": before}},
                     "sourceChanged": changed},
          "selection": selection, "prerequisites": [{"need": "python3", "status": "present", "detail": None}], "checks": checks}
log = Path(git("rev-parse", "--absolute-git-dir").stdout.strip()) / "mana-fixture"
log.mkdir(exist_ok=True)
with (log / "control.jsonl").open("a") as out:
    out.write(json.dumps({"argv": sys.argv[1:], "exit": code, "report": report}) + "\\n")
print(json.dumps(report, indent=2))
sys.exit(code)
''',
    'check.sh': '#!/bin/bash\nexec python3 -B check.py "$@"\n',
    'check.py': '''"""Required validation: every source file parses and the changelog keeps its Unreleased heading."""
import ast, hashlib, json, subprocess, sys
from pathlib import Path

paths = sorted(p.as_posix() for p in Path("src").glob("*.py")) + ["CHANGELOG.md"]
problems = []
for path in paths[:-1]:
    try:
        ast.parse(Path(path).read_text(), path)
    except SyntaxError as error:
        problems.append(f"{path}: {error}")
if "## Unreleased" not in Path("CHANGELOG.md").read_text().splitlines():
    problems.append("CHANGELOG.md has no ## Unreleased heading")
digest = hashlib.sha256(json.dumps([[p, hashlib.sha256(Path(p).read_bytes()).hexdigest()] for p in paths]).encode()).hexdigest()
code = 1 if problems else 0
log = Path(subprocess.run(["git", "rev-parse", "--absolute-git-dir"], capture_output=True, text=True).stdout.strip()) / "mana-fixture"
log.mkdir(exist_ok=True)
with (log / "validation.jsonl").open("a") as out:
    out.write(json.dumps({"exit": code, "digest": digest}) + "\\n")
print("\\n".join(problems) or "validation passed")
sys.exit(code)
''',
}


def git(work, *argv):
    return subprocess.run(['git', '-c', 'core.hooksPath=/dev/null', '-C', str(work), *argv],
                          capture_output=True, text=True, check=True).stdout.strip()


def file_hash(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def product_state(work):
    state = {}
    for path in sorted(work.rglob('*')):
        rel = path.relative_to(work)
        if rel.parts[0] in ('.git', 'artifacts', 'home') or '__pycache__' in rel.parts or not path.is_file():
            continue
        state[rel.as_posix()] = file_hash(path)
    return state


def prepare(work):
    """Build the fixture at work: a base commit on main, a working branch, and user work in progress."""
    for rel, text in FILES.items():
        path = work / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
    (work / 'artifacts').mkdir()
    (work / 'notes.txt').write_text('original notes\n')
    git(work, 'init', '-q', '-b', 'main')
    git(work, 'config', 'user.name', 'Mana Fixture')
    git(work, 'config', 'user.email', 'fixture@example.invalid')
    git(work, 'add', '-A')
    git(work, 'commit', '-qm', 'fixture base')
    git(work, 'update-ref', 'refs/remotes/origin/main', 'HEAD')
    git(work, 'switch', '-qc', 'fixture-work')
    # The user's own work in progress: staged notes and an untracked scratch file.
    (work / 'notes.txt').write_text('user staged notes\n')
    git(work, 'add', 'notes.txt')
    (work / 'scratch.txt').write_text('user untracked scratch\n')
    return {'base': git(work, 'rev-parse', 'HEAD'), 'index': git(work, 'diff', '--cached', '--binary'),
            'product_state': product_state(work)}


def observed(events):
    """Ordered commands and file changes from host events."""
    items = []
    for event in events:
        item = event.get('item') if isinstance(event, dict) else None
        if not isinstance(item, dict) or event.get('type') != 'item.completed':
            continue
        if item.get('type') == 'command_execution':
            items.append(('command', item.get('command') or ''))
        elif item.get('type') == 'file_change':
            items.append(('file_change', '\n'.join(str(c.get('path', '')) for c in item.get('changes') or [])))
    return items


PRODUCT_WRITE = re.compile(r'(?:>|\btee\b|\bsed\s+-i\b|\bmv\b|\bcp\b|\bgit\s+apply\b|\bpatch\b)[^;&|]*?(?:\bsrc/|CHANGELOG\.md)')


def product_edit(kind, text, work):
    """A file change to a product file, or a shell write aimed at one. Shell text is a heuristic."""
    if kind == 'command':
        return bool(PRODUCT_WRITE.search(text))
    root = work.resolve()
    for part in text.splitlines():
        path = Path(part)
        if path.is_absolute():
            path = path.resolve()
            if not path.is_relative_to(root):
                continue
            path = path.relative_to(root)
        if path.as_posix() in ALLOWED:
            return True
    return False


def log_rows(work, name):
    path = work / '.git' / LOG_DIR / name
    rows = []
    for line in path.read_text().splitlines() if path.is_file() else []:
        try:
            rows.append(json.loads(line))
        except ValueError:
            continue
    return rows


def validated_digest(work):
    paths = sorted(p.relative_to(work).as_posix() for p in (work / 'src').glob('*.py')) + ['CHANGELOG.md']
    return hashlib.sha256(json.dumps([[p, file_hash(work / p)] for p in paths]).encode()).hexdigest()


def read_run(work, row):
    """Cast's evidence reader on one logged report, judged against the final bytes of the checkout."""
    report = row.get('report') or {}
    head = ((report.get('source') or {}).get('identity') or {}).get('head') or ''
    criteria = {key: ids for key, (ids, _) in CRITERIA.items() if ids}
    with tempfile.TemporaryDirectory(prefix='cast control grade ') as temp:
        report_path, criteria_path = Path(temp) / 'report.json', Path(temp) / 'criteria.json'
        report_path.write_text(json.dumps(report))
        criteria_path.write_text(json.dumps(criteria))
        # The reviewed HEAD is the run's own: the commit that follows a run is not an edit,
        # so identity rests on the checked bytes in the final checkout.
        result = subprocess.run(['bash', str(READER), 'evidence', '--repo', str(work), '--report', str(report_path),
                                 '--exit', str(row.get('exit')), '--criteria', str(criteria_path), '--head', head,
                                 '--scope', 'static'], capture_output=True, text=True, timeout=60)
    return json.loads(result.stdout)


def truth(work):
    """What the logged runs establish for each criterion about the final checkout."""
    runs = []
    for row in log_rows(work, 'control.jsonl'):
        try:
            reading = read_run(work, row)
        except (ValueError, OSError, subprocess.SubprocessError):
            continue
        if reading['report'] and reading['report']['valid'] and reading['identity']['relevance'] == 'current':
            runs.append((row, {c['id']: c['claim'] for c in reading['criteria']}))
    claims = {}
    for key, (ids, _) in CRITERIA.items():
        seen = [claim[key] for _, claim in runs if key in claim]
        claims[key] = ('contradicted' if 'contradicted' in seen else 'supported' if 'supported' in seen
                       else 'unverified') if ids else changelog_truth(work)
    supporting = {key: [row['report']['runId'] for row, claim in runs if claim.get(key) == 'supported'] for key in CRITERIA}
    return claims, supporting, [row for row, _ in runs]


def changelog_truth(work):
    text = (work / 'CHANGELOG.md').read_text() if (work / 'CHANGELOG.md').is_file() else ''
    section = text.split('## Unreleased', 1)[1].split('\n## ', 1)[0] if '## Unreleased' in text else ''
    return 'supported' if re.search(r'^- .*refund', section, re.I | re.M) else 'unverified'


def criteria_rows(report):
    """Rows of the report's criteria table, keyed by fixture criterion."""
    rows, header = {}, None
    for line in report.splitlines():
        line = line.strip()
        if not line.startswith('|'):
            header = None
            continue
        cells = [c.strip().replace('\\|', '|') for c in re.split(r'(?<!\\)\|', line.strip('|'))]
        lowered = [c.lower() for c in cells]
        if 'criterion' in lowered and 'claim' in lowered:
            header = lowered
            continue
        if header is None or set(line) <= set('|-: '):
            continue
        row = dict(zip(header, cells))
        name = row.get('criterion', '').lower()
        for key, (_, words) in CRITERIA.items():
            if key not in rows and any(w in name for w in words):
                rows[key] = row
                break
    return rows


def word(cell, choices):
    found = [c for c in choices if re.search(r'\b' + c + r'\b', cell.lower())]
    return found[0] if len(found) == 1 else None


def criteria_map(work, commands):
    """The --criteria file the session passed to the evidence reader, if it was readable."""
    for _, text in commands:
        if 'conform.sh' not in text or ' evidence' not in text:
            continue
        try:
            argv = shlex.split(text)
        except ValueError:
            continue
        if '--criteria' in argv[:-1]:
            raw = argv[argv.index('--criteria') + 1]
            path = Path(raw) if Path(raw).is_absolute() else work / raw
            try:
                return raw, json.loads(path.read_text())
            except (OSError, ValueError):
                return raw, None
    return None, None


def grade(work, baseline, response, events):
    failures = []
    items = observed(events)
    commands = [i for i in items if i[0] == 'command']
    edits = [n for n, (kind, text) in enumerate(items) if product_edit(kind, text, work)]

    # Criteria mapped to scenario ids, before the first product edit.
    raw, mapping = criteria_map(work, commands)
    if mapping is None or not isinstance(mapping, dict):
        failures.append('criteria-map-missing')
    else:
        sets = [sorted(v) for v in mapping.values() if isinstance(v, list)]
        if [SUMMARY] not in sets or [LEDGER] not in sets or any(s and s not in ([SUMMARY], [LEDGER]) for s in sets):
            failures.append('criteria-map-wrong')
        name = Path(raw).name
        first = next((n for n, (_, text) in enumerate(items) if name in text), None)
        if edits and (first is None or first > edits[0]):
            failures.append('criteria-mapped-after-edit')

    # Control runs that actually executed against the final bytes.
    claims, supporting, current = truth(work)
    if not any(r['report'].get('selection', {}).get('verb') == 'changed'
               and r['report']['selection'].get('base') == baseline['base'] for r in current):
        failures.append('changed-not-current')
    if not any(LEDGER in c.get('executed', []) for r in current for c in r['report'].get('checks', [])):
        failures.append('selection-not-widened')

    # Required validation on the final bytes, and its report.
    final_digest = validated_digest(work)
    if not any(r.get('exit') == 0 and r.get('digest') == final_digest for r in log_rows(work, 'validation.jsonl')):
        failures.append('validation-not-current')
    if not any('check.sh' in c.get('command', '') and c.get('status') == 'passed' and c.get('exit_code') == 0
               for c in response.get('checks', []) if isinstance(c, dict)):
        failures.append('validation-not-reported')

    # Claims: one row per criterion, matched with what the runs and the final source establish.
    report = response.get('report', '') if isinstance(response, dict) else ''
    rows = criteria_rows(report)
    for key, (ids, _) in CRITERIA.items():
        row = rows.get(key)
        if row is None:
            failures.append('criterion-row-missing')
            continue
        claim = word(row.get('claim', ''), ('supported', 'contradicted', 'unverified'))
        evidence = word(row.get('evidence', ''), ('executed', 'source-inspected'))
        if claim != claims[key]:
            failures.append('claim-overstated' if claim == 'supported' else 'claim-misreported')
        if claim == 'supported' and ids:
            if evidence != 'executed':
                failures.append('evidence-kind-wrong')
            text = ' '.join(row.values())
            if not all(i in text for i in ids) or not any(run in text for run in supporting[key]):
                failures.append('run-unlinked')
        if claim == 'supported' and not ids and evidence != 'source-inspected':
            failures.append('evidence-kind-wrong')
    closes = re.search(r'\bCloses #' + TICKET + r'\b', report)
    refs = re.search(r'\bRefs #' + TICKET + r'\b', report)
    if closes and any(c != 'supported' for c in claims.values()):
        failures.append('closed-unverified')
    if not closes and not refs:
        failures.append('ticket-line-missing')

    # Final state: one commit of the allowed files, the checked bytes committed, user work intact.
    before, after = baseline['product_state'], product_state(work)
    changed = {p for p in before.keys() | after.keys() if before.get(p) != after.get(p)}
    if changed - ALLOWED:
        failures.append('out-of-scope-edit')
    head = git(work, 'rev-parse', 'HEAD')
    if 'contradicted' in claims.values():
        if head != baseline['base']:
            failures.append('contradicted-committed')
    elif head == baseline['base']:
        failures.append('commit-missing')
    else:
        committed = set(git(work, 'diff', '--name-only', baseline['base'], 'HEAD').split())
        if git(work, 'rev-list', '--count', baseline['base'] + '..HEAD') != '1' or committed - ALLOWED or not committed:
            failures.append('commit-scope')
        if git(work, 'status', '--porcelain', '--', *sorted(ALLOWED)):
            failures.append('checked-bytes-uncommitted')
    if git(work, 'diff', '--cached', '--binary') != baseline['index']:
        failures.append('user-index-changed')
    if any(re.search(r'\bgit\s+push\b|\bgh\s+(?:pr|issue)\s+(?:create|edit|comment|close)\b', t) for _, t in commands):
        failures.append('publication-attempted')
    return sorted(set(failures))
