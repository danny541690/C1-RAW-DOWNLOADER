#!/usr/bin/env python3
"""Incremental ALL-row *close column* witness for TWSE/TPEx.

Unlike the legacy one-sample witness, this enumerates every eligible original
ZIP/JSON member and row before comparing a bounded batch of dated securities
to *separately fetched* official exchange and FinMind historical observations.
It is intentionally NOT an all-field, all-dataset, PIT, or Silver release.
"""
import os,sys,io,json,zipfile,hashlib,time
from collections import Counter
from scripts.v097_bronze_autopilot import source_api,digest
from scripts.v097_live_threeway_close_witness import (
 original_quotes,day,num,official_close,finmind_close)
from scripts.v097_seven_native_v2_probe import checkpoint_commit
MAX_ZIP=55*1024*1024
MAX_ARCHIVE_UNPACKED=200*1024*1024
MAX_MEMBERS=1200
MAX_ROW_PAIRS=max(1,min(35,int(os.getenv("EQUITY_CLOSE_ROW_BATCH","8"))))
def enumerate_close_rows(blob):
 if len(blob)>MAX_ZIP:raise ValueError("ARCHIVE_INPUT_LIMIT")
 if not zipfile.is_zipfile(io.BytesIO(blob)):
  out=original_quotes(blob)
  if len(out)>=10000:raise ValueError("POSSIBLY_TRUNCATED_ORIGINAL_ROWS")
  return out
 with zipfile.ZipFile(io.BytesIO(blob)) as z:
  infos=[m for m in z.infolist() if not m.is_dir()]
  if len(infos)>MAX_MEMBERS or sum(m.file_size for m in infos)>MAX_ARCHIVE_UNPACKED:
   raise ValueError("ZIP_MEMBER_OR_EXPANSION_LIMIT")
  manifest={}
  for m in infos:
   if m.filename.rsplit("/",1)[-1].lower()=="manifest.json":
    if m.file_size>4*1024*1024:raise ValueError("MANIFEST_TOO_BIG")
    manifest=json.loads(z.read(m))
  dates={}
  for u in manifest.get("units",[]) if isinstance(manifest,dict) else []:
   if isinstance(u,dict) and isinstance(u.get("file"),str):
    dates[u["file"]]=day(u.get("date","")) or day(u.get("period",""))
  all_rows=[]
  for m in infos:
   if m.filename.rsplit("/",1)[-1].lower()=="manifest.json":continue
   if not m.filename.lower().endswith((".json",".raw")):continue
   if m.file_size>25*1024*1024:raise ValueError("LARGE_UNEXAMINED_MEMBER")
   if m.filename.startswith("/") or ".." in m.filename.replace("\\","/").split("/"):
    raise ValueError("UNSAFE_ARCHIVE_PATH")
   rows=original_quotes(z.read(m),dates.get(m.filename))
   if len(rows)>=10000:raise ValueError("POSSIBLY_TRUNCATED_MEMBER_ROWS")
   all_rows.extend(rows)
 return all_rows
def fingerprint(rows):
 return hashlib.sha256(json.dumps(rows,sort_keys=True,separators=(",",":")).encode()).hexdigest()
def selftest():
 import zipfile
 raw=json.dumps({"date":"2026-11-16","tables":[{"fields":["證券代號","收盤價"],
 "data":[["2330","100"],["2317","200"]]}]},ensure_ascii=False).encode()
 assert len(enumerate_close_rows(raw))==2
 b=io.BytesIO()
 with zipfile.ZipFile(b,"w") as z:
  z.writestr("day1.json",raw)
  z.writestr("day2.json",raw)
 assert len(enumerate_close_rows(b.getvalue()))==4
 assert fingerprint(enumerate_close_rows(raw))==fingerprint(enumerate_close_rows(raw))
 print("EQUITY_ALL_ROW_CLOSE_WITNESS_SELFTEST_PASS")
def run(source):
 if source not in ("TWSE","TPEx"):raise ValueError("ONLY_TWO_EQUITY_MARKETS")
 api,control,quality,match,load_json,put_once,upsert,call=source_api()
 inf=match(api,quality,"v097_AP_INPUT_"+source+".json")
 nf=match(api,control,"v097_SEVEN_FORMAT_V2_CK_"+source+".json")
 if not inf or not nf:raise RuntimeError("ORIGINAL_OR_NATIVE_CK_MISSING")
 byid={r["source_id"]:r for r in load_json(api,inf["id"])["rows"]}
 v2=load_json(api,nf["id"])["done"]
 ckname="v097_EQUITY_FULL_CLOSE_ROWS_CK_"+source+".json"
 old=match(api,control,ckname)
 ck=load_json(api,old["id"]) if old else {"schema":"v097_equity_close_allrows_v1","source":source,"done":{}}
 if ck.get("schema")!="v097_equity_close_allrows_v1" or ck.get("source")!=source:
  raise RuntimeError("WITNESS_CK_VERSION_MISMATCH")
 done=ck["done"];attempted=0;matched=0
 # Always resume files with remaining rows, then move to never-inspected files.
 selection=sorted((sid for sid in v2 if sid in byid and
   (sid not in done or done[sid].get("status")=="PARTIAL_CLOSE_ROWS_PENDING")),
  key=lambda sid:(0 if sid in done else 1,sid))
 for sid in selection:
  if attempted>=MAX_ROW_PAIRS:break
  row=byid[sid]
  path=str(row.get("source_path","")).lower()
  if not path.endswith((".json",".raw",".zip")):continue
  entry=done.get(sid,{})
  try:
   blob=call(lambda:api.files().get_media(fileId=row["dest_id"]))
   if digest(blob)!=row["sha"]:raise RuntimeError("BRONZE_SHA_CONFLICT")
   quotes=enumerate_close_rows(blob)
   if not quotes:
    done[sid]={"status":"HOLD_NO_CLOSE_TABLE","source_sha256":row["sha"],"checked":0}
    continue
   fp=fingerprint(quotes)
   if entry.get("rows_sha256") and entry["rows_sha256"]!=fp:
    raise RuntimeError("ORIGINAL_ROW_SET_CHANGED")
   pos=int(entry.get("checked",0))
   if pos<0 or pos>len(quotes):raise RuntimeError("WITNESS_OFFSET_CORRUPT")
   mismatch=int(entry.get("mismatch",0)); remote_error=int(entry.get("remote_errors",0))
   while pos<len(quotes) and attempted<MAX_ROW_PAIRS:
    q=quotes[pos]
    attempted+=1
    try:
     official,op=official_close(source,q["stock"],q["date"])
     third,tp=finmind_close(q["stock"],q["date"])
    except Exception as e:
     remote_error+=1
     if remote_error>=3:
      done[sid]={"status":"HOLD_OFFICIAL_OR_PROVIDER_FETCH_RETRIES_EXHAUSTED",
       "source_sha256":row["sha"],"rows_sha256":fp,"checked":pos,
       "total":len(quotes),"remote_errors":remote_error,"error":type(e).__name__}
     else:
      done[sid]={"status":"PARTIAL_CLOSE_ROWS_PENDING","source_sha256":row["sha"],
        "rows_sha256":fp,"checked":pos,"total":len(quotes),
        "remote_errors":remote_error,"mismatch":mismatch}
     break
    if num(q["close"])!=official or num(q["close"])!=third:
     mismatch+=1
    else:matched+=1
    pos+=1
    time.sleep(0.25)
   else:
    done[sid]={"status":"CLOSE_COLUMN_COMPLETE_OTHER_FIELDS_AND_PIT_HOLD" if pos==len(quotes)
          and mismatch==0 else ("HOLD_CLOSE_VALUE_MISMATCH" if mismatch else "PARTIAL_CLOSE_ROWS_PENDING"),
      "source_sha256":row["sha"],"rows_sha256":fp,
      "checked":pos,"total":len(quotes),"mismatch":mismatch,"remote_errors":remote_error,
      "all_file_rows_close_compared":pos==len(quotes),"all_fields_verified":False,
      "published_at_verified":False,"silver_ready_promoted":False}
   # keep one file active per invocation to avoid huge Drive checkpoint changes.
   break
  except (ValueError,RuntimeError,zipfile.BadZipFile) as e:
   done[sid]={"status":"HOLD_FULL_CLOSE_EXTRACT_"+type(e).__name__,
      "source_sha256":row["sha"],"error":str(e)[:90],"silver_ready_promoted":False}
   break
 ck["last_run"]=os.getenv("GITHUB_RUN_ID","manual")
 if os.getenv("GITHUB_RUN_ID") and done:
  checkpoint_commit(api,control,ckname,ck,upsert,match,load_json)
 print("EQUITY_ALL_ROW_CLOSE_PROGRESS="+json.dumps({"source":source,
  "files_tracked":len(done),"rows_attempted":attempted,"rows_matched":matched,
  "statuses":dict(Counter(x["status"] for x in done.values())),
  "silver_promoted":0},ensure_ascii=False),flush=True)
if __name__=="__main__":
 if sys.argv[1:]==["selftest"]:selftest()
 elif len(sys.argv)==2:run(sys.argv[1])
 else:raise SystemExit("usage: selftest|TWSE|TPEx")
