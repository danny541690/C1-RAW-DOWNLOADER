"""Bounded real missing TDCC capture through shared executor and isolated Drive.

Only old failed weekly tasks still offered by today's official date menu qualify.
Preserves prior attempts; no old successful RAW is downloaded again.
"""
import argparse,datetime,gzip,hashlib,http.cookiejar,json,re,urllib.parse,urllib.request
from pathlib import Path
from scripts import v093_tdcc_independent as native
from scripts.v093_source_coordination import Coordinator
from scripts.v093_source_executor import Executor
from scripts.v093_source_git_store import GitCAS


def select(review,dates):
 available=set(dates);rows=[]
 for key,item in review['tasks'].items():
  versions=item.get('provenance',[])
  if item.get('source')!='TDCC' or item.get('action')!='CLASSIFY_APPLICABILITY_AND_MISSING_EVIDENCE' or not versions or not 0<=item['attempts']<3:continue
  if any(v.get('raw_reference') or v.get('status') in ('SKIPPED_SOURCE_EMPTY','SKIPPED_NOT_PUBLISHED','SAVED_BASIC_VERIFIED','REQUEST_INTENT','PROCESSING') for v in versions):continue
  units={v.get('legacy_unit_id') for v in versions}
  if len(units)!=1:continue
  unit=next(iter(units));match=re.fullmatch(r'(20\d{6})\|([0-9A-Za-z]{4,8})',str(unit))
  if not match or match[1] not in available:continue
  if not any(v.get('status')=='UNRESOLVED' for v in versions):continue
  rows.append(dict(key=key,date=match[1],code=match[2],period=match[1][:4]+'-'+match[1][4:6]+'-'+match[1][6:],attempts=item['attempts'],legacy_review=item,missing_evidence='FROZEN_ALL_VERSIONS_NO_RAW_REF_FAILED_TASK_AND_CURRENT_OFFICIAL_MENU'))
 rows.sort(key=lambda x:(x['date'],x['code']))
 if not rows:return []
 chosen=[dict(rows[-1],slot='DESC')]
 if rows[0]['key']!=rows[-1]['key']:chosen.append(dict(rows[0],slot='ASC'))
 return chosen

class Adapter:
 download_authorized=True
 def __init__(self,drive,folder,job,worker=None,form=None):self.d=drive;self.folder=folder;self.job=job;self.worker=worker;self.form=form;self.crash=False;self.requests=0
 def find(self,key):return None
 def find_locator(self,name):
  found=self.d.find(self.folder,name);return found['id'] if found else None
 def read(self,ref):return self.d.call(lambda:self.d.api.files().get_media(fileId=ref))
 def locator(self,key,sha):return 'TDCC_'+self.job['date']+'_'+self.job['code']+'_'+sha+'.html'
 def fetch(self):
  if self.worker is None or not self.form:raise ValueError('LIVE_FORM_REQUIRED')
  fields=native.query_fields(self.form,self.job['date'],self.job['code']);self.requests+=1
  return self.worker.request(native.QUERY,urllib.parse.urlencode(fields).encode())
 def validate(self,raw):return dict(basic_verified=True,rows=native.validate_history(raw,self.job['date'],self.job['code']),source='TDCC',date=self.job['date'],code=self.job['code'])
 def put(self,name,raw):
  self.d.direct_readback=True;self.d.put(self.folder,name,raw,'text/html',overwrite=False)
  ref=self.find_locator(name)
  if not ref:raise ValueError('SAVED_REFERENCE_MISSING')
  if self.crash:raise OSError('QA_FAULT_AFTER_DRIVE_SAVE')
  return ref

def main():
 from scripts.annual_actual_firstpass import Drive,service
 p=argparse.ArgumentParser();p.add_argument('mode',choices=('start','resume'));p.add_argument('--namespace',required=True);a=p.parse_args()
 out=Path('results');out.mkdir(exist_ok=True);d=Drive(service());c=Coordinator(GitCAS(Path.cwd(),'jarvis-source-preflight/'+a.namespace),'TDCC',ttl=600)
 if a.mode=='start':
  worker=object.__new__(native.Worker);worker.requests=0;worker.opener=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
  page=worker.request(native.QUERY);form=page.decode('utf-8-sig');today=datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).strftime('%Y%m%d')
  dates=sorted({v for v in re.findall(r'<option\s+value="(20\d{6})"',form) if '20000101'<=v<=today})
  review=json.loads(gzip.decompress(Path('frozen/TDCC.review.json.gz').read_bytes()));jobs=select(review,dates)
  if not jobs:raise ValueError('NO_ADMISSIBLE_MISSING_TDCC_CASE')
  folder=d.folder('1p3Ij6ZGL4htYhhGKtEytU2MVOXW-wAit','JARVIS_TDCC_MISSING_QA_'+a.namespace)
  meta=dict(folder=folder,jobs=jobs,menu_sha256=hashlib.sha256(page).hexdigest(),menu_dates=dates,source_requests=0)
  (out/'case.json').write_text(json.dumps(meta,ensure_ascii=False))
  c.add([dict(source='TDCC',key=j['key'],period=j['period'],slot=j['slot']) for j in jobs])
  def seed(s):
   for j in jobs:s['tasks'][j['key']].update(attempts=j['attempts'],legacy_review=j['legacy_review'],missing_evidence=j['missing_evidence'],official_menu_sha256=meta['menu_sha256'])
  c.update(seed);outcomes=[]
  for job in jobs:
   adapter=Adapter(d,folder,job,worker,form);adapter.crash=True
   try:Executor(c,adapter).one(job['slot'],'live-'+job['slot'])
   except OSError as exc:
    if str(exc)!='QA_FAULT_AFTER_DRIVE_SAVE':raise
   else:raise ValueError('SAVE_FAULT_NOT_EXERCISED')
   c.update(lambda s:s['tasks'][job['key']].update(expires=0))
   outcomes.append(dict(key=job['key'],slot=job['slot'],prior_attempts=job['attempts'],fetches=adapter.requests))
  meta['source_requests']=worker.requests;(out/'case.json').write_text(json.dumps(meta,ensure_ascii=False))
  result=dict(mode='REAL_MISSING_SAVE_FAULT_INJECTED',tasks=outcomes,source_requests=worker.requests,production_activation=False,qa_folder=folder)
 else:
  meta=json.loads(Path('expected/case.json').read_text());outcomes=[]
  for job in meta['jobs']:
   adapter=Adapter(d,meta['folder'],job);evidence=Executor(c,adapter).resume(job['slot'],'cold-'+job['slot'])
   _,state=c.store.read('TDCC');task=state['tasks'][job['key']]
   if not evidence or task['status']!='RAW_BASIC_VERIFIED' or task['attempts']!=job['attempts']+1 or adapter.requests:raise ValueError('COLD_RESUME_INVARIANT')
   if task['legacy_review']!=job['legacy_review']:raise ValueError('PROVENANCE_LOST')
   outcomes.append(dict(key=job['key'],slot=job['slot'],date=job['date'],code=job['code'],prior_attempts=job['attempts'],attempts=task['attempts'],evidence=evidence))
  result=dict(mode='REAL_MISSING_TDCC_COLD_RESUME_PASS',tasks=outcomes,source_requests_this_job=0,total_source_requests=meta['source_requests'],production_activation=False,full_data_acceptance=False,limitation='Bounded missing TDCC weekly tasks only; seven-source production integration not complete')
 (out/(a.mode+'.json')).write_text(json.dumps(result,ensure_ascii=False,indent=2));print(json.dumps(result,ensure_ascii=False),flush=True)
if __name__=='__main__':main()
