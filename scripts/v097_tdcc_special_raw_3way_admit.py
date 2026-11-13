#!/usr/bin/env python3
"""Promote externally crosschecked TDCC SPECIAL-security HTML to isolated v097
non-common-stock raw evidence archive, NEVER to listed/OTC ordinary-stock Bronze.
Proof requires A4 original SHA+totals, thirdparty YYYYMMDD/code exact holders/shares,
V4 destination SHA and current source MD5+SHA. Idempotent per-file checkpoint.
"""
import os,re,json,hashlib
from collections import Counter
from datetime import datetime,timezone
from googleapiclient.http import MediaInMemoryUpload
from scripts.v097_bronze_first_pipeline import service,common,match,load_json,put_once,upsert,call,makefolder
RUN=os.getenv("GITHUB_RUN_ID","manual")
LANE=int(os.getenv("SPECIAL_RAW_LANE","0"))
CAP=max(1,min(90,int(os.getenv("SPECIAL_RAW_BATCH","28"))))
CROSS="v097_TDCC_5035_THIRDPARTY_ALL_43428270828.json"
NAME="v097_TDCC_SPECIAL_RAW_3WAY_QA_V1"
def sha(b):return hashlib.sha256(b).hexdigest()
def now():return datetime.now(timezone.utc).isoformat()
def valid_record(r):
    if r.get("result")!="THIRDPARTY_HOLDER_SHARE_EXACT":return False
    if not re.fullmatch(r"[A-Z0-9]{4,6}",str(r.get("code") or "")):return False
    if re.fullmatch(r"\d{4}",r["code"]):return False
    return (re.fullmatch(r"20\d{6}",str(r.get("day") or "")) is not None and
       re.fullmatch(r"[0-9a-f]{64}",str(r.get("source_sha256") or "")) is not None and
       isinstance(r.get("holders"),int) and isinstance(r.get("shares"),int))
def population(api,q):
    f=match(api,q,CROSS)
    if not f:raise RuntimeError("UNVERIFIED_MIRROR_REPORT_NOT_FOUND")
    all=load_json(api,f["id"])
    if all.get("population")!=5035:raise RuntimeError("CENSUS_NOT_5035")
    good=[r for r in all["records"] if valid_record(r)]
    if len(good)!=2377:raise RuntimeError("CROSS_SOURCE_PASS_COUNT_DIFFERENT_"+str(len(good)))
    if len({r["file_id"] for r in good})!=len(good):raise RuntimeError("DUPLICATE_SOURCE_ID")
    return good
def sha_lane(fid):return int(sha(fid.encode())[:8],16)%6
def archive_root(api,bronze):
    p=call(lambda:api.files().get(fileId=bronze,fields="parents")).get("parents",[])
    if len(p)!=1:raise RuntimeError("DATA_LAKE_PARENT_AMBIGUOUS")
    special=makefolder(api,p[0],"00_TDCC_SPECIAL_SECURITY_SIDECAR")
    return makefolder(api,special,"01_CROSSSOURCE_VALIDATED_NONSTOCK_RAW")
def bootstrap(api):
    m,c,q,bronze=common(api);root=archive_root(api,bronze)
    for lane in range(6):makefolder(api,root,"SPECIAL_LANE_%02d"%lane)
    print("SPECIAL_RAW_BOOTSTRAP_READY",flush=True)
def one(api,r,parent,stage):
    fid=r["file_id"];out={"file_id":fid,"date":r["day"],"code":r["code"],
      "ordinary_stock_bronze_admitted":False,
      "market_membership_certified":False}
    try:
        if stage.get("status")!="V097_V4_QUARANTINE_SHA_PASS" or stage.get("source_sha256")!=r["source_sha256"]:
            raise ValueError("V4_QUARANTINE_PROOF_CONFLICT")
        meta=call(lambda:api.files().get(fileId=fid,fields="name,size,md5Checksum"))
        fname=str(meta.get("name") or "")
        if ("_"+r["day"]+"_"+r["code"]+"_") not in fname:raise ValueError("ORIGINAL_FILENAME_CODE_DATE_CONFLICT")
        length=int(meta.get("size") or 0)
        if not 0<length<=4_000_000:raise ValueError("FILE_SIZE_NOT_SUPPORTED")
        raw=call(lambda:api.files().get_media(fileId=fid))
        q=call(lambda:api.files().get_media(fileId=stage["dest_id"]))
        if len(raw)!=length or sha(raw)!=r["source_sha256"] or sha(q)!=r["source_sha256"]:
            raise ValueError("ORIGINAL_QUARANTINE_BYTES_CHANGED")
        if meta.get("md5Checksum") and hashlib.md5(raw).hexdigest()!=meta["md5Checksum"]:
            raise ValueError("SOURCE_MD5_MISMATCH")
        name=fid+"__"+sha(raw)[:16]+"__"+fname
        f=match(api,parent,name)
        if not f:
            media=MediaInMemoryUpload(raw,mimetype="application/octet-stream",resumable=False)
            f=call(lambda:api.files().create(body={"name":name,"parents":[parent],
               "description":"JARVIS original TDCC HTML; SHA+holding totals independently mirrored. NONSTOCK only; NOT MARKET BRONZE"},
               media_body=media,fields="id,name"))
        dup=call(lambda:api.files().get_media(fileId=f["id"]))
        fm=call(lambda:api.files().get(fileId=f["id"],fields="name,parents"))
        if sha(dup)!=sha(raw) or len(dup)!=len(raw) or fm.get("parents")!=[parent] or fm.get("name")!=name:
            raise ValueError("INDEPENDENT_NONSTOCK_RAW_DESTINATION_QA_FAILED")
        out.update(state="NONSTOCK_RAW_SHA_AND_3WAY_HOLDINGS_QA_PASS",
           source_sha256=sha(raw),dest_id=f["id"],holders=r["holders"],shares=r["shares"])
    except Exception as exc:
        out.update(state="SPECIAL_RAW_HOLD",error=type(exc).__name__+":"+str(exc)[:170])
    return out
def lane(api,lane):
    m,c,q,bronze=common(api)
    rows=[r for r in population(api,q) if sha_lane(r["file_id"])==lane]
    root=archive_root(api,bronze)
    target=match(api,root,"SPECIAL_LANE_%02d"%lane)
    if not target:raise RuntimeError("BOOTSTRAP_NOT_READY")
    ckname=NAME+"_CK_%02d.json"%lane
    f=match(api,c,ckname)
    ck=load_json(api,f["id"]) if f else {"schema":"tdcc_special_raw_checkpoint_1","lane":lane,"done":{}}
    if ck.get("lane")!=lane or ck.get("schema")!="tdcc_special_raw_checkpoint_1":raise RuntimeError("CK_SCHEMA_CONFLICT")
    ids={r["file_id"] for r in rows}
    if not set(ck["done"]).issubset(ids):raise RuntimeError("CK_ORPHAN")
    todo=[r for r in rows if r["file_id"] not in ck["done"]][:CAP]
    stage_map={}
    for original_lane in range(6):
        f=match(api,c,"v097_V4_EXCEPTIONS_STAGED_V1_CK_%02d.json"%original_lane)
        if not f:raise RuntimeError("MISSING_V4_STAGE_CK")
        stage_map.update(load_json(api,f["id"])["done"])
    sig=sha("\n".join(r["file_id"] for r in todo).encode())[:12]
    name=NAME+"_"+RUN+"_L%02d_O%04d_%s.json"%(lane,len(ck["done"]),sig)
    f=match(api,q,name)
    if f:items=load_json(api,f["id"])["items"]
    else:
        items=[one(api,r,target["id"],stage_map.get(r["file_id"],{})) for r in todo]
        put_once(api,q,name,{"schema":"tdcc_special_raw_receipt_1","run":RUN,"lane":lane,
            "items":items,"ordinary_stock_bronze_promoted":0})
    for item in items:
        ck["done"][item["file_id"]]={"state":item["state"],"dest_id":item.get("dest_id"),"error":item.get("error")}
    upsert(api,c,ckname,dict(ck,last_receipt=name,updated_at=now()))
    states=Counter(x["state"] for x in ck["done"].values())
    print("SPECIAL_RAW_LANE="+json.dumps({"lane":lane,"eligible":len(rows),"checked":len(ck["done"]),
        "remaining":len(rows)-len(ck["done"]),"states":dict(states)},ensure_ascii=False),flush=True)
def summary(api):
    m,c,q,_=common(api);n=0;state=Counter()
    for laneid in range(6):
        f=match(api,c,NAME+"_CK_%02d.json"%laneid)
        d=load_json(api,f["id"])["done"] if f else {}
        n+=len(d);state.update(x["state"] for x in d.values())
    report={"schema":"v097_tdcc_special_original_3way_summary_1","run":RUN,
       "eligible":2377,"checked":n,"remaining":2377-n,
       "by_state":dict(state),"listed_otc_market_bronze_promotions":0,
       "special_raw_3way_pass":state["NONSTOCK_RAW_SHA_AND_3WAY_HOLDINGS_QA_PASS"]}
    put_once(api,q,NAME+"_SUMMARY_"+RUN+".json",report)
    print("SPECIAL_RAW_SUMMARY="+json.dumps(report,ensure_ascii=False),flush=True)
if __name__=="__main__":
 mode=os.getenv("SPECIAL_RAW_MODE","selftest")
 if mode=="selftest":
    assert sha_lane("abc") in range(6)
    print("SPECIAL_RAW_SELFTEST_PASS")
 else:
    api=service()
    if mode=="bootstrap":bootstrap(api)
    elif mode=="lane":lane(api,LANE)
    elif mode=="summary":summary(api)
    else:raise SystemExit("BAD_MODE")
