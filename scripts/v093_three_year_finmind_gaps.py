"""Bounded FinMind supplementation AFTER official three-year audit.
Only explicit company/report/quarter gaps; no universe-wide blind recrawl.
Unfilled work and unmapped daily fields remain visible in the final report.
"""
import collections, datetime as dt, io, json, math, os, re, time, urllib.error, urllib.parse, urllib.request, zipfile
from scripts.annual_actual_firstpass import Drive,service
from scripts.v093_three_year_repair import ROOT,REPORT_ROOT,PASS,listing,read,putj,stamp,sha
MAP={'IncomeStatement':'TaiwanStockFinancialStatements','BalanceSheet':'TaiwanStockBalanceSheet','CashflowStatement':'TaiwanStockCashFlowsStatement'}

def getj(d,p,name):
 f=d.find(p,name)
 return json.loads(read(d,f)) if f else None
def financial_rows(raw,name):
 try:x=json.loads(raw.decode('utf-8-sig'))
 except (UnicodeDecodeError,ValueError):return []
 if not isinstance(x,dict):return []
 ds=x.get('dataset') or next((v for v in MAP.values() if v in name),'')
 if ds not in MAP.values():return []
 rows=x.get('data',x.get('rows',[]))
 if not isinstance(rows,list):return []
 out=[]
 for r in rows:
  if not isinstance(r,dict):continue
  code=str(r.get('stock_id',''));date=str(r.get('date',''))
  if not re.fullmatch(r'[1-9]\d{3}',code) or not re.fullmatch(r'20\d{2}-(03-31|06-30|09-30|12-31)',date):continue
  try:value=float(r.get('value'))
  except (ValueError,TypeError):continue
  if math.isfinite(value):out.append((code,ds,date))
 return out

def main():
 d=Drive(service());reports=d.find(REPORT_ROOT,PASS)
 if not reports:raise ValueError('OFFICIAL_REPORT_FOLDER_NOT_FOUND')
 report=reports['id'];yearinfo={};covered=set();audit=[];queues={};unknown=[]
 for year in (2024,2025,2026):
  yf=d.find(report,str(year))
  if not yf:unknown.append({'year':year,'reason':'OFFICIAL_AUDIT_NOT_FINISHED'});continue
  summary=getj(d,yf['id'],'year_summary.json');groups=getj(d,yf['id'],'financial_gap_groups.json')
  if summary is None or groups is None:unknown.append({'year':year,'reason':'OFFICIAL_AUDIT_NOT_FINISHED'});continue
  yearinfo[year]={'report_folder':yf['id'],'summary':summary,'groups':groups}
  yroot=d.find(ROOT,str(year));fm=d.find(yroot['id'],'FinMind') if yroot else None
  if fm:
   for month in listing(d,fm['id']):
    if month['mimeType']!='application/vnd.google-apps.folder' or not re.fullmatch(str(year)+r'-\d\d',month['name']):continue
    for f in listing(d,month['id']):
     if f['mimeType']=='application/vnd.google-apps.folder' or f['name'].endswith('.receipt.json'):continue
     e={'year':year,'file':f['name'],'file_id':f['id']}
     try:
      if int(f.get('size',0))>350000000:raise ValueError('LARGE_FILE_DEFERRED')
      b=read(d,f);e['sha256']=sha(b);n=0
      if f['name'].endswith('.zip'):
       with zipfile.ZipFile(io.BytesIO(b)) as z:
        if sum(x.file_size for x in z.infolist())>1200000000:raise ValueError('UNCOMPRESSED_SIZE_LIMIT')
        if z.testzip():raise ValueError('ZIP_CRC_FAILED')
        for name in z.namelist():
         if name.endswith(('.raw','.json')) and not name.endswith('manifest.json'):
          rows=financial_rows(z.read(name),name);covered.update(rows);n+=len(rows)
      elif f['name'].endswith(('.json','.raw')):
       rows=financial_rows(b,f['name']);covered.update(rows);n=len(rows)
      e.update(status='STORAGE_AND_FINANCIAL_ROWS_AUDITED',financial_numeric_rows=n)
     except Exception as exc:e.update(status='AUDIT_HOLD',error=str(exc)[:200])
     audit.append(e)
  q=[]
  for g in groups:
   per=g['period'];quarter=int(per[-1]);end=f'{year}-{quarter*3:02d}-'+('31' if quarter in (1,4) else '30')
   for code in g['codes']:
    if code in g.get('covered_codes',[]):continue
    task=(code,MAP[g['report']],end)
    if task not in covered:q.append({'year':year,'stock_id':code,'dataset':MAP[g['report']],'period_end':end,'month':end[:7],'official_gap_report':g['report'],'official_gap_status':g['status']})
  # Every task corresponds to an explicit residual official financial gap.
  queues[year]=q
 putj(d,report,'FinMind_existing_file_audit.json',audit)
 token=(os.environ.get('FINMIND_TOKEN','') or os.environ.get('FINMIND_API_TOKEN','')).strip()
 limit=480 if token else 240;start=time.time();completed=[];failed=[];out=[];stop=None;attempts=0
 # Fair interleave across years; one annual dataset never starves the other years.
 work=[]
 for i in range(max([len(q) for q in queues.values()] or [0])):
  for y in (2024,2025,2026):
   if i<len(queues.get(y,[])):work.append(queues[y][i])
 ledger=getj(d,report,'FinMind_request_ledger.json') or []
 recent=[x for x in ledger if start-x['at']<3600]
 available=max(0,limit-sum(x['count'] for x in recent))
 for task in work[:available]:
  if time.time()-start>35*60:stop='EXECUTION_TIME_BUDGET';break
  params={'dataset':task['dataset'],'data_id':task['stock_id'],'start_date':task['period_end'][:4]+'-'+f'{int(task["period_end"][5:7])-2:02d}'+'-01','end_date':task['period_end']}
  headers={'User-Agent':'Mozilla/5.0 JARVIS-official-gap-only','Accept':'application/json'}
  if token:headers['Authorization']='Bearer '+token
  try:
   attempts+=1;req=urllib.request.Request('https://api.finmindtrade.com/api/v4/data?'+urllib.parse.urlencode(params),headers=headers)
   with urllib.request.urlopen(req,timeout=25) as r:b=r.read(18000001)
   if len(b)>18000000:raise ValueError('BODY_LIMIT')
   obj=json.loads(b);status=obj.get('status')
   if status!=200 or not isinstance(obj.get('data'),list):
    if status in (401,402,403,429):stop='PROVIDER_QUOTA_OR_AUTHENTICATION'
    raise ValueError('API_STATUS:'+str(status))
   rows=obj['data']
   if not rows:raise ValueError('EMPTY_NOT_VERIFIED_NO_FILING')
   if any(not isinstance(r,dict) or str(r.get('stock_id',''))!=task['stock_id'] or str(r.get('date',''))!=task['period_end'] for r in rows):raise ValueError('STOCK_OR_QUARTER_MISMATCH')
   if (task['stock_id'],task['dataset'],task['period_end']) not in financial_rows(b,task['dataset']):raise ValueError('NO_FINITE_NUMERIC_CELLS')
   yr=d.find(ROOT,str(task['year']))['id'];folder=d.folder(d.folder(yr,'FinMind'),task['month'])
   name=f"{PASS}_{task['dataset']}_{task['stock_id']}_{task['period_end']}_{sha(b)[:12]}.json"
   d.put(folder,name,b,'application/json',overwrite=False)
   receipt=dict(task,request_params=params,sha256=sha(b),bytes=len(b),rows=len(rows),source='FinMind',saved_at_utc=stamp(),numeric_verified=False,pit_verified=False,coverage='PARTIAL_REPORTED_NUMERIC_CELLS_ONLY',official_raw_overwritten=False)
   d.put(folder,name+'.receipt.json',json.dumps(receipt,ensure_ascii=False,indent=2).encode(),'application/json',overwrite=False)
   completed.append(dict(task,file=name,rows=len(rows),bytes=len(b),sha256=sha(b)));out.append(dict(task,status='SAVED_AND_REMOTE_READBACK_VERIFIED'))
  except Exception as exc:
   if isinstance(exc,urllib.error.HTTPError) and exc.code in (401,402,403,429):stop='PROVIDER_QUOTA_OR_AUTHENTICATION'
   failed.append(dict(task,error=type(exc).__name__+':'+str(exc)[:180]));out.append(dict(task,status='DEFERRED_GAP'))
  putj(d,report,'FinMind_request_ledger.json',recent+[{'at':time.time(),'count':attempts}])
  putj(d,report,'FinMind_gap_checkpoint.json',{'completed':completed,'failed':failed,'attempts':attempts,'last_update_utc':stamp()})
  if stop:break
  time.sleep(.3)
 result={'pass':PASS,'finished_utc':stamp(),'token_present':bool(token),'api_requests':attempts,'requested_budget':available,'elapsed_seconds':round(time.time()-start,2),'planned_explicit_financial_tasks':len(work),'already_existing_finmind_company_dataset_quarters':len(covered),'saved_tasks':len(completed),'saved_rows':sum(x['rows'] for x in completed),'saved_bytes':sum(x['bytes'] for x in completed),'failed_tasks':len(failed),'not_requested':len(work)-len(out),'stop_reason':stop or ('BATCH_QUOTA_BUDGET' if len(out)<len(work) else 'FINITE_QUEUE_FINISHED'),'per_year':{str(y):{'official_summary':{k:v for k,v in z['summary'].items() if k!='remaining_core_units'},'finmind_saved':sum(x['year']==y for x in completed),'official_core_still_unfilled':len(z['summary']['remaining_core_units'])} for y,z in yearinfo.items()},'daily_gap_policy':'Explicit daily gaps retained; no automatic cross-source field merge without definition alignment','unknown_years':unknown,'full_market_complete':False,'numeric_verified':False,'pit_verified':False,'production_gate':'BLOCKED','completed':completed,'failed':failed,'remaining_financial_tasks':work[len(out):]}
 putj(d,report,'FINAL_THREE_YEAR_RESULT.json',result)
 text='# 2024–2026 官方優先查核與補抓結果\n\n'+f'完成時間：{result["finished_utc"]}。官方原始檔均維持不覆寫；新增檔已上傳並回讀 SHA-256。\n\n'
 text+='|年份|官方原有內容驗證單元|本輪官方補回單元|仍缺官方核心單元|FinMind本輪補回公司報表季度|\n|---|---:|---:|---:|---:|\n'
 for y,z in result['per_year'].items():
  c=z['official_summary']['core_counts'];text+=f'|{y}|{c.get("EXISTING_PAYLOAD_VERIFIED",0)}|{c.get("REPAIRED_REMOTE_READBACK_VERIFIED",0)}|{z["official_core_still_unfilled"]}|{z["finmind_saved"]}|\n'
 text+=f'\nFinMind本輪請求 {attempts} 次，成功保存 {len(completed)} 配對、失敗 {len(failed)}，尚有 {result["not_requested"]} 配對未請求；停止原因 {result["stop_reason"]}。完整缺漏見 JSON 及逐年資料夾。\n\n財報只驗證明確公司、報告期與部分數值存在，不代表整張財報完整。官方表格單元取得率不等於股票/欄位完整率。數值跨來源、公告PIT及歷史普通股名單尚未驗收；production_gate=BLOCKED。2026年未發布的月份/季別不算缺漏。\n'
 d.put(report,'RESULT.md',text.encode(),'text/markdown',overwrite=True)
 print(json.dumps({k:v for k,v in result.items() if k not in ('remaining_financial_tasks','completed','failed')},ensure_ascii=False),flush=True)

if __name__=='__main__':main()
