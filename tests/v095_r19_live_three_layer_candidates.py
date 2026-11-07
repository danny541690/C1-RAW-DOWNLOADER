"""R19: official API -> isolated local Bronze -> Parquet Silver -> QA-only Gold.
Three sources (MOPS revenue, TDCC shareholding bounded sample, NDC workbook).
No Drive writes, no publish, no secrets. Conservative source-specific checks.
"""
import hashlib,io,json,os,pathlib,urllib.request,urllib.error,zipfile,time
from decimal import Decimal,InvalidOperation
import pyarrow as pa
import pyarrow.parquet as pq
import openpyxl

ROOT=pathlib.Path("r19_live_candidates")
ROOT.mkdir(exist_ok=True)
NDC="https://ws.ndc.gov.tw/Download.ashx?u=LzAwMS9hZG1pbmlzdHJhdG9yLzEwL3JlbGZpbGUvNjIxNy80MDQ5NS85OTVhZTM4YS1mNzRkLTRjODAtODI2My0wYmI5ZTliZjMwNmIueGxzeA%3d%3d&n=MTE1MDjmlrDogZ7nqL%2fpmYTku7bmlbjliJcueGxzeA%3d%3d&icon=.xlsx"
SOURCES=[
    ("MOPS","https://openapi.twse.com.tw/v1/opendata/t187ap05_L",8*1024*1024,True),
    ("TDCC","https://openapi.tdcc.com.tw/v1/opendata/1-5",262144,False),
    ("NDC",NDC,4*1024*1024,True)
]
def digest(b):return hashlib.sha256(b).hexdigest()
def fetch(url,limit,full):
    headers={"User-Agent":"Mozilla/5.0 (JARVIS-v095 R19 read-only)","Accept":"application/json,*/*"}
    with urllib.request.urlopen(urllib.request.Request(url,headers=headers),timeout=25) as r:
        data=r.read(limit+int(full))
        if full and len(data)>limit:raise ValueError("BODY_TOO_LARGE_FOR_COMPLETE_BRONZE")
        return data,r.status

def normalize(source,blob):
    if source=="MOPS":
        payload=json.loads(blob.decode("utf-8-sig"))
        if not isinstance(payload,list) or not payload:raise ValueError("NO_COMPANY_DATA")
        sample=next((r for r in payload if "公司代號" in r and "營業收入-當月營收" in r and "資料年月" in r),None)
        if not sample:raise ValueError("MONTHLY_REVENUE_SCHEMA_MISSING")
        rev=Decimal(str(sample["營業收入-當月營收"]).replace(",",""))
        period=str(sample["資料年月"])
        if not period.isdecimal() or len(period)<5:raise ValueError("ROC_MONTH_INVALID")
        row={"company_id":str(sample["公司代號"]),"period_roc":period,
             "revenue_thousand_ntd":str(rev),"bronze_sha256":digest(blob)}
        gold={"metric":"single_company_revenue_億元_QA_ONLY","value":str(rev/Decimal(100000)),
              "source_native_unit":"thousand_NTD","period_roc":period}
        return row,gold
    if source=="TDCC":
        text=blob.decode("utf-8-sig").lstrip()
        if not text.startswith("["):raise ValueError("NOT_JSON_ARRAY_PREFIX")
        row,_=json.JSONDecoder().raw_decode(text[1:].lstrip())
        if not isinstance(row,dict):raise ValueError("NOT_OBJECT")
        keys=" ".join(row)
        if not any(t in keys for t in ("證券代號","股票代號","持股","集保戶","股權")):
            raise ValueError("WRONG_TDCC_DATASET")
        silver={"one_record_json":json.dumps(row,ensure_ascii=False,sort_keys=True),
                "sample_only":True,"bronze_sample_sha256":digest(blob)}
        return silver,{"metric":"shareholding_rows_sampled_QA_ONLY","value":1,"full_dataset":False}
    if not blob.startswith(b"PK\x03\x04"):raise ValueError("NOT_WORKBOOK")
    wb=openpyxl.load_workbook(io.BytesIO(blob),read_only=True,data_only=True)
    detected=None
    for sheet in wb:
        for row in sheet.iter_rows(max_row=100,min_row=1):
            for cell in row:
                if isinstance(cell.value,(int,float)) and not isinstance(cell.value,bool):
                    detected={"sheet":sheet.title,"cell":cell.coordinate,"native_value":str(cell.value),
                             "bronze_sha256":digest(blob)}
                    break
            if detected:break
        if detected:break
    wb.close()
    if not detected:raise ValueError("NO_NUMERIC_WORKBOOK_CELL")
    return detected,{"metric":"NDC_sample_native_numeric_cell_QA_ONLY",
                     "value":detected["native_value"],"unit":"NOT_VERIFIED"}

def main():
    results=[]
    for name,url,limit,full in SOURCES:
        out=ROOT/name;out.mkdir(parents=True,exist_ok=True)
        record={"source":name,"status":"BLOCKED","complete_bronze":False,"pit_verified":False,
                "numeric_verified":False,"gold_production_approved":False}
        try:
            if name=="MOPS":
                errors=[]
                for attempt in range(1,4):
                    try:
                        blob,code=fetch(url,limit,full)
                        if not blob.lstrip().startswith((b"[",b"\xef\xbb\xbf[")):
                            raise ValueError("MOPS_NON_JSON_RESPONSE")
                        json.loads(blob.decode("utf-8-sig"))
                        record["attempts"]=attempt
                        break
                    except (ValueError,UnicodeError,urllib.error.URLError,TimeoutError) as exc:
                        errors.append(type(exc).__name__+":"+str(exc)[:90])
                        if attempt==3:raise ValueError("MOPS_FAILED_THREE_ATTEMPTS:"+repr(errors))
                        time.sleep(2)
            else:
                blob,code=fetch(url,limit,full)
            record["http"]=code
            bronze=out/("bronze_full.bin" if full else "bronze_prefix_SAMPLE_ONLY.bin")
            bronze.write_bytes(blob)
            if bronze.read_bytes()!=blob:raise AssertionError("BRONZE_READBACK_FAILED")
            row,gold=normalize(name,blob)
            silver=out/"silver_sample.parquet"
            pq.write_table(pa.Table.from_pylist([row]),silver)
            read=pq.read_table(silver).to_pylist()
            if read!=[row]:raise AssertionError("SILVER_PARQUET_READBACK_FAILED")
            goldpath=out/"gold_qa_only.json"
            payload={"source":name,"source_sha256":digest(blob),"silver_sha256":digest(silver.read_bytes()),
                     "metrics":gold,"release_approved":False}
            goldpath.write_text(json.dumps(payload,ensure_ascii=False,indent=2))
            if json.loads(goldpath.read_text())!=payload:raise AssertionError("GOLD_READBACK_FAILED")
            record.update(status="PASS_LOCAL_THREE_LAYER_QA_ONLY",http=code,
                          bronze_sha256=digest(blob),bronze_bytes=len(blob),complete_bronze=full,
                          silver_rows=1,silver_sha256=digest(silver.read_bytes()))
        except Exception as e:
            record["error"]=type(e).__name__+":"+str(e)[:180]
        print("R19",name,record["status"],record.get("error",""),"complete_bronze",record["complete_bronze"])
        results.append(record)
    report={"schema":"JARVIS_R19_READ_ONLY_LIVE_THREE_LAYER","release_approved":False,"results":results}
    (ROOT/"report.json").write_text(json.dumps(report,ensure_ascii=False,indent=2))
    print("R19_PASS",sum(r["status"].startswith("PASS") for r in results),"/",len(results))
if __name__=="__main__":main()
