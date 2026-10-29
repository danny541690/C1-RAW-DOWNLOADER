"""Per-task native read/download bridge. Missing tasks require explicit evidence.

The production CLI remains gated independently. Unknown contracts are isolated;
no adapter turns an empty response into a historical-absence certification.
"""
import datetime as dt,hashlib,http.cookiejar,json,os,re,urllib.parse,urllib.request
from scripts.v093_native_reuse_batch import Adapter as Retained
from scripts.v093_source_executor import ApplicabilityUnproven
from scripts.v093_source_rate import reserve,SourcePaused
RAW_ROOT='1hKq9jYgmM2oJa8GqWwTENKKayELg2yDn'

class NativeAdapter(Retained):
 def __init__(self,coordinator,drive,ticket,task,target_root=RAW_ROOT):
  case=task.get('execution_contract')
  if not isinstance(case,dict) or any(case.get(k)!=task['definition'][k] for k in ('source','key','period')):raise ValueError('NATIVE_CONTRACT_BINDING')
  if ticket['key']!=case['key'] or ticket['source']!=case['source']:raise ValueError('NATIVE_TICKET_BINDING')
  if case.get('mode') not in ('RETAINED','MISSING'):raise ValueError('NATIVE_EXECUTION_MODE')
  dt.date.fromisoformat(case['period']+'-01' if len(case['period'])==7 else case['period'])
  if case['period'][:7]<'2000-01' or case['period'][:10]>dt.datetime.now(dt.timezone(dt.timedelta(hours=8))).date().isoformat():raise ValueError('NATIVE_PERIOD_SCOPE')
  super().__init__(drive,dict(case));self.c=coordinator;self.ticket=ticket;self.target_root=target_root;self.folder=None;self.source_requests=0
  self.download_authorized=case['mode']=='MISSING'
  if not self.download_authorized:
   if not isinstance(case.get('reference'),str) or not re.fullmatch('[0-9a-f]{64}',case.get('sha256') or ''):raise ValueError('RETAINED_NATIVE_RECEIPT')
   old=task.get('legacy_review',{})
   if old.get('source')!=case['source'] or old.get('task_key')!=case['key'] or not any(v.get('raw_reference')==case['reference'] and v.get('sha256')==case['sha256'] and v.get('period')==case['period'] for v in old.get('provenance',[])):raise ValueError('RETAINED_LEGACY_BINDING')
  else:self.check_missing(task)
 def check_missing(self,task):
  case=self.case;proof=case.get('missing_evidence',{});old=task.get('legacy_review',{})
  if case.get('reference') or case.get('sha256') or old.get('source')!=case['source'] or old.get('task_key')!=case['key'] or not old.get('provenance'):raise ValueError('MISSING_LEGACY_PROOF')
  if any(v.get('raw_reference') or v.get('status') in ('SAVED_BASIC_VERIFIED','SAVED_RAW_ROWS_READBACK_VERIFIED','PROCESSING','REQUEST_INTENT','FINMIND_REQUEST_INTENT','SKIPPED_SOURCE_EMPTY','SKIPPED_NOT_PUBLISHED') for v in old['provenance']):raise ValueError('REUSE_OR_RECONCILIATION_REQUIRED')
  if any(proof.get(k)!=case[k] for k in ('source','key','period')):raise ValueError('MISSING_EVIDENCE_BINDING')
  applicable=proof.get('availability_verified') is True
  if case['source']=='TAIFEX' and proof.get('query_applicability_verified') is True:
   form=proof.get('official_form',{});job=case.get('native_job',{});fields=job.get('fields',{})
   if not {'queryStartDate','queryEndDate'}<=set(form.get('fields',{})) or urllib.parse.urlsplit(form.get('source_page','')).hostname!='www.taifex.com.tw' or job.get('url')!='https://www.taifex.com.tw/cht/3/'+str(form.get('action')):raise ValueError('QUERY_FORM_FILTER_PROOF_REQUIRED')
   for name,expected in [('queryStartDate',job['start']),('queryEndDate',job['end'])]:
    if dt.date.fromisoformat(str(fields.get(name,'')).replace('/','-')).isoformat()!=expected:raise ValueError('QUERY_DATE_BINDING')
   if not job['start']<=case['period']<=job['end'] and not job['start'].startswith(case['period']):raise ValueError('QUERY_TASK_PERIOD_BINDING')
   applicable=True
  if old.get('attempts',0)>task['attempts'] or not applicable or not proof.get('official_evidence_id'):raise ValueError('MISSING_AVAILABILITY_OR_ATTEMPTS')
  if case['source']=='FinMind' and (proof.get('official_source') not in ('TWSE','TPEx','MOPS') or not all(proof.get(k) is True for k in ('confirmed_gap','identity_period_market_verified','definition_unit_frequency_verified','cross_source_alignment_approved'))):raise ValueError('FINMIND_GAP_NOT_APPROVED')
 def find(self,key):
  if key!=self.case['key']:raise ValueError('ADAPTER_TASK_MISMATCH')
  return self.case.get('reference')
 def expected_receipt(self,key):
  if key!=self.case['key']:raise ValueError('ADAPTER_TASK_MISMATCH')
  return dict(source=self.case['source'],task_key=self.case['key'],period=self.case['period'],reference=self.case.get('reference'),sha256=self.case.get('sha256'))
 def before_request(self,ticket):
  source=self.case['source'];cost=2 if source=='TDCC' else 0 if source=='NDC' else 1
  reserve(self.c,ticket,cost=cost,limit=200 if source=='FinMind' else 30,window=3600 if source=='FinMind' else 60,spacing=2)
 def http(self,url,params=None,headers=None):
  source=self.case['source'];allowed={'TWSE':{'www.twse.com.tw'},'TPEx':{'www.tpex.org.tw'},'MOPS':{'mopsov.twse.com.tw','mops.twse.com.tw','mopsfin.twse.com.tw'},'TAIFEX':{'www.taifex.com.tw','openapi.taifex.com.tw'},'FinMind':{'api.finmindtrade.com'}}
  if urllib.parse.urlsplit(url).scheme!='https' or urllib.parse.urlsplit(url).hostname not in allowed.get(source,set()):raise ValueError('NATIVE_SOURCE_HOST')
  data=urllib.parse.urlencode(params).encode() if params is not None else None
  self.source_requests+=1
  req=urllib.request.Request(url,data=data,headers=dict({'User-Agent':'Mozilla/5.0 JARVIS-C1/0.93','Accept-Encoding':'identity'},**(headers or {})))
  class OfficialRedirect(urllib.request.HTTPRedirectHandler):
   def redirect_request(self,request,fp,code,message,headers,newurl):
    if urllib.parse.urlsplit(newurl).scheme!='https' or urllib.parse.urlsplit(newurl).hostname not in allowed[source]:raise ValueError('NATIVE_REDIRECT_HOST')
    return super().redirect_request(request,fp,code,message,headers,newurl)
  with urllib.request.build_opener(OfficialRedirect()).open(req,timeout=40) as response:
   if urllib.parse.urlsplit(response.geturl()).hostname not in allowed[source]:raise ValueError('NATIVE_REDIRECT_HOST')
   raw=response.read(32000001)
  if len(raw)>32000000:raise ValueError('NATIVE_DOWNLOAD_SIZE_LIMIT')
  return raw
 def fetch(self):
  case=self.case;source=case['source']
  if source in ('TWSE','TPEx','MOPS'):
   from scripts.v093_three_year_repair import Audit
   jobs=[j for j in Audit.jobs(object.__new__(Audit),case['period'][:7],set()) if j['source']==source and j['period']==case['period'] and j['category']==case['category']]
   if len(jobs)!=1:raise ApplicabilityUnproven('OFFICIAL_NATIVE_ROUTE_NOT_UNIQUE')
   return self.http(jobs[0]['url'],jobs[0].get('params'))
  if source=='TAIFEX':
   job=case['native_job']
   if job['kind']!='csv' or job['start']>job['end'] or job['end']>dt.datetime.now(dt.timezone(dt.timedelta(hours=8))).date().isoformat():raise ApplicabilityUnproven('TAIFEX_KIND_OR_PERIOD_NOT_ADMITTED')
   return self.http(job['url'],job.get('fields'))
  if source=='TDCC':
   from scripts import v093_tdcc_independent as native
   worker=object.__new__(native.Worker);worker.requests=0;worker.opener=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
   form=worker.request(native.QUERY).decode('utf-8-sig');self.source_requests+=1
   if case['date'] not in re.findall(r'<option\s+value="(20\d{6})"',form):raise ApplicabilityUnproven('TDCC_DATE_NOT_IN_CURRENT_MENU')
   fields=native.query_fields(form,case['date'],case['code']);self.source_requests+=1
   return worker.request(native.QUERY,urllib.parse.urlencode(fields).encode())
  if source=='FinMind':
   job=case['native_job'];params=dict(dataset=job['dataset'],data_id=job['stock_id'],start_date=job['start_date'],end_date=job['end_date'])
   url='https://api.finmindtrade.com/api/v4/data?'+urllib.parse.urlencode(params)
   token=(os.environ.get('FINMIND_TOKEN') or os.environ.get('FINMIND_API_TOKEN') or '').strip()
   return self.http(url,headers={'Authorization':'Bearer '+token} if token else {})
  if source=='NDC':
   from scripts.v093_ndc_independent import parse_bundle,month_payload
   archive=case['source_archive'];raw=self.read(archive['file_id'])
   if hashlib.sha256(raw).hexdigest()!=archive['sha256']:raise ValueError('NDC_ARCHIVE_SHA')
   return json.dumps(month_payload(parse_bundle(raw),case['period'],archive),ensure_ascii=False,sort_keys=True).encode()
  raise ValueError('NATIVE_SOURCE_UNSUPPORTED')
 def validate(self,raw):
  source=self.case['source']
  if source=='TWSE':
   from scripts.v093_three_year_repair import validate
   stats=validate(raw,source,self.case['category'],self.case['period'])
   return dict(basic_verified=True,native=stats)
  if source=='TDCC':
   from scripts.v093_tdcc_independent import validate_history,SourceEmpty
   try:rows=validate_history(raw,self.case['date'],self.case['code'])
   except SourceEmpty:raise ApplicabilityUnproven('OFFICIAL_EMPTY_UNCONFIRMED') from None
   return dict(basic_verified=True,rows=rows)
  try:return super().validate(raw)
  except Exception as exc:
   if source=='TAIFEX':
    from scripts.v093_taifex_independent import OfficialEmpty
    if isinstance(exc,OfficialEmpty):raise ApplicabilityUnproven('OFFICIAL_EMPTY_UNCONFIRMED') from None
   if source=='FinMind':
    if str(exc)=='EMPTY_FINMIND_NOT_ACCEPTED':raise ApplicabilityUnproven('FINMIND_EMPTY_UNCONFIRMED') from None
    from scripts.v093_stage07_finmind import ProviderPause
    if isinstance(exc,ProviderPause):raise SourcePaused('FINMIND_PROVIDER_REVIEW') from None
   raise
 def locator(self,key,sha):return hashlib.sha256(key.encode()).hexdigest()+'_'+sha+'.raw'
 def storage_folder(self):
  if not self.folder:self.folder=self.d.folder(self.d.folder(self.d.folder(self.target_root,self.case['period'][:4]),self.case['source']),self.case['period'][:7])
  return self.folder
 def find_locator(self,name):
  f=self.d.find(self.storage_folder(),name);return f['id'] if f else None
 def put(self,name,raw):
  self.d.direct_readback=True;self.d.put(self.storage_folder(),name,raw,'application/octet-stream',overwrite=False)
  ref=self.find_locator(name)
  if not ref:raise ValueError('IMMUTABLE_NATIVE_SAVE_REFERENCE_MISSING')
  return ref

def factory(coordinator,drive,target_root=RAW_ROOT):
 return lambda ticket,task:NativeAdapter(coordinator,drive,ticket,task,target_root)
