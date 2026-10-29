"""Freeze twelve release-candidate catalogs with later verified/held evidence.

Consumes completed native QA. Does not authorize source downloads or enable a
release. Unknown/empty files remain in preserved evidence, not runnable checks.
"""
import argparse,hashlib,json,os
from pathlib import Path
from scripts.v093_admission_runtime import catalog_state,Catalog,code_digest
from scripts.v093_source_git_store import GitCAS
from scripts.v093_source_adapters import RAW_ROOT

def filter_rows(source,rows,held):
 kept=[];removed=[]
 for row in rows:
  d=row['definition'];key=d['key'];evidence=held.get((source,key))
  if d['source']!=source:raise ValueError('FINAL_CATALOG_SOURCE')
  if not evidence:kept.append(row);continue
  case=row['execution_contract']
  if evidence['period']!=d['period'] or evidence['reference']!=case['reference'] or evidence['sha256']!=case['sha256']:raise ValueError('FINAL_HOLD_RECEIPT_BINDING')
  removed.append(evidence)
 return kept,removed

def main():
 p=argparse.ArgumentParser();p.add_argument('--namespace',required=True);p.add_argument('--qa-run',required=True);a=p.parse_args();root=Path.cwd();summary=json.loads(Path('inputs/twelve-native-summary.json').read_text())
 if summary.get('passed') is not True or len(summary['slots'])!=12:raise ValueError('COMPLETED_TWELVE_SLOT_EVIDENCE_REQUIRED')
 held={}
 for report in summary['slots']:
  if not report.get('units_held'):continue
  source=report['source'];slot=report['slot'];namespace=report['native_namespace']
  for chunk in range(report['cold_cursor']['chunk_number']):
   store=GitCAS(root,'jarvis-source-preflight/archive-'+namespace+'-'+slot+'-'+str(chunk));commit,snapshot=store.read(source)
   if not snapshot:raise ValueError('FINAL_HOLD_ARCHIVE_MISSING')
   for key,task in snapshot['tasks'].items():
    if task['status'] not in ('APPLICABILITY_HOLD','CONTENT_BLOCKED'):continue
    case=task['execution_contract']
    if task.get('error',{}).get('phase') not in ('VALIDATE','HASH_CHECK','READBACK'):raise ValueError('FINAL_HOLD_PHASE')
    held[source,key]=dict(source=source,key=key,period=task['definition']['period'],status=task['status'],reference=case['reference'],sha256=case['sha256'],attempts=task['attempts'],archive_commit=commit,archive_ref=store.ref(source),full_acceptance=False,confirmed_historical_absence=False)
 if len(held)!=summary['units_held']:raise ValueError('FINAL_HOLD_COUNTS')
 pins={};counts={};all_removed=[]
 for source,directions in summary['catalogs']['catalogs'].items():
  pins[source]={};counts[source]={}
  for slot,prior in directions.items():
   reader=GitCAS(root,'jarvis-source-preflight/final-catalog-reader');catalog=Catalog(reader,prior,source,slot);rows=[]
   for page in range(len(catalog.index['pages'])):rows.extend(row for _,row in catalog.page(page))
   kept,removed=filter_rows(source,rows,held);all_removed+=removed
   if any(row['status']!='READY_CHECK' for row in kept):raise ValueError('FINAL_CATALOG_RETAINED_ONLY_SCOPE')
   state=catalog_state(source,slot,kept,'2026-10-30');state['admission_catalog'].update(prior_catalog=prior,held_exclusions=removed,release_approved=False)
   store=GitCAS(root,'jarvis-source-preflight/final-catalog-'+a.namespace+'-'+slot)
   if store.remote_head(source)!=0 or not store.cas(source,0,state):raise ValueError('FINAL_CATALOG_FRESH_NAMESPACE')
   commit=store.remote_head(source);index=store.git('show',commit+':state.json').stdout;pin=dict(commit=commit,index_sha256=hashlib.sha256(index).hexdigest())
   cold=Catalog(store,pin,source,slot);restored=sum(len(cold.page(p)) for p in range(len(cold.index['pages'])))
   if restored!=len(kept):raise ValueError('FINAL_CATALOG_COLD_READ_COUNT')
   pins[source][slot]=pin;counts[source][slot]=restored
 if len(all_removed)!=len(held):raise ValueError('FINAL_EXCLUSIONS_NOT_ALL_APPLIED')
 out=Path('results');out.mkdir(exist_ok=True)
 proposed=dict(schema='JARVIS_NATIVE_RELEASE_V1',enabled=False,tested_code_sha256=code_digest(root),approved_checks=dict(source_contracts=False,continuation_and_quota=False,cutover=False),catalogs=pins,raw_root=RAW_ROOT,candidate_scope='RETAINED_NATIVE_CHECKS_ONLY',missing_download_authority=False)
 report=dict(schema='JARVIS_FINAL_HANDOFF_CATALOGS_V1',source_sha=os.environ['GITHUB_SHA'],prior_qa_run=a.qa_run,directions=sum(len(v) for v in pins.values()),candidate_counts=counts,retained_candidates=sum(sum(v.values()) for v in counts.values()),held_exclusions=all_removed,later_qa_overlays=summary['catalogs']['later_qa_overlays'],catalogs=pins,source_requests=0,formal_raw_writes=0,formal_state_writes=0,production_activation=False,missing_download_authority=False,limitation='Complete pinned retained-check handoff candidate; missing/repair task generation, scope approval and provider load are separate release gates')
 (out/'proposed-release.json').write_text(json.dumps(proposed,ensure_ascii=False,indent=2)+'\n');(out/'final-handoff-catalogs.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(json.dumps(dict(schema=report['schema'],directions=report['directions'],retained_candidates=report['retained_candidates'],held_exclusions=len(all_removed),production_activation=False)),flush=True)
if __name__=='__main__':main()
