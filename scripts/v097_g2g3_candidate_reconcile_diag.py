#!/usr/bin/env python3
"""Diagnose G3 full-native candidate accounting without any warehouse mutations.

Reconciles TDCC true native 16-row/17-row candidate states against the
Unified Master source-ID count. Prints aggregate only, no sensitive raw values.
"""
import collections,json,os,sys
from scripts.v097_v3_preflight import source_api,read_baseline,assert_cohort
from scripts.v097_g2g3_typed_contract_audit import CHECKPOINT
from scripts.v097_g2g3_native_headers import HEADER_PREFIX
def check():
    api,control,quality,match,load_json,put_once,upsert,call=source_api()
    summaries={}
    for src in ("TDCC","TWSE","TPEx","MOPS","TAIFEX","NDC","FinMind"):
        raw=read_baseline(api,quality,match,load_json,src)
        assert_cohort(raw,src)
        idx={r["source_id"]:r for r in raw}
        f=match(api,control,CHECKPOINT+src+".json")
        ck=load_json(api,f["id"]) if f else {"done":{}}
        done=ck.get("done",{})
        if set(done)-set(idx):raise RuntimeError("TYPED_ORPHAN_"+src)
        status=collections.Counter()
        badsha=0
        n=0
        for sid,x in done.items():
            if x.get("sha")!=idx[sid]["source_sha256"]:badsha+=1;continue
            n+=1
            for member in x.get("members",[]):
                obj=member.get("full_native_shape",{})
                status[obj.get("status","NONE")]+=1
        summaries[src]={"typed_record_count":n,"bad_sha":badsha,
          "full_native_member_status":dict(status),
          "candidate_total":sum(status[k] for k in ("TDCC_FULL_NATIVE_LAYOUT_CANDIDATE_UNCERTIFIED",
                      "FULL_NATIVE_SHAPE_CANDIDATE_UNCERTIFIED"))}
    f=match(api,control,"v097_V3_UNIFIED_MASTER_LATEST.json")
    master=load_json(api,f["id"]) if f else {}
    result={"source_summaries":summaries,"current_master_run":master.get("run"),
       "master_native_candidates":master.get("overall",{}).get("g3_full_native_shape_candidate_members"),
       "live_candidates":sum(s["candidate_total"] for s in summaries.values())}
    print("G2G3_G3_RECONCILE_DIAG="+json.dumps(result,ensure_ascii=False,sort_keys=True),flush=True)
    if result["live_candidates"] and result["master_native_candidates"]==0:
        print("G3_MASTER_STALE_OR_MISMAPPED",flush=True)
if __name__=="__main__":check()
