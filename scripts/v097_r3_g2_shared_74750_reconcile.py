"""Run 74,750-row G2 shared template reconciliation on real frozen Drive manifest.

Only validated templates plus independent per-file native binding may yield a
certificate; a candidate becomes PASS ONLY after immutable Drive readback.
All other records receive a detailed, separate HOLD reason and remain reusable.
No old R1/V3 Master updates; no Bronze/Silver/Gold mutations.
"""
from __future__ import annotations
from collections import Counter
from datetime import datetime, timezone
import hashlib, json, os, re, sys
from urllib.parse import urlparse
from scripts.v097_bronze_autopilot import source_api
from scripts.v097_v3_preflight import read_baseline,assert_cohort
from scripts.v097_r3_gate_core import SOURCES,COHORT,digest
from scripts.v097_r3_g2_shared_contract_engine import (
  group_candidates, approved_template, file_decision, confirm_g2_readback, date_census)
from scripts.v097_bronze_first_pipeline import put_once

VERSION="R3_G2_74750_SHARED_TEMPLATE_RECONCILE_V1"
QA_FOLDER="R3_G2_COMMON_TEMPLATE_RECONCILE_ISOLATED"
APPROVAL_FILE="R3_G2_APPROVED_SHARED_TEMPLATES_V1.json"
BINDING_PREFIX="R3_G2_NATIVE_BINDINGS_"
HOSTS={"TWSE":["twse.com.tw"],"TPEx":["tpex.org.tw"],
 "MOPS":["twse.com.tw"],"TDCC":["tdcc.com.tw"],
 "TAIFEX":["taifex.com.tw"],"NDC":["ndc.gov.tw"],
 "FinMind":["finmind.github.io","github.com"]}

def safe_origin(reference,source):
    u=urlparse(reference)
    host=(u.hostname or "").lower()
    return u.scheme=="https" and any(host==v or host.endswith("."+v) for v in HOSTS[source])

def verify_document_factory(api,call,load_json):
    cache={}
    def check(t):
        doc=t["official_document_drive_id"]
        review=t["independent_review_record_id"]
        if not safe_origin(t["official_reference"],t["source"]):return False
        tag=(doc,t["official_document_sha256"],review,t["independent_review_sha256"])
        if tag in cache:return cache[tag]
        try:
            md=call(lambda:api.files().get(fileId=doc,fields="id,size,mimeType"))
            mr=call(lambda:api.files().get(fileId=review,fields="id,size,mimeType"))
            if not all(x and 0<int(x.get("size") or 0)<=20*1024*1024 for x in (md,mr)):
                cache[tag]=False;return False
            raw=call(lambda:api.files().get_media(fileId=doc))
            audit=call(lambda:api.files().get_media(fileId=review))
            if hashlib.sha256(raw).hexdigest()!=t["official_document_sha256"].lower():
                cache[tag]=False;return False
            if hashlib.sha256(audit).hexdigest()!=t["independent_review_sha256"].lower():
                cache[tag]=False;return False
            reviewer=json.loads(audit.decode("utf-8-sig"))
            if not isinstance(reviewer,dict) or reviewer.get("approval_status")!="APPROVED":
                cache[tag]=False;return False
            if reviewer.get("reviewer_id")!=t["independent_reviewer_id"]:
                cache[tag]=False;return False
            if reviewer.get("template_id")!=t["template_id"]:
                cache[tag]=False;return False
            if reviewer.get("official_document_sha256")!=t["official_document_sha256"]:
                cache[tag]=False;return False
            cache[tag]=True
        except Exception:
            cache[tag]=False
        return cache[tag]
    return check

def main():
    api,control,quality,match,load_json,put_once_fn,_,call=source_api()
    templates=group_candidates()
    src_approval=match(api,control,APPROVAL_FILE)
    registry=load_json(api,src_approval["id"]) if src_approval else None
    if registry and (not isinstance(registry,dict) or not isinstance(registry.get("templates"),list)):
        raise RuntimeError("INVALID_OFFICIAL_SHARED_REGISTRY")
    approved={}
    audit=Counter()
    checker=verify_document_factory(api,call,load_json)
    for k,t in templates.items():
        arr,reason=approved_template(registry,t,checker)
        if arr:
            approved[k]=arr
        audit["template:"+reason]+=1
    if registry:
        seen=set(templates)
        for v in registry["templates"]:
            k=(v.get("source"),v.get("dataset"),v.get("historical_era"))
            if k not in seen:raise RuntimeError("UNEXPECTED_APPROVED_TEMPLATE_GROUP")
        if len(registry["templates"])!=len(set(x.get("template_id") for x in registry["templates"])):
            raise RuntimeError("DUPLICATE_APPROVAL_TEMPLATE_ID")
    folder=match(api,quality,QA_FOLDER)
    if folder is None:
        folder=call(lambda:api.files().create(body={"name":QA_FOLDER,
               "parents":[quality],"mimeType":"application/vnd.google-apps.folder"},fields="id,mimeType"))
    if folder.get("mimeType")!="application/vnd.google-apps.folder":raise RuntimeError("BAD_QA_FOLDER")
    fid=folder["id"];run=os.getenv("GITHUB_RUN_ID","manual")
    allcounts=Counter();source_summary=[];n=0
    # Only independently attested per-file native registry entries can yield
    # precise binding. No inferred dataset from filename or era is accepted.
    for src in SOURCES:
        rows=read_baseline(api,quality,match,load_json,src)
        assert_cohort(rows,src)
        n+=len(rows)
        # V2 NDC is additive, immutable and preserves the original first-ten cert proofs.
        bfile=(match(api,control,BINDING_PREFIX+src+"_V3.json") if src=="NDC" else None)
        if not bfile and src=="NDC":bfile=match(api,control,BINDING_PREFIX+src+"_V2.json")
        if not bfile:bfile=match(api,control,BINDING_PREFIX+src+".json")
        bdata=load_json(api,bfile["id"]) if bfile else {}
        if bdata and (not isinstance(bdata,dict)
                      or bdata.get("schema")!="R3_G2_NATIVE_BINDINGS_V1"
                      or not isinstance(bdata.get("done"),dict)):
            raise RuntimeError("INVALID_NATIVE_BINDING_REGISTRY_"+src)
        binds=bdata.get("done",{})
        if set(binds)-set(r["source_id"] for r in rows):
            raise RuntimeError("NATIVE_BINDING_ORPHAN_"+src)
        state=Counter();records=[];certified=0
        source_review_cache={}
        for row in rows:
            native=binds.get(row["source_id"])
            if isinstance(native,dict):
                key=(src,native.get("dataset"),native.get("historical_era"))
                candidates=approved.get(key,[])
                decision=file_decision(row,candidates,native)
            else:
                decision={"status":"HOLD","reason":"G2_NATIVE_BINDING_MISSING" if approved else "G2_SHARED_TEMPLATE_NOT_YET_APPROVED"}
            if decision["status"]=="CANDIDATE":
                # Cross-check each approved source-vintage file against an
                # independently committed proof, not merely binding flags.
                if any(t.get("era_basis")=="source_publication_vintage" for t in candidates):
                    eid=native.get("independent_evidence_id")
                    if eid not in source_review_cache:
                        source_review_cache[eid]=load_json(api,eid) if eid else None
                    review=source_review_cache[eid]
                    matched=([x for x in review.get("records",[]) if
                              x.get("source_id")==row["source_id"] and
                              x.get("source_sha256")==row["source_sha256"]]
                             if isinstance(review,dict) else [])
                    if (len(matched)!=1 or matched[0].get("mismatch_count")!=0 or
                        matched[0].get("source_month")+"-01"!=native.get("source_data_date") or
                        matched[0].get("archive_sha256")!=native.get("native_date_evidence_sha256") or
                        review.get("published_archive_sha256")!=native.get("native_date_evidence_sha256") or
                        native.get("historical_backtest_eligible_before_source_publication") is not False):
                        decision={"status":"HOLD","reason":"G2_INDEPENDENT_VINTAGE_NATIVE_REVIEW_MISSING_OR_CONFLICT"}
            if decision["status"]=="CANDIDATE":
                # A certificate is immutable, individually uploaded and independently
                # fetched before it can be counted as PASS.
                cert_name="g2_cert_"+digest([src,row["source_id"],row["source_sha256"]])+".json"
                cert_id=put_once_fn(api,fid,cert_name,decision["certificate"])
                read=load_json(api,cert_id)
                verdict=confirm_g2_readback(decision,read)
                if verdict["status"]=="PASS":certified+=1
                decision=verdict
            state[decision["status"]]+=1;state["reason:"+decision.get("reason","NONE")]+=1
            allcounts[decision["status"]]+=1;allcounts["reason:"+decision.get("reason","NONE")]+=1
            records.append({"source_id":row["source_id"],"source_sha256":row["source_sha256"],
                            "status":decision["status"],"reason":decision.get("reason","G2_REMOTE_CERT_VERIFIED" if decision["status"]=="PASS" else "UNKNOWN"),
                            "certificate_sha256":decision.get("certificate_sha256"),
                            "dataset":native.get("dataset") if isinstance(native,dict) else None,
                            "era":native.get("historical_era") if isinstance(native,dict) else None})
        out={"schema":"R3_G2_FILE_AUDIT_SHARD_V1","run":run,"source":src,
             "cohort":len(rows),"counts":dict(state),"records":records}
        filename="r3_g2_full_source_"+src+"_run_"+run+".json"
        fileid=put_once_fn(api,fid,filename,out)
        if load_json(api,fileid)!=out:raise RuntimeError("SOURCE_G2_READBACK_MISMATCH_"+src)
        part={"source":src,"cohort":len(rows),"counts":dict(state),
              "certified":certified,"readback":True,"receipt":filename,
              "receipt_id":fileid,"bronze_coverage":date_census(rows),
              "binding_registry_entries":len(binds)}
        source_summary.append(part)
        print("R3_G2_SHARED_SOURCE="+json.dumps({k:v for k,v in part.items() if k!="receipt_id"},ensure_ascii=False,sort_keys=True),flush=True)
    if n!=COHORT or sum(x["cohort"] for x in source_summary)!=COHORT:
        raise RuntimeError("FROZEN_COHORT_74750_CHANGED")
    result={"schema":VERSION,"run":run,"cohort":COHORT,
            "created_at":datetime.now(timezone.utc).isoformat(),
            "source_template_era_candidates":len(templates),
            "distinct_approved_template_era_groups":len(approved),
            "approved_native_editions":sum(map(len,approved.values())),
            "approval_registry_found":src_approval is not None,
            "source_counts":source_summary,"counts":dict(allcounts),
            "template_reviews":dict(audit),
            "g2_formal_per_file_pass":allcounts["PASS"],
            "g2_hold":allcounts["HOLD"],
            "all_sources_readback_verified":True,
            "bronze_modified":False,"silver_materialized":False,"gold_materialized":False,
            "source_earliest_observed_is_not_official_start":True}
    mname="r3_g2_shared_master_run_"+run+".json"
    mid=put_once_fn(api,fid,mname,result)
    if load_json(api,mid)!=result:raise RuntimeError("G2_MASTER_READBACK_MISMATCH")
    print("R3_G2_SHARED_MASTER="+json.dumps({
      "run":run,"cohort":COHORT,"candidate_groups":len(templates),
      "approved_groups":len(approved),"approved_editions":sum(map(len,approved.values())),
      "pass":allcounts["PASS"],"hold":allcounts["HOLD"],
      "template_review":dict(audit),
      "master_name":mname,"master_id":mid,"readback_verified":True,
      "source_summary":[{"source":x["source"],"cohort":x["cohort"],
         "pass":x["counts"].get("PASS",0),"hold":x["counts"].get("HOLD",0),
         "bronze_earliest_observed_date":x["bronze_coverage"]["bronze_earliest_observed_date"]}
         for x in source_summary]
    },sort_keys=True,ensure_ascii=False),flush=True)

if __name__=="__main__":
    if sys.argv[1:]!=["run"]:raise SystemExit("usage: run")
    main()
