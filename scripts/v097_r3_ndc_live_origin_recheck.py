"""Independent NDC official server re-fetch versus original archived XLSX SHA.

A failed live fetch is an unavailable historical origin, NOT a corrupt Bronze.
Never promotes a template or issues G2 merely because URL matches.
"""
import hashlib,json,os,urllib.parse,requests
from scripts.v097_bronze_autopilot import source_api
from scripts.v097_bronze_first_pipeline import put_once
RUN=os.getenv("GITHUB_RUN_ID","manual")
def main():
 api,control,quality,match,load,_,_,call=source_api()
 folder=match(api,quality,"R3_G2_FIRST_REAL_CERT_PILOT_ISOLATED")
 prior=match(api,folder["id"],"r3_g2_first_real_cert_discovery_run_44256183662.json")
 doc=load(api,prior["id"])
 archive=next(s for s in doc["sources"] if s["source"]=="NDC")["records"][0]["source_archive"]
 url=archive["url"];parsed=urllib.parse.urlparse(url)
 if parsed.scheme!="https" or (parsed.hostname or "").lower()!="ws.ndc.gov.tw":raise RuntimeError("UNTRUSTED_OFFICIAL_ORIGIN")
 saved=call(lambda:api.files().get_media(fileId=archive["file_id"]))
 if hashlib.sha256(saved).hexdigest()!=archive["sha256"]:raise RuntimeError("ARCHIVE_SHA_INVALID")
 outcome={"schema":"R3_NDC_ORIGINAL_OFFICIAL_HOST_BYTE_RECHECK_V1","run":RUN,
  "archive_sha256":archive["sha256"],"archived_bytes_verified":True,
  "source_url":url,"official_remote_byte_match":False,
  "official_remote_available":False,"release_policy":"NO_G2_PASS_WITHOUT_ERA_PIT_AND_REVIEW"}
 try:
  response=requests.get(url,timeout=22,stream=True,headers={"User-Agent":"JARVIS-R3-official-source-evidence/1.0"})
  outcome["http_status"]=response.status_code
  if response.status_code==200:
   h=hashlib.sha256();total=0
   for chunk in response.iter_content(chunk_size=65536):
    if chunk:
     total+=len(chunk)
     if total>3*1024*1024:raise RuntimeError("OFFICIAL_SOURCE_BYTES_LIMIT")
     h.update(chunk)
   outcome["official_remote_available"]=True
   outcome["official_remote_bytes"]=total
   outcome["official_remote_sha256"]=h.hexdigest()
   outcome["official_remote_byte_match"]=(h.hexdigest()==archive["sha256"])
 except (requests.RequestException,RuntimeError) as e:
  outcome["unavailable_reason"]=type(e).__name__
  outcome["formal_origin_status"]="HOLD_REMOTE_ORIGINAL_TEMPORARILY_UNAVAILABLE"
 outcome["formal_origin_status"]="REMOTE_BYTES_SHA_VERIFIED" if outcome["official_remote_byte_match"] else outcome.get("formal_origin_status","HOLD_REMOTE_BYTES_NOT_MATCHED")
 receipt="r3_ndc_official_remote_source_run_"+RUN+".json"
 fid=put_once(api,folder["id"],receipt,outcome)
 if load(api,fid)!=outcome:raise RuntimeError("REMOTE_PROBE_RECEIPT_MISMATCH")
 print("R3_NDC_REMOTE_OFFICIAL_SOURCE="+json.dumps({
  "run":RUN,"remote_available":outcome["official_remote_available"],
  "remote_sha_match":outcome["official_remote_byte_match"],
  "formal_origin_status":outcome["formal_origin_status"],
  "receipt":receipt,"receipt_id":fid,"readback":True
 },sort_keys=True),flush=True)
if __name__=="__main__":main()
