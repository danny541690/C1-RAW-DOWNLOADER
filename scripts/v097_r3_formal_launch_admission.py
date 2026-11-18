"""R3 FORMAL RELEASE ADMISSION — live fail-closed hard gate.

Never disables R1/V3, never publishes formal R3 Master, no Bronze writes,
no Silver/Gold. It is not a production publisher.
"""
import json,sys
from scripts.v097_r3_live_handover_audit import inspect
from scripts.v097_r3_live_contract_census import census
from scripts.v097_r3_real_formal_70_pilot import run as pilot70
from scripts.v097_r3_gate_core import COHORT

def admission():
    g0=inspect()
    contracts=census()
    pilot=pilot70()
    blockers=[]
    if g0["handover"]["status"]!="PASS":blockers.append("G0_OLD_WRITERS_NOT_RETIRED")
    if contracts["cohort"]!=COHORT:blockers.append("COHORT_DRIFT")
    if sum(s["g2_official_review_shape_valid"] for s in contracts["sources"])!=COHORT:
        blockers.append("G2_OFFICIAL_PER_FILE_CERTIFICATES_INCOMPLETE")
    if sum(s["g3_full_parse_shape_valid"] for s in contracts["sources"])!=COHORT:
        blockers.append("G3_NATIVE_FULL_FILE_CERTIFICATES_INCOMPLETE")
    if pilot.get("production_ready") is not True:
        blockers.append("G4_REAL_SILVER_INPUT_CONTRACT_NOT_CERTIFIED")
    # The production G5 Drive writer and durable certificate readback
    # must be separately deployed and verified. Never infer from staging receipt.
    blockers.append("G5_PRODUCTION_WRITER_AND_READBACK_NOT_RELEASED")
    report={"schema":"R3_FORMAL_ADMISSION_V1","cohort":COHORT,
            "result":"BLOCKED" if blockers else "ADMITTED","blockers":blockers,
            "active_legacy_sample":g0["old_writers_active_at_snapshot"],
            "g2_shape_valid":sum(s["g2_official_review_shape_valid"] for s in contracts["sources"]),
            "g3_shape_valid":sum(s["g3_full_parse_shape_valid"] for s in contracts["sources"]),
            "sample":pilot["sample"],"production_writes":0,
            "silver_materialized":0,"gold_materialized":0}
    print("R3_FORMAL_ADMISSION="+json.dumps(report,ensure_ascii=False,sort_keys=True),flush=True)
    if blockers:raise SystemExit(12)
if __name__=="__main__":
    if sys.argv[1:]!=["check"]:raise SystemExit("usage: check")
    admission()
