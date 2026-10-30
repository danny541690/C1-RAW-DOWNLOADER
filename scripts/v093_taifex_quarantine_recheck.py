"""Recheck frozen TAIFEX rejected CSV bytes, no source HTTP or formal RAW writes."""
import argparse,collections,gzip,hashlib,json,re,os
from pathlib import Path
from scripts.v093_legacy_handoff import normalize
from scripts.v093_source_coordination import Coordinator
from scripts.v093_source_git_store import GitCAS
from scripts.v093_taifex_independent import validate,OfficialEmpty

def candidates():
 review=json.loads(gzip.decompress(Path('frozen/TAIFEX.review.json.gz').read_bytes()));found={};ledger_ids=set()
 for f in json.loads(Path('original/ledger_manifest.json').read_text()):
  if not f['path'].startswith(('TAIFEX_INDEPENDENT_STAGE06/','TAIFEX_INDEPENDENT_STAGE06_ASC/')):continue
  raw=gzip.decompress((Path('original')/f['local']).read_bytes())
  if hashlib.sha256(raw).hexdigest()!=f['sha256']:raise ValueError('FROZEN_LEDGER_SHA')
  obj=json.loads(raw)
  if not isinstance(obj,dict) or not obj.get('receipts'):continue
  ledger_ids.add(f['id'])
  rows,_=normalize(obj,f['path'],'TAIFEX',dict(file_id=f['id'],version=f['version'],sha256=f['sha256']))
  for row in rows:
   item=review['tasks'].get(row['task_key']);entry=obj.get(row['legacy_bucket'],{}).get(row['legacy_unit_id'],{});job=entry.get('request',{});sha=entry.get('response_sha256')
   if not item or any(v.get('raw_reference') for v in item['provenance']) or job.get('kind')!='csv' or not re.fullmatch('[0-9a-f]{64}',sha or ''):continue
   identity=hashlib.sha256((row['task_key']+'|'+sha).encode()).hexdigest()
   found[identity]=dict(identity=identity,task_key=row['task_key'],period=row['period'],expected_raw_sha256=sha,native_job=job,prior_attempts=item['attempts'],ledger_id=f['id'],ledger_sha256=f['sha256'],legacy_status=entry.get('status'),quarantine_name='UNRESOLVED_'+sha+'.raw')
 return found,ledger_ids

def main():
 from scripts.annual_actual_firstpass import Drive,service
 p=argparse.ArgumentParser();p.add_argument('--part',type=int,choices=(0,1),required=True);p.add_argument('--namespace',required=True);a=p.parse_args()
 all_items,ledger_ids=candidates();items=[item for key,item in sorted(all_items.items()) if int(key,16)%2==a.part]
 d=Drive(service());parents=set();ledger_parents={}
 for fid in sorted(ledger_ids):
  metadata=d.call(lambda:d.api.files().get(fileId=fid,fields='parents'));ledger_parents[fid]=metadata['parents'];parents.update(metadata['parents'])
 c=Coordinator(GitCAS(Path.cwd(),'jarvis-source-preflight/'+a.namespace),'TAIFEX',ttl=600)
 _,old=c.store.read('TAIFEX')
 if old and old.get('parser_code_sha')!=os.environ.get('GITHUB_SHA'):raise ValueError('PARSER_CHANGED_REQUIRE_NEW_RECHECK_NAMESPACE')
 c.update(lambda s:s.update(parser_code_sha=os.environ.get('GITHUB_SHA')))
 previous=(old or {}).get('tasks',{});batch={};counts=collections.Counter();cache={};reads=0
 def flush(done):
  if batch:
   saved=dict(batch)
   def change(s):
    for key,value in saved.items():
     if key in s['tasks'] and s['tasks'][key]!=value:raise ValueError('RECHECK_RESULT_IDENTITY_CHANGED')
     s['tasks'][key]=value
    s.setdefault('parts',{})[str(a.part)]=dict(checked=sum(counts.values()),planned=len(items),counts=dict(counts),done=done,source_requests=0,formal_raw_writes=0)
   c.update(change);batch.clear()
  elif done:c.update(lambda s:s.setdefault('parts',{}).update({str(a.part):dict(checked=sum(counts.values()),planned=len(items),counts=dict(counts),done=True,source_requests=0,formal_raw_writes=0)}))
 for item in items:
  key=item['identity']
  if key in previous:
   counts[previous[key]['classification']]+=1;continue
  result=dict(task_key=item['task_key'],period=item['period'],expected_raw_sha256=item['expected_raw_sha256'],prior_attempts=item['prior_attempts'],attempts_after=item['prior_attempts'],ledger_id=item['ledger_id'],ledger_sha256=item['ledger_sha256'],full_acceptance=False,formal_repaired=False)
  try:
   sha=item['expected_raw_sha256']
   if sha in cache:raw,ref=cache[sha]
   else:
    ref=None
    for parent in list(ledger_parents[item['ledger_id']])+sorted(parents-set(ledger_parents[item['ledger_id']])):
     candidate=d.find(parent,item['quarantine_name'])
     if candidate:ref=candidate['id'];break
    if not ref:raise FileNotFoundError('RETAINED_QUARANTINE_REFERENCE_NOT_FOUND')
    before=d.call(lambda:d.api.files().get(fileId=ref,fields='size,version'))
    if int(before.get('size',0))>32000000:raise ValueError('RECHECK_SIZE_REQUIRES_STREAM')
    raw=d.call(lambda:d.api.files().get_media(fileId=ref));reads+=1
    after=d.call(lambda:d.api.files().get(fileId=ref,fields='version'))
    if after['version']!=before['version']:raise ValueError('RETAINED_CHANGED_DURING_READ')
    if hashlib.sha256(raw).hexdigest()!=sha:raise ValueError('RETAINED_SHA_MISMATCH')
    if sum(len(v[0]) for v in cache.values())+len(raw)>32000000:cache.clear()
    cache[sha]=(raw,ref)
   result['reference']=ref;result['remote_old_sha_verified']=True
   try:
    stats=validate(raw,item['native_job']);result.update(classification='NATIVE_VALID_CANDIDATE_REQUIRES_PROMOTION_REVIEW',native_stats=stats)
   except OfficialEmpty:result['classification']='OFFICIAL_EMPTY_UNCONFIRMED'
   except Exception as exc:
    result.update(classification='NATIVE_REPARSE_REVIEW',error=type(exc).__name__)
    message=str(exc)
    if re.fullmatch('[A-Z0-9_]+',message):result['validation_code']=message
  except FileNotFoundError:result['classification']='RETAINED_REFERENCE_NOT_FOUND'
  except Exception as exc:
   result.update(classification='STORAGE_OR_INTEGRITY_REVIEW',error=type(exc).__name__)
   if re.fullmatch('[A-Z0-9_]+',str(exc)):result['validation_code']=str(exc)
  counts[result['classification']]+=1;batch[key]=result
  if len(batch)>=25:flush(False)
 flush(True)
 _,state=c.store.read('TAIFEX');subset={key:state['tasks'][key] for key in [i['identity'] for i in items]}
 report=dict(schema='JARVIS_TAIFEX_RETAINED_QUARANTINE_RECHECK_V1',part=a.part,all_unique_candidates=len(all_items),planned=len(items),checked=len(subset),counts=dict(counts),drive_raw_reads=reads,source_requests=0,formal_raw_writes=0,production_activation=False,full_acceptance=False,results=subset)
 out=Path('results');out.mkdir(exist_ok=True);(out/'quarantine-recheck.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
 print(json.dumps({k:v for k,v in report.items() if k!='results'}),flush=True)
if __name__=='__main__':main()
