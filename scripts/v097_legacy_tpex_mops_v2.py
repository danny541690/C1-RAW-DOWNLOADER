#!/usr/bin/env python3
"""JARVIS v0.97 TPEx/MOPS legacy HTML repair V2.
Uses real 2003 and 2005 TPEx tables and 2004/2006 Big5 revenue reports.
Strictly preserve identity, original SHA and 0.97 staging readback; no false
Bronze, Silver or PIT certification.
"""
import os,re,json,hashlib
from decimal import Decimal,InvalidOperation
from datetime import date,datetime,timezone
from collections import Counter
from bs4 import BeautifulSoup
from googleapiclient.http import MediaInMemoryUpload
from scripts.v097_bronze_first_pipeline import service,common,match,load_json,put_once,upsert,call,makefolder
from scripts.v097_tpex_rsta3104_recovery import candidates as tpex_candidates
from scripts.v097_mops_html_matrix_recovery import candidates as mops_candidates
RUN=os.getenv("GITHUB_RUN_ID","manual")
LANE=int(os.getenv("LEGACY_REPAIR_LANE","0"))
MODE=os.getenv("LEGACY_REPAIR_MODE","selftest")
CAP=max(1,min(30,int(os.getenv("LEGACY_BATCH","15"))))
NAME="v097_LEGACY_TPEX_MOPS_V2"
MAX_BYTES=8_000_000
NUM=r"[+\-]?(?:(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?|\.\d+)"
PRICE_COLS=["close","change","open","high","low","average","shares","turnover_twd","trades","bid","ask"]
ROWS_2003=re.compile(r"(?<![A-Z0-9])(\d{4}[A-Z]?)\s+(\S+)\s+("+r"\s+".join(["(?:"+NUM+")"]*11)+r")(?=\s|$)")
def sha(b):return hashlib.sha256(b).hexdigest()
def n(s):
    s=str(s).strip().replace(",","")
    if s in ("","---","----","--","-","N/A"):return None
    d=Decimal(s)
    if not d.is_finite():raise ValueError("NON_FINITE")
    return d
def numeric_qa(v):
    close,change,op,high,low,avg,vol,amt,trades,bid,ask=v
    if any(x is None for x in (vol,amt,trades)):return False
    if any(x<0 for x in (vol,amt,trades)):return False
    if high is not None and low is not None and high>0 and low>0 and high<low:return False
    for p in (op,close):
        if p is None or p==0:continue
        if high and p>high:return False
        if low and p<low:return False
    return True
def roc_date(rawtext):
    m=re.search(r"資料日期\s*[:：]\s*(\d{6,7})",rawtext)
    if m:
        s=m.group(1);return date(1911+int(s[:-4]),int(s[-4:-2]),int(s[-2:])).isoformat()
    m=re.search(r"交易日期\s*[:：]\s*(\d{2,3})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日",rawtext)
    if m:return date(1911+int(m.group(1)),int(m.group(2)),int(m.group(3))).isoformat()
    raise ValueError("TPEX_DATE_NOT_PARSEABLE")
def parse_tpex(raw,expected_month):
    text=raw.decode("cp950",errors="strict")
    soup=BeautifulSoup(text,"html.parser");plain=soup.get_text(" ",strip=True)
    if "櫃檯買賣中心" not in plain[:200] or "上櫃股票行情" not in plain[:200]:
        raise ValueError("NOT_OFFICIAL_TPEX_LEGACY_STOCK_REPORT")
    dt=roc_date(plain)
    if dt[:7]!=expected_month:raise ValueError("TPEX_PERIOD_NOT_MATCH_"+dt)
    records={};skipped=Counter()
    # 2005-ish layout contains 19 td cells; close and price-change symbol split.
    modern=bool(re.search("成交金額\\s*\\(元\\)",plain[:600])) or "次日 參考價" in plain[:500]
    if modern:
        layout="TPEX_2005_EXPANDED_HTML"
        for tr in soup.find_all("tr"):
            tds=tr.find_all(["td","th"],recursive=False)
            if len(tds) not in (18,19):continue
            a=[t.get_text(" ",strip=True) for t in tds]
            code=a[0]
            if not re.fullmatch(r"\d{4}[A-Z]?",code):continue
            if not re.fullmatch(r"\d{4}",code):skipped["SPECIAL_CODE"]+=1;continue
            # Empty close + text marker means auction section price placement.
            try:
                shift=-1 if len(a)==18 else 0
                vals=[n(a[i+shift]) for i in [3,5,6,7,8,9,10,11,12,13,14]]
                if a[4+shift] in ("▽","▼","-"):vals[1]=-abs(vals[1] or Decimal(0))
                if a[4+shift] in ("△","▲","+"):vals[1]=abs(vals[1] or Decimal(0))
                if not numeric_qa(vals):skipped["NUMERIC_QA_FAIL"]+=1;continue
                if vals[0] is None:skipped["NO_CLOSE"]+=1;continue
                rec={"code":code,"company_name":a[1],
                    **{k:(str(v) if v is not None else None) for k,v in zip(PRICE_COLS,vals)}}
                if code in records and rec!=records[code]:raise ValueError("DUPLICATE_DIFFERENT_VALUES_"+code)
                records[code]=rec
            except (InvalidOperation,ValueError) as exc:
                if "DUPLICATE_DIFFERENT_VALUES_" in str(exc):raise
                skipped["NONNUMERIC_ROW"]+=1
    else:
        layout="TPEX_2003_NESTED_HTML"
        for matchrow in ROWS_2003.finditer(plain):
            code,name,rest=matchrow.groups()
            if not re.fullmatch(r"\d{4}",code):skipped["SPECIAL_CODE"]+=1;continue
            vals=[n(x) for x in rest.split()]
            if len(vals)!=11 or not numeric_qa(vals):
                skipped["NUMERIC_QA_FAIL"]+=1;continue
            rec={"code":code,"company_name":name,
                **{k:str(v) if v is not None else None for k,v in zip(PRICE_COLS,vals)}}
            if code in records and records[code]!=rec:raise ValueError("DUPLICATE_DIFFERENT_VALUES_"+code)
            records[code]=rec
    if len(records)<30:raise ValueError("TOO_FEW_VERIFIED_TPEX_ROWS_"+str(len(records)))
    return {"report_type":layout,"market":"TPEx","date":dt,
        "stock_scope":"FOUR_DIGIT_CODE_CANDIDATES_ONLY_NO_HISTORICAL_LISTING_PROOF",
        "turnover_unit":"TWD_YUAN","records":list(records.values()),
        "records_count":len(records),"skipped":dict(skipped),
        "official_publication_time":"UNKNOWN","formal_bronze_pass":False}
def parse_revenue(raw,expected_period):
    try:text=raw.decode("cp950",errors="strict")
    except UnicodeDecodeError:
        try:text=raw.decode("big5hkscs",errors="strict")
        except UnicodeDecodeError:text=raw.decode("cp950",errors="replace")
    soup=BeautifulSoup(text,"html.parser")
    plain=soup.get_text(" ",strip=True)
    if "營業收入統計表" not in plain[:300] or "單位：千元" not in plain:
        raise ValueError("NOT_MOPS_LEGACY_MONTHLY_REVENUE")
    m=re.search(r"公司\s*(\d{2,3})\s*年\s*(\d{1,2})\s*月份",plain[:300])
    if not m:raise ValueError("MOPS_REVENUE_REPORT_PERIOD_NOT_FOUND")
    dt="%04d-%02d"%(1911+int(m.group(1)),int(m.group(2)))
    if dt!=expected_period:raise ValueError("MOPS_REVENUE_PERIOD_MISMATCH_"+dt)
    publish=re.search(r"出表日期\s*[:：]\s*(\d{2,3})/(\d{1,2})/(\d{1,2})",plain[:450])
    print_date=(date(1911+int(publish.group(1)),int(publish.group(2)),int(publish.group(3))).isoformat() if publish else None)
    companies={};subtotals=0;invalid=Counter()
    fields=["monthly_thousand","prior_month_thousand","year_ago_thousand",
        "mom_percent_reported","yoy_percent_reported",
        "ytd_thousand","year_ago_ytd_thousand","ytd_yoy_percent_reported"]
    for tr in soup.find_all("tr"):
        c=[x.get_text(" ",strip=True) for x in tr.find_all(["td","th"],recursive=False)]
        if not c:continue
        if c[0].replace(" ","") in ("合計","總計"):subtotals+=1;continue
        if len(c)!=10 or not re.fullmatch(r"\d{4}",c[0]):continue
        code,name=c[:2]
        if "\ufffd" in name:invalid["COMPANY_NAME_ENCODING_UNVERIFIED"]+=1;continue
        try:nums=[n(t) for t in c[2:]]
        except InvalidOperation:invalid["NON_NUMERIC_CELL"]+=1;continue
        if nums[0] is None:invalid["MISSING_MONTHLY_REVENUE"]+=1;continue
        if any(v is not None and v<0 for v in (nums[0],nums[1],nums[2],nums[5],nums[6])):
            # Allow negative monthly revenue credit notes, but cannot silently call it ordinary.
            invalid["NEGATIVE_REVENUE_REVIEW"]+=1;continue
        rec={"code":code,"company_name":name,
             **{key:(str(val) if val is not None else None) for key,val in zip(fields,nums)}}
        # Validate derived YoY, MOM to 0.12 pct points when both inputs exist.
        for ix,pctidx,label in [(1,3,"MOM"),(2,4,"YOY"),(6,7,"YTD_YOY")]:
            old=nums[ix];pct=nums[pctidx]
            base=nums[5] if ix==6 else nums[0]
            if old is not None and old!=0 and pct is not None and base is not None:
                calc=(base-old)*100/old
                if abs(calc-pct)>Decimal("0.15"):
                    invalid[label+"_MISMATCH"]+=1
                    rec.setdefault("warnings",[]).append(label+"_REPORTED_PCT_DIFF")
        if code in companies and companies[code]!=rec:
            invalid["DUPLICATE_COMPANY_WITH_CONFLICT"]+=1;continue
        companies[code]=rec
    if len(companies)<1:raise ValueError("MOPS_REVENUE_TOO_FEW_ROWS_"+str(len(companies)))
    return {"report_type":"MOPS_BIG5_MONTHLY_REVENUE",
       "revenue_month":dt,"html_report_print_date":print_date,
       "unit":"TWD_THOUSAND","amount_multiplier_to_100m":"0.00001",
       "records_count":len(companies),"records":list(companies.values()),
       "row_warnings":dict(invalid),
       "first_publication_datetime":"UNKNOWN","pit_certified":False}
def candidates(api,m,c,lane,source):
    fn=tpex_candidates if source=="TPEx" else mops_candidates
    name="v097_TPEX_LEGACY_RSTA3104_V1" if source=="TPEx" else "v097_MOPS_HTML_MATRIX_QA_V1"
    status="TPEX_ADAPTER_HOLD" if source=="TPEx" else "MOPS_ADAPTER_HOLD"
    base={r["file_id"]:(r,a,v) for r,a,v in fn(api,m,c,lane)}
    f=match(api,c,name+"_CK_%02d.json"%lane)
    if not f:raise RuntimeError("MISSING_PRIOR_ADAPTER_CHECKPOINT")
    ck=load_json(api,f["id"])["done"]
    return [(r,a,v) for fid,(r,a,v) in base.items() if ck.get(fid,{}).get("status")==status]
def bootstrap(api):
    _,_,_,bronze=common(api)
    parents=call(lambda:api.files().get(fileId=bronze,fields="parents")).get("parents",[])
    if len(parents)!=1:raise RuntimeError("DATA_LAKE_PARENT_AMBIGUOUS")
    name="00_QUARANTINE_LEGACY_REPAIRED_V2"
    root=makefolder(api,parents[0],name)
    for source in ("TPEx","MOPS"):
        sf=makefolder(api,root,source)
        for lane in range(6):makefolder(api,sf,"LEGACY_LANE_%02d"%lane)
    print("LEGACY_V2_BOOTSTRAP_OK",flush=True)
def folder(api,source,lane):
    _,_,_,bronze=common(api)
    parents=call(lambda:api.files().get(fileId=bronze,fields="parents")).get("parents",[])
    f=match(api,parents[0],"00_QUARANTINE_LEGACY_REPAIRED_V2")
    if not f:raise RuntimeError("NOT_BOOTSTRAPPED")
    s=match(api,f["id"],source)
    l=match(api,s["id"],"LEGACY_LANE_%02d"%lane)
    if not l:raise RuntimeError("LANE_NOT_BOOTSTRAPPED")
    return l["id"]
def repair_one(api,row,prior,dest,source):
    fid=row["file_id"]
    out={"file_id":fid,"source":source,"bronze_certified":False,"silver_certified":False}
    try:
        meta=call(lambda:api.files().get(fileId=fid,fields="name,size,md5Checksum"))
        if meta["name"]!=row.get("file_name"):raise ValueError("SOURCE_NAME_MISMATCH")
        length=int(meta.get("size") or 0)
        if not 0<length<MAX_BYTES:raise ValueError("SOURCE_SIZE_UNSUPPORTED")
        raw=call(lambda:api.files().get_media(fileId=fid))
        if len(raw)!=length:raise ValueError("SOURCE_SIZE_CHANGED")
        if meta.get("md5Checksum") and hashlib.md5(raw).hexdigest()!=meta["md5Checksum"]:
            raise ValueError("SOURCE_MD5_CHANGED")
        raw_sha=sha(raw)
        if raw_sha!=prior.get("sha256"):raise ValueError("SOURCE_SHA_CHANGED")
        path=str(row.get("path") or "")
        if not path.startswith(str(row["year"])+"/"+source+"/"+str(row["month"])+"/"):
            raise ValueError("SOURCE_PERIOD_PATH_MISMATCH")
        doc=parse_tpex(raw,row["month"]) if source=="TPEx" else parse_revenue(raw,row["month"])
        doc.update(schema="v097_legacy_repaired_qa_1",source_file_id=fid,
            source_sha256=raw_sha,source_path=path,
            original_name=meta["name"],run=RUN)
        body=json.dumps(doc,ensure_ascii=False,separators=(",",":")).encode()
        dest_sha=sha(body)
        name=fid+"__"+dest_sha[:16]+"__"+source+"_legacy_v2.json"
        f=match(api,dest,name)
        if not f:
            upload=MediaInMemoryUpload(body,mimetype="application/json",resumable=False)
            f=call(lambda:api.files().create(body={"name":name,"parents":[dest],
                "description":"JARVIS v0.97 legacy parsed original; source="+fid+"; PIT and listing proof pending"},
                media_body=upload,fields="id,name"))
        verified=call(lambda:api.files().get_media(fileId=f["id"]))
        info=call(lambda:api.files().get(fileId=f["id"],fields="name,parents"))
        if sha(verified)!=dest_sha or info.get("parents")!=[dest] or info.get("name")!=name:
            raise ValueError("DESTINATION_CONTENT_SHA_OR_PATH_CONFLICT")
        out.update(state="LEGACY_PARSED_STAGED_PIT_PENDING",dest_id=f["id"],
            src_sha256=raw_sha,dest_sha256=dest_sha,
            records=doc["records_count"],report_type=doc["report_type"])
    except Exception as exc:
        out.update(state="LEGACY_REPAIR_HOLD",error=type(exc).__name__+":"+str(exc)[:170])
    return out
def lane_run(api,lane,source):
    m,c,q,_=common(api)
    eligible=candidates(api,m,c,lane,source)
    ckname=NAME+"_"+source+"_CK_%02d.json"%lane
    f=match(api,c,ckname)
    ck=load_json(api,f["id"]) if f else {"schema":"v097_legacy_v2_ck_1","lane":lane,
        "source":source,"done":{}}
    ids={r["file_id"] for r,a,v in eligible}
    if not set(ck["done"]).issubset(ids):raise RuntimeError("CHECKPOINT_ORPHAN")
    todo=[(r,a,v) for r,a,v in eligible
          if r["file_id"] not in ck["done"] or
          (ck["done"][r["file_id"]].get("state")=="LEGACY_REPAIR_HOLD"
           and ck["done"][r["file_id"]].get("retry_version")!="V3"
           and not (source=="MOPS" and "THREE_YEAR_OFFICIAL_GAPS" in str(r.get("file_name") or "")))][:CAP]
    offset=len(ck["done"])
    sig=hashlib.sha256("\n".join(r["file_id"] for r,a,v in todo).encode()).hexdigest()[:12]
    receipt=NAME+"_"+source+"_"+RUN+"_L%02d_O%04d_%s.json"%(lane,offset,sig)
    old=match(api,q,receipt)
    if old:results=load_json(api,old["id"])["rows"]
    else:
        dest=folder(api,source,lane)
        results=[repair_one(api,r,v,dest,source) for r,a,v in todo]
        put_once(api,q,receipt,{"schema":"v097_legacy_v2_receipt_1","source":source,
            "run":RUN,"lane":lane,"rows":results,"formal_bronze_promotions":0})
    for row in results:ck["done"][row["file_id"]]={"state":row["state"],
        "dest_id":row.get("dest_id"),"records":row.get("records"),"error":row.get("error"),"retry_version":"V3"}
    upsert(api,c,ckname,dict(ck,last_receipt=receipt,updated_at=datetime.now(timezone.utc).isoformat()))
    by=Counter(x["state"] for x in ck["done"].values())
    print("LEGACY_V2_LANE="+json.dumps({"source":source,"lane":lane,
        "checked":len(ck["done"]),"total":len(eligible),
        "remaining":len(eligible)-len(ck["done"]),"by_state":dict(by)},ensure_ascii=False),flush=True)
def summary(api):
    m,c,q,_=common(api);result={}
    for source,expected in [("TPEx",656),("MOPS",120)]:
        checked=0;group=Counter();records=0;ids=set()
        for lane in range(6):
            rows=candidates(api,m,c,lane,source);src={r["file_id"] for r,a,v in rows}
            if src&ids:raise RuntimeError("CROSS_LANE_DUPLICATE")
            ids.update(src)
            f=match(api,c,NAME+"_"+source+"_CK_%02d.json"%lane)
            if f:
                done=load_json(api,f["id"])["done"]
                if not set(done).issubset(src):raise RuntimeError("CHECKPOINT_ORPHANS")
                checked+=len(done);group.update(x["state"] for x in done.values())
                records+=sum(x.get("records") or 0 for x in done.values())
        if len(ids)!=expected:raise RuntimeError("EXPECTED_"+source+"_FAIL_"+str(len(ids)))
        result[source]={"expected":expected,"checked":checked,"remaining":expected-checked,
            "by_state":dict(group),"parsed_rows":records}
    report={"schema":"v097_legacy_v2_summary_1","run":RUN,"sources":result,
        "market_bronze_certified":0,"silver_certified":0,
        "pit_unverified":True,"originals_modified":False}
    put_once(api,q,NAME+"_SUMMARY_"+RUN+".json",report)
    print("LEGACY_V2_SUMMARY="+json.dumps(report,ensure_ascii=False),flush=True)
def selftest():
    assert roc_date("資料日期：921128")=="2003-11-28"
    assert roc_date("交易日期:94年07月29日")=="2005-07-29"
    assert n(".39")==Decimal(".39")
    assert numeric_qa([Decimal("10"),Decimal("0"),Decimal("10"),Decimal("11"),Decimal("9"),Decimal("10"),Decimal(100),Decimal(1000),Decimal(5),Decimal(10),Decimal(10)])
    print("LEGACY_V2_SELFTEST_PASS",flush=True)
if __name__=="__main__":
    if MODE=="selftest":selftest()
    else:
        api=service()
        if MODE=="bootstrap":bootstrap(api)
        elif MODE=="lane":
            for source in ("TPEx","MOPS"):lane_run(api,LANE,source)
        elif MODE=="summary":summary(api)
        else:raise SystemExit("BAD_MODE")
