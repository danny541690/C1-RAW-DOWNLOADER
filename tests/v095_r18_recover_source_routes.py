"""R18 public-source recovery smoke: MOPS revenue, TDCC shareholding, NDC archived XLSX.
Read-only, no credentials, limited requests, no production release. Per-source evidence.
"""
import csv, datetime, hashlib, io, json, os, pathlib, urllib.request, urllib.error, zipfile
from decimal import Decimal, InvalidOperation

NDC_URL="https://ws.ndc.gov.tw/Download.ashx?u=LzAwMS9hZG1pbmlzdHJhdG9yLzEwL3JlbGZpbGUvNjIxNy80MDQ5NS85OTVhZTM4YS1mNzRkLTRjODAtODI2My0wYmI5ZTliZjMwNmIueGxzeA%3d%3d&n=MTE1MDjmlrDogZ7nqL%2fpmYTku7bmlbjliJcueGxzeA%3d%3d&icon=.xlsx"
SOURCES=[
 ("MOPS_REVENUE","https://openapi.twse.com.tw/v1/opendata/t187ap05_L",8*1024*1024),
 ("TDCC_SHAREHOLDING","https://openapi.tdcc.com.tw/v1/opendata/1-5",8*1024*1024),
 ("NDC_XLSX","https://ws.ndc.gov.tw/Download.ashx?u=LzAwMS9hZG1pbmlzdHJhdG9yLzEwL3JlbGZpbGUvNjIxNy80MDQ5NS85OTVhZTM4YS1mNzRkLTRjODAtODI2My0wYmI5ZTliZjMwNmIueGxzeA%3d%3d&n=MTE1MDjmlrDogZ7nqL%2fpmYTku7bmlbjliJcueGxzeA%3d%3d&icon=.xlsx",4*1024*1024)
]
def get(url,limit):
    req=urllib.request.Request(url,headers={"User-Agent":"Mozilla/5.0 (compatible; JARVIS-v095-isolated-test/1.0)","Accept":"application/json,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet,*/*"})
    with urllib.request.urlopen(req,timeout=25) as resp:
        content=resp.read(limit+1)
        return resp.status,resp.headers.get("Content-Type",""),content, len(content)<=limit

def sample_json(data):
    obj=json.loads(data.decode("utf-8-sig"))
    if not isinstance(obj,list) or not obj or not isinstance(obj[0],dict):raise ValueError("NOT_NONEMPTY_OBJECT_ARRAY")
    return obj

def validate(name,blob):
    if name=="MOPS_REVENUE":
        arr=sample_json(blob)
        first=next((v for v in arr if "公司代號" in v and ("資料年月" in v or "營業收入-當月營收" in v)),None)
        if first is None:raise ValueError("NO_REVENUE_SCHEMA")
        return {"rows":len(arr),"fields":list(first)[:16],"example_company":str(first.get("公司代號")),"period":str(first.get("資料年月")),"publish_time_known":False,"pit_approved":False}
    if name=="TDCC_SHAREHOLDING":
        # Validate a single complete JSON object from a deliberately bounded prefix.
        # A full-dataset approval requires a separate complete ingestion.
        prefix=blob.decode("utf-8-sig","strict").lstrip()
        if not prefix.startswith("["):raise ValueError("NOT_ARRAY_PREFIX")
        first,_=json.JSONDecoder().raw_decode(prefix[1:].lstrip())
        if not isinstance(first,dict):raise ValueError("NOT_OBJECT_RECORD")
        keys=" ".join(first.keys())
        if not any(tag in keys for tag in ("證券代號","股票代號","持股","集保戶","股權")):
            raise ValueError("NOT_SHAREHOLDING_SCHEMA")
        return {"rows_sampled":1,"full_payload_read":False,"fields":list(first)[:20],"example":{str(k):str(v)[:70] for k,v in list(first.items())[:6]},"pit_approved":False}
    if not blob.startswith(b"PK\x03\x04"):raise ValueError("NDC_NOT_XLSX_ZIP")
    with zipfile.ZipFile(io.BytesIO(blob)) as z:
        names=z.namelist()
        if "[Content_Types].xml" not in names or "xl/workbook.xml" not in names:raise ValueError("INVALID_XLSX_STRUCTURE")
        bad=z.testzip()
        if bad:raise ValueError("ZIP_CRC_FAIL:"+str(bad))
    return {"bytes":len(blob),"sha256":hashlib.sha256(blob).hexdigest(),"xlsx_structure":True,"pit_approved":False}

def main():
    records=[]
    for name,url,limit in SOURCES:
        item={"source":name,"status":"BLOCKED","http":None,"valid_data":False,"pit_approved":False}
        try:
            if name=="TDCC_SHAREHOLDING":
                # The endpoint is large: stream only enough to parse its first record.
                status,ctype,body,_=get(url,262144)
                complete=False
                item["sample_only"]=True
            else:
                status,ctype,body,complete=get(url,limit)
            item.update(http=status,mime=ctype,bytes=len(body),complete=complete)
            if not complete and name!="TDCC_SHAREHOLDING":
                raise ValueError("BOUNDED_READ_INCOMPLETE")
            if name=="NDC_XLSX":
                expected="c035dc5bbd3fe91ca80a620fd84828a54e8c49885a1b3aa51db5e42857772c83"
                item["same_as_20261023_captured_file"]=hashlib.sha256(body).hexdigest()==expected
            item["sample"]=validate(name,body)
            item["status"]="PASS_BOUNDED_SAMPLE" if name=="TDCC_SHAREHOLDING" else "PASS_DATA_FETCH";item["valid_data"]=True
        except urllib.error.HTTPError as e:
            item.update(http=e.code,error=f"HTTP_{e.code}")
        except Exception as e:
            item["error"]=type(e).__name__+":"+str(e)[:260]
        records.append(item)
        print("SOURCE",name,"RESULT",item["status"],"HTTP",item["http"],"ERROR",item.get("error"))
    report={"schema":"R18_TEST_ONLY_RECOVERY","release_approved":False,"source_results":records}
    pathlib.Path("r18_live_recovery_report.json").write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
    print("SOURCE_PASS",sum(v["valid_data"] for v in records),"/",len(records),"RELEASE_APPROVED=false")
if __name__=="__main__":main()
