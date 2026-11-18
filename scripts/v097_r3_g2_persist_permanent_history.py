"""JARVIS R3 persistent G2 seven-source QA history, rules and evidence catalog.

Immutable per-run snapshot under dedicated Google Drive QUALITY folder:
  - 7 independent source histories
  - documented shared-template SOP and failure taxonomy
  - full indexed source evidence from previous successful real runs
  - master with evidence ID, SHA, exact known run status and continuity plan

All existing original receipts are READ ONLY. Do not update G2/G5 official
production ledgers, change Bronze, or materialize Silver/Gold.
"""
from __future__ import annotations
import datetime
import hashlib
import json
import os
from scripts.v097_bronze_autopilot import source_api
from scripts.v097_bronze_first_pipeline import put_once
from scripts.v097_r3_gate_core import SOURCES, COHORT, digest

RUN=os.getenv("GITHUB_RUN_ID","manual")
FOLDER="R3_G2_SEVEN_SOURCE_TEMPLATE_PERMANENT_HISTORY"
SEVEN_SOURCE_FOLDER="R3_G2_SEVEN_SOURCE_PERIODIC_TEMPLATE_COMPARE_ISOLATED"
SIX_SAMPLE_FOLDER="R3_G2_SIX_SOURCE_REAL_SMALL_PILOT_ISOLATED"
SIX_OFFICIAL_FOLDER="R3_G2_SIX_SOURCE_OFFICIAL_DATASET_APPROVAL_ISOLATED"
SIX_ORIGIN_FOLDER="R3_G2_SIX_SOURCE_ORIGINAL_URL_PROVENANCE_ISOLATED"
G2_OVERLAY_FOLDER="R3_G2_SEVEN_SOURCE_OFFICIAL_QA_COMPOSITE_ISOLATED"
COUNTS={"TWSE":12071,"TPEx":13200,"MOPS":1935,"TDCC":40384,"TAIFEX":3140,"NDC":320,"FinMind":3700}
DATASETS={"TWSE":8,"TPEx":7,"MOPS":6,"TDCC":3,"TAIFEX":6,"NDC":5,"FinMind":4}
PERIODS={"TWSE":4,"TPEx":5,"MOPS":4,"TDCC":2,"TAIFEX":2,"NDC":6,"FinMind":1}
VERIFIED={"TWSE":1,"TPEx":1,"MOPS":0,"TDCC":0,"TAIFEX":0,"NDC":320,"FinMind":0}
SOURCE_HOLD={
 "TWSE":["Mixed source ZIP can contain multiple datasets","Historical MI_MARGN verified only for 2026 source-vintage snapshot; 2001 PIT unverified","API mismatch for other returned historical endpoints not proof Bronze corruption"],
 "TPEx":["2024-06-20 valuation snapshot verified; historical 2024 publication version unverified","Mixed ZIP report identities need native member-to-original mapping"],
 "MOPS":["MOPS financial report URL GET/POST/query payload, filing identity and IFRS taxonomy not bound one-to-one","Published timestamp and corrected/amended report PIT absent"],
 "TDCC":["Week-ending date and historic security identifier identity unverified","16-versus-17-tier original schema and original official source URL unproven"],
 "TAIFEX":["Futures spread orders, options and large traders are DISTINCT dataset templates","Daily/session boundary and native source URL not verified; one ZIP resource guard is not file corruption"],
 "NDC":["2026-10-23 revised government XLSX snapshot verified for all 320 JSON derived source files","Historical months within snapshot must not be treated as contemporary point-in-time published values","Literal original ellipsis means missing value, never zero"],
 "FinMind":["FinMind provider API dataset, params, source_version and publish PIT unverified","Provider API entrypoint alone cannot attest exact frozen JSON response bytes"]
}
RUN_HISTORY=[
 (44250976481,"Seven-source initial 74750 shared G2 candidate census, no approved templates"),
 (44251222513,"Frozen 7-source manifest lacks dataset and verified day, requiring independent per-file native evidence"),
 (44251486666,"74750 whole-cohort QA before first official source-native approval"),
 (44251892156,"70 actual frozen Bronze files (10/source) native candidate evidence and SHA verified"),
 (44256183662,"20 actual NDC/TAIFEX original provenance discovery"),
 (44257047358,"10 NDC JSON months checked cell-by-cell against government XLSX, 337 values and 3 blanks"),
 (44257356412,"Government NDC live original XLSX SHA re-fetch matches original archive"),
 (44258064219,"10 initial NDC source-vintage G2 per-file certificates"),
 (44258835703,"NDC all 320 source files native cells incremental audit; 309 more verified and one null-marker exception"),
 (44259887707,"2026-08 NDC eight literal official missing markers certified without zero imputation"),
 (44260700121,"NDC 320 per-file SHA cert shard + 74750 census and immutable remote readback"),
 (44261840978,"Six other sources x10 actual native files, 60 SHA-match, no new G2 cert"),
 (44263828295,"Seven nested source-level historical version libraries + 74750 candidate-date reconciliation"),
 (44266370461,"Six sources official references 60 original files, 14 document pages bytes+SHA"),
 (44266749919,"Six sources 60 frozen original ZIP manifests mined for exact provider/official API URL candidates"),
 (44267275612,"8 TWSE/TPEx official API original response SHA probes, 5 exact native member matches"),
 (44267841704,"TPEx 2024-06-20 valuation real official source-vintage G2 one-file certificate"),
 (44268565232,"TWSE 2001-03-02 margin MI_MARGN real official source-vintage G2 one-file certificate"),
 (44269047906,"322 G2 source-vintage QA overlay: NDC 320, TWSE 1, TPEx 1, all 74750 IDs reconciled"),
]
PROVENANCE={
 "template_compare_run":44263828295,
 "six_native_run":44261840978,
 "six_official_run":44266370461,
 "six_origin_run":44266749919,
 "overlay_run":44269047906,
 "ndc_cert_run":44260700121,
 "http_original_run":44267275612
}
RULES={
 "architecture":"Exactly seven shared SOURCE template libraries, each with Dataset -> native format -> historically applicable effective date window and version",
 "not_143_approved_templates":"143=7-source Dataset x source-era CANDIDATE combinations. Different dataset inception/edition dates may require split, merge or not applicable",
 "dates_separate":["official_dataset_begin_date","native_format_effective_start/end_day","archived_source_publication_asof","observation_data_date","bronze_earliest_observed_date"],
 "match_order":["source","dataset","native_original_type/member","verified source_data_date","approved effective day window","template_version","original official response SHA","independent review","frozen outer Bronze source_id/SHA"],
 "g2_gate":"Approved official native historical/or source-vintage evidence, required fields and aliases, native key, independent official document SHA/review ID, each file source_id+SHA and original publication vintage, immutable per-file certificate/readback",
 "g2_statuses":{
  "PASS":"Approved source- and edition-scoped template plus verified individual frozen source SHA and independent remote-readback certificate",
  "HOLD":"Missing/ambiguous original source or dataset/date/edition evidence, not presumed broken Bronze",
  "ERROR":"Confirmed file bytes/ZIP CRC/schema mismatch; isolate independently from upstream absence"
 },
 "PIT":"2026-revalidated historical observation values do not become historically published as-of the earlier observation year; block backtests preceding source_publication_asof",
 "zip_rule":"Validate outer ZIP SHA, member CRC, exact member-to-original-API mapping; different members/datasets require different native contracts",
 "error_rules":["G2_SHARED_TEMPLATE_NOT_YET_APPROVED","G2_NATIVE_BINDING_MISSING","G2_NO_UNIQUE_NATIVE_EDITION","G2_FROZEN_ID_OR_SHA_MISMATCH","G2_DATE_CONFLICT_WITH_BASELINE","G2_INDEPENDENT_VINTAGE_NATIVE_REVIEW_MISSING_OR_CONFLICT"],
 "reuse":"Keep unchanged previously approved source-vintage G2 certificate and source evidence SHA. Re-test only novel format, new source data or invalidated evidence",
 "no_false_pass":"Run SUCCESS, SHA 60/60, URL landing page availability, path YYYY-MM or candidate header are NOT G2 PASS",
 "scope":"Only G2. No Silver Ready/G3/G4 inference; Bronze read-only; no Silver/Gold; no formal G5 release or old R1/V3 writer changes"
}
CODE_PATHS=[
 "scripts/v097_seven_historical_format_registry.py",
 "scripts/v097_g2g3_formal_contracts_v2.py",
 "scripts/v097_r3_g2_seven_source_periodic_templates.py",
 "scripts/v097_r3_g2_seven_source_template_compare.py",
 "scripts/v097_r3_g2_shared_contract_engine.py",
 "scripts/v097_r3_g2_shared_74750_reconcile.py",
 "scripts/v097_r3_g2_six_source_60_real_pilot.py",
 "scripts/v097_r3_g2_six_official_approval_gate.py",
 "scripts/v097_r3_g2_six_source_original_url_provenance.py",
 "scripts/v097_r3_g2_official_api_exact_sha_pilot.py",
 "scripts/v097_r3_g2_seven_official_qa_overlay.py",
 "scripts/v097_r3_g2_fast_batch_74750.py",
 "scripts/v097_r3_ndc_last_missing_marker_cert.py",
 "scripts/v097_r3_twse_first_formal_g2_source_vintage.py",
 "scripts/v097_r3_tpex_first_formal_g2_source_vintage.py"
]
REPORT_PATHS=[
 "docs/V097_R3_G2_SEVEN_SOURCE_PERIODIC_TEMPLATES_DB_COMPARE_20261118.md",
 "docs/V097_R3_G2_SIX_SOURCE_60_REAL_NATIVE_PILOT_20261118.md",
 "docs/V097_R3_G2_SIX_SOURCE_OFFICIAL_APPROVAL_TEST_20261118.md",
 "docs/V097_R3_G2_FIRST_REAL_320_CERTIFIED_20261118.md",
]
def safe_existing(api,match,load,parent,name):
    found=match(api,parent,name)
    if found is None:
        return {"name":name,"state":"MISSING","drive_id":None}
    obj=load(api,found["id"])
    return {"name":name,"state":"FOUND_AND_READABLE","drive_id":found["id"],
            "content_sha256":digest(obj),
            "source_schema":obj.get("schema") if isinstance(obj,dict) else None}
def main():
    api,control,quality,match,load,_,_,call=source_api()
    root=match(api,quality,FOLDER)
    if not root:
        root=call(lambda:api.files().create(body={"name":FOLDER,"parents":[quality],
          "mimeType":"application/vnd.google-apps.folder"},fields="id,mimeType"))
    if root.get("mimeType")!="application/vnd.google-apps.folder":raise RuntimeError("NOT_A_FOLDER")
    prior={
        "source_templates":match(api,quality,SEVEN_SOURCE_FOLDER),
        "native_60":match(api,quality,SIX_SAMPLE_FOLDER),
        "official_60":match(api,quality,SIX_OFFICIAL_FOLDER),
        "original_url_60":match(api,quality,SIX_ORIGIN_FOLDER),
        "seven_overlay":match(api,quality,G2_OVERLAY_FOLDER),
    }
    if any(v is None for v in prior.values()):raise RuntimeError("REQUIRED_PRIOR_QA_FOLDER_MISSING")
    artifacts=[];source_history=[]
    for src in SOURCES:
        t=safe_existing(api,match,load,prior["source_templates"]["id"],
            f"r3_g2_shared_source_template_{src}_run_44263828295.json")
        cmp=safe_existing(api,match,load,prior["source_templates"]["id"],
            f"r3_g2_template_compare_{src}_{COUNTS[src]}_run_44263828295.json")
        evidence={"template":t,"frozen_comparison":cmp}
        if src!="NDC":
            evidence["native_sample_10"]=safe_existing(api,match,load,prior["native_60"]["id"],
                f"r3_g2_pilot_{src}_10_run_44261840978.json")
            evidence["official_doc_pilot"]=safe_existing(api,match,load,prior["official_60"]["id"],
                f"r3_g2_official_attempt_{src}_10_run_44266370461.json")
            evidence["original_url_provenance"]=safe_existing(api,match,load,prior["original_url_60"]["id"],
                f"r3_g2_original_provenance_{src}_run_44266749919.json")
        for role,ref in evidence.items():
            if ref["state"]!="FOUND_AND_READABLE":
                raise RuntimeError("MISSING_HISTORICAL_SOURCE_ARTIFACT:"+src+":"+role)
        payload={"schema":"R3_G2_PERSISTENT_SOURCE_HISTORY_V1","source":src,
            "created_by_github_run":RUN,"versioned_source_template":True,
            "dataset_type_count":DATASETS[src],"historical_source_period_candidate_count":PERIODS[src],
            "source_dataset_era_candidate_count":DATASETS[src]*PERIODS[src],
            "frozen_cohort":COUNTS[src],
            "qa_verified_source_vintage_g2":VERIFIED[src],
            "remaining_unverified":COUNTS[src]-VERIFIED[src],
            "existing_evidence_refs":evidence,
            "missing_proof_and_next_checks":SOURCE_HOLD[src],
            "template_official_era_scope_rule":"Source period candidates are NOT automatically certified per Dataset",
            "readme":"Proof hashes refer to immutable existing Drive receipts; do not re-download or overwrite existing Bronze",
            "history_replay_run_ids":[r for r,_ in RUN_HISTORY],
            "PIT_rule":RULES["PIT"],
            "bronze_modified":False,"silver_gold_materialized":False}
        name="R3_G2_SOURCE_HISTORY_"+src+"_RUN_"+RUN+".json"
        fid=put_once(api,root["id"],name,payload)
        if load(api,fid)!=payload:raise RuntimeError("SOURCE_HISTORY_NOT_READABLE:"+src)
        item={"source":src,"file_id":fid,"filename":name,"sha256":digest(payload),
              "source_template_file_id":t["drive_id"],
              "per_file_compare_report_id":cmp["drive_id"],"verified_readback":True}
        source_history.append(item)
        print("R3_G2_SOURCE_HISTORY_PERSISTED="+json.dumps(item,sort_keys=True,ensure_ascii=False),flush=True)
    # Reuse already committed 322 source-vintage QA overlay, without rewriting its prior Master.
    composite=safe_existing(api,match,load,prior["seven_overlay"]["id"],
       "r3_g2_official_322_seven_source_QA_overlay_run_44269047906.json")
    if composite["state"]!="FOUND_AND_READABLE":raise RuntimeError("PRIOR_322_IMMUTABLE_QA_OVERLAY_NOT_FOUND")
    rules_doc={"schema":"R3_G2_SHARED_TEMPLATE_SOP_AND_GATE_RULES_V1",
        "created_by_github_run":RUN,
        "seven_source_total":7,"frozen_cohort":COHORT,
        "candidate_formats":sum(DATASETS[s]*PERIODS[s] for s in SOURCES),
        "rules":RULES,
        "github_staging_branch":"r3-bronze-silver-ready-staging-20261118",
        "github_root":"https://github.com/danny541690/C1-RAW-DOWNLOADER",
        "implementations":CODE_PATHS,"longform_reports":REPORT_PATHS,
        "github_runs":[{"run_id":r,"description":d,
           "url":"https://github.com/danny541690/C1-RAW-DOWNLOADER/actions/runs/"+str(r)}
            for r,d in RUN_HISTORY]}
    rules_name="R3_G2_SEVEN_SOURCE_LONG_TERM_RULES_SOP_RUN_"+RUN+".json"
    rules_id=put_once(api,root["id"],rules_name,rules_doc)
    if load(api,rules_id)!=rules_doc:raise RuntimeError("SOP_PERSISTENCE_FAILED")
    index={"schema":"R3_G2_SEVEN_SOURCE_PERMANENT_HISTORY_MASTER_V1",
        "run":RUN,"created_utc":datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "source":"actual real-GitHub/Google-Drive receipts",
        "seven_sources":len(source_history),"frozen_cohort":COHORT,
        "historical_candidates":sum(DATASETS[s]*PERIODS[s] for s in SOURCES),
        "source_qa_total_g2_verified_source_vintage":sum(VERIFIED.values()),
        "still_hold_or_unproven":COHORT-sum(VERIFIED.values()),
        "historical_pit_asof_earlier_years_certified":False,
        "official_2026_source_vintage_scope_only":True,
        "prior_immutable_322_qa_overlay":composite,
        "source_history":source_history,
        "rules_sop_receipt_id":rules_id,
        "rules_sop_receipt_sha256":digest(rules_doc),
        "github_runs":[r for r,_ in RUN_HISTORY],
        "all_prior_required_evidence_readback":True,
        "all_new_documents_readback":True,
        "no_production_master_update":True,
        "bronze_modified":False,"silver_gold_materialized":False}
    name="R3_G2_SEVEN_SOURCE_PERMANENT_HISTORY_MASTER_RUN_"+RUN+".json"
    fid=put_once(api,root["id"],name,index)
    if load(api,fid)!=index:raise RuntimeError("PERMANENT_HISTORY_MASTER_READBACK_FAILED")
    print("R3_G2_PERMANENT_HISTORY_MASTER="+json.dumps({
        "run":RUN,"source_count":7,"cohort":COHORT,"g2_qa_verified":sum(VERIFIED.values()),
        "g2_qa_hold":COHORT-sum(VERIFIED.values()),"master_file_id":fid,
        "rules_file_id":rules_id,"folder_id":root["id"],
        "source_files":[{"source":x["source"],"file_id":x["file_id"]} for x in source_history],
        "readback":True},sort_keys=True,ensure_ascii=False),flush=True)
if __name__=="__main__":
    main()
