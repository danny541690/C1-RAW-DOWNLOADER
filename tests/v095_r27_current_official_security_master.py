"""R27 official current TWSE/TPEx security master vs historical/as-of TDCC.
Snapshot overlap is useful CURRENT membership QA, NOT historical PIT approval.
No production writes. Every failed endpoint stays BLOCKED.
"""
import collections,datetime,hashlib,json,pathlib,re,urllib.request,urllib.error
import pyarrow.parquet as pq
ROOT=pathlib.Path("r27_official_security_master")
ROOT.mkdir(exist_ok=True)
SOURCES={
 "TSE":"https://openapi.twse.com.tw/v1/opendata/t187ap03_L",
 "OTC":"https://www.tpex.org.tw/openapi/v1/mopsfin_t187ap03_O",
}
def sha(x):return hashlib.sha256(x).hexdigest()
def download(label,url):
    r=urllib.request.Request(url,headers={"User-Agent":"Mozilla/5.0 (compatible; JARVIS-v095-readonly-QA)","Accept":"application/json"})
    with urllib.request.urlopen(r,timeout=30) as resp:
        status=resp.status;buf=resp.read(12*1024*1024+1)
    if len(buf)>12*1024*1024:raise ValueError("SIZE_LIMIT_12M")
    if not buf.strip().startswith((b"[",b"\xef\xbb\xbf[")):
        raise ValueError("NON_JSON_SOURCE_RESPONSE")
    obj=json.loads(buf.decode("utf-8-sig"))
    if not isinstance(obj,list) or not obj or not isinstance(obj[0],dict):raise ValueError("NONEMPTY_COMPANY_ARRAY_REQUIRED")
    code_field="公司代號" if label=="TSE" else "SecuritiesCompanyCode"
    if code_field not in obj[0]:raise ValueError("EXPECTED_"+label+"_CODE_FIELD_MISSING:"+",".join(obj[0].keys())[:160])
    (ROOT/(label+"_snapshot.json")).write_bytes(buf)
    return obj,{"status":"PASS_CURRENT_SNAPSHOT","http":status,"row_count":len(obj),
        "sha256":sha(buf),"retrieval_utc":datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "official_endpoint":url,"asof_historical_verified":False}
def main():
    result={"schema":"JARVIS_R27_OFFICIAL_MARKET_MASTER","release_approved":False,
       "current_snapshot_not_historical":True,"market_sources":{}}
    index={}
    for market,url in SOURCES.items():
        try:
            data,meta=download(market,url)
            codes=set()
            code_field="公司代號" if market=="TSE" else "SecuritiesCompanyCode"
            for row in data:
                code=str(row.get(code_field,"")).rstrip(" ")
                if re.fullmatch(r"\d{4}",code):codes.add(code)
            meta["four_digit_company_codes"]=len(codes)
            index[market]=codes;result["market_sources"][market]=meta
            print("R27_MARKET",market,"STATUS",meta["status"],"CODES",len(codes))
        except Exception as exc:
            result["market_sources"][market]={"status":"BLOCKED","error":type(exc).__name__+":"+str(exc)[:160],
                                             "official_endpoint":url}
            print("R27_MARKET",market,"BLOCKED",str(exc)[:160])
    tdcc=pq.read_table("r24_tdcc_numeric_gold_candidate/tdcc_gold_qa_only.parquet",
                       columns=["security_id","semantic_review_required","source_date_raw"]).to_pylist()
    total=len(tdcc); shape=collections.Counter()
    statuses=collections.Counter();samples=collections.defaultdict(list)
    for row in tdcc:
        code=row["security_id"].rstrip(" ")
        if not re.fullmatch(r"\d{4}",code):
            status="NOT_FOUR_DIGIT_CANDIDATE"
        elif len(index)<2:
            status="BLOCKED_SOURCE_MASTER_INCOMPLETE"
        elif code in index["TSE"] and code in index["OTC"]:
            status="CONFLICT_BOTH_MARKETS"
        elif code in index["TSE"]:
            status="CURRENT_TSE_SNAPSHOT_MATCH"
        elif code in index["OTC"]:
            status="CURRENT_OTC_SNAPSHOT_MATCH"
        else:
            status="NO_CURRENT_COMPANY_MATCH_NOT_HISTORICAL_ABSENCE"
        statuses[status]+=1
        if len(samples[status])<5:samples[status].append(code)
    result["tdcc_security_date_groups"]=total
    result["tdcc_current_master_match_categories"]=dict(statuses)
    result["tdcc_category_examples"]={k:v for k,v in samples.items()}
    result["current_market_snapshot_join_pass"]=len(index)==2
    result["historical_security_master_pit_verified"]=False
    result["data_published_timestamp_verified"]=False
    result["investment_gold_approved"]=False
    (ROOT/"R27_current_master_join_report.json").write_text(json.dumps(result,ensure_ascii=False,indent=2))
    print("R27_TDCC_CURRENT_MATCH_COUNTS",json.dumps(dict(statuses),ensure_ascii=False))
    print("R27_HISTORICAL_PIT_VERIFIED=false")
    print("R27_RELEASE_APPROVED=false")
    # A missing market source is a reported BLOCKER and should never qualify the candidate for release.
    if len(index)!=2:
        print("R27_OFFICIAL_MASTER_CHECK=BLOCKED_ONE_OR_MORE_MARKETS")
    else:
        print("R27_OFFICIAL_MASTER_CHECK=PASS_CURRENT_SNAPSHOT_ONLY")
if __name__=="__main__":main()
