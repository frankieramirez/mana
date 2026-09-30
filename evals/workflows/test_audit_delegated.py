import json
from pathlib import Path
import tempfile
import unittest
from audit_delegated import audit
import delegated_review as d
import run


class Audit(unittest.TestCase):
    def test_complete_roles_and_collection_order_are_required(self):
        with tempfile.TemporaryDirectory() as temporary:
            out=Path(temporary)
            _,work,baseline=d.prepare(out,run.ROOT/'skills')
            roles=['protection-warrior','retribution-paladin','marksmanship-hunter','subtlety-rogue','havoc-demon-hunter']
            def command(role):
                return {'type':'commandExecution','id':role,'command':'python3 bin/probe.py '+role,
                        'aggregatedOutput':'containment verified '+role+'\n','exitCode':0,'status':'completed'}
            def thread(role,parent):
                return {'parentThreadId':parent,'cwd':str(work),'model':'pinned','reasoningEffort':'medium',
                        'turns':[{'id':role,'status':'completed','itemsView':'full','items':[
                            command(role),{'type':'agentMessage','phase':'final_answer','text':'result'}]}]}
            threads={'parent':thread('parent',None)}
            for role in roles+['validator']:threads[role]=thread(role,'parent')
            items=threads['parent']['turns'][0]['items']
            items[1:1]=[{'type':'subAgentActivity','kind':'completed','agentThreadId':role} for role in roles]
            merge={'type':'commandExecution','id':'merge','command':'bash installed/scan/scripts/review.sh merge artifacts/run',
                   'aggregatedOutput':'merged','exitCode':0,'status':'completed'}
            items.insert(-1,merge)
            result={'requested_model':'pinned','reasoning':'medium','baseline':baseline,'case':'delegated-full-review'}
            (out/'result.json').write_text(json.dumps(result))
            events=[{'type':'thread.started','thread_id':'parent'}]+[
                {'type':'item.completed','item':{'type':'command_execution','command':i['command'],
                 'aggregated_output':i['aggregatedOutput'],'exit_code':i['exitCode']}}
                for i in items if i['type']=='commandExecution']
            (out/'events.jsonl').write_text(''.join(json.dumps(e)+'\n' for e in events))
            (work/'artifacts/run').mkdir()
            review={'status':'ok','reviewers':[{'name':r,'status':'ok'} for r in roles]}
            (work/'artifacts/run/review.json').write_text(json.dumps(review))
            (out/'threads.json').write_text(json.dumps(threads))
            self.assertEqual([],audit(out)['failures'])
            items.remove(merge);items.insert(1,merge)
            (out/'threads.json').write_text(json.dumps(threads))
            self.assertIn('complete reviewer collection before first merge not observed',audit(out)['failures'])
            review['reviewers'].pop()
            (work/'artifacts/run/review.json').write_text(json.dumps(review))
            self.assertTrue(any('missing risk reviewer' in f for f in audit(out)['failures']))


if __name__=='__main__':unittest.main()
