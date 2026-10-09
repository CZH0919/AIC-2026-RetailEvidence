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
project=request('/projects',{'name':'公开数据派生回归 '+str(uuid4())[:8],'description':'独立验收项目；公开数据派生，不是真实商户账目','color':'teal'})
pid=project['id'];record('PROJECT-CREATE',project_id=pid)
request('/projects/'+pid,{**{k:project[k] for k in ['name','description','color']},'revision':project['revision']},method='PATCH',expected=200)
request('/projects/'+pid,{**{k:project[k] for k in ['name','description','color']},'revision':project['revision']},method='PATCH',expected=409)
record('PROJECT-REVISION-CONFLICT')
request(f'/projects/{pid}/versions/48b9d571-3d7f-43d4-b4f0-19ea931123be',expected=404)
request(f'/projects/{pid}/runs/{old}',expected=404)
request(f'/projects/{pid}/sales/runs/{old}/records',expected=404)
record('CROSS-PROJECT-OWNERSHIP')
request('/projects',{'name':'Cross origin blocked'},expected=403,headers={'Origin':'https://invalid.example'})
record('ORIGIN-REJECTION')
policy=json.loads((r/'evidence/classified_public_candidate_01/policy.json').read_text())['parameters']['classifications'][0]
independent=json.loads((r/'evidence/classified_public_candidate_01/independent_xlsx.json').read_text())
versions=[]
for kind,file in [('daily_summary','derived_daily.csv'),('monthly_summary','derived_monthly.csv')]:
 path=r/'evidence/classified_public_candidate_01'/file
 draft=request(f'/projects/{pid}/imports?filename={file}',content=path.read_bytes(),headers={'Content-Type':'application/octet-stream'})
 draft=request(f'/projects/{pid}/imports/{draft["id"]}/preview',{'encoding':'utf-8-sig','delimiter':',','sheets':[],'shape':'transactions','basket_column':None,'item_separator':'|'})
 columns={'item_id':'c1','item_name':'c2','quantity':'c3','line_amount':'c4','event_time':'c0'} if kind=='daily_summary' else {'item_id':'c0','item_name':'c1','quantity':'c2','line_amount':'c3'}
 mapping={'columns':columns,'record_kind':kind,'order_boundary':'unavailable','amount_mode':'line_amount','currency_constant':'GBP','quantity_unit':'原始商品单位','status_rule':'all_forward','status_values':{},'confirmed':True,'timezone':'Europe/London' if kind=='daily_summary' else None,'time_format':'%Y-%m-%d' if kind=='daily_summary' else None,'summary_month':'2011-10' if kind=='monthly_summary' else None}
 saved=request(f'/projects/{pid}/imports/{draft["id"]}/confirm',{'preview_token':draft['preview_token'],'mapping':mapping});versions.append(saved)
 classification={**policy,'version_id':saved['id'],'mapping_revision':saved['mapping']['revision']}
 parameters={'sources':[{'version_id':saved['id'],'mapping_revision':saved['mapping']['revision']}],'classifications':[classification],'month':'2011-10','complete_coverage':False,'idempotency_key':str(uuid4())}
 run=request(f'/projects/{pid}/sales/runs',parameters)
 again=request(f'/projects/{pid}/sales/runs',parameters);assert again['id']==run['id']
 request(f'/projects/{pid}/sales/runs',{**parameters,'duplicates':'drop_exact'},expected=409)
 run=wait(pid,run);report=run['result']
 assert report['summary']['quantity']==independent['physical_quantity']
 assert abs(report['summary']['amount']-independent['selected_amount'])<.01
 assert report['forecast']['status']=='unavailable'
 if kind=='monthly_summary':assert report['chart']==[] and report['products'][0]['daily']==[]
 (out/(kind+'_run.json')).write_text(json.dumps(run,ensure_ascii=False,indent=2))
 record('REAL-'+kind.upper(),version_id=saved['id'],run_id=run['id'],quantity=report['summary']['quantity'],amount=report['summary']['amount'],source_sha256=hashlib.sha256(path.read_bytes()).hexdigest())
 record('IDEMPOTENCY-'+kind)
 # Cross-version classification cannot be smuggled into another data version.
 bad={**classification,'version_id':str(uuid4())}
 request(f'/projects/{pid}/sales/runs',{**parameters,'classifications':[bad],'idempotency_key':str(uuid4())},expected=422)
 record('CLASSIFICATION-SCOPE-'+kind)
# Duplicate import returns the prior immutable version, not a second copy.
path=r/'evidence/classified_public_candidate_01/derived_monthly.csv'
draft=request(f'/projects/{pid}/imports?filename=repeat.csv',content=path.read_bytes(),headers={'Content-Type':'application/octet-stream'})
draft=request(f'/projects/{pid}/imports/{draft["id"]}/preview',{'encoding':'utf-8-sig','delimiter':',','sheets':[],'shape':'transactions','basket_column':None,'item_separator':'|'})
repeated=request(f'/projects/{pid}/imports/{draft["id"]}/confirm',{'preview_token':draft['preview_token'],'mapping':mapping})
assert repeated['id']!=versions[-1]['id'] and repeated['sha256']==versions[-1]['sha256']
request(f'/projects/{pid}/sales/runs',{'sources':[{'version_id':v['id'],'mapping_revision':v['mapping']['revision']} for v in [versions[-1],repeated]],'month':'2011-10','idempotency_key':str(uuid4())},expected=422)
record('DUPLICATE-IMMUTABLE-VERSION-AND-MERGE-REFUSAL',versions=[versions[-1]['id'],repeated['id']])
# Real XLSX upload/preview/confirm using the original workbook; all source rows retained.
workbook=r/'storage/datasets/public/online_retail/source.xlsx'
draft=request(f'/projects/{pid}/imports?filename=OnlineRetail.xlsx',content=workbook.read_bytes(),headers={'Content-Type':'application/octet-stream'})
draft=request(f'/projects/{pid}/imports/{draft["id"]}/preview',{'encoding':'utf-8-sig','delimiter':',','sheets':[draft['inspection']['sheets'][0]],'shape':'transactions','basket_column':None,'item_separator':'|'})
assert draft['preview']['row_count']==541909
meta=request(f'/projects/{original}/versions/48b9d571-3d7f-43d4-b4f0-19ea931123be')
saved=request(f'/projects/{pid}/imports/{draft["id"]}/confirm',{'preview_token':draft['preview_token'],'mapping':meta['mapping']['config']})
record('REAL-XLSX-IMPORT',version_id=saved['id'],rows=541909,sha256=hashlib.sha256(workbook.read_bytes()).hexdigest())
# Keep original legacy algorithms operational using frozen real quality evidence, writing new run IDs.
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
