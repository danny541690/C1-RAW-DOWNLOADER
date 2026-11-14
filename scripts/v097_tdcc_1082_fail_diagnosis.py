#!/usr/bin/env python3
"""Read frozen immutable per-file strict QA receipts, report actual failure reasons."""
import json,re
from collections import Counter
from scripts.v097_bronze_first_pipeline import service,common,children,load_json,match
api=service();_,c,q,_=common(api)
groups=Counter();examples={}
for f in children(api,q):
 if not re.match(r"^v097_TDCC_1084_INTERNAL_PROOF_RAW_(?:43521294768|43531417736)_L\d\d_O\d+(?:_[a-f0-9]{12})?\.json$",f["name"]):continue
 data=load_json(api,f["id"])
 for r in data.get("rows",[]):
  err=r.get("error","?")
  groups[(f["name"].split("_L")[0].split("_")[-1],err)]+=1
  examples.setdefault(str((f["name"].split("_L")[0].split("_")[-1],err)),{"file_id":r.get("file_id"),"date":r.get("date"),"code":r.get("code")})
print("REASONS="+json.dumps({"total":sum(groups.values()),"causes":{str(k):v for k,v in groups.items()},"examples":examples},ensure_ascii=False))
