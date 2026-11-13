#!/usr/bin/env python3
"""TPEx legacy RSTA3104 HTML salvage, Big5/CP950, point-in-time safe STAGING.
Precise report identity and date/source-period checks plus prices, volumes, hash.
No silent official-origin certificate or Bronze admission without release proof.
"""
import os,re,json,hashlib
from datetime import date,datetime,timezone
from decimal import Decimal,InvalidOperation
from collections import Counter
from bs4 import BeautifulSoup
from googleapiclient.http import MediaInMemoryUpload
from scripts.v097_bronze_first_pipeline import service,common,match,load_json,put_once,upsert,call,makefolder
from scripts.v097_bf_residual_1131 import format_candidates
RUN=os.getenv("GITHUB_RUN_ID","manual")
LANE=int(os.getenv("TPEX_ADAPTER_LANE","0"))
BATCH=max(1,min(35,int(os.getenv("TPEX_ADAPTER_BATCH","18"))))
NAME="v097_TPEX_LEGACY_RSTA3104_V1"
MAX_BYTES=6*1024*1024
NUM=r"[+\-]?(?:\d+(?:,\d{3})*|\d*)\.\d+|[+\-]?\d+(?:,\d{3})*"
ROW=re.compile(r"(?<!\w)(\d{4})\s+(\S+)\s+((?:(?:"+NUM+r")(?:\s+|$)){11})")
COLS=["close","change","open","high","low","average","shares","turnover_twd","trade_count","last_bid","last_ask"]
def sha(b):return hashlib.sha256(b).hexdigest()
def now():return datetime.now(timezone.utc).isoformat()
def parse_roc(text):
    mm=re.search(r"資料日期\s*[:：]?\s*(\d{6,7})",text)
    if not mm:raise ValueError("OFFICIAL_TPEX_REPORT_DATE_MISSING")
    d=mm.group(1);y=int(d[:-4])+1911;m=int(d[-4:-2]);dd=int(d[-2:])
    return date(y,m,dd).isoformat()
def parse(raw,expected_period=None):
    text=BeautifulSoup(raw.decode("cp950",errors="replace"),"html.parser").get_text(" ",strip=True)
    if "中華民國證券櫃檯買賣中心" not in text[:300] or "<RSTA3104>" not in text[:400] or "上櫃股票行情" not in text[:400]:
        raise ValueError("UNSUPPORTED_TPEX_REPORT_NOT_RSTA3104")
    if not all(k in text[:800] for k in ["證券名稱","成交股數","成交金額","收盤價","成交筆數"]):
        raise ValueError("TPEX_HEADER_SCHEMA_NOT_MATCHED")
    day=parse_roc(text)
    if expected_period and day[:7]!=expected_period:
        raise ValueError("TPEX_INNER_REPORT_DATE_NOT_SOURCE_PERIOD")
    found=[];seen=set()
    for match_row in ROW.finditer(text):
        code,name,raw_fields=match_row.groups()
        fields=raw_fields.split()
        if len(fields)!=11:continue
        if code in seen:raise ValueError("TPEX_DUPLICATE_STOCK_CODE")
        vals=[]
        try:
            for val in fields:vals.append(Decimal(val.replace(",","")))
            if not all(v.is_finite() for v in vals):raise ValueError("NONFINITE")
            if any(vals[i]<0 for i in (6,7,8)):raise ValueError("NEGATIVE_VOLUME_OR_AMOUNT")
            if vals[3]>0 and vals[4]>0 and vals[3]<vals[4]:raise ValueError("HIGH_LOWER_THAN_LOW")
            if vals[2]>0 and vals[3]>0 and vals[2]>vals[3]:raise ValueError("OPEN_HIGH_CONTRADICTION")
            if vals[2]>0 and vals[4]>0 and vals[2]<vals[4]:raise ValueError("OPEN_LOW_CONTRADICTION")
            if vals[0]>0 and vals[3]>0 and vals[0]>vals[3]:raise ValueError("CLOSE_HIGH_CONTRADICTION")
            if vals[0]>0 and vals[4]>0 and vals[0]<vals[4]:raise ValueError("CLOSE_LOW_CONTRADICTION")
        except (InvalidOperation,ValueError) as exc:
            raise ValueError("TPEX_NUMERIC_INVALID_"+code+"_"+str(exc)[:70])
        seen.add(code)
        found.append({"stock_code":code,"stock_name":name,**{k:str(v) for k,v in zip(COLS,vals)}})
    if len(found)<10:raise ValueError("TPEX_RSTA3104_TOO_FEW_ROWS")
    return {"schema":"v097_tpex_legacy_rsta3104_staged_1",
            "report_code":"RSTA3104","report_date":day,"encoding":"CP950_BIG5",
            "market":"TPEx","row_count":len(found),"column_names":COLS,
            "turnover_unit":"TWD_YUAN_FROM_REPORT_COLUMN",
            "turnover_to_100m_twd_multiplier":"0.00000001",
            "historical_stock_membership_verified":False,
            "official_publication_time_verified":False,
            "records":found}
def candidates(api,m,c,lane):
    f=match(api,c,"v097_BF_RESIDUAL_FORMAT_V1_CK_%02d.json"%lane)
    if not f:raise RuntimeError("MISSING_FORMAT_QA")
    ck=load_json(api,f["id"]).get("done",{})
    return [(r,a,ck[r["file_id"]]) for r,a in format_candidates(api,m,c,lane)
           if r.get("source")=="TPEx" and ck.get(r["file_id"],{}).get("state")=="TPEX_HTML_TABLE_ADAPTER_AND_DATASET_ORIGIN_PENDING"]
def root(api,create=False):
    _,_,_,bronze=common(api)
    p=call(lambda:api.files().get(fileId=bronze,fields="parents")).get("parents",[])
    if len(p)!=1:raise RuntimeError("PARENT_NOT_UNIQUE")
    name="00_QUARANTINE_TPEX_RSTA3104_PARSED_V1"
    if create:return makefolder(api,p[0],name)
    f=match(api,p[0],name)
    if not f:raise RuntimeError("TPEX_ROOT_NOT_BOOTSTRAPPED")
    return f["id"]
def bootstrap(api):
    target=root(api,True)
    for lane in range(6):makefolder(api,target,"TPEX_LANE_%02d"%lane)
    print("TPEX_BOOTSTRAP_READY",flush=True)
def one(api,row,prior,dest,lane):
    fid=row["file_id"];out={"file_id":fid,"source":"TPEx",
        "bronze_admitted":False,"silver_admitted":False,
        "original_v093_unchanged":True}
    try:
        meta=call(lambda:api.files().get(fileId=fid,fields="id,name,size,md5Checksum"))
        size=int(meta.get("size") or 0)
        if meta["name"]!=row.get("file_name"):raise ValueError("SOURCE_NAME_CHANGED")
        if not 0<size<=MAX_BYTES:raise ValueError("SOURCE_EMPTY_OR_TOO_LARGE")
        raw=call(lambda:api.files().get_media(fileId=fid))
        if len(raw)!=size:raise ValueError("SOURCE_BYTE_COUNT_CHANGED")
        if meta.get("md5Checksum") and hashlib.md5(raw).hexdigest()!=meta["md5Checksum"]:
            raise ValueError("SOURCE_MD5_CHANGED")
        source_sha=sha(raw)
        if source_sha!=prior.get("sha256"):raise ValueError("SOURCE_SHA_CHANGED_FROM_FORMAT_QA")
        prefix=str(row.get("year"))+"/TPEx/"+str(row.get("month"))+"/"
        if not str(row.get("path") or "").startswith(prefix):
            raise ValueError("SOURCE_OR_PERIOD_PATH_NOT_EVIDENCED")
        parsed=parse(raw,str(row.get("month")))
        parsed.update(source_file_id=fid,source_sha256=source_sha,
            source_original_filename=meta["name"],source_original_path=row.get("path"),
            run=RUN,official_publication_datetime="UNKNOWN")
        data=json.dumps(parsed,ensure_ascii=False,separators=(",",":")).encode()
        digest=sha(data);name="%s__%s__tpex_rsta3104.json"%(fid,digest[:16])
        found=match(api,dest,name)
        if not found:
            upload=MediaInMemoryUpload(data,mimetype="application/json",resumable=False)
            found=call(lambda:api.files().create(body={"name":name,"parents":[dest],
              "description":"Historical TPEx RSTA3104 parsed and SHA-verified; PIT/source provenance pending; original="+fid},
              media_body=upload,fields="id,name"))
        actual=call(lambda:api.files().get_media(fileId=found["id"]))
        dm=call(lambda:api.files().get(fileId=found["id"],fields="name,parents"))
        if sha(actual)!=digest or dm.get("name")!=name or dm.get("parents")!=[dest]:
            raise ValueError("TPEX_STAGING_DEST_NOT_VERIFIED")
        out.update(status="TPEX_RSTA3104_PARSE_QA_PASS_PIT_PENDING",
            source_sha256=source_sha,parsed_sha256=digest,
            parsed_dest_id=found["id"],rows=parsed["row_count"],
            report_date=parsed["report_date"])
    except Exception as exc:
        out.update(status="TPEX_ADAPTER_HOLD",error=type(exc).__name__+":"+str(exc)[:150])
    return out
def lane_run(api,lane):
    m,c,q,_=common(api)
    src=candidates(api,m,c,lane)
    ckname=NAME+"_CK_%02d.json"%lane
    f=match(api,c,ckname)
    ck=load_json(api,f["id"]) if f else {"schema":"v097_tpex_rsta3104_ck_1","lane":lane,"done":{}}
    if ck.get("schema")!="v097_tpex_rsta3104_ck_1" or ck.get("lane")!=lane:
        raise RuntimeError("TPEX_CHECKPOINT_CONFLICT")
    ids={r["file_id"] for r,a,v in src}
    if not set(ck["done"]).issubset(ids):raise RuntimeError("TPEX_ORPHAN")
    todo=[(r,a,v) for r,a,v in src if r["file_id"] not in ck["done"]][:BATCH]
    dest=match(api,root(api),"TPEX_LANE_%02d"%lane)
    if not dest:raise RuntimeError("NO_DEST_LANE")
    off=len(ck["done"]);receipt="%s_%s_L%02d_O%05d.json"%(NAME,RUN,lane,off)
    prior=match(api,q,receipt)
    if prior:results=load_json(api,prior["id"])["rows"]
    else:
        results=[one(api,r,v,dest["id"],lane) for r,a,v in todo]
        put_once(api,q,receipt,{"schema":"v097_tpex_legacy_receipt_1",
            "run":RUN,"lane":lane,"rows":results,"market_bronze_promotions":0})
    for result in results:ck["done"][result["file_id"]]={"status":result["status"],
        "parsed_dest_id":result.get("parsed_dest_id"),"rows":result.get("rows"),
        "error":result.get("error")}
    upsert(api,c,ckname,dict(ck,last_receipt=receipt,updated_at=now()))
    print("TPEX_RSTA3104_LANE="+json.dumps({"lane":lane,"checked":len(ck["done"]),
        "total":len(src),"remaining":len(src)-len(ck["done"]),
        "statuses":dict(Counter(v["status"] for v in ck["done"].values()))},ensure_ascii=False),flush=True)
def summary(api):
    m,c,q,_=common(api);total=checked=rows=0;by_status=Counter()
    for lane in range(6):
        src=candidates(api,m,c,lane);total+=len(src)
        f=match(api,c,NAME+"_CK_%02d.json"%lane)
        if f:
            ck=load_json(api,f["id"])
            checked+=len(ck["done"])
            by_status.update(x["status"] for x in ck["done"].values())
            rows+=sum(x.get("rows") or 0 for x in ck["done"].values())
    if total!=711:raise RuntimeError("EXPECTED_TPEX_711_GOT_%d"%total)
    report={"schema":"v097_tpex_rsta3104_summary_1","run":RUN,
        "expected":total,"checked":checked,"remaining":total-checked,
        "by_status":dict(by_status),"staged_market_rows":rows,
        "bronze_admitted":0,"pit_pending":True}
    put_once(api,q,NAME+"_SUMMARY_%s.json"%RUN,report)
    print("TPEX_RSTA3104_SUMMARY="+json.dumps(report,ensure_ascii=False),flush=True)
def selftest():
    sample=("中華民國證券櫃檯買賣中心 <RSTA3104> 上櫃股票行情 資料日期：930205 代號 證券名稱 收盤價 漲跌 開盤價 最高價 最低價 均價 成交股數 成交金額 成交筆數 最後委買價 最後委賣價 " +
       "3067 全域 38.80 -1.30 40.60 40.80 38.80 39.95 22,006 879,134 23 38.60 38.80 "*10)
    try:parse(sample.encode("cp950"),"2004-03")
    except ValueError:pass
    else:raise AssertionError("BAD_PERIOD_MUST_FAIL")
    assert parse_roc(sample)=="2004-02-05"
    print("TPEX_RSTA3104_SELFTEST_PASS",flush=True)
if __name__=="__main__":
    mode=os.getenv("TPEX_RSTA_MODE","selftest")
    if mode=="selftest":selftest()
    else:
        api=service()
        if mode=="bootstrap":bootstrap(api)
        elif mode=="lane":lane_run(api,LANE)
        elif mode=="summary":summary(api)
        else:raise SystemExit("INVALID_TPEX_MODE")
