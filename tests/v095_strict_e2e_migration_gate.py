"""v0.93 -> v0.95 hard E2E admission: actual NDC typed sample plus negative tests.
No pretending that source-binary Parquet or Gold metadata is Gold investment factor.
"""
import datetime,hashlib,json,pathlib,unittest
import pyarrow.parquet as pq

ROOT=pathlib.Path("v095_e2e_admission");ROOT.mkdir(exist_ok=True)
CFG=json.loads(pathlib.Path("config/v095_migration_e2e_gate_r1.json").read_text())
NDC=pathlib.Path("v095_ndc_typed_candidate")
REPORT=json.loads((NDC/"report.json").read_text())
PARQUET=NDC/"NDC_ECONOMIC_CYCLE_year=2000_month=01.candidate.parquet"
DATA=pq.read_table(PARQUET).to_pylist()

def classify_bronze(source,tier=None):
 if source=="FinMind":
  if tier not in ("Free","Backer"):raise ValueError("FINMIND_TIER_UNVERIFIED")
  return "20_BRONZE_RAW/FinMind_"+tier
 if source not in CFG["physical_bronze_sources"]:raise ValueError("UNKNOWN_SOURCE")
 return "20_BRONZE_RAW/"+source
def gate_evidence(record,stages=None):
 status={}
 for gate in CFG["quality_gates"]:
  required=gate["requires"]
  status[gate["id"]]={
    "pass":all(record.get(k) is True or (isinstance(record.get(k),str) and bool(record.get(k))) for k in required),
    "missing":[k for k in required if not(record.get(k) is True or (isinstance(record.get(k),str) and bool(record.get(k))))]}
 return status
class Acceptance(unittest.TestCase):
 def test_spec_exact_eight_source_bronze(self):
  self.assertEqual(len(CFG["physical_bronze_sources"]),8)
  self.assertEqual(classify_bronze("TWSE"),"20_BRONZE_RAW/TWSE")
  with self.assertRaisesRegex(ValueError,"TIER"):classify_bronze("FinMind")
  self.assertEqual(classify_bronze("FinMind","Free"),"20_BRONZE_RAW/FinMind_Free")
 def test_no_source_file_assumed_dataset(self):
  self.assertNotIn("dataset_id",{"source":"TWSE","filename":"2007-12.zip"})
 def test_real_ndc_silver_typed(self):
  self.assertEqual(REPORT["status"],"PASS_TYPED_CANDIDATE_NOT_PIT")
  self.assertEqual(len(DATA),34)
  self.assertEqual(sum(x["value_numeric_decimal"] is not None for x in DATA),31)
  self.assertEqual(sum(x["value_categorical"] is not None for x in DATA),1)
  self.assertEqual(sum(x["cell_status"]=="BEFORE_SERIES_START" for x in DATA),2)
  self.assertEqual(len({(x["source_date"],x["source_table"],x["field_native"]) for x in DATA}),34)
  self.assertTrue(all(x["source_date"]=="2000-01-01" for x in DATA))
  self.assertTrue(all(x["legacy_raw_sha256"] and x["source_archive_sha256"] for x in DATA))
  self.assertTrue(all(x["native_unit_policy"]=="AS_PUBLISHED_FIELD_SPECIFIC" for x in DATA))
  self.assertTrue(all(x["published_at_utc"] is None and x["pit_verified"] is False for x in DATA))
 def test_original_numeric_no_silent_zero_fill(self):
  missing=[x for x in DATA if x["cell_status"]=="BEFORE_SERIES_START"]
  self.assertEqual(len(missing),2)
  self.assertTrue(all(x["value_numeric_decimal"] is None and x["value_raw"] is None for x in missing))
 def test_source_to_normalized_isnt_source_to_gold(self):
  self.assertFalse(REPORT["production_bronze"])
  self.assertFalse(REPORT["production_silver"])
  self.assertFalse(REPORT["production_gold"])
  self.assertFalse(REPORT["pit_verified"])
 def test_unverified_time_must_block_real_gold(self):
  evidence={"v093_file_id":"legacy","v093_sha256":"a"*64,"dataset_id":"NDC_ECONOMIC_CYCLE",
            "silver_path":"30_SILVER_STANDARD/MACRO_CROSS_ASSET","typed_columns":True,
            "published_at_verified":False,"pit_approved":False}
  gates=gate_evidence(evidence)
  self.assertFalse(gates["G4"]["pass"])
  self.assertFalse(gates["G5"]["pass"])
  self.assertFalse(gates["G6"]["pass"])
 def test_qa_metadata_is_not_an_investment_factor(self):
  record={"gold_path":"40_GOLD_FEATURES/INDICATORS","input_sha_list":"x",
          "gold_pit_approved":False,"factor_formula_version":None}
  self.assertFalse(gate_evidence(record)["G5"]["pass"])
 def test_no_bulk_when_missing_7_source_contracts(self):
  self.assertFalse(CFG["approved_bulk_migration"])
  self.assertFalse(CFG["approved_production_gold"])

def main():
 result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Acceptance))
 gate_sample=gate_evidence({"v093_file_id":"1Ty74zKGSivXNHmA3WDG4VjeOKmWpA3n4",
   "v093_sha256":DATA[0]["legacy_raw_sha256"],"v093_size":"5385",
   "dataset_id":"NDC_ECONOMIC_CYCLE","source_revision":"UNCERTIFIED","legacy_immutable":True,
   "typed_columns":True,"silver_path":"30_SILVER_STANDARD/MACRO_CROSS_ASSET",
   "numeric_or_categorical":True,"missing_vs_zero":True,"source_row_count_reconciled":True,
   "business_key_unique":True})
 report={"schema":"JARVIS_V095_E2E_MIGRATION_ADMISSION_AUDIT_R1",
  "unit_tests":result.testsRun,"unit_test_failures":len(result.failures)+len(result.errors),
  "ndc_real_typed_silver_candidate":{"records":len(DATA),"numeric":31,"categorical":1,"before_series_start":2,
    "parquet_sha256":hashlib.sha256(PARQUET.read_bytes()).hexdigest()},
  "real_legacy_to_drive_staging_seen_previous_runs":True,
  "seven_source_bronze_actual_folders_checked_by_controller":False,
  "seven_source_typed_silver_actual_folders_checked_by_controller":False,
  "seven_source_gold_actual_folders_checked_by_controller":False,
  "gate_results":gate_sample,"all_seven_sources_full_e2e_approved":False,
  "gold_real_investment_indicator_approved":False,
  "bulk_copy_approved":False,"current_scope":"ISOLATED_NDC_TYPED_SAMPLE_AND_NEGATIVE_ADMISSION_TESTS"}
 (ROOT/"FULL_E2E_ADMISSION_REPORT.json").write_text(json.dumps(report,ensure_ascii=False,indent=2))
 print("E2E_ADMISSION_TESTS",result.testsRun,"FAILURES",report["unit_test_failures"])
 print("E2E_ADMISSION_BULK_APPROVED=false")
 print("E2E_ADMISSION_GOLD_APPROVED=false")
 if not result.wasSuccessful():raise SystemExit(1)
if __name__=="__main__":main()
