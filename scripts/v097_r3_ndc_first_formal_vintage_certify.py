"""Issue first *real* R3 G2 for 2026-source-vintage NDC archived data.

Proof: live official ws.ndc.gov.tw XLSX sha equals archived Drive XLSX;
second independent runner compared all 10 frozen NDC JSON documents against
all 5 XLSX sheets, 337 values and 3 documented native blanks.
VINTAGE is first verified as of 2026-10-23 and MUST NEVER be used as
contemporaneous 2001-2025 PIT data in historical backtests.
"""
from __future__ import annotations
import hashlib,json,os
from datetime import date
from scripts.v097_bronze_autopilot import source_api
from scripts.v097_v3_preflight import read_baseline,assert_cohort
from scripts.v097_bronze_first_pipeline import put_once
from scripts.v097_r3_g2_shared_contract_engine import approved_template,file_decision,confirm_g2_readback,group_candidates
from scripts.v097_r3_g2_shared_74750_reconcile import verify_document_factory
from scripts.v097_r3_gate_core import digest
RUN=os.environ.get("GITHUB_RUN_ID","manual")
SOURCE_FIRST="44256183662"
SOURCE_NATIVE="44257047358"
SOURCE_LIVE="44257356412"
DOC_SHA="c035dc5bbd3fe91ca80a620fd84828a54e8c49885a1b3aa51db5e42857772c83"
TEMPLATE_ID="NDC_2026_CAPTURED_REVISED_XLSX_5SHEET_JSON_V1"
REVIEWER_ID="R3_TWO_INDEPENDENT_GITHUB_EVIDENCE_RUNS_NDC_V1"
ASOF="2026-10-23"
def read_verified(api,match,load,parent,name):
    f=match(api,parent,name)
    if not f:raise RuntimeError("EVIDENCE_RECEIPT_NOT_FOUND:"+name)
    doc=load(api,f["id"])
    return f,doc
def main():
    api,control,quality,match,load,_,_,call=source_api()
    folder=match(api,quality,"R3_G2_FIRST_REAL_CERT_PILOT_ISOLATED")
    if not folder:raise RuntimeError("PILOT_DRIVE_FOLDER_MISSING")
    folder=folder["id"]
    firstfile,first=read_verified(api,match,load,folder,
        "r3_g2_first_real_cert_discovery_run_"+SOURCE_FIRST+".json")
    crossfile,cross=read_verified(api,match,load,folder,
        "r3_ndc_xlsx_native_cell_crosscheck_run_"+SOURCE_NATIVE+".json")
    livefile,live=read_verified(api,match,load,folder,
        "r3_ndc_official_remote_source_run_"+SOURCE_LIVE+".json")
    ndc=next(s for s in first["sources"] if s["source"]=="NDC")
    assert len(ndc["records"])==10
    if (cross["crosscheck_totals"].get("mismatches")!=0 or
        cross["crosscheck_totals"].get("cells")!=337 or
        cross["crosscheck_totals"].get("documented_blank")!=3 or
        cross["sample_count"]!=10 or cross["published_archive_sha256"]!=DOC_SHA or
        live["official_remote_byte_match"] is not True or
        live["official_remote_sha256"]!=DOC_SHA):
        raise RuntimeError("INDEPENDENT_SOURCE_PROOF_NOT_CONVERGENT")
    official=ndc["records"][0]["source_archive"]
    if any(x["source_archive"]["sha256"]!=DOC_SHA or
           x["source_archive"]["file_id"]!=official["file_id"] for x in ndc["records"]):
        raise RuntimeError("MIXED_NDC_ORIGINAL_ARCHIVES")
    if date.fromisoformat(official["captured_utc"][:10])!=date.fromisoformat(ASOF):
        raise RuntimeError("SOURCE_SNAPSHOT_ASOF_NOT_STABLE")
    rows=read_baseline(api,quality,match,load,"NDC");assert_cohort(rows,"NDC")
    byid={r["source_id"]:r for r in rows}
    reviewed={r["source_id"]:r for r in cross["records"]}
    if set(reviewed)!={r["source_id"] for r in ndc["records"]}:raise RuntimeError("REVIEW_SAMPLE_ID_MISMATCH")
    for record in ndc["records"]:
        original=byid[record["source_id"]]
        review=reviewed[record["source_id"]]
        if (record["source_sha256"]!=original["source_sha256"] or
            review["source_sha256"]!=original["source_sha256"] or
            review["mismatch_count"]!=0):
            raise RuntimeError("PER_FILE_SOURCE_OR_NATIVE_CHECK_FAILED")
    raw=call(lambda:api.files().get_media(fileId=official["file_id"]))
    if hashlib.sha256(raw).hexdigest()!=DOC_SHA:raise RuntimeError("REAL_ORIGINAL_DOC_CHANGED")
    original_url=official["url"]
    if not original_url.startswith("https://ws.ndc.gov.tw/Download.ashx?"):
        raise RuntimeError("OFFICIAL_HOST_MISMATCH")
    if cross.get("official_dataset_edition_pit_certified") is not False:
        raise RuntimeError("HISTORIC_PIT_REVIEW_NOT_RECORDED")
    # Independent machine review binds different runs: one value-level native
    # extraction review; one official-host live byte source check.
    reviewdoc={"schema":"R3_G2_INDEPENDENT_MACHINE_VINTAGE_REVIEW_V1",
        "approval_status":"APPROVED","reviewer_id":REVIEWER_ID,
        "template_id":TEMPLATE_ID,"official_document_sha256":DOC_SHA,
        "source":"NDC","reviewed_official_url":original_url,
        "source_snapshot_first_verified_asof":ASOF,
        "source_archive_drive_id":official["file_id"],
        "separately_observed_runs":[SOURCE_NATIVE,SOURCE_LIVE],
        "native_crosscheck_report_id":crossfile["id"],
        "official_origin_recheck_report_id":livefile["id"],
        "source_snapshot_historical_revisions":True,
        "contemporaneous_historical_pit_verified":False,
        "backtest_eligible_before_asof":False,
        "verified_original_cell_values":337,
        "verified_original_blanks":3,
        "certified_scope":"NDC_2026_REVISED_XLSX_SNAPSHOT_FORMAT_AND_DERIVED_JSON_NATIVE_ONLY",
        "not_certified_scope":"HISTORICAL_AS_OF_2001_2025_REVISIONS"}
    review_name="r3_ndc_vintage_machine_independent_review_"+SOURCE_NATIVE+"_"+SOURCE_LIVE+".json"
    reviewid=put_once(api,folder,review_name,reviewdoc)
    if load(api,reviewid)!=reviewdoc:raise RuntimeError("REVIEW_READBACK_MISMATCH")
    reviewsha=hashlib.sha256(call(lambda:api.files().get_media(fileId=reviewid))).hexdigest()
    candidate_key=("NDC","BUSINESS_SIGNAL","NDC_SIGNAL_2024")
    template=group_candidates()[candidate_key]
    approved={
     "source":"NDC","dataset":"BUSINESS_SIGNAL","historical_era":"NDC_SIGNAL_2024",
     "template_id":TEMPLATE_ID,"contract_version":"R3_NDC_VINTAGE_V1",
     "native_format":"JSON","native_layout_id":"NDC_XLSX_5_SHEETS_DERIVED_JSON",
     "era_basis":"source_publication_vintage",
     "dataset_start_date_mode":"FIRST_VERIFIED_ARCHIVED_SNAPSHOT_NOT_DATASET_INCEPTION",
     "official_dataset_start_date":ASOF,"effective_start_day":ASOF,
     "effective_end_day":ASOF,
     "required_fields":["source","month","source_archive","tables"],
     "optional_fields":["gaps","representation","units","coverage_certified","pit_verified","numeric_verified"],
     "approved_aliases":{},"primary_key":["source","month"],
     "official_reference":original_url,
     "official_document_drive_id":official["file_id"],
     "official_document_sha256":DOC_SHA,
     "official_document_origin_verified":True,
     "independent_reviewer_id":REVIEWER_ID,
     "independent_review_record_id":reviewid,
     "independent_review_sha256":reviewsha,
     "publication_asof_verified":True,
     "backtest_eligible_before_2026_10_23":False,
     "approval_status":"APPROVED"}
    checker=verify_document_factory(api,call,load)
    arr,reason=approved_template(
        {"schema":"R3_G2_APPROVED_SHARED_TEMPLATES_V1","templates":[approved]},
        template,checker)
    if not arr or len(arr)!=1:raise RuntimeError("TEMPLATE_APPROVAL_REMOTE_RECHECK_FAILED:"+reason)
    bind={}
    for ref in ndc["records"]:
        rawrow=byid[ref["source_id"]]
        obs=ref["month"]
        b={"source_id":rawrow["source_id"],"source":"NDC",
          "source_sha256":rawrow["source_sha256"],
          "source_document_sha256":rawrow["source_sha256"],
          "source_path":rawrow["source_path"],
          "dataset":"BUSINESS_SIGNAL","historical_era":"NDC_SIGNAL_2024",
          "native_format":"JSON","native_layout_id":"NDC_XLSX_5_SHEETS_DERIVED_JSON",
          "source_data_date":obs+"-01","source_data_date_verified":True,
          "native_date_evidence_sha256":DOC_SHA,
          "publication_asof_verified":True,"native_layout_verified":True,
          "dataset_origin_verified":True,
          "independent_evidence_id":crossfile["id"],
          "binding_version":"R3_NDC_VINTAGE_V1",
          "source_publication_asof":ASOF,
          "source_publication_asof_verified":True,
          "historical_backtest_eligible_before_source_publication":False,
          "native_review_source_id":crossfile["id"]}
        decision=file_decision(rawrow,arr,b)
        if decision["status"]!="CANDIDATE":
            raise RuntimeError("G2_FILE_NATIVE_BINDING_NOT_CERTIFIABLE:"+decision.get("reason",""))
        bind[rawrow["source_id"]]=b
    # Use canonical R3-only immutable registry names in existing Drive control
    # folder; never modify old R1/V3 writers or their Master.
    reg={"schema":"R3_G2_APPROVED_SHARED_TEMPLATES_V1",
         "certified_scope":"CONSERVATIVE_ASOF_2026_REVISED_NDC_SOURCE_VINTAGE",
         "templates":[approved]}
    bindreg={"schema":"R3_G2_NATIVE_BINDINGS_V1","source":"NDC",
             "certified_scope":"CONSERVATIVE_ASOF_2026_REVISED_NDC_SOURCE_VINTAGE",
             "done":bind}
    names=[("R3_G2_APPROVED_SHARED_TEMPLATES_V1.json",reg),
           ("R3_G2_NATIVE_BINDINGS_NDC.json",bindreg)]
    persisted={}
    for name,obj in names:
        rid=put_once(api,control,name,obj)
        if load(api,rid)!=obj:raise RuntimeError("APPROVED_REGISTRY_NOT_DURABLE:"+name)
        persisted[name]=rid
    # Commit the exact ten G2 file certificates using the existing engine's
    # canonical per-file immutable IDs, with independent remote readback.
    qa=match(api,quality,"R3_G2_COMMON_TEMPLATE_RECONCILE_ISOLATED")
    if not qa:raise RuntimeError("R3_G2_COMMON_QA_FOLDER_MISSING")
    passed=0
    for sid,b in bind.items():
        row=byid[sid]
        v=file_decision(row,arr,b)
        name="g2_cert_"+digest(["NDC",sid,row["source_sha256"]])+".json"
        fileid=put_once(api,qa["id"],name,v["certificate"])
        after=load(api,fileid)
        if confirm_g2_readback(v,after)["status"]!="PASS":
            raise RuntimeError("PER_FILE_G2_DURABLE_CERT_READBACK_FAILED")
        passed+=1
    print("R3_NDC_VINTAGE_FIRST_FORMAL_PASS="+json.dumps({
        "run":RUN,"template_id":TEMPLATE_ID,
        "approved_shared_native_templates":1,"g2_certificates_issued":passed,
        "asof_first_verified":ASOF,
        "historic_contemporaneous_pit_verified":False,
        "backtest_eligible_before_asof":False,
        "registry_files":persisted,
        "certificate_drive_folder":qa["id"],
        "review_file_id":reviewid,
        "all_certificates_readback":True,
        "source_original_live_sha_verified":True
       },ensure_ascii=False,sort_keys=True),flush=True)
if __name__=="__main__":main()
