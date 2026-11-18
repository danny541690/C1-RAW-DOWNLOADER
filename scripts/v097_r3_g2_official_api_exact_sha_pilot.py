"""R3 TWSE/TPEx historical official API response re-download SHA crosscheck.

For every selected real ZIP sample, attempt original official endpoint URL
already found INSIDE archive. Compare live response sha256 with the exact
source-member sha256; no host or url inference. Historic data can be revised,
and HTTP 200 alone never certifies the original source edition.
"""
from __future__ import annotations
import collections,hashlib,json,os,requests
from urllib.parse import urlparse
from scripts.v097_bronze_autopilot import source_api
from scripts.v097_bronze_first_pipeline import put_once

RUN=os.getenv("GITHUB_RUN_ID","manual")
INPUT="R3_G2_SIX_SOURCE_ORIGINAL_URL_PROVENANCE_ISOLATED"
OUTPUT="R3_G2_ORIGINAL_OFFICIAL_API_BYTE_CROSSCHECK_ISOLATED"
OLD_RUN="44266749919"
SOURCES=("TWSE","TPEx")
def allowed(src,url):
 h=(urlparse(url).hostname or "").lower()
 return urlparse(url).scheme=="https" and h.endswith(".twse.com.tw") if src=="TWSE" else urlparse(url).scheme=="https" and h.endswith(".tpex.org.tw")
def attempt(src,source,url):
 trial={"source_id":source["source_id"],"url":url,"reason":None,
        "origin_response_exact_member_sha":False,"is_historically_applicable_dataset_edition":False}
 if not allowed(src,url):
  trial["reason"]="HOST_NOT_AUTHORITATIVE_FOR_SOURCE";return trial
 try:
  r=requests.get(url,timeout=15,stream=True,headers={"User-Agent":"Mozilla/5.0 (compatible; JARVIS-R3-OfficialArchiveVerifier/1.0)"})
  if not allowed(src,r.url):
   trial["reason"]="REDIRECT_NOT_ALLOWED";return trial
  trial["http_status"]=r.status_code
  if r.status_code!=200:
   trial["reason"]="HTTP_"+str(r.status_code);return trial
  sha=hashlib.sha256();count=0
  for chunk in r.iter_content(chunk_size=65536):
   count+=len(chunk)
   if count>2_000_000:
    trial["reason"]="RESPONSE_TOO_LARGE";return trial
   sha.update(chunk)
  trial["remote_bytes"]=count
  trial["remote_sha256"]=sha.hexdigest()
  allmembers=[p for p in source.get("native_evidence",[]) if isinstance(p.get("sha256"),str)]
  same=[p for p in allmembers if p["sha256"]==trial["remote_sha256"]]
  trial["matching_zip_members"]=[p["source_member"] for p in same]
  trial["origin_response_exact_member_sha"]=bool(same)
  trial["reason"]="OFFICIAL_ORIGINAL_MEMBER_SHA_MATCH" if same else "OFFICIAL_RESPONSE_BYTES_DIFFER_FROM_ARCHIVE"
 except requests.RequestException as e:
  trial["reason"]="OFFICIAL_REQUEST_"+type(e).__name__
 return trial
def main():
 api,control,quality,match,load,_,_,call=source_api()
 prior=match(api,quality,INPUT)
 if not prior:raise RuntimeError("ORIGINAL_ENDPOINT_CENSUS_NOT_FOUND")
 folder=match(api,quality,OUTPUT)
 if not folder:
  folder=call(lambda:api.files().create(body={"name":OUTPUT,"parents":[quality],
       "mimeType":"application/vnd.google-apps.folder"},fields="id,mimeType"))
 results=[];counts=collections.Counter()
 for src in SOURCES:
  priorfile=match(api,prior["id"],f"r3_g2_original_provenance_{src}_run_{OLD_RUN}.json")
  if not priorfile:raise RuntimeError("SOURCE_ORIGINAL_URL_EVIDENCE_MISSING")
  rows=load(api,priorfile["id"])["per_file_provenance"]
  targets=[]
  for row in rows:
   valid=[url for url in row.get("file_origin_url_candidates",[]) if allowed(src,url)]
   if not valid:continue
   # Limit to 4 distinct source files, one actual original URL each.
   targets.append((row,valid[0]))
   if len(targets)>=4:break
  probes=[]
  for row,url in targets:
   item=attempt(src,row,url);probes.append(item)
   counts[item["reason"]]+=1
  result={"schema":"R3_G2_OFFICIAL_ORIGINAL_RESPONSE_SHA_PILOT_V1",
          "source":src,"run":RUN,"target_files":len(targets),
          "probes":probes,"full_native_dataset_era_verified":False,
          "formal_g2_issued":0,"bronze_changed":False,
          "note":"HTTP exact member SHA only validates original bytes. Independently attest historical format edition and source publication as-of before issuing G2."}
  name=f"r3_g2_original_http_sha_{src}_run_{RUN}.json"
  id=put_once(api,folder["id"],name,result)
  if load(api,id)!=result:raise RuntimeError("REMOTE_SOURCE_PROOF_READBACK_MISMATCH")
  summary={"source":src,"probes":len(probes),
      "exact_member_sha_matches":sum(v["origin_response_exact_member_sha"] for v in probes),
      "outcomes":dict(collections.Counter(p["reason"] for p in probes)),
      "receipt_id":id,"readback_verified":True}
  results.append(summary)
  print("R3_G2_OFFICIAL_HTTP_SOURCE="+json.dumps(summary,ensure_ascii=False,sort_keys=True),flush=True)
 master={"schema":"R3_G2_OFFICIAL_API_ORIGINAL_BYTES_COMPARISON_MASTER_V1",
  "run":RUN,"sources":results,"outcomes":dict(counts),
  "formal_new_approved_template_count":0,"formal_new_g2_pass":0,
  "no_bronze_changes":True,"no_silver_gold":True}
 name=f"r3_g2_real_official_http_sha_master_run_{RUN}.json"
 id=put_once(api,folder["id"],name,master)
 if load(api,id)!=master:raise RuntimeError("OFFICIAL_HTTP_MASTER_READBACK_FAILED")
 print("R3_G2_OFFICIAL_HTTP_MASTER="+json.dumps({"run":RUN,"source_results":results,
  "master_id":id,"master_name":name,"readback_verified":True},sort_keys=True,ensure_ascii=False),flush=True)
if __name__=="__main__":main()
