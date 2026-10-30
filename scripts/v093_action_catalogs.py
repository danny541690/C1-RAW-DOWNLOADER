"""Merge proof-bound fetch/repair/promotion actions into the common twelve queues.

Automatic missing selection is deliberately restricted to TDCC's proven date
menu and frozen unresolved tasks. Other sources require typed approved evidence,
not inferred availability. No downloads or formal activation happen here.
"""
import argparse,copy,hashlib,json,re
from pathlib import Path
from scripts.v093_admission_runtime import prepare_row,catalog_state,Catalog,code_digest
from scripts.v093_source_git_store import GitCAS
from scripts.v093_source_partition import COUNTS,partition
from scripts.v093_handoff_overlays import apply_manifest,apply_task
from scripts.v093_source_adapters import RAW_ROOT

def promotion_row(row,evidence_id):
 row=copy.deepcopy(row);case=row['execution_contract'];proof=dict(source=case['source'],key=case['key'],period=case['period'],reference=case.pop('reference'),sha256=case.pop('sha256'),verified_evidence_id=evidence_id)
 case.update(mode='PROMOTE',promotion_evidence=proof);row['status']='READY'
 return prepare_row(case['source'],row['definition']['slot'],case['key'],row)

def tdcc_missing_rows(review,proof,existing_identities):
 menu=proof['official_menu'];dates=set(menu['offered_dates']);result=[]
 for key,item in review.items():
  versions=item.get('provenance',[])
  if item.get('source')!='TDCC' or item.get('action')!='CLASSIFY_APPLICABILITY_AND_MISSING_EVIDENCE' or not versions or not 0<=item['attempts']<4:continue
  if any(v.get('raw_reference') or v.get('status') in ('SKIPPED_SOURCE_EMPTY','SKIPPED_NOT_PUBLISHED','SAVED_BASIC_VERIFIED','SAVED_RAW_ROWS_READBACK_VERIFIED','REQUEST_INTENT','FINMIND_REQUEST_INTENT','PROCESSING') for v in versions):continue
  units={v.get('legacy_unit_id') for v in versions}
  if len(units)!=1:continue
  match=re.fullmatch(r'(20\d{6})\|([0-9A-Za-z]{4,8})',str(next(iter(units))))
  if not match or match[1] not in dates or (match[1],match[2]) in existing_identities or not any(v.get('status')=='UNRESOLVED' for v in versions):continue
  period=match[1][:4]+'-'+match[1][4:6]+'-'+match[1][6:];bound=copy.deepcopy(proof);bound.update(source='TDCC',key=key,period=period,availability_verified=False,query_applicability_verified=True)
  case=dict(source='TDCC',key=key,period=period,mode='MISSING',date=match[1],code=match[2],missing_evidence=bound)
  row=dict(definition=dict(source='TDCC',key=key,period=period,slot='DESC'),status='READY',attempts=item['attempts'],legacy_review=item,execution_contract=case)
  try:prepared=prepare_row('TDCC','DESC',key,row)
  except ValueError:continue # Inconsistent old periods remain in the frozen review.
  result.append(prepared);existing_identities.add((match[1],match[2]))
 return result

def main():
 import gzip
 from scripts.annual_actual_firstpass import Drive,service
 p=argparse.ArgumentParser();p.add_argument('--namespace',required=True);a=p.parse_args();root=Path.cwd();baseline=json.loads(Path('inputs/final-handoff-catalogs.json').read_text());d=Drive(service())
 reviews={s:json.loads(gzip.decompress(Path('frozen',s+'.review.json.gz').read_bytes()))['tasks'] for s in COUNTS}
 overrides,_,overlays=apply_manifest(root,reviews,'config/v093_handoff_overlays.json',d)
 from scripts.v093_native_missing_batch import later_qa_progress
 _,history=later_qa_progress(root)
 static={e['prefix'] for e in json.loads(Path('config/v093_handoff_overlays.json').read_text())['states']}
 for entry in history:
  prefix=entry['ref'].removeprefix('refs/heads/').removesuffix('/TDCC')
  if prefix in static:continue
  commit,state=GitCAS(root,prefix).read('TDCC')
  if commit!=entry['commit']:raise ValueError('ACTION_QA_HISTORY_CHANGED')
  for key,task in state['tasks'].items():
   case=apply_task(reviews,'TDCC',key,task,dict(prefix=prefix,commit=commit))
   if case:overrides['TDCC',key]=case
   overlays.append(dict(source='TDCC',key=key,pin=commit,contract_retained=bool(case),status=task['status'],attempts=task['attempts']))
 _,qa=GitCAS(root,'jarvis-source-preflight/native-positive-40910020200-1').read('TDCC')
 if not qa:raise ValueError('PROVEN_TDCC_MENU_STATE_REQUIRED')
 native=qa['tasks']['TDCC|2025-12|20251205|8401'];proof=native['execution_contract']['missing_evidence']
 # Source menu bytes are independently bound to the recorded SHA before use.
 from scripts.v093_native_reuse_batch import Adapter
 menu_raw=Adapter(d,{}).read(proof['official_evidence_id'])
 if hashlib.sha256(menu_raw).hexdigest()!=proof['official_menu']['sha256']:raise ValueError('TDCC_MENU_SOURCE_SHA_CHANGED')
 proof=copy.deepcopy(proof);offered=set(re.findall(r'<option\s+value="(20\d{6})"',menu_raw.decode('utf-8-sig')))
 proof['official_menu']['offered_dates']=sorted(offered & set(proof['official_menu']['offered_dates']))
 rows_by_source={s:[] for s in COUNTS};promoted=[]
 targets={e['key']:e['pin'] for e in overlays if e['contract_retained'] and e['source']=='TDCC'}
 for source,directions in baseline['catalogs'].items():
  for slot,pin in directions.items():
   catalog=Catalog(GitCAS(root,'jarvis-source-preflight/action-catalog-reader'),pin,source,slot)
   for page in range(len(catalog.index['pages'])):
    for key,row in catalog.page(page):
     if key in targets:row=promotion_row(row,'PINNED_VERIFIED_QA:'+targets[key]);promoted.append(key)
     rows_by_source[source].append(row)
 existing_keys={r['definition']['key'] for r in rows_by_source['TDCC']}
 for (source,key),case in overrides.items():
  if source!='TDCC' or key in existing_keys:continue
  row=dict(definition=dict(source=source,key=key,period=case['period'],slot='DESC'),status='READY_CHECK',attempts=reviews[source][key]['attempts'],legacy_review=reviews[source][key],execution_contract=case)
  rows_by_source[source].append(promotion_row(row,'PINNED_VERIFIED_QA:'+targets[key]));promoted.append(key)
 known={(r['execution_contract'].get('date'),r['execution_contract'].get('code')) for r in rows_by_source['TDCC']}
 missing=tdcc_missing_rows(reviews['TDCC'],proof,known);rows_by_source['TDCC']+=missing
 approved=json.loads(Path('config/v093_approved_actions.json').read_text())
 if approved.get('schema')!='JARVIS_TYPED_APPROVED_ACTIONS_V1':raise ValueError('APPROVED_ACTION_SCHEMA')
 for supplied in approved['actions']:
  source=supplied['definition']['source'];key=supplied['definition']['key'];row=copy.deepcopy(supplied)
  if row.get('status')!='READY' or row.get('execution_contract',{}).get('mode') not in ('MISSING','REPAIR','PROMOTE'):raise ValueError('APPROVED_ACTION_MODE')
  row['legacy_review']=reviews[source][key];row['attempts']=max(row['attempts'],reviews[source][key]['attempts'])
  row=prepare_row(source,row['definition']['slot'],key,row)
  rows_by_source[source]=[r for r in rows_by_source[source] if r['definition']['key']!=key]+[row]
 pins={};counts={};samples={};total_modes={};assigned_by_key={}
 for source,rows in rows_by_source.items():
  if len({r['definition']['key'] for r in rows})!=len(rows):raise ValueError('ACTION_DUPLICATE_LOGICAL_KEY')
  costs=[dict(source=source,key=r['definition']['key'],period=r['definition']['period'],availability='PROVEN_APPLICABLE',estimated_cost=4 if r['execution_contract']['mode'] in ('MISSING','REPAIR') else 1) for r in rows]
  division=partition(costs,source,'2026-10-30');by_key={r['definition']['key']:r for r in rows};pins[source]={};counts[source]={}
  for slot,keys in [('DESC',division['latest_first'])]+([('ASC',division['oldest_first'])] if COUNTS[source]==2 else []):
   assigned=[]
   for key in keys:
    row=copy.deepcopy(by_key[key]);row['definition']['slot']=slot;assigned.append(row)
   assigned_by_key.update({r['definition']['key']:r for r in assigned})
   state=catalog_state(source,slot,assigned,'2026-10-30');store=GitCAS(root,'jarvis-source-preflight/actions-'+a.namespace+'-'+slot)
   if store.remote_head(source)!=0 or not store.cas(source,0,state):raise ValueError('ACTION_CATALOG_FRESH_NAMESPACE')
   commit=store.remote_head(source);index=store.git('show',commit+':state.json').stdout;pin=dict(commit=commit,index_sha256=hashlib.sha256(index).hexdigest());cold=Catalog(store,pin,source,slot)
   if sum(len(cold.page(i)) for i in range(len(cold.index['pages'])))!=len(assigned):raise ValueError('ACTION_CATALOG_COLD_READ')
   pins[source][slot]=pin;counts[source][slot]={mode:sum(r['execution_contract']['mode']==mode for r in assigned) for mode in ('RETAINED','MISSING','REPAIR','PROMOTE')}
  for row in rows:
   mode=row['execution_contract']['mode'];total_modes[mode]=total_modes.get(mode,0)+1
   if mode=='PROMOTE':samples.setdefault('promotions',[]).append(assigned_by_key[row['definition']['key']])
  if source=='TDCC':samples['missing']=[assigned_by_key[r['definition']['key']] for r in sorted(missing,key=lambda r:(r['definition']['period'],r['definition']['key']),reverse=True)[:3]]
 samples['promotions']=samples.get('promotions',[])[:2]
 out=Path('results');out.mkdir(exist_ok=True)
 report=dict(schema='JARVIS_TYPED_ACTION_CATALOGS_V1',source_sha=__import__('os').environ['GITHUB_SHA'],catalogs=pins,counts=counts,total_modes=total_modes,promotion_keys=promoted,automatic_missing_sources=['TDCC'],other_source_missing_scope='Only typed approved actions; unsupported/unproven tasks remain held',source_requests=0,formal_raw_writes=0,production_activation=False)
 proposed=dict(schema='JARVIS_NATIVE_RELEASE_V1',enabled=False,tested_code_sha256=code_digest(root),approved_checks=dict(source_contracts=False,continuation_and_quota=False,cutover=False),catalogs=pins,raw_root=RAW_ROOT,candidate_scope='RETAINED_PROMOTION_AND_PROVEN_TDCC_QUERY',missing_download_authority=bool(missing))
 for name,value in [('action-catalogs.json',report),('action-samples.json',samples),('proposed-action-release.json',proposed)]: (out/name).write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')
 print(json.dumps(dict(schema=report['schema'],total_modes=total_modes,automatic_missing_sources=['TDCC'],production_activation=False)),flush=True)
if __name__=='__main__':main()
