#!/usr/bin/env python3
"""One-shot B+C evidence contract integration tests (entirely synthetic, no production reads).
Maintains independent release gates and never authorizes Silver or Gold.
"""
import io,json,zipfile
from scripts.v097_b_format_forensics import audit as b_audit
from scripts.v097_c_manifest_numeric import audit as c_audit
from scripts.v097_bronze_autopilot import digest

def sample(source="TWSE",bad_numeric=False,wrong_hash=False,marketcap=False):
 if marketcap:
  fields=["排名","股票代號","股票名稱","發行股數","收盤價","市值(佰萬元)"]
  cells=["1","2330","測試", "1000","100","100"]
 else:
  fields=["代號","名稱","收盤","開盤","最高","最低","成交股數"]
  cells=["2330","測試","N/A" if bad_numeric else "100","99","101","98","1000"]
 payload=json.dumps({"date":"20261116","tables":[{"fields":fields,"data":[cells]}]},ensure_ascii=False).encode()
 member="original_response.raw"
 manifest={"units":[{"file":member,"sha256":"0"*64 if wrong_hash else digest(payload),
   "url":"https://www.twse.com.tw/zh/trading/historical/mi-index.html"}]}
 archive=io.BytesIO()
 with zipfile.ZipFile(archive,"w",compression=zipfile.ZIP_DEFLATED) as z:
  z.writestr(member,payload)
  z.writestr("manifest.json",json.dumps(manifest).encode())
 original=archive.getvalue()
 row={"source_id":"test","sha":digest(original),
      "source_path":"2026/"+source+"/2026-11/archive.zip","year":"2026","month":"11"}
 return row,original

def run():
 r,x=sample()
 b=b_audit("TWSE",r,x);c=c_audit("TWSE",r,x)
 assert b["status"]=="B_CONTENT_FINGERPRINTED_SOURCE_PROOF_PENDING"
 assert b["formats"]["JSON"]==2
 assert c["status"]=="C_NUMERIC_AND_MANIFEST_PARSED_OFFICIAL_RECHECK_PENDING"
 assert c["table_datasets"].get("STOCK_DAILY_OHLCV")==1
 assert c["official_host_claims_in_manifest"]==1
 assert c["official_origin_retrieved"] is False
 assert c["third_party_values_compared"] is False
 assert c["silver_ready_promoted"] is False
 r,x=sample(wrong_hash=True)
 assert c_audit("TWSE",r,x)["status"]=="HOLD_MANIFEST_LINKAGE_CONFLICT"
 r,x=sample(marketcap=True)
 c=c_audit("TWSE",r,x)
 assert c["table_datasets"].get("MARKET_CAPITALIZATION")==1
 assert "STOCK_DAILY_OHLCV" not in c["table_datasets"]
 # Preserve special missing-value codes as missing, not false illegal numbers.
 r,x=sample(bad_numeric=True)
 assert c_audit("TWSE",r,x)["status"]=="C_NUMERIC_AND_MANIFEST_PARSED_OFFICIAL_RECHECK_PENDING"
 # Non-numeric stock price is a true HOLD with bounded diagnostic.
 r,x=sample()
 with zipfile.ZipFile(io.BytesIO(x)) as z:
  payload=json.loads(z.read("original_response.raw"))
 payload["tables"][0]["data"][0][2]="INVALID_PRICE"
 modified=json.dumps(payload,ensure_ascii=False).encode()
 m={"units":[{"file":"original_response.raw","sha256":digest(modified),
             "url":"https://www.twse.com.tw/"}]}
 out=io.BytesIO()
 with zipfile.ZipFile(out,"w") as z:
  z.writestr("original_response.raw",modified)
  z.writestr("manifest.json",json.dumps(m).encode())
 r["sha"]=digest(out.getvalue())
 c=c_audit("TWSE",r,out.getvalue())
 assert c["status"]=="HOLD_NUMERIC_OR_WIDTH_CONFLICT"
 assert c["invalid_numeric_cells"]==1
 assert c["members"][0]["invalid_numeric_samples"][0]["field"]=="收盤"
 print("BC_END_TO_END_SYNTHETIC_INTEGRATION_TESTS_PASS")
if __name__=="__main__":run()
