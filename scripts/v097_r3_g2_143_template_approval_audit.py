"""R3 G2 official template approval and file-binding audit.

Approvals are accepted ONLY from independently reviewed versioned registry,
after full official native document byte hash is checked in Google Drive.
No inference from candidate web link, file name, parser profile, or era bucket.
On absent official proof: emit complete 143-template and frozen-cohort HOLD
reports (not fake PASS). Stage-only QA reports are immutable and read back.
"""
from __future__ import annotations
import collections, datetime, hashlib, json, os, re, sys
from datetime import date
from scripts.v097_bronze_autopilot import source_api
from scripts.v097_v3_preflight import read_baseline,assert_cohort
from scripts.v097_g2g3_formal_contracts_v2 import catalog
from scripts.v097_r3_gate_core import SOURCES,COHORT,digest
from scripts.v097_bronze_first_pipeline import put_once

VERSION="R3_G2_TEMPLATE_CERTIFICATION_AUDIT_V1"
FOLDER="R3_G2_TEMPLATE_APPROVAL_ISOLATED"
APPROVAL_NAME="R3_G2_APPROVED_TEMPLATE_REGISTRY_V1.json"
REGEX_SHA=re.compile(r"^[0-9a-fA-F]{64}$")
HOSTS={"TWSE":("twse.com.tw",),"TPEx":("tpex.org.tw",),
       "MOPS":("twse.com.tw",),"TDCC":("tdcc.com.tw",),
       "TAIFEX":("taifex.com.tw",),"NDC":("ndc.gov.tw",),
       "FinMind":("finmind.github.io","github.com")}
def key(t):return (t["source"],t["dataset"],t["historical_era"])
def validate_candidate(template):
    missing=[]
    if template["field_spec_state"]!="CANDIDATE" or not template["required_fields"]:
        missing.append("G2_REQUIRED_FIELD_SPEC_MISSING")
    if not template["candidate_primary_key"]:
        missing.append("G2_SOURCE_PRIMARY_KEY_NOT_SPECIFIED")
    if template.get("era_is_dataset_verified") is not True:
        missing.append("G2_DATASET_ERA_OFFICIAL_PROOF_MISSING")
    if template["edition_window"]["start"][-2:] not in ("01",""):
        pass
    missing.append("G2_PRECISE_NATIVE_EDITION_AND_EFFECTIVE_DAY_NOT_ATTESTED")
    return missing

def candidate_report(templates):
    if len(templates)!=143 or len({key(x) for x in templates})!=143:
        raise RuntimeError("G2_143_CANDIDATE_COHORT_CHANGED")
    out=[];counts=collections.Counter()
    for t in templates:
        missing=validate_candidate(t)
        for m in missing:counts[m]+=1
        out.append({"source":t["source"],"dataset":t["dataset"],"era":t["historical_era"],
                    "start_month":t["edition_window"]["start"],
                    "end_month":t["edition_window"]["end"],
                    "native_variants":len(t["source_native_variants"]),
                    "required_field_count":len(t["required_fields"]),
                    "primary_key_count":len(t["candidate_primary_key"]),
                    "status":"HOLD_OFFICIAL_PROOF_PENDING","missing_evidence":missing})
    return out,counts

def verify_approval(api,call,approval,template):
    """Fail-closed; official evidence must be fetched and SHA checked."""
    if not isinstance(approval,dict):return "NO_INDEPENDENT_APPROVAL"
    required=("source","dataset","historical_era","template_id","contract_version",
              "effective_start_day","effective_end_day","native_format","required_fields",
              "approved_aliases","official_reference","official_document_drive_id",
              "official_document_sha256","official_document_origin_verified",
              "independent_reviewer_id","independent_review_record_id",
              "publication_asof_verified","approved_at","approval_status")
    if any(k not in approval for k in required):return "APPROVAL_FIELDS_MISSING"
    if any(approval[k]!=template[k] for k in ("source","dataset","historical_era")):
        return "CANDIDATE_KEY_MISMATCH"
    if approval["approval_status"]!="APPROVED" or approval["official_document_origin_verified"] is not True:
        return "OFFICIAL_ORIGIN_NOT_APPROVED"
    if approval["publication_asof_verified"] is not True:return "PUBLICATION_PIT_NOT_VERIFIED"
    if not isinstance(approval["required_fields"],list) or not approval["required_fields"]:
        return "APPROVED_REQUIRED_FIELDS_MISSING"
    if not isinstance(approval["approved_aliases"],dict):return "APPROVED_ALIAS_INVALID"
    if (not isinstance(approval["official_document_sha256"],str)
        or not REGEX_SHA.fullmatch(approval["official_document_sha256"])):
        return "OFFICIAL_SPEC_SHA_INVALID"
    try:
        lo=date.fromisoformat(approval["effective_start_day"])
        hi=date.fromisoformat(approval["effective_end_day"])
        date.fromisoformat(approval["approved_at"][:10])
        if lo>hi:return "OFFICIAL_EDITION_DATES_REVERSED"
        from urllib.parse import urlparse
        host=(urlparse(approval["official_reference"]).hostname or "").lower()
        if not any(host==d or host.endswith("."+d) for d in HOSTS[template["source"]]):
            return "UNTRUSTED_SOURCE_DOMAIN"
        docid=approval["official_document_drive_id"]
        meta=call(lambda:api.files().get(fileId=docid,fields="id,size,mimeType"))
        if not meta or int(meta.get("size") or 0)<=0:return "OFFICIAL_DOCUMENT_MISSING_OR_EMPTY"
        if int(meta["size"])>20*1024*1024:return "OFFICIAL_DOCUMENT_TOO_LARGE_FOR_REVIEW"
        raw=call(lambda:api.files().get_media(fileId=docid))
        if hashlib.sha256(raw).hexdigest()!=approval["official_document_sha256"].lower():
            return "OFFICIAL_DOCUMENT_SHA_MISMATCH"
        # Byte identity cannot by itself establish that the document is an
        # applicable official native specification; independent approval required.
    except Exception as e:
        return "OFFICIAL_DOCUMENT_EVIDENCE_READ_FAILED_"+type(e).__name__
    return "APPROVAL_EVIDENCE_VERIFIED"

def main():
    api,control,quality,match,load_json,put_once_fn,_,call=source_api()
    templates=catalog()
    candidates,missing=candidate_report(templates)
    # Live registry is the ONLY possible path to approval; source-wide
    # candidate catalog is explicitly excluded.
    official=match(api,control,APPROVAL_NAME)
    approved=load_json(api,official["id"]) if official else {"schema":VERSION,"approvals":[]}
    if not isinstance(approved,dict) or not isinstance(approved.get("approvals"),list):
        raise RuntimeError("APPROVAL_REGISTRY_INVALID")
    aidx={}
    for a in approved["approvals"]:
        k=key(a)
        if k in aidx:raise RuntimeError("DUPLICATE_APPROVED_TEMPLATE_KEY")
        aidx[k]=a
    if set(aidx)-{key(t) for t in templates}:
        raise RuntimeError("APPROVAL_REGISTRY_ORPHAN")
    checked=[];good={}
    for t in templates:
        approval=aidx.get(key(t))
        reason=verify_approval(api,call,approval,t)
        if reason=="APPROVAL_EVIDENCE_VERIFIED":
            good[key(t)]=approval
        checked.append({**candidates[len(checked)],
                        "official_approval_verdict":reason,
                        "approved":reason=="APPROVAL_EVIDENCE_VERIFIED"})
    # Seven-source official documentation/field-spec repair queue.
    source_gaps=[]
    for src in SOURCES:
        source_candidates=[v for v in checked if v["source"]==src]
        kinds=collections.Counter()
        for v in source_candidates:
            for reason in v["missing_evidence"]: kinds[reason]+=1
            if v["official_approval_verdict"]!="APPROVAL_EVIDENCE_VERIFIED":
                kinds["NO_VERIFIED_INDEPENDENT_APPROVAL"]+=1
        source_gaps.append({"source":src,"candidate_templates":len(source_candidates),
                            "verified_templates":sum(v["approved"] for v in source_candidates),
                            "unapproved":sum(not v["approved"] for v in source_candidates),
                            "missing_by_reason":dict(kinds)})
    # The frozen file cohort must be read exactly, but cannot be promoted
    # using era guess alone; dataset/native-format must also be proven.
    baseline=0
    source_rows=[]
    for src in SOURCES:
        rows=read_baseline(api,quality,match,load_json,src)
        assert_cohort(rows,src)
        baseline+=len(rows)
        source_rows.append({"source":src,"cohort":len(rows),
                            "official_template_approved":sum(1 for t in checked if t["source"]==src and t["approved"]),
                            "g2_per_file_issued":0,
                            "pending_file_dataset_native_binding":len(rows)})
    if baseline!=COHORT:raise RuntimeError("FROZEN_74750_DRIFT")
    result={"schema":VERSION,"run":os.getenv("GITHUB_RUN_ID","manual"),
            "created_at":datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "cohort":COHORT,"candidate_count":len(checked),
            "approved_template_count":len(good),
            "official_registry_entries":len(aidx),
            "per_file_g2_certificates_issued":0,
            "candidate_evidence_gaps":dict(missing),
            "source_template_repair_queue":source_gaps,
            "sources":source_rows,"candidates":checked,
            "release":"BLOCKED_UNTIL_OFFICIAL_TEMPLATE_AND_NATIVE_FILE_BINDING",
            "bronze_modified":False,"silver_materialized":False,
            "gold_materialized":False}
    folder=match(api,quality,FOLDER)
    if not folder:
        folder=call(lambda:api.files().create(body={"name":FOLDER,"parents":[quality],
                "mimeType":"application/vnd.google-apps.folder"},fields="id,mimeType"))
    if folder.get("mimeType")!="application/vnd.google-apps.folder":
        raise RuntimeError("NON_FOLDER_STAGING_PATH")
    name="r3_g2_143_template_review_run_"+result["run"]+".json"
    fid=put_once_fn(api,folder["id"],name,result)
    read=load_json(api,fid)
    if read!=result:raise RuntimeError("G2_TEMPLATE_AUDIT_DRIVE_READBACK_MISMATCH")
    print("R3_G2_143_TEMPLATE_AUDIT="+json.dumps({
        "run":result["run"],"cohort":COHORT,"candidate_count":143,
        "approved_template_count":len(good),"approval_registry_entries":len(aidx),
        "per_file_certificates_issued":0,"source_counts":source_rows,
        "evidence_gaps":dict(missing),"source_template_repair_queue":source_gaps,"drive_report":name,
        "readback_sha256":digest(read),"readback_verified":True,
        "release":result["release"]
    },ensure_ascii=False,sort_keys=True),flush=True)

if __name__=="__main__":
    if sys.argv[1:]!=["audit"]:raise SystemExit("usage: audit")
    main()
