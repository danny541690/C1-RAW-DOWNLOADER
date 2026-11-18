"""R3 six source original-download provenance mining for real 60 frozen files.

Read source manifest and bounded ZIP member headers, not merely official page.
Output exact original-download URL candidates, explicit data/asof fields and
structural dataset candidates. A URL is unverified until official byte-matched
and historical effective schema confirmed. No G2 PASS fabricated.
"""
from __future__ import annotations
import collections,hashlib,io,json,os,re,zipfile
from urllib.parse import urlparse
from scripts.v097_bronze_autopilot import source_api
from scripts.v097_v3_preflight import read_baseline,assert_cohort
from scripts.v097_bronze_first_pipeline import put_once

RUN=os.getenv("GITHUB_RUN_ID","manual")
SOURCES=("TWSE","TPEx","MOPS","TDCC","TAIFEX","FinMind")
INPUT="R3_G2_SIX_SOURCE_REAL_SMALL_PILOT_ISOLATED"
OUTPUT="R3_G2_SIX_SOURCE_ORIGINAL_URL_PROVENANCE_ISOLATED"
PRIOR="44261840978"
URL_RE=re.compile(r'https?://[^\s"\'<>]{7,}',re.I)
FIELDS=("source_url","original_url","download_url","request_url","url","endpoint","api_url","asof","captured_utc","retrieved_at","source_archive","source_name","dataset","date","month","publication_date","report_date","issuer","type","origin_name")
ALLOWED={"TWSE":("twse.com.tw",),"TPEx":("tpex.org.tw",),"MOPS":("twse.com.tw",),
         "TDCC":("tdcc.com.tw",),"TAIFEX":("taifex.com.tw",),
         "FinMind":("finmindtrade.com","finmind.github.io","github.com")}
def owned(src,url):
 try:
  host=(urlparse(url).hostname or "").lower()
  return urlparse(url).scheme=="https" and any(host==d or host.endswith("."+d) for d in ALLOWED[src])
 except (ValueError,TypeError):return False
def inspect_json(src,label,data):
 result={"source_member":label,"sha256":hashlib.sha256(data).hexdigest(),
         "official_endpoints":[],"provider_endpoints":[],"native_metadata_keys":[],
         "documented_source_metadata":{},"is_canonical_original_source_verified":False}
 try:
  txt=data.decode("utf-8-sig")
  obj=json.loads(txt)
 except (UnicodeError,ValueError):return result
 if isinstance(obj,dict):
  result["native_metadata_keys"]=list(obj)[:45]
  for k in FIELDS:
   if k not in obj:continue
   value=obj[k]
   if k in ("source_archive",) and isinstance(value,dict):
    result["documented_source_metadata"][k]={x:str(value[x])[:120] for x in ("url","sha256","captured_utc","file_id") if x in value}
   elif isinstance(value,(str,int,float,bool)):
    result["documented_source_metadata"][k]=str(value)[:120]
  for url in URL_RE.findall(txt[:100000]):
   url=url.rstrip(".,;)")
   if owned(src,url) and url not in result["official_endpoints"]:
    result["official_endpoints"].append(url[:500])
 return result

def main():
 api,control,quality,match,load,_,_,call=source_api()
 priorfolder=match(api,quality,INPUT)
 if not priorfolder:raise RuntimeError("PRIOR_60_NATIVE_PROOF_NOT_FOUND")
 output=match(api,quality,OUTPUT)
 if not output:
  output=call(lambda:api.files().create(body={"name":OUTPUT,"parents":[quality],
       "mimeType":"application/vnd.google-apps.folder"},fields="id,mimeType"))
 if output.get("mimeType")!="application/vnd.google-apps.folder":raise RuntimeError("WRONG_QA_FOLDER")
 allsum=[];total=0
 for src in SOURCES:
  prior=match(api,priorfolder["id"],f"r3_g2_pilot_{src}_10_run_{PRIOR}.json")
  if not prior:raise RuntimeError("MISSING_PREVIOUS_FROZEN_SAMPLE")
  samples=load(api,prior["id"])["samples"]
  rows=read_baseline(api,quality,match,load,src);assert_cohort(rows,src)
  index={r["source_id"]:r for r in rows}
  if len(samples)!=10:raise RuntimeError("PREVIOUS_SAMPLE_TEN_DRIFT")
  out=[];counts=collections.Counter()
  for s in samples:
   row=index.get(s["source_id"])
   if not row:raise RuntimeError("SOURCE_NOT_IN_BASELINE")
   meta=call(lambda:api.files().get(fileId=row["destination_id"],fields="id,size,mimeType"))
   if int(meta.get("size") or 0)>3_000_000:
    counts["FILE_TOO_LARGE"]+=1
    out.append({"source_id":row["source_id"],"reason":"FILE_TOO_LARGE","formal_status":"HOLD"})
    continue
   blob=call(lambda:api.files().get_media(fileId=row["destination_id"]))
   if hashlib.sha256(blob).hexdigest()!=row["source_sha256"]:
    raise RuntimeError("REAL_BRONZE_SHA_CHANGED_"+src)
   infos=[]
   if zipfile.is_zipfile(io.BytesIO(blob)):
    with zipfile.ZipFile(io.BytesIO(blob)) as z:
     members=[m for m in z.infolist() if not m.is_dir()]
     if len(members)>250 or sum(m.file_size for m in members)>30_000_000:
      counts["LARGE_ARCHIVE_HOLD"]+=1
      out.append({"source_id":row["source_id"],"reason":"ZIP_EXPAND_GUARD","formal_status":"HOLD"})
      continue
     for member in members:
      if member.file_size>300_000:
       counts["LARGE_MEMBER_SKIPPED"]+=1
       continue
      if member.filename.lower().endswith(".json") or member.filename.lower().endswith(".raw"):
       raw=z.read(member)
       infos.append(inspect_json(src,member.filename,raw))
   else:
    if blob.lstrip().startswith((b"{",b"[")):
     infos.append(inspect_json(src,"direct_json",blob))
   exact_urls=sorted({u for m in infos for u in m["official_endpoints"]})
   metadata=sum(bool(m["documented_source_metadata"]) for m in infos)
   counts["SAMPLE_SHA_OK"]+=1
   counts["HAS_EXPLICIT_METADATA"]+=bool(metadata)
   counts["HAS_EXPLICIT_ORIGIN_URL_CANDIDATE"]+=bool(exact_urls)
   out.append({"source_id":row["source_id"],"source_sha256":row["source_sha256"],
     "file_origin_url_candidates":exact_urls[:30],
     "native_evidence":infos[:30],
     "dataset_era_official_document_verified":False,
     "formal_status":"HOLD",
     "hold_reason":"ORIGINAL_DOWNLOAD_BYTE_IDENTITY_AND_HISTORIC_SCHEMA_NOT_YET_PROVEN"})
  report={"schema":"R3_G2_ORIGINAL_URL_PROVENANCE_SOURCE_V1","run":RUN,
     "source":src,"sample_count":len(samples),"counts":dict(counts),
     "per_file_provenance":out,"bronze_read_only":True,
     "g2_pass":0,"g2_hold":len(samples),"no_silver_gold":True}
  name=f"r3_g2_original_provenance_{src}_run_{RUN}.json"
  fid=put_once(api,output["id"],name,report)
  if load(api,fid)!=report:raise RuntimeError("NATIVE_PROVENANCE_DRIVE_READBACK_FAILED")
  item={"source":src,"sample":len(samples),"counts":dict(counts),"g2_pass":0,
        "g2_hold":len(samples),"receipt_id":fid,"readback":True}
  allsum.append(item);total+=len(samples)
  print("R3_G2_ORIGINAL_PROVENANCE_SOURCE="+json.dumps(item,ensure_ascii=False,sort_keys=True),flush=True)
 if total!=60:raise RuntimeError("TOTAL_SIX_SAMPLES_DRIFT")
 master={"schema":"R3_G2_SIX_SOURCE_ORIGINAL_DOWNLOAD_PROVENANCE_MASTER_V1",
    "run":RUN,"source_count":6,"samples":60,"formal_new_g2_pass":0,
    "sources":allsum,"bronze_modified":False,"silver_gold_materialized":False}
 mname=f"r3_g2_original_download_provenance_master_run_{RUN}.json"
 mid=put_once(api,output["id"],mname,master)
 if load(api,mid)!=master:raise RuntimeError("MASTER_PROVENANCE_REMOTE_READBACK_FAILED")
 print("R3_G2_ORIGINAL_PROVENANCE_MASTER="+json.dumps({"run":RUN,
  "samples":60,"master_id":mid,"master_name":mname,"sources":allsum,
  "readback":True},ensure_ascii=False,sort_keys=True),flush=True)

if __name__=="__main__":main()
