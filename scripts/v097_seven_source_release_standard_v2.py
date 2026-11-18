#!/usr/bin/env python3
"""JARVIS v0.97 seven-source format acceptance release standard V2.

Pure policy engine. No network, no Bronze mutation, no Silver/Gold execution.
Production R1 G4 READY must carry a matching G3 acknowledgement of this rule.
R3 source-vintage QA overlays are evidence, never automatic R1 G2 promotion.
"""
import sys

STANDARD_VERSION="JARVIS_V097_SEVEN_SOURCE_FORMAT_G0_G5_V2_20261119"
FROZEN_COHORT=74750
SOURCE_COUNTS={"TWSE":12071,"TPEx":13200,"MOPS":1935,"TDCC":40384,
               "TAIFEX":3140,"NDC":320,"FinMind":3700}
GATES=("G0","G1","G2","G3","G4")
ERROR_FAMILIES={
 "SOURCE_DOWNLOAD":"HTTP, auth, rate limit, official endpoint or archive missing",
 "BYTE_INTEGRITY":"empty bytes, corrupt ZIP/member, SHA or CRC mismatch",
 "DATE_IDENTITY":"observation date, effective date, code or source dataset conflict",
 "HEADER_SCHEMA":"unknown era, alias, optional field, member type or header ambiguity",
 "CONTENT_VALUES":"same-date same-dataset row/key/value mismatch, rounding or unit",
 "METADATA_SCOPE":"stock scope, revision/PIT or historical publication availability",
 "PROOF_REGISTRY":"certificate mismatch, orphan ID, obsolete rule or failed readback",
 "SCHEDULER":"timeout, retry limit, paused run, checkpoint collision or writer race",
}
def release_problems(gates,g2,g3,source_id,source,sha):
    issues=[]
    if source not in SOURCE_COUNTS or not source_id or not isinstance(sha,str) or len(sha)!=64:
        issues.append("SOURCE_ID_OR_SHA_INVALID")
    if not isinstance(gates,dict) or any(gates.get(g)!=( "READY" if g=="G4" else "PASS") for g in GATES):
        issues.append("G0_G4_NOT_ALL_VERIFIED")
    if not isinstance(g2,dict) or g2.get("source_id")!=source_id or g2.get("source")!=source or g2.get("sha")!=sha:
        issues.append("G2_CERT_SOURCE_SHA_MISMATCH")
    if not isinstance(g3,dict) or g3.get("source_id")!=source_id or g3.get("source")!=source or g3.get("sha")!=sha:
        issues.append("G3_CERT_SOURCE_SHA_MISMATCH")
    if isinstance(g3,dict) and g3.get("seven_source_standard_version")!=STANDARD_VERSION:
        issues.append("NEW_STANDARD_NOT_ACKNOWLEDGED_BY_G3")
    if isinstance(g2,dict) and isinstance(g3,dict) and (
        g2.get("dataset")!=g3.get("dataset") or
        g2.get("contract_version")!=g3.get("dataset_contract_version")):
        issues.append("G2_G3_DATASET_OR_CONTRACT_CONFLICT")
    return issues
def may_release(gates,g2,g3,source_id,source,sha):
    return not release_problems(gates,g2,g3,source_id,source,sha)
def selftest():
    assert sum(SOURCE_COUNTS.values())==FROZEN_COHORT
    sha="a"*64
    p={"source_id":"S","source":"TWSE","sha":sha,"dataset":"STOCK_DAILY_OHLCV",
       "contract_version":"g2-v2"}
    g3={**p,"dataset_contract_version":"g2-v2",
        "seven_source_standard_version":STANDARD_VERSION}
    gates=dict.fromkeys(GATES,"PASS");gates["G4"]="READY"
    assert may_release(gates,p,g3,"S","TWSE",sha)
    assert not may_release(gates,p,{**g3,"seven_source_standard_version":"OLD"},"S","TWSE",sha)
    assert not may_release(gates,p,{**g3,"dataset":"INDEX"},"S","TWSE",sha)
    assert not may_release({**gates,"G3":"PENDING"},p,g3,"S","TWSE",sha)
    assert not may_release(gates,p,g3,"OTHER","TWSE",sha)
    print("SEVEN_SOURCE_RELEASE_STANDARD_V2_SELFTEST_PASS")
if __name__=="__main__":
    if sys.argv[1:]==["selftest"]:selftest()
    else:raise SystemExit("selftest")
