from pathlib import Path
import subprocess
import tempfile
import unittest
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


if __name__ == "__main__":
    unittest.main()
