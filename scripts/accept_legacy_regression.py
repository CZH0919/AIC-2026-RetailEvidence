"""Isolation-only HTTP regression: imports, scoping, immutable runs, and legacy algorithms."""
import argparse
import hashlib
import json
import time
from pathlib import Path
from uuid import uuid4
import httpx

parser=argparse.ArgumentParser();parser.add_argument('--root',type=Path,required=True);args=parser.parse_args()
r=args.root;assert r.name=='retailevidence_personal_20261009_01'
out=r/'evidence/api_regression';out.mkdir(exist_ok=True)
client=httpx.Client(base_url='http://127.0.0.1:18081/api',timeout=180)
checks=[]

def request(path,data=None,method=None,content=None,expected=None,headers=None):
 response=client.request(method or ('POST' if data is not None or content is not None else 'GET'),path,json=data,content=content,headers=headers)
 if expected is not None:assert response.status_code==expected,(path,response.status_code,response.text[:500])
 else:response.raise_for_status()
 return response.json()

def record(id,**details):
 checks.append({'id':id,'status':'PASS',**details});(out/'checks.json').write_text(json.dumps(checks,ensure_ascii=False,indent=2));print(id,'PASS',flush=True)

def wait(project,run):
 start=time.monotonic()
 while run['status'] in ['queued','running','cancelling']:
  assert time.monotonic()-start<650,run
  time.sleep(1);run=request(f'/projects/{project}/runs/{run["id"]}')
 assert run['result'],run
 return run

original='e1711757-601a-4e9a-a05f-037d7e6909e6'
old='81278059-612c-498b-9dd4-be6377e449de'
old_report=request(f'/projects/{original}/runs/{old}')['result']
old_hash=hashlib.sha256(json.dumps(old_report,sort_keys=True).encode()).hexdigest()
record('LEGACY-REPORT-READ',run_id=old,products=old_report['summary']['products'])
quality='9d915bd8-1487-489d-9c8c-3f20f886fba2'
listing=request(f'/projects/{original}/runs?kind=quality&limit=100')['items']
quality=next(x['id'] for x in listing if x['dataset_version_id']=='48b9d571-3d7f-43d4-b4f0-19ea931123be' and x['status'] in ['succeeded','completed_with_warnings'])
for mode in ['rf','rfm']:
 run=request(f'/projects/{original}/runs/{quality}/cluster',{'parameters':{'kind':mode},'idempotency_key':str(uuid4())});run=wait(original,run)
 (out/(mode+'_run.json')).write_text(json.dumps(run,ensure_ascii=False,indent=2));record('LEGACY-'+mode.upper(),run_id=run['id'],summary=run['result']['summary'])
# Find the real Groceries project and its quality evidence in the isolated DB-derived API listing.
projects=request('/projects?limit=100')['items'];basket_project=None;basket_quality=None
for p in projects:
 for v in request(f'/projects/{p["id"]}/versions')['items']:
  if v.get('source_dataset')=='groceries':
   qualities=request(f'/projects/{p["id"]}/runs?kind=quality&limit=100')['items']
   hit=next((x for x in qualities if x['dataset_version_id']==v['id'] and x['status'] in ['succeeded','completed_with_warnings']),None)
   if hit:basket_project=p['id'];basket_quality=hit['id'];break
 if basket_project:break
assert basket_project,'Real Groceries quality run not found'
run=request(f'/projects/{basket_project}/runs/{basket_quality}/association',{'parameters':{'kind':'association'},'idempotency_key':str(uuid4())});run=wait(basket_project,run)
(out/'association_run.json').write_text(json.dumps(run,ensure_ascii=False,indent=2));record('LEGACY-FP-GROWTH',run_id=run['id'],summary=run['result']['summary'])
after=request(f'/projects/{original}/runs/{old}')['result'];assert hashlib.sha256(json.dumps(after,sort_keys=True).encode()).hexdigest()==old_hash
record('OLD-REPORT-IMMUTABLE',sha256=old_hash)
request(f'/projects/{original}/sales/runs/{old}/files/sales_classification.csv',expected=404)
record('OLD-MISSING-ARTIFACT-404')
request(f'/projects/{original}/sales/runs/{old}/files/..%2F..%2Fsecret',expected=404)
record('EXPORT-PATH-TRAVERSAL-REJECTED')
legacy_ai=request(f'/projects/{original}/sales/runs/{old}/ask',{'question':'下次进货先看什么？'});assert not legacy_ai['ai_used'] and legacy_ai.get('mode')=='data_limit'
record('LEGACY-CLASSIFICATION-AI-GUARD')
print('API_REGRESSION_PASS',len(checks),flush=True)
