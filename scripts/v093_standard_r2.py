"""C1 0.93 layer 02 R2: source table staging with date checks, native fields and lineage.
Outputs STAGING Parquet, never a certified Golden Copy. RAW is immutable.
"""
import argparse,collections,csv,datetime,hashlib,io,json,re,zipfile
from html.parser import HTMLParser
import pyarrow as pa,pyarrow.parquet as pq
from scripts.v093_standard_r1 import Drive,service,ROOT,C1,folder,ls,LIMIT_ARCHIVE,LIMIT_MEMBER,MAX_ZIP_UNCOMPRESSED
SOURCES=("TWSE","TPEx","MOPS","FinMind")
def normalize_date(s):
 s=str(s or "").strip()
 m=re.fullmatch(r"(20\d\d)(\d\d)(\d\d)",s)
 if m:return "-".join(m.groups())
 m=re.fullmatch(r"(20\d\d)[/-](\d\d)[/-](\d\d)",s)
 if m:return "-".join(m.groups())
 m=re.fullmatch(r"(1\d\d)[/-]?(\d\d)[/-]?(\d\d)",s)
 if m:return f"{int(m.group(1))+1911}-{m.group(2)}-{m.group(3)}"
 return None
def period_date(s):
 m=re.fullmatch(r"(20\d\d)[/-]?(\d\d)",str(s or "").strip())
 if m:return m.group(1)+"-"+m.group(2)
 m=re.fullmatch(r"(1\d\d)[/-]?(\d\d)",str(s or "").strip())
 if m:return str(int(m.group(1))+1911)+"-"+m.group(2)
 return None
def num(s):
 if isinstance(s,bool):return None
 if isinstance(s,(int,float)):return float(s)
 if not isinstance(s,str):return None
 s=s.replace(",","").strip()
 if not re.fullmatch(r"[-+]?\d+(?:\.\d+)?",s):return None
 try:return float(s)
 except: return None
def decode(b):
 for enc in ("utf-8-sig","cp950"):
  try:return b.decode(enc),enc
  except UnicodeDecodeError:continue
 raise ValueError("UNKNOWN_ENCODING")
def source_date(name,obj=None):
 if isinstance(obj,dict):
  for k in ("date","Date","trade_date","資料日期"):
   d=normalize_date(obj.get(k))
   if d:return d,"RESPONSE"
 m=re.search(r"(?<!\d)(20(?:25|26)[01]\d[0-3]\d)(?!\d)",name)
 if m:return normalize_date(m.group(1)),"FILENAME_ONLY"
 return None,"NONE"
def rows_to_long(source,archive,member,period,records):
 out=[];invalid=0
 for t,idx,day,proof,symbol,values in records:
  if not day or day[:7]!=period or not symbol or not re.fullmatch(r"[0-9A-Za-z]{4,8}",symbol):invalid+=1;continue
  if not isinstance(values,dict):continue
  for col,val in values.items():
   nv=num(val)
   if nv is None or str(col).split("__col_")[0] in ("股票代號","證券代號","代號","公司代號","stock_id","Code","StockCode","SecuritiesCompanyCode"):continue
   out.append({"date":day,"stock_id":symbol,"source":source,"native_archive":archive,"native_member":member,
     "native_table":t,"row_index":idx,"date_proof":proof,"native_field":str(col)[:130],
     "raw_value":str(val)[:130],"numeric_unscaled":nv,"unit_verified":False,
     "numeric_verified":False,"pit_verified":False,"status":"STAGING_UNMAPPED"})
 return out,invalid
def parse_json(source,archive,member,obj,period):
 records=[];date,proof=source_date(member,obj)
 def add(tab,rs,fields=None):
  if not isinstance(rs,list):return
  for i,row in enumerate(rs):
   if isinstance(row,dict):
    values=row
   elif isinstance(row,list) and isinstance(fields,list) and len(row)==len(fields):
    # Preserve duplicate source columns with positional suffix; no silent overwrite
    values={f"{field}__col_{j:02d}":row[j] for j,field in enumerate(fields)}
   else:continue
   if "source_record" in values and isinstance(values["source_record"],dict):values=values["source_record"]
   symbol=next((str(values[k]).strip() for k in ("stock_id","SecuritiesCompanyCode","股票代號","證券代號","代號","公司代號","Code","StockCode") if k in values and values[k]),None)
   if not symbol and isinstance(fields,list) and isinstance(row,list):
    col=next((j for j,f in enumerate(fields) if f in ("股票代號","證券代號","代號","公司代號")),None)
    if col is not None:symbol=str(row[col]).strip()
   # TPEx ex-dividend tables use ROC dates per event, which can differ
   # from the query/response date. Never substitute the query date for event date.
   event_date=None
   if source=="TPEx" and isinstance(fields,list) and isinstance(row,list):
    event_idx=next((j for j,f in enumerate(fields) if f=="除權息日期"),None)
    if event_idx is not None and event_idx<len(row):
     event_date=normalize_date(row[event_idx])
     if event_date is None:continue
   rd=event_date or next((normalize_date(values[k]) for k in ("date","Date","trade_date","資料日期") if k in values and normalize_date(values[k])),None)
   day=rd or date
   date_origin="TPEx_EVENT_ROC_DATE" if event_date else "ROW" if rd else proof
   # Documented date field must not contradict row date.
   if date and rd and date!=rd and not event_date:continue
   records.append((tab,i,day,date_origin,symbol,values))
 if isinstance(obj,list):add("records",obj)
 if isinstance(obj,dict):
  add("data",obj.get("data"),obj.get("fields"))
  # FinMind annual-batch archives store dated per-stock records under rows, not data.
  # Keep original row dates and stock_id; do not synthesize either from the filename.
  if not isinstance(obj.get("data"),list):add("rows",obj.get("rows"),obj.get("fields"))
  add("aaData",obj.get("aaData"),obj.get("fields"))
  for j,t in enumerate(obj.get("tables") or []):
   if not isinstance(t,dict):continue
   # A table may carry separate ROC date
   td=normalize_date(t.get("date"))
   if td and date and td!=date:continue
   add("table_"+str(j)+":"+str(t.get("title",""))[:75],t.get("data"),t.get("fields"))
 return rows_to_long(source,archive,member,period,records)
def classify_mops_html(text):
 """Classify financial HTML without inventing stock IDs, periods, or PIT."""
 class Probe(HTMLParser):
  def __init__(self):
   super().__init__();self.tables=0;self.rows=0;self.cells=0;self.text=[]
  def handle_starttag(self,tag,attrs):
   if tag=="table":self.tables+=1
   if tag=="tr":self.rows+=1
   if tag in ("td","th"):self.cells+=1
  def handle_data(self,data):
   value=re.sub(r"\\s+"," ",data).strip()
   if value and len(self.text)<500:self.text.append(value)
 p=Probe();p.feed(text)
 combined=" ".join(p.text)
 financial=any(x in combined for x in ("資產總額","負債總額","現金及約當現金","綜合損益","營業利益"))
 revenue="營業收入" in combined or "當月營收" in combined
 return {"kind":"FINANCIAL_STATEMENT_MATRIX" if financial else "REVENUE_TABLE_CANDIDATE" if revenue else "UNKNOWN_HTML","tables":p.tables,"rows":p.rows,"cells":p.cells,"unit_hint":"NTD_THOUSANDS_UNVERIFIED" if "新台幣仟元" in combined else "UNKNOWN","pit_verified":False,"stock_id_verified":False,"certified":False}

def parse(source,archive,member,b,period):
 s,encoding=decode(b)
 lower=member.lower()
 if lower.endswith(".jsonl"):
  o=[json.loads(line) for line in s.splitlines() if line.strip()]
  return parse_json(source,archive,member,o,period)+(encoding,)
 if lower.endswith(".json") or lower.endswith(".raw") and s.lstrip().startswith(("{","[")):
  o=json.loads(s)
  return parse_json(source,archive,member,o,period)+(encoding,)
 if lower.endswith(".csv") or lower.endswith(".raw") and not s.lstrip().startswith("<"):
  date,proof=source_date(member)
  reader=csv.reader(io.StringIO(s));header=None;records=[]
  for i,r in enumerate(reader):
   if not r:continue
   if header is None:
    if any(x.strip() in ("公司代號","證券代號","股票代號","代號") for x in r):
     header=[x.strip() for x in r]
    continue
   if len(r)!=len(header):continue
   vals={f"{k}__col_{j:02d}":x for j,(k,x) in enumerate(zip(header,r))}
   j=next((k for k,x in enumerate(header) if x in ("公司代號","證券代號","股票代號","代號")),None)
   if j is None:continue
   sid=r[j].strip()
   # Revenue is monthly period data, not the daily filename date
   if source=="MOPS":
    month_col=next((k for k,x in enumerate(header) if x=="資料年月"),None)
    q=period_date(r[month_col]) if month_col is not None else None
    if q!=period:continue
    date=period+"-01";proof="REPORTED_MONTH_NOT_PUBLISHED_DATE"
   records.append(("csv",i,date,proof,sid,vals))
  return rows_to_long(source,archive,member,period,records)+(encoding,)
 if source=="MOPS" and s.lstrip().startswith("<"):
  kind=classify_mops_html(s)["kind"]
  raise ValueError("MOPS_"+kind+"_REQUIRES_STOCK_ID_PERIOD_AND_PIT_METADATA")
 raise ValueError("HTML_NEEDS_DEDICATED_ADAPTER")
def run(year,month):
 d=Drive(service());period=f"{year}-{month:02d}";base=folder(d,ROOT,str(year))
 standard=folder(d,C1,"02_STANDARD",True);dest=folder(d,folder(d,standard,str(year),True),period,True);dest=folder(d,dest,"NATIVE_STAGING_R2",True)
 control=folder(d,folder(d,C1,"05_CONTROL",True),"STANDARD_QA",True)
 report={"period":period,"status":"STAGING_NOT_APPROVED","created_at":datetime.datetime.now(datetime.timezone.utc).isoformat(),"archives":[],"quality":{"PIT_PASS":False,"COVERAGE_PASS":False,"NUMERIC_PASS":False,"GOLDEN_COPY_PUBLISHED":False},"total_staged_cells":0,"total_unparsed_members":0}
 seen=set()
 for source in SOURCES:
  f=folder(d,folder(d,base,source),period)
  for zfile in sorted((x for x in ls(d,f) if x["name"].lower().endswith(".zip")),key=lambda x:x["name"]):
   arc={"source":source,"name":zfile["name"],"status":"PENDING","members":[]};report["archives"].append(arc)
   try:
    if int(zfile.get("size",0))>LIMIT_ARCHIVE:raise ValueError("ARCHIVE_SIZE_LIMIT")
    raw=d.call(lambda:d.api.files().get_media(fileId=zfile["id"]))
    sha=hashlib.sha256(raw).hexdigest();arc["raw_sha256"]=sha
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
     if z.testzip():raise ValueError("CRC_FAIL")
     if sum(i.file_size for i in z.infolist())>MAX_ZIP_UNCOMPRESSED:raise ValueError("EXPANSION_LIMIT")
     parts=[]
     for m in z.infolist():
      if m.is_dir():continue
      entry={"member":m.filename,"bytes":m.file_size,"status":"SKIPPED"};arc["members"].append(entry)
      if m.file_size>LIMIT_MEMBER:entry["status"]="OVERSIZE";report["total_unparsed_members"]+=1;continue
      if not m.filename.lower().endswith((".json",".raw",".jsonl",".csv")):continue
      if any(t in m.filename.lower() for t in ("manifest","receipt","checkpoint","metadata")):continue
      try:
       rows,invalid,enc=parse(source,zfile["name"],m.filename,z.read(m),period)
       # Prohibit duplicated raw and pre-parsed alias within same archive
       mh=hashlib.sha256(z.read(m)).hexdigest()
       entry.update({"status":"STAGED" if rows else "NO_DATED_STOCK_NUMERIC_ROWS","parsed_fields":len(rows),"invalid_rows":invalid,"encoding":enc,"member_sha256":mh})
       if rows:parts.extend(rows)
       else:report["total_unparsed_members"]+=1
      except Exception as e:
       entry.update({"status":"QUARANTINED","error":str(e)[:160]});report["total_unparsed_members"]+=1
     if parts:
      buf=io.BytesIO();pq.write_table(pa.Table.from_pylist(parts),buf,compression="zstd")
      name=source+"_"+sha[:18]+"_native_staging.parquet"
      d.put(dest,name,buf.getvalue(),"application/octet-stream",overwrite=False)
      arc["parquet_name"]=name;arc["staged_cells"]=len(parts);report["total_staged_cells"]+=len(parts)
    arc["status"]="ARCHIVE_READ_SUCCESS"
   except Exception as e:
    arc["status"]="ARCHIVE_ERROR";arc["error"]=str(e)[:200]
   print(json.dumps({"period":period,"source":source,"archive":arc["name"],"status":arc["status"],"cells":arc.get("staged_cells",0)},ensure_ascii=False),flush=True)
 fname=period+"_STANDARD_R2_AUDIT.json"
 d.put(control,fname,json.dumps(report,ensure_ascii=False,indent=2).encode(),"application/json",overwrite=True)
 print(json.dumps({"report":fname,"staged_cells":report["total_staged_cells"],"quarantined_or_unparsed":report["total_unparsed_members"],"status":report["status"]},ensure_ascii=False),flush=True)
if __name__=="__main__":
 p=argparse.ArgumentParser();p.add_argument("--year",type=int,required=True);p.add_argument("--month",type=int,required=True);a=p.parse_args();run(a.year,a.month)
