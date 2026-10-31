"""Durable per-job test record: Git first, immutable Drive copy and readback.

Never infers data acceptance from workflow success. A Drive failure leaves the
Git outbox pending; rerunning the same record retries without losing evidence.
"""
import argparse,hashlib,json,os,re
from pathlib import Path
from scripts.v093_source_coordination import Coordinator,SOURCES
from scripts.v093_source_git_store import GitCAS
ROOT='1U5VHn3iPxnGbm2baUf27qYqt0Cq8wvBA'

def encode(value):return json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False).encode()

def collect(folder):
 root=folder.resolve();files={};total=0;manifest={}
 for path in sorted(folder.rglob('*')):
  if not path.is_file() or path.suffix not in ('.json','.md','.log'):continue
  if path.is_symlink() or not path.resolve().is_relative_to(root):raise ValueError('REPORT_PATH_BOUNDARY')
  raw=path.read_bytes();total+=len(raw)
  if total>10000000:raise ValueError('REPORT_TOTAL_SIZE_LIMIT')
  # Only configured result directories are collected, never runner/environment logs.
  name=str(path.relative_to(folder));text=raw.decode('utf-8');entry=dict(sha256=hashlib.sha256(raw).hexdigest(),bytes=len(raw),text=text)
  if name in files:raise ValueError('REPORT_PATH_COLLISION')
  if len(encode(entry))<=600000:files[name]=entry;continue
  # Split on Unicode character boundaries, bounding the encoded GitCAS entry
  # including JSON escaping, rather than dropping text or raising at 700 kB.
  prefix='__report_parts__/'+hashlib.sha256(name.encode()).hexdigest();parts=[];offset=0
  while offset<len(text):
   size=min(len(text)-offset,350000)
   while True:
    part=text[offset:offset+size];body=part.encode('utf-8');item=dict(sha256=hashlib.sha256(body).hexdigest(),bytes=len(body),text=part)
    if len(encode(item))<=600000:break
    size//=2
    if not size:raise ValueError('REPORT_CHARACTER_LIMIT')
   key=prefix+'/'+str(len(parts)).zfill(6)
   if key in files:raise ValueError('REPORT_PART_COLLISION')
   files[key]=item;parts.append(key);offset+=size
  if ''.join(files[key]['text'] for key in parts).encode()!=raw:raise ValueError('REPORT_SPLIT_ROUNDTRIP')
  manifest[name]=dict(sha256=entry['sha256'],bytes=len(raw),parts=parts)
 if manifest:
  key='__report_parts_manifest__.json'
  if key in files:raise ValueError('REPORT_MANIFEST_COLLISION')
  raw=encode(dict(schema='JARVIS_REPORT_PARTS_V1',originals=manifest));files[key]=dict(sha256=hashlib.sha256(raw).hexdigest(),bytes=len(raw),text=raw.decode())
 return files

def publish(coordinator,record,archive):
 raw=encode(record);digest=hashlib.sha256(raw).hexdigest()
 def checkpoint(s):
  if s.get('record_sha256') and s['record_sha256']!=digest:raise ValueError('PUBLICATION_IDENTITY_CONTENT_CONFLICT')
  s.update(record_sha256=digest,record_metadata=record['metadata'])
  if not s.get('drive_receipt'):s['publication_state']='DRIVE_PENDING'
  s['tasks']=record['files']
 coordinator.update(checkpoint)
 try:
  receipt=archive.save(raw,digest)
  if receipt.get('sha256')!=digest or receipt.get('readback_verified') is not True:raise ValueError('PUBLICATION_READBACK_NOT_VERIFIED')
 except Exception as exc:
  coordinator.update(lambda s:s.update(publication_state='DRIVE_PENDING',publication_error=type(exc).__name__))
  raise
 def complete(s):
  if s['record_sha256']!=digest:raise ValueError('PUBLICATION_STATE_CHANGED')
  s.update(publication_state='GIT_AND_DRIVE_READBACK_VERIFIED',drive_receipt=receipt)
  s.pop('publication_error',None)
 coordinator.update(complete)
 return dict(record_sha256=digest,files=len(record['files']),publication_state='GIT_AND_DRIVE_READBACK_VERIFIED',drive_receipt=receipt,source_requests=0,production_activation=False)

class DriveArchive:
 def __init__(self,identity):self.identity=identity
 def save(self,raw,digest):
  from scripts.annual_actual_firstpass import Drive,service
  d=Drive(service());d.direct_readback=True
  folder=d.folder(ROOT,'RUN_'+self.identity)
  def save_piece(name,payload):
   d.put(folder,name,payload,'application/json',overwrite=False)
   found=d.find(folder,name)
   if not found:raise ValueError('PUBLICATION_FILE_NOT_FOUND')
   restored=d.call(lambda:d.api.files().get_media(fileId=found['id']))
   if restored!=payload:raise ValueError('PUBLICATION_DRIVE_SHA_MISMATCH')
   return dict(file_id=found['id'],sha256=hashlib.sha256(payload).hexdigest(),bytes=len(payload))
  if len(raw)<=650000:
   receipt=save_piece('acceptance_'+digest+'.json',raw)
   return dict(receipt,folder_id=folder,readback_verified=True)
  record=json.loads(raw);header={k:v for k,v in record.items() if k!='files'};pieces=[];batch={}
  def flush():
   if not batch:return
   payload=encode(dict(header,files=dict(batch)));number=len(pieces)
   if len(payload)>650000:raise ValueError('PUBLICATION_PART_TOO_LARGE')
   receipt=save_piece('acceptance_'+digest+'.part_'+str(number).zfill(6)+'.json',payload)
   pieces.append(dict(receipt,keys=list(batch)));batch.clear()
  for name,entry in record['files'].items():
   batch[name]=entry
   if len(encode(dict(header,files=batch)))>650000:
    batch.pop(name);flush();batch[name]=entry
  flush();restored_files={}
  for piece in pieces:
   restored=json.loads(d.call(lambda:d.api.files().get_media(fileId=piece['file_id'])))
   if set(restored_files)&set(restored['files']):raise ValueError('PUBLICATION_DUPLICATE_PART_KEYS')
   restored_files.update(restored['files'])
  if encode(dict(header,files=restored_files))!=raw:raise ValueError('PUBLICATION_PART_RECONSTRUCTION')
  index=encode(dict(schema='JARVIS_ACCEPTANCE_MULTIPART_V1',record_sha256=digest,record_bytes=len(raw),parts=pieces))
  receipt=save_piece('acceptance_'+digest+'.index.json',index)
  return dict(file_id=receipt['file_id'],folder_id=folder,sha256=digest,manifest_sha256=receipt['sha256'],parts=len(pieces),readback_verified=True)

def main():
 p=argparse.ArgumentParser();p.add_argument('--source',choices=sorted(SOURCES),required=True);p.add_argument('--job',required=True);p.add_argument('--input',type=Path,default=Path('results'));p.add_argument('--status',choices=('success','failure','cancelled','skipped'),required=True);a=p.parse_args()
 run=os.environ['GITHUB_RUN_ID'];attempt=os.environ['GITHUB_RUN_ATTEMPT'];sha=os.environ['GITHUB_SHA'];repo=os.environ['GITHUB_REPOSITORY']
 if not run.isdigit() or not attempt.isdigit() or not re.fullmatch('[0-9a-f]{40}',sha) or not re.fullmatch('[A-Za-z0-9_-]{1,60}',a.job):raise ValueError('PUBLICATION_IDENTITY')
 identity=run+'-'+attempt+'-'+a.job
 record=dict(schema='JARVIS_AUTOMATIC_ACCEPTANCE_RECORD_V1',metadata=dict(run_id=run,attempt=attempt,job=a.job,source_namespace=a.source,code_sha=sha,repository=repo,job_status=a.status,run_url='https://github.com/'+repo+'/actions/runs/'+run,acceptance_semantics='PER_JOB_EVIDENCE_ONLY_NOT_FULL_DATA_CERTIFICATION'),files=collect(a.input))
 c=Coordinator(GitCAS(Path.cwd(),'jarvis-source-preflight/record-'+identity),a.source)
 result=publish(c,record,DriveArchive(identity+'-'+a.source));result.update(git_state_branch='jarvis-source-preflight/record-'+identity+'/'+a.source,job_status=a.status)
 out=Path('publication');out.mkdir(exist_ok=True);(out/'receipt.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result),flush=True)
if __name__=='__main__':main()
