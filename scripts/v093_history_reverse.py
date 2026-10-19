"""Durable, strictly newest-to-oldest 120-month official-first ingestion.
One active runner. Native response bytes and receipts committed in small ZIPs.
Month finalization != full market, numeric, or PIT certification.
"""
import calendar, collections, concurrent.futures, datetime as dt, io, json, os, re, time
import urllib.error, urllib.parse, urllib.request, zipfile
from pathlib import Path
from scripts.annual_actual_firstpass import Drive,service
from scripts.v093_three_year_repair import ROOT,REPORT_ROOT,Audit,validate,request,stamp,sha,listing,read
from scripts.v093_three_year_finmind_gaps import financial_rows,MAP

RUN='HISTORY_202312_TO_201401_R1'
OTHER_FINMIND_CONTROL='10gSrB8uPzkYob7oXlAiuiLzIJq5_gsh_'
MONTHS=[f'{y}-{m:02d}' for y in range(2023,2013,-1) for m in range(12,0,-1)]
FIN_REPORTS=('IncomeStatement','BalanceSheet','CashflowStatement')

def getj(d,parent,name):
 f=d.find(parent,name)
 return json.loads(read(d,f)) if f else None
def putj(d,parent,name,obj):
 d.put(parent,name,(json.dumps(obj,ensure_ascii=False,indent=2)+'\n').encode(),'application/json',overwrite=True)
def key(j):return sha(json.dumps({k:j.get(k) for k in ('source','category','period','stock_id','codes','dataset')},sort_keys=True).encode())[:24]
def packed(items):
 out=io.BytesIO()
 with zipfile.ZipFile(out,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
  units=[]
  for receipt,raw in items:
   n=receipt['unit_id']+'.raw';z.writestr(n,raw);units.append(dict(receipt,file=n))
  z.writestr('manifest.json',json.dumps({'run':RUN,'units':units,'numeric_verified':False,'pit_verified':False},ensure_ascii=False))
 b=out.getvalue()
 with zipfile.ZipFile(io.BytesIO(b)) as z:
  if z.testzip():raise ValueError('NEW_ZIP_CRC_FAILED')
 return b

class History:
 def __init__(self,minutes):
  self.d=Drive(service());self.control=self.d.folder(REPORT_ROOT,RUN)
  self.checkpoint=getj(self.d,self.control,'CURSOR.json') or {'version':RUN,'month_index':0,'mode':'PRIMARY_MONTHS','backlog_month_index':0,'finished_months':[],'created_utc':stamp()}
  if self.checkpoint.get('version')!=RUN:raise ValueError('CURSOR_VERSION_CONFLICT')
  self.until=time.monotonic()+minutes*60;self.circuit=collections.Counter();self.folders={};self.request_counts=collections.Counter();self.active=None
 def folder(self,source,month):
  k=(source,month)
  if k not in self.folders:self.folders[k]=self.d.folder(self.d.folder(self.d.folder(ROOT,month[:4]),source),month)
  return self.folders[k]
 def save_cursor(self):
  self.checkpoint['updated_utc']=stamp();putj(self.d,self.control,'CURSOR.json',self.checkpoint)
 def calendar(self,year):
  ref=self.d.folder(self.control,'REFERENCES');old=getj(self.d,ref,str(year)+'_calendar_validation.json')
  if old:return set(old.get('closed',[]))
  info={'year':year,'verified':False,'closed':[],'attempts':[]}
  for params in ({'date':str(year)+'0101','response':'json'},{'queryYear':year-1911,'response':'json'}):
   url='https://www.twse.com.tw/rwd/zh/holidaySchedule/holidaySchedule?'+urllib.parse.urlencode(params)
   try:
    self.request_counts['TWSE']+=1;b=request(url);x=json.loads(b);rows=x.get('data') or []
    closed=[r[0] for r in rows if isinstance(r,list) and len(r)>1 and re.fullmatch(str(year)+r'-\d\d-\d\d',str(r[0])) and not any(k in str(r[1]) for k in ('開始交易','最後交易'))]
    self.d.put(ref,f'{year}_calendar_{sha(b)[:12]}.json',b,'application/json',overwrite=False)
    info['attempts'].append({'url':url,'sha256':sha(b),'matching_year_closed_dates':len(closed)})
    if closed:info.update(verified=True,closed=closed);break
   except Exception as e:info['attempts'].append({'url':url,'error':str(e)[:160]})
  putj(self.d,ref,str(year)+'_calendar_validation.json',info);return set(info['closed'])
 def restore(self,month,ctrl):
  state=getj(self.d,ctrl,'MONTH_STATE.json') or {'month':month,'units':{},'financial_units':{},'finmind_units':{},'finmind_tasks':[],'phase':'OFFICIAL_CORE','stocks':[],'market_codes':{},'archives':[],'started_utc':stamp()}
  # Recover raw ZIPs committed before a cursor write was interrupted.
  for source in ('TWSE','TPEx','MOPS','FinMind'):
   files=listing(self.d,self.folder(source,month))
   known={x['name'] for x in state['archives']}
   for f in files:
    if not f['name'].startswith(RUN+'_') or not f['name'].endswith('.zip') or f['name'] in known:continue
    b=read(self.d,f)
    with zipfile.ZipFile(io.BytesIO(b)) as z:
     if z.testzip():raise ValueError('EXISTING_ZIP_CRC_FAILED:'+f['name'])
     man=json.loads(z.read('manifest.json'))
     if man.get('run')!=RUN:raise ValueError('ARCHIVE_RUN_MISMATCH')
     for u in man['units']:
      native=z.read(u['file'])
      if sha(native)!=u['sha256']:raise ValueError('ARCHIVE_MEMBER_SHA_MISMATCH')
      if u['month']!=month:raise ValueError('ARCHIVE_MONTH_MISMATCH')
      bucket=u.get('bucket','units');state[bucket][u['unit_id']]=u
      state['stocks']=sorted(set(state['stocks'])|set(u.get('codes_found',[])))
      if u['source'] in ('TWSE','TPEx'):
       state['market_codes'][u['source']]=sorted(set(state['market_codes'].get(u['source'],[]))|set(u.get('codes_found',[])))
    state['archives'].append({'name':f['name'],'sha256':sha(b),'file_id':f['id'],'bytes':len(b),'recovered':True})
  self.state=state;self.monthctrl=ctrl;self.active=month
 def save_state(self):
  self.state['updated_utc']=stamp();putj(self.d,self.monthctrl,'MONTH_STATE.json',self.state)
 def flush(self,results,bucket):
  groups=collections.defaultdict(list);failed=[]
  for j,e,b in results:
   if b is not None:
    if e['status']=='SAVED_BASIC_VERIFIED':groups[e['source']].append((e,b))
    else:failed.append((e,b))
  for source,items in groups.items():
   b=packed(items);name=RUN+'_'+bucket+'_'+sha(b)[:20]+'.zip'
   folder=self.folder(source,self.active);self.d.put(folder,name,b,'application/zip',overwrite=False)
   self.state['archives'].append({'name':name,'source':source,'sha256':sha(b),'bytes':len(b),'remote_readback_verified':True})
  if failed:
   q=self.d.folder(self.monthctrl,'QUARANTINE');b=packed(failed);name='quarantine_'+sha(b)[:20]+'.zip';self.d.put(q,name,b,'application/zip',overwrite=False)
  for j,e,b in results:
   self.state[bucket][e['unit_id']]=e
   self.state['stocks']=sorted(set(self.state['stocks'])|set(e.get('codes_found',[])))
   if e['source'] in ('TWSE','TPEx'):
    self.state['market_codes'][e['source']]=sorted(set(self.state['market_codes'].get(e['source'],[]))|set(e.get('codes_found',[])))
  self.save_state()
 def fetch_one(self,j,bucket):
  scope=(j['source'],j['category'],j['period'][:4]);e=dict(j,unit_id=key(j),bucket=bucket,attempts=0,status='DEFERRED_MISSING',numeric_verified=False,pit_verified=False,requested_utc=stamp());b=None
  if self.circuit[scope]>=2:e['status']='SYSTEMIC_SOURCE_HOLD';return j,e,b
  try:
   e['attempts']=1;self.request_counts[j['source']]+=1;b=request(j['url'],j.get('params'))
   if bucket=='financial_units':
    holder=object.__new__(Audit);holder.year=int(self.active[:4]);holder.financial={}
    Audit.financial_payload(holder,b,j['category'],j['url'])
    got=sorted({c for c,r,p in holder.financial if r==j['category'] and p==j['report_period'] and c in j['codes']})
    if not got:raise ValueError('NO_EXPLICIT_COMPANY_QUARTER_NUMERIC_CELLS')
    e.update(codes_found=got,rows=len(got),partial_financial_cells_only=True)
   else:
    stats=validate(b,j['source'],j['category'],j['period']);e.update(rows=stats['rows'],codes_found=stats['codes'])
   e.update(status='SAVED_BASIC_VERIFIED',sha256=sha(b),bytes=len(b));self.circuit[scope]=0
  except Exception as ex:
   err=type(ex).__name__+':'+str(ex)[:180];e['error']=err
   if not any(s in err for s in ('EMPTY_RESPONSE','EMPTY_EVENT','沒有符合條件','查無資料')):self.circuit[scope]+=1
   if b is not None:e.update(sha256=sha(b),bytes=len(b))
  e['completed_utc']=stamp();time.sleep(.35);return j,e,b
 def process(self,jobs,bucket):
  pending=[j for j in jobs if key(j) not in self.state[bucket]]
  for i in range(0,len(pending),12):
   if time.monotonic()>self.until:return False
   part=pending[i:i+12]
   # Only source HTTP calls are concurrent; all Drive commits are single-threaded.
   with concurrent.futures.ThreadPoolExecutor(max_workers=2) as ex:results=list(ex.map(lambda j:self.fetch_one(j,bucket),part))
   self.flush(results,bucket)
   print(json.dumps({'month':self.active,'phase':bucket,'processed':len(self.state[bucket]),'planned':len(jobs),'states':dict(collections.Counter(e['status'] for e in self.state[bucket].values()))}),flush=True)
  return True
 def financial_jobs(self):
  year,mo=map(int,self.active.split('-'))
  if mo not in (3,6,9,12):return []
  q=mo//3;end=f'{year}-{mo:02d}-'+('31' if mo in (3,12) else '30');codes=self.state['stocks'];jobs=[]
  for report in FIN_REPORTS:
   for i in range(0,len(codes),20):
    chunk=codes[i:i+20];params=[('compareItem',report),('quarter','false'),('ylabel',{'IncomeStatement':'綜合損益表(累計)','BalanceSheet':'資產負債表','CashflowStatement':'現金流量表(累計)'}[report]),('ys',str(year)+str(q)),('revenue','false'),('bcodeAvg','false'),('companyAvg','false'),('qnumber','')]+[('companyId',c) for c in chunk]
    jobs.append({'source':'MOPS','category':report,'period':end,'report_period':str(year)+str(q),'month':self.active,'codes':chunk,'url':'https://mopsfin.twse.com.tw/compare/report','params':params})
  return jobs
 def fm_plan(self,core):
  tasks={}
  # All explicit residual financial company/report/quarter pairs, no silent sampling.
  for e in self.state['financial_units'].values():
   for code in e['codes']:
    if code in e.get('codes_found',[]):continue
    t={'source':'FinMind','category':e['category'],'dataset':MAP[e['category']],'stock_id':code,'period':e['period'],'month':self.active,'kind':'financial','official_gap':e['unit_id']};tasks[key(t)]=t
  mapping={'prices':'TaiwanStockPrice','prices_indices':'TaiwanStockPrice','institutional':'TaiwanStockInstitutionalInvestorsBuySell','margin':'TaiwanStockMarginPurchaseShortSale','valuation':'TaiwanStockPER','foreign_holdings':'TaiwanStockShareholding'}
  for j in core:
   e=self.state['units'].get(key(j),{})
   if e.get('status')=='SAVED_BASIC_VERIFIED' or j['category'] not in mapping:continue
   for code in self.state['market_codes'].get(j['source'],[]):
    t={'source':'FinMind','category':j['category'],'dataset':mapping[j['category']],'stock_id':code,'period':self.active,'month':self.active,'kind':'daily_month','official_missing_dates':[],'raw_only_not_cross_source_aligned':True}
    k=key(t)
    if k not in tasks:tasks[k]=t
    tasks[k].setdefault('official_missing_dates',[]).append(j['period'])
  for j in core:
   if j['source']!='MOPS' or not j['category'].startswith('revenue_') or self.state['units'].get(key(j),{}).get('status')=='SAVED_BASIC_VERIFIED':continue
   market='TWSE' if '_sii_' in j['category'] else 'TPEx'
   for code in self.state['market_codes'].get(market,[]):
    t={'source':'FinMind','category':'month_revenue','dataset':'TaiwanStockMonthRevenue','stock_id':code,'period':self.active,'month':self.active,'kind':'revenue','official_gap':key(j),'date_role':'revenue_month_not_announcement_month'};tasks[key(t)]=t
  return list(tasks.values())
 def quota(self):
  token=(os.environ.get('FINMIND_TOKEN') or os.environ.get('FINMIND_API_TOKEN') or '').strip();cap=480 if token else 240;now=time.time()
  ledger=getj(self.d,self.control,'FINMIND_REQUEST_LEDGER.json') or []
  own=[x for x in ledger if now-x['at']<3600]
  other=getj(self.d,OTHER_FINMIND_CONTROL,'FinMind_request_ledger.json') or []
  shared=sum(x['count'] for x in other if now-x['at']<3600)
  return max(0,cap-shared-sum(x['count'] for x in own)),own,token
 def finmind(self,max_tasks):
  budget,ledger,token=self.quota();budget=min(budget,max_tasks);tasks=self.state.get('finmind_tasks',[])
  pending=[t for t in tasks if key(t) not in self.state['finmind_units']]
  for task in pending[:budget]:
   if time.monotonic()>self.until:return False
   start=self.active+'-01';end=self.active+f'-{calendar.monthrange(int(self.active[:4]),int(self.active[5:]))[1]:02d}'
   if task['kind']=='financial':start=task['period'][:4]+'-'+f'{int(task["period"][5:7])-2:02d}'+'-01';end=task['period']
   elif task['kind']=='revenue':
    yy,mm=map(int,self.active.split('-'));yy,mm=(yy+1,1) if mm==12 else (yy,mm+1)
    start=f'{yy}-{mm:02d}-01';end=f'{yy}-{mm:02d}-{calendar.monthrange(yy,mm)[1]:02d}'
   params={'dataset':task['dataset'],'data_id':task['stock_id'],'start_date':start,'end_date':end}
   e=dict(task,unit_id=key(task),bucket='finmind_units',attempts=1,status='DEFERRED_MISSING',requested_utc=stamp());b=None;quota_stop=False
   # Reserve quota BEFORE the HTTP request, surviving runner interruptions.
   ledger.append({'at':time.time(),'count':1});putj(self.d,self.control,'FINMIND_REQUEST_LEDGER.json',ledger)
   try:
    self.request_counts['FinMind']+=1;headers={'User-Agent':'JARVIS-0.93-history-gap-only','Accept':'application/json'}
    if token:headers['Authorization']='Bearer '+token
    req=urllib.request.Request('https://api.finmindtrade.com/api/v4/data?'+urllib.parse.urlencode(params),headers=headers)
    with urllib.request.urlopen(req,timeout=25) as r:b=r.read(18000001)
    if len(b)>18000000:raise ValueError('API_BODY_LIMIT')
    x=json.loads(b);status=x.get('status')
    if status in (401,402,403,429):quota_stop=True;raise ValueError('FINMIND_QUOTA_OR_AUTH:'+str(status))
    if status!=200 or not isinstance(x.get('data'),list):raise ValueError('FINMIND_BAD_ENVELOPE')
    rows=x['data']
    if not rows:raise ValueError('EMPTY_NOT_PROOF_OF_NO_HISTORY')
    if any(not isinstance(r,dict) or str(r.get('stock_id',''))!=task['stock_id'] or not (start<=str(r.get('date',''))<=end) for r in rows):raise ValueError('STOCK_OR_PERIOD_MISMATCH')
    if task['kind']=='financial' and (task['stock_id'],task['dataset'],task['period']) not in financial_rows(b,task['dataset']):raise ValueError('QUARTER_NUMERIC_CELLS_UNPROVEN')
    if task['kind']=='revenue' and any(str(r.get('revenue_year'))!=self.active[:4] or int(r.get('revenue_month',0))!=int(self.active[5:]) for r in rows):raise ValueError('REVENUE_CONTENT_MONTH_MISMATCH')
    e.update(status='SAVED_BASIC_VERIFIED',sha256=sha(b),bytes=len(b),rows=len(rows),numeric_verified=False,pit_verified=False)
   except Exception as ex:
    if isinstance(ex,urllib.error.HTTPError) and ex.code in (401,402,403,429):quota_stop=True
    e['error']=type(ex).__name__+':'+str(ex)[:160]
    if b is not None:e.update(sha256=sha(b),bytes=len(b))
   if quota_stop:
    # Keep this task pending and let the rolling quota window expire.
    ledger.append({'at':time.time(),'count':480 if token else 240});putj(self.d,self.control,'FINMIND_REQUEST_LEDGER.json',ledger)
    putj(self.d,self.monthctrl,'FINMIND_PROVIDER_HOLD.json',e);return False
   self.flush([(task,e,b)],'finmind_units')
   time.sleep(.3)
  return len(pending)<=budget
 def month_report(self,core):
  units=list(self.state['units'].values());fin=list(self.state['financial_units'].values());fm=list(self.state['finmind_units'].values())
  unresolved=[e for e in units+fin+fm if e['status']!='SAVED_BASIC_VERIFIED']
  fm_pending=[t for t in self.state['finmind_tasks'] if key(t) not in self.state['finmind_units']]
  report={'run':RUN,'month':self.active,'saved_utc':stamp(),'phase':self.state['phase'],'expected_core_units':len(core),'core_counts':dict(collections.Counter(e['status'] for e in units)),'financial_counts':dict(collections.Counter(e['status'] for e in fin)),'finmind_counts':dict(collections.Counter(e['status'] for e in fm)),'finmind_pending_tasks':len(fm_pending),'archives':self.state['archives'],'source_requests':dict(collections.Counter(e['source'] for e in units+fin+fm for _ in range(e.get('attempts',0)))),'provisional_stock_ids':len(self.state['stocks']),'full_market_complete':False,'numeric_verified':False,'pit_verified':False,'missing_or_unverified':unresolved,'source_alignment':'NATIVE_SOURCES_SEPARATE_NO_SILENT_FIELD_MERGE'}
  putj(self.d,self.monthctrl,'MONTH_REPORT.json',report)
  putj(self.d,self.monthctrl,'MISSING_AND_PENDING.json',{'month':self.active,'unresolved':unresolved,'finmind_pending':fm_pending})
  putj(self.d,self.monthctrl,'DOWNLOAD_LOG.json',{'month':self.active,'units':units+fin+fm})
  good=sum(e['status']=='SAVED_BASIC_VERIFIED' for e in units)
  text=f'# {self.active} 歷史原始資料下載紀錄\n\n階段：{self.state["phase"]}。官方核心表格取得 {good}/{len(core)}；財報分組 {len(fin)}；FinMind已處理 {len(fm)}、待處理 {len(fm_pending)}。\n\n原始檔存於既有 `01_RAW/{self.active[:4]}/來源/{self.active}`；本月控制目錄保存完整下載、缺漏、雜湊及斷點。財報部分數值、股票名單、數值與公告可得時間尚未全面驗收，不能視為全市場完整庫。\n'
  self.d.put(self.monthctrl,'REPORT.md',text.encode(),'text/markdown',overwrite=True)
  return report
 def dashboard(self):
  x=self.checkpoint;idx=x['month_index'];body={'run':RUN,'order':'2023-12 descending to 2014-01','total_months':120,'months_primary_processed':idx,'primary_month_progress_percent':round(idx/120*100,2),'active_month':self.active,'mode':x['mode'],'finished_months':x['finished_months'],'last_update_utc':stamp(),'run_source_requests':dict(self.request_counts),'done':x.get('done',False),'numeric_verified':False,'pit_verified':False,'full_market_complete':False}
  putj(self.d,self.control,'PROGRESS.json',body)
  text=f'# 2014–2023 十年歷史下載進度\n\n更新：{body["last_update_utc"]}\n\n倒序：2023-12 → 2023-11 → … → 2014-01。\n\n已完成官方主流程月結：{idx}/120（{body["primary_month_progress_percent"]}%）；目前月份：{self.active}；階段：{x["mode"]}。\n\n這是月份處理進度，不是全市場資料完整率。各月 REPORT.md、DOWNLOAD_LOG.json、MISSING_AND_PENDING.json 保留成功、缺漏與尚未請求事項。FinMind額度不足時先保留補充佇列，官方月份繼續倒序處理。\n'
  self.d.put(self.control,'PROGRESS.md',text.encode(),'text/markdown',overwrite=True)
 def run(self):
  if self.checkpoint.get('done'):
   self.disable_finished_schedule();print('HISTORY_ALREADY_FINISHED_WITH_RECORDED_GAPS',flush=True);return
  if not self.d.find(self.control,'PLAN.json'):
   putj(self.d,self.control,'PLAN.json',{'run':RUN,'months':MONTHS,'order':'STRICT_DESCENDING_PRIMARY_MONTHS','sources':['TWSE','TPEx','MOPS','FinMind'],'official_first':True,'source_raw_immutable':True,'legacy_imports':0,'month_finalization_does_not_certify_completeness':True})
  self.checkpoint['active_month']=MONTHS[self.checkpoint['month_index']] if self.checkpoint['month_index']<120 else None
  self.active=self.checkpoint['active_month'];self.save_cursor();self.dashboard()
  while self.checkpoint['month_index']<120 and time.monotonic()<self.until:
   idx=self.checkpoint['month_index'];month=MONTHS[idx];ctrl=self.d.folder(self.control,month);self.restore(month,ctrl)
   closed=self.calendar(int(month[:4]));holder=object.__new__(Audit);core=Audit.jobs(holder,month,closed)
   if self.state['phase']=='OFFICIAL_CORE':
    if not self.process(core,'units'):self.month_report(core);break
    self.state['phase']='OFFICIAL_FINANCIAL';self.save_state()
   if self.state['phase']=='OFFICIAL_FINANCIAL':
    if not self.process(self.financial_jobs(),'financial_units'):self.month_report(core);break
    self.state['finmind_tasks']=self.fm_plan(core);self.state['phase']='FINMIND_SUPPLEMENT';self.save_state()
   if self.state['phase']=='FINMIND_SUPPLEMENT':
    self.finmind(6)
    self.state['phase']='PRIMARY_MONTH_SAVED_WITH_EXPLICIT_GAPS';self.save_state()
   report=self.month_report(core)
   self.checkpoint['finished_months'].append({'month':month,'core_counts':report['core_counts'],'finmind_pending':report['finmind_pending_tasks'],'report_folder_id':ctrl,'saved_utc':stamp()})
   self.checkpoint['month_index']=idx+1;self.save_cursor();self.dashboard()
   print(json.dumps({'state':'MONTH_COMMITTED','month':month,'next_month':MONTHS[idx+1] if idx+1<120 else None,'core_counts':report['core_counts'],'finmind_pending':report['finmind_pending_tasks']}),flush=True)
  if self.checkpoint['month_index']>=120:
   self.checkpoint['mode']='FINMIND_BACKLOG';index=self.checkpoint['backlog_month_index']
   while index<120 and time.monotonic()<self.until:
    month=MONTHS[index];ctrl=self.d.folder(self.control,month);self.restore(month,ctrl)
    if not self.finmind(240):self.save_state();break
    self.state['phase']='PROCESSED_WITH_RECORDED_GAPS';self.save_state()
    holder=object.__new__(Audit);core=Audit.jobs(holder,month,self.calendar(int(month[:4])));self.month_report(core)
    index+=1;self.checkpoint['backlog_month_index']=index;self.save_cursor()
   if index>=120:self.checkpoint.update(done=True,mode='FINISHED_WITH_EXPLICIT_GAPS')
  self.save_cursor();self.dashboard()
  if self.checkpoint.get('done'):self.disable_finished_schedule()
  print(json.dumps({'state':'BATCH_CHECKPOINTED','month_index':self.checkpoint['month_index'],'active_month':self.active,'mode':self.checkpoint['mode'],'done':self.checkpoint.get('done',False),'control_folder_id':self.control,'requests':dict(self.request_counts)}),flush=True)
 def disable_finished_schedule(self):
  token=os.environ.get('GITHUB_TOKEN','');repo=os.environ.get('GITHUB_REPOSITORY','')
  if not token or not repo:return
  try:
   req=urllib.request.Request('https://api.github.com/repos/'+repo+'/actions/workflows/v093-history-2023-to-2014-descending.yml/disable',data=b'',method='PUT',headers={'Authorization':'Bearer '+token,'Accept':'application/vnd.github+json'})
   with urllib.request.urlopen(req,timeout=15):pass
   print('FINISHED_SCHEDULE_DISABLED',flush=True)
  except Exception as ex:print('FINISHED_SCHEDULE_DISABLE_FAILED:'+type(ex).__name__,flush=True)

if __name__=='__main__':
 import argparse
 p=argparse.ArgumentParser();p.add_argument('--minutes',type=int,default=45);a=p.parse_args();History(a.minutes).run()
