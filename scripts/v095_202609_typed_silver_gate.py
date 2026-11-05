"""Formal typed Silver v0.95 September from verified prior candidate Parquet, not re-downloading Bronze.

This is a single transform+QA gate per scoped family. Only fields with explicit, unique
source names are eligible to be published for Gold. Ambiguous duplicate names, PIT
unknown, and unsupported reporting periods stay QUARANTINED in separate evidence.
"""
import argparse,collections,datetime,decimal,hashlib,io,json,os,pathlib,re
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
import pyarrow as pa, pyarrow.parquet as pq
D=decimal.Decimal
ROOT="1otbh4ZhJhPz0ARZuF8SSdPmpm8Zm_wTF"
LANES={
 "twse-flow":["TWSE_institutional","TWSE_foreign_holdings","TWSE_valuation"],
 "tpex-flow":["TPEx_institutional","TPEx_foreign_holdings","TPEx_valuation"],
 "twse-credit":["TWSE_margin","TWSE_lending"],
 "tpex-credit":["TPEx_margin","TPEx_lending","TPEx_marketcap"]
}
# Only truly unambiguous source-native field labels. No inference on foreign/self dealer
# from repeated positional label groups. Unsafe ambiguous metrics kept out of Gold.
ALIASES={
"TWSE_institutional":{"外陸資買進股數(不含外資自營商)":"foreign_ex_dealer_buy_shares","外陸資賣出股數(不含外資自營商)":"foreign_ex_dealer_sell_shares",
"外陸資買賣超股數(不含外資自營商)":"foreign_ex_dealer_net_shares","投信買進股數":"trust_buy_shares","投信賣出股數":"trust_sell_shares","投信買賣超股數":"trust_net_shares","三大法人買賣超股數":"institutional_total_net_shares"},
"TPEx_institutional":{"三大法人買賣超股數合計":"institutional_total_net_shares"},
"TWSE_valuation":{"本益比":"pe","股價淨值比":"pb","殖利率(%)":"dividend_yield_pct"},
"TPEx_valuation":{"本益比":"pe","股價淨值比":"pb","殖利率(%)":"dividend_yield_pct"},
"TWSE_foreign_holdings":{"全體外資及陸資持有股數":"foreign_holdings_shares","全體外資及陸資持股比率":"foreign_ownership_pct","發行股數":"issued_shares"},
"TPEx_foreign_holdings":{"僑外資及陸資持有股數(C)":"foreign_holdings_shares","僑外資及陸資持股比率(E=C/A)":"foreign_ownership_pct","發行股數(A)":"issued_shares"},
"TPEx_margin":{"資餘額":"margin_balance_lots","券餘額":"short_balance_lots","資買":"margin_buy_lots","資賣":"margin_sell_lots","券賣":"short_sell_lots","券買":"short_buy_lots","資使用率(%)":"margin_usage_pct","券使用率(%)":"short_usage_pct"},
"TWSE_margin":{},"TWSE_lending":{},"TPEx_lending":{},"TPEx_marketcap":{}
}
FAMILY_NUMERIC_REQUIRED={"TWSE_institutional":3,"TPEx_institutional":1,"TWSE_valuation":2,"TPEx_valuation":2,"TWSE_foreign_holdings":2,"TPEx_foreign_holdings":2,"TPEx_margin":4}
TRADING=sorted((datetime.date(2026,9,1)+datetime.timedelta(days=i)).isoformat() for i in range(30) if (datetime.date(2026,9,1)+datetime.timedelta(days=i)).weekday()<5 and i+1 not in (25,28))
def sha(x):return hashlib.sha256(x).hexdigest()
def n(v):
 if v is None:return None
 s=str(v).strip().replace(",","").replace("−","-").replace("%","")
 if not re.fullmatch(r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)",s):return None
 x=D(s)
 return x if x.is_finite() else None
def svc():
 c=Credentials(token=None,refresh_token=os.environ["GOOGLE_REFRESH_TOKEN"],token_uri="https://oauth2.googleapis.com/token",client_id=os.environ["GOOGLE_CLIENT_ID"],client_secret=os.environ["GOOGLE_CLIENT_SECRET"],scopes=["https://www.googleapis.com/auth/drive"])
 c.refresh(Request());return build("drive","v3",credentials=c,cache_discovery=False)
def get(s,id):return s.files().get_media(fileId=id).execute()
def ls(s,folder):
 result=[];token=None
 while True:
  res=s.files().list(q=f"'{folder}' in parents and trashed = false",fields="nextPageToken,files(id,name,mimeType)",pageSize=1000,pageToken=token).execute()
  result.extend(res.get("files",[]));token=res.get("nextPageToken")
  if not token:return result
def folder(s,parent,name):
 ff=[x for x in ls(s,parent) if x["name"]==name]
 if len(ff)>1:raise ValueError("DUPLICATE_FOLDER")
 if ff:return ff[0]["id"]
 return s.files().create(body={"name":name,"mimeType":"application/vnd.google-apps.folder","parents":[parent]},fields="id").execute()["id"]
def upload(s,parent,name,b):
 ff=[x for x in ls(s,parent) if x["name"]==name]
 if len(ff)>1:raise ValueError("DUPLICATE_OUTPUT")
 if ff:
  if sha(get(s,ff[0]["id"]))!=sha(b):raise ValueError("EXISTING_OUTPUT_HAS_DIFFERENT_SHA")
  return ff[0]["id"]
 id=s.files().create(body={"name":name,"parents":[parent]},media_body=MediaIoBaseUpload(io.BytesIO(b),mimetype="application/octet-stream",resumable=True),fields="id").execute()["id"]
 if sha(get(s,id))!=sha(b):raise ValueError("DRIVE_SHA_READBACK")
 return id
def process(s,family,source_file,output_folder):
 raw=get(s,source_file["id"]);input_sha=sha(raw);p=pq.read_table(io.BytesIO(raw))
 fields_needed=ALIASES[family];rows=[];stats=collections.Counter();coverage=collections.defaultdict(set);invalid_sample=[];unknown_labels=collections.Counter()
 for record in p.to_pylist():
  date=record.get("trade_date")
  if date not in TRADING:raise ValueError("INVALID_MONTHLY_DATE")
  market=record["market"];stock=str(record.get("security_id") or "").strip()
  rawfields=json.loads(record["native_fields_json"]);native=json.loads(record["native_row_json"])
  # No silent reorder; ordinal is the only safe join key.
  observed={str(k.split(":",1)[1]):v for k,v in native.items() if k.split(":",1)[0].isdigit()}
  if len(set(native))!=len(native):raise ValueError("DUPLICATE_POSITIONAL_KEY")
  # Exclude non-equity and ambiguous mixed tables from equity Gold. Preserve as QA.
  if not re.fullmatch(r"\d{4}",stock):
   stats["non_four_digit_or_market_aggregate"]+=1;continue
  if family not in FAMILY_NUMERIC_REQUIRED:
   stats["not_approved_semantic_map"]+=1;continue
  mapped={}
  for ordinal,label in enumerate(rawfields):
   canonical=fields_needed.get(label)
   if not canonical:continue
   if rawfields.count(label)!=1:
    stats["ambiguous_duplicate_field"]+=1;continue
   val=n(observed.get(label))
   if val is None:
    stats["missing_numeric_cells"]+=1
    if len(invalid_sample)<30:invalid_sample.append({"date":date,"stock":stock,"field":label,"value":str(observed.get(label))[:45]})
    continue
   if canonical in mapped:raise ValueError("DUPLICATE_CANONICAL_METRIC")
   mapped[canonical]=val
  if len(mapped)<FAMILY_NUMERIC_REQUIRED[family]:
   stats["insufficient_safe_metrics_rows"]+=1;continue
  q={"trade_date":datetime.date.fromisoformat(date),"stock_id":stock,"market":market,
    "source_dataset":family,"input_candidate_sha256":input_sha,
    "source_native_sha256":record["source_sha256"],
    "source_native_member":record["source_member"],"source_row_index":record["row_index"],
    "source_native_title":record["table_title"],"available_from":datetime.date.fromisoformat(date)+datetime.timedelta(days=1),
    "asof_rule":"NEXT_CALENDAR_DAY_CONSERVATIVE_NOT_SOURCE_PUBLICATION_PROOF",
    "security_type":"UNCONFIRMED_FOUR_DIGIT","pit_verified":False}
  q.update(mapped);rows.append(q);coverage[date].add(stock);stats["accepted_rows"]+=1
 stats["input_rows"]=p.num_rows
 valid=stats["accepted_rows"]/max(1,p.num_rows)
 date_count=len(coverage)
 status="CANDIDATE_QA_ONLY"
 # No formal Gold release for unproven security master/PIT even if numeric completeness passes.
 reasons=[]
 if not fields_needed:reasons.append("UNMAPPED_FAMILY_SEMANTICS")
 if valid<0.98:reasons.append("BELOW_98_ROW_CONVERSION_COVERAGE")
 if date_count!=20:reasons.append("NOT_20_OFFICIAL_DATES")
 reasons.extend(["SECURITY_TYPE_HISTORY_UNVERIFIED","OFFICIAL_PUBLICATION_PIT_NOT_VERIFIED"])
 metrics={"source":family,"input_parquet_file_id":source_file["id"],"input_source_sha256":input_sha,
 "native_rows":p.num_rows,"typed_silver_rows":len(rows),"valid_row_rate":valid,"trading_days":date_count,
 "quality_threshold":0.98,"release_status":status,"silver_typed_done":bool(rows),
 "gold_allowed":False,"release_reasons":reasons,"exceptions":dict(stats),"example_invalid":invalid_sample}
 if rows:
  # Keep separate from generic/native-only candidate. These are canonical numeric Arrow columns.
  tab=pa.Table.from_pylist(rows)
  for col in fields_needed.values():
   if col in tab.schema.names and not pa.types.is_decimal(tab.schema.field(col).type):raise ValueError("NON_NUMERIC_ARROW_SCHEMA")
  b=io.BytesIO();pq.write_table(tab,b,compression="zstd")
  out=b.getvalue()
  if pq.read_metadata(io.BytesIO(out)).num_rows!=len(rows):raise ValueError("PARQUET_COUNT_MISMATCH")
  fn=f"JARVIS_v095_202609_{family}_TYPED_SILVER_QA_R1.parquet"
  metrics["typed_parquet_id"]=upload(s,output_folder,fn,out)
  metrics["typed_parquet_sha256"]=sha(out)
 return metrics
def main():
 parser=argparse.ArgumentParser();parser.add_argument("--lane",choices=LANES,required=True);lane=parser.parse_args().lane
 s=svc();source_files=ls(s,ROOT);dest=folder(s,ROOT,"2026-09_TYPED_SILVER_QA_NOT_YET_GOLD_"+lane)
 output={"lane":lane,"period":"2026-09","families":{},"gate":"CANDIDATE_UNTIL_SOURCE_PIT_AND_SECURITY_MASTER","gold_enabled":False}
 for fam in LANES[lane]:
  src=[f for f in source_files if f["name"]==f"JARVIS_v095_SILVER_202609_{fam.replace('_','_')}_NATIVE_CANDIDATE_R1.parquet"]
  if len(src)!=1:
   output["families"][fam]={"status":"NOT_FOUND_OR_AMBIGUOUS","matches":len(src)};continue
  output["families"][fam]=process(s,fam,src[0],dest)
 report=json.dumps(output,indent=2,ensure_ascii=False).encode()
 output["report_id"]=upload(s,dest,f"JARVIS_v095_202609_{lane}_TYPED_QA_R1.json",report)
 path=pathlib.Path("v095_202609_typed_silver");path.mkdir(exist_ok=True)
 (path/(lane+".json")).write_bytes(report)
 print(json.dumps(output,ensure_ascii=False),flush=True)
if __name__=="__main__":main()
