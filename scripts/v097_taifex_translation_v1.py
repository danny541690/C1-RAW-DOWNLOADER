#!/usr/bin/env python3
"""Bronze v0.97 TAIFEX format-translation remediation v1.

Only format interpretation of existing 0.97 original bytes, never transform
or overwrite Bronze. Recheck unresolved CSV width/date/header cases against
the historically date-bearing TAIFEX native file layout. A separate Bronze
Gate remains the exclusive release authority.
"""
import json,os,sys
from collections import Counter
from scripts.v097_bronze_autopilot import source_api,parse_taifex_csv,digest
from scripts.v097_seven_native_v2_probe import checkpoint_commit
VERSION="v097_taifex_native_csv_translation_v1"
PARSER_REV="v097_taifex_native_csv_layout_20261117_v2"
NAME="v097_TAIFEX_NATIVE_CSV_TRANSLATION_CK_v1.json"
BATCH=max(1,min(450,int(os.getenv("TRANSLATION_BATCH","250"))))
TARGETS={"HOLD_TAIFEX_CSV_WIDTH","HOLD_TAIFEX_DATE_HEADER_UNRECOGNIZED",
         "HOLD_TAIFEX_CSV_HEADER","HOLD_TAIFEX_DATE_PARSE",
         "HOLD_TAIFEX_CSV_NO_ROWS"}
def examine(row,raw):
 base={"source_id":row["source_id"],"source_sha256":row["sha"],
       "destination_id":row["dest_id"],"source_path":row["source_path"],
       "original_bytes_preserved":True,"silver_gold_executed":False}
 if digest(raw)!=row["sha"]:
  return {**base,"status":"HOLD_TRANSLATION_SHA_MISMATCH"}
 name=row["source_path"].rsplit("/",1)[-1].lower()
 if not name.endswith((".csv",".txt",".raw")):
  return {**base,"status":"HOLD_TRANSLATION_NON_CSV_NOT_RECLASSIFIED"}
 parsed=parse_taifex_csv(raw,str(row["year"])+"-"+str(row["month"]))
 # This is a full-file independent parse, not a derived metadata-only READY.
 return {**base,**parsed,"format_translator_version":PARSER_REV,
         "date_vs_contract_month_kept_distinct":True}
def selftest():
 row={"source_id":"example","sha":"","dest_id":"destination","source_path":"2026/TAIFEX/2026-11/data.csv","year":"2026","month":"11"}
 example=("期貨每日交易行情下載\n"
          "交易日期,契約,成交量\n"
          "20261116,TX,100\n"
          "交易日期,契約,成交量\n"
          "20261117,TX,101,\n").encode()
 row["sha"]=digest(example)
 a=examine(row,example)
 assert a["status"]=="TAIFEX_CSV_ENCODING_WIDTH_PASS_DATE_PIT_HOLD",a
 assert a["rows_checked"]==2 and a["preamble_lines_accounted"]==1
 assert a["repeated_headers_accounted"]==1 and a["trailing_empty_cells_ignored"]==1
 assert examine(row,example+b"bad")["status"]=="HOLD_TRANSLATION_SHA_MISMATCH"
 wrong=example.replace(b"20261117",b"20261017")
 rw={**row,"sha":digest(wrong)}
 assert examine(rw,wrong)["status"]=="HOLD_TAIFEX_MONTH_CONFLICT"
 invalid=example.replace(b",TX,101,",b",TX,101,UNEXPECTED,")
 ri={**row,"sha":digest(invalid)}
 assert examine(ri,invalid)["status"]=="HOLD_TAIFEX_CSV_WIDTH"
 print("TAIFEX_ORIGINAL_FORMAT_TRANSLATION_SELFTEST_PASS parser="+PARSER_REV)
def run():
 api,control,quality,match,load_json,put_once,upsert,call=source_api()
 inp=match(api,quality,"v097_AP_INPUT_TAIFEX.json")
 old=match(api,control,"v097_AP_CHECKPOINT_TAIFEX.json")
 native=match(api,control,"v097_SEVEN_FORMAT_V2_CK_TAIFEX.json")
 if not inp or not old or not native:raise RuntimeError("MISSING_TAIFEX_FROZEN_INPUT_OR_CHECKPOINT")
 rows=load_json(api,inp["id"])["rows"]
 old_done=load_json(api,old["id"])["done"]
 native_done=load_json(api,native["id"])["done"]
 f=match(api,control,NAME)
 ck=load_json(api,f["id"]) if f else {"version":VERSION,"done":{}}
 if ck.get("version")!=VERSION:raise RuntimeError("TRANSLATION_VERSION_MISMATCH")
 ids={r["source_id"] for r in rows}
 if set(ck["done"])-ids:raise RuntimeError("TRANSLATION_ORPHAN")
 candidates=[]
 for r in rows:
  sid=r["source_id"]
  if sid in ck["done"]:continue
  n=native_done.get(sid,{})
  st=n.get("status") or old_done.get(sid,{}).get("status")
  if st in TARGETS or (st=="ZIP_MEMBERS_AUDITED_ORIGIN_HOLD" and
      r["source_path"].lower().endswith((".csv",".txt",".raw"))):
   candidates.append(r)
 # Refresh a small representative sample of last-pass width failures
 # whenever their diagnostic schema changes, without re-reading all files.
 revisits=[r for r in rows if r["source_id"] in ck["done"] and
      ck["done"][r["source_id"]].get("status","").startswith("HOLD_TAIFEX_") and
      ck["done"][r["source_id"]].get("format_translator_version")!=PARSER_REV][:BATCH]
 batch=revisits+candidates[:max(0,BATCH-len(revisits))]
 fresh={}
 for row in batch:
  sid=row["source_id"]
  try:
   blob=call(lambda:api.files().get_media(fileId=row["dest_id"]))
   fresh[sid]=examine(row,blob)
  except Exception as exc:
   fresh[sid]={"source_id":sid,"status":"RETRY_SOURCE_TRANSLATION_READ_"+type(exc).__name__}
 ck["done"].update(fresh);ck["run"]=os.getenv("GITHUB_RUN_ID","manual")
 if fresh:checkpoint_commit(api,control,NAME,ck,upsert,match,load_json)
 count=Counter(x["status"] for x in fresh.values())
 widths=Counter((x.get("header_fields"),x.get("row_fields")) for x in ck["done"].values()
    if x.get("status")=="HOLD_TAIFEX_CSV_WIDTH")
 samples=[{"source_path":row["source_path"],
    "header":ck["done"][row["source_id"]].get("header_preview"),
    "row_excerpt":ck["done"][row["source_id"]].get("row_excerpt"),
    "header_width":ck["done"][row["source_id"]].get("header_fields"),
    "row_width":ck["done"][row["source_id"]].get("row_fields")}
    for row in rows if row["source_id"] in fresh and
    ck["done"][row["source_id"]].get("status")=="HOLD_TAIFEX_CSV_WIDTH"][:8]
 print("TAIFEX_TRANSLATION_PROGRESS="+json.dumps({"batch":len(fresh),"completed":len(ck["done"]),
     "remaining":max(0,len(candidates)-(len(batch)-len(revisits))),
     "states":dict(count),"width_histogram":{str(k):v for k,v in widths.most_common(15)},
     "samples":samples,"original_bytes_unchanged":True,
     "silver_gold_executed":False},ensure_ascii=False),flush=True)
if __name__=="__main__":
 if sys.argv[1:]==["selftest"]:selftest()
 elif len(sys.argv)==1:run()
 else:raise SystemExit("selftest | default")
