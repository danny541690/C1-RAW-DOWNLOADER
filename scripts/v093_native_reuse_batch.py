"""Parallel source-native retained-RAW acceptance via the common executor.

No source HTTP, RAW writes or production activation. Descriptor provenance is
bound to frozen original ledgers and review receipts before touching Drive.
"""
import argparse,gzip,hashlib,io,json,re,zipfile
from pathlib import Path
from scripts.v093_legacy_handoff import normalize
from scripts.v093_source_coordination import Coordinator
from scripts.v093_source_executor import Executor
from scripts.v093_source_git_store import GitCAS
DEFAULT={'TDCC_INDEPENDENT_STAGE05':'TDCC','TDCC_INDEPENDENT_STAGE05_ASC':'TDCC','TAIFEX_INDEPENDENT_STAGE06':'TAIFEX','TAIFEX_INDEPENDENT_STAGE06_ASC':'TAIFEX','NDC_INDEPENDENT_STAGE07':'NDC'}
SOURCES=('TPEx','MOPS','TAIFEX','NDC','FinMind')

def descriptor(source,row,entry):
 d=dict(source=source,key=row['task_key'],period=row['period'],reference=row['raw_reference'],sha256=row['sha256'],attempts=row['attempts'],ledger_path=row['ledger_path'],ledger_origin=row['ledger_origin'])
 if source in ('TPEx','MOPS'):
  cat=entry.get('category','')
  if source=='TPEx' and cat not in ('prices','prices_indices'):return None
  if source=='MOPS' and not cat.startswith('revenue_'):return None
  d['category']=cat
 elif source=='TAIFEX':
  job=entry.get('request',{})
  if job.get('kind') not in ('csv','form'):return None
  if not all(job.get(k) for k in ('start','end','key','url')):return None
  if not job['url'].startswith('https://www.taifex.com.tw/'):return None
  d['native_job']={k:v for k,v in job.items() if k in ('key','kind','start','end','url','fields')}
 elif source=='FinMind':
  names=('stock_id','start_date','end_date','category','month','dataset')
  if not all(entry.get(k) for k in names):return None
  d['native_job']={k:entry[k] for k in names}
 elif source!='NDC':return None
 return d

def select(source):
 review=json.loads(gzip.decompress((Path('frozen')/(source+'.review.json.gz')).read_bytes()));candidates={}
 for f in json.loads(Path('original/ledger_manifest.json').read_text()):
  root=f['path'].split('/')[0];default=DEFAULT.get(root)
  if default and default!=source:continue
  raw=gzip.decompress((Path('original')/f['local']).read_bytes())
  if hashlib.sha256(raw).hexdigest()!=f['sha256']:raise ValueError('FROZEN_LEDGER_SHA')
  obj=json.loads(raw)
  if f['name'].startswith('HISTORY_'):obj={'history_receipts':obj}
  if not isinstance(obj,dict):continue
  index={}
  for bucket,entries in obj.items():
   if isinstance(entries,dict):
    for key,entry in entries.items():
     if isinstance(entry,dict):index.setdefault((bucket,str(entry.get('unit_id',key))),[]).append(entry)
  rows,_=normalize(obj,f['path'],default,dict(file_id=f['id'],version=f['version'],sha256=f['sha256']))
  for row in rows:
   if row['source']!=source or not row.get('raw_reference') or not re.fullmatch('[0-9a-f]{64}',row.get('sha256') or ''):continue
   item=review['tasks'].get(row['task_key'])
   if not item or item['action']!='VERIFY_RETAINED_RAW_FIRST' or len({v['period'] for v in item['provenance']})!=1:continue
   entries=index.get((row['legacy_bucket'],row['legacy_unit_id']),[])
   if len(entries)!=1:continue
   d=descriptor(source,row,entries[0])
   if d:
    d['attempts']=item['attempts'];candidates[d['key']]=d
 if not candidates:raise ValueError('NO_SUPPORTED_NATIVE_REUSE_CASE_'+source)
 return max(candidates.values(),key=lambda d:(d['period'],d['key']))

class Adapter:
 download_authorized=False
 def __init__(self,drive,case):self.d=drive;self.case=case;self.archive_cache={}
 def expected_receipt(self,key):return dict(source=self.case['source'],task_key=key,period=self.case['period'],reference=self.case['reference'],sha256=self.case['sha256'])
 def find(self,key):return self.case['reference']
 def read(self,reference):
  fid,sep,member=reference.partition('/')
  meta=self.d.call(lambda:self.d.api.files().get(fileId=fid,fields='size,version'))
  if int(meta.get('size',0))>150_000_000:raise ValueError('RETAINED_SIZE_LIMIT')
  raw=self.d.call(lambda:self.d.api.files().get_media(fileId=fid))
  after=self.d.call(lambda:self.d.api.files().get(fileId=fid,fields='version'))
  if after['version']!=meta['version']:raise ValueError('RAW_CHANGED_DURING_READ')
  if sep:
   with zipfile.ZipFile(io.BytesIO(raw)) as z:
    if z.getinfo(member).file_size>32_000_000:raise ValueError('MEMBER_SIZE_LIMIT')
    raw=z.read(member)
  return raw
 def validate(self,raw):
  source=self.case['source']
  if source in ('TPEx','MOPS'):
   from scripts.v093_three_year_repair import validate
   stats=validate(raw,source,self.case['category'],self.case['period'])
  elif source=='TAIFEX':
   from scripts.v093_taifex_independent import validate
   stats=validate(raw,self.case['native_job'])
  elif source=='FinMind':
   from scripts.v093_stage07_finmind import validate
   stats=validate(raw,self.case['native_job'])
   if not stats:raise ValueError('EMPTY_FINMIND_NOT_ACCEPTED')
  else:
   from scripts.v093_ndc_independent import parse_bundle,month_payload
   obj=json.loads(raw.decode('utf-8-sig'))
   if obj.get('source')!='NDC' or obj.get('month')!=self.case['period'] or obj.get('units')!='AS_PUBLISHED_NO_CONVERSION':raise ValueError('NDC_IDENTITY_OR_UNITS')
   archive=obj.get('source_archive',{});ref=archive.get('file_id');sha=archive.get('sha256')
   if not isinstance(ref,str) or not re.fullmatch('[0-9a-f]{64}',sha or ''):raise ValueError('NDC_ARCHIVE_RECEIPT')
   if sha not in self.archive_cache:
    original=self.read(ref)
    if hashlib.sha256(original).hexdigest()!=sha:raise ValueError('NDC_SOURCE_ARCHIVE_SHA')
    self.archive_cache[sha]=parse_bundle(original)
   expected=month_payload(self.archive_cache[sha],obj['month'],archive)
   if obj!=expected:raise ValueError('NDC_NATIVE_CELL_RECONSTRUCTION_MISMATCH')
   stats=dict(tables=len(obj['tables']),cells=sum(len(t['cells']) for t in obj['tables']),source_archive_sha256=sha,source_cells_reconstructed=True,gaps=len(obj['gaps']))
  return dict(basic_verified=True,native=stats,numeric_verified=False,pit_verified=False,full_acceptance=False)

def main():
 from scripts.annual_actual_firstpass import Drive,service
 p=argparse.ArgumentParser();p.add_argument('mode',choices=('start','verify'));p.add_argument('--source',choices=SOURCES,required=True);p.add_argument('--namespace',required=True);a=p.parse_args()
 c=Coordinator(GitCAS(Path.cwd(),'jarvis-source-preflight/'+a.namespace),a.source,ttl=1800);d=Drive(service());out=Path('results');out.mkdir(exist_ok=True)
 if a.mode=='start':
  case=select(a.source);c.add([dict(source=a.source,key=case['key'],period=case['period'],slot='DESC')])
  def seed(s):s.update(native_reuse_case=case);s['tasks'][case['key']]['attempts']=case['attempts']
  c.update(seed);adapter=Adapter(d,case);evidence=Executor(c,adapter).one('DESC','native-start')
 else:
  _,state=c.store.read(a.source);case=state['native_reuse_case'];adapter=Adapter(d,case)
  raw=adapter.read(case['reference'])
  if hashlib.sha256(raw).hexdigest()!=case['sha256']:raise ValueError('COLD_RAW_SHA')
  evidence=dict(reference=case['reference'],sha256=case['sha256'],stats=adapter.validate(raw))
 _,state=c.store.read(a.source);task=state['tasks'][case['key']]
 if task['status']!='RAW_BASIC_VERIFIED' or task['attempts']!=case['attempts']:raise ValueError('RETAINED_STATE_OR_ATTEMPTS')
 result=dict(schema='JARVIS_NATIVE_REUSE_BATCH_V1',mode=a.mode,source=a.source,period=case['period'],task_key=case['key'],evidence=evidence,attempts=task['attempts'],source_requests=0,raw_writes=0,production_activation=False,full_acceptance=False,limitation='One retained native case, not missing download or entire source universe')
 (out/(a.source+'-'+a.mode+'.json')).write_text(json.dumps(result,ensure_ascii=False,indent=2));print(json.dumps(result,ensure_ascii=False),flush=True)
if __name__=='__main__':main()
