#!/usr/bin/env python3
"""Full population 5035 TDCC record-level cross-reference to independent weekly CSV.
Immutable A4 original HTML per-file QA receipts include full holder/share totals
and original SHA; this script joins by YYYYMMDD + exact case-sensitive symbol.
Third-party cache is a witness, NOT official source, and CANNOT authorize
ordinary-stock Bronze admission or historical security-master classification.
"""
import os,re,json,hashlib,requests,csv,io
from collections import Counter,defaultdict
from datetime import datetime,timezone
from scripts.v097_bronze_first_pipeline import service,common,children,load_json,put_once,match
from scripts.v097_tdcc_a3_a5_auto import source_rows,FILE
RUN=os.getenv("GITHUB_RUN_ID","manual")
SRC="https://raw.githubusercontent.com/wirelessr/tdcc-opendata-archive/main/snapshots/"
def sha(b):return hashlib.sha256(b).hexdigest()
def get_week(d):
 url=SRC+d[:4]+"/"+d[:4]+"-"+d[4:6]+"-"+d[6:]+".csv"
 try:
  r=requests.get(url,timeout=(10,50),headers={"User-Agent":"JARVIS-097-independent-crosscheck"})
  if r.status_code==404:return {"state":"NO_ARCHIVE_AT_EXACT_DATE","url":url},{}
  r.raise_for_status()
  if len(r.content)>14_000_000:raise ValueError("ARCHIVE_OVERSIZE")
  rows=list(csv.DictReader(io.StringIO(r.content.decode("utf-8-sig"))))
  totals={}
  for x in rows:
   if x.get("資料日期")!=d or x.get("持股分級")!="17":continue
   code=str(x.get("證券代號") or "").strip().upper()
   if code in totals:raise ValueError("DUPLICATE_CODE_AT_LEVEL17")
   totals[code]=(int(x["人數"]),int(x["股數"]))
  return {"state":"ARCHIVE_READABLE","url":url,"sha256":sha(r.content),
          "rows":len(rows),"unique_codes":len(totals)},totals
 except Exception as exc:
  return {"state":"THIRDPARTY_SOURCE_ERROR","url":url,
   "reason":type(exc).__name__+":"+str(exc)[:170]},{}
def main():
 api=service();m,c,q,_=common(api)
 rows={};counts=Counter();dates=Counter()
 for lane in range(6):
  for x in source_rows(api,q,lane):
   if x["file_id"] in rows:raise RuntimeError("POPULATION_DUPLICATE")
   m=FILE.search(str(x.get("source_path") or ""))
   if not m:raise RuntimeError("BAD_ORIGINAL_FILENAME")
   day,code=m.group(1),m.group(2).upper()
   rows[x["file_id"]]={"file_id":x["file_id"],"day":day,"code":code,
     "source_path":x.get("source_path"),"result":"NOT_CROSSCHECKED"}
   dates[day]+=1
 if len(rows)!=5035:raise RuntimeError("POPULATION_NOT_5035")
 rx=re.compile(r"^v097_TDCC_A4_V3_\d+_L\d\d_O\d+\.json$")
 found=0
 for f in children(api,q):
  if not rx.match(f["name"]):continue
  report=load_json(api,f["id"])
  if report.get("schema")!="v097_tdcc_a4_lane_3":continue
  for rec in report.get("items",[]):
   fid=rec.get("file_id")
   if fid not in rows:continue
   prior=rows[fid]
   ob=rec.get("observations") or {}
   numeric=ob.get("table_qa") or {}
   if "holders" in prior:continue
   if rec.get("status")!="HTML_TOKEN_CONSISTENT_SECURITY_CLASS_AND_ORIGIN_PENDING" or numeric.get("status")!="HTML_DISTRIBUTION_TOTALS_MATCH":
    raise RuntimeError("A4_RECEIPT_NOT_NUMERIC_QA_PASS")
   if ob.get("date")!=prior["day"] or ob.get("content_security_id")!=prior["code"] or not ob.get("selected_date_matches"):
    raise RuntimeError("A4_DATE_CODE_DOES_NOT_MATCH")
   if not re.fullmatch(r"[0-9a-f]{64}",rec.get("source_sha256") or ""):
    raise RuntimeError("A4_NO_SHA")
   prior.update(holders=numeric["total_holders"],shares=numeric["total_shares"],
     source_sha256=rec["source_sha256"])
   found+=1
 missing_numeric_receipts=5035-found
 source_snapshots={}
 bydate=defaultdict(Counter)
 for day in sorted(dates):
  snap,lookup=get_week(day)
  source_snapshots[day]=snap
  for rec in rows.values():
   if rec["day"]!=day:continue
   if "holders" not in rec or "shares" not in rec:
    rec["result"]="A4_NUMERIC_RECEIPT_NOT_FOUND"
   elif snap["state"]!="ARCHIVE_READABLE":
    rec["result"]="THIRDPARTY_DATE_NOT_AVAILABLE"
   elif rec["code"] not in lookup:
    rec["result"]="THIRDPARTY_CODE_NOT_PRESENT"
   elif lookup[rec["code"]]==(rec["holders"],rec["shares"]):
    rec["result"]="THIRDPARTY_HOLDER_SHARE_EXACT"
   else:
    h,s=lookup[rec["code"]]
    rec.update(result="THIRDPARTY_HOLDER_SHARE_DISAGREE",
       third_party_holders=h,third_party_shares=s)
   counts[rec["result"]]+=1;bydate[day][rec["result"]]+=1
 report={"schema":"v097_tdcc_5035_all_crosssource_1","run":RUN,
  "at":datetime.now(timezone.utc).isoformat(),
  "population":5035,"original_sha_and_holder_total_receipts":found,
  "missing_original_numeric_receipts":missing_numeric_receipts,
  "by_result":dict(counts),"per_date":{k:dict(v) for k,v in bydate.items()},
  "third_party_archives":source_snapshots,
  "market_bronze_admitted":0,"source_v093_unchanged":True,
  "authority":"Auxiliary witness ONLY; official validation remains separate",
  "records":list(rows.values())}
 put_once(api,q,"v097_TDCC_5035_THIRDPARTY_ALL_"+RUN+".json",report)
 short={k:v for k,v in report.items() if k!="records"}
 print("TDCC_5035_ALL_CROSSSOURCE="+json.dumps(short,ensure_ascii=False),flush=True)
if __name__=="__main__":main()
