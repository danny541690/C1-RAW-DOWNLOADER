#!/usr/bin/env python3
"""JARVIS v097 PRE-SILVER Schema Mapping lane v1.
Reads frozen 74750 baseline, V2 / V21 format evidence. NEVER executes Silver/Gold.
No Bronze download or mutation; exact header-only matching is a candidate, never formal release.
"""
import collections,hashlib,json,os,re,sys
from datetime import datetime,timezone
from scripts.v097_schema_gate_v21 import (SOURCES,PLAN,VERSION as PROFILE_VERSION,CONTRACT as PROFILE_CONTRACT,
    read_baseline,existing_v2,lane,reused,source_api,END)
from scripts.v097_seven_historical_format_registry import OFFICIAL_VERSIONS,period

VERSION="v097_silver_schema_mapping_v1_20261117"
CONTRACT="20261117-pre-silver-field-map-v1"
RUN=os.getenv("GITHUB_RUN_ID","manual")
BATCH=max(10,min(250,int(os.getenv("MAPPING_BATCH","150"))))
CK_PREFIX="v097_SCHEMA_MAPPING_V1_CK_"
DONE={"HEADER_MATCHED_UNCERTIFIED","MAPPING_HEADER_PENDING","MAPPING_DATASET_PENDING",
      "MAPPING_MEMBERS_PENDING","MAPPING_FORMAT_EXCEPTION","MAPPING_BROnZE_HOLD",
      "MAPPING_NEEDS_SOURCE_EVIDENCE","MAPPING_PROFILE_STALE"}
MATCH_FIELDS={
 "STOCK_DAILY_OHLCV":{
   "date":["日期","交易日期","資料日期","date","trade_date","datetime"],
   "code":["證券代號","股票代號","股票代碼","代號","stock_id","stockid","code"],
   "close":["收盤價","收盤","close","closing_price"]},
 "MONTHLY_REVENUE":{
   "code":["公司代號","證券代號","股票代號","stock_id","code"],
   "period":["年月","資料年月","營收月份","month","period"],
   "revenue":["營業收入","當月營收","營收","revenue"]},
 "FUTURES_DAILY":{
   "date":["日期","交易日期","date","trade_date"],
   "contract":["契約","契約名稱","契約代號","商品代號","contract","product_id"],
   "volume":["成交量","成交口數","成交股數","volume","trade_volume"]}
}
ALLOW={
 "TWSE":{"STOCK_DAILY_OHLCV"},
 "TPEx":{"STOCK_DAILY_OHLCV"},
 "MOPS":{"MONTHLY_REVENUE"},
 "TDCC":set(),
 "TAIFEX":{"FUTURES_DAILY"},
 "NDC":set(),
 "FinMind":{"STOCK_DAILY_OHLCV"}
}
def now():return datetime.now(timezone.utc).isoformat()
def digest(obj):return hashlib.sha256(json.dumps(obj,ensure_ascii=False,sort_keys=True,separators=(",",":")).encode()).hexdigest()
def norm(x):return re.sub(r"[\s_\u3000（）()]+","",str(x)).lower()
def header_mapping(fields,kind):
    if not fields or kind not in MATCH_FIELDS:return None
    words={norm(x):str(x) for x in fields if isinstance(x,(str,int))}
    out={}
    for target,aliases in MATCH_FIELDS[kind].items():
        found=next((words[norm(a)] for a in aliases if norm(a) in words),None)
        if found is None:return None
        out[target]=found
    if len(set(out.values()))!=len(out):return None
    return out
def guessed_dataset(src,profile):
    d=str(profile.get("dataset_candidate") or profile.get("dataset") or "").lower()
    if src in ("TWSE","TPEx") and any(x in d for x in ("stock_day","quotes","daily","ohlcv")):
        return "STOCK_DAILY_OHLCV"
    if src=="FinMind" and d in ("taiwanstockprice","stock_price"):
        return "STOCK_DAILY_OHLCV"
    if src=="MOPS" and any(x in d for x in ("revenue","monthly")):
        return "MONTHLY_REVENUE"
    if src=="TAIFEX" and any(x in d for x in ("futures_daily","future","fut_daily")):
        return "FUTURES_DAILY"
    return None
def evaluate(src,profile,source_sha):
    if not profile:return {"status":"MAPPING_PROFILE_PENDING","reason":"FORMAT_PROFILE_NOT_READY"}
    if profile.get("sha")!=source_sha:
        return {"status":"MAPPING_PROFILE_STALE","reason":"PROFILE_SHA_MISMATCH"}
    status=profile.get("status","")
    if status in ("BLOCKED_BRONZE","FORMAT_STRUCTURAL_HOLD","SOURCE_READ_FAILED_FINAL",
                  "FORMAT_RESOURCE_LIMIT","FORMAT_UNSUPPORTED"):
        return {"status":"MAPPING_FORMAT_EXCEPTION","reason":status,"profile_reason":profile.get("reason")}
    sig=str(profile.get("signature") or "")
    era=str(profile.get("historical_version") or "UNKNOWN_PERIOD")
    if not era or era.startswith("UNKNOWN") or era=="HISTORICAL_VERSION_UNKNOWN":
        return {"status":"MAPPING_NEEDS_SOURCE_EVIDENCE","reason":"HISTORICAL_SCHEMA_VERSION_UNKNOWN"}
    if era not in {p["id"] for p in OFFICIAL_VERSIONS[src]["periods"]}:
        return {"status":"MAPPING_NEEDS_SOURCE_EVIDENCE","reason":"UNRECOGNIZED_HISTORICAL_VERSION"}
    if sig=="ZIP":
        return {"status":"MAPPING_MEMBERS_PENDING","reason":"ZIP_MEMBER_HEADERS_NOT_ATTESTED",
                "member_count":profile.get("members"),"era":era}
    if sig in ("XLSX","PDF","HTML_XML") or sig.startswith("XLS"):
        return {"status":"MAPPING_HEADER_PENDING","reason":"NATIVE_TABLE_FIELD_PROOF_REQUIRED",
                "signature":sig,"era":era}
    dataset=guessed_dataset(src,profile)
    if not dataset or dataset not in ALLOW[src]:
        return {"status":"MAPPING_DATASET_PENDING","reason":"SOURCE_DATASET_IDENTITY_NOT_PROVEN",
                "dataset_candidate":profile.get("dataset_candidate"),"signature":sig,"era":era}
    # Reuse an actual observed header. A guessed dataset plus aliases is NOT certified.
    header=profile.get("header") or []
    if not header and isinstance(profile.get("mapping"),dict):
        header=list(profile["mapping"].values())
    if not header and isinstance(profile.get("keys"),list):
        header=profile["keys"]
    mp=header_mapping(header,dataset)
    if not mp:return {"status":"MAPPING_HEADER_PENDING","reason":"REQUIRED_SOURCE_FIELDS_MISSING_OR_UNPROVEN",
                      "dataset_candidate":dataset,"era":era}
    return {"status":"HEADER_MATCHED_UNCERTIFIED","dataset_candidate":dataset,"era":era,
            "mapping":mp,"mapping_rule_version":CONTRACT,
            "reason":"FIELD_NAMES_ONLY; dataset identity, types, units, PIT and complete rows not attested",
            "silver_input_ready_certified":False}
def profile_of(sid,row,v2,v21):
    a=v21.get(sid)
    if a and a.get("sha")==row["source_sha256"] and a.get("contract_version")==PROFILE_CONTRACT and a.get("status") in END:
        return a
    b=v2.get(sid)
    if reused(b,row):return b
    return None
def source(src):
    if src not in SOURCES:raise ValueError(src)
    api,control,quality,match,load_json,put_once,upsert,call=source_api()
    rows=read_baseline(api,quality,match,load_json,src)
    v2=existing_v2(api,control,match,load_json,src)
    v21={}
    for shard in range(PLAN[src]):
        f=match(api,control,"v097_SCHEMA_V21_SHARD_"+src+"_"+str(shard)+".json")
        if not f:continue
        ck=load_json(api,f["id"])
        if ck.get("schema")!=PROFILE_VERSION or ck.get("shard")!=shard:raise RuntimeError("PROFILE_SHARD_VERSION_CONFLICT")
        for sid,p in ck.get("done",{}).items():
            if sid in v21 or lane(sid,PLAN[src])!=shard:raise RuntimeError("PROFILE_SHARD_DUPLICATE")
            v21[sid]=p
    ckname=CK_PREFIX+src+".json"
    f=match(api,control,ckname)
    ck=load_json(api,f["id"]) if f else {"schema":VERSION,"source":src,"done":{},"run_history":[]}
    if ck.get("schema")!=VERSION:raise RuntimeError("MAPPING_CHECKPOINT_VERSION_CONFLICT")
    done=ck["done"]
    baseline_ids={r["source_id"] for r in rows}
    if set(done)-baseline_ids:raise RuntimeError("MAPPING_CHECKPOINT_ORPHAN")
    todo=[]
    for r in rows:
        sid=r["source_id"]
        p=profile_of(sid,r,v2,v21)
        if not p:continue
        evidence_fp=digest({"sha":r["source_sha256"],"status":p.get("status"),
                            "contract":p.get("contract_version"),"era":p.get("historical_version"),
                            "signature":p.get("signature"),"header":p.get("header"),
                            "mapping":p.get("mapping"),"keys":p.get("keys"),
                            "dataset":p.get("dataset_candidate") or p.get("dataset")})
        prior=done.get(sid)
        if prior and prior.get("evidence_fingerprint")==evidence_fp and prior.get("contract_version")==CONTRACT:continue
        todo.append((r,p,evidence_fp))
    new={}
    for r,p,fp in todo[:BATCH]:
        sid=r["source_id"]
        result=evaluate(src,p,r["source_sha256"])
        new[sid]={**result,"source_id":sid,"source":src,"sha":r["source_sha256"],
                  "profile_run":p.get("run"),"profile_status":p.get("status"),
                  "evidence_fingerprint":fp,"contract_version":CONTRACT,"run":RUN,
                  "checked_at":now(),"silver_gold_executed":False,
                  "silver_input_ready_certified":False}
    if new:
        name="v097_SCHEMA_MAPPING_V1_DELTA_"+src+"_"+RUN+".json"
        fid=put_once(api,quality,name,{"schema":VERSION,"source":src,"run":RUN,"records":new})
        done.update(new);ck["done"]=done;ck["last_run"]=RUN;ck["updated_at"]=now()
        ck["run_history"]=(ck.get("run_history",[])+[{"run":RUN,"delta_id":fid,"n":len(new)}])[-150:]
        upsert(api,control,ckname,ck)
        rf=match(api,control,ckname)
        if not rf or len(load_json(api,rf["id"]).get("done",{}))!=len(done):
            raise RuntimeError("MAPPING_CHECKPOINT_READBACK_MISMATCH")
    print("SCHEMA_MAPPING_PROGRESS="+json.dumps({"source":src,"run":RUN,"cohort":len(rows),
          "profiles_available":sum(bool(profile_of(r["source_id"],r,v2,v21)) for r in rows),
          "mapping_checked":len(done),"new":len(new),"statuses":dict(collections.Counter(x["status"] for x in done.values()))},ensure_ascii=False),flush=True)
def final():
    api,control,quality,match,load_json,put_once,upsert,call=source_api()
    sources=[];counts=collections.Counter();total=0;errors=[]
    for src in SOURCES:
        rows=read_baseline(api,quality,match,load_json,src);total+=len(rows)
        v2=existing_v2(api,control,match,load_json,src)
        v21={}
        for shard in range(PLAN[src]):
            f=match(api,control,"v097_SCHEMA_V21_SHARD_"+src+"_"+str(shard)+".json")
            if not f:continue
            for sid,p in load_json(api,f["id"]).get("done",{}).items():
                if sid in v21:raise RuntimeError("PROFILE_DUPLICATE")
                v21[sid]=p
        f=match(api,control,CK_PREFIX+src+".json")
        done=load_json(api,f["id"]).get("done",{}) if f else {}
        c=collections.Counter();available=0
        for r in rows:
            sid=r["source_id"];p=profile_of(sid,r,v2,v21)
            if p:available+=1
            v=done.get(sid)
            if v and v.get("sha")==r["source_sha256"] and v.get("contract_version")==CONTRACT:
                c[v["status"]]+=1
                if v["status"] not in ("HEADER_MATCHED_UNCERTIFIED","MAPPING_HEADER_PENDING","MAPPING_DATASET_PENDING","MAPPING_MEMBERS_PENDING"):
                    errors.append({"source":src,"source_id":sid,"status":v["status"],"reason":v.get("reason")})
            else:c["MAPPING_NOT_CHECKED"]+=1
        if sum(c.values())!=len(rows):raise RuntimeError("MAPPING_SOURCE_COUNT_DRIFT")
        sources.append({"source":src,"cohort":len(rows),"format_profiles_available":available,
                        "mapping_checked":len(rows)-c["MAPPING_NOT_CHECKED"],"statuses":dict(c)})
        counts.update(c)
    if total!=74750:raise RuntimeError("MAPPING_COHORT_COUNT_CONFLICT")
    result={"schema":VERSION,"run":RUN,"cohort":total,"created_at":now(),
            "mapping_checked":total-counts["MAPPING_NOT_CHECKED"],
            "mapping_not_checked":counts["MAPPING_NOT_CHECKED"],"statuses":dict(counts),
            "sources":sources,"field_mapping_verified":0,"silver_input_ready_certified":0,
            "silver_materialized":0,"gold_materialized":0,
            "note":"Observed profile/header mapping CANDIDATES only. Every source-native mapping remains uncertified until dataset-era contracts and typed field evidence are proved."}
    err_id=put_once(api,quality,"v097_SCHEMA_MAPPING_V1_ERROR_LEDGER_"+RUN+".json",
                    {"schema":VERSION,"run":RUN,"count":len(errors),"records":errors})
    result["error_ledger_id"]=err_id
    rid=put_once(api,quality,"v097_SCHEMA_MAPPING_V1_MASTER_"+RUN+".json",result)
    upsert(api,control,"v097_SCHEMA_MAPPING_V1_MASTER_LATEST.json",{**result,"report_id":rid})
    f=match(api,control,"v097_SCHEMA_MAPPING_V1_MASTER_LATEST.json")
    if not f or load_json(api,f["id"]).get("run")!=RUN:raise RuntimeError("MAPPING_MASTER_READBACK")
    print("SCHEMA_MAPPING_MASTER="+json.dumps({**result,"report_id":rid,"sources":"seven"},ensure_ascii=False),flush=True)
def selftest():
    assert set(ALLOW)==set(SOURCES)
    assert header_mapping(["交易日期","證券代號","收盤價"],"STOCK_DAILY_OHLCV")=={"date":"交易日期","code":"證券代號","close":"收盤價"}
    assert header_mapping(["日期","證券代號"],"STOCK_DAILY_OHLCV") is None
    assert evaluate("TWSE",{"sha":"aa","status":"SCHEMA_PROFILED_NEEDS_MAPPING",
       "signature":"ZIP","historical_version":"TWSE_CLOSING_PAGE_MIXED_TABLES"},"aa")["status"]=="MAPPING_MEMBERS_PENDING"
    assert evaluate("TWSE",{"sha":"aa","status":"SCHEMA_PROFILED_NEEDS_MAPPING",
       "signature":"JSON","historical_version":"TWSE_CLOSING_PAGE_MIXED_TABLES",
       "dataset_candidate":"stock_day","header":["交易日期","證券代號","收盤價"]},"aa")["status"]=="HEADER_MATCHED_UNCERTIFIED"
    assert evaluate("TPEx",{"sha":"aa","status":"FORMAT_UNSUPPORTED",
       "reason":"CONTROL_RECEIPT_NOT_MARKET_DATA"},"aa")["status"]=="MAPPING_FORMAT_EXCEPTION"
    assert evaluate("NDC",None,"x")["status"]=="MAPPING_PROFILE_PENDING"
    print("SCHEMA_MAPPING_V1_SELFTEST_PASS")
if __name__=="__main__":
    if sys.argv[1:]==["selftest"]:selftest()
    elif sys.argv[1:]==["final"]:final()
    elif len(sys.argv)==2 and sys.argv[1] in SOURCES:source(sys.argv[1])
    else:raise SystemExit("selftest | SOURCE | final")
