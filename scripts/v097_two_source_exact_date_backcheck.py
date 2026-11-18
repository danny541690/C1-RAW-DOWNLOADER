#!/usr/bin/env python3
"""JARVIS v0.97: matched-date Bronze versus sourced historical native dataset.
TDCC: official dataset 1-5 archived weekly CSV (third-party preservation).
TAIFEX: official historical LargeTraderFut POST for exact existing Bronze dates.
Full-file audit does not imply entire 74,750-file corpus or R1 Master release.
"""
import collections,csv,hashlib,io,json,os,re,sys
from datetime import datetime,timezone
from scripts.v097_v3_preflight import read_baseline,assert_cohort,source_api,canonical
from scripts.v097_two_source_native_date_diff import tdcc_native
SOURCE="v097_two_source_exact_date_backcheck_r1"
RUN=os.getenv("GITHUB_RUN_ID","manual")
FULL_MODE=os.getenv("G2_FULL_FILE","0")=="1"
# 2026-11-18 small-sample rerun: only 2 TDCC codes + 3 TAIFEX dates;
# never expand to a full-cohort certification, Silver, or Gold in this workflow.
SAMPLE_SCOPE={"TDCC":{"week":"20261008","codes":["2365","3258"]},
              "TAIFEX":{"start":"2024/01/02","end":"2024/01/04","days":3}}

TDCC_WEEK="20261008"
TDCC_CODES=("2365","3258")
TDCC_ARCHIVE_URL="https://raw.githubusercontent.com/wirelessr/tdcc-opendata-archive/main/snapshots/2026/2026-10-08.csv"
TDCC_ORIGINAL_ISSUER="https://openapi.tdcc.com.tw/v1/opendata/1-5"
TAIFEX_DATE_START="2024/01/02"
TAIFEX_DATE_END="2024/01/31" if FULL_MODE else "2024/01/04"
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
        origin="https://www.tdcc.com.tw" if "tdcc.com.tw" in url else "https://www.taifex.com.tw"
        referer="https://www.tdcc.com.tw/portal/zh/smWeb/qryStock" if "tdcc.com.tw" in url else TAIFEX_LANDING
        response=session.get(url,**kw) if method=="get" else session.post(url,data=data,headers={
           "Referer":referer,"Origin":origin,
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
    # A successful HTTP 200 can still return a login/anti-bot HTML page.
    if blob[:4096].lstrip().lower().startswith((b"<!doctype html",b"<html",b"<?xml")):
        return None,"HTML_NOT_CSV"
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
    # Seek independent first-party TDCC historical HTML for the same date and code.
    # No guess-based certification on historical archive alone.
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
            all_compared_rows=[]
            for native_row in native.get("all_rows",[]):
                seq=native_row[0]
                source_seq="17" if seq=="16" and native.get("layout")=="HTML_15_TIERS_TOTAL" else seq
                official_row=official_by_tier.get(source_seq)
                if not official_row:
                    diffs.append({"tier":seq,"status":"OFFICIAL_ARCHIVE_TIER_MISSING"})
                    all_compared_rows.append({"tier":seq,"bronze":native_row,"official":None,"row_pass":False})
                    continue
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
                all_compared_rows.append({"tier":seq,"archive_tier":source_seq,
                                          "bronze":native_row,
                                          "official_archive":[official_row[col[z]] for z in
                                               ["持股分級","人數","股數","占集保庫存數比例%"]],
                                          "row_pass":not mismatches,"mismatches":mismatches})
                if mismatches:diffs.append({"tier":seq,"mismatches":mismatches})
            proof["all_rows_compared"]=all_compared_rows
            proof["archive_columns"]=["持股分級","人數","股數","占集保庫存數比例%"]
            proof["archived_rows_same_date"]=len(subset)
            proof["row_differences"]=diffs[:30]
            proof["full_native_tier_rows_checked"]=len(native.get("all_rows",[]))
            proof["status"]="ARCHIVED_OFFICIAL_DATASET_SAME_DATE_NUMERIC_MATCH" if len(subset)>=16 and len(all_compared_rows)==16 and not diffs else "SAME_DATE_NUMERIC_OR_TEMPLATE_HOLD"
        proof["g2_numeric_validation"]="PASS" if proof.get("status")=="ARCHIVED_OFFICIAL_DATASET_SAME_DATE_NUMERIC_MATCH" else "HOLD"
        if FULL_MODE and proof["g2_numeric_validation"]=="PASS":
            official_result={"verified":False,"attempts":[]}
            payload={"scaDates":TDCC_WEEK,"scaDate":TDCC_WEEK,"SqlMethod":"StockNo",
                     "StockNo":code,"radioStockNo":code,"REQ_OPR":"SELECT",
                     "clkStockNo":code,"StockName":"","clkStockName":""}
            for endpoint in ("https://s.tdcc.com.tw/portal/zh/smWeb/qryStock",
                             "https://www.tdcc.com.tw/portal/zh/smWeb/qryStock",
                             "https://original-www.tdcc.com.tw/portal/zh/smWeb/qryStock"):
                for method in ("post","get"):
                    if method=="post":
                        remote1,body1=fetch_official(endpoint,"post",payload)
                    else:
                        # First-party portal commonly renders a normal HTML form;
                        # GET is diagnostic, not proof if it returns blank query fields.
                        remote1,body1=fetch_official(endpoint,"get")
                    attempt={"url":endpoint,"method":method,"http":remote1,"layout":None}
                    if body1 and b"<table" in body1.lower():
                        candidate=tdcc_native(body1)
                        attempt["layout"]=candidate.get("layout")
                        attempt["native_row_count"]=len(candidate.get("all_rows",[]))
                        if (candidate.get("layout")==native.get("layout") and
                            candidate.get("all_rows")==native.get("all_rows") and
                            candidate.get("total_shares")==native.get("total_shares") and
                            candidate.get("total_holders")==native.get("total_holders")):
                            official_result={"verified":True,"url":endpoint,
                                "method":method,"response_sha":sha(body1),
                                "native_rows":len(candidate["all_rows"]),
                                "attempts":official_result["attempts"]+[attempt]}
                            break
                    official_result["attempts"].append(attempt)
                if official_result.get("verified"):break
            proof["first_party_historical_check"]=official_result
            proof["g2_file_result"]="G2_FILE_PASS" if official_result.get("verified") else "G2_FILE_HOLD_FIRST_PARTY"
        else:
            proof["g2_file_result"]="G2_SAMPLE_PASS" if proof["g2_numeric_validation"]=="PASS" else "G2_HOLD"
        proof["formal_g2_missing_evidence"]=["FIRST_PARTY_20261008_OFFICIAL_PUBLICATION_SHA","HISTORICAL_ASOF_ATTESTATION","R1_G2_PER_FILE_CERT"] if proof["g2_numeric_validation"]=="PASS" else ["NUMERIC_OR_LAYOUT_HOLD"]
        result.append(proof)
    return {"dataset":"TDCC_SHAREHOLDING_DISTRIBUTION",
        "historical_origin_kind":"THIRD_PARTY_ARCHIVE_OF_OFFICIAL_OPEN_DATA",
        "source_url":url,"underlying_issuer":TDCC_ORIGINAL_ISSUER,
        "official_original_publication_sha_certified":False,
        "source_response":remote,"csv_encoding":enc,"cases":result,
        "formal_g2_certified":False}
def taifex_source(rows,api,call,quality=None,match=None,load_json=None,put_once=None):
    source=next((r for r in rows if r["source_id"]==TAIFEX_SID),None)
    if not source:return {"status":"FROZEN_SOURCE_ID_MISSING"}
    raw=call(lambda:api.files().get_media(fileId=source["destination_id"]))
    sha_ok=sha(raw)==source["source_sha256"]
    baseline,base_enc=csv_decode(raw,("cp950","utf-8-sig","big5"))
    # Historical endpoint may decline a full month per request.
    # Fetch in bounded 3-trading-date windows; aggregate only successfully
    # decoded official responses with the same 10-column header.
    if FULL_MODE and baseline:
        from datetime import datetime as _datetime
        dates=sorted({norm_cell(x[0]) for x in baseline[1:] if x and
                     re.fullmatch(r"2024/01/\d{2}",norm_cell(x[0]))})
        chunks=[dates[i:i+3] for i in range(0,len(dates),3)]
        other=None
        remote={"status":"FETCHED","chunks":[],"official_endpoint":TAIFEX_OFFICIAL}
        official_enc=None
        for c in chunks:
            receipt_name="v097_G2_TAIFEX_OFFICIAL_LARGE_TRADER_202401_"+c[0].replace("/","")+ "_" + c[-1].replace("/","")+"_V1.json"
            cached=match(api,quality,receipt_name) if quality and match else None
            if cached:
                saved=load_json(api,cached["id"])
                if saved.get("dates")!=c or not saved.get("rows") or not saved.get("source_url"):
                    raise RuntimeError("TAIFEX_CHUNK_CK_INVALID")
                response=saved["response"]
                parsed=[saved["header"]]+saved["rows"]
                enc=saved["encoding"]
                from_cache=True
            else:
                from_cache=False
                parsed=None
                enc=None
                import time
                for attempt in range(3):
                    response,blob=fetch_official(TAIFEX_OFFICIAL,"post",{
                        "queryStartDate":c[0],"queryEndDate":c[-1]})
                    parsed,enc=csv_decode(blob,("cp950","utf-8-sig","big5"))
                    if parsed and len(parsed)>1:break
                    if attempt<2:time.sleep(3*(attempt+1))
                if parsed and len(parsed)>1 and quality and put_once:
                    wanted=set(c)
                    receipt={"schema":"v097_taifex_official_chunk_v1","dates":c,
                             "source_url":TAIFEX_OFFICIAL,"response":response,
                             "header":parsed[0],"encoding":enc,
                             "rows":[x for x in parsed[1:] if x and norm_cell(x[0]) in wanted]}
                    put_once(api,quality,receipt_name,receipt)
            
            step={"start":c[0],"end":c[-1],"response":response,
                  "csv_encoding":enc,"rows":len(parsed or []),"reused_checkpoint":from_cache}
            remote["chunks"].append(step)
            if not parsed or len(parsed)<2:
                remote["status"]="OFFICIAL_CHUNK_DOWNLOAD_HOLD"
                other=None
                break
            if other is None:
                other=[parsed[0]]
                official_enc=enc
            elif compact(parsed[0])!=compact(other[0]):
                remote["status"]="OFFICIAL_CHUNK_HEADER_CONFLICT"
                other=None
                break
            wanted=set(c)
            other.extend(x for x in parsed[1:] if x and norm_cell(x[0]) in wanted)
        remote["chunk_total"]=len(chunks)
        remote["chunk_success"]=sum(z["response"].get("status")=="FETCHED" and z["rows"]>1
                                    for z in remote["chunks"])
        remote["http_status"]=200 if remote["status"]=="FETCHED" else None
    else:
        remote,official_bytes=fetch_official(TAIFEX_OFFICIAL,"post",{
            "queryStartDate":TAIFEX_DATE_START,"queryEndDate":TAIFEX_DATE_END})
        other,official_enc=csv_decode(official_bytes,("cp950","utf-8-sig","big5"))
        if official_enc=="HTML_NOT_CSV":
            remote["status"]="OFFICIAL_HTTP_HTML_NOT_CSV"
    result={"dataset":"TAIFEX_LARGE_TRADER_FUTURES","source_id":TAIFEX_SID,
        "bronze_sha_verified":sha_ok,"bronze_encoding":base_enc,
        "bronze_rows_including_notes":len(baseline or []),
        "request_window":[TAIFEX_DATE_START,TAIFEX_DATE_END],
        "official_response":remote,"official_csv_encoding":official_enc,
        "historical_2024_contemporaneous_PIT_proven":False}
    if not sha_ok or not baseline:
        result["status"]="BRONZE_READ_OR_SHA_HOLD";return result
    original_days={norm_cell(x[0]) for x in baseline[1:]
                   if x and re.fullmatch(r"2024/01/\d{2}",norm_cell(x[0]))}
    target=(original_days if FULL_MODE else {"2024/01/02","2024/01/03","2024/01/04"})
    result["whole_file_target_dates"]=sorted(original_days)
    result["whole_file_target_date_count"]=len(original_days)
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
    if not their_date:
        result["status"]="OFFICIAL_RESPONSE_NO_MATCHED_DATE_ROWS"
        return result
    their_counts=collections.Counter(tuple(v) for v in their_date)
    our_counts=collections.Counter(tuple(v) for v in native_date)
    first_only=list((our_counts-their_counts).elements())
    second_only=list((their_counts-our_counts).elements())
    # Full row-level comparison is kept in immutable Drive QA, not reduced to sample snippets.
    all_pairs=[]
    for v in sorted(our_counts):
        copies=our_counts[v]
        count_other=their_counts.get(v,0)
        all_pairs.append({"columns":list(v),"bronze_count":copies,"official_count":count_other,
                          "row_pass":copies==count_other})
    for v in sorted(their_counts.keys()-our_counts.keys()):
        all_pairs.append({"columns":list(v),"bronze_count":0,"official_count":their_counts[v],
                          "row_pass":False})
    result["all_compared_rows"]=all_pairs
    result["unique_row_patterns_compared"]=len(all_pairs)
    result.update({"official_csv_header":compact(other[0]),"official_rows_by_day":
       dict(collections.Counter(v[0] for v in their_date)),
       "count_bronze":len(native_date),"count_official":len(their_date),
       "bronze_only_rows_first5":first_only[:5],"official_only_rows_first5":second_only[:5],
       "normalized_multiset_equal":our_counts==their_counts})
    result["status"]="SAME_DATE_ALL_NATIVE_ROWS_MATCH" if our_counts==their_counts and bool(our_counts) else "OFFICIAL_NATIVE_DIFFERENCES"
    result["g2_numeric_validation"]="PASS" if result["status"]=="SAME_DATE_ALL_NATIVE_ROWS_MATCH" else "HOLD"
    result["formal_g2_missing_evidence"]=["2024_CONTEMPORANEOUS_PUBLICATION_ASOF","INDEPENDENT_OFFICIAL_DATASET_ERA_ATTESTATION","R1_G2_PER_FILE_CERT"] if result["g2_numeric_validation"]=="PASS" else ["NUMERIC_OR_LAYOUT_HOLD"]
    if FULL_MODE:
        # All dated lines in the monthly Bronze CSV must be covered by the
        # first-party response; header and trailing documentation are excluded.
        non_date=[x for x in baseline[1:] if x and norm_cell(x[0]) and
                  not re.fullmatch(r"\d{4}/\d{2}/\d{2}",norm_cell(x[0]))]
        full_ok=(result["g2_numeric_validation"]=="PASS" and sha_ok and
            result.get("original_csv_header")==result.get("official_csv_header") and
            len(native_date)==sum(bool(x and norm_cell(x[0]) in original_days) for x in baseline) and
            not any(x[0] not in target for x in native_date) and
            len(target)>=15 and len(non_date)<=6)
        result["g2_file_result"]="G2_FILE_PASS" if full_ok else "G2_FILE_HOLD"
        result["full_month_compared_rows"]=len(native_date)
        result["trailing_note_rows_excluded"]=len(non_date)
        result["full_file_sha"]=sha(raw)
    result["formal_g2_certified"]=False
    return result
# Simplified G2 v2, limited to the exact same-date sample. Not a whole-file
# certificate when only a subset of a monthly Bronze file was verified.
G2_RULE_V2="v097_g2_source_date_headers_all_sample_cells_sha_v2"
def g2_v2_verdict(source,info):
    if source=="TDCC":
        cases=info.get("cases",[])
        ok=(info.get("dataset")=="TDCC_SHAREHOLDING_DISTRIBUTION" and
            info.get("source_response",{}).get("http_status")==200 and
            len(cases)==2 and all(
                c.get("sha_match") is True and c.get("native_row_count")==16
                and c.get("full_native_tier_rows_checked")==16
                and c.get("archived_rows_same_date")==17
                and c.get("g2_numeric_validation")=="PASS"
                and len(c.get("all_rows_compared",[]))==16
                and all(r.get("row_pass") is True for r in c["all_rows_compared"])
                for c in cases))
        return {"rule":G2_RULE_V2,"scope":"TDCC_20261008_2365_3258",
                "sample_result":"G2_SAMPLE_PASS" if ok else "G2_SAMPLE_HOLD",
                "sample_files_pass":2 if ok else 0,"sample_rows_pass":32 if ok else 0,
                "comparison_origin":"THIRD_PARTY_ARCHIVE_OF_OFFICIAL_OPEN_DATA",
                "official_first_party_comparison":False,
                "full_file_g2_pass":False,
                "reason":"Third-party historical copy matches all 16 native rows per file; official first-party same-week query not independently compared" if ok else "TDCC_SOURCE_SHA_LAYOUT_DATE_OR_VALUES_HOLD"}
    target={"2024/01/02":1150,"2024/01/03":1150,"2024/01/04":1150}
    ok=(info.get("dataset")=="TAIFEX_LARGE_TRADER_FUTURES" and
        info.get("bronze_sha_verified") is True and
        info.get("official_response",{}).get("http_status")==200 and
        info.get("g2_numeric_validation")=="PASS" and
        info.get("original_csv_header")==info.get("official_csv_header") and
        info.get("native_rows_by_day")==target and
        info.get("official_rows_by_day")==target and
        info.get("count_bronze")==3450 and info.get("count_official")==3450 and
        all(r.get("row_pass") is True for r in info.get("all_compared_rows",[])) and
        len(info.get("all_compared_rows",[]))==3450)
    return {"rule":G2_RULE_V2,"scope":"TAIFEX_LARGE_TRADER_20240102_20240104",
            "sample_result":"G2_SAMPLE_PASS" if ok else "G2_SAMPLE_HOLD",
            "sample_files_pass":0,"sample_rows_pass":3450 if ok else 0,
            "official_first_party_comparison":True,
            "full_file_g2_pass":False,
            "reason":"Same-date first-party official download matches three days, but original monthly Bronze file has additional days" if ok else "TAIFEX_SHA_HEADER_DATE_OR_VALUES_HOLD"}

def publish_g2_v2_full_file_certificates(source,rows,info,verdict,rid,
                                         api,control,match,load_json,upsert):
    """Only independently verified first-party full Bronze files are certified.

    No sample promotion. All certificates are bound to source_id, frozen SHA,
    official report ID, dataset and historically valid dataset era.
    """
    if verdict.get("full_file_result")!="G2_FILE_PASS" or not verdict.get("official_first_party_comparison"):
        return []
    from scripts.v097_seven_historical_format_registry import period
    candidates=info.get("cases",[]) if source=="TDCC" else [info]
    registry="v097_R1_G2_CERT_"+source+".json"
    found=match(api,control,registry)
    old=load_json(api,found["id"]) if found else {"schema":"R1_G2_DATASET_CERT_V2","source":source,"done":{}}
    if old.get("schema") not in ("R1_G2_DATASET_CERT_V1","R1_G2_DATASET_CERT_V2"):
        raise RuntimeError("G2_REGISTRY_SCHEMA_CONFLICT")
    done=dict(old.get("done",{}))
    index={r["source_id"]:r for r in rows}
    published=[]
    for c in candidates:
        if c.get("g2_file_result")!="G2_FILE_PASS":continue
        sid=c["source_id"]
        raw=index.get(sid)
        if not raw or not raw.get("source_sha256"):raise RuntimeError("G2_FROZEN_SOURCE_NOT_FOUND")
        if source=="TDCC":
            if c.get("sha_match") is not True or c.get("first_party_historical_check",{}).get("verified") is not True:
                raise RuntimeError("G2_TDCC_FIRST_PARTY_NOT_VERIFIED")
            url=c["first_party_historical_check"]["url"]
            era_date="2026-10"
            ds="SHAREHOLDING_DISTRIBUTION"
        else:
            if not c.get("bronze_sha_verified") or not c.get("normalized_multiset_equal"):
                raise RuntimeError("G2_TAIFEX_FULL_FILE_CONTENT_NOT_VERIFIED")
            if c.get("full_file_sha")!=raw["source_sha256"]:
                raise RuntimeError("G2_TAIFEX_SHA_NOT_EQUAL")
            if c.get("official_response",{}).get("status")!="FETCHED":
                raise RuntimeError("G2_TAIFEX_OFFICIAL_NOT_FETCHED")
            if c.get("whole_file_target_date_count",0)<15:
                raise RuntimeError("G2_TAIFEX_DAY_COUNT_HOLD")
            url=TAIFEX_OFFICIAL
            era_date="2024-01"
            ds="LARGE_TRADER"
        edition=period(source,era_date)["id"]
        evidence_sha=sha(json.dumps({"report_id":rid,"source_id":sid,"official":url,
            "bronze_sha":raw["source_sha256"],"matched_file":c.get("g2_file_result")},
            ensure_ascii=False,sort_keys=True).encode())
        cert={"schema":"R1_G2_DATASET_CERT_V2","source":source,
              "source_id":sid,"sha":raw["source_sha256"],"dataset":ds,
              "era":edition,"contract_version":"v097_g2_official_native_full_v2",
              "evidence_sha256":evidence_sha,"official_reference":url,
              "official_evidence_id":rid,"official_attested":True,
              "dataset_origin_verified":True,"same_date_header_rows_verified":True,
              "full_bronze_file_verified":True,"source_lineage_verified":True,
              "publication_asof_verified":False,
              "publication_asof_status":"INDEPENDENT_PIT_GATE_NOT_G2",
              "run":RUN}
        if sid in done and done[sid]!=cert:
            if done[sid].get("sha")!=cert["sha"]:
                raise RuntimeError("G2_CERT_IMMUTABLE_SHA_CONFLICT")
        done[sid]=cert
        published.append(sid)
    if published:
        upsert(api,control,registry,{"schema":"R1_G2_DATASET_CERT_V2",
                 "source":source,"done":done,"updated_at":datetime.now(timezone.utc).isoformat(),
                 "last_run":RUN})
        witness=match(api,control,registry)
        actual=load_json(api,witness["id"]) if witness else {}
        if any(actual.get("done",{}).get(sid)!=done[sid] for sid in published):
            raise RuntimeError("G2_CERT_REGISTRY_READBACK_MISMATCH")
    return published

def run(source):
    api,control,quality,match,load_json,put_once,upsert,call=source_api()
    rows=read_baseline(api,quality,match,load_json,source)
    assert_cohort(rows,source)
    try:
        info=tdcc_source(rows,api,call) if source=="TDCC" else taifex_source(rows,api,call,quality,match,load_json,put_once)
    except Exception as ex:
        # Keep the exact failure class as a Drive QA receipt when credentials permit.
        info={"status":"SOURCE_DIAGNOSTIC_EXCEPTION","error_type":type(ex).__name__,
              "error_message":str(ex)[:240],"official_g2_certified":False}
    verdict=g2_v2_verdict(source,info)
    if FULL_MODE:
        file_cases=(info.get("cases",[]) if source=="TDCC" else [info])
        passing=[v for v in file_cases if v.get("g2_file_result")=="G2_FILE_PASS"]
        verdict["full_file_result"]="G2_FILE_PASS" if len(passing)==len(file_cases) and bool(file_cases) else "G2_FILE_HOLD"
        verdict["full_file_pass_count"]=len(passing)
        verdict["full_file_verified_ids"]=[v.get("source_id") for v in passing]
        verdict["official_first_party_comparison"]=bool(passing) and (
            source=="TAIFEX" or all(v.get("first_party_historical_check",{}).get("verified") for v in passing))
        # Full-file result is NOT a seven-source R1 Master certificate.
        verdict["r1_master_promoted"]=False
    record={"schema":SOURCE,"source":source,"run":RUN,
        "g2_rule":G2_RULE_V2,"g2_v2_verdict":verdict,"full_file_mode":FULL_MODE,
        "sample_mode":not FULL_MODE,"sample_scope":SAMPLE_SCOPE[source],
        "time_utc":datetime.now(timezone.utc).isoformat(),
        "result":info,"formal_g2_new_pass":0,
        "certification_boundary":"FULL_FILE_G2_REQUIRES_VERIFIED_FIRST_PARTY_DATE_HEADER_VALUES_AND_BRONZE_SHA; release independent of PIT time metadata",
        "bronze_modified":False,"silver_gold_materialized":False}
    # Large resumable Drive receipts use JSON readback equality.
    # Normalize tuple-like collections to their on-disk JSON representation.
    record=json.loads(json.dumps(record,ensure_ascii=False,separators=(",",":")))
    rid=put_once(api,quality,"v097_EXACT_DATE_ORIGINAL_SOURCE_COMPARE_"+source+"_"+RUN+".json",record)
    certificates=publish_g2_v2_full_file_certificates(
        source,rows,info,verdict,rid,api,control,match,load_json,upsert)
    upsert(api,control,"v097_EXACT_DATE_ORIGINAL_SOURCE_COMPARE_"+source+"_LATEST.json",
        {"schema":SOURCE,"source":source,"run":RUN,"report_id":rid,
         "status":verdict["sample_result"],"g2_rule":G2_RULE_V2,
         "formal_file_g2_pass":bool(certificates),"formal_g2_certified_file_ids":certificates})
    print("MATCHED_ORIGINAL_SOURCE="+canonical({
        "source":source,"report_id":rid,"run":RUN,
        "overall":info.get("status"),
        "counts":dict(collections.Counter(c.get("status") for c in info.get("cases",[]))),
        "formal_G2_new_pass":len(certificates),
        "g2_file_result":verdict.get("full_file_result","NOT_RUN"),
        "g2_file_pass_count":verdict.get("full_file_pass_count",0),
        "g2_sample_result":verdict["sample_result"],
        "g2_sample_rows_pass":verdict["sample_rows_pass"],
        "g2_sample_files_pass":verdict["sample_files_pass"]}),flush=True)
def selftest():
    assert len(TDCC_CODES)==2 and len({TAIFEX_DATE_START,TAIFEX_DATE_END})==2
    assert compact(["1","2","",""])==["1","2"]
    assert csv_decode(b"<!DOCTYPE html><html>Access denied</html>")[1]=="HTML_NOT_CSV"
    assert norm_header("\ufeff占集保庫存數比例 (%)")==norm_header("占集保庫存數比例%")
    assert TAIFEX_DATE_START=="2024/01/02" and TAIFEX_DATE_END in ("2024/01/04","2024/01/31")
    assert g2_v2_verdict("TAIFEX",{})["sample_result"]=="G2_SAMPLE_HOLD"
    assert g2_v2_verdict("TDCC",{})["sample_result"]=="G2_SAMPLE_HOLD"
    print("G2_MATCHED_DATE_SOURCE_DIFF_SELFTEST_PASS")
if __name__=="__main__":
    if sys.argv[1:]==["selftest"]:selftest()
    elif len(sys.argv)==3 and sys.argv[1]=="source" and sys.argv[2] in ("TDCC","TAIFEX"):run(sys.argv[2])
    else:raise SystemExit("selftest | source TDCC/TAIFEX")
