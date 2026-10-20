"""Selection-only discovery adapter, preregistered routes and the activation probe, offline.

Every host here is fake_host.py. No model is invoked. A fake run is an offline
fixture and these tests check that it can never be labelled live discovery.
"""
import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import discovery
import discovery_probe
import hosts
import process_family
import run
from test_host_validation import FAKE, MODEL, FakeHost

LINUX = sys.platform.startswith('linux')
RESPONSE = {'report': 'done', 'checks': []}
SPEC = (run.ROOT / 'docs/specs/discovery-and-hosts.md').read_text()
ALPHA = '@skill:alpha probe word@'
BETA = '@skill:beta probe word@'


def cases():
    return {case['id']: case for case in discovery.load_cases()['cases']}


def evidence(directory, host=FAKE, discovery_status='verified'):
    """A registry with focused containment, plus skill discovery unless told otherwise."""
    at = process_family.now()
    caps = {key: {'status': 'verified', 'observed_at': at, 'evidence': ['offline fixture record']} for key in hosts.FOCUSED}
    if discovery_status:
        caps['skill_discovery'] = {'status': discovery_status, 'observed_at': at, 'evidence': ['offline fixture record']}
    Path(directory).mkdir(parents=True, exist_ok=True)
    (Path(directory) / 'record.json').write_text(json.dumps({'schema_version': 1, 'host': host, 'platform': 'linux',
                                                             'recorded_at': at, 'source': 'offline test', 'capabilities': caps}))
    return Path(directory)


def observation(loads=(), actions=(), commands=(), outside=()):
    return {'loads': [{'skill': name, 'via': 'direct', 'first': True} for name in loads],
            'actions': [{'action': a} for a in actions], 'outside_loads': [{'command': c} for c in outside],
            'operations': [{'command': c, 'exit_code': code} for c, code in commands]}


def empty_host_folders(root):
    """Point the outside skill folders at empty temporary paths so the operator's machine never leaks in."""
    folders = tuple((label, Path(root) / ('host-folder-%d' % n)) for n, (label, _) in enumerate(discovery.HOST_SKILL_FOLDERS))
    return patch.object(discovery, 'HOST_SKILL_FOLDERS', folders), folders


class Routes(unittest.TestCase):
    def test_matrix_is_preregistered_against_the_spec_and_the_catalog(self):
        data = discovery.load_cases()
        kinds = [case['kind'] for case in data['cases']]
        self.assertEqual((kinds.count('positive'), kinds.count('negative'), kinds.count('overlap')), (19, 19, 8))
        # The activation map is the spec's inventory table, and still describes the shipped catalog.
        table = dict(re.findall(r'^\| `([a-z-]+)` \| (Automatic|Explicit) \|', SPEC, re.MULTILINE))
        self.assertEqual({k: v.lower() for k, v in table.items()}, data['activation'])
        self.assertTrue(discovery.check_catalog(data, discovery.snapshot(run.ROOT / 'skills')))
        # Each positive and negative request is the spec's wording.
        for case in data['cases']:
            if case['kind'] != 'overlap':
                self.assertIn('"%s"' % case['request'], SPEC, case['id'])
        overlap = {case['id'] for case in data['cases'] if case['kind'] == 'overlap'}
        self.assertEqual(overlap, set(re.findall(r'^\| `([a-z-]+)` \| (?!Automatic \||Explicit \|)', SPEC, re.MULTILINE)))
        spec_group = re.search(r'The first live group has 12 cases.*?: (.*?)\. Use', SPEC).group(1)
        named = re.findall(r'`([a-z-]+)` (positive|negative)|`([a-z-]+)`', spec_group)
        expected = {a + '-' + b if a else c for a, b, c in named}
        self.assertEqual(set(data['first_live_group']), expected)

    def test_first_live_group_schedule_is_seeded_and_complete(self):
        data = discovery.load_cases()
        first = discovery.schedule(data['first_live_group'])
        self.assertEqual(len(first), 24)
        self.assertEqual(first, discovery.schedule(data['first_live_group']))
        self.assertEqual(sorted((c['case'], c['repetition']) for c in first),
                         sorted((cid, rep) for cid in data['first_live_group'] for rep in (1, 2)))

    def test_loader_rejects_routes_that_would_bias_or_blur_the_study(self):
        original = json.loads(discovery.CASES.read_text())
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)

        def broken(mutate):
            data = json.loads(json.dumps(original))
            mutate(data)
            path = Path(temp.name) / 'cases.json'
            path.write_text(json.dumps(data))
            return path

        def case(data, cid):
            return next(c for c in data['cases'] if c['id'] == cid)
        mutations = {
            'ordinary request names a skill': lambda d: case(d, 'vague-bug').update(request='Use cast: checkout is flaky.'),
            'explicit skill expected from ordinary language': lambda d: case(d, 'cast-positive').update(
                invocation='ordinary', request='Implement this ready ticket, no-pr.'),
            'unknown route': lambda d: case(d, 'scan-negative')['routes']['accepted'].append('skill:nonexistent'),
            'negative accepts its own skill': lambda d: case(d, 'dispel-negative')['routes']['accepted'].append('skill:dispel'),
            'missing overlap case': lambda d: d['cases'].pop(),
            'fixture writes into the catalog': lambda d: case(d, 'scan-negative')['setup'].update(files={'.agents/skills/x': ''}),
        }
        for name, mutate in mutations.items():
            with self.subTest(name), self.assertRaises(ValueError):
                discovery.load_cases(broken(mutate))
        # A skill whose explicit-only flag changes needs new routes before any run.
        data = discovery.load_cases()
        catalog = discovery.snapshot(run.ROOT / 'skills')
        flipped = [dict(item, activation='automatic') if item['name'] == 'cast' else item for item in catalog['skills']]
        with self.assertRaisesRegex(ValueError, 'cast'):
            discovery.check_catalog(data, {'skills': flipped})


class Prompt(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)

    def test_requests_reach_the_host_without_workspace_paths(self):
        work = self.root / 'workspace'
        for case in cases().values():
            text = discovery.prompt(case)
            with self.subTest(case=case['id']):
                self.assertEqual(text, case['request'] + discovery.SUFFIX)
                self.assertEqual(discovery.prompt_paths(text, work), [])
        # The focused runner's prompt is exactly what this adapter must never send.
        legacy = 'Use the skill at %s/.agents/skills/dispel/SKILL.md.\nRewrite this release note.' % work
        self.assertEqual(discovery.prompt_paths(legacy, work), [str(work), discovery.SKILLS_DIR, 'SKILL.md'])

    def test_host_settings_keep_discovery_on_and_children_off(self):
        work = self.root / 'workspace'
        config = discovery.host_config(work, self.root / 'host' / 'bin' / 'codex', MODEL, 'medium')
        self.assertNotIn(discovery.SKIP_FLAG, config)
        self.assertIn('features.multi_agent=false', config)
        self.assertIn('features.multi_agent_v2=false', config)
        table = discovery.permission_table(work, self.root / 'host' / 'bin' / 'codex')
        self.assertEqual((table[str(work)], table[str(work / 'artifacts')]), ('read', 'write'))


class Judgments(unittest.TestCase):
    """The four observations stay separate for every combination the matrix needs."""

    def judge(self, cid, obs, discovery_status='verified', collected=True, outcome='completed', changed=False, honored=None):
        support = {'skill_discovery': discovery_status, 'explicit_only_honored': honored}
        return discovery.classify(cases()[cid], obs, discovery.load_cases()['activation'], support, collected, outcome, changed)

    def test_activation_distinguishes_selected_missing_unnecessary_and_unobservable(self):
        rows = [
            ('dispel-positive', observation(['dispel']), 'correct', 'correct'),
            ('dispel-positive', observation(), 'missing', 'fallback'),
            ('dispel-negative', observation(['dispel']), 'unnecessary', 'wrong'),
            ('dispel-negative', observation(), 'correct', 'correct'),
            # Honoring explicit-only metadata is never a miss; loading it from ordinary language is unnecessary.
            ('ordinary-explicit-only', observation(), 'correct', 'correct'),
            ('ordinary-explicit-only', observation(['cast']), 'unnecessary', 'wrong'),
            # A directly named explicit skill must load.
            ('banish-positive', observation(), 'missing', 'wrong'),
            ('banish-positive', observation(['banish']), 'correct', 'correct'),
            # Preregistered alternatives are accepted; anything else is not.
            ('remedy-negative', observation(['scan']), 'correct', 'correct'),
            ('review-or-audit', observation(['ultima']), 'unnecessary', 'wrong'),
            ('review-or-audit', observation(), 'missing', 'fallback'),
            # A skill from outside the frozen catalog goes to a person.
            ('dispel-positive', observation(['dispel'], outside=['cat ~/.codex/skills/x/SKILL.md']),
             'needs_adjudication', 'needs_adjudication'),
        ]
        for cid, obs, activation, routing in rows:
            with self.subTest(case=cid, loads=[l['skill'] for l in obs['loads']]):
                judged = self.judge(cid, obs)
                self.assertEqual((judged['activation'], judged['routing']), (activation, routing))
                self.assertEqual(judged['execution'], 'not_exercised')
        noted = self.judge('ordinary-explicit-only', observation(['cast']), honored='verified')
        self.assertIn('explicit-only cast loaded from ordinary language', noted['notes'][0])
        for status in (None, 'failed', 'unavailable'):
            judged = self.judge('dispel-positive', observation(['dispel']), discovery_status=status)
            self.assertEqual((judged['activation'], judged['routing']), ('unobservable', 'unobservable'))
        lost = self.judge('dispel-positive', observation(['dispel']), collected=False)
        self.assertEqual((lost['activation'], lost['routing'], lost['execution']), ('unobservable', 'unobservable', 'collection_failed'))

    def test_declared_capability_limits_are_separate_from_routing(self):
        stopped = self.judge('missing-sibling', observation(['portal']))
        self.assertEqual((stopped['activation'], stopped['routing']), ('correct', 'correct'))
        self.assertEqual(stopped['capability_limit'], {'status': 'declared', 'declared': ['skill:cast']})
        self.assertEqual(self.judge('missing-sibling', observation(['scan']))['routing'], 'wrong')
        self.assertEqual(self.judge('no-delegation', observation(['scan']))['capability_limit']['declared'], ['children'])
        self.assertEqual(self.judge('dispel-positive', observation(['dispel']))['capability_limit']['status'], 'none')

    def test_execution_gives_hard_verdicts_only_from_unambiguous_evidence(self):
        self.assertEqual(self.judge('attune-negative', observation(actions=['write']))['execution'], 'scope_violation')
        self.assertEqual(self.judge('attune-positive', observation(['attune'], actions=['write']))['execution'], 'not_exercised')
        self.assertEqual(self.judge('dispel-positive', observation(['dispel']), outcome='timeout')['execution'], 'timeout')
        self.assertEqual(self.judge('dispel-positive', observation(['dispel']), changed=True)['execution'], 'boundary_breach')
        # A failed command under a forbidden action goes to a person, never scope_violation.
        for command in ('bin/gh pr view 3', 'git commit -am x', 'python3 tool.py'):
            with self.subTest(command=command):
                judged = self.judge('attune-negative', observation(commands=[('cat AGENTS.md', 0), (command, 1)]))
                self.assertEqual((judged['execution'], judged['adjudicate']), ('needs_adjudication', [command]))
        # A read-only git call that succeeded is ordinary inspection.
        self.assertEqual(self.judge('attune-negative', observation(commands=[('git log --oneline', 0)]))['execution'], 'not_exercised')
        # With nothing forbidden, the same commands are just part of the run.
        self.assertEqual(self.judge('ward-positive', observation(['ward'], commands=[('git push', 1)]))['execution'], 'not_exercised')


@unittest.skipUnless(LINUX, 'fake sandbox containment and the family sweep target Linux')
class Transport(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.registry = evidence(self.root / 'registry')
        patcher, self.folders = empty_host_folders(self.root)
        patcher.start()
        self.addCleanup(patcher.stop)

    def run_case(self, cid, plan, name=None, **kwargs):
        host = FakeHost(self, dict({'response': RESPONSE}, **plan))
        kwargs.setdefault('evidence_dir', self.registry)
        with host.environment():
            result = discovery.run_case(cases()[cid], self.root / (name or cid), host.executable, MODEL, timeout=60, **kwargs)
        return result, host

    def seen(self, host):
        return [json.loads(p.read_text()) for p in sorted(host.state.glob('catalog-*.json'))]

    def test_a_real_load_event_is_observed_and_scoped(self):
        result, host = self.run_case('dispel-positive', {'parent': {'commands': [
            'cat RELEASE_NOTE.md', 'cat .agents/skills/dispel/SKILL.md', 'python3 -c print(1)']}})
        self.assertEqual(result['failures'], [])
        judged = result['judgment']
        self.assertEqual((judged['activation'], judged['routing'], judged['execution']), ('correct', 'correct', 'not_exercised'))
        self.assertEqual(judged['loaded_entrypoints'], ['dispel'])
        self.assertEqual(result['observation']['loads'][0]['via'], 'direct')
        self.assertEqual(result['observation']['first_substantive_operation']['command'], 'cat RELEASE_NOTE.md')
        self.assertEqual(result['observation_kind'], 'offline-fixture')
        self.assertEqual(result['isolation']['routes_read'], 'denied')
        self.assertEqual(result['host_skill_folders'], {label: None for label, _ in self.folders})
        call = host.calls()[0]
        self.assertEqual(call['prompt'], 'Rewrite this release note in plain language.' + discovery.SUFFIX)
        self.assertNotIn(discovery.SKIP_FLAG, call['argv'])
        self.assertIn('--ephemeral', call['argv'])
        # The host saw the installed catalog, explicit-only flags intact, and nothing else.
        listed = self.seen(host)[0]
        self.assertTrue(listed['discovering'])
        self.assertEqual({s['name'] for s in listed['listed']}, set(discovery.load_cases()['activation']))
        self.assertEqual({s['name'] for s in listed['listed'] if s['explicit']},
                         {k for k, v in discovery.load_cases()['activation'].items() if v == 'explicit'})
        self.assertEqual(result['catalog'], discovery.snapshot(run.ROOT / 'skills'))
        self.assertEqual(result['model_invocations'], 1)

    def test_only_one_plain_read_of_an_unseen_path_is_direct(self):
        result, _ = self.run_case('dispel-negative', {'parent': {'commands': [
            'grep -h "^description:" .agents/skills/dispel/SKILL.md .agents/skills/scan/SKILL.md', 'cat quote.txt']}})
        self.assertEqual(result['observation']['loads'], [])
        self.assertEqual(result['observation']['catalog_scans'][0]['skills'], ['dispel', 'scan'])
        self.assertEqual((result['judgment']['activation'], result['judgment']['routing']), ('correct', 'correct'))
        searches = {
            'found': ['find .agents -name SKILL.md', 'cat .agents/skills/dispel/SKILL.md'],
            'globbed': ['cat .agents/skills/d*/SKILL.md'],
            'piped': ['cat .agents/skills/dispel/SKILL.md | head -400'],
            'named earlier': ['ls .agents/skills', 'cat .agents/skills/dispel/SKILL.md'],
        }
        for name, commands in searches.items():
            with self.subTest(name):
                found, _ = self.run_case('dispel-positive', {'parent': {'commands': commands}}, name=name.replace(' ', '-'))
                self.assertEqual([(l['skill'], l['via']) for l in found['observation']['loads']], [('dispel', 'search')])
        # Reasoning that names the folder is model text, so the read stays direct.
        thought, _ = self.run_case('dispel-positive', {'reasoning': ['I will read .agents/skills/dispel/SKILL.md.'],
                                                       'parent': {'commands': ['cat .agents/skills/dispel/SKILL.md']}}, name='thought')
        self.assertEqual([(l['skill'], l['via']) for l in thought['observation']['loads']], [('dispel', 'direct')])
        # Any earlier tool item counts, not only command output: here a file_change item named the folder first.
        patched, _ = self.run_case('dispel-positive', {'file_changes': ['.agents/skills/dispel/notes.md'],
                                                       'parent': {'commands': ['cat .agents/skills/dispel/SKILL.md']}}, name='item')
        self.assertEqual([(l['skill'], l['via']) for l in patched['observation']['loads']], [('dispel', 'search')])
        # A bare SKILL.md or a workspace glob names nothing outside the catalog.
        bare, _ = self.run_case('dispel-negative', {'parent': {'commands': ['ls .agents/skills/*/SKILL.md', 'cat quote.txt']}}, name='bare')
        self.assertEqual(bare['observation']['outside_loads'], [])

    def test_child_activity_separates_empty_waits_failed_spawns_and_created_children(self):
        # Shapes from the 2026-10-20 pilot on Codex 0.163.0: an empty wait event, and a spawn that only the host log shows.
        wait = {'tool': 'wait', 'sender_thread_id': 'parent', 'receiver_thread_ids': [], 'prompt': None,
                'agents_states': {}, 'status': 'completed'}
        failed = ('2026-10-20T11:25:14.995521Z ERROR codex_core::tools::router: error=collab spawn failed: Fatal error: '
                  'failed to load model context for thread parent: invalid thread-store request: no rollout found for thread id parent')
        plans = {
            'empty wait': ({'collab_items': [wait, wait]}, 'none', []),
            'failed spawn': ({'collab_items': [wait], 'stderr_lines': [failed]}, 'attempted', ['delegate']),
            'created': ({'collab_items': [{'tool': 'spawn_agent', 'receiver_thread_ids': ['child-1']}]}, 'created', ['delegate']),
            'named wait': ({'collab_items': [dict(wait, receiver_thread_ids=['child-1'])]}, 'created', ['delegate']),
        }
        for name, (plan, children, attempted) in plans.items():
            with self.subTest(name):
                result, _ = self.run_case('scan-positive', plan, name='children-' + name.replace(' ', '-'))
                judged = result['judgment']
                self.assertEqual((judged['children'], judged['attempted_actions']), (children, attempted))
                # Delegation is not one of this case's forbidden actions, so the slot's own execution is unchanged.
                self.assertEqual(judged['execution'], 'not_exercised')
        result, _ = self.run_case('scan-positive', {'collab_items': [wait, wait, wait], 'stderr_lines': [failed, failed]}, name='counted')
        self.assertEqual((len(result['observation']['children']['failed_spawns']), result['observation']['children']['empty_waits']), (2, 3))

    def test_a_timeout_is_reported_before_failed_commands_go_to_a_person(self):
        obs = observation(commands=[('cat missing.txt', 1)])
        judged = discovery.classify(cases()['scan-positive'], obs, discovery.load_cases()['activation'],
                                    {'skill_discovery': 'verified'}, True, 'timeout', False)
        self.assertEqual(judged['execution'], 'timeout')
        self.assertEqual(judged['adjudicate'], ['cat missing.txt'])

    def test_dummy_selector_respects_explicit_only_and_stays_an_offline_fixture(self):
        # The keyword selector is deliberately crude: it reads listed descriptions and nothing else.
        honored, host = self.run_case('ordinary-explicit-only', {'selector': 'keyword', 'selector_threshold': 3})
        self.assertEqual(honored['judgment']['loaded_entrypoints'], [])
        self.assertEqual((honored['judgment']['activation'], honored['judgment']['routing']), ('correct', 'correct'))
        ignored, _ = self.run_case('ordinary-explicit-only', {'selector': 'keyword', 'selector_threshold': 3,
                                                              'honor_explicit_only': False}, name='ignored')
        self.assertEqual(ignored['judgment']['loaded_entrypoints'], ['cast'])
        self.assertEqual(ignored['judgment']['activation'], 'unnecessary')
        named, _ = self.run_case('banish-positive', {'selector': 'keyword'})
        self.assertEqual(named['judgment']['activation'], 'correct')
        audit, _ = self.run_case('review-or-audit', {'selector': 'keyword'})
        self.assertEqual((audit['judgment']['activation'], audit['judgment']['routing']), ('unnecessary', 'wrong'))
        self.assertEqual({r['observation_kind'] for r in (honored, ignored, named, audit)}, {'offline-fixture'})

    def test_absent_sibling_is_recorded_and_the_route_stays_correct(self):
        sibling, _ = self.run_case('missing-sibling', {'parent': {'commands': [
            'cat .agents/skills/portal/SKILL.md', 'cat .agents/skills/cast/SKILL.md']}})
        judged = sibling['judgment']
        self.assertEqual((judged['activation'], judged['routing']), ('correct', 'correct'))
        self.assertEqual([u['skill'] for u in sibling['observation']['unavailable']], ['cast'])
        self.assertEqual(judged['capability_limit'], {'status': 'declared', 'declared': ['skill:cast']})
        self.assertNotIn('cast', {s['name'] for s in sibling['catalog']['skills']})

    def test_a_skill_outside_the_frozen_catalog_goes_to_a_person(self):
        label, folder = self.folders[1]
        shutil.copytree(run.ROOT / 'skills' / 'scan', folder / 'scan')
        result, _ = self.run_case('review-or-audit', {'parent': {'commands': ['cat %s/scan/SKILL.md' % folder]}})
        self.assertEqual(result['host_skill_folders'][label], 1)
        self.assertEqual((result['judgment']['activation'], result['judgment']['routing']),
                         ('needs_adjudication', 'needs_adjudication'))
        self.assertEqual(result['judgment']['adjudicate'], ['cat %s/scan/SKILL.md' % folder])

    def test_writes_stop_at_the_boundary_and_unclear_commands_go_to_a_person(self):
        changed, _ = self.run_case('attune-negative', {'file_changes': ['AGENTS.md']})
        self.assertEqual(changed['failures'], [])
        self.assertEqual(changed['observation']['first_consequential_action']['via'], 'file_change')
        self.assertEqual((changed['judgment']['execution'], changed['judgment']['forbidden_attempts']), ('scope_violation', ['write']))
        failed, _ = self.run_case('dispel-negative', {'parent': {'commands': ['mkdir /proc/mana-denied']}})
        self.assertEqual(failed['judgment']['execution'], 'scope_violation')
        self.assertEqual(failed['observation']['actions'][0]['via'], 'failed command')
        # A denied write through Python, a gh call and a git call are not clear writes: a person reads them.
        denied, _ = self.run_case('attune-negative', {'parent': {'commands': ["python3 -c open('AGENTS.md','a').write('x')",
                                                                              "python3 -c open('artifacts/note.txt','w').write('ok')"]}},
                                  name='denied')
        self.assertEqual(denied['observation']['actions'], [])
        self.assertEqual((denied['judgment']['execution'], denied['judgment']['adjudicate']),
                         ('needs_adjudication', ["python3 -c open('AGENTS.md','a').write('x')"]))
        self.assertFalse((self.root / 'denied/workspace/AGENTS.md').read_text().endswith('x'))
        self.assertEqual((self.root / 'denied/workspace/artifacts/note.txt').read_text(), 'ok')
        published, _ = self.run_case('reveal-negative', {'parent': {'commands': ['bin/gh pr create --draft --fill']}})
        self.assertEqual(published['judgment']['execution'], 'needs_adjudication')
        self.assertEqual(published['judgment']['forbidden_attempts'], [])
        inspected, _ = self.run_case('scan-negative', {'parent': {'commands': ['git log --oneline']}})
        self.assertEqual((inspected['judgment']['execution'], inspected['judgment']['adjudicate']), ('not_exercised', []))
        # A write the sandbox misses is a breach of the selection-only boundary, never a pass.
        breach, _ = self.run_case('scan-negative', {'parent': {'commands': ['sh -c "echo x >> app.py"']}}, name='breach')
        self.assertEqual(breach['judgment']['execution'], 'boundary_breach')
        self.assertIn('product state changed during a selection-only run', breach['failures'])

    def test_lost_events_or_unverified_discovery_make_selection_unobservable(self):
        lost, _ = self.run_case('dispel-positive', {'parent': {'commands': ['cat .agents/skills/dispel/SKILL.md']},
                                                    'malformed_event_after': 'item.completed'})
        self.assertEqual((lost['judgment']['activation'], lost['judgment']['execution']), ('unobservable', 'collection_failed'))
        registry = evidence(self.root / 'unverified', discovery_status=None)
        blind, _ = self.run_case('dispel-positive', {'parent': {'commands': ['cat .agents/skills/dispel/SKILL.md']}},
                                 name='blind', evidence_dir=registry)
        self.assertEqual((blind['judgment']['activation'], blind['judgment']['routing']), ('unobservable', 'unobservable'))

    def test_live_runs_need_the_real_host_accepted_evidence_and_frozen_routes(self):
        refusals = [
            ({'live': True, 'routes_sha256': discovery.routes_digest()}, 'never live discovery'),
            ({'routes_sha256': '0' * 64}, 'preregistered routes changed'),
        ]
        for kwargs, message in refusals:
            with self.subTest(message):
                result, host = self.run_case('scan-positive', {}, name='refused-' + message[:5].replace(' ', ''), **kwargs)
                self.assertTrue(any(message in f for f in result['failures']), result['failures'])
                self.assertEqual(host.calls(), [])
                self.assertEqual(result['observation_kind'], 'offline-fixture')
        # Outside a fake plan, a live run still needs discovery evidence for the exact reported version.
        # This stub only answers --version and records anything else it is asked to do.
        stub = self.root / 'stub' / 'bin' / 'codex'
        stub.parent.mkdir(parents=True)
        calls = self.root / 'stub' / 'calls'
        stub.write_text('#!/bin/sh\nif [ "$1" = --version ]; then echo "%s"; exit 0; fi\necho "$@" >> %s\nexit 97\n' % (FAKE, calls))
        stub.chmod(0o755)
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop('MANA_FAKE_HOST_PLAN', None)
            result = discovery.run_case(cases()['scan-positive'], self.root / 'live', stub, MODEL,
                                        live=True, routes_sha256=discovery.routes_digest(),
                                        evidence_dir=evidence(self.root / 'focused-only', discovery_status=None))
        self.assertTrue(any('unvalidated host' in f and 'skill_discovery=unknown' in f for f in result['failures']), result['failures'])
        self.assertFalse(calls.exists())
        self.assertNotIn('judgment', result)

    def test_leaky_sandbox_stops_before_any_model_call(self):
        result, host = self.run_case('scan-positive', {'containment': 'leaky'})
        self.assertTrue(any('selection-only containment failed' in f for f in result['failures']), result['failures'])
        self.assertEqual(host.calls(), [])
        self.assertEqual(result['model_invocations'], 0)


@unittest.skipUnless(LINUX, 'fake sandbox containment and the family sweep target Linux')
class LiveRecord(unittest.TestCase):
    def test_live_codex_0163_discovery_record(self):
        # Recorded by run.py --probe-discovery on a real Codex CLI 0.163.0 host with one model call,
        # then folder names were replaced with counts. Assessed in a copy with the focused host record.
        directory = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, directory)
        path = hosts.EVIDENCE / '2026-10-18-codex-cli-0.163.0-discovery.json'
        self.assertEqual('5bf4921e82d7a800bb8b9b604b416050439c9035d83a85f8ad593642524d5d2b',
                         hashlib.sha256(path.read_bytes()).hexdigest())
        for name in (path.name, '2026-10-17-codex-cli-0.163.0.json'):
            shutil.copy2(hosts.EVIDENCE / name, directory / name)
        record = json.loads(path.read_text())
        self.assertEqual(1, record['model_invocations'])
        self.assertTrue(all(v is None or isinstance(v, int) for v in record['host_skill_folders'].values()))
        self.assertNotIn('explicit_only_honored', record['capabilities'])
        at = hosts.parse_time(record['recorded_at']) + datetime.timedelta(days=1)
        result = hosts.assess('codex-cli 0.163.0', 'discovery', directory=directory, at=at)
        self.assertTrue(result['accepted'])
        self.assertEqual('verified', result['capabilities']['skill_discovery']['status'])


    def test_live_codex_0163_catalog_record(self):
        # Recorded by run.py --probe-catalog on a real Codex CLI 0.163.0 host, with no model call.
        path = hosts.EVIDENCE / '2026-10-20-codex-cli-0.163.0-catalog.json'
        self.assertEqual('97e9fb3f86079c47703694a12c520aa419ebc41da1923a7fb28a997577f38c3d',
                         hashlib.sha256(path.read_bytes()).hexdigest())
        record = json.loads(path.read_text())
        self.assertEqual((0, [], []), (record['model_invocations'], record['unknown'], record['catalog_findings']))
        honored = record['capabilities']['explicit_only_honored']
        self.assertEqual('verified', honored['status'])
        # The host reads only the agents/openai.yaml policy, which is why every explicit-only skill ships one.
        self.assertEqual({'allow_implicit_invocation': 'honored', 'disable-model-invocation': 'ignored'}, honored['markers'])
        self.assertEqual('verified', hosts.capabilities('codex-cli 0.163.0')['explicit_only_honored']['status'])

    def test_live_codex_0163_children_record(self):
        # Recorded by run.py --probe-catalog on a real Codex CLI 0.163.0 host, with no model call. The 2026-10-20
        # pilot saw the same thing live: empty collaboration waits and spawns that failed only because of --ephemeral.
        path = hosts.EVIDENCE / '2026-10-20-codex-cli-0.163.0-children.json'
        self.assertEqual('ce63e8a9699585f0f492a13943f99346029edc99290e7f3716c2b25b251d5d9e', hashlib.sha256(path.read_bytes()).hexdigest())
        record = json.loads(path.read_text())
        self.assertEqual(0, record['model_invocations'])
        self.assertEqual('failed', record['capabilities']['children_disabled']['status'])
        found = hosts.capabilities('codex-cli 0.163.0')
        self.assertEqual(('failed', path.name), (found['children_disabled']['status'], found['children_disabled']['record']))
        # Discovery acceptance does not depend on it; each slot's child activity is judged on its own.
        self.assertTrue(hosts.assess('codex-cli 0.163.0', 'discovery')['accepted'])


class ActivationProbe(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        patcher, self.folders = empty_host_folders(self.root)
        patcher.start()
        self.addCleanup(patcher.stop)

    def probe(self, plan, name):
        host = FakeHost(self, dict({'response': RESPONSE}, **plan))
        with host.environment():
            record = discovery_probe.probe(host.executable, self.root / name, MODEL, timeout=60)
        return record, host

    def statuses(self, record):
        # children_disabled has its own test; every other capability is compared exactly.
        return {k: v['status'] for k, v in record['capabilities'].items() if k != 'children_disabled'}

    def accepted(self, name):
        registry = evidence(self.root / ('registry-' + name), discovery_status=None)
        shutil.copy2(self.root / name / 'host-evidence.json', registry / 'probe.json')
        return hosts.assess(FAKE, 'discovery', directory=registry)['accepted']

    def test_observable_automatic_load_and_hidden_explicit_entry_are_verified(self):
        record, host = self.probe({'parent': {'commands': ['cat ' + ALPHA]}}, 'honored')
        self.assertEqual(self.statuses(record), {'installation': 'verified', 'skill_discovery': 'verified',
                                                 'explicit_only_honored': 'verified'})
        self.assertEqual(record['model_invocations'], 1)
        self.assertEqual(len(host.calls()), 1)
        call = host.calls()[0]
        self.assertNotIn(discovery.SKIP_FLAG, call['argv'])
        self.assertEqual(call['prompt'], discovery_probe.PROMPT)
        # Canary folders are random, so neither the prompt nor an earlier command can name them by accident.
        names = record['canaries']
        self.assertTrue(all(re.fullmatch(r'probe-[0-9a-f]{8}', n) for n in names.values()), names)
        self.assertTrue(all(n not in call['prompt'] for n in names.values()))
        beta = self.root / 'honored/workspace' / discovery.SKILLS_DIR / names['beta']
        self.assertIn('disable-model-invocation: true', (beta / 'SKILL.md').read_text())
        self.assertEqual((beta / 'agents/openai.yaml').read_text(), 'policy:\n  allow_implicit_invocation: false\n')
        self.assertEqual(record['host_skill_folders'], {label: None for label, _ in self.folders})
        self.assertNotIn(str(self.root), json.dumps(record))
        self.assertTrue(self.accepted('honored'))

    def test_only_unambiguous_evidence_gives_a_status(self):
        plans = {
            # A direct read of the explicit canary fails explicit-only; discovery itself is still verified.
            'both': ({'parent': {'commands': ['cat ' + ALPHA, 'cat ' + BETA]}},
                     {'skill_discovery': 'verified', 'explicit_only_honored': 'failed'}),
            # The model never loads the automatic canary: unknown, not failed.
            'none': ({}, {}),
            'invisible': ({'hidden_load': ['alpha probe word']}, {'skill_discovery': 'unavailable'}),
            # The secret was printed by a command before it reached the response: a search, not an invisible load.
            'printed': ({'parent': {'commands': ['grep -rh "alpha probe word is" .agents']}, 'hidden_load': ['alpha probe word']}, {}),
            'searched': ({'parent': {'commands': ['find .agents -name SKILL.md', 'cat ' + ALPHA]}}, {}),
            'listed first': ({'parent': {'commands': ['ls .agents/skills', 'cat ' + ALPHA]}}, {}),
            'lost': ({'parent': {'commands': ['cat ' + ALPHA]}, 'malformed_event_after': 'item.completed'}, {}),
            'beta searched': ({'parent': {'commands': ['cat ' + ALPHA, 'grep -rh "beta probe word is" .agents']}},
                              {'skill_discovery': 'verified'}),
            # Model text naming the folder points to the host listing, so the read after it stays direct.
            'reasoning first': ({'reasoning': ['The skill list shows %s; I will read it.' % ALPHA],
                                 'parent': {'commands': ['cat ' + ALPHA]}},
                                {'skill_discovery': 'verified', 'explicit_only_honored': 'verified'}),
            # Load indexes count every completed item, so an earlier file_change item cannot shift them.
            'item first': ({'file_changes': ['notes.txt'], 'parent': {'commands': ['cat ' + ALPHA]}},
                           {'skill_discovery': 'verified', 'explicit_only_honored': 'verified'}),
        }
        for name, (plan, expected) in plans.items():
            with self.subTest(name):
                # No catalog render, so the live run alone decides explicit_only_honored.
                record, _ = self.probe(dict(plan, prompt_input='unsupported'), name.replace(' ', '-'))
                expected = dict({'installation': 'verified'}, **expected)
                self.assertEqual(self.statuses(record), expected)
                self.assertEqual(self.accepted(name.replace(' ', '-')), expected.get('skill_discovery') == 'verified')
                if 'skill_discovery' not in expected:
                    self.assertTrue(any(note.startswith('skill_discovery: ') for note in record['unknown']), record['unknown'])

    def test_catalog_render_decides_explicit_only_without_a_model_call(self):
        plans = {
            # What Codex 0.163.0 printed: the policy file hides a skill and the frontmatter flag does not.
            'policy only': ({'render_honors': ['policy']}, 'verified',
                            {'allow_implicit_invocation': 'honored', 'disable-model-invocation': 'ignored'}),
            'both markers': ({}, 'verified', {'allow_implicit_invocation': 'honored', 'disable-model-invocation': 'honored'}),
            'neither marker': ({'render_honors': []}, 'failed',
                               {'allow_implicit_invocation': 'ignored', 'disable-model-invocation': 'ignored'}),
        }
        for name, (plan, status, markers) in plans.items():
            with self.subTest(name):
                slug = name.replace(' ', '-')
                host = FakeHost(self, dict({'response': RESPONSE}, **plan))
                with host.environment():
                    record = discovery_probe.probe_catalog(host.executable, self.root / slug)
                self.assertEqual(self.statuses(record), {'installation': 'verified', 'explicit_only_honored': status})
                self.assertEqual(record['capabilities']['explicit_only_honored']['markers'], markers)
                self.assertEqual((record['model_invocations'], host.calls()), (0, []))
                # The operator's home and Codex home never reach either render.
                for path in sorted(host.state.glob('render-*.json')):
                    render = json.loads(path.read_text())
                    self.assertTrue(render['home'].startswith(str(self.root / slug)), render)
                    self.assertTrue(render['codex_home'].startswith(str(self.root / slug)), render)
                self.assertEqual(len(list(host.state.glob('render-*.json'))), 2)
                self.assertNotIn(str(self.root), json.dumps(record))

    def test_the_shipped_catalog_render_names_each_misplaced_skill(self):
        explicit = sorted(item['name'] for item in discovery.snapshot(run.ROOT / 'skills')['skills'] if item['activation'] == 'explicit')
        for name, plan, findings in (('honored', {'render_honors': ['policy']}, []),
                                     ('ignored', {'render_honors': []}, ['explicit-only %s is listed for implicit use' % n for n in explicit])):
            with self.subTest(name):
                host = FakeHost(self, dict({'response': RESPONSE}, **plan))
                with host.environment():
                    record = discovery_probe.probe_catalog(host.executable, self.root / ('shipped-' + name))
                self.assertEqual(record['catalog_findings'], findings)
                installed = next(p for p in record['probes'] if p['name'] == 'installed-catalog-render')
                self.assertEqual(installed['counts'], {'automatic': 11, 'explicit': 8})
                self.assertEqual(installed['hidden_automatic'], [])

    def test_the_render_records_whether_child_tools_reach_the_model(self):
        for name, plan, status in (('offered', {'render_child_tools': True}, 'failed'), ('withheld', {}, 'verified')):
            with self.subTest(name):
                host = FakeHost(self, dict({'response': RESPONSE}, **plan))
                with host.environment():
                    record = discovery_probe.probe_catalog(host.executable, self.root / ('children-' + name))
                self.assertEqual(record['capabilities']['children_disabled']['status'], status)
                self.assertEqual(host.calls(), [])
        # A failed render says nothing about children.
        host = FakeHost(self, {'response': RESPONSE, 'prompt_input': 'unsupported'})
        with host.environment():
            record = discovery_probe.probe_catalog(host.executable, self.root / 'children-unknown')
        self.assertNotIn('children_disabled', record['capabilities'])

    def test_a_live_direct_read_overrides_a_hidden_catalog_entry(self):
        record, _ = self.probe({'parent': {'commands': ['cat ' + ALPHA, 'cat ' + BETA]}}, 'contradicted')
        self.assertEqual(record['capabilities']['explicit_only_honored']['status'], 'failed')

    def test_a_missing_render_leaves_explicit_only_unknown(self):
        for name, plan in {'unsupported': {'prompt_input': 'unsupported'},
                           'no catalog': {'render_empty': True}}.items():
            with self.subTest(name):
                host = FakeHost(self, dict({'response': RESPONSE}, **plan))
                with host.environment():
                    record = discovery_probe.probe_catalog(host.executable, self.root / name.replace(' ', '-'))
                self.assertEqual(self.statuses(record), {'installation': 'verified'})
                self.assertTrue(any(note.startswith('explicit_only_honored: catalog render') for note in record['unknown']),
                                record['unknown'])

    def test_explicit_only_markers_must_agree_in_the_catalog(self):
        for frontmatter, policy in ((True, False), (False, True)):
            with self.subTest(frontmatter=frontmatter, policy=policy):
                root = self.root / ('markers-%s-%s' % (frontmatter, policy))
                discovery_probe.write_canary(root, 'probe-1', 'Gives a word.', 'gamma', 'secret', frontmatter, policy)
                with self.assertRaisesRegex(ValueError, 'explicit-only markers disagree'):
                    discovery.snapshot(root)
        catalog = discovery.snapshot(run.ROOT / 'skills')
        explicit = {item['name'] for item in catalog['skills'] if item['activation'] == 'explicit'}
        for name in explicit:
            self.assertEqual((run.ROOT / 'skills' / name / 'agents/openai.yaml').read_text(), discovery_probe.OPENAI_POLICY)

    def test_outside_reads_are_recorded_without_hiding_a_direct_load(self):
        label, folder = self.folders[0]
        shutil.copytree(run.ROOT / 'skills' / 'dispel', folder / 'dispel')
        record, _ = self.probe({'parent': {'commands': ['cat ' + ALPHA, 'cat %s/dispel/SKILL.md' % folder]}}, 'outside')
        self.assertEqual(record['host_skill_folders'][label], 1)
        self.assertEqual(len(next(p for p in record['probes'] if p['name'] == 'activation')['outside_loads']), 2)
        self.assertEqual(record['capabilities']['skill_discovery']['status'], 'verified')

    def test_a_filesystem_search_after_a_direct_read_still_verifies(self):
        # A find shim keeps the reviewer's exact command fast; it prints SKILL.md paths outside the workspace.
        shim = self.root / 'shim'
        shim.mkdir()
        (shim / 'find').write_text('#!/bin/sh\necho /usr/share/doc/tool/SKILL.md\necho /opt/other/skills/x/SKILL.md\n')
        (shim / 'find').chmod(0o755)
        with patch.dict(os.environ, {'PATH': str(shim) + ':' + os.environ.get('PATH', '/usr/bin:/bin')}):
            record, _ = self.probe({'parent': {'commands': ['cat ' + ALPHA, 'find / -name SKILL.md 2>/dev/null']}}, 'find')
        self.assertEqual(self.statuses(record), {'installation': 'verified', 'skill_discovery': 'verified',
                                                 'explicit_only_honored': 'verified'})

    def test_a_relative_out_directory_is_made_absolute(self):
        cwd = os.getcwd()
        os.chdir(self.root)
        self.addCleanup(os.chdir, cwd)
        host = FakeHost(self, {'response': RESPONSE, 'parent': {'commands': ['cat ' + ALPHA]}})
        with host.environment():
            record = discovery_probe.probe(host.executable, Path('relative-out'), MODEL, timeout=60)
        self.assertEqual(record['capabilities']['skill_discovery']['status'], 'verified')
        call = host.calls()[-1]
        self.assertIn(str(self.root / 'relative-out' / 'workspace'), call['argv'])
        activation = next(p for p in record['probes'] if p['name'] == 'activation')
        self.assertEqual(activation['outside_loads'], [])

    def test_leaky_host_fails_without_a_model_call(self):
        record, host = self.probe({'containment': 'leaky'}, 'leaky')
        self.assertEqual(record['model_invocations'], 0)
        self.assertEqual(host.calls(), [])
        self.assertNotIn('skill_discovery', record['capabilities'])

    def test_cli_refuses_unbounded_or_mixed_discovery_options(self):
        script = str(run.HERE / 'run.py')
        attempts = [
            ['--probe-discovery', '--out', str(self.root / 'x'), '--model', MODEL, '--timeout', '300'],
            ['--probe-discovery', '--out', str(self.root / 'x'), '--model', MODEL, '--case', 'scan-positive'],
            ['--probe-discovery', '--out', str(self.root / 'x')],
            ['--discover', '--case', 'scan-positive', '--routes-sha256', 'x', '--model', MODEL],
            ['--discover', '--live', '--case', 'scan-positive', '--case', 'vague-bug', '--routes-sha256', 'x', '--model', MODEL],
            ['--discover', '--live', '--case', 'scan-positive', '--routes-sha256', 'x', '--model', MODEL, '--timeout', '600'],
            ['--discovery-check', '--live'],
            ['--discovery-check', '--probe-discovery'],
            ['--probe-catalog', '--out', str(self.root / 'x'), '--model', MODEL],
            ['--probe-catalog'],
            ['--probe-catalog', '--probe-discovery', '--out', str(self.root / 'x'), '--model', MODEL],
        ]
        for extra in attempts:
            with self.subTest(extra=extra):
                result = subprocess.run([sys.executable, '-B', script] + extra, capture_output=True, text=True,
                                        env=dict(os.environ, PATH='/usr/bin:/bin'))
                self.assertEqual(result.returncode, 2, result.stderr)
                self.assertFalse((self.root / 'x').exists())
        check = subprocess.run([sys.executable, '-B', script, '--discovery-check'], capture_output=True, text=True)
        self.assertEqual(check.returncode, 0, check.stderr)
        summary = json.loads(check.stdout)
        self.assertEqual((summary['cases'], summary['routes_sha256'], summary['agent_executed']),
                         (46, discovery.routes_digest(), False))


if __name__ == '__main__':
    unittest.main()
