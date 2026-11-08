#!/usr/bin/env python3
"""Read-only-to-source 2026 Gold catalog gate / lineage check.
No invented Gold factors, no production certification, no Bronze or Silver mutation.
"""
import collections,datetime as dt,hashlib,io,json,os,pathlib
from googleapiclient.http import MediaIoBaseUpload
from scripts.v095_market_release_calendar_drive_archive import drive,OPS
CATALOG="1lbWk0qRZZFjpV-yL1gZNUb2pCZmHDHW7"
YEAR=int(os.getenv("V095_DATA_YEAR","2026"))
if YEAR not in (2025,2026):raise ValueError("GOLD_AUDIT_YEAR_OUT_OF_SCOPE")
MODE=os.getenv("V095_AUDIT_MODE")
if MODE not in ("GOLD_MARKET","GOLD_FUNDAMENTAL","LINEAGE"):raise ValueError("UNKNOWN_AUDIT_MODE")
OUT=pathlib.Path("v095_2026_gold_lineage_gate" if YEAR==2026 else "v095_2025_gold_lineage_gate")
MARKET={"OHLCV/MASTER","OHLC","OHLCV/SHARES","OHLC/BENCHMARK","OHLC/UNIVERSE",
        "INST_DAILY","BROKER/MARGIN","SECTOR/CONSTITUENTS"}
def sha(b):return hashlib.sha256(b).hexdigest()
def ls(d,q):
 rows=[];token=None
 while True:
  z=d.files().list(q=q,fields="nextPageToken,incompleteSearch,files(id,name,createdTime)",
      pageSize=500,pageToken=token).execute()
  if z.get("incompleteSearch"):raise ValueError("DRIVE_INCOMPLETE_SEARCH")
  rows.extend(z.get("files",[]))
  if len(rows)>2500:raise ValueError("AUDIT_SCAN_CAP")
  token=z.get("nextPageToken")
  if not token:return rows
def audit_catalog(d):
 raw=d.files().get_media(fileId=CATALOG).execute()
 cat=json.loads(raw);ind=cat.get("indicators",[])
 if len(ind)!=443 or len({v.get("id") for v in ind})!=443:raise ValueError("NOT_443_CATALOG")
 selected=[x for x in ind if (x.get("legacy_source") in MARKET)==(MODE=="GOLD_MARKET")]
 state=[]
 for x in selected:
  formula=x.get("formula")
  status="DISABLED_MISSING_FORMULA" if not formula or formula=="DEFINITION_PENDING" else "DISABLED_UNVERIFIED_INPUT_PIT"
  state.append({"indicator_id":x["id"],"legacy_source":x.get("legacy_source"),
    "formula_declared":bool(formula and formula!="DEFINITION_PENDING"),
    "status":status,"computed_value":None,"pit_verified":False,
    "ready_for_research":False,"reason":"Requires typed source partitions, exact formulas, dependency lookback and announcement time"})
 return {"catalog_count":443,"catalog_sha256":sha(raw),"scope_count":len(selected),
         "indicator_rows":state,"computed_count":0,"PIT_approved_count":0,
         "note":"Gold readiness inventory only; descriptive candidate Gold produced by source downstream workers"}
def audit_lineage(d):
 rows=ls(d,"'"+OPS+"' in parents and name contains 'JARVIS_V095_'+str(YEAR)+'_RUN_RECEIPT_' and trashed = false")
 checks=[];errors=[];status=collections.Counter()
 for f in sorted(rows,key=lambda x:x.get("createdTime",""),reverse=True):
  if len(checks)>=60:break
  try:
   blob=d.files().get_media(fileId=f["id"]).execute();h=sha(blob)
   if not f["name"].endswith("_"+h[:20]+".json"):raise ValueError("EVIDENCE_SHA_FILE_NAME")
   j=json.loads(blob)
   for p,val in j.get("source_results",{}).items():
    if not p.endswith("lineage_receipt.json"):continue
    q=val.get("data",{})
    if not isinstance(q,dict):continue
    x={"run_id":j["run_id"],"source":j["source"],"receipt_sha256":h,
       "forward_backward_observed":len(q.get("verified",[])) if isinstance(q.get("verified"),list) else None,
       "lineage_failures":len(q.get("failed",[])) if isinstance(q.get("failed"),list) else None,
       "PIT_approved":False}
    checks.append(x);status[j["source"]]+=1
  except Exception as exc:errors.append({"id":f["id"],"error":type(exc).__name__+":"+str(exc)[:130]})
 return {"lineage_run_receipts":checks,"sources_with_lineage_receipts":dict(status),"read_errors":errors,
    "year_fully_lineaged":False,"PIT_certified":False,
    "note":"Verified source-level SHA receipts only. Complete native B/S/G row lineage for six sources and 443 factors remains open."}
def publish(d,b):
 h=sha(b);name="JARVIS_V095_"+str(YEAR)+"_"+MODE+"_GATE_"+h[:22]+".json"
 rows=ls(d,"'"+OPS+"' in parents and name = '"+name+"' and trashed=false")
 if len(rows)>1:raise ValueError("DUPLICATE_GATE")
 if rows:fid=rows[0]["id"];action="REUSED"
 else:
  fid=d.files().create(body={"name":name,"parents":[OPS]},
   media_body=MediaIoBaseUpload(io.BytesIO(b),mimetype="application/json",resumable=False),
   fields="id").execute()["id"];action="CREATED"
 if sha(d.files().get_media(fileId=fid).execute())!=h:raise ValueError("AUDIT_READBACK_SHA")
 return {"drive_id":fid,"sha256":h,"readback":"PASS","action":action}
def main():
 OUT.mkdir(exist_ok=True)
 x=json.loads(pathlib.Path("governance/v095/PHASE1_FLAGS.json").read_text())
 assert not x["RELEASE_APPROVED"] and not x["BULK_COPY_APPROVED"]
 d=drive();body=audit_lineage(d) if MODE=="LINEAGE" else audit_catalog(d)
 summary={"schema":"JARVIS_V095_2026_GOLD_LINEAGE_GATE_R1","mode":MODE,
  "scope":str(YEAR),"run_id":os.getenv("GITHUB_RUN_ID"),
  "evaluated_utc":dt.datetime.now(dt.timezone.utc).isoformat(),
  "production_certified":False,"full_443_computed":False,"result":body}
 raw=(json.dumps(summary,ensure_ascii=False,sort_keys=True,indent=2)+"\n").encode()
 (OUT/"result.json").write_bytes(raw)
 print(json.dumps({"mode":MODE,"run_id":summary["run_id"],"records":
   len(body.get("indicator_rows",body.get("lineage_run_receipts",[]))),
   "drive":publish(d,raw),"production_certified":False},ensure_ascii=False))
if __name__=="__main__":main()
