#!/usr/bin/env python3
"""Independent TDCC official same-day evidence extension for v0.97 5035 historical HTML.
For each of six frozen lanes sample one row per available date (bounded).
Verify SHA of ORIGINAL and 0.97 quarantine, HTML identity+totals, then compare
against contemporary official portal with same DATE/CODE and exact totals.
Third-party snapshots, if used, must be separate untrusted auxiliary evidence.
No ordinary-stock Bronze promotion for Y security IDs.
"""
import os,re,json,hashlib,requests
from collections import Counter,defaultdict
from datetime import datetime,timezone
from scripts.v097_bronze_first_pipeline import service,common,match,load_json,put_once,call
from scripts.v097_tdcc_a3_a5_auto import source_rows,FILE,html_identity,table_diagnostics
from scripts.v097_tdcc_official_same_day_compare import query as official_query
RUN=os.getenv("GITHUB_RUN_ID","manual");LANE=int(os.getenv("TDCC_SAMPLER_LANE","0"))
def sha(b):return hashlib.sha256(b).hexdigest()
def main():
 api=service();_,control,qa,_=common(api)
 frozen=source_rows(api,qa,LANE)
 f=match(api,control,"v097_V4_EXCEPTIONS_STAGED_V1_CK_%02d.json"%LANE)
 if not f:raise RuntimeError("SOURCE_QUARANTINE_CHECKPOINT_MISSING")
 copied=load_json(api,f["id"])["done"]
 dategroups=defaultdict(list)
 for row in frozen:
  m=FILE.search(str(row.get("source_path") or ""))
  if m:dategroups[m.group(1)].append((m.group(2),row))
 results=[];s=requests.Session()
 # One per covered date and lane. Maximum ten, spread across six lanes.
 for day in sorted(dategroups):
  code,row=sorted(dategroups[day],key=lambda z:z[0])[len(dategroups[day])//2]
  fid=row["file_id"]; prior=copied.get(fid,{})
  r={"date":day,"code":code,"original_id":fid,"status":"UNVERIFIED","market_bronze_promoted":False}
  try:
   if prior.get("status")!="V097_V4_QUARANTINE_SHA_PASS":raise ValueError("V4_QUARANTINE_NOT_HASH_VERIFIED")
   raw=call(lambda:api.files().get_media(fileId=fid))
   dest=call(lambda:api.files().get_media(fileId=prior["dest_id"]))
   if not raw or sha(raw)!=prior.get("source_sha256") or sha(dest)!=sha(raw):
    raise ValueError("ORIGINAL_QUARANTINE_SHA_DISAGREE")
   content_code,dates,table=html_identity(raw)
   nums=table_diagnostics(raw)
   if content_code!=code or day not in dates or nums.get("status")!="HTML_DISTRIBUTION_TOTALS_MATCH":
    raise ValueError("ORIGINAL_DATE_CODE_NUMERIC_NOT_CERTIFIED")
   probe=official_query(s,{"date":day,"code":code,
     "old_holders":nums["total_holders"],"old_shares":nums["total_shares"],
     "orig_sha":sha(raw)})
   r.update(status=probe["state"],original_holders=nums["total_holders"],
      original_shares=nums["total_shares"],original_sha256=sha(raw),
      official_response_sha256=probe.get("response_sha256"),
      official_holders=probe.get("official_distribution",{}).get("total_holders"),
      official_shares=probe.get("official_distribution",{}).get("total_shares"),
      official_error=probe.get("error"),
      same_date_code_proved=probe.get("same_code_date_proved",False))
  except Exception as exc:r.update(status="ORIGINAL_OR_OFFICIAL_PROOF_HOLD",
      error=type(exc).__name__+":"+str(exc)[:180])
  results.append(r)
 name="v097_TDCC_MANY_DATE_EVIDENCE_"+RUN+"_L%02d.json"%LANE
 counts=dict(Counter(x["status"] for x in results))
 doc={"schema":"v097_tdcc_multi_date_official_crosscheck_1",
   "run":RUN,"lane":LANE,"frozen_lane_files":len(frozen),
   "sampled_distinct_dates":len(results),
   "source":"https://www.tdcc.com.tw/portal/zh/smWeb/qryStock",
   "by_status":counts,"market_bronze_promoted":0,"rows":results}
 put_once(api,qa,name,doc)
 print("TDCC_CROSSCHECK_LANE="+json.dumps(doc,ensure_ascii=False),flush=True)
if __name__=="__main__":main()
