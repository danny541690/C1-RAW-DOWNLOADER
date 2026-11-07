"""v0.95 October three-source REAL Bronze→Silver→Gold descriptive batch.
Only three explicitly verified October candidate source files; fails closed per partition.
No retrospective PIT certification; no historical backtest or 443 full completion claim.\nV2 writes content-addressed immutable partitions; it does not overwrite earlier candidates.\nNever embed the current run date in deterministic Parquet rows.
"""
import os,io,json,csv,zipfile,re,hashlib,pathlib,datetime as dt,collections
import pyarrow as pa,pyarrow.parquet as pq
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload

ROOT=pathlib.Path("ultimate_r1");ROOT.mkdir(exist_ok=True)
CANDIDATES={
 "TWSE_VALUATION":("TWSE","1IGvKIy9aZGkQ_15xHzKu1PyiSRW-U_Q8","1I83nUMJjBEYJrUDj9zUDCvl4nfKEDvjE","1ick4kRSlmz1ukibDq3TOD7QQxiBHtzWb"),
 "TPEX_INDICES":("TPEx","1Io5ls3bton2CGF79FdMqMGX25GD0reLN","15hlfRj8gTXsPpbRBZBxvRJrgTtZQT-IG","1_KDD5xM9IeyBLSfDRppnrjAYQTEnGPRz"),
 "TAIFEX_PCR":("TAIFEX","10_sQcRvkMjemilqM3kKzZS1DinLtmAsq","1p5pXKgk3iN1ECvGdMosFP0eixvAVfIiz","1TmZXrdW2sqOmgoMHgK7W2ifyTjz4UFH8"),
}
GOLD_PARENT="1XT_54SXjGDksTz6PAdwhsVA8czZ1FTE3"
RUN=os.getenv("GITHUB_RUN_ID","local")
def sha(b):return hashlib.sha256(b).hexdigest()
def number(x):
 v=str(x).strip().replace(",","").replace("−","-").replace("－","-")
 if not re.fullmatch(r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)",v):return None
 try:return float(v)
 except ValueError:return None
def api():
 c=Credentials(token=None,refresh_token=os.environ["GOOGLE_REFRESH_TOKEN"],client_id=os.environ["GOOGLE_CLIENT_ID"],client_secret=os.environ["GOOGLE_CLIENT_SECRET"],token_uri="https://oauth2.googleapis.com/token",scopes=["https://www.googleapis.com/auth/drive"])
 c.refresh(Request());return build("drive","v3",credentials=c,cache_discovery=False)
def read(s,fid):return s.files().get_media(fileId=fid).execute()
def children(s,parent):
 out=[];page=None
 while True:
  a=s.files().list(q="'"+parent+"' in parents and trashed=false",fields="nextPageToken,files(id,name,mimeType,size)",pageSize=1000,pageToken=page).execute()
  out+=a.get("files",[]);page=a.get("nextPageToken")
  if not page:return out
def ensurefolder(s,parent,name):
 found=[x for x in children(s,parent) if x["name"]==name]
 if len(found)>1:raise ValueError("DUPLICATE_FOLDER_"+name)
 if found:
  if found[0]["mimeType"]!="application/vnd.google-apps.folder":raise ValueError("NAME_OCCUPIED")
  return found[0]["id"]
 return s.files().create(body={"name":name,"parents":[parent],"mimeType":"application/vnd.google-apps.folder"},fields="id").execute()["id"]
def immutable(s,parent,name,b):
 found=[x for x in children(s,parent) if x["name"]==name]
 if len(found)>1:raise ValueError("AMBIGUOUS_DUPLICATE_FILE_"+name)
 digest=sha(b)
 if found:
  fid=found[0]["id"]
  if sha(read(s,fid))!=digest:raise ValueError("IMMUTABLE_OUTPUT_CONFLICT_"+name)
  return fid,"REUSED"
 fid=s.files().create(body={"name":name,"parents":[parent]},media_body=MediaIoBaseUpload(io.BytesIO(b),mimetype="application/octet-stream",resumable=True),fields="id").execute()["id"]
 if sha(read(s,fid))!=digest:raise ValueError("UPLOAD_READBACK_SHA_MISMATCH_"+name)
 return fid,"CREATED"
def load_candidate(blob,lane):
 if lane=="TAIFEX_PCR":
  text=None
  for enc in ("utf-8-sig","cp950"):
   try:text=blob.decode(enc);break
   except UnicodeError:continue
  if text is None:raise ValueError("TAIFEX_CSV_ENCODING")
  rows=list(csv.reader(io.StringIO(text)))
  if len(rows)<2:raise ValueError("TAIFEX_EMPTY")
  expected=["日期","賣權成交量","買權成交量","買賣權成交量比率%","賣權未平倉量","買權未平倉量","買賣權未平倉量比率%"]
  if rows[0][:7]!=expected:raise ValueError("TAIFEX_SCHEMA_UNEXPECTED")
  parsed=[];dates=set()
  for row in rows[1:]:
   if not row or not row[0].strip():continue
   if len(row)<7:raise ValueError("TAIFEX_ROW_WIDTH")
   day=dt.datetime.strptime(row[0],"%Y/%m/%d").date()
   if day.strftime("%Y-%m")!="2026-10" or day in dates:raise ValueError("TAIFEX_DATE_OR_DUPLICATE")
   dates.add(day)
   vals=[number(z) for z in row[1:7]]
   if any(z is None for z in vals) or vals[1]<=0 or vals[4]<=0:raise ValueError("TAIFEX_NUMERIC")
   if abs(100*vals[0]/vals[1]-vals[2])>0.04:raise ValueError("TAIFEX_VOLUME_RATIO_NOT_CONSISTENT")
   if abs(100*vals[3]/vals[4]-vals[5])>0.04:raise ValueError("TAIFEX_OI_RATIO_NOT_CONSISTENT")
   parsed.append(dict(trade_date=day,market="TAIFEX",put_volume=int(vals[0]),call_volume=int(vals[1]),put_call_volume_ratio_pct=vals[2],
    put_open_interest=int(vals[3]),call_open_interest=int(vals[4]),put_call_oi_ratio_pct=vals[5]))
  if not parsed:raise ValueError("NO_TAIFEX_RECORDS")
  return parsed,{"source_category":"PCR","observations":len(parsed),"dates":[min(dates).isoformat(),max(dates).isoformat()]}
 with zipfile.ZipFile(io.BytesIO(blob)) as z:
  if z.testzip() is not None:raise ValueError("ZIP_CRC")
  manifest=json.loads(z.read("manifest.json"))
  units=manifest.get("units") or []
  if len(units)!=1:raise ValueError("NOT_ONE_NATIVE_UNIT")
  u=units[0]
  target="valuation_2026-10-19.json" if lane=="TWSE_VALUATION" else "indices_2026-10-19.json"
  if target not in z.namelist():raise ValueError("NATIVE_MEMBER_MISSING")
  b=z.read(target)
  if sha(b)!=u.get("sha256"):raise ValueError("ORIGINAL_MEMBER_SHA_MISMATCH")
  obj=json.loads(b)
  if obj.get("date")!="20261019":raise ValueError("OBJECT_DATE_MISMATCH")
  day=dt.date(2026,10,19)
  if lane=="TWSE_VALUATION":
   expected=["證券代號","證券名稱","收盤價","殖利率(%)","股利年度","本益比","股價淨值比","財報年/季"]
   if obj.get("fields")!=expected:raise ValueError("TWSE_VALUATION_FIELDS_CHANGED")
   data=obj.get("data") or [];rows=[];seen=set()
   for raw in data:
    if len(raw)!=len(expected):raise ValueError("TWSE_WIDTH_MISMATCH")
    code=str(raw[0]).strip()
    if not re.fullmatch(r"\d{4}",code):continue
    if code in seen:raise ValueError("TWSE_DUPLICATE_CODE")
    seen.add(code)
    row=dict(trade_date=day,stock_id=code,market="TSE",company_name=str(raw[1]),close_price_ntd=number(raw[2]),
     dividend_yield_pct=number(raw[3]),dividend_year=str(raw[4]),pe_ratio=number(raw[5]),pb_ratio=number(raw[6]),reported_financial_period=str(raw[7]))
    rows.append(row)
   if len(rows)<100:raise ValueError("TWSE_SUSPICIOUSLY_FEW")
  else:
   data=[];rows=[];seen=set()
   for table in obj.get("tables",[]):
    fields=table.get("fields") or []
    if not all(x in fields for x in ("指數","收市指數","漲跌","漲跌幅度(%)")):continue
    idx=[fields.index(x) for x in ("指數","收市指數","漲跌","漲跌幅度(%)")]
    for raw in table.get("data",[]):
     if len(raw)!=len(fields):raise ValueError("TPEX_WIDTH_MISMATCH")
     name=str(raw[idx[0]]).strip();key=(table.get("title"),name)
     if not name or key in seen:raise ValueError("TPEX_DUPLICATE_INDEX")
     seen.add(key)
     rows.append(dict(trade_date=day,market="OTC",index_name=name,table_name=str(table.get("title")),
      close_index=number(raw[idx[1]]),index_change=number(raw[idx[2]]),index_change_pct=number(raw[idx[3]])))
   if len(rows)<10:raise ValueError("TPEX_TOO_FEW_INDICES")
  return rows,{"source_category":u.get("category"),"observations":len(rows),"native_sha256":sha(b),"source_url":u.get("url")}
def asbytes(rows):
 stream=io.BytesIO();pq.write_table(pa.Table.from_pylist(rows),stream,compression="zstd")
 b=stream.getvalue()
 if pq.read_metadata(io.BytesIO(b)).num_rows!=len(rows):raise ValueError("SILVER_ROWCOUNT_MISMATCH")
 return b
def execute():
 s=api();report={"schema":"JARVIS_V095_ULTIMATE_R1_REAL_OCT_BSG_CANARY","run_id":RUN,"period":"2026-10","results":{},"errors":{},
  "pit_certified":False,"all_443_gold_complete":False,"historical_backtest_allowed":False}
 for lane,(source,candidate,bronze_parent,silver_parent) in CANDIDATES.items():
  try:
   blob=read(s,candidate);digest=sha(blob)
   rows,meta=load_candidate(blob,lane)
   bronze_month=ensurefolder(s,bronze_parent,"2026-10")
   original_name="V095_BRONZE_V093_202610_"+lane+"_"+digest[:20]+(".csv" if lane=="TAIFEX_PCR" else ".zip")
   bronze_id,bronze_action=immutable(s,bronze_month,original_name,blob)
   stamped=[]
   for row in rows:
    row.update(bronze_file_id=bronze_id,bronze_sha256=digest,v093_staging_file_id=candidate,
     source_observation_month="2026-10",
     source_period="2026-10",historical_pit_verified=False)
    stamped.append(row)
   silver_parent_month=ensurefolder(s,silver_parent,"2026-10_CANDIDATE")
   # stable metadata for reproducibility; no run ID in Parquet and time stamped only to date.
   silver_bytes=asbytes(stamped)
   silver_name="JARVIS_V095_202610_"+lane+"_SILVER_V2_"+sha(silver_bytes)[:20]+".parquet"
   silver_id,silver_action=immutable(s,silver_parent_month,silver_name,silver_bytes)
   # Gold descriptive: only formula-verified copies of direct source values; no fitted strategy signals.
   # Source-native PE/PB/dividend yield and index ratios are descriptive; not historical PIT.
   if lane=="TWSE_VALUATION":
    keys=("trade_date","stock_id","market","close_price_ntd","pe_ratio","pb_ratio","dividend_yield_pct")
   elif lane=="TPEX_INDICES":
    keys=("trade_date","market","index_name","close_index","index_change","index_change_pct")
   else:
    keys=("trade_date","market","put_call_volume_ratio_pct","put_call_oi_ratio_pct")
   features=[]
   for row in stamped:
    r={k:row[k] for k in keys};r.update(silver_sha256=sha(silver_bytes),silver_file_id=silver_id,
     bronze_sha256=digest,bronze_file_id=bronze_id,historical_pit_verified=False,usage="DESCRIPTIVE_ONLY_NOT_PIT")
    features.append(r)
   gold_month=ensurefolder(s,GOLD_PARENT,"2026-10_DESCRIPTIVE_ONLY")
   gold_bytes=asbytes(features)
   gold_name="JARVIS_V095_202610_"+lane+"_GOLD_DESCRIPTIVE_V2_"+sha(gold_bytes)[:20]+".parquet"
   gold_id,gold_action=immutable(s,gold_month,gold_name,gold_bytes)
   report["results"][lane]={"source":source,"rows":len(rows),"source_meta":meta,"bronze_id":bronze_id,
    "bronze_sha256":digest,"silver_id":silver_id,"silver_sha256":sha(silver_bytes),
    "gold_id":gold_id,"gold_sha256":sha(gold_bytes),"actions":{"bronze":bronze_action,"silver":silver_action,"gold":gold_action},
    "lineage":"GOLD_SILVER_BRONZE_SHA_INCLUDED","pit":"UNVERIFIED","usage":"DESCRIPTIVE_ONLY",
    "v2_content_addressed":True,"prior_candidate_not_overwritten":True}
  except Exception as e:
   report["errors"][lane]={"type":type(e).__name__,"message":str(e)[:250],"status":"QUARANTINED_NO_FAKE_PASS"}
  (ROOT/"october_bronze_silver_gold_receipt.json").write_text(json.dumps(report,ensure_ascii=False,indent=2))
 print(json.dumps({"run_id":RUN,"source_partitions_completed":len(report["results"]),"source_partitions_failed":len(report["errors"]),
  "rows":{k:v["rows"] for k,v in report["results"].items()},
  "drive_ids":{k:{"bronze":v["bronze_id"],"silver":v["silver_id"],"gold":v["gold_id"]} for k,v in report["results"].items()},
  "errors":report["errors"],"pit":False},ensure_ascii=False),flush=True)
 if report["errors"]:raise SystemExit("PARTIAL_SOURCE_FAILURE_QA_RECORDED")
if __name__=="__main__":execute()
