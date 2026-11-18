#!/usr/bin/env python3
"""JARVIS v0.97: seven-source incremental native template verification.
R3 325 QA records are referenced, never silently promoted into the G0-G5 Master.
Source Bronze bytes and existing R1 certificates remain untouched.
"""
import collections,datetime,hashlib,json,os,sys
from scripts.v097_v3_preflight import read_baseline,assert_cohort,source_api,canonical
from scripts.v097_seven_source_format_smoke import SOURCES, audit
from scripts.v097_two_source_pilot_g2 import ordered
from scripts.v097_v3_contract_registry import REGISTRY_VERSION

VERSION="v097_seven_source_native_incremental_v1"
RUN=os.getenv("GITHUB_RUN_ID","manual")
SAMPLE=min(12,max(1,int(os.getenv("SEVEN_INC_SAMPLE","6"))))
BATCH=min(100,max(1,int(os.getenv("SEVEN_INC_BATCH","30"))))
CHECK_PREFIX="v097_SEVEN_NATIVE_INCREMENTAL_CK_"
R3_QA_REFERENCE={
 "run":"44285197374","master_id":"1zi603mMo-6GQQOrZxArvjdvzQfqYdfp8",
 "frozen_cohort":74750,"qa_source_vintage_verified":325,
 "g2_hold":74425,"not_production_master":True,
 "sources":{"TWSE":1,"TPEx":1,"MOPS":1,"TDCC":0,"TAIFEX":0,"NDC":320,"FinMind":2}
}
def read_index(api,control,match,load_json,prefix,source):
    f=match(api,control,prefix+source+".json")
    if not f:return {}
    data=load_json(api,f["id"])
    if not isinstance(data,dict) or not isinstance(data.get("done"),dict):
        raise RuntimeError("INVALID_PRIOR_CHECKPOINT_"+prefix+source)
    return data["done"]
def reusable(row,header,typed):
    sid=row["source_id"];expected=row["source_sha256"]
    t=typed.get(sid)
    if isinstance(t,dict) and t.get("sha")==expected and t.get("status")=="TYPED_EVIDENCE_RECORDED":
        return {"source_id":sid,"source":row["source"],"sha":expected,"path":row.get("source_path"),
                "status":"REUSED_TYPED_NATIVE_QA_UNCERTIFIED","raw_integrity":"PRIOR_SHA_MATCH",
                "format_candidate":False,"evidence_id":"v097_G2G3_TYPED_AUDIT_CK_",
                "g2_official_verified":False,"reused":True}
    h=header.get(sid)
    if isinstance(h,dict) and h.get("sha")==expected and h.get("status")=="NATIVE_HEADERS_EXTRACTED_UNCERTIFIED":
        return {"source_id":sid,"source":row["source"],"sha":expected,"path":row.get("source_path"),
                "status":"REUSED_HEADER_NATIVE_QA_UNCERTIFIED","raw_integrity":"PRIOR_SHA_MATCH",
                "format_candidate":False,"evidence_id":"v097_G2G3_HEADER_CK_",
                "g2_official_verified":False,"reused":True}
    return None
def run(source):
    if source not in SOURCES:raise ValueError("UNKNOWN_SOURCE")
    api,control,quality,match,load_json,put_once,upsert,call=source_api()
    rows=read_baseline(api,quality,match,load_json,source)
    assert_cohort(rows,source)
    idx={r["source_id"]:r for r in rows}
    headers=read_index(api,control,match,load_json,"v097_G2G3_HEADER_CK_",source)
    typed=read_index(api,control,match,load_json,"v097_G2G3_TYPED_AUDIT_CK_",source)
    if set(headers)-set(idx) or set(typed)-set(idx):
        raise RuntimeError("EXISTING_QA_EVIDENCE_ORPHAN_"+source)
    ckfile=CHECK_PREFIX+source+".json"
    f=match(api,control,ckfile)
    ck=load_json(api,f["id"]) if f else {"schema":VERSION,"source":source,"done":{}}
    if ck.get("schema")!=VERSION or ck.get("source")!=source:
        raise RuntimeError("INCREMENTAL_CHECKPOINT_CONFLICT_"+source)
    done=ck.get("done",{})
    if set(done)-set(idx):raise RuntimeError("INCREMENTAL_CHECKPOINT_ORPHAN_"+source)
    representatives,buckets=ordered(rows,source)
    samples=[];fresh={};sampled_ids=set()
    def evaluate(row):
        sid=row["source_id"]
        prior=done.get(sid)
        if prior and prior.get("sha")==row["source_sha256"] and prior.get("contract_registry")==REGISTRY_VERSION:
            return {**prior,"reused_checkpoint":True}
        native=reusable(row,headers,typed)
        if native:
            native["contract_registry"]=REGISTRY_VERSION
            return native
        current=audit(row,source,api,call)
        current["contract_registry"]=REGISTRY_VERSION
        current["reused"]=False
        return current
    # Six representative records prove the audit engine is reading real 0.97 sources.
    # NDC 320 source-vintage QA proofs are already separately recorded in R3; never re-certify.
    for row in representatives[:SAMPLE]:
        if source=="NDC":
            record={"source_id":row["source_id"],"source":"NDC",
                    "sha":row["source_sha256"],
                    "status":"R3_PREVIOUSLY_VERIFIED_SOURCE_VINTAGE_REUSED",
                    "r3_master_id":R3_QA_REFERENCE["master_id"],
                    "reused":True,"g2_official_verified":False}
        else:
            record=evaluate(row)
        samples.append(record);sampled_ids.add(row["source_id"])
        if source!="NDC" and not record.get("reused_checkpoint") and record["source_id"] not in done:
            fresh[record["source_id"]]=record
    # Reuse existing header/typed QA before reading any additional Bronze bytes.
    reused_existing=0
    for row in ([] if source=="NDC" else rows):
        sid=row["source_id"]
        if sid in done and done[sid].get("sha")==row["source_sha256"] and done[sid].get("contract_registry")==REGISTRY_VERSION:
            continue
        if sid in sampled_ids:continue
        native=reusable(row,headers,typed)
        if native:
            native["contract_registry"]=REGISTRY_VERSION
            fresh[sid]=native;reused_existing+=1
        if reused_existing>=BATCH:break
    # Bounded fresh raw readback: finish representative variants first,
    # then continue through every untouched member of the frozen source cohort.
    newly_read=0
    representative_ids={r["source_id"] for r in representatives}
    pending_order=representatives+[r for r in rows if r["source_id"] not in representative_ids]
    if source!="NDC":
        for row in pending_order:
            sid=row["source_id"]
            if sid in done and done[sid].get("sha")==row["source_sha256"] and done[sid].get("contract_registry")==REGISTRY_VERSION:continue
            if sid in fresh or sid in sampled_ids:continue
            if reusable(row,headers,typed):continue
            record=evaluate(row)
            fresh[sid]=record
            newly_read+=1
            if newly_read>=BATCH:break
    if fresh:
        delta_name="v097_SEVEN_NATIVE_INCREMENTAL_DELTA_"+source+"_"+RUN+".json"
        delta_id=put_once(api,quality,delta_name,{"schema":VERSION,"source":source,"run":RUN,
            "delta":fresh,"r3_reference":R3_QA_REFERENCE})
        done.update(fresh)
        ck.update({"done":done,"run":RUN,"delta_id":delta_id,"schema":VERSION,"source":source})
        upsert(api,control,ckfile,ck)
        witness=match(api,control,ckfile)
        if not witness or len(load_json(api,witness["id"]).get("done",{}))!=len(done):
            raise RuntimeError("INCREMENTAL_CHECKPOINT_READBACK_FAILED_"+source)
    known_qa=R3_QA_REFERENCE["sources"][source]
    counts=dict(collections.Counter(rec.get("status","UNKNOWN") for rec in samples))
    summary={"source":source,"run":RUN,"cohort":len(rows),"r3_qa_verified_not_reissued":known_qa,
      "sampled":len(samples),"sample_status_counts":counts,
      "sample_format_candidates":sum(1 for c in samples if c.get("format_candidate")),
      "newly_read_bronze":newly_read,
      "new_or_reused_incremental_records":len(fresh),"prior_checkpoints_reused":reused_existing,
      "checkpoint_total":len(done),"unaccounted_by_this_checkpoint":len(rows)-len(done),
      "era_format_buckets":len(buckets),"official_new_g2_pass":0,"silver_gold_materialized":0}
    rid=put_once(api,quality,"v097_SEVEN_NATIVE_INCREMENTAL_REPORT_"+source+"_"+RUN+".json",
      {"schema":VERSION,"source":source,"run":RUN,"summary":summary,"pilot":samples,
       "r3_immutable_provenance_reference":R3_QA_REFERENCE,
       "note":"R3 source-vintage QA is not production-G5; reused header/typed evidence is not official G2 PASS."})
    upsert(api,control,"v097_SEVEN_NATIVE_INCREMENTAL_"+source+"_LATEST.json",
      {"schema":VERSION,"source":source,"run":RUN,"report_id":rid,"summary":summary})
    print("SEVEN_NATIVE_INCREMENTAL="+canonical({**summary,"report_id":rid}),flush=True)
def selftest():
    assert set(SOURCES)==set(R3_QA_REFERENCE["sources"])
    assert sum(R3_QA_REFERENCE["sources"].values())==325
    assert R3_QA_REFERENCE["g2_hold"]+325==R3_QA_REFERENCE["frozen_cohort"]
    row={"source_id":"x","source":"TWSE","source_sha256":"a"*64}
    assert reusable(row,{},{"x":{"sha":"a"*64,"status":"TYPED_EVIDENCE_RECORDED"}})["reused"]
    assert reusable(row,{},{"x":{"sha":"b"*64,"status":"TYPED_EVIDENCE_RECORDED"}}) is None
    print("SEVEN_INCREMENTAL_REUSE_AND_R3_325_SEPARATION_SELFTEST_PASS")
if __name__=="__main__":
    if sys.argv[1:]==["selftest"]:selftest()
    elif len(sys.argv)==3 and sys.argv[1]=="source" and sys.argv[2] in SOURCES:run(sys.argv[2])
    else:raise SystemExit("usage: selftest | source SOURCE")
