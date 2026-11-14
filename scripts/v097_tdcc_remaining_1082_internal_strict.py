#!/usr/bin/env python3
"""TDCC 1084 special-security raw Bronze original admission, with explicit
EXTERNAL_WITNESS_PENDING label. Strict source/original/quarantine SHA,
original HTML code/date, 15-16 detailed levels, holders/shares conservation,
official-style % consistency, source identity and restore readback. This is
a provenance-preserving RAW layer only; not cross-source certification, not
listed/OTC ordinary stocks, not release, not Silver or Gold.
"""
import os,json,re,hashlib
from collections import Counter
from datetime import datetime,timezone
from decimal import Decimal
from googleapiclient.http import MediaInMemoryUpload
from scripts.v097_bronze_first_pipeline import service,common,match,load_json,put_once,upsert,call,makefolder
from scripts.v097_tdcc_a3_a5_auto import html_identity,table_diagnostics,assess,FILE
from scripts.v097_tdcc_special_raw_3way_admit import archive_root,sha_lane
RUN=os.getenv("GITHUB_RUN_ID","manual")
LANE=int(os.getenv("TDCC_1084_LANE","0"));LIMIT=max(1,min(55,int(os.getenv("TDCC_1084_BATCH","25"))))
NAME="v097_TDCC_1084_INTERNAL_PROOF_RAW"
REPORT="v097_TDCC_5035_THIRDPARTY_ALL_43428270828.json"
def sha(x):return hashlib.sha256(x).hexdigest()
def now():return datetime.now(timezone.utc).isoformat()
def get(api,folder,name):
 f=match(api,folder,name)
 return load_json(api,f["id"]) if f else {}
def population(api,c,q):
 frozen=get(api,q,REPORT)
 if frozen.get("population")!=5035:raise RuntimeError("CENSUS_MISSING")
 mapping={}
 for n in range(6):
  for fid,rec in get(api,c,"v097_TDCC_800_REVERIFY_V1_CK_%02d.json"%n).get("done",{}).items():
   if fid in mapping:raise RuntimeError("RECOVERY_DUPLICATE")
   mapping[fid]=rec
 official={}
 for n in range(6):
  d=get(api,c,"v097_TDCC_2025_OFFICIAL_HISTORY_PROOFS_CK_%02d.json"%n).get("done",{})
  for fid,rec in d.items():
   if fid in official:raise RuntimeError("OFFICIAL_CHECKPOINT_DUPLICATE")
   official[fid]=rec
 rows=[]
 for r in frozen["records"]:
  condition=((r["result"]=="THIRDPARTY_DATE_NOT_AVAILABLE" and
               official.get(r["file_id"],{}).get("state")=="DATE_NOT_AVAILABLE_IN_OFFICIAL_HISTORY_WINDOW") or
             (r["result"]=="A4_NUMERIC_RECEIPT_NOT_FOUND" and
               mapping.get(r["file_id"],{}).get("state")=="ORIGINAL_INTERNAL_QA_PASS_EXTERNAL_DATE_NOT_AVAILABLE"))
  if not condition:continue
  rr=dict(r)
  if not rr.get("source_sha256"):
   rec=mapping.get(rr["file_id"],{})
   rr.update(source_sha256=rec.get("sha"),holders=rec.get("holders"),shares=rec.get("shares"))
  if not re.fullmatch(r"[0-9a-f]{64}",str(rr.get("source_sha256") or "")):
   raise RuntimeError("MISSING_ORIGINAL_SHA:"+rr["file_id"])
  if not isinstance(rr.get("holders"),int) or not isinstance(rr.get("shares"),int):
   raise RuntimeError("MISSING_HOLDING_NUMERICS:"+rr["file_id"])
  rows.append(rr)
 if len(rows)!=1082:raise RuntimeError("EXPECTED_1082_WITHOUT_TWO_OFFICIAL_ERRORS_GOT_"+str(len(rows)))
 return rows
def stage_map(api,c):
 stage={}
 for i in range(6):
  d=get(api,c,"v097_V4_EXCEPTIONS_STAGED_V1_CK_%02d.json"%i).get("done",{})
  if set(stage)&set(d):raise RuntimeError("V4_STAGE_DUPLICATES")
  stage.update(d)
 return stage
def folder(api,bronze):
 top=archive_root(api,bronze)
 return makefolder(api,top,"04_INTERNAL_PROOF_EXTERNAL_PENDING_RAW")
def bootstrap(api):
 _,_,_,bronze=common(api);p=folder(api,bronze)
 for lane in range(6):makefolder(api,p,"LANE_%02d"%lane)
 print("TDCC_1084_INTERNAL_BOOTSTRAP_OK",flush=True)
def validate_levels(raw):
 from bs4 import BeautifulSoup
 soup=BeautifulSoup(raw.decode("utf-8-sig",errors="strict"),"html.parser")
 target=next((t for t in soup.select("table") if "持股/單位數分級" in t.get_text(" ",strip=True) and "股數/單位數" in t.get_text(" ",strip=True)),None)
 if target is None:raise ValueError("TDCC_DISTRIBUTION_TABLE_MISSING")
 rows=[]
 for tr in target.select("tr"):
  vals=[x.get_text(" ",strip=True).replace(",","") for x in tr.find_all("td",recursive=False)]
  if len(vals)!=5 or not vals[0].strip().isdigit():continue
  level=int(vals[0])
  if not (1<=level<=17):raise ValueError("LEVEL_OUT_OF_RANGE")
  h=int(vals[2].strip());shares=int(vals[3].strip());pct=Decimal(vals[4].strip())
  if h<0 or shares<0 or pct<0 or pct>Decimal("100.1"):raise ValueError("NEGATIVE_OR_EXCESSIVE_PERCENT")
  rows.append((level,h,shares,pct,vals[1]))
 if len(rows) not in (16,17):raise ValueError("LEVEL_COUNT_NOT_16_17")
 if len({r[0] for r in rows})!=len(rows):raise ValueError("DUPLICATE_HOLDING_LEVEL")
 total=next((r for r in rows if "合計" in "".join(r[4].split())),None)
 if total is None or total[0] not in (16,17):raise ValueError("HTML_SUM_TOTAL_NOT_FOUND")
 levels=[x for x in rows if x[0]!=total[0]]
 if sum(x[1] for x in levels)!=total[1] or sum(x[2] for x in levels)!=total[2]:
  raise ValueError("HOLDER_SHARE_CONSERVATION_FAIL")
 if abs(sum(x[3] for x in levels)-total[3])>Decimal("0.12"):
  raise ValueError("PERCENTAGE_SUM_DIFFERENCE")
 if total[3] < 0 or total[3]>Decimal("100.1"):raise ValueError("TOTAL_PERCENTAGE_INVALID")
 return {"levels":len(rows),"holders":total[1],"shares":total[2],
  "percentage_total":str(total[3]),"detail_percentage_sum":str(sum(x[3] for x in levels))}
def process(api,r,stage,output):
 fid=r["file_id"];result={"file_id":fid,"date":r["day"],"code":r["code"],
   "external_witness_certified":False,"ordinary_stock_bronze":False}
 try:
  s=stage.get(fid,{})
  if s.get("status")!="V097_V4_QUARANTINE_SHA_PASS" or s.get("source_sha256")!=r["source_sha256"]:
   raise ValueError("V4_STAGE_OR_HASH_INVALID")
  meta=call(lambda:api.files().get(fileId=fid,fields="name,size,md5Checksum"))
  if ("_"+r["day"]+"_"+r["code"]+"_") not in str(meta.get("name") or ""):
   raise ValueError("FILENAME_DATE_CODE_MISMATCH")
  raw=call(lambda:api.files().get_media(fileId=fid))
  quarantined=call(lambda:api.files().get_media(fileId=s["dest_id"]))
  if sha(raw)!=r["source_sha256"] or sha(quarantined)!=sha(raw) or len(raw)!=int(meta.get("size") or 0):
   raise ValueError("SOURCE_QUARANTINE_SHA_NOT_EQUAL")
  if meta.get("md5Checksum") and hashlib.md5(raw).hexdigest()!=meta["md5Checksum"]:
   raise ValueError("ORIGINAL_MD5_NOT_EQUAL")
  contentcode,dates,table=html_identity(raw)
  if contentcode!=r["code"] or r["day"] not in dates or not table:
   raise ValueError("HTML_CONTENT_IDENTITY_OR_DATE_MISSING")
  metrics=validate_levels(raw)
  if metrics["holders"]!=r["holders"] or metrics["shares"]!=r["shares"]:
   raise ValueError("INDEPENDENT_LEVEL_SUM_OR_HISTORIC_A4_MISMATCH")
  name=fid+"__"+sha(raw)[:16]+"__"+meta["name"]
  existing=match(api,output,name)
  if not existing:
   media=MediaInMemoryUpload(raw,mimetype="application/octet-stream",resumable=False)
   existing=call(lambda:api.files().create(body={"name":name,"parents":[output],
    "description":"RAW special security TDCC original: sha+identity+17-level totals+% QA. EXTERNAL_WITNESS_PENDING. Not ordinary stock or full release."},
    media_body=media,fields="id,name"))
  copied=call(lambda:api.files().get_media(fileId=existing["id"]))
  dm=call(lambda:api.files().get(fileId=existing["id"],fields="name,parents"))
  if sha(copied)!=sha(raw) or dm.get("parents")!=[output] or dm.get("name")!=name:
   raise ValueError("DESTINATION_SHA_NAME_FOLDER_NOT_MATCHED")
  result.update(state="SPECIAL_RAW_INTERNAL_STRICT_QA_PASS_EXTERNAL_PENDING",
    dest_id=existing["id"],source_sha256=sha(raw),metrics=metrics)
 except Exception as e:result.update(state="ORIGINAL_DATA_QA_HOLD",error=type(e).__name__+":"+str(e)[:170])
 return result
def lane(api,n):
 m,c,q,bronze=common(api)
 rows=[r for r in population(api,c,q) if sha_lane(r["file_id"])==n]
 root=folder(api,bronze)
 dest=match(api,root,"LANE_%02d"%n)
 if not dest:raise RuntimeError("NO_BOOTSTRAP")
 name=NAME+"_CK_%02d.json"%n
 ck=get(api,c,name) or {"schema":"v097_tdcc_internal_strict_ck_1","lane":n,"done":{}}
 if ck["lane"]!=n or ck["schema"]!="v097_tdcc_internal_strict_ck_1":raise RuntimeError("CHECKPOINT_BAD")
 if not set(ck["done"]).issubset({r["file_id"] for r in rows}):raise RuntimeError("CHECKPOINT_ORPHAN")
 todo=[r for r in rows if r["file_id"] not in ck["done"] or (ck["done"][r["file_id"]].get("state")=="ORIGINAL_DATA_QA_HOLD" and ck["done"][r["file_id"]].get("retry_version")!="HTML_SUM_UNICODE_V4")][:LIMIT]
 stages=stage_map(api,c)
 receipt=NAME+"_"+RUN+"_L%02d_O%04d_%s.json"%(n,len(ck["done"]),sha("\n".join(r["file_id"] for r in todo).encode())[:12])
 old=match(api,q,receipt)
 if old:results=load_json(api,old["id"])["rows"]
 else:
  results=[process(api,r,stages,dest["id"]) for r in todo]
  put_once(api,q,receipt,{"schema":"v097_tdcc_internal_strict_receipt_1","run":RUN,
     "lane":n,"rows":results,"external_witness_certified":False})
 for x in results:ck["done"][x["file_id"]]={"state":x["state"],"dest_id":x.get("dest_id"),"error":x.get("error"),"retry_version":"HTML_SUM_UNICODE_V4"}
 upsert(api,c,name,dict(ck,updated_at=now(),last_receipt=receipt))
 st=Counter(x["state"] for x in ck["done"].values())
 err=Counter(x.get("error","") for x in ck["done"].values() if x.get("state")=="ORIGINAL_DATA_QA_HOLD")
 print("TDCC_INTERNAL_STRICT_LANE="+json.dumps({"lane":n,"total":len(rows),"checked":len(ck["done"]),
    "remaining":len(rows)-len(ck["done"]),"by_state":dict(st),"hold_reasons":dict(err.most_common(6))},ensure_ascii=False),flush=True)
def summary(api):
 m,c,q,_=common(api);s=Counter();checked=0;eligible=0
 for n in range(6):
  eligible+=len([r for r in population(api,c,q) if sha_lane(r["file_id"])==n])
  d=get(api,c,NAME+"_CK_%02d.json"%n).get("done",{})
  checked+=len(d);s.update(x["state"] for x in d.values())
 report={"schema":"v097_tdcc_internal_strict_summary_1","run":RUN,"eligible":eligible,
   "checked":checked,"remaining":eligible-checked,"by_state":dict(s),
   "special_raw_internal_pass_external_pending":s["SPECIAL_RAW_INTERNAL_STRICT_QA_PASS_EXTERNAL_PENDING"],
   "ordinary_stock_bronze":0,"external_witness_certified":0}
 put_once(api,q,NAME+"_SUMMARY_"+RUN+".json",report)
 print("TDCC_INTERNAL_STRICT_SUMMARY="+json.dumps(report,ensure_ascii=False),flush=True)
if __name__=="__main__":
 mode=os.getenv("TDCC_STRICT_MODE","selftest")
 if mode=="selftest":
  assert sha_lane("abc") in range(6)
  print("TDCC_INTERNAL_STRICT_SELFTEST_PASS")
 else:
  api=service()
  if mode=="bootstrap":bootstrap(api)
  elif mode=="lane":lane(api,LANE)
  elif mode=="summary":summary(api)
  else:raise SystemExit("BAD_MODE")
