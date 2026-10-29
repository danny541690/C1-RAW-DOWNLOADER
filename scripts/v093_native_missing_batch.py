"""Bounded actual missing TDCC query, native immutable save, sidecar and cold recovery.

Only frozen failed tasks with no RAW across their versions qualify. Known later
QA outcomes are excluded, not reset. Official menu proof authorizes a query, not
historical existence; an empty response is preserved and held.
"""
import argparse,copy,datetime,gzip,hashlib,http.cookiejar,json,re,urllib.request
from pathlib import Path
from scripts import v093_tdcc_independent as native
from scripts.v093_tdcc_missing_live import select
from scripts.v093_source_adapters import NativeAdapter
from scripts.v093_source_coordination import Coordinator
from scripts.v093_source_executor import Executor,ApplicabilityUnproven
from scripts.v093_source_git_store import GitCAS
from scripts.v093_admission_runtime import prepare_row

def later_qa_progress(root):
 """Never select a task already attempted by an earlier native QA run."""
 control=GitCAS(root,'jarvis-source-preflight/native-positive-history')
 raw=control.git('ls-remote','--heads','origin','refs/heads/jarvis-source-preflight/native-positive-*/TDCC').stdout.decode()
 refs=[]
 for line in raw.splitlines():
  commit,ref=line.split()
  if not re.fullmatch('[0-9a-f]{40}',commit) or not re.fullmatch(r'refs/heads/jarvis-source-preflight/native-positive-[0-9]+-[0-9]+/TDCC',ref):raise ValueError('NATIVE_QA_HISTORY_REF_SCOPE')
  refs.append((commit,ref))
 if len(refs)>64:raise ValueError('NATIVE_QA_HISTORY_REQUIRES_COMPACTION')
 tasks={};receipts=[]
 for expected,ref in sorted(refs):
  store=GitCAS(root,ref.removeprefix('refs/heads/').removesuffix('/TDCC'));commit,state=store.read('TDCC')
  if not state:raise ValueError('NATIVE_QA_HISTORY_STATE_MISSING')
  receipts.append(dict(ref=ref,commit=commit,observed_commit=expected))
  for key,task in state.get('tasks',{}).items():
   definition=task.get('definition',{})
   if definition.get('key')!=key or definition.get('source')!='TDCC' or type(task.get('attempts')) is not int:raise ValueError('NATIVE_QA_HISTORY_TASK_SCOPE')
   previous=tasks.get(key)
   if previous is None or task['attempts']>=previous['attempts']:tasks[key]=dict(status=task['status'],attempts=task['attempts'],has_save_intent=bool(task.get('save_intent')),period=definition['period'],ref=ref,commit=commit,raw_reference=task.get('raw_reference'),raw_sha256=task.get('raw_sha256'))
 return tasks,receipts

def main():
 from scripts.annual_actual_firstpass import Drive,service
 p=argparse.ArgumentParser();p.add_argument('mode',choices=('capture','resume'));p.add_argument('--namespace',required=True);a=p.parse_args();root=Path.cwd();out=Path('results');out.mkdir(exist_ok=True)
 c=Coordinator(GitCAS(root,'jarvis-source-preflight/'+a.namespace),'TDCC',ttl=600);d=Drive(service())
 if a.mode=='capture':
  if c.store.remote_head('TDCC')!=0:raise ValueError('FRESH_NATIVE_MISSING_NAMESPACE_REQUIRED')
  review=json.loads(gzip.decompress(Path('frozen/TDCC.review.json.gz').read_bytes()));excluded,qa_history=later_qa_progress(root)
  for key in excluded:review['tasks'].pop(key,None)
  # Preserve successful 6912 and held 8042 outcomes from the prior real download.
  _,prior=GitCAS(root,'jarvis-source-preflight/tdcc-missing-40853248163-1').read('TDCC')
  if not prior:raise ValueError('LATER_QA_HANDOFF_MISSING')
  for key,task in prior.get('tasks',{}).items():
   excluded[key]=dict(status=task['status'],attempts=task['attempts'],has_save_intent=bool(task.get('save_intent')));review['tasks'].pop(key,None)
  worker=object.__new__(native.Worker);worker.requests=0;worker.opener=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
  page=worker.request(native.QUERY);today=datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).strftime('%Y%m%d')
  dates=sorted({v for v in re.findall(r'<option\s+value="(20\d{6})"',page.decode('utf-8-sig')) if '20000101'<=v<=today})
  candidates=[]
  for _ in range(3):
   selected=select(review,dates)
   if not selected:break
   job=selected[0];candidates.append(job);review['tasks'].pop(job['key'])
  if not candidates:raise ValueError('NO_UNATTEMPTED_PROVEN_MISSING_CANDIDATE')
  folder=d.folder('1p3Ij6ZGL4htYhhGKtEytU2MVOXW-wAit','NATIVE_MISSING_'+a.namespace);menu_sha=hashlib.sha256(page).hexdigest();menu_name='official_menu_'+menu_sha+'.html';d.direct_readback=True;d.put(folder,menu_name,page,'text/html',overwrite=False);menu_ref=d.find(folder,menu_name)['id']
  c.update(lambda s:s.update(qa_root=folder,excluded_later_qa=excluded,qa_history=qa_history,initial_menu_source_requests=1))
  outcomes=[];saved=False;source_requests=1
  for job in candidates:
   proof=dict(source='TDCC',key=job['key'],period=job['period'],availability_verified=False,query_applicability_verified=True,official_evidence_id=menu_ref,official_menu=dict(url=native.QUERY,sha256=menu_sha,offered_dates=dates))
   case=dict(source='TDCC',key=job['key'],period=job['period'],mode='MISSING',date=job['date'],code=job['code'],missing_evidence=proof)
   row=dict(definition=dict(source='TDCC',key=job['key'],period=job['period'],slot='DESC'),attempts=job['attempts'],status='READY',legacy_review=job['legacy_review'],execution_contract=case)
   prepared=prepare_row('TDCC','DESC',job['key'],row)
   def seed(s):
    if job['key'] in s['tasks']:raise ValueError('DUPLICATE_TASK_NO_RESET')
    s['tasks'][job['key']]=copy.deepcopy(prepared)
   c.update(seed);adapter=NativeAdapter(c,d,dict(source='TDCC',key=job['key']),prepared,target_root=folder);put=adapter.put
   def fault(name,raw):
    put(name,raw);raise OSError('EXPLICIT_QA_FAULT_AFTER_NATIVE_RAW_SAVE')
   adapter.put=fault
   try:Executor(c,adapter).one('DESC','native-capture')
   except Exception as exc:
    _,state=c.store.read('TDCC');task=state['tasks'][job['key']]
    if isinstance(exc,OSError) and str(exc)=='EXPLICIT_QA_FAULT_AFTER_NATIVE_RAW_SAVE' and task.get('save_intent'):
     saved=True;outcome='REAL_RAW_SAVED_COLD_RESUME_REQUIRED'
    elif task['status'] in ('APPLICABILITY_HOLD','CONTENT_BLOCKED'):
     outcome='SOURCE_RESPONSE_HELD_NOT_CERTIFIED_ABSENCE'
    else:raise
   else:raise ValueError('FAULT_NOT_EXERCISED')
   source_requests+=adapter.source_requests;outcomes.append(dict(key=job['key'],period=job['period'],code=job['code'],status=outcome,prior_attempts=job['attempts'],attempts=task['attempts'],source_requests=adapter.source_requests,rejected_evidence=task.get('rejected_evidence')))
   c.update(lambda s:s.update(qa_capture_outcomes=outcomes,source_requests_total=source_requests))
   if saved:break
  result=dict(schema='JARVIS_NATIVE_MISSING_CAPTURE_V1',outcomes=outcomes,excluded_later_qa=excluded,qa_history=qa_history,source_requests=source_requests,qa_only=True,formal_raw_writes=0,production_activation=False,positive_saved=saved)
  (out/'native-missing-capture.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(json.dumps(result),flush=True)
  if not saved:raise ValueError('NO_POSITIVE_MISSING_RESULT_ACCEPTED')
 else:
  _,state=c.store.read('TDCC');outcomes=[]
  for key,task in state['tasks'].items():
   if not task.get('save_intent'):continue
   adapter=NativeAdapter(c,d,dict(source='TDCC',key=key),task,target_root=state['qa_root'])
   def never_fetch():raise AssertionError('COLD_RESUME_MUST_NOT_DOWNLOAD')
   adapter.fetch=never_fetch;evidence=Executor(c,adapter).resume('DESC','independent-native-resume')
   _,after=c.store.read('TDCC');t=after['tasks'][key]
   if t['status']!='RAW_BASIC_VERIFIED' or t['attempts']!=t['legacy_review']['attempts']+1 or not t.get('storage_receipt',{}).get('readback_verified'):raise ValueError('NATIVE_COLD_RAW_AND_SIDECAR_INVARIANT')
   outcomes.append(dict(key=key,period=t['definition']['period'],attempts=t['attempts'],evidence=evidence,storage_receipt=t['storage_receipt']))
  result=dict(schema='JARVIS_NATIVE_MISSING_COLD_RESUME_V1',outcomes=outcomes,source_requests_this_job=0,source_requests_total=state['source_requests_total'],formal_raw_writes=0,qa_downloaded_and_basic_verified=len(outcomes),formal_data_repaired=0,production_activation=False,full_acceptance=False)
  (out/'native-missing-resume.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(json.dumps(result),flush=True)
  if not outcomes:raise ValueError('NO_NATIVE_SAVED_RAW_TO_VERIFY')
if __name__=='__main__':main()
