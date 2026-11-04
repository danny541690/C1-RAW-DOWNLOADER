"""R20 isolated full TDCC read + real Parquet candidate + QA-only grouped summary.
No secrets, no Drive/main writes, never authorizes production. Bounds 96MiB.
"""
import hashlib,json,pathlib,urllib.request,urllib.error,collections,datetime
import pyarrow as pa
import pyarrow.parquet as pq
ROOT=pathlib.Path("r20_tdcc_full")
ROOT.mkdir(exist_ok=True)
URL="https://openapi.tdcc.com.tw/v1/opendata/1-5"
MAX_BYTES=96*1024*1024
def sha_file(path):
    h=hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda:f.read(1024*1024),b""):h.update(chunk)
    return h.hexdigest()
def main():
    result={"schema":"JARVIS_R20_TDCC_FULL_TEST","source":"TDCC","release_approved":False,
      "status":"BLOCKED","pit_verified":False,"numeric_verified":False,
      "full_bronze_verified":False,"gold_production_approved":False}
    try:
        p=ROOT/"bronze.json"
        request=urllib.request.Request(URL,headers={"User-Agent":"Mozilla/5.0 (JARVIS-v095 R20 isolated)","Accept":"application/json"})
        count=0
        with urllib.request.urlopen(request,timeout=45) as resp,p.open("wb") as f:
            result["http"]=resp.status
            while True:
                chunk=resp.read(1024*1024)
                if not chunk:break
                count+=len(chunk)
                if count>MAX_BYTES:raise ValueError("MAX_BYTES_96M_EXCEEDED")
                f.write(chunk)
        if not count:raise ValueError("EMPTY_BRONZE")
        result["bronze_bytes"]=count
        result["bronze_sha256"]=sha_file(p)
        data=json.loads(p.read_text(encoding="utf-8-sig"))
        if not isinstance(data,list) or not data or not isinstance(data[0],dict):
            raise ValueError("NOT_NONEMPTY_JSON_OBJECT_ARRAY")
        keys=list(data[0])
        if not any(x in "".join(keys) for x in ["證券代號","股票代號","持股","集保戶","股權"]):
            raise ValueError("INCORRECT_TDCC_SCHEMA")
        result["source_rows"]=len(data)
        result["source_fields"]=keys[:25]
        # Preserve every source column; no conversion guess of units or publication time.
        # Convert to a lossless JSON-lines payload within Parquet for bounded schema drift.
        candidate=[{"source":"TDCC","source_record_json":json.dumps(row,ensure_ascii=False,sort_keys=True,default=str),
                    "source_row_number":i,"source_sha256":result["bronze_sha256"]}
                    for i,row in enumerate(data)]
        silver=ROOT/"silver_candidate.parquet"
        pq.write_table(pa.Table.from_pylist(candidate),silver,compression="zstd")
        back=pq.read_table(silver).to_pylist()
        if len(back)!=len(data):raise AssertionError("ROW_COUNT_READBACK")
        for i in [0,len(back)//2,len(back)-1]:
            if json.loads(back[i]["source_record_json"])!=data[i]:raise AssertionError("CONTENT_READBACK")
        result["silver_bytes"]=silver.stat().st_size
        result["silver_sha256"]=sha_file(silver)
        # Only structural metrics; no investment metrics without domain and PIT review.
        qa={"metric":"structural_row_count_QA_ONLY","value":len(data),
            "unique_full_record_sha_count":len(set(hashlib.sha256(x["source_record_json"].encode()).hexdigest() for x in back)),
            "bronze_sha256":result["bronze_sha256"],"silver_sha256":result["silver_sha256"],
            "numeric_verified":False,"pit_verified":False,"release_approved":False}
        gold=ROOT/"gold_qa_only.json";gold.write_text(json.dumps(qa,ensure_ascii=False,indent=2))
        if json.loads(gold.read_text())!=qa:raise AssertionError("GOLD_READBACK")
        result["full_bronze_verified"]=True
        result["status"]="PASS_FULL_BRONZE_SILVER_GOLD_QA_ONLY"
        # raw retained in GitHub artifact as independent candidate: has no production approval.
    except Exception as e:
        result["error"]=type(e).__name__+":"+str(e)[:300]
    (ROOT/"report.json").write_text(json.dumps(result,ensure_ascii=False,indent=2))
    print("R20_TDCC_STATUS="+result["status"])
    print("R20_BYTES="+str(result.get("bronze_bytes")))
    print("R20_ROWS="+str(result.get("source_rows")))
    print("R20_RELEASE_APPROVED=false")
if __name__=="__main__":main()
