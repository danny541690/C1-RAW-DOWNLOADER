"""Repair 2026-09 TWSE P/E lost in original Silver schema inference, then Gold descriptive R2.
Only native exact column 5 本益比. Preserve all prior versions, source checksum and no historical PIT.
"""
import os,io,json,hashlib,decimal,re,pathlib,datetime
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
import pyarrow as pa,pyarrow.parquet as pq
D=decimal.Decimal
NATIVE_ID="1HxpjvcKCoh7J3H6BUDV0CRdI84wT-d4O"
SILVER_R1="1-yw7DxlsuNXXRjVRcwOfU5AjjhPqMwbq"
SILVER_FOLDER="13syLa0OLu8--8JLmMUsgC2_uwExDisS-"
GOLD_FOLDER="1FYIz-uylwZLM7HL-7MG2iH90BefMyXDw"
def sha(b):return hashlib.sha256(b).hexdigest()
def n(v):
 if v is None:return None
 s=str(v).strip().replace(",","")
 if not re.fullmatch(r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)",s):return None
 x=D(s);return x if x.is_finite() else None
def service():
 c=Credentials(token=None,refresh_token=os.environ["GOOGLE_REFRESH_TOKEN"],token_uri="https://oauth2.googleapis.com/token",client_id=os.environ["GOOGLE_CLIENT_ID"],client_secret=os.environ["GOOGLE_CLIENT_SECRET"],scopes=["https://www.googleapis.com/auth/drive"])
 c.refresh(Request());return build("drive","v3",credentials=c,cache_discovery=False)
def get(s,id):return s.files().get_media(fileId=id).execute()
def write(s,parent,name,b):
 files=s.files().list(q=f"'{parent}' in parents and name = '{name}' and trashed = false",fields="files(id)",pageSize=50).execute()["files"]
 if len(files)>1:raise ValueError("AMBIGUOUS_OUTPUT")
 if files:
  if sha(get(s,files[0]["id"]))!=sha(b):raise ValueError("GOLD_OUTPUT_ALREADY_EXISTS_WITH_OTHER_SHA")
  return files[0]["id"]
 id=s.files().create(body={"name":name,"parents":[parent]},media_body=MediaIoBaseUpload(io.BytesIO(b),mimetype="application/octet-stream",resumable=True),fields="id").execute()["id"]
 if sha(get(s,id))!=sha(b):raise ValueError("OUTPUT_SHA_READBACK")
 return id
def main():
 s=service()
 oldbytes=get(s,SILVER_R1);old=pq.read_table(io.BytesIO(oldbytes)).to_pylist()
 nativebytes=get(s,NATIVE_ID);source=pq.read_table(io.BytesIO(nativebytes)).to_pylist()
 if len(old)!=21620 or len(source)!=21620:raise ValueError("UNEXPECTED_INPUT_ROW_COUNTS")
 keyed={}
 for q in source:
  d=q["trade_date"];id=q["security_id"];market=q["market"]
  key=(d,market,id)
  if key in keyed:raise ValueError("DUPLICATE_NATIVE_KEY")
  fields=q["native_fields_json"];labels=json.loads(fields)
  if labels.count("本益比")!=1:raise ValueError("UNMAPPED_NATIVE_PE")
  idx=labels.index("本益比")
  raw=json.loads(q["native_row_json"]).get(str(idx)+":本益比")
  keyed[key]=n(raw)
 typed=[];valid=0
 for r in old:
  d=r["trade_date"].isoformat() if hasattr(r["trade_date"],"isoformat") else r["trade_date"]
  key=(d,r["market"],r["stock_id"])
  if key not in keyed:raise ValueError("MISSING_NATIVE_SOURCE_ROW")
  p=keyed[key]
  if p is not None and p>0:valid+=1
  typed.append({**r,"pe":p,"source_PE_native_input_sha256":sha(nativebytes)})
 table=pa.Table.from_pylist(typed)
 if not pa.types.is_decimal(table.schema.field("pe").type):raise ValueError("PE_NOT_DECIMAL_AFTER_REPAIR")
 buf=io.BytesIO();pq.write_table(table,buf,compression="zstd")
 b=buf.getvalue()
 if pq.read_metadata(io.BytesIO(b)).num_rows!=21620:raise ValueError("ROW_MISMATCH")
 silver_id=write(s,SILVER_FOLDER,"JARVIS_v095_202609_TWSE_valuation_TYPED_SILVER_PE_FIXED_R2.parquet",b)
 gold=[]
 for r in typed:
  pe,pb,dy=r.get("pe"),r.get("pb"),r.get("dividend_yield_pct")
  gold.append({"trade_date":r["trade_date"],"stock_id":r["stock_id"],"market":r["market"],
   "pe":pe,"pb":pb,"dividend_yield_pct":dy,
   "earnings_yield_pct":D(100)/pe if pe is not None and pe>0 else None,
   "book_value_to_price":D(1)/pb if pb is not None and pb>0 else None,
   "asof_available_date":datetime.date(2026,11,6),
   "source_Silver_SHA256":sha(b),"historical_pit_verified":False,
   "security_type_verified":False,"output_usage":"DESCRIPTIVE_ONLY_NO_BACKTEST"})
 out=io.BytesIO();pq.write_table(pa.Table.from_pylist(gold),out,compression="zstd")
 gb=out.getvalue()
 if pq.read_metadata(io.BytesIO(gb)).num_rows!=21620:raise ValueError("GOLD_ROW_MISMATCH")
 gold_id=write(s,GOLD_FOLDER,"JARVIS_v095_202609_GOLD_TWSE_VALUATION_PE_REPAIRED_DESCRIPTIVE_R2.parquet",gb)
 qa={"schema":"JARVIS_v095_202609_TWSE_PE_FIELD_RECOVERY_R2","source_original_candidate_id":NATIVE_ID,
  "original_SHA256":sha(nativebytes),"Silver_R1_file_id":SILVER_R1,"Silver_R1_SHA256":sha(oldbytes),
  "Silver_R2_file_id":silver_id,"Silver_R2_SHA256":sha(b),
  "Gold_R2_file_id":gold_id,"Gold_R2_SHA256":sha(gb),
  "rows":21620,"valid_positive_pe_rows":valid,"source_pe_valid_rate":valid/21620,
  "pit_backtest_allowed":False,"asof":"2026-11-06","security_master_verified":False,
  "status":"DESCRIPTIVE_GOLD_PUBLISHED_PE_FIELD_REPAIRED","all_market_PE_or_historical_correctness_certified":False}
 q=json.dumps(qa,ensure_ascii=False,indent=2).encode()
 qa["qa_drive_id"]=write(s,GOLD_FOLDER,"JARVIS_v095_202609_GOLD_TWSE_VALUATION_PE_REPAIR_QA_R2.json",q)
 work=pathlib.Path("v095_gold_pe_repair");work.mkdir(exist_ok=True)
 (work/"result.json").write_bytes(q)
 print(json.dumps(qa,ensure_ascii=False),flush=True)
if __name__=="__main__":main()
