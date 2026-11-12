#!/usr/bin/env python3
"""Fast V5 diagnosis: classify frozen V3 exceptions; read only bounded representative
TDCC HTML samples to compare filename date/code against page's selected controls.
No file is silently declared a listed/OTC security; no v0.93/V3 mutation.
"""
import os,re,json,html
from collections import Counter,defaultdict
from datetime import datetime,timezone
from scripts.v097_bronze_first_pipeline import common,match,load_json,put_once,service,call
from scripts.v097_bronze_first_batch_v3 import ck_name
RUN=os.getenv("GITHUB_RUN_ID","manual")
SAMPLE_CAP=min(12,max(0,int(os.getenv("V5_SAMPLE_PER_LANE","6"))))
TDCC_NAME=re.compile(r"^(?:distribution|tdcc)[_-](\d{8})[_-]([A-Za-z0-9]{4,6})_",re.I)
def now():return datetime.now(timezone.utc).isoformat()
def parse_identity(name,path):
    m=TDCC_NAME.match(str(name))
    if not m:return {"reason":"FILENAME_IDENTITY_UNKNOWN"}
    date,code=m.groups()
    month=re.search(r"/((?:19|20)\d{2})-(0[1-9]|1[0-2])/",str(path))
    if not month or date[:6]!=month.group(1)+month.group(2):return {"reason":"FILE_PERIOD_CONFLICT","date":date,"code":code}
    if not re.fullmatch(r"\d{4,6}",code):return {"reason":"ALPHANUMERIC_SECURITY_ID_NEEDS_MASTER","date":date,"code":code}
    return {"reason":"NUMERIC_ID_NEEDS_HISTORICAL_MASTER","date":date,"code":code}
def page_match(payload,code,date):
    if isinstance(payload,bytes):page=payload.decode("utf-8-sig",errors="replace")
    else:page=str(payload)
    sel=re.search(r'<option\s+value=["\']'+re.escape(date)+r'["\'][^>]*\bselected\b',page,re.I)
    stock=re.search(r'<input\b[^>]*\bid=["\']StockNo["\'][^>]*\bvalue=["\']([^"\']+)["\']',page,re.I)
    return {"selected_date_matches":bool(sel),
        "stock_no_matches":bool(stock and stock.group(1).upper()==code.upper()),
        "has_tdcc_table":bool(re.search(r"<table\b",page,re.I)),
        "source_url_verification":False,
        "historical_listed_otc_master_verified":False}
def lane(api,i):
    m,c,q,_=common(api)
    f=match(api,c,ck_name("COPY",i))
    if not f:raise RuntimeError("V3_COPY_LANE_MISSING")
    done=load_json(api,f["id"])["done"]
    exc=[(fid,row) for fid,row in done.items() if row.get("state")=="COPY_EXCEPTION"]
    counters=Counter();sample=[];examples=defaultdict(list)
    for fid,row in exc:
        e=str(row.get("error") or "")
        path=str(row.get("source_path") or "")
        fn=path.rsplit("/",1)[-1]
        if "TDCC_SYMBOL_DATE_NOT_EVIDENCED" in e:
            identity=parse_identity(fn,path)
            code=identity.get("reason","UNKNOWN")
            # sample proof through actual source bytes, without attempting to approve symbols
            if len(sample)<SAMPLE_CAP and code=="ALPHANUMERIC_SECURITY_ID_NEEDS_MASTER":
                obs={"file_id":fid,"source_path":path,"code":identity.get("code"),"date":identity.get("date")}
                try:
                    b=call(lambda:api.files().get_media(fileId=fid))
                    obs["html_observation"]=page_match(b,identity["code"],identity["date"])
                except Exception as ex:obs["html_read_error"]=type(ex).__name__
                sample.append(obs)
        elif "CONTROL_SIDECAR_NOT_MARKET_RAW" in e:code="CONTROL_SIDECAR_EXCLUDE"
        elif "429" in e or "HttpError" in e:code="TRANSIENT_EXISTING_V4"
        else:code="OTHER_UNRESOLVED"
        counters[code]+=1
        if len(examples[code])<3:examples[code].append({"id":fid,"path":path,"error":e[:150]})
    result={"schema":"v097_tdcc_fast_proof_v5_1","run":RUN,"lane":i,"utc":now(),
            "frozen_v3_exceptions":len(exc),"classification":dict(counters),
            "examples":dict(examples),"bounded_source_samples":sample,
            "passed_market_identity":0,"certified":False,
            "note":"TDCC filename+HTML agreement is evidence of internal consistency, NOT proof of valid historical TSE/OTC membership. Do not mass-copy alphanumeric symbols."}
    put_once(api,q,"v097_TDCC_V5_%s_L%02d.json"%(RUN,i),result)
    print("V5_LANE="+json.dumps({"lane":i,"exceptions":len(exc),"classification":dict(counters),
                                "source_samples":len(sample)},ensure_ascii=False),flush=True)
def aggregate(api):
    _,_,q,_=common(api)
    d=[];count=Counter();samples=[]
    for i in range(6):
        f=match(api,q,"v097_TDCC_V5_%s_L%02d.json"%(RUN,i))
        if not f:raise RuntimeError("V5_MISSING_LANE_%d"%i)
        row=load_json(api,f["id"]);d.append(row)
        count.update(row["classification"]);samples.extend(row["bounded_source_samples"])
    observation=Counter()
    for x in samples:
        h=x.get("html_observation") or {}
        if h:observation["all_three_html_checks_pass" if h["stock_no_matches"] and h["selected_date_matches"] and h["has_tdcc_table"] else "html_mismatch_or_missing"]+=1
        else:observation["html_read_failed"]+=1
    report={"schema":"v097_tdcc_v5_fast_diagnosis_1","run":RUN,"utc":now(),
      "frozen_v3_exceptions_total":sum(x["frozen_v3_exceptions"] for x in d),
      "by_identity_category":dict(count),"sample_count":len(samples),
      "sample_observations":dict(observation),"market_identity_certified":0,
      "official_downloads":0,"v093_untouched":True,"v3_checkpoints_untouched":True,
      "next_action":"VERIFY_HISTORICAL_TSE_OTC_SECURITY_MASTER_AND_TDCC_SOURCE_BEFORE_ANY_PROMOTION; KEEP_CONTROL_METADATA_OUTSIDE_MARKET_BRONZE",
      "samples":samples[:12],"bronze_final_certified":False}
    put_once(api,q,"v097_TDCC_V5_SUMMARY_%s.json"%RUN,report)
    print("V5_SUMMARY="+json.dumps({k:v for k,v in report.items() if k!="samples"},ensure_ascii=False),flush=True)
def selftest():
    a=parse_identity("distribution_20251107_YJR4_deadbeef.html","2025/TDCC/2025-11/distribution_20251107_YJR4_deadbeef.html")
    assert a["reason"]=="ALPHANUMERIC_SECURITY_ID_NEEDS_MASTER"
    assert parse_identity("distribution_20251107_2330_deadbeef.html","2025/TDCC/2025-11/x")["reason"]=="NUMERIC_ID_NEEDS_HISTORICAL_MASTER"
    assert parse_identity("distribution_20251031_2330_deadbeef.html","2025/TDCC/2025-11/x")["reason"]=="FILE_PERIOD_CONFLICT"
    print("V5_SELFTEST_PASS")
if __name__=="__main__":
    mode=os.getenv("V5_MODE","selftest")
    if mode=="selftest":selftest()
    elif mode=="lane":lane(service(),int(os.environ["V5_LANE"]))
    elif mode=="aggregate":aggregate(service())
    else:raise SystemExit("BAD_MODE")
