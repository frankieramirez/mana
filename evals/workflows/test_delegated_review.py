from pathlib import Path
import json
import subprocess
import tempfile
import unittest
from unittest.mock import patch, MagicMock
import delegated_review as d
import run


class Fixture(unittest.TestCase):
    def test_fixture_has_distinct_supported_failures(self):
        namespace={}
        exec(d.BASE_APP,namespace)
        from types import SimpleNamespace as Obj
        document=Obj(tenant='a')
        member=Obj(active=True,role='member',tenant='a')
        outsider=Obj(active=True,role='admin',tenant='b')
        self.assertFalse(namespace['can_delete'](member,document))
        self.assertFalse(namespace['can_delete'](outsider,document))
        self.assertEqual(namespace['page']([1,2,3],2),[1,2])
        exec(d.BAD_APP,namespace)
        self.assertTrue(namespace['can_delete'](member,document))
        self.assertTrue(namespace['can_delete'](outsider,document))
        self.assertEqual(namespace['page']([1,2,3],2),[1])
        self.assertFalse(namespace['can_delete'](None,document))

    def test_preparation_preserves_frozen_baseline_and_detects_scope(self):
        with tempfile.TemporaryDirectory() as temporary:
            case,work,baseline=d.prepare(Path(temporary),run.ROOT/'skills')
            diff=run.git(work,'diff','origin/main')
            self.assertIn('return user.active',diff)
            self.assertEqual('app.py',run.git(work,'diff','--name-only','origin/main'))
            events=[{'type':'item.completed','item':{'type':'command_execution','command':'true','exit_code':0}}]
            response={'report':'review','checks':[]}
            self.assertEqual([],run.grade(case,work,baseline,response,events))
            (work/'legacy.py').write_text('MESSAGE = "Success"\n')
            self.assertTrue(any('out-of-scope' in f for f in run.grade(case,work,baseline,response,events)))

class Heldout(unittest.TestCase):
    def test_retry_and_queue_failures_are_independent(self):
        for source,expected_calls,raises,queue_after in [(d.HELDOUT_BASE,3,True,[1,2]),(d.HELDOUT_BAD,1,False,[2])]:
            namespace={};exec(source,namespace)
            calls=[]
            def broken():
                calls.append(1)
                raise OSError('offline')
            if raises:
                with self.assertRaises(OSError):namespace['fetch'](broken,3)
            else:
                self.assertIsNone(namespace['fetch'](broken,3))
            self.assertEqual(expected_calls,len(calls))
            queue=[1,2]
            def send(item):raise OSError('offline')
            with self.assertRaises(OSError):namespace['deliver'](queue,send)
            self.assertEqual(queue_after,queue)

    def test_heldout_fixture_diff_is_only_product_change(self):
        with tempfile.TemporaryDirectory() as temporary:
            _,work,_=d.prepare(Path(temporary),run.ROOT/'skills',True)
            self.assertEqual('app.py',run.git(work,'diff','--name-only','origin/main'))
            self.assertIn('Retry and delivery', (work/'spec.md').read_text())
            output=subprocess.check_output([str(work/'bin/gh'),'issue','view','7'],text=True)
            self.assertIn('propagates the last OSError',output)


class InterruptedEvents(unittest.TestCase):
    def execute_fixture(self, raw, timeout=False):
        temporary=tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        out=Path(temporary.name)
        prepared=d.prepare(out,run.ROOT/'skills')
        work=prepared[1]
        (work/'artifacts/run').mkdir()
        (work/'artifacts/run/review.json').write_text('{}')
        process=MagicMock()
        process.__enter__.return_value=process
        process.returncode=0
        def communicate(*args, **kwargs):
            if 'timeout' in kwargs:
                (out/'events.jsonl').write_text(raw)
                if timeout:raise subprocess.TimeoutExpired('fixture',1)
        process.communicate.side_effect=communicate
        threads={'parent':{'model':'pinned','reasoningEffort':'medium'},
                 'child':{'parentThreadId':'parent','model':'pinned','reasoningEffort':'medium'}}
        with patch.object(d.shutil,'which',return_value='/fixture/codex'), \
             patch.object(d.subprocess,'check_output',return_value=run.SUPPORTED_HOST), \
             patch.object(d,'prepare',return_value=prepared), \
             patch.object(run,'permission_config',return_value=[]), \
             patch.object(run,'preflight',return_value={}), \
             patch.object(d.subprocess,'Popen',return_value=process), \
             patch.object(d.os,'killpg'), \
             patch.object(d,'Reader') as reader, \
             patch.object(d,'collect',return_value=threads) as collector, \
             patch.object(d,'inspect',return_value=([],[])), \
             patch.object(run,'grade',return_value=[]):
            result=d.execute(out,run.ROOT/'skills',1,'pinned','medium')
            collected=collector.call_args
            closed=reader.return_value.close.called
        self.assertEqual(raw,(out/'events.jsonl').read_text())
        self.assertEqual(result,json.loads((out/'result.json').read_text()))
        return result,out,collected,closed

    def test_timeout_with_truncated_event_still_collects_child_history(self):
        raw='{"type":"thread.started","thread_id":"parent"}\n{"type":"item.completed"'
        result,out,collected,closed=self.execute_fixture(raw,timeout=True)
        self.assertEqual('timeout',result['execution'])
        self.assertIn('unparseable event at line 2',result['failures'])
        self.assertEqual('parent',collected.args[1])
        self.assertTrue(closed)
        self.assertTrue((out/'threads.json').is_file())
        self.assertTrue((out/'attributed-events.jsonl').is_file())
        self.assertFalse(result['accepted_execution'])

    def test_invalid_event_shapes_preserve_usage_and_collection_but_reject_run(self):
        raw='{}\nnull\n{"type":"thread.started","thread_id":"parent"}\n{"type":"turn.completed","usage":{}}\n'
        result,out,collected,_=self.execute_fixture(raw)
        self.assertEqual(['invalid event at line 1','invalid event at line 2'],result['failures'])
        self.assertEqual('parent',collected.args[1])
        self.assertEqual(1,len(result['usage']))
        self.assertTrue((out/'threads.json').is_file())
        self.assertFalse(result['accepted_execution'])

    def test_missing_parent_is_explicit_and_preserves_raw_evidence(self):
        result,out,collected,_=self.execute_fixture('{}\n')
        self.assertIsNone(collected)
        self.assertIn('ValueError: missing parent thread identity; descendant collection unavailable',result['failures'])
        self.assertFalse(result['accepted_execution'])


if __name__ == "__main__":
    unittest.main()
