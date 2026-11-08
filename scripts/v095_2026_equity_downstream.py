#!/usr/bin/env python3
"""Incremental independent TWSE/TPEx Bronze->Silver/descriptive Gold worker.
No official HTTP, no Bronze writes, no cursor modification, no PIT release.
Single source writer for same Silver/Gold partition. Immutable filenames + SHA readback.
"""
import collections,datetime as dt,hashlib,json,os,pathlib,re,sys
from scripts import v095_ultimate_r1_november_official as base
from scripts.v093_three_year_repair import validate
from scripts.v095_2026_price_incremental import job_for,dates
SOURCE=os.getenv("V095_PRICE_SOURCE","").strip()
if SOURCE not in ("TWSE","TPEx"):raise ValueError("EQUITY_DOWNSTREAM_SOURCE_REQUIRED")
DATA_YEAR=int(os.getenv("V095_DATA_YEAR","2026"))
if DATA_YEAR not in (2025,2026):raise ValueError("ONLY_2025_2026")
OUT=pathlib.Path("v095_2026_equity_downstream" if DATA_YEAR==2026 else "v095_2025_equity_downstream")
LIMIT=max(1,min(15,int(os.getenv("V095_DOWNSTREAM_BATCH","10"))))
def sha(b):return hashlib.sha256(b).hexdigest()
def folders(d,root):
 return [f for f in base.ls(d,root) if f.get("mimeType")=="application/vnd.google-apps.folder"]
def verified(d,items,prefix,suffix):
 matched=[f for f in items if f["name"].startswith(prefix) and f["name"].endswith(suffix)]
 if len(matched)>1:raise ValueError("AMBIGUOUS_DOWNSTREAM_OUTPUT_"+prefix)
 if not matched:return False
 x=matched[0];raw=d.files().get_media(fileId=x["id"]).execute()
 match=re.search(r"_([0-9a-f]{20})\."+re.escape(suffix.lstrip("."))+r"$",x["name"])
 if not match or sha(raw)[:20]!=match.group(1):raise ValueError("DOWNSTREAM_OUTPUT_SHA_MISMATCH")
 return True
def process(d,source,day,f):
 cfg=base.SOURCES[source];job=job_for(day,source);raw=d.files().get_media(fileId=f["id"]).execute()
 h=sha(raw);expected="V095_"+day[:7].replace("-","")+"_"+source+"_"+day+"_"+h[:20]+".json"
 if f["name"]!=expected:raise ValueError("BRONZE_FILENAME_SHA_MISMATCH")
 facts=validate(raw,source,job["category"],day)
 rows,unparsed=base.parse(raw,source,day)
 for r in rows:r.update(bronze_file_id=f["id"],bronze_sha256=h,source_url=job["url"])
 b=base.to_parquet(rows);sh=sha(b)
 sm=base.folder(d,cfg["silver"],day[:7]+"_CANDIDATE")
 sid,sa=base.save(d,sm,"V095_"+day[:7].replace("-","")+"_"+source+"_"+day+"_OHLCV_"+sh[:20]+".parquet",b)
 gold=[{"trade_date":r["trade_date"],"market":r["market"],"stock_id":r["stock_id"],
        "close":r["close"],"volume_shares":r["volume_shares"],"turnover_億元":r["turnover_億元"],
        "silver_file_id":sid,"silver_sha256":sh,
        "bronze_file_id":f["id"],"bronze_sha256":h,
        "historical_pit_verified":False,"usage":"DESCRIPTIVE_NO_BACKTEST"}
       for r in rows if r["close"] is not None and r["close"]>0]
 gb=base.to_parquet(gold);gh=sha(gb)
 gm=base.folder(d,base.GOLD,day[:7]+"_DESCRIPTIVE_ONLY")
 gid,ga=base.save(d,gm,"V095_"+day[:7].replace("-","")+"_"+source+"_"+day+"_PRICE_GOLD_"+gh[:20]+".parquet",gb)
 return {"source":source,"date":day,"rows":len(rows),"gold_rows":len(gold),
  "bronze_id":f["id"],"silver_id":sid,"gold_id":gid,
  "bronze_sha256":h,"silver_sha256":sh,"gold_sha256":gh,
  "actions":[sa,ga],"pit_verified":False,"unparsed":unparsed}
def main():
 OUT.mkdir(exist_ok=True)
 flags=json.loads(pathlib.Path("governance/v095/PHASE1_FLAGS.json").read_text())
 assert not flags["BULK_COPY_APPROVED"] and not flags["RELEASE_APPROVED"]
 d=base.api();cfg=base.SOURCES[SOURCE];completed=[];skipped=[];failures=[];attempted=0
 months=sorted(folders(d,cfg["bronze"]),key=lambda f:f["name"])
 for month in months:
  if len(completed)>=LIMIT:break
  if not re.fullmatch(fr"{DATA_YEAR}-\d\d",month["name"]):continue
  monthname=month["name"]
  native=[x for x in base.ls(d,month["id"]) if x["name"].endswith(".json") and
       x["name"].startswith("V095_"+monthname.replace("-","")+"_"+SOURCE+"_")]
  if not native:continue
  sf=[f for f in folders(d,cfg["silver"]) if f["name"]==monthname+"_CANDIDATE"]
  gf=[f for f in folders(d,base.GOLD) if f["name"]==monthname+"_DESCRIPTIVE_ONLY"]
  silver_files=base.ls(d,sf[0]["id"]) if len(sf)==1 else []
  gold_files=base.ls(d,gf[0]["id"]) if len(gf)==1 else []
  if len(sf)>1 or len(gf)>1:raise ValueError("DUPLICATE_STAGE_MONTH_FOLDERS")
  for native_file in sorted(native,key=lambda x:x["name"]):
   if len(completed)>=LIMIT:break
   match=re.fullmatch(r"V095_\d{6}_"+SOURCE+fr"_({DATA_YEAR}-\d\d-\d\d)_[0-9a-f]{{20}}\.json",native_file["name"])
   if not match:continue
   day=match.group(1)
   key="V095_"+monthname.replace("-","")+"_"+SOURCE+"_"+day+"_"
   try:
    # No blind reprocessing: successful existing candidate artifacts are inspected by content SHA.
    if verified(d,silver_files,key+"OHLCV_",".parquet") and verified(d,gold_files,key+"PRICE_GOLD_",".parquet"):
     skipped.append(day);continue
    attempted+=1
    completed.append(process(d,SOURCE,day,native_file))
   except Exception as exc:
    failures.append({"source":SOURCE,"date":day,"type":type(exc).__name__,
      "reason":str(exc)[:180],"status":"QA_REVIEW_NOT_REDOWNLOAD"})
 report={"schema":"V095_2026_EQUITY_DOWNSTREAM_R1","source":SOURCE,"run_id":os.getenv("GITHUB_RUN_ID"),
  "completed":completed,"converted_count":len(completed),"reused_valid_stage_days":len(skipped),
  "failed":failures,"attempted":attempted,"total_months_inspected":len(months),
  "historical_PIT_certified":False,"443_gold_certified":False,"year_complete":False,"data_year":DATA_YEAR}
 (OUT/"result.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
 # Lineage gate checks fresh triplets, including remote SHA and forward/reverse per-row mapping.
 from scripts.v095_2026_bsg_lineage_gate import audit
 confirmed=[];errors=[]
 for item in completed:
  try:confirmed.append(audit(d,item))
  except Exception as exc:errors.append({"date":item["date"],"error":type(exc).__name__+":"+str(exc)[:160]})
 (OUT/"lineage_receipt.json").write_text(json.dumps({"source":SOURCE,"verified":confirmed,"failed":errors,
  "PIT_certified":False,"year_certified":False},ensure_ascii=False,indent=2)+"\n")
 print(json.dumps({"source":SOURCE,"converted":len(completed),"reused":len(skipped),
  "failed":len(failures),"lineage_pass":len(confirmed),"lineage_fail":len(errors),
  "year_complete":False,"pit":False},ensure_ascii=False))
 return 2 if errors else 0
if __name__=="__main__":sys.exit(main())
