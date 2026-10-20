"""The paired integration runner, offline against fake_host.py and a synthetic consumer. No model is invoked."""
import json
import sys
import unittest

import integration
import integration_run
from test_integration import EXITS, Consumer

LINUX = sys.platform.startswith('linux')
RESPONSE = {'report': 'done', 'checks': []}


@unittest.skipUnless(LINUX, 'the fake sandbox and the process-family sweep target Linux')
class Runner(Consumer):
    def study(self, name='study'):
        result = integration.freeze(self.manifest(), self.base / name)
        return integration.FrozenIntegration(self.base / name, result['controls_sha256'])

    def plan(self, **plan):
        self.host.write(dict({'version': 'codex-cli 0.163.0', 'response': RESPONSE,
                              'parent': {'commands': ['python3 check.py']}}, **plan))

    def test_sandbox_preflight_runs_every_cell_without_a_model(self):
        study = self.study()
        record = integration_run.preflight(study, self.base / 'preflight')
        self.assertTrue(record['passed'], record)
        self.assertEqual(record['model_invocations'], 0)
        self.assertEqual(self.host.calls(), [], 'the preflight never runs exec')
        cells = {(row['family'], row['arm']): row for row in record['cells']}
        self.assertEqual(len(cells), 6)
        for (family, arm), row in cells.items():
            self.assertEqual(row['checks'][0]['exit'], EXITS[family])
            self.assertEqual(row['probe']['outside_listener'], 'refused')
            self.assertEqual(row['probe']['loopback'], 'allowed')
            self.assertEqual(row['head'], study.controls['families'][family]['fixtures'][arm]['head'])
            self.assertTrue((self.base / 'preflight' / ('%s-%s' % (family, arm)) / 'work/consumer/node_modules/pkg').is_dir())

    def test_a_wrong_expectation_fails_its_cell(self):
        self.families = [dict(f, checks=[dict(f['checks'][0], exit=7)]) if f['id'] == 'feature-change' else f
                         for f in self.families]
        record = integration_run.preflight(self.study(), self.base / 'preflight')
        self.assertFalse(record['passed'])
        failed = sorted((r['family'], r['arm']) for r in record['cells'] if r['failures'])
        self.assertEqual(failed, [('feature-change', 'baseline'), ('feature-change', 'control')])

    def test_a_leaky_host_fails_the_probe_before_any_check(self):
        self.host.write({'version': 'codex-cli 0.163.0', 'containment': 'leaky'})
        record = integration_run.preflight(self.study(), self.base / 'preflight')
        self.assertFalse(record['passed'])
        self.assertTrue(all('containment probe failed' in r['failures'][0] and not r['checks'] for r in record['cells']))

    def test_live_runs_all_twelve_slots_in_order_with_one_invocation_each(self):
        study = self.study()
        self.plan()
        rows = integration_run.run_all(study)
        self.assertEqual([r['schedule_slot'] for r in rows], list(range(1, 13)))
        self.assertEqual({r['execution'] for r in rows}, {'completed'})
        calls = self.host.calls()
        self.assertEqual(len(calls), 12)
        for cell, call in zip(study.schedule, calls):
            result = json.loads((study.root / 'results' / ('%03d' % cell['slot']) / 'result.json').read_text())
            family = study.controls['families'][cell['family']]
            self.assertEqual((result['family'], result['arm'], result['model_invocations']), (cell['family'], cell['arm'], 1))
            self.assertIsNone(result['task_outcome'])
            self.assertEqual(result['children']['judgment'], 'none')
            self.assertIn('/work/consumer/' + family['entrypoint'], call['prompt'])
            self.assertIn('zz-private-marker ' + cell['family'], call['prompt'])
            configs = call['options']['configs']
            self.assertIn('features.network_proxy=true', configs)
            self.assertIn('permissions.mana-eval.network.allow_local_binding=true', configs)
            self.assertNotIn('project_doc_max_bytes=0', configs, 'AGENTS.md must load in both arms')
            self.assertEqual(result['final_state'], result['initial_state'])
        prompts = {}
        for cell, call in zip(study.schedule, calls):
            prompts.setdefault(cell['family'], set()).add(call['prompt'].split('\n', 1)[1])
        self.assertTrue(all(len(texts) == 1 for texts in prompts.values()), 'both arms get the same request')
        self.assertEqual(integration_run.run_all(study), [], 'a finished slot never runs again')

    def test_a_created_child_stops_the_group(self):
        study = self.study()
        self.plan(collab_items=[{'tool': 'spawn_agent', 'receiver_thread_ids': ['thread-child']}])
        rows = integration_run.run_all(study)
        self.assertEqual(len(rows), 1)
        self.assertIn('child thread was created', rows[0]['stop_reason'])
        self.assertTrue((study.root / 'results/STOP.json').is_file())
        with self.assertRaisesRegex(ValueError, 'study stopped'):
            study.claim(2)

    def test_a_failed_spawn_is_attempted_and_the_group_continues(self):
        study = self.study()
        self.plan(stderr_lines=['ERROR codex_core::tools::router: error=collab spawn failed: no rollout found'],
                  collab_items=[{'tool': 'wait', 'receiver_thread_ids': []}])
        integration_run.run_slot(study, 1)
        result = json.loads((study.root / 'results/001/result.json').read_text())
        self.assertEqual((result['children']['judgment'], result['children']['empty_waits']), ('attempted', 1))
        self.assertIsNone(result['stop_reason'])

    def test_containment_failure_is_a_setup_failure_that_stops_the_group(self):
        study = self.study()
        self.plan(containment='leaky')
        rows = integration_run.run_all(study)
        self.assertEqual([(r['schedule_slot'], r['execution']) for r in rows], [(1, 'setup_failed')])
        self.assertEqual(self.host.calls(), [])

    def test_slots_run_in_order_and_once(self):
        study = self.study()
        self.plan()
        with self.assertRaisesRegex(ValueError, 'in order'):
            study.claim(2)
        integration_run.run_slot(study, 1)
        with self.assertRaises(FileExistsError):
            study.claim(1)
        self.assertFalse((study.root / 'results/.active').exists(), 'a refused claim releases the lock')

    def test_a_changed_runtime_refuses_the_slot(self):
        study = self.study()
        self.plan()
        (self.base / 'browsers/shell-1/chrome').write_text('swapped browser')
        result = integration_run.run_slot(study, 1)
        self.assertEqual(result['execution'], 'setup_failed')
        self.assertIn('runtime changed', result['stop_reason'])
        self.assertEqual(self.host.calls(), [])


if __name__ == '__main__':
    unittest.main()
