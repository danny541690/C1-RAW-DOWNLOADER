"""Real remote quota race and one evidence-backed TAIFEX missing download."""
import argparse,concurrent.futures,gzip,hashlib,json,urllib.parse
from pathlib import Path
from scripts.v093_source_coordination import Coordinator,SOURCES
from scripts.v093_source_git_store import GitCAS
from scripts.v093_source_rate import reserve,RequestDeferred
from scripts.v093_source_worker import run_native_batch
from scripts.v093_legacy_handoff import normalize

def choose_taifex(audit_only=False):
 review=json.loads(gzip.decompress(Path('frozen/TAIFEX.review.json.gz').read_bytes()));choices=[];reasons={};examples={}
 for f in json.loads(Path('original/ledger_manifest.json').read_text()):
  if not f['path'].startswith(('TAIFEX_INDEPENDENT_STAGE06/','TAIFEX_INDEPENDENT_STAGE06_ASC/')):continue
  raw=gzip.decompress((Path('original')/f['local']).read_bytes())
  if hashlib.sha256(raw).hexdigest()!=f['sha256']:raise ValueError('FROZEN_LEDGER_SHA')
  obj=json.loads(raw)
  if not isinstance(obj,dict):continue
  rows,_=normalize(obj,f['path'],'TAIFEX',dict(file_id=f['id'],version=f['version'],sha256=f['sha256']))
  for row in rows:
   item=review['tasks'].get(row['task_key']);entry=obj.get(row['legacy_bucket'],{}).get(row['legacy_unit_id'],{});job=entry.get('request',{})
   if not item or item['action']!='CLASSIFY_APPLICABILITY_AND_MISSING_EVIDENCE':continue
   action=job.get('key','').split('|')[1] if job.get('key','').startswith('HISTORY|') else None
   form=obj.get('catalog',{}).get(action,{})
   reason=('RETRY_BUDGET_REQUIRES_REVIEW' if item['attempts']>=3 else
           'EXISTING_RAW_REUSE_FIRST' if any(v.get('raw_reference') for v in item['provenance']) else
           'LEGACY_STATUS_'+str(entry.get('status','UNKNOWN')) if entry.get('status')!='UNRESOLVED' else
           'RETAINED_QUARANTINE_RECHECK_FIRST' if entry.get('response_sha256') or entry.get('quarantine_file') else
           'INTERRUPTED_REQUEST_RECONCILIATION_FIRST' if entry.get('interrupted_request') else
           'NO_SUPPORTED_CSV_HISTORY_ROUTE' if job.get('kind')!='csv' or not action else
           'OFFICIAL_FORM_BOUNDARY_UNPROVEN' if not form.get('boundary_confirmed') else
           'OUTSIDE_CONFIRMED_FORM_RANGE' if not (form['first']<=job['start']<=job['end']<=form['last']) else
           'OFFICIAL_ROUTE_BINDING_MISMATCH' if job.get('url')!='https://www.taifex.com.tw/cht/3/'+action else 'ELIGIBLE')
   reasons.setdefault(row['task_key'],set()).add(reason)
   sample=dict(key=row['task_key'],legacy_status=entry.get('status'),kind=job.get('kind'),attempts=item['attempts'],action=action)
   if len(examples.setdefault(reason,[]))<3:examples[reason].append(sample)
   if reason!='ELIGIBLE':continue
   proof=dict(source='TAIFEX',key=row['task_key'],period=row['period'],availability_verified=True,official_evidence_id=f['id'],frozen_ledger_sha256=f['sha256'],source_form=form.get('source_page'),confirmed_query_bounds=dict(first=form['first'],last=form['last']),availability_semantics='PUBLISHED_FORM_QUERY_RANGE_NOT_PROOF_ROWS_EXIST')
   case=dict(source='TAIFEX',key=row['task_key'],period=row['period'],mode='MISSING',native_job=job,missing_evidence=proof)
   choices.append(dict(case=case,review=item))
 from collections import Counter
 combinations=Counter('|'.join(sorted(v)) for v in reasons.values())
 audit=dict(schema='JARVIS_TAIFEX_MISSING_ADMISSION_AUDIT_V1',review_candidate_tasks=sum(x['action']=='CLASSIFY_APPLICABILITY_AND_MISSING_EVIDENCE' for x in review['tasks'].values()),original_receipt_tasks_evaluated=len(reasons),reason_combinations=dict(combinations),examples=examples,eligible_tasks=len({x['case']['key'] for x in choices}),source_requests=0,formal_raw_writes=0,production_activation=False,acceptance='AUDIT_ONLY_NOT_MISSING_DOWNLOAD_PASS')
 out=Path('results');out.mkdir(exist_ok=True);(out/'admission-audit.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2)+'\n')
 if audit_only:return audit
 if not choices:raise ValueError('NO_ADMISSIBLE_TAIFEX_MISSING_CASE')
 return max(choices,key=lambda x:(x['case']['native_job']['end'],x['case']['key']))

def main():
 p=argparse.ArgumentParser();p.add_argument('--mode',choices=('quota','missing','audit'),required=True);p.add_argument('--source',choices=sorted(SOURCES),required=True);p.add_argument('--namespace',required=True);a=p.parse_args()
 c=Coordinator(GitCAS(Path.cwd(),'jarvis-source-preflight/'+a.namespace),a.source,ttl=600)
 if a.mode=='audit':result=choose_taifex(audit_only=True)
 elif a.mode=='quota':
  slots=['ASC','DESC'] if a.source not in ('NDC','FinMind') else ['DESC','DESC']
  keys=['quota-a','quota-b'];c.add([dict(source=a.source,key=key,slot=slot,period='2026-10-29') for key,slot in zip(keys,slots)])
  tickets=[c.claim(slot,key,slot) for key,slot in zip(keys,slots)]
  def take(ticket):
   try:reserve(c,ticket,limit=1,window=60,spacing=0);return 'RESERVED_NO_HTTP_SENT'
   except RequestDeferred as exc:c.defer(ticket,exc.seconds);return 'DEFERRED_WITHOUT_ATTEMPT'
  with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:outcomes=list(pool.map(take,tickets))
  _,state=c.store.read(a.source)
  if sorted(outcomes)!=['DEFERRED_WITHOUT_ATTEMPT','RESERVED_NO_HTTP_SENT'] or sum(x['cost'] for x in state['http_budget']['intents'])!=1 or any(t['attempts']!=0 for t in state['tasks'].values()):raise ValueError('SHARED_QUOTA_RACE_FAILURE')
  result=dict(schema='JARVIS_SOURCE_ADAPTER_QUOTA_QA_V1',mode='REAL_REMOTE_QUOTA_RACE',source=a.source,outcomes=outcomes,attempts_preserved=True,source_requests=0,formal_raw_writes=0,production_activation=False,limitation='Remote control budget race, not a measured provider throughput limit')
 else:
  if a.source!='TAIFEX':raise ValueError('ONLY_ONE_BOUNDED_REAL_MISSING_SOURCE')
  from scripts.annual_actual_firstpass import Drive,service
  chosen=choose_taifex();case=chosen['case'];old=chosen['review'];d=Drive(service())
  qa_root=d.folder('1p3Ij6ZGL4htYhhGKtEytU2MVOXW-wAit','JARVIS_NATIVE_ADAPTER_QA_'+a.namespace)
  c.add([dict(source='TAIFEX',key=case['key'],period=case['period'],slot='DESC')])
  c.update(lambda s:s['tasks'][case['key']].update(attempts=old['attempts'],legacy_review=old,execution_contract=case))
  batch=run_native_batch(c,d,'DESC','actual-native',qa_root,max_units=1,seconds=180)
  _,state=c.store.read('TAIFEX');task=state['tasks'][case['key']]
  result=dict(schema='JARVIS_SOURCE_ADAPTER_QUOTA_QA_V1',mode='REAL_TAIFEX_MISSING_NATIVE_BRIDGE',batch=batch,qa_root=qa_root,prior_attempts=old['attempts'],attempts=task['attempts'],source_http_intents=sum(x['cost'] for x in state.get('http_budget',{}).get('intents',[])),accepted=task['status']=='RAW_BASIC_VERIFIED',production_activation=False,full_acceptance=False)
 out=Path('results');out.mkdir(exist_ok=True);(out/'adapter.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(json.dumps(result),flush=True)
 if a.mode=='missing' and not result['accepted']:raise ValueError('REAL_MISSING_ADAPTER_NOT_ACCEPTED')
if __name__=='__main__':main()
