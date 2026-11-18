"""Deterministic R3 dry-run checks; synthetic records only, no Drive writes."""
import unittest
from hashlib import sha256
from scripts.v097_r3_gate_core import (
    Template, evidence_key, check_migration, template_for, match_fields,
    reusable, next_gate, disposition, reconcile, SOURCES, GATES
)
SHA_A = sha256(b"official-byte-stream").hexdigest()
SHA_B = sha256(b"mutated-byte-stream").hexdigest()

class R3GateTests(unittest.TestCase):
    def test_migration_and_provenance_separation(self):
        self.assertEqual(check_migration(source_sha=SHA_A,destination_sha=SHA_A)["status"],"PASS")
        self.assertEqual(check_migration(source_sha=None,destination_sha=SHA_A,direct_download_sha=SHA_A)["status"],"PASS")
        self.assertEqual(check_migration(source_sha=SHA_A,destination_sha=SHA_B)["status"],"HOLD")
        self.assertEqual(check_migration(source_sha=None,destination_sha=SHA_A)["status"],"HOLD")
    def test_historical_template_alias_and_critical_field(self):
        t=Template("TWSE","quotes","twse-v1","2000-01-01","2010-12-31",
                   frozenset({"date","volume","amount"}),frozenset({"memo"}),
                   {"交易股數":"volume","成交金額":"amount"}, "approved-official-reference",True)
        self.assertEqual(template_for([t],"TWSE","quotes","2005-01-01"),t)
        self.assertIsNone(template_for([t],"TWSE","quotes","2012-01-01"))
        self.assertEqual(match_fields(t,["date","交易股數","成交金額","memo"])["status"],"PASS")
        self.assertEqual(match_fields(t,["date","交易股數","count"])["status"],"HOLD")
        candidate=Template("TWSE","quotes","candidate","2011-01-01",None,
                           frozenset({"date"}),official_evidence="",evidence_verified=False)
        self.assertEqual(match_fields(candidate,["date"])["status"],"HOLD")
    def test_era_overlap_blocks(self):
        t1=Template("TWSE","d","a","2000-01-01","2010-12-31",frozenset())
        t2=Template("TWSE","d","b","2010-01-01",None,frozenset())
        with self.assertRaises(ValueError): template_for([t1,t2],"TWSE","d","2010-06-01")
    def test_reuse_and_gate_order(self):
        k=evidence_key("rid",SHA_A,"G2","r3",template_version="twse-v1")
        self.assertTrue(reusable({"evidence_key":k,"status":"PASS","durably_committed":True},k))
        self.assertFalse(reusable({"evidence_key":k,"status":"PASS","durably_committed":False},k))
        self.assertFalse(reusable({"evidence_key":k,"status":"PASS","durably_committed":True},k,False))
        self.assertEqual(next_gate({"G1":"PASS"}),"G2")
        self.assertIsNone(next_gate({"G1":"HOLD"}))
        self.assertEqual(disposition({g:"PASS" for g in GATES},durable_release=False),"PENDING")
        self.assertEqual(disposition({g:"PASS" for g in GATES},durable_release=True),"SILVER_READY")
    def test_70_record_gate_functional(self):
        records=[{"record_id":f"{SOURCES[i%7]}-{i}","source":SOURCES[i%7],"status":"PENDING"} for i in range(70)]
        self.assertEqual(reconcile(records)["count"],70)
    def test_700_record_parallel_failure_isolation(self):
        records=[{"record_id":f"{SOURCES[i%7]}-{i}","source":SOURCES[i%7],
                  "status":"HOLD" if i in (5,25) else "PENDING"} for i in range(700)]
        x=reconcile(records)
        self.assertEqual(x["states"]["HOLD"],2)
        self.assertTrue(all(x["sources"][s] == 100 for s in SOURCES))
        self.assertFalse(x["complete"])
    def test_1000_record_handover_replay(self):
        records=[{"record_id":f"r3-{i}","source":SOURCES[i%7],
                  "status":"SILVER_READY" if i%11 else "HOLD"} for i in range(1000)]
        self.assertEqual(reconcile(records)["count"],1000)
        records.append(dict(records[0]))
        with self.assertRaises(ValueError): reconcile(records)

if __name__=="__main__":
    unittest.main()
