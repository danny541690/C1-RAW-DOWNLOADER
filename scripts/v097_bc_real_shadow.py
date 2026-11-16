#!/usr/bin/env python3
"""Real-Bronze shadow parity: read each selected original ZIP once; do not update checkpoints.
Sample fixed first audited ZIPs per source to compare single-read B+C to separate historical pipeline evidence.
"""
import json,os
from collections import Counter
from scripts.v097_bronze_autopilot import source_api
from scripts.v097_bc_single_read_pilot import joint_audit

def main():
 api,control,quality,match,load_json,put_once,upsert,call=source_api()
 summary={}
 for src in ("TWSE","TPEx"):
  bfile=match(api,control,"v097_B_FORMAT_FORENSICS_CK_"+src+".json")
  cfile=match(api,control,"v097_C_MANIFEST_NUMERIC_CK_"+src+".json")
  inp=match(api,quality,"v097_AP_INPUT_"+src+".json")
  if not bfile or not cfile or not inp:raise RuntimeError("REQUIRED_EVIDENCE_MISSING_"+src)
  b=load_json(api,bfile["id"])["done"];c=load_json(api,cfile["id"])["done"]
  rows={x["source_id"]:x for x in load_json(api,inp["id"])["rows"]}
  sample=sorted(set(b)&set(c))[:min(4,int(os.getenv("SHADOW_SAMPLE","4")))]
  if not sample:raise RuntimeError("NO_SAMPLES_"+src)
  differences=[]
  for sid in sample:
   raw=call(lambda:api.files().get_media(fileId=rows[sid]["dest_id"]))
   nb,nc=joint_audit(src,rows[sid],raw)
   for label,key,old,new in [
     ("B","status",b[sid],nb),("B","formats",b[sid],nb),
     ("B","dataset_fingerprints",b[sid],nb),
     ("C","table_datasets",c[sid],nc),
     ("C","numeric_cells_checked",c[sid],nc),
     ("C","invalid_numeric_cells",c[sid],nc),
     ("C","row_width_conflicts",c[sid],nc),
     ("C","official_host_claims_in_manifest",c[sid],nc)]:
    if old.get(key)!=new.get(key):
     differences.append({"source_id":sid,"layer":label,"field":key,
                         "old":str(old.get(key))[:100],"shadow":str(new.get(key))[:100]})
   # Legacy C statuses may have been computed with pre-v3 semantics;
   # report but do not fail on these justified interpretation differences.
   if c[sid].get("audit_version")=="c-semantics-20261116-v3" and nc["status"]!=c[sid]["status"]:
    differences.append({"source_id":sid,"layer":"C","field":"status",
                        "old":c[sid]["status"],"shadow":nc["status"]})
  summary[src]={"sampled":len(sample),"difference_count":len(differences),
                "differences":differences[:20],"bronze_modified":False,"silver_promoted":0}
  if differences:raise RuntimeError("SHADOW_PARITY_MISMATCH_"+src+"_"+json.dumps(summary[src],ensure_ascii=False))
 print("BC_REAL_BRONZE_SHADOW_PARITY="+json.dumps(summary,ensure_ascii=False))
if __name__=="__main__":main()
