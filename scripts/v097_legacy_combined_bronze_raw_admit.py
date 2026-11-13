#!/usr/bin/env python3
"""JARVIS v0.97 incremental Bronze original raw admission for 1094 parsed TPEx/MOPS.
Only source bytes that pass independent parsed-data identity, schema, value,
date and SHA checks may enter EXISTING 01_BRONZE_ORIGINAL. Originals remain
immutable. Distinguish Bronze RAW QA from separate dataset/PIT/Gold release.
"""
import os,re,json,hashlib
from decimal import Decimal,InvalidOperation
from collections import Counter
from datetime import datetime,timezone
from googleapiclient.http import MediaInMemoryUpload
from scripts.v097_bronze_first_pipeline import service,common,match,load_json,put_once,upsert,call,partition,raw_integrity
from scripts.v097_bronze_first_batch_v3 import qa_one
from scripts.v097_tpex_rsta3104_recovery import candidates as tpex_candidates
from scripts.v097_mops_html_matrix_recovery import candidates as mops_candidates
RUN=os.getenv("GITHUB_RUN_ID","manual")
LANE=int(os.getenv("LEGACY_BRONZE_LANE","0"))
BATCH=max(1,min(150,int(os.getenv("LEGACY_BRONZE_BATCH","90"))))
NAME="v097_LEGACY_COMBINED_BRONZE_RAW_V1"
def sha(b):return hashlib.sha256(b).hexdigest()
def now():return datetime.now(timezone.utc).isoformat()
def getck(api,c,name):
    f=match(api,c,name)
    return load_json(api,f["id"])["done"] if f else {}
def candidates(api,m,c,lane):
    out=[]
    specs=[
       ("TPEx",tpex_candidates,"v097_TPEX_LEGACY_RSTA3104_V1","v097_LEGACY_TPEX_MOPS_V2_TPEx"),
       ("MOPS",mops_candidates,"v097_MOPS_HTML_MATRIX_QA_V1","v097_LEGACY_TPEX_MOPS_V2_MOPS")
    ]
    for source,fn,base,legacy in specs:
        v1=getck(api,c,base+"_CK_%02d.json"%lane)
        v2=getck(api,c,legacy+"_CK_%02d.json"%lane)
        for row,rawqa,fmt in fn(api,m,c,lane):
            fid=row["file_id"];a=v1.get(fid,{}) ;b=v2.get(fid,{})
            if source=="TPEx" and (b.get("state")=="LEGACY_PARSED_STAGED_PIT_PENDING" or a.get("status")=="TPEX_RSTA3104_PARSE_QA_PASS_PIT_PENDING"):
                dest=b.get("dest_id") or a.get("parsed_dest_id")
            elif source=="MOPS" and (b.get("state")=="LEGACY_PARSED_STAGED_PIT_PENDING" or a.get("status")=="MOPS_MATRIX_QA_PASS_STAGED_PIT_PENDING"):
                dest=b.get("dest_id") or a.get("parsed_dest_id")
            else:continue
            if not dest:raise RuntimeError("PASS_WITHOUT_STAGE_DEST:"+fid)
            out.append({"file_id":fid,"lane":lane,"source":source,
                "source_row":row,"original_qa":fmt,"staged_id":dest})
    ids=[x["file_id"] for x in out]
    if len(ids)!=len(set(ids)):raise RuntimeError("CROSS_SOURCE_DUPLICATE")
    return out
def decimal(v):
    if v is None:return None
    d=Decimal(str(v))
    if not d.is_finite():raise ValueError("NONFINITE")
    return d
def numeric_check(doc,source,yearmonth):
    if doc.get("source_file_id") is None:raise ValueError("STAGE_NO_ORIGINAL_LINK")
    if source=="TPEx":
        trade_date=doc.get("date") or doc.get("report_date")
        if not isinstance(trade_date,str) or not trade_date.startswith(yearmonth+"-"):
            raise ValueError("TPEx_ORIGINAL_DATE_MISMATCH")
        rows=doc.get("records") or []
        if not isinstance(rows,list) or len(rows)<30:raise ValueError("TPEx_DATA_ROWS_TOO_FEW")
        if doc.get("records_count",doc.get("row_count"))!=len(rows):raise ValueError("TPEx_RECORDED_ROW_COUNT")
        seen=set()
        for r in rows:
            code=str(r.get("code") or r.get("stock_code") or "")
            if not re.fullmatch(r"\d{4}",code) or code in seen:raise ValueError("TPEx_NONFOUR_OR_DUPLICATE_CODE")
            seen.add(code)
            lo=decimal(r.get("low"));hi=decimal(r.get("high"))
            op=decimal(r.get("open"));cl=decimal(r.get("close"))
            vol=decimal(r.get("shares"));turn=decimal(r.get("turnover_twd"))
            if vol is None or turn is None or vol<0 or turn<0:raise ValueError("TPEx_NEGATIVE_VOLUME_AMOUNT")
            if lo is not None and hi is not None and lo>0 and hi>0:
                if lo>hi:raise ValueError("TPEx_BAD_HIGH_LOW")
                for x in (op,cl):
                    if x is not None and x>0 and (x<lo or x>hi):
                        raise ValueError("TPEx_OPEN_CLOSE_OUTSIDE_RANGE")
        return len(rows)
    if source=="MOPS":
        if doc.get("dataset_type")=="MOPS_FINANCIAL_HTML_MATRIX":
            if doc.get("source_month")!=yearmonth or doc.get("unit")!="TWD_THOUSAND":
                raise ValueError("MOPS_MATRIX_PERIOD_OR_UNIT")
            companies=doc.get("companies") or []
            rows=doc.get("rows") or []
            if len(companies)<1 or len(rows)<5 or len({x.get("code") for x in companies})!=len(companies):
                raise ValueError("MOPS_MATRIX_SHAPE")
            if doc.get("company_count")!=len(companies) or doc.get("account_count")!=len(rows):
                raise ValueError("MOPS_MATRIX_COUNT")
            nonempty=0
            for r in rows:
                values=r.get("values_thousand_twd") or []
                if len(values)!=len(companies):raise ValueError("MOPS_MATRIX_WIDTH")
                for x in values:
                    if x is not None:decimal(x);nonempty+=1
            if nonempty<1:raise ValueError("MOPS_ALL_EMPTY")
            return nonempty
        elif doc.get("report_type")=="MOPS_BIG5_MONTHLY_REVENUE":
            if doc.get("revenue_month")!=yearmonth or doc.get("unit")!="TWD_THOUSAND":
                raise ValueError("MOPS_REVENUE_PERIOD_OR_UNIT")
            records=doc.get("records") or []
            if len(records)<1 or doc.get("records_count")!=len(records):
                raise ValueError("MOPS_REVENUE_COUNT")
            seen=set()
            for r in records:
                code=str(r.get("code") or "")
                if not re.fullmatch(r"\d{4}",code) or code in seen:raise ValueError("MOPS_REVENUE_DUPLICATE")
                seen.add(code)
                if decimal(r.get("monthly_thousand")) is None:raise ValueError("MOPS_MONTHLY_MISSING")
            return len(records)
        else:raise ValueError("UNKNOWN_MOPS_DATASET_TYPE")
    raise ValueError("UNKNOWN_SOURCE")
def one(api,bronze,record):
    row=record["source_row"];fid=record["file_id"];lane=record["lane"];source=record["source"]
    result={"file_id":fid,"source":source,"source_path":row.get("path"),
        "repaired_stage_id":record["staged_id"],"formal_dataset_release_certified":False,
        "historical_publication_date_certified":False,"v093_original_untouched":True}
    try:
        ym=str(row.get("month") or "")
        year=str(row.get("year") or "")
        name=str(row.get("file_name") or "")
        if not re.fullmatch(r"(19|20)\d{2}-(0[1-9]|1[0-2])",ym) or ym[:4]!=year:
            raise ValueError("ORIGINAL_YEAR_MONTH")
        if not str(row.get("path") or "").startswith(year+"/"+source+"/"+ym+"/"):
            raise ValueError("ORIGINAL_SOURCE_PATH")
        fmt=record["original_qa"]
        prior_sha=fmt.get("sha256")
        if not re.fullmatch(r"[0-9a-f]{64}",str(prior_sha or "")):
            raise ValueError("NO_ORIGINAL_FORMAT_QA_SHA")
        parsedbytes=call(lambda:api.files().get_media(fileId=record["staged_id"]))
        staged=json.loads(parsedbytes.decode("utf-8"))
        if staged.get("source_file_id")!=fid or staged.get("source_sha256")!=prior_sha:
            raise ValueError("REPAIRED_STAGE_SOURCE_PROVENANCE_CONFLICT")
        count=numeric_check(staged,source,ym)
        meta=call(lambda:api.files().get(fileId=fid,fields="id,name,size,md5Checksum,parents"))
        if meta.get("name")!=name:raise ValueError("SOURCE_NAME_CHANGED")
        raw=call(lambda:api.files().get_media(fileId=fid))
        if len(raw)!=int(meta.get("size") or 0) or sha(raw)!=prior_sha:
            raise ValueError("SOURCE_SHA_OR_SIZE_CHANGED")
        if meta.get("md5Checksum") and hashlib.md5(raw).hexdigest()!=meta["md5Checksum"]:
            raise ValueError("SOURCE_MD5_CHANGED")
        if raw_integrity(raw,name)!="RAW_STRUCTURE_PASS":
            raise ValueError("SOURCE_NATIVE_RAW_STRUCTURE_NOT_VALID")
        # Raw immutable destination: same established 74,750 accepted RAW-bronze format.
        destfolder=partition(api,bronze,row,lane)
        destname=fid+"__"+prior_sha[:16]+"__"+name.replace("/","_")
        found=match(api,destfolder,destname)
        if not found:
            media=MediaInMemoryUpload(raw,mimetype="application/octet-stream",resumable=False)
            found=call(lambda:api.files().create(body={"name":destname,"parents":[destfolder],
                "description":"JARVIS v0.97 raw Bronze byte/path/numeric QA, source="+fid+"; not fully PIT/release-certified"},
                media_body=media,fields="id,name"))
        qa=qa_one(api,fid,{"state":"COPY_MATCHED_PENDING_INDEPENDENT_QA",
            "sha":prior_sha,"dest_id":found["id"],"dest_folder_id":destfolder,
            "dest_path":"/".join([source,"BF_LANE_%02d"%lane,year,ym[-2:],destname])},lane)
        if qa.get("state")!="BRONZE_BYTE_PROVENANCE_AND_PATH_PASS":
            raise ValueError("INDEPENDENT_RAW_BRONZE_SHA:"+str(qa.get("error")))
        result.update(state="BRONZE_ORIGINAL_RAW_QA_PASS_RELEASE_PENDING",
            bronze_file_id=found["id"],bronze_sha256=prior_sha,
            numerical_cells_or_rows_checked=count,
            dataset_type=staged.get("dataset_type") or staged.get("report_type") or staged.get("schema"),
            original_format_state=fmt.get("state"))
    except Exception as exc:
        result.update(state="HOLD_COMBINED_QA_NOT_RELEASED",
            error=type(exc).__name__+":"+str(exc)[:180])
    return result
def lane(api,lane):
    m,c,q,bronze=common(api)
    eligible=candidates(api,m,c,lane)
    key=NAME+"_CK_%02d.json"%lane
    ckf=match(api,c,key)
    ck=load_json(api,ckf["id"]) if ckf else {"schema":"v097_combined_raw_qa_1","lane":lane,"done":{}}
    if ck.get("schema")!="v097_combined_raw_qa_1" or ck.get("lane")!=lane:
        raise RuntimeError("WRONG_COMBINED_QA_CHECKPOINT")
    known={x["file_id"] for x in eligible}
    if not set(ck["done"]).issubset(known):raise RuntimeError("COMBINED_QA_ORPHAN")
    todo=[x for x in eligible if x["file_id"] not in ck["done"]][:BATCH]
    sig=sha("\n".join(x["file_id"] for x in todo).encode())[:12]
    receipt=NAME+"_"+RUN+"_L%02d_O%04d_%s.json"%(lane,len(ck["done"]),sig)
    f=match(api,q,receipt)
    if f:results=load_json(api,f["id"])["rows"]
    else:
        results=[one(api,bronze,x) for x in todo]
        put_once(api,q,receipt,{"schema":"v097_combined_raw_batch_receipt_1","run":RUN,"lane":lane,
           "rows":results,"full_release_certified":0,"no_v093_mutations":True})
    for x in results:
        ck["done"][x["file_id"]]={"state":x["state"],"bronze_file_id":x.get("bronze_file_id"),
            "reason":x.get("error"),"dataset_type":x.get("dataset_type")}
    upsert(api,c,key,dict(ck,last_receipt=receipt,updated_at=now()))
    st=Counter(x["state"] for x in ck["done"].values())
    print("COMBINED_RAW_QA_LANE="+json.dumps({"lane":lane,"seen":len(ck["done"]),
        "eligible":len(eligible),"remaining":len(eligible)-len(ck["done"]),
        "states":dict(st)},ensure_ascii=False),flush=True)
def summary(api):
    m,c,q,bronze=common(api)
    state=Counter();source=Counter();expected=completed=0
    for laneid in range(6):
        eligible=candidates(api,m,c,laneid)
        ids={x["file_id"] for x in eligible}
        f=match(api,c,NAME+"_CK_%02d.json"%laneid)
        done=load_json(api,f["id"])["done"] if f else {}
        if not set(done).issubset(ids):raise RuntimeError("INVALID_FINAL_CHECKPOINT")
        for x in eligible:
            if x["file_id"] in done:
                source[x["source"]+"__"+done[x["file_id"]]["state"]]+=1
        completed+=len(done);expected+=len(eligible)
        state.update(x["state"] for x in done.values())
    if expected!=1094:raise RuntimeError("EXPECTED_1094_PARSED_RESIDUALS_GOT_"+str(expected))
    report={"schema":"v097_combined_raw_bronze_report_1","run":RUN,
        "expected":expected,"checked":completed,"remaining":expected-completed,
        "by_state":dict(state),"by_source_and_state":dict(source),
        "new_or_existing_raw_bronze_pass":state["BRONZE_ORIGINAL_RAW_QA_PASS_RELEASE_PENDING"],
        "blocked":state["HOLD_COMBINED_QA_NOT_RELEASED"],
        "full_market_source_publication_PIT_release_certified":0,
        "silver_gold_promoted":0,"original_093_modified":False}
    put_once(api,q,NAME+"_SUMMARY_"+RUN+".json",report)
    print("COMBINED_RAW_QA_SUMMARY="+json.dumps(report,ensure_ascii=False),flush=True)
def selftest():
    assert numeric_check({"source_file_id":"f","date":"2005-10-06","records_count":30,
      "records":[{"code":str(1000+i),"open":"10","high":"11","low":"9","close":"10",
       "shares":"1000","turnover_twd":"10000"} for i in range(30)]},"TPEx","2005-10")==30
    print("COMBINED_RAW_QA_SELFTEST_PASS",flush=True)
if __name__=="__main__":
    mode=os.getenv("COMBINED_QA_MODE","selftest")
    if mode=="selftest":selftest()
    else:
        api=service()
        if mode=="lane":lane(api,LANE)
        elif mode=="summary":summary(api)
        else:raise SystemExit("BAD_COMBINED_MODE")
