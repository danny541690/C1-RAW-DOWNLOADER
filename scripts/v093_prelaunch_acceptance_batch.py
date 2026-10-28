"""Read-only combined acceptance batch. Missing evidence stays open for next round."""
import argparse,collections,csv,datetime,gzip,hashlib,io,json,re,zipfile
from pathlib import Path
from decimal import Decimal
VERSION='PRELAUNCH_COMBINED_V3_DATED_ESB_RAW_ONLY'
def sha(b):return hashlib.sha256(b).hexdigest()
def inspect_raw(b,r,esb_evidence=None):
 s=r['來源'];cat=r['資料集']
 if s=='MOPS' and cat in ('BalanceSheet','IncomeStatement','CashflowStatement'):
  from scripts.v093_stage06_financial_repair import structure,number,text
  unit=dict(source=s,market='UNKNOWN',dataset=cat,security_id='ALL_MARKET',period_start=r['期間'],period_end=r['期間'],native_unit_id=r['單元ID'])
  m=structure(b,unit);cells=[[number(text(c)) for c in row] for row in m['cells']]
  missing=set(json.loads(r['預期代碼'] or '[]'))-set(m['codes'])
  if missing:raise ValueError('EXPECTED_COMPANIES_MISSING')
  ev=dict(companies=len(m['codes']),accounts=len(cells),numeric_cells=sum(c is not None for row in cells for c in row),native_unit=m['unit'])
  if cat=='BalanceSheet':
   aliases={'assets':('資產總額','資產總計'),'liabilities':('負債總額','負債總計'),'equity':('權益總額','權益總計')}
   mapping={k:[i for i,label in enumerate(m['labels']) if label in labels] for k,labels in aliases.items()};checks=[]
   for ci,code in enumerate(m['codes']):
    vals={k:[(i,cells[i][ci]) for i in ids if cells[i][ci] is not None] for k,ids in mapping.items()}
    if not all(len(v)==1 for v in vals.values()):checks.append(dict(code=code,result='UNKNOWN_TOTAL_MAPPING'));continue
    delta=Decimal(vals['assets'][0][1])-Decimal(vals['liabilities'][0][1])-Decimal(vals['equity'][0][1])
    checks.append(dict(code=code,result='PASS_EXACT' if delta==0 else 'REVIEW_DELTA',delta=str(delta),rows={k:v[0][0] for k,v in vals.items()}))
   ev['balance_identity']=checks
  return ev
 if s=='TPEx' and cat=='prices' and (r.get('原件參照','').endswith('.csv') or not b.lstrip().startswith((b'{',b'['))):
  from scripts.v093_standard_r4 import decode,csv_header_date,day
  from scripts.v093_official_content_audit import audit_json
  text,encoding=decode(b);grid=list(csv.reader(io.StringIO(text)))
  hi=next((i for i,row in enumerate(grid) if '代號' in row),None)
  if hi is None:raise ValueError('CSV_HEADER_MISSING')
  dates={day(x) for x in re.findall(r'(?<!\d)(20\d{6})(?!\d)',r['原件參照'])}-{None}
  filename_day=next(iter(dates)) if len(dates)==1 else None
  content_day=csv_header_date(s,grid,hi,filename_day)
  if not content_day or content_day!=r['期間']:raise ValueError('CSV_CONTENT_PERIOD_NOT_CONFIRMED')
  fields=grid[hi];data=[];metadata=[];managed=set();section='GENERAL';ci=fields.index('代號')
  for index,row in enumerate(grid[hi+1:],hi+1):
   if not any(str(v).strip() for v in row):continue
   if row==fields:
    metadata.append(dict(row_index=index,cells=row))
   elif len(row)==len(fields):
    data.append(row)
    if section=='MANAGED':managed.add(row[ci].strip())
   elif row==['管理股票']:
    section='MANAGED';metadata.append(dict(row_index=index,cells=row))
   elif (len(row)==1 and row[0].startswith(('註：','註:'))) or (len(row)==3 and row[0] in ('上櫃家數','總成交金額','總成交股數','總成交筆數') and row[2]==''):
    metadata.append(dict(row_index=index,cells=row))
   else:raise ValueError('CSV_UNRECOGNIZED_NON_DATA_ROW')
  scope=sorted({row[ci].strip() for row in data if re.fullmatch('[1-9][0-9]{3}',row[ci].strip())}-managed)
  ev=audit_json(json.dumps(dict(fields=fields,data=data)).encode(),dict(source=s,category=cat,applicable_security_codes=scope))
  if managed:ev['unverified']=sorted(set(ev['unverified'])|{'MANAGED_STOCK_PRICE_SEMANTICS_NOT_PROVEN'})
  ev.update(actual_date=content_day,date_proof='CSV_HEADER',encoding=encoding,csv_metadata_rows=metadata,managed_codes_not_ohlc_certified=sorted(managed));return ev
 if s in ('MOPS','TWSE','TPEx'):

  from scripts.v093_official_content_audit import audit_rows
  return audit_rows(b,dict(source=s,category=cat))
 if s=='TAIFEX':
  from scripts.v093_taifex_independent import validate
  if cat!='futDataDown' or not zipfile.is_zipfile(io.BytesIO(b)):raise ValueError('UNMAPPED_TAIFEX_DATASET')
  y=r['期間'][:4];return validate(b,dict(kind='annual',start=y+'-01-01',end=y+'-12-31'))
 if s=='TDCC':
  from scripts.v093_tdcc_independent import validate_history
  return dict(rows=validate_history(b,r['期間'].replace('-',''),r['代碼']))
 if s=='FinMind' and r.get('原件參照','').endswith('.jsonl'):
  records=[json.loads(line) for line in b.decode('utf-8-sig').splitlines() if line.strip()]
  if not records or any(not isinstance(x,dict) or set(x)!={'parent_row_index','source_record'} or isinstance(x['parent_row_index'],bool) or not isinstance(x['parent_row_index'],int) or x['parent_row_index']<0 or not isinstance(x['source_record'],dict) for x in records):raise ValueError('INVALID_FINMIND_NATIVE_PARTITION')
  obj=dict(status=200,data=[x['source_record'] for x in records],retained_representation='NATIVE_MONTH_PARTITION')
 else:obj=json.loads(b)
 if not isinstance(obj,dict):raise ValueError('EXPECTED_SOURCE_OBJECT')
 if s=='NDC':
  if obj.get('source')!='NDC' or obj.get('month')!=r['月份'] or not obj.get('tables'):raise ValueError('NDC_PERIOD_OR_TABLES')
  return dict(tables=len(obj['tables']),gaps=obj.get('gaps'),source_archive=obj.get('source_archive'),validation='MONTH_ENVELOPE_ONLY_NOT_SOURCE_XLSX_RECHECK')
 if s!='FinMind' or cat!='TaiwanStockPrice':raise ValueError('UNMAPPED_DATASET')
 if 'rows' in obj:
  if obj.get('status')!='RAW_MONTH_SLICE_NOT_PIT_VERIFIED' or obj.get('dataset')!=cat or obj.get('stock_id')!=r['代碼'] or not re.fullmatch('[0-9a-f]{64}',str(obj.get('response_sha256',''))) or obj.get('data'):raise ValueError('INVALID_FINMIND_SLICE_PROVENANCE')
  obj=dict(status=200,data=obj['rows'],retained_representation='MONTH_SLICE_WITH_UNVERIFIED_PARENT_SHA')
 rows=obj.get('data');seen=set();esb_rows=[]
 if obj.get('status')!=200 or not isinstance(rows,list) or not rows:raise ValueError('FINMIND_EMPTY_OR_ERROR')
 for x in rows:
  if x.get('stock_id')!=r['代碼'] or not str(x.get('date','')).startswith(r['月份']):raise ValueError('FINMIND_PERIOD_CODE')
  datetime.date.fromisoformat(x['date'])
  key=(x['date'],x['stock_id'])
  if key in seen:raise ValueError('DUPLICATE_KEY')
  seen.add(key);v={k:Decimal(str(x[k])) for k in ('open','max','min','close')}
  if not all(n.is_finite() for n in v.values()):raise ValueError('NONFINITE_PRICE')
  if esb_evidence and key in esb_evidence:
   from scripts.v093_esb_market_evidence import compare_row
   esb_rows.append(compare_row(x,esb_evidence[key]))
   if not v['min']<=v['close']<=v['max']:raise ValueError('ESB_LAST_TRADE_RELATIONSHIP')
  elif not v['min']<=v['open']<=v['max'] or not v['min']<=v['close']<=v['max']:raise ValueError('OHLC_RELATIONSHIP')
 return dict(rows=len(rows),ohlc_rows_checked=len(rows)-len(esb_rows),esb_raw_only_rows=esb_rows,analysis_release_approved=False,representation=obj.get('retained_representation','NATIVE_API_RESPONSE'),parent_response_sha_readback_verified=False)
def retained_raw(cache,ref,archives):
 fid,sep,member=ref.partition('/')
 if not re.fullmatch(r'[A-Za-z0-9_-]+',fid):raise ValueError('UNSAFE_CACHE_ID')
 path=cache/fid
 if not path.is_file():return None,None
 if fid not in archives:
  raw=path.read_bytes()
  if zipfile.is_zipfile(io.BytesIO(raw)):
   with zipfile.ZipFile(io.BytesIO(raw)) as z:
    if sum(i.file_size for i in z.infolist())>1_500_000_000:raise ValueError('EXPANSION_LIMIT')
    if z.testzip() is not None:raise ValueError('CRC_FAILURE')
  archives[fid]=(raw,sha(raw))
 raw,archive_sha=archives[fid]
 if sep:
  with zipfile.ZipFile(io.BytesIO(raw)) as z:raw=z.read(member)
 return raw,archive_sha
def run(register,cache,out,resume=None,esb_dir=None):
 if not register.is_dir() or not list(register.glob('*_units.csv.gz')):raise ValueError('REGISTER_INPUT_MISSING')
 out.mkdir(parents=True,exist_ok=True)
 from scripts.v093_esb_market_evidence import load_evidence
 esb_evidence=load_evidence(esb_dir) if esb_dir else {}
 signature=sha(b''.join(p.read_bytes() for p in sorted(Path(__file__).parent.glob('*.py')))+json.dumps(sorted(esb_evidence.items()),sort_keys=True,default=str).encode())
 old=json.loads(resume.read_text()) if resume and resume.is_file() else {};prior=old.get('completed',{}) if old.get('signature')==signature else {}
 counts=collections.Counter();sources={};archives={};completed={};evidence=[];manifest={}
 cols=('task_key','source','dataset','year','month','period','raw_reference','raw_sha256','status','next_action')
 with gzip.open(out/'next_round.csv.gz','wt',encoding='utf-8-sig',newline='') as stream:
  writer=csv.DictWriter(stream,fieldnames=cols);writer.writeheader()
  for p in sorted(register.glob('*_units.csv.gz')):
   manifest[p.name]=sha(p.read_bytes())
   with gzip.open(p,'rt',encoding='utf-8-sig',newline='') as f:
    for r in csv.DictReader(f):
     s=r['來源'];c=sources.setdefault(s,collections.Counter());c['units']+=1;counts['units']+=1;key=s+'|'+r['單元ID'];ref=r['原件參照']
     status='RECONCILE_FROZEN_MISSING';action='先對帳最新收據與核准母體，再決定是否下載'
     if r['已下載']=='1':
      counts['registered_retained_units']+=1
      try:
       b,archive_sha=retained_raw(cache,ref,archives)
       if b is None:status='RAW_NOT_IN_LOCAL_CACHE';action='讀回既有原件，勿直接重下載來源'
       else:
        actual=sha(b)
        if actual!=r['RAW_SHA256']:raise ValueError('RAW_SHA_MISMATCH')
        token=sha((key+actual+archive_sha).encode());ev=prior.get(token)
        if ev:counts['resumed_content_units']+=1
        else:
         ev=dict(task_key=key,source=s,dataset=r['資料集'],period=r['期間'],raw_reference=ref,raw_sha256=actual,archive_sha256=archive_sha,content=inspect_raw(b,r,esb_evidence),result='PARTIAL_CONTENT_NOT_RELEASED');counts['new_content_units']+=1
        completed[token]=ev;evidence.append(ev);c['content_evidence_units']+=1;status='REMAINING_RULES_OPEN';action='補母體、契約、完整數值與PIT等適用證據'
      except Exception as e:status='CONTENT_BLOCKED';action=type(e).__name__+':'+str(e)[:240];c['content_blocked_units']+=1
     if status=='REMAINING_RULES_OPEN' and ev.get('content',{}).get('esb_raw_only_rows'):
      status='ESB_RAW_ONLY_RULES_OPEN';action='興櫃原件保留；開盤語意、末筆價及PIT未全驗，不進正式分析'
     counts[status]+=1
     writer.writerow(dict(task_key=key,source=s,dataset=r['資料集'],year=r['年份'],month=r['月份'],period=r['期間'],raw_reference=ref,raw_sha256=r['RAW_SHA256'],status=status,next_action=action))
 from scripts.v093_layer02_governance import gate_release,GateBlocked
 try:gate_release({'kind':'APPROVED_STANDARD','qa':{}});gate='UNEXPECTED_PASS'
 except GateBlocked as e:gate=str(e)
 names=('母體與全量原件','歷史證券日期主鍵','欄位單位契約','完整數值覆蓋','獨立跨來源比對','公告PIT與版本','真實發布與下游','全量復原與時效')
 summary=dict(version=VERSION,checked_at_taipei=datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat(),register_snapshot='INPUT_REGISTER_SET_NOT_APPROVED_UNIVERSE',register_sha256=manifest,validator_signature=signature,counts=dict(counts),sources={s:dict(c) for s,c in sources.items()},groups=[dict(id='R%02d'%(i+1),name=n,result='PARTIAL' if i in (0,1,3) else 'BLOCKED' if i==6 else 'UNKNOWN') for i,n in enumerate(names)],release_gate=gate,approved_scopes=[],source_downloads=0,production_writes=0)
 for name,obj in [('summary.json',summary),('raw_content_evidence.json',evidence),('checkpoint.json',dict(signature=signature,completed=completed))]:(out/name).write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n')
 return summary
def main():
 p=argparse.ArgumentParser();p.add_argument('--register',required=True,type=Path);p.add_argument('--raw-cache',required=True,type=Path);p.add_argument('--out',required=True,type=Path);p.add_argument('--resume',type=Path);p.add_argument('--esb-evidence',type=Path);a=p.parse_args();print(json.dumps(run(a.register,a.raw_cache,a.out,a.resume,a.esb_evidence)['counts'],ensure_ascii=False))
if __name__=='__main__':main()
