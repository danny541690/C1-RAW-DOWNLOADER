"""JARVIS v0.95 contract audit for v0.93->v0.95 migration and repair.
Only isolated static checks and synthetic QA. No Drive modifications or market data
classification without an official source manifest and per-dataset contracts.
"""
import json,os,pathlib,unittest
ROOT=pathlib.Path("v095_migration_architecture_audit")
ROOT.mkdir(exist_ok=True)
SOURCE_MAP={
 "TWSE":"TWSE","TPEx":"TPEx","MOPS":"MOPS","TDCC":"TDCC",
 "TAIFEX":"TAIFEX","NDC":"NDC","FinMind":None,"XQ":None
}
STAGES={
 "10_INGEST_STAGING":"quarantine/inbox/candidate/rejected",
 "20_BRONZE_RAW":"immutable source-native bytes, sha256, origin and fetched_at",
 "30_SILVER_STANDARD":"typed dataset-specific Parquet; official units and business keys",
 "40_GOLD_FEATURES":"PIT approved versioned factors only",
 "60_OPERATIONS_QA":"persistent manifest, issue queue, repair attempts and checkpoint",
 "70_RELEASE_BACKUP":"atomic version pointer, restore evidence and independent backup"
}
ALLOWED_STATUSES={
 "EXPECTED","PENDING","FETCHED_UNVERIFIED","VALIDATED","PIT_APPROVED",
 "NOT_YET_PUBLISHED","NOT_AVAILABLE","NOT_APPLICABLE",
 "DOWNLOAD_ERROR","CORRUPTED","SCHEMA_ERROR","VALUE_ERROR","PIT_ERROR",
 "REPAIRING","BLOCKED","CLOSED_VERIFIED"
}
def assess_legacy(file,source,source_manifest=None,policy=None):
    """Do not infer dataset or official coverage from filename/year/folder."""
    if source not in SOURCE_MAP:return {"decision":"REJECT_UNKNOWN_SOURCE"}
    if source=="XQ":return {"decision":"HOLD_XQ_MANUAL_EXPORT_CONTRACT"}
    if source=="FinMind" and not (policy or {}).get("license_tier_verified"):
        return {"decision":"HOLD_FINMIND_TIER_UNKNOWN"}
    if not file.get("sha256") or not file.get("size_bytes"):
        return {"decision":"HOLD_UNVERIFIED_BYTES"}
    if file.get("manifest_only") or file.get("is_canary") or file.get("archive_empty"):
        return {"decision":"QUARANTINE_NON_MARKET_DATA"}
    required=("dataset_id","source_endpoint","native_units","frequency",
      "market_scope","business_key","published_at","schema_version",
      "availability_start","expected_population","revision_policy")
    if not source_manifest or any(not source_manifest.get(k) for k in required):
        return {"decision":"HOLD_DATA_CONTRACT_MISSING"}
    if source_manifest["published_at"]=="UNKNOWN":
        return {"decision":"HOLD_PIT_FOR_GOLD"}
    return {"decision":"STAGING_VALIDATION_ONLY"}
def decide_missing(availability,observed,source_available=None):
    """Empty folder never equals download error without an expected official release."""
    if observed:return "FETCHED_UNVERIFIED"
    if availability=="not_yet_published":return "NOT_YET_PUBLISHED"
    if availability=="source_not_available_with_evidence":return "NOT_AVAILABLE"
    if availability=="out_of_scope":return "NOT_APPLICABLE"
    if availability=="published_and_expected":return "EXPECTED"
    return "PENDING"
def repair_route(issue,attempts):
    if issue in ("SCHEMA_ERROR","VALUE_ERROR","PIT_ERROR"):
        return "ADAPTER_OR_MANUAL_SEMANTIC_REVIEW_NO_BLIND_REFETCH"
    if issue in ("CORRUPTED","DOWNLOAD_ERROR") and attempts<3:
        return "RETRY_OFFICIAL_BACKOFF"
    if issue in ("CORRUPTED","DOWNLOAD_ERROR") and attempts>=3:
        return "BLOCKED_RETRY_BUDGET_EXHAUSTED"
    if issue=="NOT_YET_PUBLISHED":return "WAIT_OFFICIAL_RELEASE"
    if issue in ("NOT_AVAILABLE","NOT_APPLICABLE"):return "PROVEN_EXCEPTION"
    return "REVIEW_REQUIRED"
def audit_inventory(snapshot):
    return {"historical_file_inventory_complete":snapshot.get("historical_file_inventory_complete",False),
      "per_file_sha256_complete":snapshot.get("per_file_sha256_complete",False),
      "source_contracts_complete":snapshot.get("source_contracts_complete",False),
      "complete_historical_pit":snapshot.get("complete_historical_pit",False),
      "drive_writer_cas_tested":snapshot.get("drive_writer_cas_tested",False),
      "bulk_copy_approved":False,"production_release_approved":False,
      "source_root":"C1_0.93/01_RAW",
      "dest_staging":"C1_0.95/10_INGEST_STAGING/CANDIDATE",
      "dest_bronze":"C1_0.95/20_BRONZE_RAW",
      "months_not_proof":"27 years x 8 folders only, many months empty / unverified"}
class GateTests(unittest.TestCase):
    def test_legacy_folder_is_not_dataset_identity(self):
        self.assertEqual(assess_legacy({"sha256":"abc","size_bytes":128},"TWSE")["decision"],
                         "HOLD_DATA_CONTRACT_MISSING")
    def test_manifest_only_never_valid_market_data(self):
        self.assertEqual(assess_legacy({"sha256":"abc","size_bytes":256,"manifest_only":True},"MOPS")["decision"],
                         "QUARANTINE_NON_MARKET_DATA")
    def test_finmind_tier_must_be_proven(self):
        self.assertEqual(assess_legacy({"sha256":"abc","size_bytes":64},"FinMind")["decision"],
                         "HOLD_FINMIND_TIER_UNKNOWN")
    def test_xq_not_official_download_source(self):
        self.assertEqual(assess_legacy({"sha256":"abc","size_bytes":64},"XQ")["decision"],
                         "HOLD_XQ_MANUAL_EXPORT_CONTRACT")
    def test_empty_not_automatically_redownload(self):
        self.assertEqual(decide_missing("unknown",False),"PENDING")
        self.assertEqual(decide_missing("not_yet_published",False),"NOT_YET_PUBLISHED")
        self.assertEqual(decide_missing("source_not_available_with_evidence",False),"NOT_AVAILABLE")
    def test_expected_and_missing_can_enqueue(self):
        self.assertEqual(decide_missing("published_and_expected",False),"EXPECTED")
    def test_no_blind_refetch_on_schema_or_pit(self):
        for issue in ("SCHEMA_ERROR","VALUE_ERROR","PIT_ERROR"):
            self.assertIn("REVIEW",repair_route(issue,0))
    def test_bounded_transport_retry(self):
        self.assertEqual(repair_route("DOWNLOAD_ERROR",2),"RETRY_OFFICIAL_BACKOFF")
        self.assertEqual(repair_route("DOWNLOAD_ERROR",3),"BLOCKED_RETRY_BUDGET_EXHAUSTED")
    def test_no_pit_false_promotion(self):
        m={k:"source_declared" for k in ("dataset_id","source_endpoint","native_units","frequency","market_scope",
          "business_key","published_at","schema_version","availability_start","expected_population","revision_policy")}
        m["published_at"]="UNKNOWN"
        self.assertEqual(assess_legacy({"sha256":"abc","size_bytes":128},"TWSE",m)["decision"],"HOLD_PIT_FOR_GOLD")
    def test_never_releases_incomplete_inventory(self):
        r=audit_inventory({})
        self.assertFalse(r["bulk_copy_approved"])
        self.assertFalse(r["production_release_approved"])
if __name__=="__main__":
    suite=unittest.defaultTestLoader.loadTestsFromTestCase(GateTests)
    run=unittest.TextTestRunner(verbosity=2).run(suite)
    report={"schema":"JARVIS_v095_MIGRATION_ARCHITECTURE_AUDIT_V1",
      "spec_basis":"Drive JARVIS_C1_v0.95_Architecture_Management_R1.xlsx",
      "prelaunch_test_count":run.testsRun,
      "prelaunch_test_failures":len(run.failures)+len(run.errors),
      "stages":STAGES,"legacy_mapping":SOURCE_MAP,
      "source_roles":{"FinMind":"requires Free/Backer split verified by provenance and tier",
                      "XQ":"legacy independent manually exported raw; no automatic official redownload"},
      "missing_policy":{"source_available_date":"per dataset and official release evidence",
          "empty_archive":"quarantine and classify rather than blindly retry",
          "error_retry":"max 3 exponential backoff, then BLOCKED",
          "schema_value_pit":"adapter and semantic contract fix, no blind redownload"},
      "inventory":audit_inventory({}),
      "admission":{"migration_staging_only":True,
                   "bronze_promotion_approved":False,"silver_production_approved":False,
                   "gold_production_approved":False,"bulk_copy_approved":False},
      "required_evidence":["complete paginated 2000-2026 recursive inventory incl. high-cardinality TDCC",
        "source and destination per-file SHA256 and CRC/format/semantic tests",
        "dataset registry with official historical availability, native units, revised releases and PIT",
        "classification of historical placeholders, canaries, duplicate archives, XQ exports",
        "Drive production writer credentials, quota, fencing, lease and isolated recovery proof",
        "date-dataset coverage denominator from official available dates rather than empty folders",
        "readback of staged copy, idempotent no-overwrite and source unchanged",
        "real Bronze/Silver partition tests with PIT revisions and dependent feature recompute"]}
    (ROOT/"MIGRATION_ARCHITECTURE_GATE.json").write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
    print("MIGRATION_ARCHITECTURE_TESTS="+str(run.testsRun))
    print("MIGRATION_ARCHITECTURE_TEST_FAILURES="+str(len(run.failures)+len(run.errors)))
    print("BULK_COPY_APPROVED=false")
    if not run.wasSuccessful():raise SystemExit(1)
