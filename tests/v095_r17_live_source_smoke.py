"""R17 bounded public-source connectivity smoke; read-only, no credentials, no production writes.
Data-bearing endpoints are distinguished from simple site reachability.
"""
import json
from pathlib import Path
from urllib.request import Request,urlopen
from urllib.error import HTTPError,URLError

ENDPOINTS=[
 ("TWSE","https://www.twse.com.tw/rwd/zh/marginTrading/MI_MARGN?date=20261022&response=json","DATA_JSON"),
 ("TPEx","https://www.tpex.org.tw/www/zh-tw/margin/sbl?date=2026%2F10%2F22&response=json","DATA_JSON"),
 ("FinMind","https://api.finmindtrade.com/api/v4/data?dataset=TaiwanStockPrice&data_id=1101&start_date=2026-10-22&end_date=2026-10-22","DATA_JSON"),
 ("TAIFEX","https://openapi.taifex.com.tw/swagger.json","API_SCHEMA_ONLY"),
 ("MOPS","https://mops.twse.com.tw/","SITE_ONLY"),
 ("TDCC","https://www.tdcc.com.tw/portal/zh/smWeb/qryStock","SITE_ONLY"),
 ("NDC","https://www.ndc.gov.tw/","SITE_ONLY")
]
def check_one(source,url,kind):
    result={"source":source,"check_type":kind,"status":"BLOCKED","http_code":None,
            "data_verified":False,"reason":None}
    try:
        req=Request(url,headers={"User-Agent":"JARVIS-v095-safe-smoke/1.0 (single-test-request)","Accept":"application/json,text/html;q=0.8,*/*;q=0.1"})
        with urlopen(req,timeout=18) as resp:
            result["http_code"]=resp.status
            blob=resp.read(131072)
            result["bytes_read_bounded"]=len(blob)
        if kind=="DATA_JSON":
            try:
                parsed=json.loads(blob)
            except (ValueError,UnicodeDecodeError) as exc:
                result["reason"]="NOT_JSON_OR_TRUNCATED"
                return result
            if source=="TWSE":
                good=parsed.get("stat")=="OK" and isinstance(parsed.get("tables"),list) and any(t.get("data") for t in parsed["tables"])
            elif source=="TPEx":
                good=isinstance(parsed.get("tables"),list) and any(t.get("data") for t in parsed["tables"])
            else:
                good=isinstance(parsed.get("data"),list) and len(parsed["data"])>0
            result["status"]="PASS" if good else "BLOCKED"
            result["data_verified"]=good
            result["reason"]="VALID_DATA_RESPONSE" if good else "EMPTY_OR_UNEXPECTED_SCHEMA"
        else:
            result["status"]="REACHABLE_ONLY"
            result["reason"]="REQUIRES_EXPLICIT_DATA_ENDPOINT_FOR_BRONZE_INGEST"
    except HTTPError as exc:
        result["http_code"]=exc.code;result["reason"]="HTTP_ERROR"
    except (URLError,TimeoutError,OSError) as exc:
        result["reason"]=type(exc).__name__
    return result
if __name__=="__main__":
    records=[check_one(*row) for row in ENDPOINTS]
    report={"kind":"JARVIS_V095_R17_PUBLIC_SOURCE_PROBE","release_approved":False,
            "live_data_sources_passed":sum(x["data_verified"] for x in records),
            "tested_sources":len(records),"results":records}
    Path("r17_live_source_connectivity.json").write_text(json.dumps(report,ensure_ascii=False,indent=2))
    for x in records:
        print("SOURCE="+x["source"]+" STATUS="+x["status"]+" HTTP="+str(x["http_code"])+" REASON="+str(x["reason"]))
    print("RELEASE_APPROVED=false")
