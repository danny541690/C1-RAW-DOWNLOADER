"""R3 live G2/G3 official registries and G4 candidate mapping census.

Reads existing R1 contract certificates and V097 mapping checkpoints only.
A candidate source/era or header-match is never counted as a certified PASS.
Does not change any Google Drive data or produce Silver/Gold.
"""
from __future__ import annotations
import collections, json, sys
from scripts.v097_bronze_autopilot import source_api
from scripts.v097_v3_preflight import read_baseline, assert_cohort
from scripts.v097_r3_gate_core import SOURCES, COHORT
from scripts.v097_acceptance_engine_r1 import get_contracts, CERT_G2, CERT_G3

def census():
    api,control,quality,match,load_json,_,_,call=source_api()
    report=[];total=0
    for source in SOURCES:
        rows=read_baseline(api,quality,match,load_json,source)
        assert_cohort(rows,source);total+=len(rows)
        known={r["source_id"]:r for r in rows}
        cert2=get_contracts(api,control,match,load_json,CERT_G2,source)
        cert3=get_contracts(api,control,match,load_json,CERT_G3,source)
        if set(cert2)-set(known) or set(cert3)-set(known):
            raise RuntimeError("CERTIFICATE_REGISTRY_ORPHAN_"+source)
        candidates=0;valid2=0;valid3=0
        from scripts.v097_acceptance_engine_r1 import valid_proof
        for sid,proof in cert2.items():
            if isinstance(proof,dict) and valid_proof(proof,known[sid],"R1_G2_DATASET_CERT_V1"):
                if proof.get("dataset_origin_verified") is True and proof.get("publication_asof_verified") is True:
                    valid2+=1
        for sid,proof in cert3.items():
            g2=cert2.get(sid)
            if not isinstance(g2,dict):continue
            if valid_proof(proof,known[sid],"R1_G3_SCHEMA_CERT_V1",dataset=g2.get("dataset")) and (
                proof.get("dataset_contract_version")==g2.get("contract_version")
                and proof.get("full_file_scanned") is True and proof.get("native_units_verified") is True
                and proof.get("types_and_keys_verified") is True and proof.get("validation_errors") == 0):
                valid3+=1
        f=match(api,control,"v097_SCHEMA_MAPPING_V1_CK_"+source+".json")
        if f:
            data=load_json(api,f["id"])
            mapping=data.get("done",{})
            if not isinstance(mapping,dict) or set(mapping)-set(known):
                raise RuntimeError("MAPPING_REGISTRY_ORPHAN_"+source)
            candidates=sum(1 for c in mapping.values() if isinstance(c,dict) and
                           c.get("status")=="HEADER_MATCHED_UNCERTIFIED")
        row={"source":source,"cohort":len(rows),"legacy_g2_cert_registry_entries":len(cert2),
             "legacy_g3_cert_registry_entries":len(cert3),
             "g2_official_review_shape_valid":valid2,"g3_full_parse_shape_valid":valid3,
             "g4_header_candidates_uncertified":candidates,
             "r3_formal_approved":0}
        report.append(row)
        print("R3_LIVE_G2_G4_SOURCE="+json.dumps(row,sort_keys=True),flush=True)
    if total!=COHORT:raise RuntimeError("G2_G4_COHORT_DRIFT")
    output={"schema":"R3_LIVE_CERTIFICATE_CENSUS_V1","cohort":total,
            "sources":report,"formal_r3_ready":0,
            "warning":"Existing cert entries are only SHAPE checks, not independently verified R3 official template, G4 mapping or G5 PASS."}
    print("R3_LIVE_G2_G4_SUMMARY="+json.dumps(output,sort_keys=True),flush=True)
    return output
if __name__=="__main__":
    if sys.argv[1:]!=["read-only"]:raise SystemExit("usage: read-only")
    census()
