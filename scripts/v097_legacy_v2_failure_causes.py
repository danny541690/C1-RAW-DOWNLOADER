#!/usr/bin/env python3
"""Classify V2 legacy repair exceptions from checkpoint/receipts; no mutations."""
import re,os,json
from collections import Counter,defaultdict
from scripts.v097_bronze_first_pipeline import service,common,match,load_json,put_once,children
RUN=os.getenv("GITHUB_RUN_ID","manual")
def main():
    api=service();m,c,q,_=common(api)
    out={}
    for source in ("MOPS","TPEx"):
        prefix="v097_LEGACY_TPEX_MOPS_V2_"+source
        allholds={}
        for lane in range(6):
            f=match(api,c,prefix+"_CK_%02d.json"%lane)
            if not f:continue
            for fid,record in load_json(api,f["id"])["done"].items():
                if record.get("state")=="LEGACY_REPAIR_HOLD":
                    allholds[fid]={"lane":lane,"checkpoint":record}
        causes=Counter();examples={};seen=set()
        rx=re.compile("^"+re.escape(prefix)+r"_\d+_L\d\d_O\d+\.json$")
        for item in children(api,q):
            if not rx.match(item["name"]):continue
            receipt=load_json(api,item["id"])
            for row in receipt.get("rows",[]):
                fid=row.get("file_id")
                if fid not in allholds or row.get("state")!="LEGACY_REPAIR_HOLD":continue
                if fid in seen:continue
                seen.add(fid)
                e=str(row.get("error") or "MISSING_ERROR")
                category=e.split(":",1)[-1].split(":",1)[0][:85]
                causes[category]+=1
                examples.setdefault(category,{"file_id":fid,"error":e,"lane":allholds[fid]["lane"]})
        out[source]={"holds":len(allholds),"explained":len(seen),
           "by_cause":dict(causes),"examples":examples}
    report={"schema":"v097_legacy_v2_exception_causes_1","run":RUN,
       "by_source":out,"originals_modified":False}
    put_once(api,q,"v097_LEGACY_V2_ERROR_CAUSES_"+RUN+".json",report)
    print("LEGACY_V2_ERRORS="+json.dumps(report,ensure_ascii=False),flush=True)
if __name__=="__main__":main()
