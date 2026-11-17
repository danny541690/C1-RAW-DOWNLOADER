#!/usr/bin/env python3
"""Real TDCC 2025-11-28 4609 HTML read-only fixture from preexisting v0.97 Drive.
Validates genuine page structure, source metadata and full native 17-tier rows.
This is test evidence, not official numerical source approval or Silver Ready.
"""
import os,sys
from scripts.v097_bronze_autopilot import source_api
from scripts.v097_g2g3_tdcc_native_html import inspect
from scripts.v097_g2g3_native_headers import header_for
from scripts.v097_v3_contract_registry import infer
from scripts.v097_seven_historical_format_registry import OFFICIAL_VERSIONS
FILE_ID="1--oAGav1QBgijxyNgkM3NVR5JiJ5oAgC"
FILENAME="distribution_20251128_4609_989c1986d35efa05f5efb11c4999cb90109fd498234e02b8e7cd64c877c2565d.html"
if __name__=="__main__":
    api,control,quality,match,load_json,put_once,upsert,call=source_api()
    blob=call(lambda:api.files().get_media(fileId=FILE_ID))
    data=inspect(blob,FILENAME)
    native=header_for(blob,FILENAME,"TDCC")
    era=OFFICIAL_VERSIONS["TDCC"]["periods"][-1]["id"]
    candidate=infer("TDCC",native.get("header",[]),era,metadata=native.get("source_metadata"))
    assert data["metadata"]["code"].get("value")=="4609"
    assert data["metadata"]["date"].get("value")=="2025-11-28"
    assert data.get("data_rows")==17
    assert data["metadata"]["filename_consistent"] is True
    assert candidate["status"]=="COMPLETE_HEADER_CANDIDATE_UNCERTIFIED"
    assert not candidate["silver_schema_ready"] and not data["release"]
    qa={"run":os.getenv("GITHUB_RUN_ID","manual"),"source":"TDCC",
        "file_id":FILE_ID,"code":data["metadata"]["code"]["value"],
        "date":data["metadata"]["date"]["value"],
        "native_status":data["status"],"rows":data.get("data_rows"),
        "issues":data.get("issues"),"candidate_status":candidate["status"],
        "g2_verified":False,"g3_verified":False,"schema_ready":False,
        "silver_gold_materialized":False}
    rid=put_once(api,quality,"v097_TDCC_NATIVE_LIVE_FIXTURE_"+qa["run"]+".json",qa)
    print("TDCC_NATIVE_LIVE_FIXTURE="+__import__("json").dumps({**qa,"report_id":rid},ensure_ascii=False),flush=True)
