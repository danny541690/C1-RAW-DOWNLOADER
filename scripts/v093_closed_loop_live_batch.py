"""One bounded missing TWSE task through real HTTP, isolated Drive and cold resume."""
import argparse,datetime,gzip,hashlib,json,os,urllib.parse,io,zipfile
from pathlib import Path
from scripts.v093_source_coordination import Coordinator
from scripts.v093_source_git_store import GitCAS
from scripts.v093_source_executor import Executor
class Adapter:
 download_authorized=True
 def __init__(self,drive,folder,job):self.d=drive;self.folder=folder;self.job=job;self.crash=False;self.requests=0;self.existing_reference=None
 def expected_receipt(self,key):return dict(source='TWSE',task_key=key,period=self.job['period'],reference=self.job.get('evidence_file'),sha256=self.job.get('sha256'))
 def find(self,key):return self.existing_reference
 def find_locator(self,name):
  f=self.d.find(self.folder,name);return f['id'] if f else None
 def read(self,ref):
  fid,sep,member=ref.partition('/')
  raw=self.d.call(lambda:self.d.api.files().get_media(fileId=fid))
  if sep:
   with zipfile.ZipFile(io.BytesIO(raw)) as z:
    if z.getinfo(member).file_size>32000000:raise ValueError('MEMBER_SIZE_LIMIT')
    raw=z.read(member)
  return raw
 def locator(self,key,sha):return sha+'.raw'
 def fetch(self):
  from scripts.v093_three_year_repair import request
  self.requests+=1;return request(self.job['url'],self.job.get('params'))
 def validate(self,raw):
  from scripts.v093_three_year_repair import validate
  from scripts.v093_independent_raw import price_checks
  stats=validate(raw,'TWSE',self.job['category'],self.job['period'])
  checks=price_checks(raw,'TWSE',self.job['period']) if self.job['category'] in ('prices','prices_indices') else None
  if checks and checks['ohlc_violations']:raise ValueError('OHLC_VIOLATION')
  return dict(basic_verified=True,native=stats,price_checks=checks)
 def put(self,name,raw):
  self.d.direct_readback=True;self.d.put(self.folder,name,raw,'application/octet-stream',overwrite=False)
  ref=self.find_locator(name)
  if self.crash:raise OSError('QA_FAULT_AFTER_ACTUAL_DRIVE_SAVE')
  return ref
def select():
 review=json.loads(gzip.decompress(Path('frozen/TWSE.review.json.gz').read_bytes()))
 manifest=json.loads(Path('original/ledger_manifest.json').read_text());candidates=[]
 from scripts import v093_three_year_repair as native
 from scripts.v093_official_firstpass import LOWER_BOUNDS
 routes={};trading_dates=set()
 primary=[]
 for f in manifest:
  if '/RAW/' in f['path'] and '/RECONCILE_REPAIR/' not in f['path'] and f['name']=='MONTH_STATE.json':
   obj=json.loads(gzip.decompress((Path('original')/f['local']).read_bytes()));primary.append((f,obj))
   for r in obj.get('units',{}).values():
    if r.get('source')=='TWSE' and r.get('category') in ('prices','prices_indices') and r.get('status')=='SAVED_BASIC_VERIFIED':trading_dates.add(r.get('period'))
 for f,obj in primary:
  for key,r in obj.get('units',{}).items():
   if r.get('source')!='TWSE' or r.get('category') not in {x[0] for x in native.DAILY['TWSE']} or r.get('evidence_file'):continue
   period=r.get('period','');task='TWSE|'+f['path'].split('/RAW/')[1][:7]+'|'+r.get('unit_id',key)
   item=review['tasks'].get(task)
   if not item or item['action']!='CLASSIFY_APPLICABILITY_AND_MISSING_EVIDENCE':continue
   if period not in trading_dates:continue
   earliest=LOWER_BOUNDS.get(('TWSE',r['category']))
   if not earliest:continue
   if not (earliest<=period<='2026-10-28') or len(period)!=10:continue
   if datetime.date.fromisoformat(period).weekday()>4:continue
   month=period[:7]
   if month not in routes:routes[month]={(j['category'],j['period']):j for j in native.Audit.jobs(object.__new__(native.Audit),month,set()) if j['source']=='TWSE'}
   route=routes[month].get((r['category'],period))
   if not route or urllib.parse.urlparse(route['url']).hostname!='www.twse.com.tw':continue
   candidates.append(dict(r,**{k:route[k] for k in ('url','month')},key=task,missing_evidence='NO_KNOWN_RAW_REFERENCE_IN_FROZEN_REVIEW',trading_date_evidence='SAVED_TWSE_PRICE_RECEIPT'))
 if not candidates:
  for f,obj in primary:
   for key,r in obj.get('units',{}).items():
    if r.get('source')=='TWSE' and r.get('category') in ('prices','prices_indices') and r.get('status')=='SAVED_BASIC_VERIFIED' and r.get('evidence_file'):
     return dict(r,key='retained-'+r.get('unit_id',key),test_mode='RETAINED_REUSE_ONLY_MISSING_CASE_NOT_AVAILABLE')
  raise RuntimeError('NO_ADMISSIBLE_MISSING_OR_RETAINED_CASE')
 return sorted(candidates,key=lambda r:r['period'],reverse=True)[0]
def main():
 from scripts.annual_actual_firstpass import Drive,service
 p=argparse.ArgumentParser();p.add_argument('mode',choices=['start','resume']);p.add_argument('--namespace',required=True);a=p.parse_args()
 out=Path('results');out.mkdir(exist_ok=True);d=Drive(service());store=GitCAS(Path.cwd(),'jarvis-source-preflight/'+a.namespace);c=Coordinator(store,'TWSE',ttl=3600)
 if a.mode=='start':
  job=select();folder=None if job.get('test_mode') else d.folder('1p3Ij6ZGL4htYhhGKtEytU2MVOXW-wAit','JARVIS_TWELVE_E2E_QA_'+a.namespace)
  metadata=dict(job=job,folder=folder,namespace=a.namespace);(out/'case.json').write_text(json.dumps(metadata))
  c.add([dict(source='TWSE',key=job['key'],slot='DESC',period=job['period'])]);adapter=Adapter(d,folder,job);adapter.crash=True
  if job.get('test_mode'):
   adapter.crash=False;adapter.existing_reference=job['evidence_file']
   evidence=Executor(c,adapter).one('DESC','retained-reuse')
   badkey=job['key']+'-sha-probe';c.add([dict(source='TWSE',key=badkey,slot='DESC',period=job['period'])])
   bad=Adapter(d,folder,dict(job,sha256='0'*64));bad.existing_reference=job['evidence_file']
   try:Executor(c,bad).one('DESC','wrong-sha-probe')
   except ValueError as exc:
    if str(exc)!='RETAINED_EXPECTED_SHA_MISMATCH':raise
   else:raise RuntimeError('WRONG_EXPECTED_SHA_NOT_BLOCKED')
   _,check=store.read('TWSE')
   if check['tasks'][badkey]['status']!='CONTENT_BLOCKED' or check['tasks'][badkey]['attempts']!=0:raise RuntimeError('HASH_HOLD_NOT_DURABLE')
   result=dict(mode=job['test_mode'],expected_sha_bound=True,wrong_expected_sha_blocked=True,evidence=evidence,source_requests=0,production_writes=0,required_missing_download_test='NOT_EXECUTED_NO_ELIGIBLE_CASE',ready_for_production=False)
   (out/'start.json').write_text(json.dumps(result,ensure_ascii=False,indent=2));print(json.dumps(result,ensure_ascii=False),flush=True);return
  try:Executor(c,adapter).one('DESC','live-first')
  except OSError as exc:
   if str(exc)!='QA_FAULT_AFTER_ACTUAL_DRIVE_SAVE':raise
  else:raise RuntimeError('CRASH_NOT_EXERCISED')
  # Deliberate expiry injection only inside unique QA namespace. Fresh job must recover without source HTTP.
  c.update(lambda s:s['tasks'][job['key']].update(expires=0))
  result=dict(mode='START_FAULT_INJECTED',source_requests=adapter.requests,production_writes=0,qa_drive_folder=folder)
 else:
  meta=json.loads(Path('expected/case.json').read_text());adapter=Adapter(d,meta['folder'],meta['job'])
  if meta['job'].get('test_mode'):
   raw=adapter.read(meta['job']['evidence_file']);stats=adapter.validate(raw)
   _,state=store.read('TWSE');task=state['tasks'][meta['job']['key']]
   if task['status']!='RAW_BASIC_VERIFIED' or task['attempts']!=0 or adapter.requests:raise RuntimeError('REUSE_COLD_RESTORE_INVARIANT')
   bad=state['tasks'][meta['job']['key']+'-sha-probe']
   if bad['status']!='CONTENT_BLOCKED' or bad['attempts']!=0:raise RuntimeError('HASH_HOLD_LOST_ON_RESTART')
   result=dict(mode='REAL_RETAINED_REUSE_AND_COLD_REVALIDATION_PASS',expected_sha_bound=True,wrong_expected_sha_hold_restored=True,source_requests=0,attempts=0,stats=stats,required_missing_download_test='NOT_EXECUTED_NO_ELIGIBLE_CASE',ready_for_production=False,full_data_acceptance=False)
   (out/'resume.json').write_text(json.dumps(result,ensure_ascii=False,indent=2));print(json.dumps(result,ensure_ascii=False),flush=True);return
  evidence=Executor(c,adapter).resume('DESC','fresh-runner')
  _,state=store.read('TWSE');task=state['tasks'][meta['job']['key']]
  if task['status']!='RAW_BASIC_VERIFIED' or task['attempts']!=1 or adapter.requests:raise RuntimeError('RESUME_INVARIANT')
  result=dict(mode='COLD_RESUME_PASS',evidence=evidence,source_requests_this_job=0,total_source_requests=1,attempts=task['attempts'],production_writes=0,full_data_acceptance=False,
   limitation='One actual missing TWSE native-price task; other source executors and workflow-dispatch continuation not accepted by this test')
 (out/(a.mode+'.json')).write_text(json.dumps(result,ensure_ascii=False,indent=2));print(json.dumps(result,ensure_ascii=False),flush=True)
if __name__=='__main__':main()
