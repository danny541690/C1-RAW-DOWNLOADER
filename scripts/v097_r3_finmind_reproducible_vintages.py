"""R3 G2 FinMind reproducible real 2000/2009/2022 API rows-vs-frozen audit.

For each source: exact frozen Bronze ZIP SHA, native JSON, manifest dataset,
stock id and month, reproduce supported provider API v4 GET with data_id and
date window, compare every returned row/value by native dataset primary key.
Record HTTP status + safe body detail (NO tokens), response SHA, row-level
diffs, original evidence, history PIT. Always fail closed for G2 issuance.
"""
from __future__ import annotations
import collections,datetime,hashlib,io,json,os,zipfile,requests
from urllib.parse import urlparse
from scripts.v097_bronze_autopilot import source_api
from scripts.v097_v3_preflight import read_baseline,assert_cohort
from scripts.v097_bronze_first_pipeline import put_once
RUN=os.getenv("GITHUB_RUN_ID","manual")
DEST="R3_G2_TAIFEX_FINMIND_DEEP_FORMAT_DIAGNOSTIC_ISOLATED"
IDS=("12Ym12g1tPQgHoN-zBQSKwlX4uJUwQ1Jy","19LblNra_20WRC7nfv4_r7LqOezb-TO87","1qPOj2Q9Q-h2lHUC98RviBjy4hoKR0nwE")
API="https://api.finmindtrade.com/api/v4/data"
def key(row,ds):
 if ds=="TaiwanStockFinancialStatements":return (row.get("date"),row.get("stock_id"),row.get("type"),row.get("origin_name"))
 return (row.get("date"),row.get("stock_id"))
def probe(row):
 api,control,quality,match,load,_,_,call=source_api()
 src=row["source_id"];frozen=call(lambda:api.files().get_media(fileId=row["destination_id"]))
 if hashlib.sha256(frozen).hexdigest()!=row["source_sha256"]:raise RuntimeError("FROZEN_SHA_CHANGED")
 with zipfile.ZipFile(io.BytesIO(frozen)) as z:
  if z.testzip() is not None:raise RuntimeError("ZIP_CRC_FAIL")
  names=z.namelist()
  if len(names)!=2 or "manifest.json" not in names:raise RuntimeError("ZIP_MEMBER_INVENTORY_DRIFT")
  native_name=next(n for n in names if n!="manifest.json")
  native=z.read(native_name)
  data=json.loads(native.decode("utf-8-sig"))
  manifest=json.loads(z.read("manifest.json").decode("utf-8-sig"))
 units=manifest.get("units")
 if not isinstance(units,list) or len(units)!=1:raise RuntimeError("NOT_A_SINGLE_DATASET_UNIT")
 unit=units[0]
 ds=unit.get("dataset");stock=unit.get("stock_id");month=unit.get("period") or unit.get("month")
 if ds not in ("TaiwanStockPrice","TaiwanStockFinancialStatements") or not stock or not month or len(month)!=7:
  raise RuntimeError("DATASET_ID_OR_MONTH_UNVERIFIED")
 first,last=month+"-01",month+"-31"
 from calendar import monthrange
 y,m=map(int,month.split("-"))
 last=f"{y:04d}-{m:02d}-{monthrange(y,m)[1]:02d}"
 rows=data.get("data",[])
 if not isinstance(rows,list) or not rows or any(x.get("stock_id")!=stock for x in rows):
  raise RuntimeError("ORIGINAL_DATA_SCHEMA_STOCK_CONFLICT")
 request={"dataset":ds,"data_id":stock,"start_date":first,"end_date":last}
 out={"source":"FinMind","source_id":src,"frozen_outer_sha256":row["source_sha256"],
      "frozen_native_sha256":hashlib.sha256(native).hexdigest(),
      "native_member_name":native_name,"historical_date_window":[first,last],
      "dataset":ds,"stock_id":stock,"API":API,
      "query_params_without_secrets":request,
      "original_json_status":data.get("status"),"original_json_msg":data.get("msg"),
      "original_rows":len(rows),
      "original_columns":list(rows[0]),"original_first":rows[0],
      "original_last":rows[-1],"manifest_pit_verified":unit.get("pit_verified",manifest.get("pit_verified")),
      "returned_byte_sha":None,"exact_bytes_equal":False,"row_values_equal":False,
      "historical_asof_attested":False,"formal_G2_PASS":False}
 try:
  headers={"User-Agent":"JARVIS-R3-ValidatingHistoricalData/1.0"}
  token=os.getenv("FINMIND_TOKEN","")
  if token:headers["Authorization"]="Bearer "+token
  resp=requests.get(API,params=request,headers=headers,timeout=27,stream=True)
  out["http_status"]=resp.status_code
  out["response_host"]=urlparse(resp.url).hostname
  if out["response_host"]!="api.finmindtrade.com":
   out["status"]="HOLD_UNTRUSTED_REDIRECT"
  else:
   content=bytearray()
   for chunk in resp.iter_content(65536):
    content.extend(chunk)
    if len(content)>4*1024*1024:raise RuntimeError("ENDPOINT_BYTE_GUARD")
   out["remote_body_sha256"]=hashlib.sha256(content).hexdigest()
   try:remote=json.loads(content)
   except ValueError:remote={}
   out["api_status"]=remote.get("status") if isinstance(remote,dict) else None
   out["api_msg_or_detail"]=str(remote.get("msg") or remote.get("detail") or "")[:350] if isinstance(remote,dict) else "NON_JSON"
   got=remote.get("data") if isinstance(remote,dict) else None
   if resp.status_code!=200 or not isinstance(got,list):
    out["status"]="HOLD_API_HTTP_OR_DATA"
   else:
    out["response_rows"]=len(got)
    out["response_columns"]=list(got[0]) if got and isinstance(got[0],dict) else []
    out["exact_bytes_equal"]=(hashlib.sha256(content).hexdigest()==out["frozen_native_sha256"])
    expected=collections.defaultdict(list);actual=collections.defaultdict(list)
    for x in rows:expected[key(x,ds)].append(x)
    for x in got:actual[key(x,ds)].append(x)
    missing=[str(k) for k in expected.keys()-actual.keys()]
    extra=[str(k) for k in actual.keys()-expected.keys()]
    changed=[]
    for k in expected.keys()&actual.keys():
     if expected[k]!=actual[k]:
      changed.append({"key":str(k),"frozen":expected[k][:1],"live":actual[k][:1]})
    out["missing_keys"]=len(missing);out["extra_keys"]=len(extra);out["different_values_or_multiplicity"]=len(changed)
    out["first_diff_examples"]=changed[:3]
    out["missing_examples"]=missing[:3];out["extra_examples"]=extra[:3]
    out["missing_full_examples"]=[{"key":str(k),"rows":expected[k][:1]} for k in sorted(expected.keys()-actual.keys())[:3]]
    out["extra_full_examples"]=[{"key":str(k),"rows":actual[k][:1]} for k in sorted(actual.keys()-expected.keys())[:3]]
    if ds=="TaiwanStockFinancialStatements":
     historical={(z["date"],z["stock_id"],z["origin_name"]):z["value"] for z in rows}
     today={(z["date"],z["stock_id"],z["origin_name"]):z["value"] for z in got}
     out["same_origin_name_values_exact"]=historical==today
     out["historical_and_current_accounting_labels_count"]=len(historical)
     out["alias_candidate_only_not_officially_approved"]=(len(missing)==1 and len(extra)==1 and historical==today)

    out["row_values_equal"]=(len(missing)==0 and len(extra)==0 and len(changed)==0)
    out["status"]="LIVE_ALL_NATIVE_ROWS_EQUAL_SOURCE_VINTAGE_ONLY" if out["row_values_equal"] else "HOLD_LIVE_ROW_REVISION_OR_QUERY_MISMATCH"
 except requests.RequestException as exc:
  out["status"]="HOLD_API_"+type(exc).__name__
 return out
def main():
 api,control,quality,match,load,_,_,call=source_api()
 files=read_baseline(api,quality,match,load,"FinMind");assert_cohort(files,"FinMind")
 ix={r["source_id"]:r for r in files}
 outfolder=match(api,quality,DEST)
 if not outfolder:outfolder=call(lambda:api.files().create(body={"name":DEST,
   "parents":[quality],"mimeType":"application/vnd.google-apps.folder"},fields="id,mimeType"))
 summaries=[]
 for sid in IDS:
  if sid not in ix:raise RuntimeError("SOURCE_ID_NOT_IN_FROZEN_COHORT")
  result=probe(ix[sid])
  name=f"r3_finmind_reproducible_{sid[:10]}_run_{RUN}.json"
  did=put_once(api,outfolder["id"],name,result)
  if load(api,did)!=result:raise RuntimeError("FINMIND_SOURCE_RECEIPT_REMOTE_READBACK_FAIL")
  summary={"source_id":sid,"dataset":result["dataset"],"stock_id":result["stock_id"],
    "window":result["historical_date_window"],"original_rows":result["original_rows"],
    "http":result.get("http_status"),"status":result["status"],
    "remote_rows":result.get("response_rows"),
    "row_values_equal":result["row_values_equal"],
    "api_error":result.get("api_msg_or_detail"),"missing":result.get("missing_keys"),
    "extra":result.get("extra_keys"),"changed":result.get("different_values_or_multiplicity"),
    "receipt_id":did,"readback":True}
  summaries.append(summary)
  print("R3_G2_FINMIND_REPRODUCIBLE="+json.dumps(summary,sort_keys=True,ensure_ascii=False),flush=True)
 master={"schema":"R3_G2_FINMIND_THREE_VINTAGE_NATIVE_QUERY_AUDIT_V1","run":RUN,
   "source":"FinMind","tested_files":len(summaries),"formal_new_g2_pass":0,
   "source_query_results":summaries,"no_2022_historical_publication_PIT_inferred":True,
   "no_bronze_mutation":True,"no_silver_gold":True}
 name=f"r3_finmind_2000_2009_2022_native_reproducibility_master_run_{RUN}.json"
 mid=put_once(api,outfolder["id"],name,master)
 if load(api,mid)!=master:raise RuntimeError("FINMIND_REPRO_MASTER_READBACK_FAIL")
 print("R3_G2_FINMIND_REPRO_MASTER="+json.dumps({"run":RUN,"id":mid,"results":summaries,"readback":True},sort_keys=True,ensure_ascii=False),flush=True)
if __name__=="__main__":main()
