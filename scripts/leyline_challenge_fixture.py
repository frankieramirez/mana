#!/usr/bin/env python3
"""Build a synthetic project with a generated control for Leyline challenge acceptance.

The project starts a real local HTTP server as an owned child process, reads it through
a stand-in browser executable kept outside the checkout, and reports Vitest-shaped JSON
from actual Node assertions. The control is generated and installed by Leyline itself.
Nothing here is a consumer, a deployed service, or a real browser.

    python3 scripts/leyline_challenge_fixture.py DIR

prints the repository, plan, environment and challenge command for a fixture in DIR.
"""

import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
GENERATOR = ROOT / "skills/leyline/scripts/generate.sh"
CHALLENGE = ROOT / "skills/leyline/scripts/challenge.sh"
SCENARIOS = ("briefing.return-summary", "briefing.no-activity")

BRIEFING = """export function briefing(workers) {
  return {
    produced: workers.reduce((sum, worker) => sum + worker.produced, 0),
    workers: workers.map(worker => worker.name),
    message: workers.length ? 'Welcome back' : 'No activity',
  };
}
"""

SERVER = r"""import http from 'node:http';
import {readFile} from 'node:fs/promises';
import {spawnSync} from 'node:child_process';
import {briefing} from './briefing.mjs';

const [token, store] = process.argv.slice(2);
const preferred = Number(process.env.FIXTURE_PREFERRED_PORT || 0);
const server = http.createServer(async (request, response) => {
  const url = new URL(request.url, 'http://fixture.invalid');
  const workers = async () => url.searchParams.get('empty') ? [] : JSON.parse(await readFile(store, 'utf8'));
  if (url.pathname === '/health') return response.end(JSON.stringify({service: 'briefing-fixture', token}));
  if (url.pathname === '/briefing') { response.writeHead(302, {location: '/kingdom' + url.search}); return response.end(); }
  if (url.pathname === '/api/kingdom') {
    response.setHeader('content-type', 'application/json');
    return response.end(JSON.stringify(briefing(await workers())));
  }
  if (url.pathname === '/kingdom') {
    const summary = briefing(await workers());
    response.setHeader('content-type', 'text/html');
    return response.end(`<main><h1>${summary.message}</h1><p>Produced ${summary.produced}</p></main>`);
  }
  response.writeHead(404);
  response.end();
});
function listen(port) {
  return new Promise((resolve, reject) => {
    server.once('error', reject);
    server.listen(port, '127.0.0.1', () => { server.off('error', reject); resolve(); });
  });
}
// A careless fixture clears its preferred port by pattern. The challenge must catch it.
function evict() {
  const table = spawnSync('ps', ['-A', '-o', 'pid=,args='], {encoding: 'utf8'}).stdout || '';
  for (const line of table.split('\n')) {
    const [pid, ...args] = line.trim().split(/\s+/);
    if (args.join(' ').includes('leyline-challenge-sentinel')) try { process.kill(Number(pid), 'SIGTERM'); } catch {}
  }
}
let preferredBusy = false;
try {
  await listen(preferred);
} catch (error) {
  if (error.code !== 'EADDRINUSE' || !preferred) throw error;
  preferredBusy = true;
  if (process.env.LEYLINE_FIXTURE_MODE === 'evict') evict();
  await listen(0);  // Never take an occupied port; bind a fresh one this run owns.
}
process.on('SIGTERM', () => { server.close(() => process.exit(0)); server.closeAllConnections(); });
process.stdout.write(JSON.stringify({port: server.address().port, preferred, preferredBusy}) + '\n');
"""

PROBE = r"""import {spawnSync} from 'node:child_process';
const browser = process.env.FIXTURE_BROWSER;
if (!browser) { console.error('chromium is unavailable: FIXTURE_BROWSER is not set'); process.exit(1); }
const result = spawnSync(browser, ['--version'], {encoding: 'utf8', timeout: 10000});
if (result.error || result.status !== 0 || !/Chromium/.test(result.stdout)) {
  console.error(`chromium is unavailable at ${browser}`);
  process.exit(1);
}
console.log(result.stdout.trim());
"""

BROWSER = r"""#!/usr/bin/env node
// Synthetic stand-in for a browser: it follows redirects and prints the final document.
const [flag, address] = process.argv.slice(2);
if (flag === '--version') { console.log('Chromium 0.0 synthetic fixture'); process.exit(0); }
if (flag !== '--dump-dom' || !address) { console.error('usage: chromium --version | --dump-dom URL'); process.exit(2); }
const response = await fetch(address, {redirect: 'follow'});
console.log(response.url);
console.log(await response.text());
"""

RUNNER = r"""import assert from 'node:assert/strict';
import {spawn, spawnSync} from 'node:child_process';
import {mkdtemp, readFile, rename, writeFile, rm} from 'node:fs/promises';
import {existsSync, rmSync} from 'node:fs';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {randomUUID} from 'node:crypto';

const destination = process.argv[2];
assert.ok(destination, 'runner report destination is required');
const mode = process.env.LEYLINE_FIXTURE_MODE || 'normal';
const tests = [];
function scenario(id, _kind, run) { tests.push({id, run}); }

let base = null;
async function api(path) {
  const response = await fetch(base + path);
  assert.equal(response.status, 200);
  return response.json();
}
function browse(path) {
  const result = spawnSync(process.env.FIXTURE_BROWSER, ['--dump-dom', base + path], {encoding: 'utf8', timeout: 10000});
  assert.equal(result.status, 0, result.stderr);
  const [finalUrl, ...body] = result.stdout.split('\n');
  return {url: new URL(finalUrl), text: body.join('\n')};
}

scenario('briefing.return-summary', 'api+browser', async () => {
  const summary = await api('/api/kingdom');
  assert.equal(summary.produced, 5);
  assert.deepEqual(summary.workers, ['mill', 'mine']);
  assert.equal(summary.message, 'Welcome back');
  const page = browse('/briefing');
  assert.equal(page.url.pathname, '/kingdom');
  assert.match(page.text, /<h1>Welcome back<\/h1>/);
  assert.match(page.text, /Produced 5/);
});
scenario('briefing.no-activity', 'api', async () => {
  const summary = await api('/api/kingdom?empty=1');
  assert.equal(summary.produced, 0);
  assert.deepEqual(summary.workers, []);
  assert.equal(summary.message, 'No activity');
});

const started = Date.now();
const fixture = await mkdtemp(join(tmpdir(), 'briefing-fixture-'));
const store = join(fixture, 'workers.json');
await writeFile(store, await readFile('fixtures/ready.json', 'utf8'));
const token = randomUUID();
const lifecycle = {runnerPid: process.pid, serverPid: null, port: null, preferredPort: null, preferredBusy: null,
  tempPath: fixture, serverStopped: false, cleaned: false};
const assertions = [];
let teardownError = '';

const server = spawn(process.execPath, ['src/hosted/server.mjs', token, store], {stdio: ['ignore', 'pipe', 'inherit']});
lifecycle.serverPid = server.pid;
// Cancellation still stops the server and releases this run's temporary store.
for (const signal of ['SIGINT', 'SIGTERM']) process.on(signal, () => {
  try { server.kill('SIGKILL'); } catch {}
  rmSync(fixture, {recursive: true, force: true});
  process.exit(signal === 'SIGINT' ? 130 : 143);
});
const exited = new Promise(resolve => server.once('exit', resolve));
try {
  const line = await new Promise((resolve, reject) => {
    let text = '';
    const timer = setTimeout(() => reject(new Error('fixture server did not report its port')), 10000);
    server.stdout.on('data', chunk => {
      text += chunk;
      if (text.includes('\n')) { clearTimeout(timer); resolve(text.split('\n')[0]); }
    });
    server.once('exit', code => { clearTimeout(timer); reject(new Error(`fixture server exited ${code}`)); });
  });
  const bound = JSON.parse(line);
  Object.assign(lifecycle, {port: bound.port, preferredPort: bound.preferred, preferredBusy: bound.preferredBusy});
  base = `http://127.0.0.1:${bound.port}`;
  // Bounded readiness: the service must answer with this run's identity.
  const deadline = Date.now() + 10000;
  for (;;) {
    try { if ((await (await fetch(base + '/health')).json()).token === token) break; } catch {}
    assert.ok(Date.now() < deadline, 'fixture server never became ready');
    await new Promise(resolve => setTimeout(resolve, 20));
  }
  console.error('fixture ready ' + JSON.stringify(lifecycle));
  if (mode === 'leak') {
    const stray = spawn(process.execPath, ['-e', 'setInterval(() => {}, 1000)'], {detached: true, stdio: 'ignore'});
    stray.unref();
    await writeFile(process.env.LEYLINE_FIXTURE_LEAK_FILE, String(stray.pid));
    await new Promise(resolve => setTimeout(resolve, 400));
  }
  if (mode === 'escape') await writeFile(process.env.LEYLINE_FIXTURE_ESCAPE_PATH, 'written from outside the snapshot\n');
  const sync = process.env.LEYLINE_FIXTURE_SYNC_DIR;
  if (sync) {
    // Rename into place so a poller that sees the file never reads it half written.
    await writeFile(join(sync, 'ready.tmp'), JSON.stringify(lifecycle));
    await rename(join(sync, 'ready.tmp'), join(sync, 'ready'));
    const wait = Date.now() + 30000;
    while (!existsSync(join(sync, 'release'))) {
      assert.ok(Date.now() < wait, 'challenge handshake timed out');
      await new Promise(resolve => setTimeout(resolve, 10));
    }
  }
  if (mode !== 'zero') {
    for (const test of tests) {
      const assertion = {title: test.id, fullName: `briefing ${test.id}`, ancestorTitles: ['briefing'],
        status: 'passed', duration: 0, failureMessages: []};
      const begin = Date.now();
      try { await test.run(); }
      catch (error) { assertion.status = 'failed'; assertion.failureMessages = [String(error)]; }
      assertion.duration = Date.now() - begin;
      assertions.push(assertion);
    }
  }
} finally {
  if (mode === 'teardown-fail') {
    teardownError = 'afterAll: the fixture server did not stop';
  } else {
    server.kill('SIGTERM');
    let timer;
    const stopped = await Promise.race([exited.then(() => true), new Promise(resolve => { timer = setTimeout(() => resolve(false), 5000); })]);
    clearTimeout(timer);
    lifecycle.serverStopped = stopped;
    if (!stopped) teardownError = 'afterAll: the fixture server ignored SIGTERM';
  }
  await rm(fixture, {recursive: true, force: true});
  lifecycle.cleaned = !existsSync(fixture);
}
const failed = assertions.filter(item => item.status === 'failed').length;
const report = {
  success: failed === 0 && !teardownError, startTime: started, numTotalTestSuites: 1,
  numPassedTestSuites: failed || teardownError ? 0 : 1, numFailedTestSuites: failed || teardownError ? 1 : 0,
  numTotalTests: assertions.length, numPassedTests: assertions.length - failed,
  numFailedTests: failed, numPendingTests: 0, numTodoTests: 0,
  testResults: [{name: 'tests/hosted/briefing.test.mjs', status: failed || teardownError ? 'failed' : 'passed',
    startTime: started, endTime: Date.now(), message: teardownError, assertionResults: assertions}],
  fixtureLifecycle: lifecycle,
};
await writeFile(destination, JSON.stringify(report));
process.exitCode = failed || teardownError ? 1 : 0;
if (mode === 'teardown-fail') process.exit();  // The server child stays behind for the control to reap.
"""

PLAN = {
    "feature": "briefing",
    "timeoutSeconds": 60,
    "occupiedPortEnv": "FIXTURE_PREFERRED_PORT",
    "syncEnv": "LEYLINE_FIXTURE_SYNC_DIR",
    "variants": [
        {"name": "missing-browser", "env": {"FIXTURE_BROWSER": None},
         "expect": {"status": "incomplete", "missing": ["chromium"]}},
        {"name": "missing-fixture", "remove": ["fixtures/ready.json"],
         "expect": {"status": "incomplete", "missing": ["fixture-assets"]}},
        {"name": "zero-cases", "env": {"LEYLINE_FIXTURE_MODE": "zero"}, "expect": {"status": "incomplete"}},
        {"name": "source-mutation", "break": True, "mutate": {"path": "src/hosted/briefing.mjs"},
         "expect": {"status": "incomplete", "sourceChanged": True, "failed": ["briefing.return-summary"]}},
        {"name": "teardown-failure", "break": True, "env": {"LEYLINE_FIXTURE_MODE": "teardown-fail"},
         "expect": {"status": "incomplete", "failed": ["briefing.return-summary"]}},
    ],
}


def write(root, relative, content, mode=None):
    target = Path(root, relative)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    if mode:
        target.chmod(mode)
    return target


class Fixture:
    """A committed synthetic checkout with an installed generated control."""

    def __init__(self, base):
        self.base = Path(base).resolve()
        self.repo = self.base / "app"
        self.tmp = self.base / "tmp"
        self.browser = self.base / "bin" / "chromium"
        self.plan_path = self.base / "challenge-plan.json"
        self.env = {k: v for k, v in os.environ.items() if not k.startswith(("GIT_", "LEYLINE_FIXTURE_", "FIXTURE_"))}
        self.env.update(GIT_AUTHOR_NAME="Fixture", GIT_AUTHOR_EMAIL="fixture@example.test",
                        GIT_COMMITTER_NAME="Fixture", GIT_COMMITTER_EMAIL="fixture@example.test",
                        GIT_OPTIONAL_LOCKS="0", TMPDIR=str(self.tmp), FIXTURE_BROWSER=str(self.browser))

    def run(self, argv, check=True, **kwargs):
        result = subprocess.run([str(a) for a in argv], cwd=self.repo, env=self.env, capture_output=True, text=True, **kwargs)
        if check and result.returncode:
            raise RuntimeError(f"{argv} exited {result.returncode}: {result.stdout[-2000:]} {result.stderr[-2000:]}")
        return result

    def git(self, *args):
        return self.run(["git", *args])

    def build(self, plan=None, install=True):
        self.repo.mkdir(parents=True)
        self.tmp.mkdir()
        write(self.base, "bin/chromium", BROWSER, stat.S_IRWXU)
        write(self.repo, "AGENTS.md", "# Hosted app\n\nHuman-owned guidance.\n\n## Agent skills\n\nValidation: `npm run --silent verify -- release --json`\n")
        write(self.repo, "package.json", json.dumps({"name": "challenge-fixture", "type": "module", "private": True}))
        write(self.repo, "src/hosted/briefing.mjs", BRIEFING)
        write(self.repo, "src/hosted/server.mjs", SERVER)
        write(self.repo, "tests/hosted/briefing.test.mjs", RUNNER)
        write(self.repo, "tests/hosted/browser-probe.mjs", PROBE)
        write(self.repo, "fixtures/ready.json", '[{"name":"mill","produced":2},{"name":"mine","produced":3}]\n')
        self.git("init", "-q")
        self.git("add", ".")
        self.git("commit", "-qm", "synthetic hosted fixture")
        write(self.repo, "src/hosted/briefing.mjs", BRIEFING.replace("'Welcome back'", "'Old summary'"))
        patch = self.git("diff", "--", "src/hosted/briefing.mjs").stdout
        write(self.repo, "src/hosted/briefing.mjs", BRIEFING)
        write(self.repo, "control-inputs/briefing.return-summary.patch", patch)
        self.git("add", ".")
        self.git("commit", "-qm", "declared behavior break")
        spec = {
            "project": "challenge-fixture",
            "feature": {"id": "briefing", "summary": "Read a return summary in the kingdom overview",
                        "aliases": ["welcome back", "came back", "empty briefing"],
                        "sourceRoots": ["src/hosted", "fixtures/ready.json"], "knowledge": "proposed",
                        "reach": [{"route": "/kingdom", "steps": ["Open /briefing and follow its redirect."]}]},
            "scenarios": [
                {"id": SCENARIOS[0], "steps": [{"action": "Return after two workers produced resources.",
                                                "expect": "The API and the rendered overview show their total and a welcome."}]},
                {"id": SCENARIOS[1], "steps": [{"action": "Request an account with no workers.",
                                                "expect": "The API reports zero production and no workers."}]},
            ],
            "bindings": ["tests/hosted/briefing.test.mjs"],
            "runner": {"argv": ["node", "tests/hosted/briefing.test.mjs", "{report}"], "format": "vitest-json"},
            "prerequisites": [{"need": "fixture-assets", "path": "fixtures/ready.json"},
                              {"need": "chromium", "probe": {"argv": ["node", "tests/hosted/browser-probe.mjs"]}}],
            "timeoutSeconds": 20,
            "release": None,
            "break": {"scenario": SCENARIOS[0], "path": "control-inputs/briefing.return-summary.patch"},
        }
        spec_path = write(self.base, "spec.json", json.dumps(spec))
        self.map_path = self.base / "map.json"
        self.run(["bash", GENERATOR, "map", self.repo, "--spec", spec_path, "--out", self.map_path])
        if not install:
            return self
        self.run(["bash", GENERATOR, "install", self.repo, "--map", self.map_path])
        self.git("add", ".")
        self.git("commit", "-qm", "install generated control")
        self.plan_path.write_text(json.dumps(plan or PLAN, indent=2))
        return self

    def challenge(self, *extra, evidence=None, plan=True):
        argv = ["bash", CHALLENGE, self.repo, "--trust", "--timeout", "60"]
        if plan:
            argv += ["--plan", self.plan_path]
        if evidence is not None:
            argv += ["--evidence", evidence]
        result = self.run([*argv, *extra], check=False, timeout=600)
        try:
            doc = json.loads(result.stdout)
        except ValueError:
            doc = None
        return result.returncode, doc, result


def main(argv):
    if len(argv) != 1:
        print(__doc__.strip(), file=sys.stderr)
        return 2
    if shutil.which("node") is None:
        print("Node 22.13 or newer is required", file=sys.stderr)
        return 4
    fixture = Fixture(argv[0]).build()
    print(json.dumps({"repo": str(fixture.repo), "plan": str(fixture.plan_path),
                      "env": {"TMPDIR": fixture.env["TMPDIR"], "FIXTURE_BROWSER": fixture.env["FIXTURE_BROWSER"]},
                      "command": ["bash", str(CHALLENGE), str(fixture.repo), "--trust", "--plan", str(fixture.plan_path)]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
