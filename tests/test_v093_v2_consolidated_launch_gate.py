import unittest
from scripts.v093_v2_consolidated_launch_gate import decide,evidence_from_inventory
class ConsolidatedLaunchGateTests(unittest.TestCase):
    def test_actual_inventory_blocks_production(self):
        x=evidence_from_inventory({"months":322,"counts":{"source_month_pairs":1288,"EMPTY_MONTH_FOLDER":690,"duplicate_names":7}})
        r=decide(x)
        self.assertEqual(r["decision"],"BLOCKED_KEEP_MANUAL_ONLY")
        self.assertIn("no_empty_source_months",r["failed"])
        self.assertIn("cross_system_commit_safe",r["failed"])
    def test_missing_evidence_fail_closed(self):
        self.assertEqual(decide({})["decision"],"BLOCKED_KEEP_MANUAL_ONLY")
    def test_all_explicit_evidence_required(self):
        x={"months":322,"source_month_pairs":1288,"empty_source_months":0,"unresolved_duplicate_names":0,"deep_qa_pass":1288,"pit_verified":True,"numeric_verified":True,"cross_system_commit_safe":True,"durable_resume_all_stages":True,"approved_price_adapter":True,"approved_financial_adapter":True,"approved_chip_adapter":True,"old_writers_quiesced":True}
        self.assertEqual(decide(x)["decision"],"READY_TO_ENABLE_SCHEDULES")
        x["approved_chip_adapter"]=False
        self.assertEqual(decide(x)["decision"],"BLOCKED_KEEP_MANUAL_ONLY")
if __name__=="__main__":unittest.main()
