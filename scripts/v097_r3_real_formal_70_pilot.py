"""R3 live 70-row formal G2/G3/G4 pilot, read-only against Drive registries.

Does not bootstrap prior candidate evidence into official attestation.
Ten frozen rows per source are evaluated with the exact R3 formal kernel.
Results are publicly summarized without file IDs or private raw contents.
"""
from __future__ import annotations
import collections, json, sys
from scripts.v097_bronze_autopilot import source_api
from scripts.v097_v3_preflight import read_baseline, assert_cohort
from scripts.v097_acceptance_engine_r1 import get_contracts,CERT_G2,CERT_G3
from scripts.v097_r3_gate_core import SOURCES, COHORT
from scripts.v097_r3_formal_release_contracts import certified_contract,validate_g3,validate_g4

def run():
    api,control,quality,match,load_json,_,_,call=source_api()
    all_reports=[];total=0
    for src in SOURCES:
        rows=read_baseline(api,quality,match,load_json,src)
        assert_cohort(rows,src)
        total+=len(rows)
        c2=get_contracts(api,control,match,load_json,CERT_G2,src)
        c3=get_contracts(api,control,match,load_json,CERT_G3,src)
        mf=match(api,control,"v097_SCHEMA_MAPPING_V1_CK_"+src+".json")
        maps=load_json(api,mf["id"]).get("done",{}) if mf else {}
        if not isinstance(maps,dict):raise RuntimeError("BAD_SOURCE_MAPPING_CHECKPOINT")
        if set(c2)-{r["source_id"] for r in rows} or set(c3)-{r["source_id"] for r in rows} or set(maps)-{r["source_id"] for r in rows}:
            raise RuntimeError("REGISTRY_ORPHAN_"+src)
        outcomes=collections.Counter()
        for slot in range(10):
            item=rows[min(len(rows)-1,int((slot+0.5)*len(rows)/10))]
            sid=item["source_id"]
            # Existing R1 registries are read as historical source evidence. The
            # new R3 contract is not automatically granted based on these entries.
            g2=certified_contract(c2.get(sid),item)
            g3=validate_g3(c3.get(sid),item,g2)
            g4=validate_g4(maps.get(sid),item,g2,g3)
            for gate,rec in (("G2",g2),("G3",g3),("G4",g4)):
                outcomes[gate+":"+rec.get("status","UNKNOWN")]+=1
                if rec.get("status")!="PASS":
                    outcomes["reason:"+rec.get("reason","UNKNOWN")]+=1
        out={"source":src,"cohort":len(rows),"sample":10,
             "g2_g3_g4_results":dict(outcomes),"released":0}
        all_reports.append(out)
        print("R3_REAL_FORMAL_70_SOURCE="+json.dumps(out,sort_keys=True),flush=True)
    if total!=COHORT:raise RuntimeError("FROZEN_COHORT_COUNT_DRIFT")
    doc={"schema":"R3_REAL_70_CONTRACT_PILOT_V1","cohort":total,
         "sample":70,"sources":all_reports,"r3_g5_issued":0,"production_ready":False,
         "note":"Live registries evaluated against formal R3 contract; existing R1 candidates are not automatically promoted."}
    print("R3_REAL_FORMAL_70_MASTER="+json.dumps(doc,sort_keys=True),flush=True)
if __name__=="__main__":
    if sys.argv[1:]!=["read-only"]:raise SystemExit("usage: read-only")
    run()
