#!/usr/bin/env python3
"""TDCC true-code permutation diagnosis on 5,035 frozen V4 exception originals.
Read bounded samples across six fixed lanes and dates, compare filename+HTML+table
and current official TDCC 1-5 shape. No promotion or false PIT certification.
"""
import os,re,json,hashlib,html,csv,io,requests
from collections import Counter,defaultdict
from datetime import datetime,timezone
from scripts.v097_bronze_first_pipeline import service,common,match,load_json,put_once,call
from scripts.v097_tdcc_a3_a5_auto import source_rows,html_identity,table_diagnostics,assess,FILE
RUN=os.getenv("GITHUB_RUN_ID","manual")
LIMIT=int(os.getenv("TDCC_DIAG_SAMPLE_PER_LANE","12"))
MASTER_URL="https://openapi.tdcc.com.tw/v1/opendata/1-5"
def pattern(code):
    code=(code or "").strip().upper()
    if re.fullmatch(r"\d{4}",code):return "FOUR_DIGIT_NUMERIC"
    if re.fullmatch(r"\d{4}[ ]{1,2}",code):return "PADDED_FOUR"
    if re.fullmatch(r"\d{4}[A-Z]",code):return "FOUR_PLUS_ONE_ALPHA"
    if re.fullmatch(r"\d{4}\d",code):return "FIVE_NUMERIC"
    if re.fullmatch(r"\d{4}[A-Z]\d",code):return "FOUR_PLUS_ALPHA_DIGIT"
    if re.fullmatch(r"\d{4}\d[A-Z]",code):return "FOUR_PLUS_DIGIT_ALPHA"
    if re.fullmatch(r"\d{4}[A-Z]{2}",code):return "FOUR_PLUS_TWO_ALPHA"
    if re.fullmatch(r"\d{6}",code):return "SIX_NUMERIC"
    if re.fullmatch(r"\d{4}[0-9A-Z]{2}",code):return "FOUR_PLUS_TWO_MIXED"
    if re.fullmatch(r"[A-Z0-9]{4,6}",code):return "NON_TDCC_GOV_PREFIX_ALPHANUMERIC"
    return "OTHER_OR_INVALID"
def download_official():
    # Public original 1-5 data is published on the official openapi service; snapshot is NOT historical master.
    obs={"url":MASTER_URL,"historical_membership_proof":False}
    try:
        r=requests.get(MASTER_URL,timeout=(10,28),headers={"User-Agent":"JARVIS-v097-TDCC-QA/0.97"})
        obs["http_status"]=r.status_code
        r.raise_for_status()
        payload=r.content
        obs["bytes"]=len(payload)
        obs["sha256"]=hashlib.sha256(payload).hexdigest()
        if len(payload)>65_000_000:raise ValueError("OFFICIAL_OVER_LIMIT")
        if payload.lstrip().startswith((b"[",b"{")):
            data=r.json()
            rows=data if isinstance(data,list) else next((v for v in data.values() if isinstance(v,list)),[])
            obs["format"]="JSON"
        else:
            rows=list(csv.DictReader(io.StringIO(payload.decode("utf-8-sig"))))
            obs["format"]="CSV"
        obs["rows"]=len(rows)
        examples=[]
        for row in rows[:1000]:
            if isinstance(row,dict):
                examples.append({"date":row.get("資料日期"),"code":row.get("證券代號"),
                  "level":row.get("持股分級"),"holders":row.get("人數"),
                  "shares":row.get("股數"),"percent":row.get("占集保庫存數比例%")})
        obs["sample_code_patterns"]=dict(Counter(pattern(str(z.get("code") or "")) for z in examples))
        obs["sample_dates"]=list(sorted({str(z["date"]) for z in examples if z.get("date")}))[:6]
        obs["sample_first"]=examples[:3]
    except Exception as exc:
        obs["error"]=type(exc).__name__+":"+str(exc)[:180]
    return obs
def run(api):
    m,c,q,_=common(api)
    cases=[];counts=Counter();status=Counter();source_period=Counter();days=Counter()
    example_days=set()
    for lane in range(6):
        src=source_rows(api,q,lane)
        # Take spread over available records, not only the first.
        take=min(LIMIT,len(src))
        ix=sorted(set(round(i*(len(src)-1)/max(1,take-1)) for i in range(take)))
        for i in ix:
            rr=src[i];fid=rr["file_id"];path=rr.get("source_path") or ""
            fm=FILE.search(path);file_code=fm.group(2).upper() if fm else None
            file_day=fm.group(1) if fm else None
            item={"file_id":fid,"lane":lane,"file_name":path[-180:],
                  "date_in_filename":file_day,"code_in_filename":file_code,
                  "filename_pattern":pattern(file_code)}
            try:
                meta=call(lambda:api.files().get(fileId=fid,fields="id,name,size,md5Checksum"))
                length=int(meta.get("size") or 0)
                item["size"]=length
                if not 0<length<=4_000_000:raise ValueError("MISSING_OR_OVER_4MB")
                raw=call(lambda:api.files().get_media(fileId=fid))
                if len(raw)!=length:raise ValueError("LENGTH_CHANGED")
                if meta.get("md5Checksum") and hashlib.md5(raw).hexdigest()!=meta["md5Checksum"]:
                    raise ValueError("SOURCE_MD5_MISMATCH")
                content_code,content_dates,has_table=html_identity(raw)
                qa=table_diagnostics(raw)
                prior,obs=assess(path,raw)
                item.update(content_code=content_code,content_pattern=pattern(content_code),
                    content_matches_filename=bool(content_code and file_code and content_code==file_code),
                    content_date_matches=file_day in content_dates,
                    table_qa=qa,legacy_status=prior,source_sha256=hashlib.sha256(raw).hexdigest())
                status[prior]+=1;counts[item["content_pattern"]]+=1
            except Exception as exc:
                item.update(error=type(exc).__name__+":"+str(exc)[:180])
                status["READ_OR_QA_FAILED"]+=1
            if file_day:
                days[file_day]+=1;source_period[file_day[:6]]+=1
            cases.append(item)
    official=download_official()
    report={"schema":"v097_tdcc_code_combinations_diagnostic_1","run":RUN,
       "at":datetime.now(timezone.utc).isoformat(),
       "frozen_population":5035,"samples":len(cases),
       "source_code_patterns":dict(counts),"legacy_qa_status":dict(status),
       "sample_months":dict(source_period),"sample_dates":dict(days),
       "official_snapshot":official,
       "government_schema":"https://schema.nat.gov.tw/lists/75",
       "code_rule":"first four digits; last 2 may be blanks/numbers/A-Z; preserve original six positions",
       "historical_membership_verified":False,
       "notes":"Current 1-5 dataset cannot authenticate older stock-market membership.",
       "cases":cases}
    put_once(api,q,"v097_TDCC_CODE_DIAG_%s.json"%RUN,report)
    brief={k:v for k,v in report.items() if k!="cases"}
    brief["sample_examples"]=cases[:12]
    print("TDCC_CODE_DIAG="+json.dumps(brief,ensure_ascii=False),flush=True)
def selftest():
    expected={"2330":"FOUR_DIGIT_NUMERIC","2330  ":"FOUR_DIGIT_NUMERIC",
       "2330A":"FOUR_PLUS_ONE_ALPHA","23301":"FIVE_NUMERIC",
       "2330A1":"FOUR_PLUS_ALPHA_DIGIT","23301A":"FOUR_PLUS_DIGIT_ALPHA",
       "2330AB":"FOUR_PLUS_TWO_ALPHA","233012":"SIX_NUMERIC",
       "YJR4":"NON_TDCC_GOV_PREFIX_ALPHANUMERIC"}
    for c,want in expected.items():
        assert pattern(c)==want,(c,pattern(c),want)
    print("TDCC_CODE_DIAG_SELFTEST_PASS",flush=True)
if __name__=="__main__":
    mode=os.getenv("TDCC_CODE_DIAG_MODE","selftest")
    if mode=="selftest":selftest()
    elif mode=="diagnose":run(service())
    else:raise SystemExit("UNKNOWN_MODE")
