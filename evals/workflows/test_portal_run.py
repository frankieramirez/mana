import importlib.util
import json
import os
import configparser
from pathlib import Path
import subprocess
import tempfile
import unittest

spec = importlib.util.spec_from_file_location('portal_workflow_fixture', Path(__file__).with_name('run.py'))
fixture = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fixture)
ROOT = Path(__file__).resolve().parents[2]
HELPER = ROOT / 'skills/portal/scripts/run-state.sh'


class Continuation(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='mana portal run ')
        self.addCleanup(self.temp.cleanup)
        self.repo = Path(self.temp.name) / 'repo'
        self.repo.mkdir()
        fixture.git(self.repo, 'init', '-q', '-b', 'main')
        fixture.git(self.repo, 'config', 'user.name', 'Fixture')
        fixture.git(self.repo, 'config', 'user.email', 'fixture@example.invalid')
        (self.repo / 'app.txt').write_text('baseline\n')
        fixture.git(self.repo, 'add', 'app.txt')
        fixture.git(self.repo, 'commit', '-qm', 'Baseline')
        self.scope = 'github:github.com/fixture/mana#10'

    def helper(self, *args, ok=True, cwd=None, env=None):
        result = subprocess.run(['bash', str(HELPER), *args], cwd=cwd or self.repo,
                                env=env, text=True, capture_output=True)
        if ok:
            self.assertEqual(result.returncode, 0, result.stderr)
        else:
            self.assertNotEqual(result.returncode, 0)
        return result

    def start(self, owner='run-a', actions='implement,verify,commit'):
        return self.helper('start', self.scope, owner, 'build', actions, 'Prepare named effort').stdout.strip()

    def test_one_coordinator_per_scope_across_worktrees(self):
        state = self.start()
        self.assertTrue(Path(state).is_file())
        second = self.repo.parent / 'second'
        fixture.git(self.repo, 'worktree', 'add', '-qb', 'codex/second', str(second), 'HEAD')
        self.helper('start', self.scope, 'run-b', 'build', 'implement', 'Prepare named effort', ok=False, cwd=second)
        self.helper('stop', self.scope, 'run-b', 'cancelled', ok=False)
        self.helper('stop', self.scope, 'run-a', 'cancelled')
        self.start('run-b', 'verify')
        snapshot = self.helper('show', self.scope).stdout
        self.assertIn('run.actions=verify', snapshot)
        self.assertIn('run.version=1', snapshot)

    def test_cancel_resume_keeps_workspace_and_commit_without_duplicate_effects(self):
        self.start()
        unit = self.repo.parent / 'unit-11'
        self.helper('record', self.scope, 'run-a', '11', 'reserved', str(unit), 'codex/unit-11', '-', '-', '-')
        fixture.git(self.repo, 'worktree', 'add', '-qb', 'codex/unit-11', str(unit), 'HEAD')
        (unit / 'app.txt').write_text('verified unit 11\n')
        fixture.git(unit, 'commit', '-qam', 'Unit 11')
        commit = fixture.git(unit, 'rev-parse', 'HEAD').strip()
        evidence = unit / 'check.txt'
        evidence.write_text('check exit 0\n')
        self.helper('record', self.scope, 'run-a', '11', 'verified', str(unit), 'codex/unit-11', commit, '-', str(evidence))
        (unit / 'draft.txt').write_text('preserve this edit\n')
        self.helper('stop', self.scope, 'run-a', 'cancelled')
        self.start('run-b')
        snapshot = self.helper('show', self.scope).stdout
        self.assertIn('unit.11.commit=' + commit, snapshot)
        self.assertIn('unit.11.status=verified', snapshot)
        self.assertEqual((unit / 'draft.txt').read_text(), 'preserve this edit\n')
        self.helper('record', self.scope, 'run-b', '12', 'reserved', str(unit), 'codex/unit-12', '-', '-', '-', ok=False)
        self.helper('record', self.scope, 'run-b', '12', 'reserved', str(unit.parent / 'unit-12'), 'codex/unit-11', '-', '-', '-', ok=False)
        self.assertEqual(fixture.git(unit, 'rev-parse', 'HEAD').strip(), commit)
        self.assertEqual(fixture.git(self.repo, 'branch', '--show-current').strip(), 'main')
        self.assertEqual((self.repo / 'app.txt').read_text(), 'baseline\n')

    def test_verified_record_requires_actual_commit_branch_and_evidence(self):
        self.start()
        unit = self.repo.parent / 'verified-11'
        branch = 'codex/verified-11'
        fixture.git(self.repo,'worktree','add','-qb',branch,str(unit),'HEAD')
        head = fixture.git(unit,'rev-parse','HEAD')
        evidence = unit / 'check.txt'
        self.helper('record',self.scope,'run-a','11','verified',str(unit),branch,head,'-',str(evidence),ok=False)
        evidence.write_text('unit verification exit 0\n')
        self.helper('record',self.scope,'run-a','11','verified',str(unit),'codex/changed',head,'-',str(evidence),ok=False)
        self.helper('record',self.scope,'run-a','11','verified',str(unit),branch,'0000000000000000000000000000000000000000','-',str(evidence),ok=False)
        self.helper('record',self.scope,'run-a','11','awaiting-review',str(unit),branch,head,'-',str(evidence),ok=False)
        self.helper('record',self.scope,'run-a','11','verified',str(unit),branch,head,'-',str(evidence))
        self.helper('record',self.scope,'run-a','11','reserved',str(unit),branch,'-','-','-',ok=False)

    def test_scope_identity_and_schema_cannot_be_silently_reused(self):
        path = Path(self.start())
        self.helper('stop',self.scope,'run-a','cancelled')
        self.helper('start',self.scope,'run-b','map','decide','Different destination',ok=False)
        self.start('run-b')
        self.helper('stop',self.scope,'run-b','cancelled')
        fixture.git(self.repo,'config','--file',str(path),'run.version','9')
        self.helper('show',self.scope,ok=False)

    def test_inherited_git_environment_keeps_state_and_lock_in_current_repository(self):
        foreign = self.repo.parent / 'foreign'
        foreign.mkdir()
        fixture.git(foreign, 'init', '-q', '-b', 'main')
        foreign_git = foreign / '.git'
        config = self.repo.parent / 'foreign.config'
        config.write_text('[core]\n\tworktree = "' + str(foreign) + '"\n')
        environments = {
            'GIT_DIR': {'GIT_DIR': str(foreign_git)},
            'GIT_COMMON_DIR': {'GIT_COMMON_DIR': str(foreign_git)},
            'GIT_WORK_TREE': {'GIT_WORK_TREE': str(foreign)},
            'GIT_INDEX_FILE': {'GIT_INDEX_FILE': str(foreign_git / 'index')},
            'GIT_OBJECT_DIRECTORY': {'GIT_OBJECT_DIRECTORY': str(foreign_git / 'objects')},
            'GIT_ALTERNATE_OBJECT_DIRECTORIES': {'GIT_ALTERNATE_OBJECT_DIRECTORIES': str(foreign_git / 'objects')},
            'GIT_CONFIG': {'GIT_CONFIG': str(config)},
            'GIT_CONFIG_PARAMETERS': {'GIT_CONFIG_PARAMETERS': "'core.worktree=" + str(foreign) + "'"},
            'GIT_CONFIG_COUNT': {'GIT_CONFIG_COUNT': '1', 'GIT_CONFIG_KEY_0': 'core.worktree',
                                 'GIT_CONFIG_VALUE_0': str(foreign)},
        }
        for name, inherited in environments.items():
            with self.subTest(variable=name):
                scope = self.scope + ':' + name
                env = dict(os.environ, **inherited)
                path = Path(self.helper('start', scope, 'run-a', 'build', 'implement',
                                        'Prepare named effort', env=env).stdout.strip())
                self.assertEqual(path.parent.parent, self.repo / '.git/mana-portal')
                self.assertEqual((path.parent / 'lock/owner').read_text().strip(), 'run-a')
                snapshot = self.helper('show', scope, env=env).stdout
                self.assertIn('run.original=' + str(self.repo), snapshot)
                self.assertIn('run.repository=' + str(self.repo / '.git'), snapshot)
                self.helper('stop', scope, 'run-a', 'cancelled', env=env)
                self.assertFalse((path.parent / 'lock').exists())
                self.assertFalse((foreign_git / 'mana-portal').exists())

    def test_workspace_verification_ignores_inherited_repository_context(self):
        self.start()
        foreign = self.repo.parent / 'foreign'
        foreign.mkdir()
        fixture.git(foreign, 'init', '-q', '-b', 'main')
        evidence = foreign / 'check.txt'
        evidence.write_text('unit verification exit 0\n')
        head = fixture.git(self.repo, 'rev-parse', 'HEAD')
        env = dict(os.environ, GIT_DIR=str(self.repo / '.git'), GIT_WORK_TREE=str(self.repo))
        rejected = self.helper('record', self.scope, 'run-a', '11', 'verified', str(foreign),
                               'main', head, '-', str(evidence), env=env, ok=False)
        self.assertIn('workspace belongs to another repository', rejected.stderr)
        unit = self.repo.parent / 'unit-11'
        branch = 'codex/unit-11'
        fixture.git(self.repo, 'worktree', 'add', '-qb', branch, str(unit), 'HEAD')
        env = dict(os.environ, GIT_DIR=str(foreign / '.git'),
                   GIT_COMMON_DIR=str(foreign / '.git'), GIT_WORK_TREE=str(foreign),
                   GIT_INDEX_FILE=str(foreign / '.git/index'),
                   GIT_OBJECT_DIRECTORY=str(foreign / '.git/objects'))
        self.helper('record', self.scope, 'run-a', '11', 'verified', str(unit),
                    branch, head, '-', str(evidence), env=env)
        self.assertIn('unit.11.status=verified', self.helper('show', self.scope, env=env).stdout)

    def test_git_environment_discovery_fails_closed_and_help_needs_no_git(self):
        bin_path = self.repo.parent / 'bin'
        bin_path.mkdir()
        git = bin_path / 'git'
        git.write_text('#!/usr/bin/env bash\nexit 97\n')
        git.chmod(0o755)
        env = dict(os.environ, PATH=str(bin_path) + ':' + os.environ['PATH'])
        self.assertIn('Local portal continuation state', self.helper('--help', env=env).stdout)
        result = self.helper('start', self.scope, 'run-a', 'build', 'implement',
                             'Prepare named effort', env=env, ok=False)
        self.assertIn('cannot identify repository-local Git environment', result.stderr)
        self.assertFalse((self.repo / '.git/mana-portal').exists())


class TrackerFrontier(unittest.TestCase):
    helper = Continuation.helper
    start = Continuation.start

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='mana frontier fixture ')
        self.addCleanup(self.temp.cleanup)
        self.case = next(c for c in fixture.load_cases() if c['id'] == 'portal-run-independent')
        self.repo, self.baseline = fixture.prepare(self.case, Path(self.temp.name))
        self.scope = 'github:github.com/fixture/mana#10'
        self.env = fixture.clean_env(self.repo / 'home')
        self.env['PATH'] = str(self.repo / 'bin') + ':/usr/bin:/bin'
        self.env['TMPDIR'] = str(self.repo / 'artifacts')

    def adapter(self, *args, ok=True):
        result = subprocess.run(['bash', str(self.repo / 'installed/portal/scripts/tickets.sh'),
                                 '--repo', 'fixture/mana', *args], cwd=self.repo, env=self.env,
                                capture_output=True, text=True)
        if ok:
            self.assertEqual(result.returncode, 0, result.stderr)
        return result

    def tracker(self, **changes):
        path = self.repo / 'artifacts/tracker.json'
        data = json.loads(path.read_text())
        data.update(changes)
        path.write_text(json.dumps(data))
        return data

    def test_native_dependency_read_failure_is_unknown(self):
        self.tracker(dependency_fail=['13'])
        result = self.adapter('blocked', '13', ok=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('cannot read', result.stderr)

    def test_two_independent_units_have_distinct_workspaces_evidence_and_open_prs(self):
        self.start()
        self.assertEqual(self.adapter('children','10').stdout.splitlines()[0].split('\t')[0], '11')
        records = {}
        for n in ('11','12'):
            self.assertIn('state\tOPEN', self.adapter('view', n).stdout)
            self.assertEqual(self.adapter('blocked', n, ok=False).returncode, 1)
            self.adapter('claim', n)
            self.assertIn('assignees\tfixture', self.adapter('view', n).stdout)
            path = self.repo / 'artifacts/workspaces' / n
            branch = 'codex/unit-' + n
            self.helper('record', self.scope, 'run-a', n, 'reserved', str(path), branch, '-', '-', '-')
            fixture.git(self.repo, 'fetch', '-q', 'origin', 'main')
            fixture.git(self.repo, 'worktree', 'add', '-qb', branch, str(path), 'origin/main')
            (path / ('unit'+n+'.txt')).write_text('new'+n+'\n')
            check = subprocess.run(['bash','check.sh',n],cwd=path,capture_output=True,text=True)
            self.assertEqual(check.returncode,0)
            evidence = self.repo / ('artifacts/unit-'+n+'.txt')
            evidence.write_text(check.stdout)
            fixture.git(path,'add','unit'+n+'.txt')
            fixture.git(path,'commit','-qm','Prepare unit '+n)
            commit = fixture.git(path,'rev-parse','HEAD')
            pr = 'https://github.com/fixture/mana/pull/'+str(int(n)+100)
            data = self.tracker()
            data['prs'][str(int(n)+100)] = {'state':'OPEN','url':pr,'headRefOid':commit,'baseRefName':'main','mergedAt':None}
            self.tracker(**data)
            observed = subprocess.run(['gh','pr','view',str(int(n)+100),'--json','state,url,headRefOid,baseRefName,mergedAt'],env=self.env,cwd=path,text=True,capture_output=True)
            self.assertEqual(json.loads(observed.stdout)['state'],'OPEN')
            self.helper('record', self.scope,'run-a',n,'awaiting-review',str(path),branch,commit,pr,str(evidence))
            records[n] = commit
            self.assertEqual(self.adapter('blocked','13').stdout.strip(),'11')
            self.adapter('children','10')
        self.helper('stop',self.scope,'run-a','awaiting review; dependency 13 open; 14 held; 15 unready')
        snapshot = self.helper('show',self.scope).stdout
        self.assertEqual(snapshot.count('status=awaiting-review'),2)
        self.assertEqual(len(set(records.values())),2)
        self.assertEqual(fixture.git(self.repo,'rev-parse','HEAD'),self.baseline['head'])
        self.assertEqual((self.repo/'unit11.txt').read_text(),'old\n')
        data = self.tracker()
        for n in ('13','15','99'):
            self.assertEqual(data['issues'][n]['assignees'],[])
        self.assertEqual(data['issues']['14']['assignees'],['other'])
        response = {'report':'cast absent; open PRs awaiting review','checks':[]}
        commands = [{'command':'bash check.sh '+n,'exit_code':0,'aggregated_output':'unit '+n+' verified'} for n in ('11','12')]
        self.assertEqual(fixture.grade_portal_fixture(self.case,self.repo,self.baseline,response,commands),[])
        self.assertIn('unit check not observed: 12',fixture.grade_portal_fixture(self.case,self.repo,self.baseline,response,commands[:1]))
        evidence.write_text('Commands: bash check.sh 12 (exit 0). Checked commit: '+records['12'])
        self.assertEqual(fixture.grade_portal_fixture(self.case,self.repo,self.baseline,response,commands),[])
        evidence.write_text('')
        self.assertIn('unit verification evidence missing: 12',fixture.grade_portal_fixture(self.case,self.repo,self.baseline,response,commands))
        evidence.write_text('unit 12 verified')
        data['issues']['11']['state']='CLOSED'; self.tracker(**data)
        self.assertIn('prepared unit was falsely closed: 11',fixture.grade_portal_fixture(self.case,self.repo,self.baseline,response,commands))

    def test_claim_race_releases_our_assignment_and_new_dependency_stays_blocked(self):
        self.tracker(claim_race='12')
        result = self.adapter('claim','12',ok=False)
        self.assertNotEqual(result.returncode,0)
        self.assertIn('other',result.stderr)
        self.assertEqual(self.tracker()['issues']['12']['assignees'],['other'])
        self.tracker(claim_race='',block_after_claim='11')
        self.adapter('claim','11')
        self.assertEqual(self.adapter('blocked','11').stdout.strip(),'11')

    def test_changed_membership_and_remote_are_read_before_resume(self):
        self.start()
        self.adapter('claim','11')
        data = self.tracker()
        data['issues']['12']['parent']=None
        data['issues']['12']['body']='Moved to another effort.'
        self.tracker(**data)
        self.assertNotIn('12', [x.split('\t')[0] for x in self.adapter('children','10').stdout.splitlines()])
        previous = fixture.git(self.repo,'rev-parse','origin/main')
        advanced = fixture.git(self.repo,'commit-tree','HEAD^{tree}','-p',previous,'-m','Concurrent base')
        fixture.git(self.repo,'push','-q','origin',advanced+':refs/heads/main')
        fixture.git(self.repo,'fetch','-q','origin','main')
        self.assertEqual(fixture.git(self.repo,'rev-parse','origin/main'),advanced)
        self.assertNotEqual(previous,advanced)
        self.helper('stop',self.scope,'run-a','remote changed; reconcile before continuation')
        self.start('run-b','verify')
        self.assertIn('run.actions=verify',self.helper('show',self.scope).stdout)
        self.assertEqual(fixture.git(self.repo,'rev-parse','HEAD'),self.baseline['head'])

    def test_map_frontier_reaches_destination_without_claiming_build(self):
        script = self.repo / 'installed/portal/scripts/map.sh'
        def map_call(*args):
            result = subprocess.run(['bash',str(script),*args,'fixture/mana'],cwd=self.repo,env=self.env,text=True,capture_output=True)
            self.assertEqual(result.returncode,0,result.stderr)
            return result.stdout
        self.assertEqual(map_call('frontier','20').split('\t')[0],'21')
        map_call('claim','21')
        (self.repo/'decision.md').write_text('Use stable ids.\n')
        self.adapter('comment','21')
        map_call('close','21')
        data = self.tracker();data['issues']['20']['body']='## Destination\nRecord the stable-id decision in decision.md.\n\n## Decisions so far\nUse stable ids.\n\n## Not yet specified\nNone.\n\n## Completion\nDestination verified in decision.md.\n'
        self.tracker(**data)
        map_call('close-map','20')
        case = next(c for c in fixture.load_cases() if c['id']=='portal-run-map')
        self.assertEqual(fixture.grade_portal_fixture(case,self.repo,self.baseline,{'report':'Decision destination complete','checks':[]},[]),[])
        self.assertEqual(self.tracker()['issues']['11']['assignees'],[])

    def test_workspace_stop_grader_requires_no_claims(self):
        case = next(c for c in fixture.load_cases() if c['id']=='portal-run-no-workspace')
        response = {'report':'Workspace isolation unavailable; prerequisite: linked Git worktree support.','checks':[]}
        self.assertEqual(fixture.grade_portal_fixture(case,self.repo,self.baseline,response,[]),[])
        self.adapter('claim','11')
        self.assertIn('workspace limit bypassed',fixture.grade_portal_fixture(case,self.repo,self.baseline,response,[]))

    def test_single_ticket_and_go_oracles_reject_continuation(self):
        for name in ('portal-single-unit','portal-go-single-unit'):
            case = next(c for c in fixture.load_cases() if c['id']==name)
            (self.repo/'unit11.txt').write_text('new11\n')
            (self.repo/'unit12.txt').write_text('old\n')
            response={'report':'One plain task; cast absent.','checks':[]}
            self.assertEqual(fixture.grade_portal_fixture(case,self.repo,self.baseline,response,[]),[])
            (self.repo/'unit12.txt').write_text('new12\n')
            self.assertIn('single handoff continued into another unit',fixture.grade_portal_fixture(case,self.repo,self.baseline,response,[]))

    def test_resume_fixture_preserves_prior_effects_and_rejects_lost_edits(self):
        case = next(c for c in fixture.load_cases() if c['id']=='portal-run-resume')
        with tempfile.TemporaryDirectory(prefix='mana verified resume ') as temp:
            work, before = fixture.prepare(case, Path(temp))
            prior = before['resume']
            self.assertEqual(fixture.git(Path(prior['workspace']),'rev-parse','HEAD'),prior['commit'])
            response = {'report':'cast absent; prior open PR awaiting review','checks':[]}
            failures = fixture.grade_portal_fixture(case,work,before,response,[])
            self.assertNotIn('resume duplicated completed work or discarded user edits',failures)
            (Path(prior['workspace'])/'draft.txt').unlink()
            self.assertIn('resume duplicated completed work or discarded user edits',fixture.grade_portal_fixture(case,work,before,response,[]))

    def test_resume_reads_changed_pr_head_and_reports_unknown_reads(self):
        case = next(c for c in fixture.load_cases() if c['id']=='portal-run-resume')
        with tempfile.TemporaryDirectory(prefix='mana remote resume ') as temp:
            work, before = fixture.prepare(case, Path(temp))
            path = work/'artifacts/tracker.json'
            data = json.loads(path.read_text())
            data['prs']['111']['headRefOid']='f'*40
            path.write_text(json.dumps(data))
            env=fixture.clean_env(work/'home'); env['PATH']=str(work/'bin')+':/usr/bin:/bin'
            current = subprocess.run(['gh','pr','view','111','--json','state,headRefOid,mergedAt'],cwd=work,env=env,text=True,capture_output=True)
            self.assertEqual(current.returncode,0)
            observed=json.loads(current.stdout)
            self.assertNotEqual(observed['headRefOid'],before['resume']['commit'])
            self.assertEqual(observed['state'],'OPEN')
            data['issues']['11']['assignees']=['other']; data['read_fail']=['12']; path.write_text(json.dumps(data))
            helper=work/'installed/portal/scripts/tickets.sh'
            owner=subprocess.run(['bash',str(helper),'--repo','fixture/mana','view','11'],cwd=work,env=env,text=True,capture_output=True)
            self.assertIn('assignees\tother',owner.stdout)
            unknown=subprocess.run(['bash',str(helper),'--repo','fixture/mana','view','12'],cwd=work,env=env,text=True,capture_output=True)
            self.assertNotEqual(unknown.returncode,0)
            self.assertIn('read failed',unknown.stderr)


if __name__ == '__main__':
    unittest.main()
