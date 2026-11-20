#!/usr/bin/env python3
"""R20B actual frozen-membership join. v097 G2G3 SOURCE_DETAIL Run 44653667173
has the real 74750 source_id cohort; R2_FROZEN is a DIFFERENT 82273 candidate
population and must never be substituted. Read-only in Google Drive.
Output only aggregate counts to public GitHub Actions; no source IDs published.
"""
import argparse,collections,json,pathlib,sys
from v098_r11_six_source_metadata_pilot import SOURCES,service
from v098_r16_full_private_manifest import list_children,one_child
OLD={"TWSE":12071,"TPEx":13200,"MOPS":1935,"TDCC":40384,"TAIFEX":3140,"NDC":320,"FinMind":3700}
NEW={"TWSE":12346,"TPEx":14383,"MOPS":2594,"TDCC":45439,"TAIFEX":3199,"NDC":320}
def save(path,obj):
 p=pathlib.Path(path);p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(obj,indent=2,sort_keys=True))
def audit(source,out):
 stat={"api_pages":0}
 result={"source":source,"status":"STARTED","old_count":0,"new_count":0,
         "matched_same_file_id":0,"old_only":0,"new_only":0,
         "old_contract_candidate_not_g2_verified":0,
         "bulk_migration_allowed":False}
 try:
  api=service()
  main=one_child(api,"root","ChatGPT資料存取",stat)
  prior=one_child(api,main,"JARVIS_C1_v097_LIFECYCLE",stat)
  quality=one_child(api,prior,"03_DATA_QUALITY",stat)
  reports=one_child(api,quality,"07_VERIFICATION_REPORTS",stat)
  oldname=f"v097_G2G3_SOURCE_DETAIL_{source}_44653667173.json"
  matching=[f for f in list_children(api,reports,stat) if f["name"]==oldname]
  if len(matching)!=1:raise RuntimeError("MISSING_OR_DUPLICATE_74750_SOURCE_DETAIL")
  old=json.loads(api.files().get_media(fileId=matching[0]["id"]).execute())
  entries=old.get("records")
  if old.get("source")!=source or not isinstance(entries,list):raise RuntimeError("OLD_DETAIL_INVALID")
  oldids=set()
  for row in entries:
   fid=row.get("source_id")
   if row.get("source")!=source or not isinstance(fid,str) or not fid or fid in oldids:
    raise RuntimeError("OLD_DETAIL_BAD_OR_DUPLICATE_ID")
   oldids.add(fid)
   result["old_contract_candidate_not_g2_verified"]+=int(not row.get("g2_verified",False))
  if len(oldids)!=OLD[source]:raise RuntimeError("OLD_COHORT_SOURCE_COUNT_DRIFT")
  newids=set()
  if source!="FinMind":
   v98=one_child(api,main,"C1_0.98",stat)
   recovery=one_child(api,v98,"99_RECOVERY",stat)
   private=one_child(api,recovery,"R16_PRIVATE_MANIFEST_TEST_ONLY",stat)
   manifests={f["name"]:f["id"] for f in list_children(api,private,stat)}
   for year in range(2000,2027):
    fname=f"R16_{source}_{year}_PRIVATE_RAW_METADATA_v1.jsonl"
    if fname not in manifests:raise RuntimeError("MISSING_R16_YEAR")
    raw=api.files().get_media(fileId=manifests[fname]).execute()
    for line in raw.splitlines():
     if not line.strip():continue
     row=json.loads(line);fid=row.get("file_id")
     if row.get("source")!=source or row.get("year")!=year or not isinstance(fid,str) or not fid or fid in newids:
      raise RuntimeError("NEW_MANIFEST_INVALID_OR_DUPLICATE_ID")
     newids.add(fid)
   if len(newids)!=NEW[source]:raise RuntimeError("NEW_COHORT_SOURCE_COUNT_DRIFT")
  matched=len(oldids&newids)
  result.update({"old_count":len(oldids),"new_count":len(newids),
                 "matched_same_file_id":matched,"old_only":len(oldids-newids),
                 "new_only":len(newids-oldids),
                 "new_census_excludes_finmind":source=="FinMind",
                 "status":"PASS_EXACT_SOURCE_ID_MEMBERSHIP_WITH_CONTRACT_HOLD"})
 except Exception as exc:
  result["status"]="ERROR_HOLD";result["error_class"]=type(exc).__name__
 finally:
  result["api_pages"]=stat["api_pages"];save(out,result)
  print(json.dumps({k:v for k,v in result.items() if k in ("source","status","old_count","new_count","matched_same_file_id","old_only","new_only","error_class")}))
 if result["status"]=="ERROR_HOLD":sys.exit(2)
if __name__=="__main__":
 p=argparse.ArgumentParser();p.add_argument("--source",required=True,choices=tuple(OLD))
 p.add_argument("--out",required=True);x=p.parse_args();audit(x.source,x.out)
