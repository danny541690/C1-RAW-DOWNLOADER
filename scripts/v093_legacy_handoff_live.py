"""Read-only Drive ledger freeze and candidate import rehearsal after legacy drain."""
import collections,datetime,gzip,hashlib,io,json,os,re,subprocess,time,urllib.request,zipfile
from pathlib import Path
from scripts.v093_legacy_handoff import normalize,inspect
from scripts.v093_source_receipt_migration import migrate
REPORT='1p3Ij6ZGL4htYhhGKtEytU2MVOXW-wAit'
ROOT_NAMES={'LIVE_FIVE_STAGE_202610_TO_200001_V1':None,'TDCC_INDEPENDENT_STAGE05':'TDCC','TDCC_INDEPENDENT_STAGE05_ASC':'TDCC','TAIFEX_INDEPENDENT_STAGE06':'TAIFEX','TAIFEX_INDEPENDENT_STAGE06_ASC':'TAIFEX','NDC_INDEPENDENT_STAGE07':'NDC'}
NAMES={'CURSOR.json','STATUS.json','MONTH_STATE.json','OFFICIAL_REPAIR_STATE.json','RETRY_MONTHS.json','FINMIND_SUPPLEMENT_STATE.json','FINMIND_GAPFILL_STATUS.json'}
def encode(v):return json.dumps(v,ensure_ascii=False,sort_keys=True).encode()
def put(path,value):path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(encode(value))
def wait_drain():
 req=urllib.request.Request('https://api.github.com/repos/'+os.environ['GITHUB_REPOSITORY']+'/actions/runs/'+os.environ['PAUSE_RUN_ID'],headers={'Authorization':'Bearer '+os.environ['GH_TOKEN']})
 deadline=time.monotonic()+65*60
 while True:
  with urllib.request.urlopen(req,timeout=40) as r:d=json.load(r)
  if d['status']=='completed':
   if d['conclusion']!='success':raise RuntimeError('LEGACY_DRAIN_NOT_SUCCESSFUL')
   return d
  if time.monotonic()>deadline:raise RuntimeError('LEGACY_DRAIN_WAIT_TIMEOUT')
  print('WAITING_FOR_LEGACY_CHECKPOINTS',flush=True);time.sleep(20)
def main():
 out=Path('handoff-import');out.mkdir(exist_ok=True);pause=wait_drain()
 from scripts.annual_actual_firstpass import service,Drive
 api=service();d=Drive(api)
 def children(parent):
  found=[];token=None
  while True:
   r=d.call(lambda:api.files().list(q="'"+parent+"' in parents and trashed=false",pageSize=1000,pageToken=token,fields='nextPageToken,files(id,name,mimeType,size,version,modifiedTime)'))
   found.extend(r['files']);token=r.get('nextPageToken')
   if not token:return found
 roots=[f for f in children(REPORT) if f['name'] in ROOT_NAMES]
 if {f['name'] for f in roots}!=set(ROOT_NAMES):raise RuntimeError('EXPECTED_LEGACY_ROOTS_MISSING')
 if len(roots)!=len(ROOT_NAMES):raise RuntimeError('AMBIGUOUS_LEGACY_ROOT_NAMES')
 queue=[(r['id'],r['name'],ROOT_NAMES[r['name']]) for r in roots]
 files=[];rows=[];issues=[];inventory=[]
 while queue:
  parent,path,source=queue.pop(0)
  for f in children(parent):
   name=f['name'];fp=path+'/'+name
   if f['mimeType']=='application/vnd.google-apps.folder':
    if name in ('REPAIR_EVIDENCE','REPARSE_STAGING','SOURCE_ARCHIVES','STAGING'):continue
    queue.append((f['id'],fp,source));continue
   if name not in NAMES and not re.fullmatch(r'HISTORY_\d{8}\.json',name):continue
   if int(f.get('size',0))>60_000_000:raise RuntimeError('LEDGER_REQUIRES_STREAMING')
   raw=d.call(lambda:api.files().get_media(fileId=f['id']))
   after=d.call(lambda:api.files().get(fileId=f['id'],fields='version,modifiedTime'))
   if after['version']!=f['version']:raise RuntimeError('LEDGER_CHANGED_AFTER_DRAIN')
   local='ledgers/'+f['id']+'.json.gz';target=out/local;target.parent.mkdir(exist_ok=True);target.write_bytes(gzip.compress(raw,mtime=0))
   record=dict(f,path=fp,local=local,sha256=hashlib.sha256(raw).hexdigest());files.append(record)
   obj=json.loads(raw)
   if re.fullmatch(r'HISTORY_\d{8}\.json',name):obj={'history_receipts':obj}
   if not isinstance(obj,dict):issues.append(dict(path=fp,reason='DOCUMENT_SCHEMA'));continue
   rr,ii=normalize(obj,fp,source,dict(file_id=f['id'],version=f['version'],sha256=record['sha256']))
   rows.extend(rr);issues.extend(dict(path=fp,**x) for x in ii)
  if len(files)>3000:raise RuntimeError('LEDGER_LIMIT_REQUIRES_PAGING')
 put(out/'ledger_manifest.json',files);put(out/'normalization_issues.json',issues)
 # Persist per-source compressed review pages rather than one oversized Git state.
 totals={};samples={};api_raw_cache={}
 def read_ref(ref):
  fid,sep,member=ref.partition('/')
  if fid not in api_raw_cache:
   meta=d.call(lambda:api.files().get(fileId=fid,fields='size'))
   if int(meta.get('size',0))>30_000_000:raise ValueError('SAMPLE_SIZE_LIMIT')
   api_raw_cache.clear();api_raw_cache[fid]=d.call(lambda:api.files().get_media(fileId=fid))
  raw=api_raw_cache[fid]
  if sep:
   with zipfile.ZipFile(io.BytesIO(raw)) as z:
    if z.getinfo(member).file_size>30_000_000:raise ValueError('MEMBER_SIZE_LIMIT')
    raw=z.read(member)
  return raw
 for source in sorted(normalize.__globals__['SOURCES']):
  selected=[r for r in rows if r['source']==source];review=inspect(selected)
  target=out/(source+'.review.json.gz');target.write_bytes(gzip.compress(encode(review),mtime=0))
  totals[source]=dict(receipts=len(selected),unique_tasks=review['unique_tasks'],conflicts=len(review['version_conflicts']),actions=dict(collections.Counter(t['action'] for t in review['tasks'].values())))
  eligible=[r for r in selected if r.get('raw_reference') and r.get('sha256') and r['status'] in ('SAVED_BASIC_VERIFIED','SAVED_RAW_ROWS_READBACK_VERIFIED','RAW_DOWNLOADED_UNVERIFIED')]
  # Two deterministic retained samples/source; oversize or failed copies remain failures, never a false pass.
  chosen=list({r['task_key']:r for r in eligible}.values())[:2]
  result=migrate(chosen,read_ref,source);samples[source]=dict(tested=len(chosen),counts=result['counts'])
  put(out/(source+'.readback-sample.json'),result)
 summary=dict(schema='JARVIS_REAL_LEGACY_HANDOFF_REHEARSAL_V1',captured_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
  pause_run=pause['id'],candidate_sha=os.environ['GITHUB_SHA'],ledger_files=len(files),normalized_receipts=len(rows),sources=totals,
  normalization_issues=len(issues),issues_by_reason=dict(collections.Counter(x['reason'] for x in issues)),retained_raw_samples=samples,
  market_requests=0,drive_writes=0,old_ledgers_overwritten=False,new_production_state_written=False,
  full_data_acceptance=False,ready_for_production_cutover=False)
 put(out/'summary.json',summary);print(json.dumps(summary,ensure_ascii=False),flush=True)
if __name__=='__main__':main()
