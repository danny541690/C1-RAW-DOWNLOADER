#!/usr/bin/env python3
"""JARVIS v0.97: matched-date Bronze versus sourced historical native dataset.
TDCC: official dataset 1-5 archived weekly CSV (third-party preservation).
TAIFEX: official historical LargeTraderFut POST for exact existing Bronze dates.
This is source QA only. Official G2 certificate remains pending independent issuer/PIT proof.
"""
import collections,csv,hashlib,io,json,os,re,sys
from datetime import datetime,timezone
from scripts.v097_v3_preflight import read_baseline,assert_cohort,source_api,canonical
from scripts.v097_two_source_native_date_diff import tdcc_native
SOURCE="v097_two_source_exact_date_backcheck_r1"
RUN=os.getenv("GITHUB_RUN_ID","manual")
TDCC_WEEK="20261008"
TDCC_CODES=("2365","3258")
TDCC_ARCHIVE_URL="https://raw.githubusercontent.com/wirelessr/tdcc-opendata-archive/main/snapshots/2026/2026-10-08.csv"
TDCC_ORIGINAL_ISSUER="https://openapi.tdcc.com.tw/v1/opendata/1-5"
TAIFEX_DATE_START="2024/01/02"
TAIFEX_DATE_END="2024/01/04"
TAIFEX_OFFICIAL="https://www.taifex.com.tw/cht/3/largeTraderFutDown"
TAIFEX_LANDING="https://www.taifex.com.tw/cht/3/largeTraderFutView"
TAIFEX_SID="1V3tY6CRlSB6JjOYld8sFPxmv2vDdg3tu"
CAP=30*1024*1024

def sha(b):return hashlib.sha256(b).hexdigest()
def norm_header(s):return re.sub(r"[\s_\u3000（）()%％]+","",str(s).replace("\ufeff","")).lower()
def norm_cell(x):return str(x).strip().replace("\u3000"," ").replace("\ufeff","").strip()
def compact(r):
    rr=[norm_cell(v) for v in r]
    while rr and not rr[-1]:rr.pop()
    return rr
def fetch_official(url,method="get",data=None):
    import requests
    try:
        session=requests.Session()
        kw=dict(timeout=(10,60),allow_redirects=True)
        response=session.get(url,**kw) if method=="get" else session.post(url,data=data,headers={
           "Referer":TAIFEX_LANDING,"Origin":"https://www.taifex.com.tw",
           "User-Agent":"Mozilla/5.0 JARVIS-v097-source-audit"},**kw)
        response.raise_for_status()
        if len(response.content)>CAP:raise ValueError("HTTP_RESPONSE_OVER_CAP")
        return {"status":"FETCHED","final_url":response.url,"http_status":response.status_code,
            "sha256":sha(response.content),"byte_count":len(response.content),
            "content_type":response.headers.get("Content-Type","")},response.content
    except Exception as ex:
        return {"status":"SOURCE_HTTP_HOLD","error_type":type(ex).__name__,
                "error":str(ex)[:200],"requested_url":url},None
def csv_decode(blob,prefer=("utf-8-sig","cp950","big5")):
    if not blob:return None,None
    for enc in prefer:
        try:return list(csv.reader(io.StringIO(blob.decode(enc)))),enc
        except (UnicodeError,csv.Error):continue
    return None,None
def tdcc_source(rows,api,call):
    url=TDCC_ARCHIVE_URL
    remote,blob=fetch_official(url)
    raw_rows,enc=csv_decode(blob)
    if raw_rows:
        header=[norm_header(v) for v in raw_rows[0]]
        keys=["資料日期","證券代號","持股分級","人數","股數","占集保庫存數比例%"]
        matched={}
        for target in keys:
            n=norm_header(target)
            matched[target]=next((j for j,v in enumerate(header) if v==n),None)
        if any(v is None for v in matched.values()):
            remote["status"]="OFFICIAL_ARCHIVE_FIELDS_MISSING"
            remote["columns"]=raw_rows[0][:25]
            raw_rows=None
    else:
        remote["status"]=remote["status"] if remote["status"]!="FETCHED" else "ARCHIVED_CSV_DECODE_HOLD"
    result=[]
    for code in TDCC_CODES:
        original=next((r for r in rows if "distribution_"+TDCC_WEEK+"_"+code+"_" in str(r.get("source_path",""))),None)
        if not original:
            result.append({"code":code,"date":TDCC_WEEK,"status":"FROZEN_BRONZE_EXACT_DATE_CODE_NOT_FOUND"});continue
        b=call(lambda:api.files().get_media(fileId=original["destination_id"]))
        sha_match=sha(b)==original["source_sha256"]
        native=tdcc_native(b)
        proof={"source_id":original["source_id"],"sha_match":sha_match,
            "native_header":native.get("header"),
            "native_row_count":native.get("data_rows"),
            "native_layout":native.get("layout"),
            "native_tier1":native.get("first_three",[])[:1],
            "native_last":native.get("last_two",[])[-1:],
            "native_total_holders":native.get("total_holders"),
            "native_total_shares":native.get("total_shares")}
        if not sha_match:proof["status"]="BRONZE_SHA_HOLD"
        elif not raw_rows:proof["status"]="ARCHIVE_UNAVAILABLE_OR_SCHEMA_HOLD"
        else:
            col=matched
            subset=[r for r in raw_rows[1:] if len(r)>max(col.values()) and
                re.sub(r"\D","",r[col["資料日期"]])==TDCC_WEEK and
                norm_cell(r[col["證券代號"]]).upper()==code]
            official_by_tier={norm_cell(r[col["持股分級"]]):r for r in subset}
            diffs=[]
            for native_row in native.get("all_rows",[]):
                seq=native_row[0]
                source_seq="17" if seq=="16" and native.get("layout")=="HTML_15_TIERS_TOTAL" else seq
                official_row=official_by_tier.get(source_seq)
                if not official_row:
                    diffs.append({"tier":seq,"status":"OFFICIAL_ARCHIVE_TIER_MISSING"});continue
                fields={
                    "人數":(native_row[2],official_row[col["人數"]]),
                    "股數":(native_row[3],official_row[col["股數"]]),
                    "比例":(native_row[4],official_row[col["占集保庫存數比例%"]])
                }
                mismatches={}
                for field,(a,bv) in fields.items():
                    if field=="比例":
                        try:equal=abs(float(a.replace(",",""))-float(bv.replace(",","")))<0.011
                        except ValueError:equal=False
                    else:equal=a.replace(",","").strip()==bv.replace(",","").strip()
                    if not equal:mismatches[field]={"bronze":a,"historical_official_archive":bv}
                if mismatches:diffs.append({"tier":seq,"mismatches":mismatches})
            proof["archived_rows_same_date"]=len(subset)
            proof["row_differences"]=diffs[:30]
            proof["full_native_tier_rows_checked"]=len(native.get("all_rows",[]))
            proof["status"]="ARCHIVED_OFFICIAL_DATASET_SAME_DATE_NUMERIC_MATCH" if len(subset)>=16 and not diffs else "SAME_DATE_NUMERIC_OR_TEMPLATE_HOLD"
        result.append(proof)
    return {"dataset":"TDCC_SHAREHOLDING_DISTRIBUTION",
        "historical_origin_kind":"THIRD_PARTY_ARCHIVE_OF_OFFICIAL_OPEN_DATA",
        "source_url":url,"underlying_issuer":TDCC_ORIGINAL_ISSUER,
        "official_original_publication_sha_certified":False,
        "source_response":remote,"csv_encoding":enc,"cases":result,
        "formal_g2_certified":False}
def taifex_source(rows,api,call):
    source=next((r for r in rows if r["source_id"]==TAIFEX_SID),None)
    if not source:return {"status":"FROZEN_SOURCE_ID_MISSING"}
    raw=call(lambda:api.files().get_media(fileId=source["destination_id"]))
    sha_ok=sha(raw)==source["source_sha256"]
    baseline,base_enc=csv_decode(raw,("cp950","utf-8-sig","big5"))
    remote,official_bytes=fetch_official(TAIFEX_OFFICIAL,"post",{
        "queryStartDate":TAIFEX_DATE_START,"queryEndDate":TAIFEX_DATE_END})
    other,official_enc=csv_decode(official_bytes,("cp950","utf-8-sig","big5"))
    result={"dataset":"TAIFEX_LARGE_TRADER_FUTURES","source_id":TAIFEX_SID,
        "bronze_sha_verified":sha_ok,"bronze_encoding":base_enc,
        "bronze_rows_including_notes":len(baseline or []),
        "request_window":[TAIFEX_DATE_START,TAIFEX_DATE_END],
        "official_response":remote,"official_csv_encoding":official_enc,
        "historical_2024_contemporaneous_PIT_proven":False}
    if not sha_ok or not baseline:
        result["status"]="BRONZE_READ_OR_SHA_HOLD";return result
    target={"2024/01/02","2024/01/03","2024/01/04"}
    native_date=[compact(x) for x in baseline if x and norm_cell(x[0]) in target]
    result["original_csv_header"]=compact(baseline[0])
    result["native_rows_by_day"]=dict(collections.Counter(v[0] for v in native_date))
    result["native_examples"]=native_date[:3]
    result["original_notes_first3"]=[compact(x) for x in baseline if x and
        not re.fullmatch(r"\d{4}/\d{2}/\d{2}",norm_cell(x[0]))][:3]
    if not other:
        result["status"]="OFFICIAL_SAME_DATE_DOWNLOAD_HOLD"
        return result
    their_date=[compact(x) for x in other if x and norm_cell(x[0]) in target]
    their_counts=collections.Counter(tuple(v) for v in their_date)
    our_counts=collections.Counter(tuple(v) for v in native_date)
    first_only=list((our_counts-their_counts).elements())
    second_only=list((their_counts-our_counts).elements())
    result.update({"official_csv_header":compact(other[0]),"official_rows_by_day":
       dict(collections.Counter(v[0] for v in their_date)),
       "count_bronze":len(native_date),"count_official":len(their_date),
       "bronze_only_rows_first5":first_only[:5],"official_only_rows_first5":second_only[:5],
       "normalized_multiset_equal":our_counts==their_counts})
    result["status"]="SAME_DATE_ALL_NATIVE_ROWS_MATCH" if our_counts==their_counts and bool(our_counts) else "OFFICIAL_NATIVE_DIFFERENCES"
    result["formal_g2_certified"]=False
    return result
def run(source):
    api,control,quality,match,load_json,put_once,upsert,call=source_api()
    rows=read_baseline(api,quality,match,load_json,source)
    assert_cohort(rows,source)
    info=tdcc_source(rows,api,call) if source=="TDCC" else taifex_source(rows,api,call)
    record={"schema":SOURCE,"source":source,"run":RUN,
        "time_utc":datetime.now(timezone.utc).isoformat(),
        "result":info,"formal_g2_new_pass":0,
        "bronze_modified":False,"silver_gold_materialized":False}
    rid=put_once(api,quality,"v097_EXACT_DATE_ORIGINAL_SOURCE_COMPARE_"+source+"_"+RUN+".json",record)
    upsert(api,control,"v097_EXACT_DATE_ORIGINAL_SOURCE_COMPARE_"+source+"_LATEST.json",
        {"schema":SOURCE,"source":source,"run":RUN,"report_id":rid,
         "status":"COMPARED_OR_HOLD_NO_OFFICIAL_G2_PROMOTION"})
    print("MATCHED_ORIGINAL_SOURCE="+canonical({
        "source":source,"report_id":rid,"run":RUN,
        "overall":info.get("status"),
        "counts":dict(collections.Counter(c.get("status") for c in info.get("cases",[]))),
        "formal_G2_new_pass":0}),flush=True)
def selftest():
    assert len(TDCC_CODES)==2 and len({TAIFEX_DATE_START,TAIFEX_DATE_END})==2
    assert compact(["1","2","",""])==["1","2"]
    assert norm_header("\ufeff占集保庫存數比例 (%)")==norm_header("占集保庫存數比例%")
    assert {"2024/01/02","2024/01/03","2024/01/04"}=={TAIFEX_DATE_START,TAIFEX_DATE_END,"2024/01/03"}
    print("G2_MATCHED_DATE_SOURCE_DIFF_SELFTEST_PASS")
if __name__=="__main__":
    if sys.argv[1:]==["selftest"]:selftest()
    elif len(sys.argv)==3 and sys.argv[1]=="source" and sys.argv[2] in ("TDCC","TAIFEX"):run(sys.argv[2])
    else:raise SystemExit("selftest | source TDCC/TAIFEX")
