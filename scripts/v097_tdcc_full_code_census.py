#!/usr/bin/env python3
"""Full TDCC 5035 filename security-code census and official same-date spot checks.
No auto-truncation of ticker and no Bronze admission. Query official historical
site only with code/date from frozen source; record HTTP and direct content proof.
"""
import os,re,json,hashlib,requests
from collections import Counter,defaultdict
from datetime import datetime,timezone
from bs4 import BeautifulSoup
from scripts.v097_bronze_first_pipeline import service,common,put_once,call
from scripts.v097_tdcc_a3_a5_auto import source_rows,FILE,html_identity,table_diagnostics
from scripts.v097_tdcc_code_permutation_diagnosis import pattern
RUN=os.getenv("GITHUB_RUN_ID","manual")
QUERIES=[
    ("20251031","YKQ8"),
    ("20251107","YY0037"),
    ("20260918","YY0064"),
    ("20261002","YFJ1"),
    ("20260918","2330"), # normal listed-stock control
]
OLD_URL="https://www.tdcc.com.tw/smWeb/QryStockAjax.do"
PORTAL="https://www.tdcc.com.tw/portal/zh/smWeb/qryStock"
def now():return datetime.now(timezone.utc).isoformat()
def parse_html_values(raw):
    c,dates,_=html_identity(raw)
    t=table_diagnostics(raw)
    return {"code":c,"selected_dates":dates[:6],"distribution":t}
def official_compare():
    import requests
    s=requests.Session()
    result=[]
    try:
        main=s.get(PORTAL,timeout=(8,20),headers={"User-Agent":"Mozilla/5.0"})
        result.append({"step":"official_portal","url":PORTAL,
            "http":main.status_code,"content_type":main.headers.get("Content-Type"),
            "bytes":len(main.content),
            "form_names":list(sorted({e.get("name") for e in BeautifulSoup(main.content,"html.parser").select("input[name],select[name]") if e.get("name")}))[:30],
            "date_tokens":re.findall(r'(?:20\d{6})',main.text)[:8]})
    except Exception as exc:
        result.append({"step":"official_portal","error":type(exc).__name__+":"+str(exc)[:150]})
    for day,code in QUERIES:
        record={"step":"official_historical_same_date_check","date":day,"code":code,"url":OLD_URL}
        try:
            payload={"scaDates":day,"scaDate":day,"SqlMethod":"StockNo",
                "StockNo":code,"radioStockNo":code,"StockName":"",
                "REQ_OPR":"SELECT","clkStockNo":code,"clkStockName":""}
            resp=s.post(OLD_URL,data=payload,timeout=(8,25),
                headers={"User-Agent":"Mozilla/5.0","Referer":PORTAL})
            record.update(http=resp.status_code,bytes=len(resp.content),
                response_sha256=hashlib.sha256(resp.content).hexdigest(),
                content_type=resp.headers.get("Content-Type"),
                final_host=resp.url.split("/")[2] if "/" in resp.url else "UNKNOWN")
            if resp.ok and len(resp.content)<5_000_000:
                decoded=resp.content.decode("utf-8-sig",errors="replace")
                if decoded.count("\ufffd")>20:
                    decoded=resp.content.decode("cp950",errors="replace")
                z=parse_html_values(decoded.encode("utf-8"))
                record.update(query_code_in_response=z["code"],
                    query_date_in_response=day in z["selected_dates"],
                    distribution_status=z["distribution"].get("status"),
                    total_shares=z["distribution"].get("total_shares"),
                    total_holders=z["distribution"].get("total_holders"))
                record["same_code_and_date_proved"]=bool(z["code"]==code and day in z["selected_dates"])
            else:record["same_code_and_date_proved"]=False
        except Exception as exc:
            record.update(error=type(exc).__name__+":"+str(exc)[:160],same_code_and_date_proved=False)
        result.append(record)
    return result
def census(api):
    m,c,q,_=common(api)
    pattern_counts=Counter();month_counts=Counter();day_counts=Counter();prefix_counts=Counter()
    examples={};total=0;allkeys=set();dates_by_code=defaultdict(set);unparseable=[]
    for lane in range(6):
        for row in source_rows(api,q,lane):
            total+=1
            fid=row["file_id"];path=str(row.get("source_path") or "")
            m=FILE.search(path)
            if not m:
                unparseable.append({"file_id":fid,"path":path[-140:]});continue
            day,code=m.group(1),m.group(2).upper()
            klass=pattern(code)
            pattern_counts[klass]+=1;day_counts[day]+=1;month_counts[day[:6]]+=1
            prefix_counts[code[:2]]+=1;dates_by_code[code].add(day)
            if klass not in examples:examples[klass]={"code":code,"date":day,"file_id":fid}
    if total!=5035:raise RuntimeError("V4_TOTAL_DIFFERENT:"+str(total))
    official=official_compare()
    # Actual original spot-check ledger from previous run, not generated from guesses.
    records={"schema":"v097_tdcc_5035_code_census_1","run":RUN,"at":now(),
        "frozen_exception_count":total,"matched_filename":total-len(unparseable),
        "unparseable_filename":len(unparseable),"by_pattern":dict(pattern_counts),
        "by_month":dict(month_counts),"by_day":dict(day_counts),
        "by_prefix":dict(prefix_counts),"distinct_code_count":len(dates_by_code),
        "representative_codes":examples,
        "same_date_official_historical_checks":official,
        "government_rule":"first 4 positions numeric, positions 5-6 space/digit/A-Z",
        "stock_market_membership_verified":False,
        "source_originals_unchanged":True,
        "official_source_url":"https://www.tdcc.com.tw/portal/zh/smWeb/qryStock",
        "notes":"Unmatched historical query is NOT evidence that source did not exist or was corrupt; retain quarantine."}
    put_once(api,q,"v097_TDCC_5035_CODE_CENSUS_%s.json"%RUN,records)
    print("TDCC_5035_CODE_CENSUS="+json.dumps(records,ensure_ascii=False),flush=True)
def selftest():
    assert pattern("YY0037")=="NON_TDCC_GOV_PREFIX_ALPHANUMERIC"
    assert pattern("2330A1")=="FOUR_PLUS_ALPHA_DIGIT"
    print("TDCC_5035_CENSUS_SELFTEST_PASS")
if __name__=="__main__":
    mode=os.getenv("TDCC_5035_MODE","selftest")
    if mode=="selftest":selftest()
    elif mode=="census":census(service())
    else:raise RuntimeError("BAD_MODE")
