#!/usr/bin/env python3
"""Root-cause classification of TPEx and MOPS residual adapter holds.
Read all 711 TPEx checkpoint statuses and all 388 MOPS receipt outcomes;
inspect bounded original bytes only for representative examples.
Does not promote or change raw/previous checkpoints.
"""
import os,re,json,hashlib
from collections import Counter,defaultdict
from datetime import datetime,timezone
from bs4 import BeautifulSoup
from scripts.v097_bronze_first_pipeline import service,common,match,load_json,put_once,children,call
from scripts.v097_bf_residual_1131 import format_candidates
from scripts.v097_tpex_rsta3104_recovery import candidates as tpex_candidates
from scripts.v097_mops_html_matrix_recovery import candidates as mops_candidates
RUN=os.getenv("GITHUB_RUN_ID","manual")
def normalize_error(err):
    s=str(err or "")
    for name in ("UNSUPPORTED_TPEX_REPORT_NOT_RSTA3104","TPEX_HEADER_SCHEMA_NOT_MATCHED",
        "OFFICIAL_TPEX_REPORT_DATE_MISSING","TPEX_INNER_REPORT_DATE_NOT_SOURCE_PERIOD",
        "TPEX_RSTA3104_TOO_FEW_ROWS","SOURCE_SHA_CHANGED_FROM_FORMAT_QA",
        "MOPS_HEADER_OR_ROW_DIMENSION_MISMATCH","NOT_MOPS_MATRIX_TWO_TABLES",
        "MISSING_COMPANY_HEADERS","NON_4DIGIT_COMPANY_COLUMN","MOPS_UNIT_NOT_DISCLOSED",
        "MOPS_FINANCIAL_UNIT_NEEDS_MANUAL","NONNUMERIC_MOPS_CELL","MOPS_VALUE_COLUMN_COUNT_MISMATCH",
        "UNEXPECTED_MOPS_TABLE_DIMENSIONS","MOPS_PERIOD_PATH_MISMATCH",
        "PRIOR_QA_SHA_CHANGED","SOURCE_NAME_CHANGED","SOURCE_EMPTY_OR_TOO_LARGE",
        "MOPS_NUMERIC_INVALID"):
        if name in s:return name
    return s.split(":")[-1][:70] or "UNKNOWN_ERROR"
def bounded_sample(api,row,err):
    fid=row["file_id"];src=row.get("source");res={"file_id":fid,"source":src,
        "month":row.get("month"),"filename":row.get("file_name"),
        "error_group":normalize_error(err)}
    try:
        meta=call(lambda:api.files().get(fileId=fid,fields="size,md5Checksum,name"))
        size=int(meta.get("size") or 0)
        if size>2_500_000 or not size:raise ValueError("SAMPLE_SIZE_OUT_OF_BOUND")
        raw=call(lambda:api.files().get_media(fileId=fid))
        res["sha256"]=hashlib.sha256(raw).hexdigest()
        res["bytes"]=len(raw)
        encoding="cp950" if src=="TPEx" else "utf-8-sig"
        text=raw.decode(encoding,errors="replace")
        soup=BeautifulSoup(text,"html.parser")
        plain=soup.get_text(" ",strip=True)
        res["html_tables"]=len(soup.select("table"))
        res["body_table_present"]=bool(soup.select_one("#bodyTable table"))
        res["head_table_present"]=bool(soup.select_one("#headTable table"))
        res["report_code"]=re.findall(r"RSTA\d{4}",plain[:2000])[:5]
        res["declared_dates"]=re.findall(r"(?:資料日期|日期)\s*[:：]?\s*\d{6,8}",plain[:1000])[:4]
        res["source_head_text"]=plain[:240]
        res["table_header_samples"]=[t.get_text(" ",strip=True)[:120] for t in soup.select("table")[:2]]
    except Exception as ex:res["inspection_error"]=type(ex).__name__+":"+str(ex)[:120]
    return res
def main():
    api=service();m,c,q,_=common(api)
    inventories={};counter={};samples={};errors={}
    # All TPEx checkpoint error fields retained in checkpoints
    for source,name,sourcefn,expected in [
        ("TPEx","v097_TPEX_LEGACY_RSTA3104_V1",tpex_candidates,711),
        ("MOPS","v097_MOPS_HTML_MATRIX_QA_V1",mops_candidates,388)]:
        source_rows={};done={}
        for lane in range(6):
            for row,a,v in sourcefn(api,m,c,lane):
                if row["file_id"] in source_rows:raise RuntimeError("DUPLICATE_SOURCE_ID")
                source_rows[row["file_id"]]=row
            f=match(api,c,name+"_CK_%02d.json"%lane)
            if f:
                d=load_json(api,f["id"])["done"]
                done.update(d)
        if len(source_rows)!=expected:raise RuntimeError("EXPECTED_"+source+"_"+str(len(source_rows)))
        if len(done)!=expected:raise RuntimeError("CK_INCOMPLETE_"+source+"_"+str(len(done)))
        error_by_id={}
        if source=="MOPS":
            # Read immutable run receipts; checkpoint stores only status (by design)
            rx=re.compile(r"^"+re.escape(name)+r"_\d+_L\d\d_O\d+\.json$")
            for f in children(api,q):
                if not rx.match(f["name"]):continue
                d=load_json(api,f["id"])
                for x in d.get("rows",[]):
                    if x.get("file_id") in source_rows and x.get("status")=="MOPS_ADAPTER_HOLD":
                        error_by_id[x["file_id"]]=x.get("error")
        else:
            error_by_id={fid:v.get("error") for fid,v in done.items() if v.get("status")=="TPEX_ADAPTER_HOLD"}
        bad={fid:v for fid,v in done.items() if v.get("status") in ("TPEX_ADAPTER_HOLD","MOPS_ADAPTER_HOLD")}
        groups=defaultdict(list)
        for fid in bad:
            er=error_by_id.get(fid) or "ERROR_RECEIPT_NOT_FOUND"
            groups[normalize_error(er)].append(fid)
        counts=Counter({x:len(ids) for x,ids in groups.items()})
        examples=[]
        for group,ids in groups.items():
            for fid in ids[:min(2,len(ids))]:
                examples.append(bounded_sample(api,source_rows[fid],error_by_id.get(fid)))
        inventories[source]={"expected":expected,
          "passed":sum(x.get("status","").endswith("PASS_PIT_PENDING") for x in done.values()),
          "failed":len(bad),"groups":dict(counts),
          "examples":examples}
    out={"schema":"v097_rootcause_failure_census_1","run":RUN,
       "at":datetime.now(timezone.utc).isoformat(),
       "tp_ex":inventories["TPEx"],"mops":inventories["MOPS"],
       "raw_changed":False,"formal_bronze_promoted":0,
       "note":"Actual failure reasons from immutable receipts/checkpoints, small original source byte inspections."}
    put_once(api,q,"v097_ROOTCAUSE_TPEX_MOPS_%s.json"%RUN,out)
    print("ROOTCAUSE_REPORT="+json.dumps(out,ensure_ascii=False),flush=True)
if __name__=="__main__":main()
