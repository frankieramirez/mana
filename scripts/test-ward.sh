#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

# Offline contract tests for the simplified ward protocol.
python3 - <<'PY'
import json, os, pathlib, subprocess, tempfile
watch=pathlib.Path("skills/ward/scripts/pr-watch.sh")
MOCK='''#!/usr/bin/env python3
import json,os,pathlib,sys
r=pathlib.Path(os.environ["WARD_FIXTURE"]); a=sys.argv[1:]; d=json.loads((r/"fixture.json").read_text())
(r/"calls.log").open("a").write(json.dumps(a)+"\\n")
def out(x,code=0):
 if x: print(x,end="" if str(x).endswith("\\n") else "\\n")
 raise SystemExit(code)
def bad(x): print(x,file=sys.stderr); raise SystemExit(97)
if a[:2]==["pr","view"]:
 v=(d.get("views") or [d])[0]; d["views"]=(d.get("views") or [])[1:]; (r/"fixture.json").write_text(json.dumps(d))
 if "--jq" in a:
  print(json.dumps({k:v.get(k) for k in ('url','state','isDraft','mergeable','mergeStateStatus','headRefOid','headRefName','baseRefName','baseRefOid','author','closedAt','mergedAt','reviewDecision','headRepository','headRepositoryOwner')}))
  out(f"{v['url']}\\t{v.get('headRefOid') or '-'}\\t{v['state']}")
 out(json.dumps({k:v.get(k) for k in ('url','state','isDraft','mergeable','mergeStateStatus','headRefOid','headRefName','baseRefName','baseRefOid','author','closedAt','mergedAt','reviewDecision','headRepository','headRepositoryOwner')}))
elif a[:2]==["pr","checks"]:
 if "headSha" in a[a.index("--json")+1].split(","): bad("headSha is not native")
 out(d.get("checks","[]"),int(d.get("checks_exit",0)))
elif a[:2]==["repo","view"]: out(f"{d['owner']}\\t{d['repo']}\\t{d['repo_url']}")
elif a[:2]==["api","graphql"]:
 if any("mutation" in x for x in a): bad("mutation")
 cur=next((a[i+1].split("=",1)[1] for i,x in enumerate(a[:-1]) if x=="-f" and a[i+1].startswith("endCursor=")),"")
 if any(x.startswith("threadId=") for x in a):
  out("__WARD_CURSOR__"+"\\n"+"\\n".join(json.dumps(x,separators=(",",":")) for x in d.get("nested",[])))
 query=next(x for x in a if x.startswith("query="))
 if d.get("nested") and "comments(first: 100) {\\n            pageInfo" not in query: bad("nested cursor not requested")
 pages=d.get("thread_pages",[[]]); rows=[]
 for row in pages[1 if cur else 0]:
  key,_=row.split("\\t",1); rows += ["__WARD_NESTED__"+key.split(":",1)[1]+"\\t"+("nested" if d.get("nested") else ""),row]
 out("__WARD_CURSOR__"+("next" if not cur and len(pages)>1 else "")+"\\n"+"\\n".join(rows))
elif a[:1]==["api"] and len(a)>2 and a[2].startswith("repos/"):
 ep=a[2]; kind="comment" if ep.endswith("comments") else "review"; rows=[]
 for raw in d.get(kind+"s",[]):
  o=json.loads(raw); ident=str(o.get("id",o.get("node_id",""))); rows.append(kind+":"+ident+"\\t"+json.dumps({"kind":kind,"id":ident,"body":o.get("body",""),"resolved":False}))
 out("\\n".join(rows))
else: bad("unexpected gh call: "+" ".join(a))
'''
def fixture(r,**kw):
 d=dict(number=7,owner='acme',repo='widget',repo_url='https://github.com/acme/widget',url='https://github.com/acme/widget/pull/7',state='OPEN',isDraft=False,mergeable='MERGEABLE',mergeStateStatus='CLEAN',headRefOid='sha-a',headRefName='feature',baseRefName='main',baseRefOid='base',author={'login':'alice'},closedAt=None,mergedAt=None,reviewDecision='APPROVED',headRepository={'nameWithOwner':'acme/widget'},headRepositoryOwner={'login':'acme'},checks='[]',checks_exit=0,thread_pages=[[]],comments=[],reviews=[]); d.update(kw); (r/'fixture.json').write_text(json.dumps(d))
def run(r,*a,ok=True):
 e=os.environ|{'WARD_GH':str(r/'gh'),'WARD_STATE_ROOT':str(r/'state'),'WARD_FIXTURE':str(r)}; p=subprocess.run(['bash',str(watch),*a],env=e,text=True,capture_output=True)
 if (p.returncode==0)!=ok: raise AssertionError((a,p.returncode,p.stdout,p.stderr))
 return p
def snap(r,t='7'): return json.loads(run(r,'snapshot',t).stdout)
with tempfile.TemporaryDirectory(prefix='ward-') as td:
 r=pathlib.Path(td); (r/'gh').write_text(MOCK); (r/'gh').chmod(0o700); fixture(r)
 assert 'snapshot' in run(r,'--help').stdout and 'reserve retry' in run(r,'--help').stdout
 s=snap(r,'auto'); assert set(s)=={'pr','checks','feedback','state_path','snapshot_path'}; assert isinstance(s['checks'],list) and isinstance(s['feedback'],list)
 fixture(r,comments=[json.dumps({'id':'c1','body':'explain'})],reviews=[json.dumps({'id':3,'body':'review','state':'COMMENTED'})],thread_pages=[['thread:t1\t'+json.dumps({'kind':'inline','id':'t1','body':'inline','resolved':False,'comments':[{'id':'n1','body':'reply'}]})],['thread:t2\t'+json.dumps({'kind':'inline','id':'t2','body':'second','resolved':True,'comments':[{'id':'n2','body':'reply2'}]})]])
 s=snap(r); assert len(s['feedback'])>=3; x=next(x for x in s['feedback'] if x['key'].startswith('comment:')); token=x['key']+'@'+str(x['version'])
 fixture(r,comments=[json.dumps({'id':'c1','body':'changed'})]); changed=snap(r); changed_item=next(y for y in changed['feedback'] if y['key']==x['key']); assert changed_item['version'] != x['version']; run(r,'ack',s['pr']['url'],token,ok=False)
 fixture(r,comments=[json.dumps({'id':'c1','body':'explain'})]); restored=snap(r); current=next(y for y in restored['feedback'] if y['key']==x['key']); assert current['version'] != x['version']; run(r,'ack',s['pr']['url'],current['key']+'@'+str(current['version'])); assert any(y['acknowledged'] for y in snap(r)['feedback'])
 fixture(r,comments=[json.dumps({'id':'c1','body':'explain'})],headRefOid='sha-b'); h=snap(r); current=next(y for y in h['feedback'] if y['key']==x['key']); run(r,'ack',h['pr']['url'],current['key']+'@'+str(current['version']))
 fixture(r,state='CLOSED',fail='checks'); before=(r/'calls.log').read_text().count('"pr", "checks"'); assert snap(r)['pr']['state']=='CLOSED'; assert (r/'calls.log').read_text().count('"pr", "checks"')==before
 fixture(r,state='OPEN',headRefOid='sha-a'); snap(r); run(r,'reserve','retry',s['pr']['url'],'sha-a'); run(r,'reserve','retry',s['pr']['url'],'sha-a',ok=False); run(r,'reserve','fix',s['pr']['url'],'sha-a','BUG-1'); fixture(r,headRefOid='sha-b'); snap(r); run(r,'reserve','fix',s['pr']['url'],'sha-b','BUG-1'); fixture(r,headRefOid='sha-c'); snap(r); run(r,'reserve','fix',s['pr']['url'],'sha-c','BUG-1',ok=False)
 fixture(r,views=[dict(url=s['pr']['url'],headRefOid='x',state='OPEN'),dict(url=s['pr']['url'],headRefOid='y',state='OPEN')]); run(r,'snapshot',s['pr']['url'],ok=False)
 # Green checks still surface late feedback; repeated observations preserve exact versions.
 green='[{"name":"test","state":"SUCCESS","bucket":"pass","link":""}]'
 fixture(r,checks=green); empty=snap(r); assert not empty['feedback']
 def thread(resolved=False):
  return 'thread:reopen\t'+json.dumps(dict(kind='inline',id='reopen',threadId='reopen',resolved=resolved,comments=[dict(id='n',body='fix')]),separators=(',',':'))
 fixture(r,checks=green,thread_pages=[[thread()]],nested=[dict(id='later',body='later page')]); first=snap(r); item=first['feedback'][0]; assert len(item['data']['comments'])==2
 assert snap(r)['feedback']==first['feedback']
 old=item['key']+'@'+item['version']; run(r,'ack',s['pr']['url'],old)
 fixture(r,thread_pages=[[thread(True)]],nested=[dict(id='later',body='later page')]); snap(r)
 fixture(r,thread_pages=[[thread()]],nested=[dict(id='later',body='later page')]); reopened=snap(r)['feedback'][0]; assert not reopened['acknowledged'] and reopened['version']!=item['version']; run(r,'ack',s['pr']['url'],old,ok=False)
 # Failed checks are data. Transport failures and head races cannot commit partial observations.
 state=pathlib.Path(first['state_path']); before=(state/'state.tsv').read_bytes()
 fixture(r,checks='',checks_exit=1,comments=[json.dumps(dict(id='lost',body='partial'))]); run(r,'snapshot',s['pr']['url'],ok=False); assert (state/'state.tsv').read_bytes()==before
 fixture(r,checks='[]',checks_exit=8); assert snap(r)['checks']==[]
 fixture(r,checks='[{"bucket":"fail"}]',checks_exit=1); assert snap(r)['checks'][0]['bucket']=='fail'
 fixture(r,headRefOid='sha-b'); snap(r); run(r,'reserve','retry',s['pr']['url'],'sha-b')
 fixture(r,headRefOid='sha-a'); snap(r); run(r,'reserve','retry',s['pr']['url'],'sha-a',ok=False)
 for terminal in ('MERGED','CLOSED'):
  fixture(r,state=terminal,headRefOid=None,checks='',checks_exit=97); assert snap(r)['pr']['state']==terminal
 # Only read operations reached GitHub.
 calls=[json.loads(line) for line in (r/'calls.log').read_text().splitlines()]
 assert all(a[:2] in (['pr','view'],['pr','checks'],['api','graphql'],['api','--paginate']) for a in calls)
 fixture(r)
 state=pathlib.Path(snap(r)['state_path']); lines=(state/'state.tsv').read_text().splitlines(); assert lines[0].startswith('ward-v2\t') and lines[1].startswith('head\t'); (state/'operation.lock').mkdir(); (state/'operation.lock'/'pid').write_text('999999999\n'); run(r,'snapshot',s['pr']['url'],ok=False); (state/'operation.lock'/'pid').unlink(); (state/'operation.lock').rmdir(); (state/'state.tsv').write_text('corrupt\n'); run(r,'reserve','retry',s['pr']['url'],'sha-c',ok=False)
print('ward watcher fixture tests: ok')
PY
