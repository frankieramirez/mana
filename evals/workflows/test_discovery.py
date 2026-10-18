"""Selection-only discovery adapter, preregistered routes and the activation probe, offline.

Every host here is fake_host.py. No model is invoked. A fake run is an offline
fixture and these tests check that it can never be labelled live discovery.
"""
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


def cases():
    return {case['id']: case for case in discovery.load_cases()['cases']}


def evidence(directory, *extra, host=FAKE, discovery_status='verified'):
    """A registry with focused containment, plus skill discovery unless told otherwise."""
    at = process_family.now()
    caps = {key: {'status': 'verified', 'observed_at': at, 'evidence': ['offline fixture record']} for key in hosts.FOCUSED}
    if discovery_status:
        caps['skill_discovery'] = {'status': discovery_status, 'observed_at': at, 'evidence': ['offline fixture record']}
    for key in extra:
        caps[key] = {'status': 'verified', 'observed_at': at, 'evidence': ['offline fixture record']}
    Path(directory).mkdir(parents=True, exist_ok=True)
    (Path(directory) / 'record.json').write_text(json.dumps({'schema_version': 1, 'host': host, 'platform': 'linux',
                                                             'recorded_at': at, 'source': 'offline test', 'capabilities': caps}))
    return Path(directory)


def observation(loads=(), unavailable=(), actions=()):
    return {'loads': [{'skill': name, 'via': 'direct', 'first': True} for name in loads],
            'unavailable': [{'capability': c} for c in unavailable], 'actions': [{'action': a} for a in actions]}


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
            'forbidden skill is also accepted': lambda d: case(d, 'review-or-audit')['forbidden_skills'].append('scan'),
            'unknown route': lambda d: case(d, 'scan-negative')['routes']['accepted'].append('skill:nonexistent'),
            'negative may load its own skill': lambda d: case(d, 'dispel-negative').update(forbidden_skills=[]),
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

    def test_requests_reach_the_host_without_hidden_load_instructions(self):
        catalog = discovery.snapshot(run.ROOT / 'skills')
        work = self.root / 'workspace'
        for case in cases().values():
            text = discovery.prompt(case)
            with self.subTest(case=case['id']):
                self.assertEqual(text, case['request'] + discovery.SUFFIX)
                self.assertEqual(discovery.hidden_instructions(text, case, catalog, work), [])
        # The focused runner's prompt is exactly what this adapter must never send.
        case = cases()['dispel-positive']
        legacy = 'Use the skill at %s/installed/dispel/SKILL.md.\n%s' % (work, case['request'])
        problems = discovery.hidden_instructions(legacy, case, catalog, work)
        self.assertTrue(any('SKILL.md' in p for p in problems) and any('names skills' in p for p in problems), problems)

    def test_host_settings_keep_discovery_on_children_off_and_routes_unreadable(self):
        work = self.root / 'workspace'
        executable = self.root / 'host' / 'bin' / 'codex'
        config, table = discovery.host_config(work, executable, MODEL, 'medium')
        self.assertNotIn(discovery.SKIP_FLAG, config)
        self.assertIn('features.multi_agent=false', config)
        self.assertIn('features.multi_agent_v2=false', config)
        self.assertEqual(table[str(work)], 'read')
        self.assertEqual(table[str(work / 'artifacts')], 'write')
        self.assertFalse(discovery.readable(table, discovery.CASES))
        self.assertTrue(discovery.readable(table, work / discovery.SKILLS_DIR / 'scan' / 'SKILL.md'))


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

    def test_unavailable_capabilities_are_separate_from_wrong_routing(self):
        stopped = self.judge('missing-sibling', observation(['portal'], ['skill:cast']))
        self.assertEqual((stopped['activation'], stopped['routing']), ('correct', 'correct'))
        self.assertEqual(stopped['capability_limit'], {'status': 'observed', 'declared': ['skill:cast'], 'observed': ['skill:cast']})
        wrong = self.judge('missing-sibling', observation(['scan'], ['skill:cast']))
        self.assertEqual(wrong['routing'], 'wrong')
        self.assertEqual(wrong['capability_limit']['observed'], ['skill:cast'])
        declared = self.judge('no-delegation', observation(['scan']))
        self.assertEqual(declared['capability_limit']['status'], 'declared')
        self.assertEqual(self.judge('changed-target', observation(['scan'], ['tool:gh']))['routing'], 'correct')

    def test_execution_records_scope_without_claiming_a_workflow_outcome(self):
        self.assertEqual(self.judge('attune-negative', observation(actions=['write']))['execution'], 'scope_violation')
        self.assertEqual(self.judge('attune-positive', observation(['attune'], actions=['write']))['execution'], 'not_exercised')
        self.assertEqual(self.judge('dispel-positive', observation(['dispel']), outcome='timeout')['execution'], 'timeout')
        self.assertEqual(self.judge('dispel-positive', observation(['dispel']), changed=True)['execution'], 'boundary_breach')


@unittest.skipUnless(LINUX, 'fake sandbox containment and the family sweep target Linux')
class Transport(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.registry = evidence(self.root / 'registry')

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
            'cat RELEASE_NOTE.md', 'cat .agents/skills/dispel/SKILL.md', 'python3 -c "print(1)"']}})
        self.assertEqual(result['failures'], [])
        judged = result['judgment']
        self.assertEqual((judged['activation'], judged['routing'], judged['execution']), ('correct', 'correct', 'not_exercised'))
        self.assertEqual(judged['loaded_entrypoints'], ['dispel'])
        self.assertEqual(result['observation']['loads'][0]['via'], 'direct')
        self.assertEqual(result['observation']['first_substantive_operation']['command'], 'cat RELEASE_NOTE.md')
        self.assertEqual(result['observation_kind'], 'offline-fixture')
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
        self.assertNotIn(str(self.root), json.dumps(result['command']).replace(str(host.dir), ''))

    def test_browsing_descriptions_is_a_catalog_scan_not_a_load(self):
        result, _ = self.run_case('dispel-negative', {'parent': {'commands': [
            'grep -h "^description:" .agents/skills/dispel/SKILL.md .agents/skills/scan/SKILL.md', 'cat quote.txt']}})
        self.assertEqual(result['observation']['loads'], [])
        self.assertEqual(result['observation']['catalog_scans'][0]['skills'], ['dispel', 'scan'])
        self.assertEqual((result['judgment']['activation'], result['judgment']['routing']), ('correct', 'correct'))
        found, _ = self.run_case('dispel-positive', {'parent': {'commands': [
            'find .agents -name SKILL.md', 'cat .agents/skills/dispel/SKILL.md']}}, name='searched')
        self.assertEqual(found['observation']['loads'][0]['via'], 'search')

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
        results = [honored, ignored, named, audit]
        self.assertTrue(all(r['observation_kind'] == 'offline-fixture' for r in results))
        self.assertEqual(discovery.tally(results)['denominator'], 0)
        self.assertEqual(discovery.tally(results, 'offline-fixture')['denominator'], 4)

    def test_unavailable_skill_and_tool_are_capability_limits(self):
        sibling, _ = self.run_case('missing-sibling', {'parent': {'commands': [
            'cat .agents/skills/portal/SKILL.md', 'cat .agents/skills/cast/SKILL.md']}})
        judged = sibling['judgment']
        self.assertEqual((judged['activation'], judged['routing']), ('correct', 'correct'))
        self.assertEqual(judged['capability_limit']['observed'], ['skill:cast'])
        self.assertNotIn('cast', {s['name'] for s in sibling['catalog']['skills']})
        target, _ = self.run_case('changed-target', {'parent': {'commands': [
            'cat .agents/skills/scan/SKILL.md', 'bin/gh pr view 31 --repo other-org/other-repo']}})
        self.assertEqual(target['judgment']['routing'], 'correct')
        self.assertEqual(target['judgment']['capability_limit']['observed'], ['tool:gh'])
        self.assertEqual(target['judgment']['execution'], 'not_exercised')

    def test_mutation_attempts_stop_at_the_boundary_and_are_recorded(self):
        result, _ = self.run_case('attune-negative', {
            # The fake splits commands on whitespace, so the Python bodies carry none.
            'parent': {'commands': ["python3 -c open('AGENTS.md','a').write('x')",
                                    "python3 -c open('artifacts/note.txt','w').write('ok')"]},
            'file_changes': ['AGENTS.md']})
        self.assertEqual(result['failures'], [])
        actions = result['observation']['actions']
        self.assertEqual([a['action'] for a in actions], ['write', 'write'])
        self.assertEqual(result['observation']['first_consequential_action']['via'], 'file_change')
        self.assertEqual(result['judgment']['execution'], 'scope_violation')
        self.assertEqual(result['judgment']['forbidden_attempts'], ['write'])
        self.assertFalse((self.root / 'attune-negative/workspace/AGENTS.md').read_text().endswith('x'))
        self.assertEqual((self.root / 'attune-negative/workspace/artifacts/note.txt').read_text(), 'ok')
        published, _ = self.run_case('reveal-negative', {'parent': {'commands': ['bin/gh pr create --draft --fill']}})
        self.assertEqual(published['judgment']['forbidden_attempts'], ['publish'])
        # A write the sandbox misses is a breach of the selection-only boundary, never a pass.
        breach, _ = self.run_case('scan-negative', {'parent': {'commands': ['sh -c "echo x >> app.py"']}})
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
class ActivationProbe(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)

    def probe(self, plan, name):
        host = FakeHost(self, dict({'response': RESPONSE}, **plan))
        with host.environment():
            record = discovery_probe.probe(host.executable, self.root / name, MODEL, timeout=60)
        return record, host

    def statuses(self, record):
        return {k: v['status'] for k, v in record['capabilities'].items()}

    def test_observable_automatic_load_and_hidden_explicit_entry_are_verified(self):
        record, host = self.probe({'parent': {'commands': ['cat .agents/skills/probe-alpha/SKILL.md']}}, 'honored')
        self.assertEqual(self.statuses(record), {'installation': 'verified', 'skill_discovery': 'verified',
                                                 'explicit_only_honored': 'verified'})
        self.assertEqual(record['model_invocations'], 1)
        self.assertEqual(len(host.calls()), 1)
        call = host.calls()[0]
        self.assertNotIn(discovery.SKIP_FLAG, call['argv'])
        self.assertEqual(call['prompt'], discovery_probe.PROMPT)
        self.assertNotIn('probe-alpha', call['prompt'])
        self.assertNotIn('SKILL.md', call['prompt'])
        self.assertNotIn(str(self.root), json.dumps(record))
        # Copied into a registry beside focused containment evidence, the host is accepted for discovery.
        registry = evidence(self.root / 'registry', discovery_status=None)
        shutil.copy2(self.root / 'honored/host-evidence.json', registry / 'probe.json')
        self.assertTrue(hosts.assess(FAKE, 'discovery', directory=registry)['accepted'])

    def test_each_failure_mode_is_recorded_without_inference(self):
        both, _ = self.probe({'parent': {'commands': ['cat .agents/skills/probe-alpha/SKILL.md',
                                                      'cat .agents/skills/probe-beta/SKILL.md']}}, 'both')
        self.assertEqual(self.statuses(both)['explicit_only_honored'], 'failed')
        none, _ = self.probe({}, 'none')
        self.assertEqual(self.statuses(none)['skill_discovery'], 'failed')
        self.assertNotIn('explicit_only_honored', none['capabilities'])
        hidden, _ = self.probe({'hidden_load': ['probe-alpha']}, 'hidden')
        self.assertEqual(self.statuses(hidden)['skill_discovery'], 'unavailable')
        searched, _ = self.probe({'parent': {'commands': ['find .agents -name SKILL.md',
                                                          'cat .agents/skills/probe-alpha/SKILL.md']}}, 'searched')
        self.assertNotIn('skill_discovery', searched['capabilities'])
        self.assertTrue(any('searching the workspace' in note for note in searched['unknown']))
        lost, _ = self.probe({'parent': {'commands': ['cat .agents/skills/probe-alpha/SKILL.md']},
                              'malformed_event_after': 'item.completed'}, 'lost')
        self.assertEqual(self.statuses(lost)['skill_discovery'], 'failed')
        for name, record in (('both', both), ('none', none), ('hidden', hidden), ('searched', searched), ('lost', lost)):
            registry = evidence(self.root / ('registry-' + name), discovery_status=None)
            shutil.copy2(self.root / name / 'host-evidence.json', registry / 'probe.json')
            accepted = hosts.assess(FAKE, 'discovery', directory=registry)['accepted']
            self.assertEqual(accepted, name == 'both', name)

    def test_leaky_host_fails_without_a_model_call(self):
        record, host = self.probe({'containment': 'leaky'}, 'leaky')
        self.assertEqual(record['model_invocations'], 0)
        self.assertEqual(host.calls(), [])
        self.assertNotIn('skill_discovery', record['capabilities'])

    def test_recorded_hosts_are_not_yet_accepted_for_discovery(self):
        self.assertEqual(hosts.accepted_versions('discovery'), set())
        result = hosts.assess('codex-cli 0.163.0', 'discovery')
        self.assertEqual(result['missing'], ['skill_discovery=unknown'])

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
