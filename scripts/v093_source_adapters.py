"""Per-task native read/download bridge. Missing tasks require explicit evidence.

The production CLI remains gated independently. Unknown contracts are isolated;
no adapter turns an empty response into a historical-absence certification.
"""
import datetime as dt,hashlib,http.cookiejar,json,os,re,urllib.parse,urllib.request
from scripts.v093_native_reuse_batch import Adapter as Retained
from scripts.v093_source_executor import ApplicabilityUnproven
from scripts.v093_source_rate import reserve,SourcePaused
RAW_ROOT='1hKq9jYgmM2oJa8GqWwTENKKayELg2yDn'

def unconfirmed_empty(source,error):
 if source not in ('TWSE','TPEx'):return False
 message=str(error)
 if message=='EMPTY_RESPONSE_NOT_COVERAGE':return True
 if not message.startswith('SOURCE_STATUS:'):return False
 status=message.removeprefix('SOURCE_STATUS:').strip().rstrip('!！。')
 return status in {'很抱歉，沒有符合條件的資料','查無資料','沒有資料','查無符合條件資料'}

class NativeAdapter(Retained):
 def __init__(self,coordinator,drive,ticket,task,target_root=RAW_ROOT):
  case=task.get('execution_contract')
  if not isinstance(case,dict) or any(case.get(k)!=task['definition'][k] for k in ('source','key','period')):raise ValueError('NATIVE_CONTRACT_BINDING')
  if ticket['key']!=case['key'] or ticket['source']!=case['source']:raise ValueError('NATIVE_TICKET_BINDING')
  if case.get('mode') not in ('RETAINED','MISSING','REPAIR','PROMOTE'):raise ValueError('NATIVE_EXECUTION_MODE')
  dt.date.fromisoformat(case['period']+'-01' if len(case['period'])==7 else case['period'])
  if case['period'][:7]<'2000-01' or case['period'][:10]>dt.datetime.now(dt.timezone(dt.timedelta(hours=8))).date().isoformat():raise ValueError('NATIVE_PERIOD_SCOPE')
  super().__init__(drive,dict(case));self.c=coordinator;self.ticket=ticket;self.target_root=target_root;self.folder=None;self.source_requests=0
  self.download_authorized=case['mode'] in ('MISSING','REPAIR','PROMOTE');self.requires_source_request=case['mode']!='PROMOTE';self.destination_reference=None
  if not self.download_authorized:
   if not isinstance(case.get('reference'),str) or not re.fullmatch('[0-9a-f]{64}',case.get('sha256') or ''):raise ValueError('RETAINED_NATIVE_RECEIPT')
   old=task.get('legacy_review',{})
   if old.get('source')!=case['source'] or old.get('task_key')!=case['key'] or not any(v.get('raw_reference')==case['reference'] and v.get('sha256')==case['sha256'] and v.get('period')==case['period'] for v in old.get('provenance',[])):raise ValueError('RETAINED_LEGACY_BINDING')
  elif case['mode']=='MISSING':self.check_missing(task)
  elif case['mode']=='REPAIR':self.check_repair(task)
  else:self.check_promotion(task)
 def check_missing(self,task):
  case=self.case;proof=case.get('missing_evidence',{});old=task.get('legacy_review',{})
  if case.get('reference') or case.get('sha256') or old.get('source')!=case['source'] or old.get('task_key')!=case['key'] or not old.get('provenance'):raise ValueError('MISSING_LEGACY_PROOF')
  if any(v.get('raw_reference') or v.get('status') in ('SAVED_BASIC_VERIFIED','SAVED_RAW_ROWS_READBACK_VERIFIED','PROCESSING','REQUEST_INTENT','FINMIND_REQUEST_INTENT','SKIPPED_SOURCE_EMPTY','SKIPPED_NOT_PUBLISHED') for v in old['provenance']):raise ValueError('REUSE_OR_RECONCILIATION_REQUIRED')
  if any(proof.get(k)!=case[k] for k in ('source','key','period')):raise ValueError('MISSING_EVIDENCE_BINDING')
  applicable=proof.get('availability_verified') is True
  if case['source'] in ('TWSE','TPEx','MOPS') and proof.get('query_applicability_verified') is True:
   from scripts.v093_missing_rules import official_job
   job=official_job(case['source'],case['period'],case.get('category'))
   origin_sha=proof.get('frozen_ledger_sha256')
   if not job or proof.get('native_route')!=job or not re.fullmatch('[0-9a-f]{64}',origin_sha or '') or not any(v.get('ledger_origin',{}).get('sha256')==origin_sha and v.get('ledger_origin',{}).get('file_id')==proof.get('official_evidence_id') for v in old.get('provenance',[])):raise ValueError('OFFICIAL_QUERY_ROUTE_OR_LEDGER_BINDING')
   applicable=True
  if case['source']=='TAIFEX' and proof.get('query_applicability_verified') is True:
   form=proof.get('official_form',{});job=case.get('native_job',{});fields=job.get('fields',{})
   if not {'queryStartDate','queryEndDate'}<=set(form.get('fields',{})) or urllib.parse.urlsplit(form.get('source_page','')).hostname!='www.taifex.com.tw' or job.get('url')!='https://www.taifex.com.tw/cht/3/'+str(form.get('action')):raise ValueError('QUERY_FORM_FILTER_PROOF_REQUIRED')
   for name,expected in [('queryStartDate',job['start']),('queryEndDate',job['end'])]:
    if dt.date.fromisoformat(str(fields.get(name,'')).replace('/','-')).isoformat()!=expected:raise ValueError('QUERY_DATE_BINDING')
   if not job['start']<=case['period']<=job['end'] and not job['start'].startswith(case['period']):raise ValueError('QUERY_TASK_PERIOD_BINDING')
   applicable=True
  if case['source']=='TDCC' and proof.get('query_applicability_verified') is True:
   menu=proof.get('official_menu',{})
   if menu.get('url')!='https://www.tdcc.com.tw/portal/zh/smWeb/qryStock' or not re.fullmatch('[0-9a-f]{64}',menu.get('sha256') or '') or case.get('date') not in menu.get('offered_dates',[]) or not re.fullmatch('[0-9A-Za-z]{4,8}',case.get('code','')):raise ValueError('TDCC_QUERY_MENU_PROOF')
   if case['period']!=case['date'][:4]+'-'+case['date'][4:6]+'-'+case['date'][6:]:raise ValueError('TDCC_QUERY_PERIOD_BINDING')
   applicable=True
  if case['source']=='NDC' and proof.get('availability_verified') is True:
   archive=case.get('source_archive',{})
   if not re.fullmatch('[0-9a-f]{64}',archive.get('sha256') or '') or proof.get('verified_archive_sha256')!=archive['sha256'] or proof.get('verified_archive_file_id')!=archive.get('file_id'):raise ValueError('NDC_MISSING_ARCHIVE_BINDING')
  if old.get('attempts',0)>task['attempts'] or not applicable or not proof.get('official_evidence_id'):raise ValueError('MISSING_AVAILABILITY_OR_ATTEMPTS')
  if case['source']=='FinMind' and (proof.get('official_source') not in ('TWSE','TPEx','MOPS') or not all(proof.get(k) is True for k in ('confirmed_gap','identity_period_market_verified','definition_unit_frequency_verified','cross_source_alignment_approved'))):raise ValueError('FINMIND_GAP_NOT_APPROVED')
 def check_promotion(self,task):
  case=self.case;proof=case.get('promotion_evidence',{});old=task.get('legacy_review',{})
  if any(proof.get(k)!=case[k] for k in ('source','key','period')) or case.get('reference') or case.get('sha256') or not proof.get('verified_evidence_id'):raise ValueError('PROMOTION_IDENTITY_PROOF')
  if old.get('source')!=case['source'] or old.get('task_key')!=case['key'] or old.get('action')=='VERSION_CONFLICT_REVIEW' or old.get('attempts',0)>task['attempts']:raise ValueError('PROMOTION_LEGACY_SCOPE')
  if not isinstance(proof.get('reference'),str) or not re.fullmatch('[0-9a-f]{64}',proof.get('sha256') or '') or not any(v.get('raw_reference')==proof['reference'] and v.get('sha256')==proof['sha256'] and v.get('period')==case['period'] for v in old.get('provenance',[])):raise ValueError('PROMOTION_RECEIPT_BINDING')
 def check_repair(self,task):
  case=self.case;proof=case.get('repair_evidence',{});old=task.get('legacy_review',{})
  if case['source']=='FinMind':raise ValueError('FINMIND_REPAIR_ALIGNMENT_REVIEW_REQUIRED')
  if {v.get('period') for v in old.get('provenance',[])}!={case['period']}:raise ValueError('REPAIR_PERIOD_CONFLICT')
  if any(proof.get(k)!=case[k] for k in ('source','key','period')) or proof.get('download_approved') is not True or proof.get('reason')!='NATIVE_CONTENT_REJECTED' or not proof.get('official_evidence_id'):raise ValueError('REPAIR_APPROVAL_BINDING')
  if case.get('reference') or old.get('source')!=case['source'] or old.get('task_key')!=case['key'] or old.get('action')=='VERSION_CONFLICT_REVIEW' or old.get('attempts',0)>task['attempts']:raise ValueError('REPAIR_LEGACY_SCOPE')
  if not isinstance(proof.get('reference'),str) or not re.fullmatch('[0-9a-f]{64}',proof.get('sha256') or '') or not any(v.get('raw_reference')==proof['reference'] and v.get('sha256')==proof['sha256'] and v.get('period')==case['period'] for v in old.get('provenance',[])):raise ValueError('REPAIR_OLD_RECEIPT_BINDING')
  if proof.get('replacement_reference') and (not re.fullmatch('[0-9a-f]{64}',proof.get('replacement_sha256') or '') or proof.get('replacement_verified') is not True):raise ValueError('REPAIR_REPLACEMENT_RECEIPT')
 def verify_repair_needed(self):
  proof=self.case['repair_evidence'];raw=self.read(proof['reference'])
  if hashlib.sha256(raw).hexdigest()!=proof['sha256']:raise ApplicabilityUnproven('REPAIR_EVIDENCE_CHANGED_REVIEW_REQUIRED')
  try:self.validate(raw)
  except ApplicabilityUnproven:raise
  except ValueError:return
  raise ApplicabilityUnproven('REPAIR_NOT_NEEDED_EXISTING_VALID')
 def find(self,key):
  if key!=self.case['key']:raise ValueError('ADAPTER_TASK_MISMATCH')
  if self.case['mode']=='PROMOTE':
   self.destination_reference=self.find_locator(self.locator(key,self.case['promotion_evidence']['sha256']));return self.destination_reference
  return self.case.get('reference')
 def expected_receipt(self,key):
  if key!=self.case['key']:raise ValueError('ADAPTER_TASK_MISMATCH')
  if self.case['mode']=='PROMOTE':return dict(source=self.case['source'],task_key=key,period=self.case['period'],reference=self.destination_reference,sha256=self.case['promotion_evidence']['sha256'])
  return dict(source=self.case['source'],task_key=self.case['key'],period=self.case['period'],reference=self.case.get('reference'),sha256=self.case.get('sha256'))
 def before_request(self,ticket):
  if self.case['mode']=='REPAIR':self.verify_repair_needed()
  source=self.case['source'];cost=2 if source=='TDCC' else 0 if source=='NDC' else 1
  if self.case['mode']=='PROMOTE' or self.case['mode']=='REPAIR' and self.case['repair_evidence'].get('replacement_reference'):cost=0
  reserve(self.c,ticket,cost=cost,limit=200 if source=='FinMind' else 30,window=3600 if source=='FinMind' else 60,spacing=2)
 def http(self,url,params=None,headers=None):
  source=self.case['source'];allowed={'TWSE':{'www.twse.com.tw'},'TPEx':{'www.tpex.org.tw','hist.tpex.org.tw'},'MOPS':{'mopsov.twse.com.tw','mops.twse.com.tw','mopsfin.twse.com.tw'},'TAIFEX':{'www.taifex.com.tw','openapi.taifex.com.tw'},'FinMind':{'api.finmindtrade.com'}}
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
  if case['mode']=='PROMOTE':
   proof=case['promotion_evidence'];raw=self.read(proof['reference'])
   if hashlib.sha256(raw).hexdigest()!=proof['sha256']:raise ValueError('PROMOTION_SOURCE_SHA_CHANGED')
   self.validate(raw);return raw
  if case['mode']=='REPAIR' and case['repair_evidence'].get('replacement_reference'):
   proof=case['repair_evidence'];raw=self.read(proof['replacement_reference'])
   if hashlib.sha256(raw).hexdigest()!=proof['replacement_sha256']:raise ValueError('REPAIR_REPLACEMENT_SHA_CHANGED')
   self.validate(raw);return raw
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
   try:stats=validate(raw,source,self.case['category'],self.case['period'])
   except ValueError as exc:
    if unconfirmed_empty(source,exc):raise ApplicabilityUnproven('OFFICIAL_EMPTY_UNCONFIRMED') from None
    raise
   return dict(basic_verified=True,native=stats)
  if source=='TDCC':
   from scripts.v093_tdcc_independent import validate_history,SourceEmpty
   try:rows=validate_history(raw,self.case['date'],self.case['code'])
   except SourceEmpty:raise ApplicabilityUnproven('OFFICIAL_EMPTY_UNCONFIRMED') from None
   return dict(basic_verified=True,rows=rows)
  try:return super().validate(raw)
  except Exception as exc:
   if unconfirmed_empty(source,exc):raise ApplicabilityUnproven('OFFICIAL_EMPTY_UNCONFIRMED') from None
   if source=='TAIFEX':
    from scripts.v093_taifex_independent import OfficialEmpty
    if isinstance(exc,OfficialEmpty):raise ApplicabilityUnproven('OFFICIAL_EMPTY_UNCONFIRMED') from None
   if source=='FinMind':
    if str(exc)=='EMPTY_FINMIND_NOT_ACCEPTED':raise ApplicabilityUnproven('FINMIND_EMPTY_UNCONFIRMED') from None
    from scripts.v093_stage07_finmind import ProviderPause
    if isinstance(exc,ProviderPause):raise SourcePaused('FINMIND_PROVIDER_REVIEW') from None
   raise
 def preserve_rejected(self,raw):
  from scripts.v093_rejected_evidence import preserve
  return preserve(self.d,self.case['source'],raw,qa=self.target_root!=RAW_ROOT)
 def ensure_receipt(self,key,sha,reference,stats):
  if not self.download_authorized:return None
  if key!=self.case['key'] or not re.fullmatch('[0-9a-f]{64}',sha):raise ValueError('NATIVE_SIDECAR_BINDING')
  proof=self.case.get('promotion_evidence') or self.case.get('repair_evidence',{})
  receipt=dict(schema='JARVIS_NATIVE_RAW_RECEIPT_V1',source=self.case['source'],task_key=key,period=self.case['period'],raw_reference=reference,raw_sha256=sha,mode=self.case['mode'],previous_reference=proof.get('reference'),previous_sha256=proof.get('sha256'),evidence_id=proof.get('verified_evidence_id') or proof.get('official_evidence_id') or self.case.get('missing_evidence',{}).get('official_evidence_id'),basic_verified=True,numeric_verified=False,pit_verified=False,full_acceptance=False,units='AS_PUBLISHED_NO_CONVERSION')
  raw=json.dumps(receipt,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode();name=self.locator(key,sha)+'.receipt_'+hashlib.sha256(raw).hexdigest()+'.json'
  self.d.direct_readback=True;self.d.put(self.storage_folder(),name,raw,'application/json',overwrite=False)
  found=self.d.find(self.storage_folder(),name)
  if not found:raise ValueError('NATIVE_SIDECAR_REFERENCE_MISSING')
  stored=self.d.call(lambda:self.d.api.files().get_media(fileId=found['id']))
  if stored!=raw:raise ValueError('NATIVE_SIDECAR_READBACK_MISMATCH')
  return dict(reference=found['id'],sha256=hashlib.sha256(raw).hexdigest(),raw_reference=reference,raw_sha256=sha,readback_verified=True)

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
