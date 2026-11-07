"""R26 evidence reconciliation / strict go-live readiness register.
Merges actual R17/R18/R19/R20/R22/R24/R25 output without converting
a narrow PASS into a wider production PASS. No changes to production.
"""
import json,pathlib,unittest,datetime
ROOT=pathlib.Path("r26_evidence_register"); ROOT.mkdir(exist_ok=True)
PROD_GATE={
"G0-01":"legacy_main_sha_and_active_runs",
"G0-02":"v093_source_manifest_inventory",
"G0-03":"drive_auth_and_quota_preflight",
"T01":"real_raw_independent_copy_sha",
"T03":"real_daily_and_migration_parallel",
"T05":"distributed_cas_two_runners",
"T08":"real_market_numeric_pit",
"T09":"real_raw_to_silver_gold",
"T10":"release_rollback_and_restore",
"T14":"two_market_sessions_daily",
"T16":"v095_independent_restore",
}
EVIDENCE={
"T01":{"scope":"7 legacy v093 raw copies -> v095 TEST_ONLY Bronze, SHA matched",
"link":"https://drive.google.com/file/d/1kyZPy6n4wZa_Z7Djka9va7K2D2bHIEO-/view","state":"PARTIAL_SCOPE"},
"T09":{"scope":"MOPS,NDC limited one-row three-layer and TDCC full structural candidate; TWSE TPEx TAIFEX FinMind lack full continuous flow",
"link":"https://github.com/danny541690/C1-RAW-DOWNLOADER/actions/runs/41827507694","state":"PARTIAL_SCOPE"},
"T16":{"scope":"TDCC live 69887-row GitHub Artifact restored on second runner + SHA, not independently restored full production database",
"link":"https://github.com/danny541690/C1-RAW-DOWNLOADER/actions/runs/41820474732","state":"PARTIAL_SCOPE"},
"T08":{"scope":"R25 TDCC source date, padding and 7-condition unsigned rejection tested, public PIT not signed",
"link":"https://github.com/danny541690/C1-RAW-DOWNLOADER/actions/runs/41827507694","state":"PARTIAL_SCOPE"},
"T05":{"scope":"GitHub Action serialization and cross-runner restore work; Google Drive distributed fencing/CAS not tested",
"link":"https://github.com/danny541690/C1-RAW-DOWNLOADER/actions/runs/41820474732","state":"PARTIAL_SCOPE"},
}
def load(p): return json.loads(pathlib.Path(p).read_text(encoding="utf-8"))
def reconcile(source_status,tdcc_report,admission):
    if set(source_status["sources"])!={"TWSE","TPEx","MOPS","NDC","TAIFEX","TDCC","FinMind"}:
        raise ValueError("SOURCE_SET_MISMATCH")
    if tdcc_report["security_date_groups"]!=admission["tdcc_groups"]:
        raise ValueError("TDCC_CANDIDATE_MISMATCH")
    if admission.get("release_approved") is not False or source_status.get("release_approved") is not False:
        raise ValueError("UNEXPECTED_RELEASE_TRUE")
    if admission["release_missing_control_rejections"]!=7:
        raise ValueError("MISSING_PUBLISH_REJECTION_TEST")
    checks=[]
    for ident,key in PROD_GATE.items():
        item=EVIDENCE.get(ident,{})
        # Strict production gate: PARTIAL_SCOPE never equals PASS.
        checks.append({"id":ident,"name":key,"production_status":"BLOCKED",
            "narrow_test_status":item.get("state","NO_LIVE_PRODUCTION_EVIDENCE"),
            "evidence_url":item.get("link"),
            "verified_limited_scope":item.get("scope")})
    out={"schema":"JARVIS_V095_R26_RECONCILED_GATE","as_of":"2026-11-04",
       "release_approved":False,"production_gates_total":len(checks),
       "production_gates_passed":0,
       "production_gates_blocked":len(checks),
       "partial_evidence_categories":sum(c["narrow_test_status"]=="PARTIAL_SCOPE" for c in checks),
       "candidate_tdcc_groups":tdcc_report["security_date_groups"],
       "candidate_tdcc_warning_groups":admission["tdcc_semantic_warning_groups"],
       "seven_source_api_or_candidate_status":{s:x["status"] for s,x in source_status["sources"].items()},
       "checks":checks,
       "interpretation":"11 production gates remain blocked at their original FULL scope. Narrow stage test achievements are recorded as partial, not erased or overstated.",
       "remaining_required_activities":["7-source public timestamp PIT and revisions",
         "complete TWSE/TPEx/TAIFEX/FinMind continuous RAW->Parquet->investment Gold",
         "TSE/OTC official historical security master with dated membership",
         "Drive publisher single-writer production credential and fencing / atomic manifest update",
         "live daily + backfill overlap, two effective market sessions",
         "full deployment rollback + independently restored Drive data and controlled promotion"]}
    return out
class Regression(unittest.TestCase):
    def test_partial_does_not_promote(self):
        x={"sources":{s:{"status":"API_SAMPLE_PASS"} for s in
        ("TWSE","TPEx","MOPS","NDC","TAIFEX","TDCC","FinMind")},"release_approved":False}
        r=reconcile(x,{"security_date_groups":4111},{"tdcc_groups":4111,"release_missing_control_rejections":7,"release_approved":False,"tdcc_semantic_warning_groups":496})
        self.assertFalse(r["release_approved"])
        self.assertEqual(r["production_gates_blocked"],11)
        self.assertEqual(r["partial_evidence_categories"],5)
    def test_missing_seventh_source_blocks(self):
        with self.assertRaises(ValueError):reconcile({"sources":{},"release_approved":False},
         {"security_date_groups":4111},{"tdcc_groups":4111,"release_missing_control_rejections":7,"release_approved":False,"tdcc_semantic_warning_groups":496})
    def test_false_approval_detected(self):
        x={"sources":{s:{"status":"PASS"} for s in
        ("TWSE","TPEx","MOPS","NDC","TAIFEX","TDCC","FinMind")},"release_approved":True}
        with self.assertRaises(ValueError):reconcile(x,{"security_date_groups":4111},
         {"tdcc_groups":4111,"release_missing_control_rejections":7,"release_approved":False,"tdcc_semantic_warning_groups":496})
if __name__=="__main__":
    unittest.main(verbosity=2,exit=False)
    evidence=reconcile(load("r22_combined/R22_RELEASE_GATE.json"),
            load("r24_tdcc_numeric_gold_candidate/report.json"),
            load("r25_integrated_admission/R25_SIGNED_ADMISSION_GATE.json"))
    (ROOT/"R26_RECONCILED_GO_LIVE_GATE.json").write_text(json.dumps(evidence,indent=2,ensure_ascii=False))
    print("R26_GATES_BLOCKED="+str(evidence["production_gates_blocked"]))
    print("R26_PARTIAL_EVIDENCE="+str(evidence["partial_evidence_categories"]))
    print("R26_RELEASE_APPROVED=false")
