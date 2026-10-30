"""Compile bounded, provenance-bound missing actions; never infer source availability.

A route authorizes a query only. Empty, interrupted, conflicting and exhausted
history is held. FinMind requires explicit official-gap/alignment proof. NDC
requires a checksummed source archive with the actual month in its tables.
"""
import argparse,collections,copy,gzip,hashlib,json,re
from pathlib import Path
from scripts.v093_legacy_handoff import normalize
from scripts.v093_native_reuse_batch import DEFAULT,descriptor
from scripts.v093_admission_runtime import prepare_row

SAFE={'WAIT_SHARED_SOURCE_WINDOW','RETRY_WAIT','ISOLATED_MISSING','UNRESOLVED_SOURCE_BACKOFF','SOURCE_CIRCUIT_WAIT','UNRESOLVED','FINMIND_GAP_UNRESOLVED','NOT_YET_PUBLISHED_IN_VERIFIED_SOURCE'}
RULES={'TWSE':'EXACT_DAILY_NATIVE_ROUTE','TPEx':'EXACT_DAILY_NATIVE_ROUTE','MOPS':'COMPLETED_REVENUE_MONTH_NATIVE_ROUTE','TAIFEX':'OFFICIAL_DATE_FILTER_FORM','NDC':'VERIFIED_ARCHIVE_MONTH','FinMind':'CONFIRMED_OFFICIAL_GAP_AND_ALIGNMENT'}

def eligibility(item):
 if item.get('action')!='CLASSIFY_APPLICABILITY_AND_MISSING_EVIDENCE':return 'REVIEW_ACTION_NOT_MISSING'
 if type(item.get('attempts')) is not int or not 0<=item['attempts']<4:return 'ATTEMPT_BUDGET'
 versions=item.get('provenance',[])
 if not versions:return 'NO_PROVENANCE'
 if any(v.get('raw_reference') for v in versions):return 'REUSE_EXISTING_RAW'
 if len({v.get('period') for v in versions})!=1:return 'PERIOD_CONFLICT'
 if any(v.get('status') not in SAFE for v in versions):return 'EMPTY_INTERRUPTED_OR_UNSUPPORTED_HISTORY'
 return None

def official_job(source,period,category):
 from scripts.v093_three_year_repair import Audit
 from scripts.v093_official_firstpass import LOWER_BOUNDS
 if source in ('TWSE','TPEx'):
  if category not in ('prices','prices_indices'):return None
  floor=LOWER_BOUNDS.get((source,category))
  if source=='TWSE' and (not floor or period<floor):return None
 elif source=='MOPS':
  if not re.fullmatch('revenue_(sii|otc)_[01]',category or ''):return None
 else:return None
 jobs=[j for j in Audit.jobs(object.__new__(Audit),period[:7],set()) if (j['source'],j['period'],j['category'])==(source,period,category)]
 return jobs[0] if len(jobs)==1 else None

def make_row(item,row,entry,document,origin):
 source=row['source'];period=row['period'];key=row['task_key']
 reason=eligibility(item)
 if reason:return None,reason
 if not any(v.get('ledger_origin')==origin and v.get('legacy_unit_id')==row['legacy_unit_id'] and v.get('period')==period for v in item['provenance']):return None,'LEDGER_REVIEW_BINDING'
 if entry.get('interrupted_request') or entry.get('quarantine_file') or entry.get('response_sha256'):return None,'RECONCILE_OR_RECHECK_QUARANTINE'
 proof=dict(source=source,key=key,period=period,availability_verified=False,official_evidence_id=origin['file_id'],frozen_ledger_sha256=origin['sha256'])
 case=dict(source=source,key=key,period=period,mode='MISSING',missing_evidence=proof)
 if source in ('TWSE','TPEx','MOPS'):
  job=official_job(source,period,entry.get('category'))
  if not job:return None,'UNSUPPORTED_NATIVE_ROUTE_OR_PERIOD'
  case['category']=entry['category'];proof.update(query_applicability_verified=True,native_route=job,query_semantics='QUERY_ONLY_NOT_ROWS_OR_HISTORICAL_EXISTENCE')
 elif source=='TAIFEX':
  job=entry.get('request',{});action=job.get('key','').split('|')[1] if job.get('key','').startswith('HISTORY|') else None
  form=document.get('catalog',{}).get(action,{})
  if job.get('kind')!='csv' or not action or not {'queryStartDate','queryEndDate'}<=set(form.get('fields',{})):return None,'OFFICIAL_FORM_NOT_PROVEN'
  case['native_job']=job;proof.update(query_applicability_verified=True,official_form=form)
 elif source=='NDC':
  # Unpublished months stay held until source archive content is independently read.
  return None,'VERIFIED_ARCHIVE_MONTH_REQUIRED'
 elif source=='FinMind':
  approved=entry.get('missing_evidence',{})
  if not all(approved.get(k) is True for k in ('confirmed_gap','identity_period_market_verified','definition_unit_frequency_verified','cross_source_alignment_approved')) or approved.get('official_source') not in ('TWSE','TPEx','MOPS'):return None,'OFFICIAL_GAP_ALIGNMENT_REQUIRED'
  if any(approved.get(k)!=case[k] for k in ('source','key','period')):return None,'FINMIND_PROOF_IDENTITY'
  desc=descriptor(source,row,entry)
  if not desc:return None,'FINMIND_NATIVE_JOB_REQUIRED'
  case['native_job']=desc['native_job'];proof.update(approved)
 else:return None,'SOURCE_RULE_NOT_SUPPORTED'
 candidate=dict(definition=dict(source=source,key=key,period=period,slot='DESC'),status='READY',attempts=item['attempts'],legacy_review=copy.deepcopy(item),execution_contract=case)
 try:return prepare_row(source,'DESC',key,candidate),None
 except (ValueError,KeyError,TypeError):return None,'NATIVE_CONTRACT_REJECTED'

def compile_rules(reviews,original=Path('original'),existing=()):
 known=set(existing);candidates={};reasons={s:{} for s in RULES};seen=set()
 manifest=json.loads((original/'ledger_manifest.json').read_text())
 for f in manifest:
  raw=gzip.decompress((original/f['local']).read_bytes())
  if hashlib.sha256(raw).hexdigest()!=f['sha256']:raise ValueError('MISSING_RULE_FROZEN_LEDGER_SHA')
  document=json.loads(raw)
  if f['name'].startswith('HISTORY_'):document={'history_receipts':document}
  if not isinstance(document,dict):continue
  origin=dict(file_id=f['id'],version=f['version'],sha256=f['sha256'])
  rows,_=normalize(document,f['path'],DEFAULT.get(f['path'].split('/')[0]),origin)
  entry_index={}
  for bucket_name,entries in document.items():
   if isinstance(entries,dict):
    for entry_key,entry in entries.items():
     if isinstance(entry,dict):entry_index.setdefault((bucket_name,str(entry.get('unit_id',entry_key))),[]).append(entry)
  for row in rows:
   source=row['source'];key=row['task_key']
   if source not in RULES or key not in reviews[source]:continue
   seen.add((source,key));item=reviews[source][key]
   if (source,key) in known:reason='ALREADY_IN_EXECUTION_QUEUE';candidate=None
   else:
    entries=entry_index.get((row['legacy_bucket'],row['legacy_unit_id']),[])
    if len(entries)!=1:candidate=None;reason='NATIVE_ENTRY_AMBIGUOUS'
    else:candidate,reason=make_row(item,row,entries[0],document,origin)
   reasons[source].setdefault(key,set()).add(reason or 'ELIGIBLE_QUERY')
   if candidate:
    prior=candidates.get((source,key))
    if prior and prior['execution_contract']!=candidate['execution_contract']:
     # Different receipt locators are fine only when the native route agrees.
     def signature(r):
      c=copy.deepcopy(r['execution_contract']);c.pop('missing_evidence');return c
     if signature(prior)!=signature(candidate):raise ValueError('MISSING_RULE_NATIVE_VERSION_CONFLICT')
    candidates[source,key]=candidate
 report=dict(schema='JARVIS_SOURCE_MISSING_RULES_V1',rules=RULES,source_requests=0,formal_raw_writes=0,production_activation=False,full_acceptance=False,sources={})
 for source in RULES:
  report['sources'][source]=dict(eligible_queries=sum(s==source for s,k in candidates),reason_combinations=dict(collections.Counter('|'.join(sorted(v)) for v in reasons[source].values())),unseen_review_tasks=sum((source,k) not in seen for k in reviews[source]),scope='Supported native contracts only; held tasks are not certified complete')
 return list(candidates.values()),report

def main():
 p=argparse.ArgumentParser();p.add_argument('--overlay-manifest');a=p.parse_args()
 reviews={s:json.loads(gzip.decompress(Path('frozen',s+'.review.json.gz').read_bytes()))['tasks'] for s in list(RULES)+['TDCC']}
 if a.overlay_manifest:
  from scripts.v093_handoff_overlays import apply_manifest
  from scripts.annual_actual_firstpass import Drive,service
  apply_manifest(Path.cwd(),reviews,a.overlay_manifest,Drive(service()))
 rows,report=compile_rules(reviews)
 Path('results').mkdir(exist_ok=True)
 Path('results/missing-rule-audit.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
 Path('results/missing-rule-actions.json').write_text(json.dumps(dict(schema='JARVIS_TYPED_APPROVED_ACTIONS_V1',actions=rows),ensure_ascii=False)+'\n')
 print(json.dumps(report,ensure_ascii=False),flush=True)
if __name__=='__main__':main()
