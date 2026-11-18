"""Seven (not 143 separate) source-level versioned G2 template libraries.

Each source library nests datasets and historical edition windows, with
format, aliases, key, official references and exact evidence state.
The original 143 source×dataset×era products are only candidate cross joins.
Do not imply those eras are certified for every dataset.
"""
from __future__ import annotations
import collections
import datetime
from scripts.v097_seven_historical_format_registry import OFFICIAL_VERSIONS
from scripts.v097_g2g3_formal_contracts_v2 import contract
from scripts.v097_r3_g2_shared_contract_engine import real_day
from scripts.v097_r3_gate_core import SOURCES

SCHEMA="R3_G2_SEVEN_SOURCE_PERIODIC_LIBRARY_V1"
NDC_VINTAGE="NDC_2026_CAPTURED_REVISED_XLSX_5SHEET_JSON_V1"

def bound_start(ym):return ym+"-01"
def bound_end(ym):
    if ym=="9999-12":return None
    year,month=(int(v) for v in ym.split("-"))
    nextyear,nextmonth=(year+1,1) if month==12 else (year,month+1)
    return (datetime.date(nextyear,nextmonth,1)-datetime.timedelta(days=1)).isoformat()

def make_source_library(source,official_registry):
    if source not in SOURCES:raise ValueError("UNKNOWN_SOURCE")
    cfg=OFFICIAL_VERSIONS[source]
    registered=[r for r in (official_registry or {}).get("templates",[])
                if isinstance(r,dict) and r.get("source")==source]
    assert len({x.get("template_id") for x in registered})==len(registered)
    entries=[]
    for ds in cfg["datasets"]:
        editions=[]
        for period in cfg["periods"]:
            spec=contract(source,ds,period["id"])
            approved=[a for a in registered if a.get("dataset")==ds
                      and a.get("historical_era")==period["id"]
                      and a.get("approval_status")=="APPROVED"]
            editions.append({
                "historical_era":period["id"],
                "historical_window_for_candidate_selection":{
                    "from":bound_start(period["start"]),
                    "to":bound_end(period["end"])},
                "era_source":"EXISTING_SEVEN_SOURCE_HISTORY_REGISTRY_NOT_DATASET_LEVEL_CERT",
                "era_description":period["format"],
                "official_dataset_start_date":None,
                "official_dataset_start_status":"NOT_ATTESTED_PER_DATASET",
                "native_format_variants":spec["source_native_variants"],
                "required_fields_candidate":spec["required_fields"],
                "optional_fields_candidate":[],
                "approved_aliases_candidate":{},
                "candidate_primary_key":spec["candidate_primary_key"],
                "native_units_candidate":spec["native_units_candidate"],
                "official_reference_candidates":spec["official_source_reference_candidates"],
                "official_document_evidence_status":"HOLD_UNLESS_VALIDATED_APPROVED_REGISTRY",
                "formal_approved_editions":approved,
                "g2_release_state":"APPROVED_ENTRY_REQUIRES_REMOTE_PROOF_AND_FILE_BINDING" if approved
                          else "CANDIDATE_ONLY_HOLD"})
        entries.append({
            "dataset":ds,
            "dataset_official_begin_date":None,
            "dataset_official_begin_status":"MISSING_DATASET_SPECIFIC_PRIMARY_EVIDENCE",
            "editions":editions,
            "candidate_period_count":len(editions),
            "actual_dataset_edition_count":"UNKNOWN_UNTIL_OFFICIAL_NATIVE_REVIEW"})
    return {"schema":SCHEMA,"source":source,"source_reference":cfg["reference"],
            "template_architecture":"ONE_SOURCE_LIBRARY_WITH_DATASET_AND_HISTORY_EDITION_CHILDREN",
            "candidate_periods":len(cfg["periods"]),
            "datasets":entries,"candidate_matrix_count":len(cfg["datasets"])*len(cfg["periods"]),
            "formal_approved_source_vintage_count":len(registered),
            "historical_revisions_warning":cfg["historical_warning"],
            "no_bronze_mutation":True,"silver_gold_materialized":False}

def library_set(official_registry):
    out={s:make_source_library(s,official_registry) for s in SOURCES}
    if len(out)!=7 or sum(v["candidate_matrix_count"] for v in out.values())!=143:
        raise RuntimeError("SEVEN_LIBRARY_143_MATRIX_DRIFT")
    for src,library in out.items():
        periods=OFFICIAL_VERSIONS[src]["periods"]
        for i,p in enumerate(periods[1:],1):
            old=periods[i-1]
            if old["end"]>p["start"]:raise RuntimeError("OVERLAPPING_SOURCE_HISTORY")
    return out
