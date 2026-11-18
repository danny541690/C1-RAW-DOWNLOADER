"""Read-only seven-source frozen manifest date-field diagnostic; no raw IDs."""
import json
from collections import Counter
from scripts.v097_bronze_autopilot import source_api
from scripts.v097_v3_preflight import read_baseline,assert_cohort
from scripts.v097_r3_gate_core import SOURCES
FIELDS=("data_date","date","year","month","year_month","period","period_start","source_month","file_name","source_path","dataset","dataset_candidate")
def main():
 api,control,quality,match,load_json,_,_,_=source_api()
 for src in SOURCES:
  rows=read_baseline(api,quality,match,load_json,src);assert_cohort(rows,src)
  nonempty=Counter();examples={};keys=Counter()
  for r in rows:
   keys.update(r.keys())
   for k in FIELDS:
    v=r.get(k)
    if v is not None and str(v).strip():
     nonempty[k]+=1
     if k not in ("file_name","source_path") and k not in examples:examples[k]=str(v)[:20]
  out={"source":src,"count":len(rows),"keys":sorted(keys),
       "nonempty":dict(nonempty),"examples_without_paths":examples}
  print("R3_G2_BASELINE_DATE_FIELDS="+json.dumps(out,ensure_ascii=False,sort_keys=True),flush=True)
if __name__=="__main__":main()
