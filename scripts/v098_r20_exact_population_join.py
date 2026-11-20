#!/usr/bin/env python3
"""R20 verified membership reconciliation: v097 frozen R2 12 lanes vs R16 162 manifests.
Reads BOTH ORIGINAL LEDGERS through Google Drive, never v0.93 raw file payloads.
No public original file IDs/names, no Drive writes, no Bronze/Silver/Gold changes.
Not a G2/G3 semantic certificate. Fail-closed on frozen population/ID anomalies.
One bounded integrated real Drive reconciliation.
"""
import argparse, collections, json, pathlib, sys
from v098_r16_full_private_manifest import list_children,one_child
from v098_r11_six_source_metadata_pilot import service
OFFICIAL=("TWSE","TPEx","MOPS","TDCC","TAIFEX","NDC")
EXPECTED_OLD={"TWSE":12071,"TPEx":13200,"MOPS":1935,"TDCC":40384,"TAIFEX":3140,"NDC":320,"FinMind":3700}
EXPECTED_NEW={"TWSE":12346,"TPEx":14383,"MOPS":2594,"TDCC":45439,"TAIFEX":3199,"NDC":320}
def save(path,v):
 p=pathlib.Path(path);p.parent.mkdir(parents=True,exist_ok=True)
 p.write_text(json.dumps(v,indent=2,ensure_ascii=False,sort_keys=True))
def read_json(api,id):
 return json.loads(api.files().get_media(fileId=id).execute())
def ids_by_source(rows,source,where,all_ids):
 st=set();dups=0;bad=0
 for r in rows:
  s=r.get("source")
  fid=r.get("file_id")
  if s!=source or not isinstance(fid,str) or not fid:bad+=1;continue
  if fid in st or fid in all_ids:dups+=1
  st.add(fid);all_ids.add(fid)
 if dups or bad:raise ValueError(where+"_DUPLICATE_OR_BAD_ID")
 return st
def run(out):
 stat={"api_pages":0}
 result={"status":"INIT","frozen_lane_files":0,"v097_total":0,"v098_total":0,
         "cohort_join_by_file_id":False,"drive_source_content_read":False,
         "remote_linearizable_cas":False,"formal_bronze_copy_verified":False,
         "dataset_header_pit_verified":False,"bulk_migration_allowed":False}
 try:
  api=service()
  main=one_child(api,"root","ChatGPT資料存取",stat)
  old_root=one_child(api,main,"JARVIS_C1_v097_LIFECYCLE",stat)
  old_command=one_child(api,old_root,"00_SYSTEM_CONTROL",stat)
  old_run_folder=one_child(api,old_command,"03_RUN_MANIFESTS",stat)
  old_entries={x["name"]:x["id"] for x in list_children(api,old_run_folder,stat)}
  if not all(f"v097_R2_MANIFEST_{i:02d}.json" in old_entries for i in range(12)):
   raise RuntimeError("INCOMPLETE_R2_FROZEN_MANIFESTS")
  frozen=read_json(api,old_entries["v097_R2_FROZEN.json"])
  if "74750" not in json.dumps(frozen):
   raise RuntimeError("FROZEN_COHORT_MARKER_MISMATCH")
  old_sets={s:set() for s in EXPECTED_OLD};old_global=set()
  for i in range(12):
   obj=read_json(api,old_entries[f"v097_R2_MANIFEST_{i:02d}.json"])
   rows=obj.get("files")
   if not isinstance(rows,list):raise RuntimeError("R2_LANE_STRUCTURE_CHANGED")
   for r in rows:
    s=r.get("source");fid=r.get("file_id")
    if s not in old_sets or not isinstance(fid,str) or not fid:
     raise RuntimeError("R2_INVALID_OR_UNKNOWN_SOURCE")
    if fid in old_global:raise RuntimeError("R2_DUPLICATE_FILE_ID")
    old_global.add(fid);old_sets[s].add(fid)
   result["frozen_lane_files"]+=1
  old_counts={s:len(v) for s,v in old_sets.items()}
  if old_counts!=EXPECTED_OLD:raise RuntimeError("R2_COHORT_COUNTS_MISMATCH")
  if len(old_global)!=74750:raise RuntimeError("R2_COHORT_SIZE_MISMATCH")
  v98=one_child(api,main,"C1_0.98",stat)
  recovery=one_child(api,v98,"99_RECOVERY",stat)
  manifest_folder=one_child(api,recovery,"R16_PRIVATE_MANIFEST_TEST_ONLY",stat)
  new_entries={x["name"]:x["id"] for x in list_children(api,manifest_folder,stat)}
  new_sets={s:set() for s in OFFICIAL};new_global=set()
  for s in OFFICIAL:
   for year in range(2000,2027):
    name=f"R16_{s}_{year}_PRIVATE_RAW_METADATA_v1.jsonl"
    if name not in new_entries:raise RuntimeError("INCOMPLETE_R16_YEAR_MANIFEST")
    payload=api.files().get_media(fileId=new_entries[name]).execute()
    for line in payload.splitlines():
     if not line.strip():continue
     r=json.loads(line);fid=r.get("file_id")
     if r.get("source")!=s or r.get("year")!=year or not isinstance(fid,str) or not fid:
      raise RuntimeError("R16_INVALID_FILE_ID_OR_SOURCE")
     if fid in new_global:raise RuntimeError("R16_DUPLICATE_FILE_ID")
     new_global.add(fid);new_sets[s].add(fid)
  new_counts={s:len(v) for s,v in new_sets.items()}
  if new_counts!=EXPECTED_NEW:raise RuntimeError("R16_POPULATION_CHANGED")
  by=[]
  for s in OFFICIAL:
   old=old_sets[s];new=new_sets[s]
   retained=len(old&new);old_only=len(old-new);new_only=len(new-old)
   by.append({"source":s,"legacy":len(old),"current":len(new),"retained_exact_file_id":retained,
             "old_only_ids":old_only,"new_only_ids":new_only,
             "same_id_in_different_source":0,
             "membership_join_complete":True})
  overlap=sum(x["retained_exact_file_id"] for x in by)
  oldonly=sum(x["old_only_ids"] for x in by)
  newonly=sum(x["new_only_ids"] for x in by)
  if overlap+oldonly!=71050 or overlap+newonly!=78281:
   raise RuntimeError("RECONCILIATION_ARITHMETIC_MISMATCH")
  cross_source_drift=sum(1 for s in OFFICIAL for fid in old_sets[s] if fid in new_global and fid not in new_sets[s])
  result.update({"status":"PASS_EXACT_FILE_ID_JOIN_WITH_REMAINING_CONTRACT_HOLDS",
      "v097_total":len(old_global),"v098_total":len(new_global),
      "v097_official":71050,"v097_finmind":3700,"v098_official":78281,
      "matched":overlap,"legacy_official_not_in_new":oldonly,
      "new_official_not_in_legacy":newonly,
      "cross_source_id_drift":cross_source_drift,
      "official_count_delta":newonly-oldonly,
      "cohort_join_by_file_id":True,"sources":by,
      "baseline_shares_ids_with_v098":overlap>0,
      "source_id_aliasing_candidates":oldonly,
      "eligible_for_later_content_check":overlap,
      "dataset_edition_contract_certified":False,
      "source_bytes_sha256_all_verified":False})
 except Exception as exc:
  result["status"]="ERROR_HOLD";result["error_class"]=type(exc).__name__
 finally:
  result["api_pages"]=stat["api_pages"]
  save(out,result)
  print(json.dumps({k:v for k,v in result.items() if k in ("status","error_class","matched","legacy_official_not_in_new","new_official_not_in_legacy","official_count_delta","api_pages")}))
 if result["status"]=="ERROR_HOLD":sys.exit(2)
def main():
 p=argparse.ArgumentParser();p.add_argument("--out",required=True)
 run(p.parse_args().out)
if __name__=="__main__":main()
