#!/usr/bin/env python3
"""v0.97 MOPS original HTML data recovery (not a Bronze/Silver admission).
Extract MOPS financial matrix only after strict row/column, numeric and unit checks.
Keep original file, immutable hashes and period; unknown disclosure time stays UNKNOWN.
"""
import os,re,json,hashlib
from datetime import datetime,timezone
from collections import Counter
from decimal import Decimal,InvalidOperation
from bs4 import BeautifulSoup
from googleapiclient.http import MediaInMemoryUpload
from scripts.v097_bronze_first_pipeline import service,common,match,load_json,put_once,upsert,call,makefolder
from scripts.v097_bf_residual_1131 import format_candidates,classify_payload
RUN=os.getenv("GITHUB_RUN_ID","manual")
LANE=int(os.getenv("MOPS_REPAIR_LANE","0"))
BATCH=max(1,min(35,int(os.getenv("MOPS_REPAIR_BATCH","20"))))
NAME="v097_MOPS_HTML_MATRIX_QA_V1"
MAX_BYTES=4*1024*1024
def now():return datetime.now(timezone.utc).isoformat()
def sha(b):return hashlib.sha256(b).hexdigest()
def parse_html(raw):
    soup=BeautifulSoup(raw.decode("utf-8-sig"),"html.parser")
    head=soup.select_one("#headTable table")
    body=soup.select_one("#bodyTable table")
    if not head or not body:raise ValueError("NOT_MOPS_MATRIX_TWO_TABLES")
    labels=[x.get_text(" ",strip=True) for x in head.select("tbody tr")]
    hrows=body.select("thead tr")
    if len(hrows)<2:raise ValueError("MISSING_COMPANY_HEADERS")
    companies=[x.get_text(" ",strip=True) for x in hrows[-1].select("th")]
    groups=[x.get_text(" ",strip=True) for x in hrows[0].select("th")]
    values=body.select("tbody tr")
    if not 2<=len(companies)<=1000 or not 5<=len(values)<=500:
        raise ValueError("UNEXPECTED_MOPS_TABLE_DIMENSIONS")
    if len(labels)!=len(values) or len(groups)!=len(companies):
        raise ValueError("MOPS_HEADER_OR_ROW_DIMENSION_MISMATCH")
    coded=[]
    for c in companies:
        match_id=re.match(r"^([0-9]{4})\s+(.+)",c)
        if not match_id:raise ValueError("NON_4DIGIT_COMPANY_COLUMN")
        coded.append({"code":match_id.group(1),"label":c})
    if len({c["code"] for c in coded})!=len(coded):
        raise ValueError("DUPLICATE_COMPANY_COLUMN")
    text=soup.get_text(" ",strip=True)
    if "仟元" in text or "千元" in text:
        unit="TWD_THOUSAND"
    elif "元" in text:
        unit="TWD_YUAN_AMBIGUOUS"
    else:raise ValueError("MOPS_UNIT_NOT_DISCLOSED")
    if unit!="TWD_THOUSAND":raise ValueError("MOPS_FINANCIAL_UNIT_NEEDS_MANUAL")
    matrix=[];n_present=0;missing=0
    for i,vr in enumerate(values):
        cells=vr.select("td")
        if len(cells)!=len(coded):raise ValueError("MOPS_VALUE_COLUMN_COUNT_MISMATCH")
        row=[]
        for td in cells:
            val=td.get_text(" ",strip=True).replace(",","").replace("−","-")
            if not val or val in ("--","-"):row.append(None);missing+=1;continue
            try:
                d=Decimal(val)
                if not d.is_finite():raise ValueError("NON_FINITE")
                row.append(str(d));n_present+=1
            except (InvalidOperation,ValueError):
                raise ValueError("NONNUMERIC_MOPS_CELL:"+val[:40])
        matrix.append({"account":labels[i],"values_thousand_twd":row})
    if not n_present:raise ValueError("ALL_FINANCIAL_CELLS_EMPTY")
    return {"dataset_type":"MOPS_FINANCIAL_HTML_MATRIX",
            "unit":"TWD_THOUSAND","original_unit_multiplier_to_TWD_100M":"0.00001",
            "companies":coded,"column_groups":groups,"rows":matrix,
            "company_count":len(coded),"account_count":len(labels),
            "numeric_cells":n_present,"missing_cells":missing,
            "market_membership_certified":False,"publication_date_certified":False}
def candidates(api,m,c,lane):
    f=match(api,c,"v097_BF_RESIDUAL_FORMAT_V1_CK_%02d.json"%lane)
    if not f:raise RuntimeError("MOPS_FORMAT_QA_MISSING")
    ck=load_json(api,f["id"])["done"]
    return [(r,a,ck[r["file_id"]]) for r,a in format_candidates(api,m,c,lane)
            if r.get("source")=="MOPS"
            and ck.get(r["file_id"],{}).get("state")=="MOPS_HTML_TABLE_ADAPTER_AND_FINANCIAL_UNITS_PENDING"]
def root(api,create=False):
    _,_,_,bronze=common(api)
    parent=call(lambda:api.files().get(fileId=bronze,fields="parents")).get("parents",[])
    if len(parent)!=1:raise RuntimeError("PARENT_NOT_UNIQUE")
    if create:return makefolder(api,parent[0],"00_QUARANTINE_MOPS_PARSED_V1")
    f=match(api,parent[0],"00_QUARANTINE_MOPS_PARSED_V1")
    if not f:raise RuntimeError("MOPS_HOLD_NOT_BOOTSTRAPPED")
    return f["id"]
def bootstrap(api):
    dest=root(api,create=True)
    for lane in range(6):makefolder(api,dest,"MOPS_LANE_%02d"%lane)
    print("MOPS_BOOTSTRAP_READY",flush=True)
def parse_one(api,dest,row,validated,lane):
    fid=row["file_id"]
    result={"file_id":fid,"original_path":row.get("path"),
       "source":"MOPS","bronze_admitted":False,"silver_admitted":False,
       "original_v093_modified":False}
    try:
        meta=call(lambda:api.files().get(fileId=fid,fields="id,name,size,md5Checksum"))
        if meta["name"]!=row.get("file_name"):raise ValueError("SOURCE_NAME_CHANGED")
        size=int(meta.get("size") or 0)
        if size<1 or size>MAX_BYTES:raise ValueError("SOURCE_EMPTY_OR_TOO_LARGE")
        raw=call(lambda:api.files().get_media(fileId=fid))
        if len(raw)!=size or hashlib.md5(raw).hexdigest()!=meta.get("md5Checksum",hashlib.md5(raw).hexdigest()):
            raise ValueError("ORIGINAL_MD5_SIZE_CHANGED")
        digest=sha(raw)
        if digest!=validated.get("sha256"):raise ValueError("PRIOR_QA_SHA_CHANGED")
        if not str(row.get("path") or "").startswith(str(row.get("year"))+"/MOPS/"+str(row.get("month"))+"/"):
            raise ValueError("MOPS_PERIOD_PATH_MISMATCH")
        parsed=parse_html(raw)
        # Data period identity is not the publication date. Do not invent it.
        parsed.update(schema="v097_mops_financial_matrix_staged_1",source_file_id=fid,
           source_sha256=digest,original_filename=row.get("file_name"),
           source_path=row.get("path"),source_year=row.get("year"),source_month=row.get("month"),
           disclosure_datetime="UNKNOWN",run=RUN)
        content=json.dumps(parsed,ensure_ascii=False,separators=(",",":")).encode("utf-8")
        outsha=sha(content)
        filename="%s__%s__mops_matrix.json"%(fid,outsha[:16])
        existing=match(api,dest,filename)
        if not existing:
            media=MediaInMemoryUpload(content,mimetype="application/json",resumable=False)
            existing=call(lambda:api.files().create(body={"name":filename,"parents":[dest],
               "description":"Verified numeric MOPS matrix; staged, NOT PIT certified Bronze/Silver; source="+fid},
               media_body=media,fields="id,name"))
        actual=call(lambda:api.files().get_media(fileId=existing["id"]))
        metadata=call(lambda:api.files().get(fileId=existing["id"],fields="name,parents"))
        if sha(actual)!=outsha or metadata.get("name")!=filename or metadata.get("parents")!=[dest]:
            raise RuntimeError("PARSED_DESTINATION_NOT_MATCHED")
        result.update(status="MOPS_MATRIX_QA_PASS_STAGED_PIT_PENDING",
            source_sha256=digest,parsed_sha256=outsha,parsed_dest_id=existing["id"],
            n_companies=parsed["company_count"],n_accounts=parsed["account_count"],
            numeric_cells=parsed["numeric_cells"],unit=parsed["unit"])
    except Exception as ex:
        result.update(status="MOPS_ADAPTER_HOLD",error=type(ex).__name__+":"+str(ex)[:160])
    return result
def lane_run(api,lane):
    m,c,q,_=common(api)
    rows=candidates(api,m,c,lane)
    ckname=NAME+"_CK_%02d.json"%lane
    f=match(api,c,ckname)
    ck=load_json(api,f["id"]) if f else {"schema":"v097_mops_parser_ck_1","lane":lane,"done":{}}
    if ck.get("schema")!="v097_mops_parser_ck_1" or ck.get("lane")!=lane:
        raise RuntimeError("MOPS_CK_CONFLICT")
    ids={r["file_id"] for r,a,v in rows}
    if not set(ck["done"]).issubset(ids):raise RuntimeError("MOPS_CK_ORPHAN")
    todo=[(r,a,v) for r,a,v in rows if r["file_id"] not in ck["done"]][:BATCH]
    folder=match(api,root(api),"MOPS_LANE_%02d"%lane)
    if not folder:raise RuntimeError("MOPS_LANE_MISSING")
    offset=len(ck["done"])
    receipt="%s_%s_L%02d_O%04d.json"%(NAME,RUN,lane,offset)
    prior=match(api,q,receipt)
    if prior:
        outcomes=load_json(api,prior["id"])["rows"]
    else:
        outcomes=[parse_one(api,folder["id"],r,v,lane) for r,a,v in todo]
        put_once(api,q,receipt,{"schema":"v097_mops_matrix_receipt_1","run":RUN,"lane":lane,
            "rows":outcomes,"source_modified":False,"market_promoted":0})
    for x in outcomes:
        ck["done"][x["file_id"]]={"status":x["status"],"parsed_dest_id":x.get("parsed_dest_id")}
    upsert(api,c,ckname,dict(ck,updated_at=now(),last_receipt=receipt))
    print("MOPS_MATRIX_LANE="+json.dumps({"lane":lane,"processed":len(ck["done"]),
       "total":len(rows),"remaining":len(rows)-len(ck["done"]),
       "states":dict(Counter(x["status"] for x in ck["done"].values()))},ensure_ascii=False),flush=True)
def summary(api):
    m,c,q,_=common(api);total=done=0;seen=set();statuses=Counter()
    for lane in range(6):
        rows=candidates(api,m,c,lane)
        ids={r["file_id"] for r,a,v in rows}
        if ids&seen or len(ids)!=len(rows):raise RuntimeError("MOPS_DUPLICATES")
        seen.update(ids);total+=len(ids)
        f=match(api,c,NAME+"_CK_%02d.json"%lane)
        ck=load_json(api,f["id"]) if f else {"done":{}}
        if not set(ck["done"]).issubset(ids):raise RuntimeError("MOPS_CK_ORPHANS")
        done+=len(ck["done"])
        statuses.update(x["status"] for x in ck["done"].values())
    if total!=388:raise RuntimeError("EXPECTED_388_GOT_%d"%total)
    report={"schema":"v097_mops_html_matrix_report_1","run":RUN,"expected":total,
       "examined":done,"unexamined":total-done,"statuses":dict(statuses),
       "validated_matrix_parsed":statuses["MOPS_MATRIX_QA_PASS_STAGED_PIT_PENDING"],
       "bronze_promoted":0,"silver_promoted":0,
       "next":"PIT and accounting semantic validation before Bronze/Silver admission"}
    put_once(api,q,NAME+"_SUMMARY_%s.json"%RUN,report)
    print("MOPS_MATRIX_SUMMARY="+json.dumps(report,ensure_ascii=False),flush=True)
def selftest():
    html=b'<div class="head">(\\xe9\\x87\\x91\\xe9\\xa1\\x8d\\xe5\\x96\\xae\\xe4\\xbd\\x8d\\xef\\xbc\\x9a\\xe6\\x96\\xb0\\xe8\\x87\\xba\\xe5\\xb9\\xa3\\xe4\\xbb\\x9f\\xe5\\x85\\x83)</div><div id="headTable"><table><tbody>'+b''.join(b"<tr><td>Account</td></tr>" for _ in range(5))+b'</tbody></table></div><div id="bodyTable"><table><thead><tr><th>C</th><th>C</th></tr><tr><th>9918 Test</th><th>9920 Test</th></tr></thead><tbody>'+b''.join(b"<tr><td>1</td><td>-2</td></tr>" for _ in range(5))+b'</tbody></table></div>'
    try:parse_html(b"<html></html>")
    except ValueError:pass
    else:raise AssertionError("MUST_REJECT_NONMATRIX")
    print("MOPS_MATRIX_SELFTEST_PASS",flush=True)
if __name__=="__main__":
    mode=os.getenv("MOPS_MATRIX_MODE","selftest")
    if mode=="selftest":selftest()
    else:
        api=service()
        if mode=="bootstrap":bootstrap(api)
        elif mode=="lane":lane_run(api,LANE)
        elif mode=="summary":summary(api)
        else:raise RuntimeError("BAD_MOPS_MODE")
