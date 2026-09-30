import copy
from pathlib import Path
import unittest
from child_events import inspect, pages, collect


def thread(parent=None):
    return {'parentThreadId': parent, 'cwd': '/fixture', 'turns': [
        {'id':'turn','status':'completed','itemsView':'full','items':[
            {'type':'commandExecution','id':'cmd','command':'python3 bin/probe.py role',
             'aggregatedOutput':'containment verified role\n','exitCode':0,'status':'completed'},
            {'type':'agentMessage','phase':'final_answer','text':'done'}]}]}


class History(unittest.TestCase):
    def setUp(self):
        self.threads={'parent':thread(),'child':thread('parent')}
        self.threads['parent']['turns'][0]['items'].append(
            {'type':'subAgentActivity','agentThreadId':'child','kind':'started'})

    def check(self):
        return inspect(self.threads,'parent',Path('/fixture'))

    def test_attribution_keeps_same_local_ids_separate(self):
        events,failures=self.check()
        self.assertEqual([],failures)
        self.assertEqual({'parent','child'},{e['item']['thread_id'] for e in events})
        self.assertEqual(2,len(events))

    def test_missing_child_is_rejected(self):
        del self.threads['child']
        self.assertIn('referenced child missing from collection',self.check()[1])

    def test_missing_outcome_and_probe_are_rejected(self):
        item=self.threads['child']['turns'][0]['items'][0]
        item['exitCode']=None;item['aggregatedOutput']=None
        self.assertIn('missing command outcome: child',self.check()[1])
        self.assertIn('missing attributed containment probe: child',self.check()[1])

    def test_null_output_is_explicit_without_losing_exit_outcome(self):
        self.threads['child']['turns'][0]['items'].insert(1,
            {'type':'commandExecution','id':'write','command':'python3 write_artifact.py',
             'aggregatedOutput':None,'exitCode':0,'status':'completed'})
        events,failures=self.check()
        self.assertEqual([],failures)
        silent=next(e['item'] for e in events if e['item']['id']=='write')
        self.assertFalse(silent['output_available'])
        self.assertEqual(0,silent['exit_code'])

    def test_failed_or_summary_turn_rejected(self):
        for field,value in [('status','interrupted'),('itemsView','summary')]:
            data=copy.deepcopy(self.threads)
            data['child']['turns'][0][field]=value
            self.assertIn('incomplete turn history: child',inspect(data,'parent',Path('/fixture'))[1])

    def test_lineage_cycle_and_wrong_workspace_rejected(self):
        self.threads['child']['parentThreadId']='child'
        self.threads['child']['cwd']='/elsewhere'
        self.assertIn('unproven parent lineage: child',self.check()[1])
        self.assertIn('unexpected thread workspace: child',self.check()[1])

    def test_parent_cannot_substitute_child_probe(self):
        self.threads['child']['turns'][0]['items']=self.threads['child']['turns'][0]['items'][1:]
        self.assertIn('missing attributed containment probe: child',self.check()[1])

    def test_no_final_is_incomplete(self):
        self.threads['child']['turns'][0]['items'].pop()
        self.assertIn('missing final outcome: child',self.check()[1])

    def test_paginate_full_history(self):
        class Reader:
            def call(self,method,params):
                self.last=params
                return {'data':[params['cursor']], 'nextCursor':'next' if params['cursor'] is None else None}
        reader=Reader()
        self.assertEqual([None,'next'],pages(reader,'thread/turns/list',{'itemsView':'full'}))
        self.assertEqual('full',reader.last['itemsView'])

    def test_repeated_cursor_fails(self):
        class Reader:
            def call(self,*args):return {'data':[],'nextCursor':'same'}
        with self.assertRaisesRegex(ValueError,'repeated history cursor'):
            pages(Reader(),'thread/turns/list',{})


if __name__=='__main__':unittest.main()
