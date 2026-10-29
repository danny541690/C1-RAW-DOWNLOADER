"""Replay the immutable Git handoff snapshot; no Drive or market access."""
import collections,gzip,hashlib,json
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
 totals={};conflicts={};tdcc=[]
 for source in sorted(SOURCES):
  selected=[r for r in rows if r['source']==source];review=inspect(selected)
  (out/(source+'.review.json.gz')).write_bytes(gzip.compress(json.dumps(review,ensure_ascii=False).encode(),mtime=0))
  totals[source]=dict(receipts=len(selected),unique_tasks=review['unique_tasks'],actions=dict(collections.Counter(t['action'] for t in review['tasks'].values())))
  conflicts[source]=[review['tasks'][k] for k in review['version_conflicts']]
  if source=='TDCC':tdcc=[r for r in selected if '/v1/opendata/1-1' in r['legacy_unit_id']][:4]
 put(out/'diagnostics.json',dict(examples=examples,version_conflicts=conflicts,tdcc_sample_reference=tdcc))
 summary=dict(schema='JARVIS_FROZEN_HANDOFF_REPLAY_V1',frozen_run=40806985547,ledger_files=len(manifest),input_receipts=inputs,
  normalized_receipts=len(rows),issues=len(issues),issues_by_reason=dict(collections.Counter(x['reason'] for x in issues)),sources=totals,
  market_requests=0,drive_requests=0,production_writes=0,ready_for_production_cutover=False)
 put(out/'summary.json',summary);print(json.dumps(summary,ensure_ascii=False),flush=True)
if __name__=='__main__':main()
