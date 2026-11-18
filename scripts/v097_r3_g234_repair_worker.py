"""JARVIS R3 seven-source G2/G3/G4 real evidence repair / reporting worker.

Consumes frozen 74750 cohort, legacy registries, and existing candidate schema maps.
Does NOT invent official approvals: only per-file attested certs can PASS.
Stores immutable, independently read-back run-scoped HOLD/PASS receipts under R3
isolated QA namespace. Never overwrites R1/V3 or Bronze and never makes Silver.
"""
from __future__ import annotations
import collections, datetime, hashlib, json, os, sys
from scripts.v097_bronze_autopilot import source_api
from scripts.v097_v3_preflight import read_baseline, assert_cohort
from scripts.v097_acceptance_engine_r1 import get_contracts,CERT_G2,CERT_G3
from scripts.v097_r3_gate_core import SOURCES, COHORT, digest
from scripts.v097_r3_formal_release_contracts import certified_contract, validate_g3, validate_g4
from scripts.v097_g2g3_formal_contracts_v2 import catalog
from scripts.v097_bronze_first_pipeline import match,put_once

FOLDER="R3_G234_FORMAL_REPAIR_ISOLATED"
COUNT={"TWSE":12071,"TPEx":13200,"MOPS":1935,"TDCC":40384,
       "TAIFEX":3140,"NDC":320,"FinMind":3700}
SIZES={70:10,700:100,1000:143}
VERSION="R3_G234_REPAIR_V1"
def sample(rows,src,size):
    if size==74750:return rows
    n=SIZES[size]
    if size==1000 and src=="FinMind":n=142
    assert len(rows)>=n
    return [rows[min(len(rows)-1,int((i+.5)*len(rows)/n))] for i in range(n)]

def evaluate_all(size):
    if size not in (70,700,1000,74750):raise ValueError("UNSUPPORTED_BOUND")
    api,control,quality,match_fn,load_json,put_once_fn,_,call=source_api()
    # Catalog is candidate-only, never a proof; deliberately record its count.
    candidate_specs=catalog()
    report={"schema":VERSION,"size":size,"run":os.environ.get("GITHUB_RUN_ID","manual"),
      "cohort":COHORT,"catalog_candidates":len(candidate_specs),"sources":[],
      "official_verified_catalog_templates":0,"no_silver_gold":True,
      "created_at":datetime.datetime.now(datetime.timezone.utc).isoformat()}
    counts=collections.Counter();total=0;baseline_total=0
    for src in SOURCES:
        rows=read_baseline(api,quality,match_fn,load_json,src)
        assert_cohort(rows,src);baseline_total+=len(rows)
        ids={r["source_id"] for r in rows}
        c2=get_contracts(api,control,match_fn,load_json,CERT_G2,src)
        c3=get_contracts(api,control,match_fn,load_json,CERT_G3,src)
        mapping_file=match_fn(api,control,"v097_SCHEMA_MAPPING_V1_CK_"+src+".json")
        maps=load_json(api,mapping_file["id"]).get("done",{}) if mapping_file else {}
        if not isinstance(maps,dict) or (set(c2)|set(c3)|set(maps))-ids:
            raise RuntimeError("ORPHAN_OR_INVALID_REGISTRY_"+src)
        picked=sample(rows,src,size)
        records=[];states=collections.Counter()
        for r in picked:
            sid=r["source_id"]
            g2=certified_contract(c2.get(sid),r)
            g3=validate_g3(c3.get(sid),r,g2)
            g4=validate_g4(maps.get(sid),r,g2,g3)
            outcomes={"G2":g2["status"],"G3":g3["status"],"G4":g4["status"]}
            reasons={gate:res.get("reason") for gate,res in (("G2",g2),("G3",g3),("G4",g4))
                     if res.get("status")!="PASS"}
            # Only independent certs with required evidence can emit PASS; the
            # existing R1/Candidate schemas do not accidentally get promoted.
            records.append({"source_id":sid,"source":src,"source_sha256":r["source_sha256"],
                "gates":outcomes,"hold_reasons":reasons,
                "legacy_g2_present":sid in c2,"legacy_g3_present":sid in c3,
                "g4_header_candidate":maps.get(sid,{}).get("status")=="HEADER_MATCHED_UNCERTIFIED",
                "g2_evidence_digest":g2.get("proof_digest"),
                "g3_evidence_digest":g3.get("proof_digest"),
                "g4_evidence_digest":g4.get("proof_digest")})
            for gate,st in outcomes.items():states[gate+":"+st]+=1;counts[gate+":"+st]+=1
            for reason in reasons.values():states["reason:"+reason]+=1;counts["reason:"+reason]+=1
        total+=len(records)
        report["sources"].append({"source":src,"cohort":len(rows),"evaluated":len(records),
               "registry_g2":len(c2),"registry_g3":len(c3),
               "existing_mapping_entries":len(maps),
               "mapping_header_candidates":sum(isinstance(v,dict) and v.get("status")=="HEADER_MATCHED_UNCERTIFIED" for v in maps.values()),
               "statuses":dict(states)})
        # Only run-scoped PRIVATE isolated QA namespace receives file-level details.
        report.setdefault("_private_records",[]).extend(records)
        print("R3_G234_REPAIR_SOURCE="+json.dumps(report["sources"][-1],sort_keys=True),flush=True)
    if baseline_total!=COHORT or total!=size:raise RuntimeError("FROZEN_COHORT_OR_SAMPLE_COUNT_MISMATCH")
    private_records=report.pop("_private_records")
    report["counts"]=dict(counts);report["evaluated"]=total
    # Always distinguish verified source-file proof from candidate template status.
    report["ready_for_G5"]=sum(1 for x in private_records if all(x["gates"][g]=="PASS" for g in ("G2","G3","G4")))
    report["formal_certificates_issued"]=0
    folder=match_fn(api,quality,FOLDER)
    if not folder:
        folder=call(lambda:api.files().create(body={"name":FOLDER,"parents":[quality],
                 "mimeType":"application/vnd.google-apps.folder"},fields="id,mimeType"))
    if folder.get("mimeType")!="application/vnd.google-apps.folder":
        raise RuntimeError("NOT_ISOLATED_FOLDER")
    fid=folder["id"]
    # idempotent full receipts, exact readback after upload.
    out={"summary":report,"records":private_records}
    filename=f"r3_g234_{size}_run_{report['run']}.json"
    objid=put_once_fn(api,fid,filename,out)
    committed=load_json(api,objid)
    if committed!=out:raise RuntimeError("IMMUTABLE_DRIVE_READBACK_MISMATCH")
    report["drive_receipt_name"]=filename
    report["readback_sha256"]=digest(committed)
    report["readback_verified"]=True
    print("R3_G234_REPAIR_SUMMARY="+json.dumps(report,sort_keys=True),flush=True)
    return report

if __name__=="__main__":
    if len(sys.argv)!=3 or sys.argv[1]!="run":raise SystemExit("usage: run 70|700|1000|74750")
    evaluate_all(int(sys.argv[2]))
