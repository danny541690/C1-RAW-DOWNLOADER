"""September typed Silver -> current-as-of Gold valuation/foreign-holding snapshot.
Safe descriptive current-as-of 2026-11-06 only. Does not confer PIT/backtest eligibility.
"""
import os,io,json,hashlib,pathlib,datetime,decimal,argparse,collections
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
import pyarrow as pa,pyarrow.parquet as pq
D=decimal.Decimal
ASOF=datetime.date(2026,11,6)
SOURCES={
 "tse-valuation":{"id":"1-yw7DxlsuNXXRjVRcwOfU5AjjhPqMwbq","expected":21620,"fields":["pb","dividend_yield_pct"],"optional_fields":["pe"]},
 "tpex-valuation":{"id":"1h9PU-3stNNWyT_SXPTtNeltbEm8QSQ1t","expected":17744,"fields":["pe","pb","dividend_yield_pct"]},
 "tpex-foreign-holdings":{"id":"1zgVmOyNvpjhzqE9QZFIPqiOCy2IOntFS","expected":17827,"fields":["foreign_holdings_shares","foreign_ownership_pct","issued_shares"]}
}
DEST="1XT_54SXjGDksTz6PAdwhsVA8czZ1FTE3"
def sha(b):return hashlib.sha256(b).hexdigest()
def svc():
 c=Credentials(token=None,refresh_token=os.environ["GOOGLE_REFRESH_TOKEN"],token_uri="https://oauth2.googleapis.com/token",
  client_id=os.environ["GOOGLE_CLIENT_ID"],client_secret=os.environ["GOOGLE_CLIENT_SECRET"],scopes=["https://www.googleapis.com/auth/drive"])
 c.refresh(Request());return build("drive","v3",credentials=c,cache_discovery=False)
def get(s,id):return s.files().get_media(fileId=id).execute()
def ls(s,parent,name):
 return s.files().list(q=f"'{parent}' in parents and name = '{name}' and trashed = false",fields="files(id)",pageSize=100).execute()["files"]
def folder(s,parent,name):
 files=ls(s,parent,name)
 if len(files)>1:raise ValueError("DUPLICATE_GOLD_FOLDER")
 if files:return files[0]["id"]
 return s.files().create(body={"name":name,"parents":[parent],"mimeType":"application/vnd.google-apps.folder"},fields="id").execute()["id"]
def save(s,parent,name,b):
 old=ls(s,parent,name)
 if len(old)>1:raise ValueError("DUPLICATE_OUTPUT")
 if old:
  if sha(get(s,old[0]["id"]))!=sha(b):raise ValueError("GOLD_GENERATION_CONFLICT")
  return old[0]["id"]
 id=s.files().create(body={"name":name,"parents":[parent]},
   media_body=MediaIoBaseUpload(io.BytesIO(b),mimetype="application/octet-stream",resumable=True),fields="id").execute()["id"]
 if sha(get(s,id))!=sha(b):raise ValueError("GOLD_OUTPUT_READBACK_SHA")
 return id
def main():
 a=argparse.ArgumentParser();a.add_argument("--lane",choices=SOURCES,required=True);lane=a.parse_args().lane
 spec=SOURCES[lane];s=svc();raw=get(s,spec["id"]);t=pq.read_table(io.BytesIO(raw))
 if t.num_rows!=spec["expected"]:raise ValueError("UNEXPECTED_TYPED_SILVER_ROW_COUNT")
 for f in spec["fields"]:
  if f not in t.schema.names or not pa.types.is_decimal(t.schema.field(f).type):
   raise ValueError("MISSING_NUMERIC_TYPED_SOURCE:"+f)
 rows=t.to_pylist();out=[];seen=set();report_counts=collections.Counter()
 for r in rows:
  date=r["trade_date"]
  if isinstance(date,str):date=datetime.date.fromisoformat(date)
  if not datetime.date(2026,9,1)<=date<=datetime.date(2026,9,30):raise ValueError("WRONG_OBSERVATION_MONTH")
  stock=r["stock_id"];market=r["market"]
  key=(date,market,stock)
  if key in seen:raise ValueError("DUPLICATE_TYPED_SILVER_KEY")
  seen.add(key)
  o={"trade_date":date,"stock_id":stock,"market":market,
    "source_typed_Silver_SHA256":sha(raw),"source_native_sha256":r["source_native_sha256"],
    "asof_available_date":ASOF,"historical_pit_verified":False,"security_type_verified":False,
    "output_usage":"DESCRIPTIVE_ONLY_NO_BACKTEST"}
  if lane.endswith("valuation"):
   pe,pb,dy=r.get("pe"),r.get("pb"),r.get("dividend_yield_pct")
   o.update(pe=pe,pb=pb,dividend_yield_pct=dy,
    earnings_yield_pct=(D(100)/pe if pe is not None and pe>0 else None),
    book_value_to_price=(D(1)/pb if pb is not None and pb>0 else None))
   if pe is None:report_counts["undefined_PE"]+=1
  else:
   holdings,issued,pct=r.get("foreign_holdings_shares"),r.get("issued_shares"),r.get("foreign_ownership_pct")
   o.update(foreign_holdings_shares=holdings,issued_shares=issued,foreign_ownership_pct=pct,
    calculated_foreign_ownership_pct=(holdings/issued*D(100) if holdings is not None and issued is not None and issued>0 else None))
   if o["calculated_foreign_ownership_pct"] is not None and pct is not None and abs(o["calculated_foreign_ownership_pct"]-pct)>D("0.15"):
    report_counts["published_vs_calculated_pct_diff_gt_0p15"]+=1
  out.append(o)
 if not out:raise ValueError("EMPTY_GOLD_FEATURE_SET")
 table=pa.Table.from_pylist(out);buf=io.BytesIO();pq.write_table(table,buf,compression="zstd")
 b=buf.getvalue()
 if pq.read_metadata(io.BytesIO(b)).num_rows!=len(out):raise ValueError("GOLD_READBACK_ROW_COUNT")
 dest=folder(s,DEST,"2026-09_DESCRIPTIVE_ONLY_ASOF_2026-11-06_"+lane)
 file=save(s,dest,"JARVIS_v095_202609_GOLD_"+lane+"_DESCRIPTIVE_R1.parquet",b)
 report={"scope":lane,"source_Silver_file_id":spec["id"],"source_Silver_sha256":sha(raw),
  "source_rows":len(rows),"gold_rows":len(out),"gold_parquet_id":file,"gold_parquet_sha256":sha(b),
  "source_numeric_field_names":spec["fields"],"optional_fields_missing":[x for x in spec.get("optional_fields",[]) if x not in t.schema.names],"exceptions":dict(report_counts),
  "status":"DESCRIPTIVE_GOLD_DATASET_PUBLISHED","available_asof":"2026-11-06",
  "historical_backtest_allowed":False,"pit_verified":False,"security_type_verified":False,
  "completeness_443_indicators_certified":False,
  "quality_caveat":"98 percent canonical numeric source row gate is not proof of exhaustive data correctness or historic PIT"}
 rep=json.dumps(report,ensure_ascii=False,indent=2).encode()
 report["qa_report_id"]=save(s,dest,"JARVIS_v095_202609_GOLD_"+lane+"_QA_R1.json",rep)
 work=pathlib.Path("v095_gold_valuation_foreign");work.mkdir(exist_ok=True)
 (work/(lane+".json")).write_bytes(rep)
 print(json.dumps(report,ensure_ascii=False),flush=True)
if __name__=="__main__":main()
