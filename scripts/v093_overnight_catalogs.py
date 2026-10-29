"""Compile read-only candidate catalogs once from frozen receipts, never authorize downloads.

The frozen source reviews are the complete handoff denominator. Unsupported,
conflicting and missing cases remain explicitly held; no candidate is production
approved. A later execution must independently validate its actual bytes.
"""
import argparse,collections,copy,gzip,hashlib,json,re
from pathlib import Path
from scripts.v093_native_reuse_batch import DEFAULT,descriptor
from scripts.v093_legacy_handoff import normalize
from scripts.v093_admission_runtime import catalog_state,Catalog,prepare_row
from scripts.v093_source_git_store import GitCAS
from scripts.v093_source_partition import COUNTS

def receipt_contract(source,row,entry):
 if source=='TWSE':
  if entry.get('category') not in ('prices','prices_indices'):return None
  return dict(source=source,key=row['task_key'],period=row['period'],reference=row['raw_reference'],sha256=row['sha256'],category=entry['category'])
 if source=='TDCC':
  match=re.fullmatch(r'(20\d{6})\|([0-9A-Za-z]{4,8})',str(row.get('legacy_unit_id','')))
  if not match or row['period']!=match[1][:4]+'-'+match[1][4:6]+'-'+match[1][6:]:return None
  return dict(source=source,key=row['task_key'],period=row['period'],reference=row['raw_reference'],sha256=row['sha256'],date=match[1],code=match[2])
 return descriptor(source,row,entry)

def bound_row(source,item,case,slot):
 periods={v.get('period') for v in item.get('provenance',[])}
 row=dict(definition=dict(source=source,key=item['task_key'],period=case['period'],slot=slot),attempts=item['attempts'],status='READY_CHECK',legacy_review=item,execution_contract=dict(case,mode='RETAINED'))
 if item.get('action')!='VERIFY_RETAINED_RAW_FIRST' or periods!={case['period']}:raise ValueError('UNREVIEWED_OR_CONFLICTING_RECEIPT')
 return prepare_row(source,slot,item['task_key'],row)

def main():
 p=argparse.ArgumentParser();p.add_argument('--namespace',required=True);a=p.parse_args();root=Path.cwd();out=Path('results');out.mkdir(exist_ok=True)
 reviews={s:json.loads(gzip.decompress(Path('frozen',s+'.review.json.gz').read_bytes()))['tasks'] for s in COUNTS}
 contracts={s:{} for s in COUNTS};errors=collections.Counter();ledger_count=0
 for f in json.loads(Path('original/ledger_manifest.json').read_text()):
  raw=gzip.decompress(Path('original',f['local']).read_bytes())
  if hashlib.sha256(raw).hexdigest()!=f['sha256']:raise ValueError('FROZEN_LEDGER_SHA')
  ledger_count+=1;obj=json.loads(raw)
  if f['name'].startswith('HISTORY_'):obj={'history_receipts':obj}
  if not isinstance(obj,dict):continue
  index={}
  for bucket,entries in obj.items():
   if isinstance(entries,dict):
    for key,entry in entries.items():
     if isinstance(entry,dict):index.setdefault((bucket,str(entry.get('unit_id',key))),[]).append(entry)
  rows,_=normalize(obj,f['path'],DEFAULT.get(f['path'].split('/')[0]),dict(file_id=f['id'],version=f['version'],sha256=f['sha256']))
  for row in rows:
   source=row['source'];item=reviews[source].get(row['task_key'])
   if not item or item.get('action')!='VERIFY_RETAINED_RAW_FIRST' or not row.get('raw_reference') or not re.fullmatch('[0-9a-f]{64}',row.get('sha256') or ''):continue
   entries=index.get((row['legacy_bucket'],row['legacy_unit_id']),[])
   if len(entries)!=1:continue
   case=receipt_contract(source,row,entries[0])
   if case:
    try:bound_row(source,item,case,'DESC')
    except (ValueError,KeyError,TypeError):errors[source+'|CONTRACT_NOT_ADMITTED']+=1;continue
    prior=contracts[source].get(row['task_key'])
    if prior and (prior['reference'],prior['sha256'])!=(case['reference'],case['sha256']):
     # Review action already resolves byte-equivalent references; choose a stable locator.
     case=min((prior,case),key=lambda x:(x['reference'],x['sha256']))
    contracts[source][row['task_key']]=case
  if ledger_count%100==0:print(json.dumps(dict(checkpoint_ledgers=ledger_count,contracts={s:len(v) for s,v in contracts.items()})),flush=True)
 summaries={};pins={};selected_ndc=[]
 for source,items in reviews.items():
  eligible=sorted(contracts[source].values(),key=lambda c:(c['period'],c['key']))
  # Retained candidates only; frozen unresolved/missing cases are not download authority.
  cut=len(eligible)//2 if COUNTS[source]==2 else 0
  partitions={'ASC':eligible[:cut],'DESC':eligible[cut:]} if COUNTS[source]==2 else {'DESC':eligible}
  pins[source]={};counts={}
  for slot,cases in partitions.items():
   rows=[bound_row(source,items[c['key']],c,slot) for c in cases]
   state=catalog_state(source,slot,rows,'2026-10-29')
   store=GitCAS(root,'jarvis-source-preflight/catalog-'+a.namespace+'-'+slot)
   if store.remote_head(source)!=0:raise ValueError('CANDIDATE_CATALOG_NAMESPACE_EXISTS')
   if not store.cas(source,0,state):raise ValueError('CATALOG_CAS')
   commit=store.remote_head(source);index=store.git('show',commit+':state.json').stdout
   entry=dict(commit=commit,index_sha256=hashlib.sha256(index).hexdigest())
   catalog=Catalog(store,entry,source,slot);read=0
   for page in range(len(catalog.index['pages'])):read+=len(catalog.page(page))
   if read!=len(rows):raise ValueError('CANDIDATE_COLD_PAGE_COUNT')
   pins[source][slot]=dict(entry,task_count=read,catalog_id=catalog.meta['catalog_id']);counts[slot]=read
  summaries[source]=dict(frozen_review_tasks=len(items),retained_candidates=len(eligible),held_not_admitted=len(items)-len(eligible),direction_counts=counts,held_action_counts=dict(collections.Counter(i['action'] for k,i in items.items() if k not in contracts[source])))
  if source=='NDC':selected_ndc=[bound_row(source,items[c['key']],c,'DESC') for c in eligible[-2:]]
  print(json.dumps(dict(source=source,candidate_summary=summaries[source])),flush=True)
 result=dict(schema='JARVIS_OVERNIGHT_CANDIDATE_CATALOG_V1',ledger_count=ledger_count,total_frozen_review_tasks=sum(len(v) for v in reviews.values()),sources=summaries,catalogs=pins,contract_rejections=dict(errors),catalog_entries=sum(len(v) for v in pins.values()),source_requests=0,formal_raw_writes=0,production_approved=False,missing_download_authority=False,scope='Retained-only candidate catalogs; held and missing scope remains in immutable frozen review, not discarded')
 (out/'candidate-catalogs.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
 # Tiny input for a real consecutive-chunk smoke test, not the production campaign.
 (out/'ndc-two-cases.json').write_text(json.dumps(selected_ndc,ensure_ascii=False,indent=2)+'\n')
 print(json.dumps(dict(summary_file='results/candidate-catalogs.json',source_summary=summaries,catalog_entries=result['catalog_entries'])),flush=True)
if __name__=='__main__':main()
