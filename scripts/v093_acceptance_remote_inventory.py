"""Read-only, paginated Drive metadata enumeration under the known RAW root.

Metadata presence is not RAW readback, completeness of observations or PIT.
No files are created, updated or deleted on Drive by this module.
"""
import argparse,datetime,json,re,time
from pathlib import Path
SCHEMA='JARVIS_REMOTE_METADATA_V1'
SOURCES={'TWSE','TPEx','MOPS','FinMind','TAIFEX','TDCC','NDC','TDCC_ARCHIVE'}
YEARS={str(y) for y in range(2000,2027)}
ROOT='1hKq9jYgmM2oJa8GqWwTENKKayELg2yDn'

def query(parents,names=None,folders=False):
 if not parents or any(not re.fullmatch(r'[A-Za-z0-9_-]+',p) for p in parents):raise ValueError('UNSAFE_DRIVE_PARENT')
 q="trashed = false and ("+' or '.join("'"+p+"' in parents" for p in parents)+')'
 if folders:q+=" and mimeType = 'application/vnd.google-apps.folder'"
 if names:q+=' and ('+' or '.join("name = '"+n+"'" for n in sorted(names))+')'
 return q

def save(out,state):
 out=Path(out);out.mkdir(parents=True,exist_ok=True);tmp=out/'checkpoint.tmp';tmp.write_text(json.dumps(state,ensure_ascii=False,sort_keys=True));tmp.replace(out/'checkpoint.json')

def collect(list_page,out,root=ROOT,max_requests=300,max_seconds=480,resume=None):
 if not re.fullmatch(r'[A-Za-z0-9_-]+',root):raise ValueError('UNSAFE_DRIVE_ROOT')
 if max_requests<1 or max_seconds<=0:raise ValueError('INVALID_ENUMERATION_BUDGET')
 now=lambda:datetime.datetime.now(datetime.timezone.utc).isoformat()
 if resume:
  state=json.loads(Path(resume).read_text())
  if state.get('schema')!=SCHEMA or state.get('root')!=root:raise ValueError('INVENTORY_RESUME_SCOPE')
 else:state=dict(schema=SCHEMA,root=root,started_at=now(),phase='YEARS',token=None,active=None,todo=[],scheduled=[],files={},year_ids=[],source_ids=[],requests_total=0)
 start=time.monotonic();calls=0;error=None
 while state['phase']!='DONE' and calls<max_requests and time.monotonic()-start<max_seconds:
  phase=state['phase']
  if phase=='YEARS':parents=[root];q=query(parents,YEARS,True)
  elif phase=='SOURCES':
   if not state['year_ids']:state['phase']='DONE';break
   parents=state['year_ids'];q=query(parents,SOURCES,True)
  elif phase=='RAW':
   if not state['active']:
    if not state['todo']:state['phase']='DONE';break
    state['active']=state['todo'][:25];del state['todo'][:25];state['token']=None
   parents=state['active'];q=query(parents)
  else:raise ValueError('INVENTORY_PHASE')
  calls+=1;state['requests_total']+=1
  try:
   page=list_page(q,state['token'])
   if not isinstance(page.get('files'),list):raise ValueError('INVENTORY_PAGE_SCHEMA')
   # Validate a whole page before changing the continuation cursor.
   accepted=[]
   for f in page['files']:
    if not all(f.get(k) for k in ('id','name','mimeType')) or not set(f.get('parents',[]))&set(parents):raise ValueError('INVENTORY_PARENT_SCOPE')
    if not re.fullmatch(r'[A-Za-z0-9_-]+',f['id']):raise ValueError('UNSAFE_REMOTE_ID')
    if phase=='YEARS' and f['name'] not in YEARS:raise ValueError('INVENTORY_YEAR_SCOPE')
    if phase=='SOURCES' and f['name'] not in SOURCES:raise ValueError('INVENTORY_SOURCE_SCOPE')
    accepted.append(f)
   for f in accepted:
    state['files'][f['id']]=f
    if phase=='YEARS' and f['id'] not in state['year_ids']:state['year_ids'].append(f['id'])
    elif phase=='SOURCES' and f['id'] not in state['source_ids']:
     state['source_ids'].append(f['id'])
     if f['id'] not in state['scheduled']:state['todo'].append(f['id']);state['scheduled'].append(f['id'])
    elif phase=='RAW' and f['mimeType']=='application/vnd.google-apps.folder' and f['id'] not in state['scheduled']:
     state['todo'].append(f['id']);state['scheduled'].append(f['id'])
   state['token']=page.get('nextPageToken') or None
   if not state['token']:
    if phase=='YEARS':state['phase']='SOURCES'
    elif phase=='SOURCES':state['phase']='RAW'
    else:state['active']=None
   state['updated_at']=now();save(out,state)
  except Exception as e:
   error=type(e).__name__+':'+str(e)[:240];break
 # The budget can end just after the final page; detect this without a new call.
 if state['phase']=='RAW' and not state['active'] and not state['todo'] and not state['token']:state['phase']='DONE'
 state['updated_at']=now();save(out,state)
 files=list(state['files'].values());summary=dict(schema=SCHEMA,root=root,started_at=state['started_at'],updated_at=state['updated_at'],enumeration_complete=state['phase']=='DONE' and not error,atomic_point_in_time_snapshot=False,requests_this_run=calls,requests_total=state['requests_total'],year_folders=len(state['year_ids']),source_folders=len(state['source_ids']),folder_records=sum(f['mimeType']=='application/vnd.google-apps.folder' for f in files),file_metadata_records=sum(f['mimeType']!='application/vnd.google-apps.folder' for f in files),remaining_folders=len(state['todo'])+(len(state['active']) if state['active'] else 0),error=error,phase=state['phase'],raw_sha_readback_verified=False,observation_universe_approved=False,production_writes=0,files=files)
 (Path(out)/'snapshot.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2));return summary

def main():
 p=argparse.ArgumentParser();p.add_argument('--out',required=True,type=Path);p.add_argument('--resume',type=Path);p.add_argument('--max-requests',type=int,default=300);p.add_argument('--max-seconds',type=int,default=480);a=p.parse_args()
 from scripts.annual_actual_firstpass import service,Drive
 api=service()
 def list_page(q,token):return Drive.call(lambda:api.files().list(q=q,pageToken=token,pageSize=1000,fields='nextPageToken,files(id,name,mimeType,size,modifiedTime,parents,md5Checksum,version)',supportsAllDrives=True,includeItemsFromAllDrives=True))
 r=collect(list_page,a.out,max_requests=a.max_requests,max_seconds=a.max_seconds,resume=a.resume);print(json.dumps({k:v for k,v in r.items() if k!='files'},sort_keys=True))
if __name__=='__main__':main()
