#!/usr/bin/env python3
"""Offline reinspection of retained execution; never replaces the original result."""
from collections import Counter
import json
import re
from pathlib import Path
import sys
import tempfile
from child_events import inspect
import run


def signature(command):
    return (command['command'],command.get('aggregated_output',''),command.get('exit_code'))


def audit(directory):
    result=json.loads((directory/'result.json').read_text())
    threads=json.loads((directory/'threads.json').read_text())
    parent_events=[json.loads(l) for l in (directory/'events.jsonl').read_text().splitlines()]
    parent=next(e['thread_id'] for e in parent_events if e['type']=='thread.started')
    work=directory/'workspace'
    events,failures=inspect(threads,parent,work)
    persisted_parent=[e['item'] for e in events if e['item']['thread_id']==parent]
    if Counter(map(signature,persisted_parent)) != Counter(map(signature,run.command_events(parent_events))):
        failures.append('CLI and persisted parent command coverage differ')
    for identity,t in threads.items():
        if identity != parent and t.get('parentThreadId') != parent:
            failures.append('unexpected nested child: '+identity)
        if t.get('model') not in (None,result['requested_model']) or t.get('reasoningEffort') not in (None,result['reasoning']):
            failures.append('model/reasoning pin mismatch: '+identity)
    baseline=result['baseline']
    final={'head':run.git(work,'rev-parse','HEAD'),'index':run.git(work,'diff','--cached','--binary'),
           'product_state':run.product_state(work)}
    for field in final:
        if final[field] != baseline[field]:failures.append('changed '+field)
    response=json.loads((work/'artifacts/run/review.json').read_text())
    if response.get('status')!='ok':failures.append('review reports degraded execution')
    roles={r['name'] for r in response.get('reviewers',[])}
    required={'protection-warrior','retribution-paladin','marksmanship-hunter','havoc-demon-hunter'}
    required.add('restoration-shaman' if result['case']=='delegated-heldout-review' else 'subtlety-rogue')
    if required-roles:failures.append('missing risk reviewer: '+','.join(sorted(required-roles)))
    for reviewer in response.get('reviewers',[]):
        if reviewer.get('status')!='ok':failures.append('reviewer failed: '+reviewer['name'])
    child_commands={identity:[e['item'] for e in events if e['item']['thread_id']==identity]
                    for identity in threads if identity != parent}
    role_threads={role:[identity for identity,commands in child_commands.items()
                       if any(('containment verified '+role+'\n') in c['aggregated_output'] and c['exit_code']==0 for c in commands)]
                  for role in roles | {'validator'}}
    for role,identities in role_threads.items():
        if len(identities)!=1:failures.append('missing or ambiguous attributed role: '+role)
    used=[identities[0] for identities in role_threads.values() if len(identities)==1]
    if len(used)!=len(set(used)):failures.append('reviewer and validator roles reused a thread')
    completed, first_merge_completed = set(), None
    for turn in threads[parent]['turns']:
        for item in turn['items']:
            if item['type']=='subAgentActivity' and item.get('kind')=='completed':
                completed.add(item['agentThreadId'])
            if (first_merge_completed is None and item['type']=='commandExecution'
                    and re.search(r"review\.sh['\"]?\s+merge",item['command'])):
                first_merge_completed=set(completed)
    expected={identity for role,identities in role_threads.items() if role!='validator' for identity in identities}
    collection_before_merge=first_merge_completed is not None and expected <= first_merge_completed
    if not collection_before_merge:failures.append('complete reviewer collection before first merge not observed')
    # The raw child outputs remain the authority for final reviewer and validator judgments.
    finals={identity:[i['text'] for turn in t['turns'] for i in turn['items']
                     if i['type']=='agentMessage' and i.get('phase')=='final_answer']
            for identity,t in threads.items() if identity != parent}
    contexts={identity:run.context_metrics([e for e in events if e['item']['thread_id']==identity],work/'installed/scan')
              for identity in threads}
    return {'agent_executed':False,'grader_sha256':run.file_hash(Path(__file__)),
            'child_adapter_sha256':run.file_hash(Path(__file__).with_name('child_events.py')),'source_result_sha256':run.file_hash(directory/'result.json'),
            'failures':failures,'parent_command_parity':not any('coverage differ' in f for f in failures),
            'final_state':final,'context_by_thread':contexts,'child_final_messages':finals,
            'null_output_commands':[{'thread_id':e['item']['thread_id'],'id':e['item']['id'],'exit_code':e['item']['exit_code']} for e in events if not e['item']['output_available']],
            'collection_before_merge':collection_before_merge,'role_threads':role_threads,'reported_roster':sorted(roles),'reported_requirements':response.get('requirements'),
            'manual_judgment_required':True}


if __name__=='__main__':
    directory=Path(sys.argv[1]).resolve()
    source=directory/'offline-audit-source'
    source.mkdir(exist_ok=True)
    for name in ('audit_delegated.py','child_events.py','run.py','review_fixtures.py'):
        path=Path(__file__).with_name(name)
        (source/(path.stem+'-'+run.file_hash(path)+path.suffix)).write_bytes(path.read_bytes())
    report=audit(directory)
    with tempfile.NamedTemporaryFile(mode='w',prefix='audit-',suffix='.json',dir=directory,delete=False) as file:
        json.dump(report,file,indent=2);file.write('\n');print(file.name)
    print(json.dumps({'failures':report['failures'],'parent_command_parity':report['parent_command_parity']}))
    sys.exit(bool(report['failures']))
