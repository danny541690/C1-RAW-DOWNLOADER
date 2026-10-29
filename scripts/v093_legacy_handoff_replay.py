"""Replay the immutable Git handoff snapshot; no Drive or market access."""
import collections,gzip,hashlib,json,os
from pathlib import Path
from scripts.v093_legacy_handoff import normalize,inspect,SOURCES,BUCKETS
ROOT_SOURCES={'TDCC_INDEPENDENT_STAGE05':'TDCC','TDCC_INDEPENDENT_STAGE05_ASC':'TDCC','TAIFEX_INDEPENDENT_STAGE06':'TAIFEX','TAIFEX_INDEPENDENT_STAGE06_ASC':'TAIFEX','NDC_INDEPENDENT_STAGE07':'NDC'}
def put(path,obj):path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n')
def main():
 frozen=Path('frozen');out=Path('handoff-replay');out.mkdir(exist_ok=True)
 manifest=json.loads((frozen/'ledger_manifest.json').read_text());rows=[];issues=[];examples={};inputs=0
 for item in manifest:
  raw=gzip.decompress((frozen/item['local']).read_bytes())
  if hashlib.sha256(raw).hexdigest()!=item['sha256']:raise ValueError('FROZEN_LEDGER_SHA_MISMATCH')
  obj=json.loads(raw);path=item['path'];root=path.split('/')[0]
  if item['name'].startswith('HISTORY_'):obj={'history_receipts':obj}
  if not isinstance(obj,dict):continue
  inputs+=sum(len(obj.get(bucket,{})) for bucket in BUCKETS if isinstance(obj.get(bucket,{}),dict))
  rr,ii=normalize(obj,path,ROOT_SOURCES.get(root),dict(file_id=item['id'],version=item['version'],sha256=item['sha256']))
  rows+=rr;issues += [dict(path=path,**i) for i in ii]
  for i in ii:
   group=i['reason']+'|'+root
   if len(examples.setdefault(group,[]))>=3:continue
   found=[(b,obj[b][i['key']]) for b in BUCKETS if isinstance(obj.get(b),dict) and i.get('key') in obj[b]]
   for bucket,r in found:
    examples[group].append(dict(path=path,bucket=bucket,key=i['key'],fields=list(r),period_fields={k:r.get(k) for k in ('source','period','date','month','content_period','start_date','end_date','status','file_id','bytes','sha256') if k in r},request=r.get('request')))
 totals={};conflicts={};tdcc=[];slots=[]
 for source in sorted(SOURCES):
  selected=[r for r in rows if r['source']==source];review=inspect(selected)
  (out/(source+'.review.json.gz')).write_bytes(gzip.compress(json.dumps(review,ensure_ascii=False).encode(),mtime=0))
  from scripts.v093_source_partition import COUNTS
  tasks=sorted(review['tasks'].values(),key=lambda t:(t['provenance'][0]['period'],t['task_key']))
  allocations=[('DESC',list(reversed(tasks)))] if COUNTS[source]==1 else [('ASC',tasks[:len(tasks)//2]),('DESC',list(reversed(tasks[len(tasks)//2:])))]
  assigned=[]
  for direction,items in allocations:
   keys=[t['task_key'] for t in items];assigned+=keys
   page=dict(source=source,direction=direction,task_keys=keys,mode='REVIEW_ONLY_NO_DOWNLOAD_AUTHORIZATION')
   (out/(source+'.'+direction+'.queue.json.gz')).write_bytes(gzip.compress(json.dumps(page).encode(),mtime=0))
   slots.append(dict(source=source,direction=direction,tasks=len(keys)))
  assert len(assigned)==len(set(assigned))==review['unique_tasks']
  totals[source]=dict(receipts=len(selected),unique_tasks=review['unique_tasks'],actions=dict(collections.Counter(t['action'] for t in review['tasks'].values())))
  conflicts[source]=[review['tasks'][k] for k in review['version_conflicts']]
  if source=='TDCC':tdcc=[r for r in selected if '/v1/opendata/1-1' in r['legacy_unit_id']][:4]
 assert len(slots)==12
 put(out/'twelve_slots.json',slots)
 if os.environ.get('VERIFY_TDCC_STREAM')=='1':
  from scripts.annual_actual_firstpass import service
  from scripts.v093_retained_stream_verify import verify
  put(out/'TDCC.streaming-readback.json',verify(service(),'11SZB2MYaEqOdZzC7iUv7H_ckWNGe2QCO','0951325a8c032cb87459fdaaec9fd9efa933aef33bb25c0dda1b1bd0ad43fc5b'))
 put(out/'diagnostics.json',dict(examples=examples,version_conflicts=conflicts,tdcc_sample_reference=tdcc))
 summary=dict(schema='JARVIS_FROZEN_HANDOFF_REPLAY_V1',frozen_run=40806985547,ledger_files=len(manifest),input_receipts=inputs,
  normalized_receipts=len(rows),issues=len(issues),issues_by_reason=dict(collections.Counter(x['reason'] for x in issues)),sources=totals,
  market_requests=0,drive_requests=('TARGETED_STREAM_READBACK' if os.environ.get('VERIFY_TDCC_STREAM')=='1' else 0),production_writes=0,twelve_review_slots=slots,ready_for_production_cutover=False)
 put(out/'summary.json',summary);print(json.dumps(summary,ensure_ascii=False),flush=True)
if __name__=='__main__':main()
