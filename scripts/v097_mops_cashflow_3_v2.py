#!/usr/bin/env python3
"""Recover all 3 identified MOPS IFRS statement matrix column-group mismatch cases.
Preserve source file, account list, company columns and numeric cells. Company
group tags are AMBIGUOUS if top band width differs; never align by guessing.
"""
import os,re,json,hashlib
from collections import Counter
from datetime import datetime,timezone
from decimal import Decimal,InvalidOperation
from bs4 import BeautifulSoup
from googleapiclient.http import MediaInMemoryUpload
from scripts.v097_bronze_first_pipeline import service,common,match,load_json,put_once,call,makefolder
from scripts.v097_mops_html_matrix_recovery import candidates
RUN=os.getenv("GITHUB_RUN_ID","manual")
NAME="v097_MOPS_3_CASHFLOW_FIXED_V2"
def sha(b):return hashlib.sha256(b).hexdigest()
def parse(raw,row):
    soup=BeautifulSoup(raw.decode("utf-8-sig"),"html.parser")
    head=soup.select_one("#headTable table");body=soup.select_one("#bodyTable table")
    if not head or not body:raise ValueError("MOPS_CASHFLOW_TABLE_MISSING")
    tags=head.select("tbody tr")
    hdr=body.select("thead tr")
    money=body.select("tbody tr")
    if len(hdr)!=2:raise ValueError("MOPS_BODY_HEADER_UNEXPECTED")
    codes=[x.get_text(" ",strip=True) for x in hdr[1].find_all("th",recursive=False)]
    group=[x.get_text(" ",strip=True) for x in hdr[0].find_all("th",recursive=False)]
    if len(group)==len(codes):raise ValueError("THIS_IS_NOT_GROUP_MISMATCH")
    if len(codes)<5 or len(money)!=len(tags) or len(money)<30:
        raise ValueError("ACCOUNT_OR_BODY_ROW_COUNT_CONFLICT")
    stock=[]
    for txt in codes:
        m=re.match(r"^(\d{4})\s+(.+)",txt)
        if not m:raise ValueError("NON_FOUR_DIGIT_COMPANY:"+txt[:25])
        stock.append({"code":m.group(1),"label":txt,"report_group":"UNVERIFIED_GROUP_HEADER_WIDTH_CONFLICT"})
    if len({x["code"] for x in stock})!=len(stock):raise ValueError("COMPANY_DUPLICATES")
    alltext=soup.get_text(" ",strip=True)
    if "金額單位：新台幣仟元" not in alltext:
        raise ValueError("FINANCIAL_UNIT_UNVERIFIED")
    mm=re.search(r"([A-Za-z]+)_(20\d{2})([1-4])(?=_|\.)",str(row.get("file_name") or ""))
    if not mm:raise ValueError("QUARTER_NOT_GROUNDED_IN_SOURCE_FILENAME")
    report_type=mm.group(1);year=int(mm.group(2));quarter=int(mm.group(3))
    period="%04d-%02d"%(year,quarter*3)
    if period!=row["month"]:raise ValueError("FILENAME_PERIOD_CONFLICT")
    accounts=[];present=0;missing=0
    for labelrow,moneyrow in zip(tags,money):
        label=labelrow.get_text(" ",strip=True)
        cells=moneyrow.find_all("td",recursive=False)
        if len(cells)!=len(stock):raise ValueError("MATRIX_WIDTH_MISMATCH")
        values=[]
        for cell in cells:
            txt=cell.get_text(" ",strip=True).replace(",","").replace("−","-")
            if txt in ("","--","-","—"):
                values.append(None);missing+=1;continue
            try:
                x=Decimal(txt)
                if not x.is_finite():raise ValueError("NOT_FINITE")
                values.append(str(x));present+=1
            except (InvalidOperation,ValueError):raise ValueError("UNPARSEABLE_FINANCIAL_CELL")
        accounts.append({"account":label,"values_thousand_twd":values})
    if present<10:raise ValueError("MOST_VALUES_EMPTY")
    return {"schema":"v097_mops_cashflow_3_column_groups_staged_v2",
        "dataset":"MOPS_"+report_type.upper()+"_IFRS","year":year,"quarter":quarter,
        "period_month":period,"financial_unit":"TWD_THOUSAND",
        "conversion_to_100m":"0.00001",
        "companies":stock,"accounts":accounts,"n_accounts":len(accounts),
        "n_companies":len(stock),"nonempty_values":present,"empty_values":missing,
        "raw_group_tag_count":len(group),"company_columns":len(codes),
        "report_group_mapping_verified":False,
        "publication_datetime_verified":False,"bronze_certified":False,
        "silver_certified":False}
def run(api):
    m,c,q,bronze=common(api)
    original=[]
    for lane in range(6):
        ck=match(api,c,"v097_MOPS_HTML_MATRIX_QA_V1_CK_%02d.json"%lane)
        if not ck:raise RuntimeError("SOURCE_CHECKPOINT_NOT_FOUND")
        done=load_json(api,ck["id"])["done"]
        for row,a,fmt in candidates(api,m,c,lane):
            fid=row["file_id"]
            if done.get(fid,{}).get("status")!="MOPS_ADAPTER_HOLD":continue
            if "THREE_YEAR_OFFICIAL_GAPS_" in str(row.get("file_name") or ""):
                original.append((row,fmt))
    if len(original)!=3:raise RuntimeError("EXPECTED_ALL_3_IFRS_COLUMN_GROUP_HOLDS_GOT_"+str(len(original)))
    parent=call(lambda:api.files().get(fileId=bronze,fields="parents")).get("parents",[])
    if len(parent)!=1:raise RuntimeError("AMBIGUOUS_LAKE_PARENT")
    dest=makefolder(api,parent[0],"00_QUARANTINE_MOPS_CASHFLOW_3_FIXED_V2")
    outcomes=[]
    for row,fmt in original:
        fid=row["file_id"];rec={"source_id":fid,"status":"PENDING","bronze_promoted":False}
        try:
            meta=call(lambda:api.files().get(fileId=fid,fields="id,name,size,md5Checksum"))
            data=call(lambda:api.files().get_media(fileId=fid))
            if len(data)!=int(meta["size"]) or (meta.get("md5Checksum") and hashlib.md5(data).hexdigest()!=meta["md5Checksum"]):
                raise ValueError("ORIGINAL_INTEGRITY_CHANGED")
            srcsha=sha(data)
            if srcsha!=fmt.get("sha256"):raise ValueError("PRIOR_FORMAT_QA_SHA_NOT_MATCHED")
            parsed=parse(data,row)
            parsed.update(source_id=fid,source_sha256=srcsha,
                source_filename=meta["name"],source_original_path=row.get("path"),run=RUN)
            body=json.dumps(parsed,ensure_ascii=False,separators=(",",":")).encode("utf-8")
            digest=sha(body);name=fid+"__"+digest[:16]+"__cashflow_v2.json"
            found=match(api,dest,name)
            if not found:
                upload=MediaInMemoryUpload(body,mimetype="application/json",resumable=False)
                found=call(lambda:api.files().create(body={"name":name,"parents":[dest],
                     "description":"Staged MOPS cashflow row-matched. Group/header width ambiguous. PIT pending"},
                     media_body=upload,fields="id,name"))
            destbytes=call(lambda:api.files().get_media(fileId=found["id"]))
            dm=call(lambda:api.files().get(fileId=found["id"],fields="name,parents"))
            if sha(destbytes)!=digest or dm.get("parents")!=[dest] or dm.get("name")!=name:
                raise ValueError("DEST_SHA_OR_PATH_NOT_MATCHED")
            rec.update(status="MOPS_CASHFLOW_MATRIX_STAGED_GROUP_UNVERIFIED",
                source_sha256=srcsha,staged_dest_sha256=digest,dest_id=found["id"],
                n_companies=parsed["n_companies"],n_accounts=parsed["n_accounts"])
        except Exception as exc:rec.update(status="HOLD",error=type(exc).__name__+":"+str(exc)[:180])
        outcomes.append(rec)
    report={"schema":"v097_cashflow_3_repair_report_v2","run":RUN,
       "source_count":len(original),"outcomes":outcomes,
       "staged":sum(x["status"]=="MOPS_CASHFLOW_MATRIX_STAGED_GROUP_UNVERIFIED" for x in outcomes),
       "hold":sum(x["status"]=="HOLD" for x in outcomes),
       "formal_bronze_admitted":0,"originals_modified":False}
    put_once(api,q,NAME+"_SUMMARY_"+RUN+".json",report)
    print("MOPS_3_CASHFLOW_SUMMARY="+json.dumps(report,ensure_ascii=False),flush=True)
if __name__=="__main__":run(service())
