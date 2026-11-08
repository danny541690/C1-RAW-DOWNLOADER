#!/usr/bin/env python3
"""v0.93 TAIFEX official-history CSV native archive adapter (daily+ only).

Reuses already saved original CSV bytes. The 64-character filename suffix is
checked against source bytes; validates documented dataset-native schema and
actual date range with the existing v0.93 parser. Never import TICK/minute rows
or infer release vintage, official acquisition status or complete source coverage.
"""
import hashlib,io,json,re,zipfile
from scripts.v093_taifex_monthly_content import inspect_month_csv
DATASETS=("futDataDown","largeTraderFutDown","dlLargeTraderOptDown")
PATTERN=re.compile(r"^HISTORY_("+("|".join(DATASETS))+r")_(20\d{2}-(?:0[1-9]|1[0-2]))_([a-f0-9]{64})\.csv$")
def sha(b):return hashlib.sha256(b).hexdigest()
def eligible(name,month):
 match=PATTERN.fullmatch(name)
 return bool(match and match.group(2)==month)
def package(raw,name,month,origin_file_id):
 match=PATTERN.fullmatch(name)
 if not match or match.group(2)!=month:raise ValueError("TAIFEX_UNRECOGNIZED_DAILY_DATASET")
 if sha(raw)!=match.group(3):raise ValueError("TAIFEX_LEGACY_CSV_SHA_FILENAME_MISMATCH")
 if len(raw)>20_000_000:raise ValueError("TAIFEX_CSV_OVER_BOUNDED_LIMIT")
 dataset=match.group(1)
 evidence=inspect_month_csv(raw,{"資料集":dataset,"期間":month})
 if not evidence.get("rows") or evidence.get("content_period",{}).get("min","")[:7]!=month or evidence.get("content_period",{}).get("max","")[:7]!=month:
  raise ValueError("TAIFEX_CSV_DATE_CONTENT_UNVERIFIED")
 member="official_history_"+dataset+"_"+month+".csv"
 manifest={"source":"TAIFEX","month":month,"schema":"V095_TAIFEX_V093_ORIGINAL_DAILY_CSV",
    "units":[{"file":member,"sha256":sha(raw),"source":"TAIFEX","month":month,
              "dataset":dataset,"origin_legacy_file_id":origin_file_id,
              "original_legacy_name":name,"schema_validated":True,
              "official_wire_origin_verified":False,
              "historical_pit_verified":False}],
    "source_response_rows":evidence["rows"],"status":"NATIVE_SCHEMA_DATE_SHA_PASS_PIT_PENDING"}
 buf=io.BytesIO()
 with zipfile.ZipFile(buf,"w",compression=zipfile.ZIP_DEFLATED) as archive:
  for filename,data in ((member,raw),("manifest.json",json.dumps(manifest,ensure_ascii=False,sort_keys=True).encode())):
   entry=zipfile.ZipInfo(filename,date_time=(1980,1,1,0,0,0))
   entry.compress_type=zipfile.ZIP_DEFLATED
   archive.writestr(entry,data)
 return buf.getvalue(),{"dataset":dataset,"native_sha256":sha(raw),"rows":evidence["rows"],
   "original_legacy_file_id":origin_file_id,"official_live_download":False,"pit_verified":False}
