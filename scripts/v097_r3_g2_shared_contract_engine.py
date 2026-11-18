"""R3 G2 shared-format contracts and bounded file-specific certification.

This is the actual binding engine. It will NOT turn candidate format profiles
into approved documentary evidence. A complete approved template and a
separately attested per-file native binding are both mandatory for G2 PASS.
"""
from __future__ import annotations
from collections import Counter
from datetime import date
import hashlib
import json
import re
from scripts.v097_g2g3_formal_contracts_v2 import catalog
from scripts.v097_r3_gate_core import digest

HEX=re.compile(r"^[0-9a-fA-F]{64}$")
REQUIRED_BINDING=("source_id","source","source_sha256","dataset","historical_era",
 "native_format","native_layout_id","source_document_sha256","source_path",
 "source_data_date","source_data_date_verified","native_date_evidence_sha256",
 "publication_asof_verified","native_layout_verified",
 "dataset_origin_verified","independent_evidence_id","binding_version")
def real_day(s):
    if not isinstance(s,str):return None
    try:return date.fromisoformat(s[:10])
    except ValueError:return None

def group_candidates():
    cs=catalog()
    if len(cs)!=143:raise ValueError("CANDIDATE_143_DRIFT")
    groups={}
    for x in cs:
        key=(x["source"],x["dataset"],x["historical_era"])
        if key in groups:raise ValueError("CANDIDATE_DUPLICATE")
        groups[key]=x
    return groups

def approved_template(registry, template, verify_document):
    """Exact source/era/edition document and independent review, no shortcuts."""
    if not isinstance(registry,dict):return None,"NO_APPROVED_REGISTRY"
    if registry.get("schema")!="R3_G2_APPROVED_SHARED_TEMPLATES_V1":
        return None,"APPROVAL_REGISTRY_SCHEMA_MISMATCH"
    candidate=(template["source"],template["dataset"],template["historical_era"])
    found=[r for r in registry.get("templates",[]) if isinstance(r,dict)
           and (r.get("source"),r.get("dataset"),r.get("historical_era"))==candidate]
    if len(found)>1:
        # More than one edition in a broad era is allowed; edition id must
        # uniquely identify distinct documents and non-overlapping active window.
        ids=[r.get("template_id") for r in found]
        if len(set(ids))!=len(ids):return None,"DUPLICATE_TEMPLATE_ID"
    approved=[]
    for r in found:
        mandatory=("template_id","contract_version","native_format","native_layout_id",
                   "official_dataset_start_date","effective_start_day",
                   "effective_end_day","required_fields","optional_fields",
                   "approved_aliases","primary_key","official_reference",
                   "official_document_drive_id","official_document_sha256",
                   "official_document_origin_verified","independent_reviewer_id",
                   "independent_review_record_id","independent_review_sha256",
                   "publication_asof_verified","approval_status")
        if any(k not in r for k in mandatory):return None,"TEMPLATE_INCOMPLETE"
        if r["approval_status"]!="APPROVED":continue
        if r["official_document_origin_verified"] is not True or r["publication_asof_verified"] is not True:
            return None,"NO_INDEPENDENT_OFFICIAL_ATTESTATION"
        if not all(isinstance(r[k],str) and r[k] for k in ("template_id","contract_version",
                     "native_format","native_layout_id","official_reference",
                     "official_document_drive_id","independent_reviewer_id","independent_review_record_id")):
            return None,"TEMPLATE_IDENTITY_INCOMPLETE"
        if not HEX.fullmatch(str(r["official_document_sha256"])) or not HEX.fullmatch(str(r["independent_review_sha256"])):
            return None,"PROOF_HASH_MISSING"
        start=real_day(r["effective_start_day"]);end=real_day(r["effective_end_day"])
        born=real_day(r["official_dataset_start_date"])
        if not (start and end and born and born<=start<=end):return None,"BAD_DATASET_OR_EDITION_DATES"
        if (not isinstance(r["required_fields"],list) or not r["required_fields"]
            or len(set(r["required_fields"]))!=len(r["required_fields"])):
            return None,"REQUIRED_FIELDS_INVALID"
        if not isinstance(r["optional_fields"],list) or not isinstance(r["approved_aliases"],dict):
            return None,"OPTIONAL_OR_ALIAS_INVALID"
        if not isinstance(r["primary_key"],list) or not r["primary_key"]:
            return None,"PRIMARY_KEY_MISSING"
        if not set(r["primary_key"]).issubset(set(r["required_fields"])):
            return None,"PRIMARY_KEY_NOT_REQUIRED_FIELD"
        if verify_document(r) is not True:return None,"OFFICIAL_DOCUMENT_REMOTE_PROOF_FAILED"
        approved.append(r)
    return approved,"APPROVED" if approved else "NO_APPROVED_TEMPLATE"

def file_decision(row,approved_templates,native_binding):
    """No native evidence means HOLD even when period or header looks similar."""
    if not approved_templates:return {"status":"HOLD","reason":"G2_NO_APPROVED_SHARED_TEMPLATE"}
    if not isinstance(native_binding,dict):
        return {"status":"HOLD","reason":"G2_NATIVE_DATASET_BINDING_MISSING"}
    if any(k not in native_binding for k in REQUIRED_BINDING):
        return {"status":"HOLD","reason":"G2_NATIVE_BINDING_EVIDENCE_INCOMPLETE"}
    if (native_binding["source_id"]!=row["source_id"] or
        native_binding["source"]!=row["source"] or
        native_binding["source_sha256"]!=row["source_sha256"] or
        native_binding["source_document_sha256"]!=row["source_sha256"]):
        return {"status":"HOLD","reason":"G2_FROZEN_ID_OR_SHA_MISMATCH"}
    if native_binding["publication_asof_verified"] is not True or native_binding["native_layout_verified"] is not True or native_binding["dataset_origin_verified"] is not True:
        return {"status":"HOLD","reason":"G2_NATIVE_PROVENANCE_UNATTESTED"}
    if not native_binding["independent_evidence_id"]:
        return {"status":"HOLD","reason":"G2_NATIVE_EVIDENCE_ID_MISSING"}
    if native_binding["source_data_date_verified"] is not True:
        return {"status":"HOLD","reason":"G2_NATIVE_DATA_DATE_NOT_ATTESTED"}
    if not isinstance(native_binding["native_date_evidence_sha256"],str) or not HEX.fullmatch(native_binding["native_date_evidence_sha256"]):
        return {"status":"HOLD","reason":"G2_NATIVE_DATE_EVIDENCE_SHA_MISSING"}
    day=real_day(native_binding["source_data_date"])
    if not day:return {"status":"HOLD","reason":"G2_FILE_DATE_UNVERIFIED"}
    baseline_date=row.get("data_date") or row.get("date")
    if baseline_date and real_day(baseline_date)!=day:
        return {"status":"HOLD","reason":"G2_DATE_CONFLICT_WITH_BASELINE"}
    matched=[t for t in approved_templates if
             native_binding["dataset"]==t["dataset"] and
             native_binding["historical_era"]==t["historical_era"] and
             native_binding["native_format"]==t["native_format"] and
             native_binding["native_layout_id"]==t["native_layout_id"] and
             real_day(t["official_dataset_start_date"])<=day and
             real_day(t["effective_start_day"])<=day<=real_day(t["effective_end_day"])]
    if len(matched)!=1:
        return {"status":"HOLD","reason":"G2_NO_UNIQUE_NATIVE_EDITION" if not matched else "G2_OVERLAPPING_APPROVED_EDITION"}
    t=matched[0]
    proof={"schema":"R3_G2_PER_FILE_CERT_V1","source":row["source"],"source_id":row["source_id"],
           "content_sha256":row["source_sha256"],"dataset":t["dataset"],
           "native_layout_id":t["native_layout_id"],"template_id":t["template_id"],
           "contract_version":t["contract_version"],"official_spec_sha256":t["official_document_sha256"],
           "official_review_sha256":t["independent_review_sha256"],
           "file_binding_sha256":digest(native_binding),
           "publication_asof_verified":True,"status":"G2_PASS_CANDIDATE_NOT_COMMITTED"}
    return {"status":"CANDIDATE","reason":"G2_COMMIT_AND_REMOTE_READBACK_REQUIRED",
            "certificate":proof,"certificate_sha256":digest(proof)}

def confirm_g2_readback(candidate,actual):
    if candidate.get("status")!="CANDIDATE" or candidate.get("certificate")!=actual:
        return {"status":"HOLD","reason":"G2_CERT_REMOTE_READBACK_MISMATCH"}
    if digest(actual)!=candidate.get("certificate_sha256"):
        return {"status":"HOLD","reason":"G2_CERT_REMOTE_SHA_MISMATCH"}
    return {"status":"PASS","certificate_sha256":candidate["certificate_sha256"]}

def date_census(rows):
    """Only infer OBSERVED Bronze coverage, NEVER the official start date."""
    mn=None;mx=None;no_date=0
    for r in rows:
        d=real_day(r.get("data_date") or r.get("date"))
        if d is None:no_date+=1
        else:
            mn=d if mn is None or d<mn else mn
            mx=d if mx is None or d>mx else mx
    return {"bronze_earliest_observed_date":mn.isoformat() if mn else None,
            "bronze_latest_observed_date":mx.isoformat() if mx else None,
            "undated":no_date,
            "official_dataset_start_date":"UNVERIFIED_FROM_BRONZE"}
